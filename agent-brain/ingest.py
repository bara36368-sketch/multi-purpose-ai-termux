"""Ingest session logs/notes into brain pages.

Input format (one JSON object per line, NDJSON)::
    {"ts": "...", "chat": "ch1", "who": "alice", "text": "..."}
or plain text lines: "alice: hello".

Pages are the unit the graph indexes: one page per (chat, session) with the
participants, a summary, and linked entities.
"""
import json
import re

_LINE_RE = re.compile(r"^(\w+)[:]\s*(.+)$")


def parse_line(line):
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
        return {"ts": obj.get("ts"), "chat": obj.get("chat", "default"),
                "who": obj.get("who", "anon"), "text": obj.get("text", "")}
    except json.JSONDecodeError:
        m = _LINE_RE.match(line)
        if m:
            return {"ts": None, "chat": "default", "who": m.group(1),
                    "text": m.group(2)}
        return {"ts": None, "chat": "default", "who": "anon", "text": line}


def extract_entities(text):
    """Simple entity extraction: @mentions, [[wikilinks]], ALLCAPS names."""
    out = set()
    out.update(re.findall(r"@([A-Za-z0-9_]+)", text))
    out.update(re.findall(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", text))
    out.update(re.findall(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", text))
    return sorted(out)


def pages_from_lines(lines, chat="default"):
    """Group parsed messages into pages keyed by 30-minute sessions."""
    msgs = [m for m in (parse_line(l) for l in lines) if m]
    pages, cur, cur_key = {}, [], None
    for m in msgs:
        key = m.get("ts", "")[:10] if m.get("ts") else "session-1"
        if cur_key is None:
            cur_key = key
        if key != cur_key and cur:
            pid = f"{chat}:{cur_key}"
            pages[pid] = _make_page(pid, chat, cur)
            cur = []
        cur.append(m)
        cur_key = key
    if cur:
        pid = f"{chat}:{cur_key}"
        pages[pid] = _make_page(pid, chat, cur)
    return pages


def _make_page(pid, chat, msgs):
    text = " ".join(m["text"] for m in msgs if m.get("text"))
    return {
        "id": pid, "chat": chat, "messages": len(msgs),
        "participants": sorted({m.get("who", "anon") for m in msgs}),
        "entities": extract_entities(text),
        "text": text,
    }
