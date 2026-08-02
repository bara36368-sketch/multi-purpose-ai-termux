# engine-rs — Rust Engine Hot Path

Lean Rust rewrite of the androidllm inference hot path: fused layer forward,
head logits, sampling. PyO3 module, bit-equal to the numpy path, booting in
~100 ms and sipping RAM — the foundation for everything else in this repo.

## Why

AURA proved a Rust cognitive core runs on 4 GB phones (45k-line daemon). The
existing `androidllm_rs` PyO3 bits already work; this module hardens and
extends them into a standalone crate with its own benchmarks.

## Layout (planned)

```
engine-rs/
├── src/
│   ├── lib.rs        # PyO3 surface
│   ├── layer.rs      # fused attention + MLP forward
│   ├── head.rs       # final logits
│   ├── sample.rs     # min-p/top-p sampling, seeded RNG
│   └── quant.rs      # Q4 dequant on the fly
├── benches/          # criterion-style timing vs numpy
├── tests/            # bit-equality against androidllm numpy path
└── Cargo.toml
```

## Design rules

- Bit-equal to the numpy reference — verified by CI on every commit.
- No_std-friendly core where possible; `androidllm` stays the numpy fallback.
- Benchmarks run on-device (ARM NEON, aarch64) in `bench/` CI.

## Status

Scaffold — first milestone: layer forward + sampling moved in from
`androidllm_rs`, bit-equality tests green on x86 and aarch64.
