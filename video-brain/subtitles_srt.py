"""Minimal SRT parser shared by video-brain modules (no deps)."""
import re

_TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _to_ms(g):
    h, m, s, ms = g
    return ((int(h) * 3600 + int(m) * 60 + int(s)) * 1000) + int(ms)


def parse_srt(text):
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})", lines[1])
        if not m:
            continue
        a, b = map(_TS_RE.match, m.groups())
        out.append({"index": len(out) + 1, "start_ms": _to_ms(a.groups()),
                    "end_ms": _to_ms(b.groups()), "text": " ".join(lines[2:])})
    return out
