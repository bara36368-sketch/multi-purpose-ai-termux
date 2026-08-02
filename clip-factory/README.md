# clip-factory — CapCut Automation

Batch Shorts/Reels factory: script → TTS → whisper subtitles → VectCut draft
→ render/export. A "director" agent plans cuts, pacing, captions, and
transitions per platform.

## Why

VectCutAPI (2.1k★), capcut-mate (1.5k★), pyCapCut, and AutoFlowCut prove the
sector is hot — and every one stops at "draft generation". The factory
pipeline (content idea → finished video) is the missing layer. Existing
VectCut skill knowledge makes this fast to build.

## Layout (planned)

```
clip-factory/
├── pipeline.py       # idea -> script -> TTS -> subs -> draft -> export
├── director.py       # edit plan (cuts, pacing, captions, transitions)
├── subtitles.py      # whisper SRT -> styled captions
├── vectcut/          # thin client over VectCutAPI (drafts + export)
└── presets/          # per-platform (tiktok/reels/shorts) templates
```

## Design rules

- Idempotent steps with a manifest; re-running a step only redoes what's stale.
- Deterministic director: given the same script, same plan (no LLM flakiness).
- Export via VectCut cloud render; draft files land in CapCut/JianYing local.

## Status

Scaffold — first milestone: script → TTS → SRT → VectCut draft with captions,
end-to-end on one Short.
