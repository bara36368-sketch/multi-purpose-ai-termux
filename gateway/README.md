# gateway — Personal Agent Gateway

Multi-channel personal AI assistant (Telegram / WhatsApp / Slack / Discord /
Signal) with the local `androidllm` server as the **offline fallback
provider**: cloud APIs when they're up, the phone's own model when they're
down.

## Why

OpenClaw-style personal agents are the fastest-growing corner of 2026 open
source, but none pair a multi-channel gateway with a Termux-hosted offline
model. This module is that pairing, on hardware that's already proven.

## Layout (planned)

```
gateway/
├── gateway.py        # core loop: channel events -> router -> providers
├── providers/        # cloud providers + androidllm local fallback
├── channels/         # telegram, whatsapp, slack, discord, signal
├── router.py         # cloud -> local fallback with health checks
└── tests/
```

## Design rules

- Provider-agnostic: any OpenAI-compatible endpoint, local or cloud.
- Fallback chain: `cloud → androidllm → polite error`. Health-check androidllm
  (`/health`) before routing, no dead waits.
- Session/memory glue delegated to `agent-brain/` via stdlib-only JSON files.

## Status

Scaffold — roadmap:
1. Telegram channel + androidllm fallback (reuse `opencode-server-bot` knowledge)
2. WhatsApp channel
3. Slack/Discord/Signal
4. Offline-mode telemetry (what got served locally vs cloud)
