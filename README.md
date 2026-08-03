# Multi-Purpose AI Termux

One repo, eight modules — a personal AI stack that turns an Android phone
into a 24/7 self-hosted server and uses it for everything: chat gateway,
local models, benchmarks, video production, memory, and agent tooling.

Built on battle-tested foundations: the [androidllm](https://github.com/bara36368-sketch/androidllm)
layer-streaming inference engine and the `opencode-server-bot` Telegram stack,
both proven on real hardware (4 GB RAM, Helio G85, Termux).

## Modules

| Folder | Module | Status | What it is |
|---|---|---|---|
| `gateway/` | Personal agent gateway | working | Multi-channel agent with androidllm as offline fallback (Router + Telegram channel) |
| `phone-server/` | Termux deploy kit | working | install.sh / run.sh / monitor.sh: 24/7 server + OOM ladder |
| `bench/` | On-device model leaderboard | working | tok/s, tok/J, thermals per SoC; GitHub Pages CI |
| `clip-factory/` | CapCut automation | working | Script → edit plan → SRT → captions → VectCut draft |
| `agent-brain/` | Agent memory layer | working | Sessions → entity graph → cited answers + gap analysis |
| `android-mcp/` | Android MCP server | working | Phone capabilities as MCP tools (stdio + HTTP) |
| `video-brain/` | Video → knowledge | working | SRT index → timestamped cited answers |
| `engine-rs/` | Rust engine hot path | working | PyO3 sampling, bit-equal to numpy (abi3) |

## Quick start

```
python cyberdeck.py up          # status table of all 8 modules
python cyberdeck.py doctor      # run every module's test suite
python cyberdeck.py task "make me a reel from my vlog"
                                # natural-language dispatch -> clip-factory (--llm for phone classification)
python cyberdeck.py task "summarize the meeting" --run
                                # execute the resolved command; journaled to ~/.cyberdeck/sessions.json
python cyberdeck.py sessions    # recent runs (--status done|failed)
python cyberdeck.py redo 3      # re-run a finished session
python cyberdeck.py fleet add g85 http://192.168.1.50:8000 --key sk-x
python cyberdeck.py fleet status --once    # one-shot health table
python cyberdeck.py fleet status           # live watch: up/down flips, model swaps, thermal spikes
python cyberdeck.py link <srt|url>   # video-brain pipeline plan
python cyberdeck.py agent "what should I deploy next?"   # ask agent-01 (sibling repo)
python cyberdeck.py agent --chat     # interactive agent-01 session
python cyberdeck.py swarm "review the gateway for security holes"
                                # 12 role-specialized agents in parallel (lead + 11 roles)
python cyberdeck.py swarm "design the next module" --roles lead architect performance
python cyberdeck.py swarm "quick check" --count 3              # subset
python cyberdeck.py swarm --add-agent "you are the battery-life specialist, watch watts"
                                # create custom agent-02 from a role prompt (auto-numbered)
python cyberdeck.py swarm --add-agent "you hunt data-hygiene rot" --name agent-07
python cyberdeck.py swarm --list-agents                       # registered custom agents
python cyberdeck.py swarm --list-agents --json               # machine-readable
python cyberdeck.py swarm --rm-agent agent-07               # delete a custom agent
```

### Rust fast path (optional)

Intent dispatch, placeholder refusal, session ids/tails and fleet alert
detection run through the `cyberdeck-rs` PyO3 extension when built; the CLI
falls back to pure Python otherwise (no hard dependency).

```
cd cyberdeck-rs && maturin build --release && pip install target/wheels/*.whl
python -c "import cyberdeck as cd; print(cd._HAS_RS)"   # -> True
```

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