"""SRT reading/writing and caption planning (stdlib only)."""
import re

_TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _to_ms(h, m, s, ms):
    return ((int(h) * 3600 + int(m) * 60 + int(s)) * 1000) + int(ms)


def parse_srt(text):
    """Parse SRT -> list of {index, start_ms, end_ms, text}."""
    blocks = re.split(r"\n\s*\n", text.strip())
    out = []
    for b in blocks:
        lines = [l for l in b.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})", lines[1])
        if not m:
            continue
        a, b_ = map(_TS_RE.match, m.groups())
        start = _to_ms(*a.groups())
        end = _to_ms(*b_.groups())
        out.append({"index": len(out) + 1, "start_ms": start, "end_ms": end,
                    "text": " ".join(lines[2:])})
    return out


def _fmt(ms):
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(cues, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, c in enumerate(cues, 1):
            f.write(f"{i}\n{_fmt(c['start_ms'])} --> {_fmt(c['end_ms'])}\n{c['text']}\n\n")


def line_wrap(text, width=42):
    """Wrap captions at word boundaries (no deps, CJK-safe per char)."""
    words = text.split()
    if not words:
        return ""
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def speed_to_duration_ms(text, chars_per_sec=14, min_ms=1200, max_ms=8000):
    """Estimate how long a caption should stay up (reading speed)."""
    return max(min_ms, min(max_ms, int(len(text) / chars_per_sec * 1000)))
