# video-brain — Video → Knowledge

YouTube / podcast / screen-recording → transcript → searchable personal brain
with citations. Productized version of the watch-video pipeline: fetch,
transcribe, chunk, index, answer — offline-first.

## Why

The multimodal wave is real (Deep-Live-Cam 80k★, video agents everywhere),
but "your video content becomes a searchable, citable knowledge base" is a
niche nobody owns. It pairs naturally with `agent-brain/` for storage and
`clip-factory/` for producing clips from findings.

## Layout (planned)

```
video-brain/
├── fetch.py          # yt-dlp / direct URLs, audio extraction
├── transcribe.py     # whisper small on-device (or cloud fallback)
├── chunk.py          # speaker-aware chunking + titles
├── index.py          # keyword index + timestamps (ffmpeg/ffprobe)
├── ask.py            # Q&A with timestamps + transcript citations
└── tests/
```

## Design rules

- Every answer carries `(video, timestamp, transcript quote)` — no guesses.
- Offline path: whisper on-device; cloud path only when the user opts in.
- Storage shared with `agent-brain/` (pages + edges), never duplicated.

## Status

Working — milestone 1 done: SRT/VTT passthrough, chunking + timestamped
inverted index, `ask.py` with cited answers, tests 5/5 (offline, no
network). yt-dlp/whisper wiring needs an on-device run.
