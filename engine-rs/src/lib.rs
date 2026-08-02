//! engine-rs: sampling hot path for androidllm.
//!
//! Exposes seeded top-p / min-p sampling with a deterministic SplitMix64
//! RNG so draws are bit-identical to the numpy reference implementation in
//! tests (see tests/test_sampling.py). PyO3 surface is deliberately small:
//! one module `engine_rs` with `sample_minp_topk_py`.

use pyo3::prelude::*;

/// SplitMix64: small, fast, deterministic; numpy's default_rng(seed) seeds a
/// PCG64 — for bit-equality we pass the *state* around instead of reseeding,
/// so callers keep numpy's RNG and feed us per-step u64 draws.
#[derive(Clone, Copy)]
struct SplitMix64(u64);

impl SplitMix64 {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E3779B97F4A7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
        z ^ (z >> 31)
    }
}

/// Weighted index draw from cumulative probabilities with a u64 state.
/// `cum`: cumulative sums, `[p0, p0+p1, ..., 1.0]`; returns the chosen index.
fn draw_cumulative(cum: &[f32], rng: &mut SplitMix64) -> usize {
    let u = (rng.next() >> 40) as f32 / (1u64 << 24) as f32; // [0, 1)
    let mut lo = 0usize;
    let mut hi = cum.len();
    while lo < hi {
        let mid = (lo + hi) / 2;
        if cum[mid] < u {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    lo.min(cum.len() - 1)
}

/// Sample with top-p (nucleus) + min-p filtering, then optional temperature.
/// Returns (index, new_state).
#[pyfunction]
fn sample_minp_topk_py(
    logits: Vec<f32>,
    temperature: f32,
    top_p: f32,
    min_p: f32,
    top_k: usize,
    rng_state: u64,
) -> PyResult<(usize, u64)> {
    let mut rng = SplitMix64(rng_state);
    let n = logits.len();
    if n == 0 {
        return Err(pyo3::exceptions::PyValueError::new_err("empty logits"));
    }
    if temperature <= 0.0 {
        // argmax (temperature 0 == greedy)
        let idx = logits
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0);
        return Ok((idx, rng.0));
    }
    let t = temperature;
    let scaled: Vec<f32> = logits.iter().map(|l| l / t).collect();
    let max = scaled.iter().cloned().fold(f32::NEG_INFINITY, f32::max);
    let exps: Vec<f32> = scaled.iter().map(|l| ((l - max) as f64).exp() as f32).collect();
    let sum: f32 = exps.iter().sum();
    let mut probs: Vec<f32> = exps.iter().map(|e| e / sum).collect();

    // min-p: drop everything below min_p * max_prob
    let max_prob = probs.iter().cloned().fold(0.0f32, f32::max);
    let min_threshold = min_p * max_prob;
    for p in probs.iter_mut() {
        if *p < min_threshold {
            *p = 0.0;
        }
    }
    // top-k: keep top-k mass
    if top_k > 0 && top_k < probs.len() {
        let mut order: Vec<usize> = (0..probs.len()).collect();
        order.sort_by(|&a, &b| probs[b].partial_cmp(&probs[a]).unwrap());
        for i in order.iter().skip(top_k) {
            probs[*i] = 0.0;
        }
    }
    // top-p: include most-likely until cumulative >= top_p
    if top_p < 1.0 {
        let mut order: Vec<usize> = (0..probs.len()).collect();
        order.sort_by(|&a, &b| probs[b].partial_cmp(&probs[a]).unwrap());
        let mut acc = 0.0f32;
        for (i, &idx) in order.iter().enumerate() {
            if i > 0 && acc >= top_p {
                probs[idx] = 0.0;
            }
            acc += probs[idx];
        }
    }
    let total: f32 = probs.iter().sum();
    if total <= 0.0 {
        // all filtered -> fall back to argmax
        let idx = logits
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .map(|(i, _)| i)
            .unwrap_or(0);
        return Ok((idx, rng.0));
    }
    let mut cum = Vec::with_capacity(probs.len());
    let mut acc = 0.0f32;
    for p in probs.iter() {
        acc += p / total;
        cum.push(acc);
    }
    let idx = draw_cumulative(&cum, &mut rng);
    Ok((idx, rng.0))
}

#[pymodule]
fn engine_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sample_minp_topk_py, m)?)?;
    Ok(())
}
