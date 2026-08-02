# android-mcp — Android MCP Server

Model Context Protocol server exposing **phone capabilities** as MCP tools:
SMS, battery, GPS, clipboard, TTS, notifications, sensors. Any agent
(OpenClaw / Claude Code / Codex / OpenCode) can then control the phone.

## Why

The MCP ecosystem exploded in 2026 (awesome-mcp-servers 82k★, WebMCP
standardizing in Chrome 146) — but there is no phone-capabilities server.
Zero competition, real demand, and the user's phone is already an always-on
server.

## Layout (planned)

```
android-mcp/
├── server.py         # MCP stdio + HTTP transport
├── tools/            # sms, battery, gps, clipboard, tts, sensors, phone
├── auth.py           # token gate for remote transport
└── tests/
```

## Design rules

- stdlib-only (or minimal deps); Termux-API via subprocess where available.
- Explicit permission file per tool: nothing is exposed by default.
- Stdio for local agents, HTTP+token for remote (OpenClaw on another box).

## Status

Working — milestone 1 done: stdio + HTTP transports, JSON-RPC 2.0/MCP
handshake, tools (`battery`, `sms_send`, `clipboard_get`, `tts_say`,
`thermal`, `device_info`), permissions gate, tests 8/8. Termux-API calls
verified only on-device so far.
