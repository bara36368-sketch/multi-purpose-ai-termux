"""Bit-equality test: Rust `engine_rs.sample_minp_topk_py` vs a numpy
reference implementing the identical algorithm (SplitMix64 draws, top-k,
min-p, top-p filtering, temperature scaling).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def splitmix64_next(state):
    state = (state + 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & ((1 << 64) - 1)
    return state, (z ^ (z >> 31)) & ((1 << 64) - 1)


def draw_cumulative(cum, state):
    state, draw = splitmix64_next(state)
    u = (draw >> 40) / (1 << 24)
    lo, hi = 0, len(cum)
    while lo < hi:
        mid = (lo + hi) // 2
        if cum[mid] < u:
            lo = mid + 1
        else:
            hi = mid
    return min(lo, len(cum) - 1), state


def sample_ref(logits, temperature, top_p, min_p, top_k, state):
    logits = np.asarray(logits, dtype=np.float32)
    if temperature <= 0.0:
        return int(np.argmax(logits)), state
    scaled = logits / temperature
    m = scaled.max()
    exps = np.exp(scaled.astype(np.float64) - m).astype(np.float32)
    probs = exps / exps.sum()

    max_prob = probs.max()
    probs = probs.copy()
    probs[probs < min_p * max_prob] = 0.0
    if 0 < top_k < len(probs):
        keep = np.argsort(-probs)[:top_k]
        mask = np.zeros(len(probs), dtype=bool)
        mask[keep] = True
        probs[~mask] = 0.0
    if top_p < 1.0:
        order = np.argsort(-probs)
        acc = 0.0
        for i, idx in enumerate(order):
            if i > 0 and acc >= top_p:
                probs[idx] = 0.0
            acc += probs[idx]
    total = probs.sum()
    if total <= 0.0:
        return int(np.argmax(logits)), state
    cum = np.cumsum(probs / total)
    return draw_cumulative(cum.tolist(), state)


def _rust_sample(logits, temperature, top_p, min_p, top_k, state):
    import engine_rs
    return engine_rs.sample_minp_topk_py(
        [float(x) for x in logits], float(temperature), float(top_p),
        float(min_p), int(top_k), int(state))


RNG_STATE = 0x1234ABCD9876EF00
SEED = 7


def _logits(rng, n=64):
    return (rng.standard_normal(n) * 1.5).astype(np.float32)


def test_bit_equal_defaults():
    import engine_rs
    rng = np.random.default_rng(SEED)
    logits = _logits(rng)
    rs = _rust_sample(logits, 0.8, 1.0, 0.0, 0, RNG_STATE)
    ref = sample_ref(logits, 0.8, 1.0, 0.0, 0, RNG_STATE)
    assert rs[0] == ref[0] and rs[1] == ref[1]


def test_bit_equal_top_p_and_min_p():
    import engine_rs
    rng = np.random.default_rng(SEED)
    for logits in (_logits(rng), _logits(rng)):
        rs = _rust_sample(logits, 0.7, 0.9, 0.02, 0, RNG_STATE)
        ref = sample_ref(logits, 0.7, 0.9, 0.02, 0, RNG_STATE)
        assert rs == ref


def test_bit_equal_top_k_and_temperature():
    import engine_rs
    rng = np.random.default_rng(SEED)
    logits = _logits(rng)
    for temp, top_p, min_p, top_k in ((1.0, 0.95, 0.0, 32),
                                      (0.5, 1.0, 0.1, 0),
                                      (2.0, 0.8, 0.05, 16)):
        rs = _rust_sample(logits, temp, top_p, min_p, top_k, RNG_STATE)
        ref = sample_ref(logits, temp, top_p, min_p, top_k, RNG_STATE)
        assert rs == ref, (temp, top_p, min_p, top_k)


def test_greedy_temperature_zero():
    import engine_rs
    logits = [0.1, -0.5, 0.9, 0.0]
    rs = _rust_sample(logits, 0.0, 1.0, 0.0, 0, RNG_STATE)
    assert rs[0] == 2


def test_all_filtered_falls_back_to_argmax():
    import engine_rs
    logits = [1.0, 2.0, 3.0]
    rs = _rust_sample(logits, 0.8, 1.0, 0.99, 0, RNG_STATE)
    assert rs[0] == 2
