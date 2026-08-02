# Cyberdeck

One repo, eight modules — a personal AI stack that turns an Android phone
into a 24/7 self-hosted server and uses it for everything: chat gateway,
local models, benchmarks, video production, memory, and agent tooling.

Built on battle-tested foundations: the [androidllm](https://github.com/bara36368-sketch/androidllm)
layer-streaming inference engine and the `opencode-server-bot` Telegram stack,
both proven on real hardware (4 GB RAM, Helio G85, Termux).

## Modules

| Folder | Module | Status | What it is |
|---|---|---|---|
| `gateway/` | Personal agent gateway | scaffold | Multi-channel (Telegram/WhatsApp/Slack/Discord/Signal) agent with androidllm as offline fallback |
| `phone-server/` | Termux deploy kit | scaffold | One `curl \| bash` to turn any Android phone into a 24/7 AI server |
| `bench/` | On-device model leaderboard | scaffold | CI-measured tok/s, tokens/W, thermals per SoC and model tier |
| `clip-factory/` | CapCut automation | scaffold | Script → TTS → subtitles → VectCut draft → batch Shorts/Reels |
| `agent-brain/` | Agent memory layer | scaffold | Sessions → entity knowledge graph → cited answers with gap analysis |
| `android-mcp/` | Android MCP server | scaffold | Expose phone capabilities (SMS, battery, GPS, TTS) as MCP tools |
| `video-brain/` | Video → knowledge | scaffold | YouTube/podcast/screen-record → transcript → searchable personal brain |
| `engine-rs/` | Rust engine hot path | scaffold | Lean Rust rewrite of the inference hot path (PyO3, bit-equal) |

## Layout conventions

- Each module is self-contained: own README, own deps, own tests, no
  cross-module imports (share via small stdlib-only helpers under `shared/`).
- Modules must run on low-RAM Android/Termux: stdlib-only or minimal deps,
  offline-friendly, no torch.
- Every module keeps a `docs/` folder with its design decisions.

## Quick start

```
# pick a module and dive in
cd gateway && python -m pip install -e . && python gateway.py --help
```

See each module's README for status and first milestones.
