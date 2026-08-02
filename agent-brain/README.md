# agent-brain — Agent Memory Layer

Sessions → entity knowledge graph → cited answers with explicit "what we
don't know" gap analysis. The memory layer your 189-agent setup is missing.

## Why

gbrain (YC's Garry Tan, 27k★ in 3 weeks) proved agents need a brain, not a
chat log. This module is a lean, phone-friendly version: stdlib-only,
file-backed, no heavy vector DB — hybrid keyword + graph traversal instead of
pgvector.

## Layout (planned)

```
agent-brain/
├── ingest.py         # session logs, notes, transcripts -> pages
├── graph.py          # typed edges (works_at, mentioned, replied_to) — zero LLM calls
├── retrieve.py       # keyword + graph-adjacency + source-tier boost
├── answer.py         # synthesis with citations + gap analysis
└── storage/          # JSON pages + edges (append-only, atomic writes)
```

## Design rules

- Zero-LLM graph wiring: edges extracted from wikilink/mention syntax only.
- Honest answers: every reply cites sources and says what it can't confirm.
- Runs on 4 GB phones: no pgvector, no embedding model, no torch.

## Status

Working — milestone 1 done: `ingest.py` (NDJSON/text), `graph.py` (zero-LLM
entity edges), `retrieve.py` (hybrid score + P@5), `answer.py` (CLI with
citations + gaps), tests 6/6.
