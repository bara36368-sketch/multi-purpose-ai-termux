"""Deterministic edit-plan director.

No LLM here by design: the same script always produces the same plan
(milestone-1 scope). Plans are plain dicts, ready for CapCut/VectCut
materials or for a later LLM pass that only tunes numbers.
"""
from subtitles import line_wrap, speed_to_duration_ms

PLATFORMS = {
    "shorts":  {"aspect": "9:16", "max_seconds": 60, "hook_ms": 1800},
    "reels":   {"aspect": "9:16", "max_seconds": 90, "hook_ms": 2000},
    "tiktok":  {"aspect": "9:16", "max_seconds": 60, "hook_ms": 1500},
    "youtube": {"aspect": "16:9", "max_seconds": 600, "hook_ms": 4000},
}


def split_sentences(text):
    out, cur = [], ""
    for part in text.replace("! ", "!<S>").replace("? ", "?<S>").replace(". ", ".<S>").split("<S>"):
        part = part.strip()
        if part:
            out.append(part)
    return out or [text.strip()]


def plan(script, platform="shorts", style="energetic"):
    """script -> {platform, aspect, beats, captions, pacing}.

    beats: per-sentence timeline {start_ms, end_ms, text, emphasis}
    captions: display segments derived from beats
    """
    cfg = PLATFORMS[platform]
    beats, t = [], 0
    for i, s in enumerate(split_sentences(script)):
        dur = speed_to_duration_ms(s)
        emphasis = "hook" if i == 0 else ("payoff" if i == len(split_sentences(script)) - 1 else "body")
        beats.append({"start_ms": t, "end_ms": t + dur, "text": s, "emphasis": emphasis})
        t += dur
    captions = []
    for b in beats:
        wrapped = line_wrap(b["text"]).splitlines()
        per = max(1, len(wrapped))
        chunk = (b["end_ms"] - b["start_ms"]) // per
        for j, w in enumerate(wrapped):
            captions.append({
                "start_ms": b["start_ms"] + j * chunk,
                "end_ms": b["start_ms"] + (j + 1) * chunk,
                "text": w,
                "emphasis": b["emphasis"],
            })
    return {
        "platform": platform,
        "aspect": cfg["aspect"],
        "hook_ms": cfg["hook_ms"],
        "style": style,
        "beats": beats,
        "captions": captions,
        "total_ms": t,
    }
