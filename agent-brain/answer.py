"""agent-brain CLI: ingest sessions, ask questions.
    python answer.py --ingest sessions.ndjson
    python answer.py --ask "what did alice say about the server?"
    python answer.py --ask "..." --top 5
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graph import Brain  # noqa: E402
from ingest import pages_from_lines  # noqa: E402
from retrieve import answer  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent-brain", description=__doc__)
    ap.add_argument("--dir", default=os.environ.get("BRAIN_DIR", "brain-data"))
    ap.add_argument("--ingest", help="NDJSON or plain session log to ingest")
    ap.add_argument("--ask")
    ap.add_argument("--top", type=int, default=3)
    args = ap.parse_args(argv)

    brain = Brain(args.dir)
    if args.ingest:
        with open(args.ingest, encoding="utf-8") as f:
            lines = f.readlines()
        pages = pages_from_lines(lines)
        n = 0
        for pid, page in pages.items():
            if pid not in brain.pages:
                brain.add_page(page)
                n += 1
        print(f"ingested {n} new pages ({len(brain.pages)} total) from {args.ingest}")
    if args.ask:
        import json
        print(json.dumps(answer(brain, args.ask, top_k=args.top), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
