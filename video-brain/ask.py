"""ask.py — Q&A over the indexed transcript library with timestamp citations.
    python ask.py --index brain-index.json "what did they say about kv cache?"
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import search  # noqa: E402


def fmt_timestamp(ms):
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s = rem // 1000
    return f"{h}:{m:02d}:{s:02d}"


def answer(index, query, limit=5):
    hits = search(index, query, limit=limit)
    if not hits:
        return {"answer": "Nothing on that in the transcript library.",
                "citations": [], "gaps": [query], "known": False}
    lines, citations = [], []
    for h in hits:
        stamp = fmt_timestamp(h["start_ms"])
        citations.append({"video": h["video"], "timestamp_ms": h["start_ms"],
                          "timestamp": stamp, "snippet": h["snippet"]})
        lines.append(f"[{stamp} {h['video']}] {h['snippet']}")
    return {"answer": "Relevant moments:\n" + "\n".join(lines),
            "citations": citations, "gaps": [], "known": True}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="video-brain", description=__doc__)
    ap.add_argument("--index", default="brain-index.json")
    ap.add_argument("query", nargs="+")
    args = ap.parse_args(argv)
    with open(args.index, encoding="utf-8") as f:
        index = json.load(f)
    print(json.dumps(answer(index, " ".join(args.query)), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
