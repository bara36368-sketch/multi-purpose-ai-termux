"""Chunking + timestamped keyword index over transcripts.

Index is an inverted map: term -> [{video, start_ms, snippet}]. Pure
stdlib JSON, append-only per video.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subtitles_srt import parse_srt  # noqa: E402  (shared parser, no deps)


def index_srt(srt_path, video_id, index_path, window_chars=180):
    """Merge SRT cues into windows, index terms, append to index_path."""
    cues = parse_srt(open(srt_path, encoding="utf-8").read())
    index = {}
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)
    for cue in cues:
        for term in _terms(cue["text"]):
            hits = index.setdefault(term, [])
            entry = {"video": video_id, "start_ms": cue["start_ms"],
                     "snippet": cue["text"][:window_chars]}
            if not hits or hits[-1]["start_ms"] != entry["start_ms"]:
                hits.append(entry)
    os.makedirs(os.path.dirname(index_path) or ".", exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    return index


def _terms(text):
    return [t.lower() for t in re.findall(r"[A-Za-z0-9_]{3,}", text) if not t.isdigit()]


def search(index, query, limit=8):
    """query terms -> ranked (score, video, start_ms, snippet) hits."""
    terms = [t.lower() for t in re.findall(r"[A-Za-z0-9_]{3,}", query)]
    scores = {}
    for t in terms:
        for hit in index.get(t, []):
            key = (hit["video"], hit["start_ms"])
            scores.setdefault(key, {"score": 0, **hit})
            scores[key]["score"] += 1
    out = sorted(scores.values(), key=lambda h: h["score"], reverse=True)
    return out[:limit]
