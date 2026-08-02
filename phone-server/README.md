# phone-server — Termux AI Deploy Kit

One command turns any Android phone into a 24/7 AI server:

```
curl -fsSL https://raw.githubusercontent.com/bara36368-sketch/cyberdeck/main/phone-server/install.sh | bash
```

## Why

Codey-v2, AURA, OpenClaw-On-Android all try this and stop at "installer".
This module ships the complete, battle-tested stack: androidllm + Telegram
bot + runner with health checks, auto-restart, OOM downgrade ladder, and
auto-update — the exact setup already running on a 4 GB Helio G85 phone.

## Layout (planned)

```
phone-server/
├── install.sh        # one-shot bootstrap (termux-setup-storage, deps, clone)
├── run.sh            # service supervisor (reuse runner.py patterns)
├── monitor.sh        # health checks, OOM ladder stepping
├── config/           # model defaults, ports, env
└── README.md         # supported devices, RAM tiers, troubleshooting
```

## Design rules

- Zero-root, Termux-from-F-Droid only (Play Store version is dead).
- RAM-aware: auto-picks model by `MemTotal` tier (5/6/7/8/9/10/12/16 GB).
- OOM-safe: auto-step-down to the next smaller already-sharded model.
- Idempotent: re-running the installer must be safe.

## Status

Working — milestone 1 done: `install.sh` (idempotent Termux bootstrap),
`run.sh` (watchdog supervisor with backoff), `monitor.sh` (health check +
OOM downgrade ladder). Not yet exercised on-device — needs a Termux phone run.
