# bench — On-Device Model Leaderboard

CI-measured tok/s, tokens/W, and thermals for sharded models per SoC and RAM
tier, published as a GitHub Pages leaderboard. The androidllm catalog (5-16 GB
tiers) is the data source.

## Why

OfflineLLM, zuza, and ollama-termux all publish hand-written RAM tables —
nobody publishes *measured* numbers. If you're telling users "expect ~0.7
tok/s on a G85", prove it with CI runs on real devices.

## Layout (planned)

```
bench/
├── runner.py         # loads model tier, warms up, times prompt+gen, reads thermals
├── metrics.py        # tok/s, tokens/J (battery drain), temp delta
├── targets/          # per-device profiles (g85, tensor-g4, sd-8elite, ...)
├── results/          # gitignored JSON + PNG charts
└── .github/workflows/bench.yml   # scheduled runs, pushes leaderboard
```

## Design rules

- Offline-measurable: every metric comes from the device itself
  (`/sys/class/power_supply`, CPUfreq, wall clock).
- Deterministic prompts: fixed seeds, fixed contexts, N repetitions.
- Charts committed to `gh-pages` via CI; results JSON retained for diffs.

## Status

Working — milestone 1 done: `runner.py` (stream/non-stream, JSON report),
`metrics.py` (tok/s, tok/J, temp delta), device profiles, GitHub Pages
workflow. Tests 6/6. On-device numbers pending a G85 run.
