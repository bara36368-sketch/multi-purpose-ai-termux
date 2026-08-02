import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from director import plan  # noqa: E402
from subtitles import line_wrap, parse_srt, speed_to_duration_ms, write_srt  # noqa: E402
from vectcut import OfflineVectCut  # noqa: E402


def test_split_sentences_and_beats():
    p = plan("Hook line! Body sentence here. Final payoff?")
    assert len(p["beats"]) == 3
    assert p["beats"][0]["emphasis"] == "hook"
    assert p["beats"][-1]["emphasis"] == "payoff"
    assert p["aspect"] == "9:16"


def test_plan_deterministic():
    a = plan("Same script every time.", platform="tiktok")
    b = plan("Same script every time.", platform="tiktok")
    assert a == b


def test_platform_caps():
    assert plan("x", platform="youtube")["total_ms"] <= 600 * 1000 + 8000


def test_srt_roundtrip():
    cues = [{"start_ms": 0, "end_ms": 1000, "text": "hello world"},
            {"start_ms": 1500, "end_ms": 2500, "text": "second cue"}]
    write_srt(cues, os.path.join(os.path.dirname(__file__), "t.srt"))
    parsed = parse_srt(open(os.path.join(os.path.dirname(__file__), "t.srt"), encoding="utf-8").read())
    os.unlink(os.path.join(os.path.dirname(__file__), "t.srt"))
    assert len(parsed) == 2
    assert parsed[0]["text"] == "hello world"
    assert parsed[1]["start_ms"] == 1500


def test_line_wrap_and_duration():
    w = line_wrap("a " * 100, width=20)
    assert all(len(l) <= 20 for l in w.splitlines())
    assert 1200 <= speed_to_duration_ms("hi") <= 8000
    assert speed_to_duration_ms("x" * 500) == 8000


def test_offline_draft(tmp_path):
    vc = OfflineVectCut(str(tmp_path))
    d = vc.create_draft("test", "9:16")
    vc.add_caption_material(d["id"], "cap", 0, 1000)
    r = vc.export(d["id"])
    import json
    saved = json.load(open(r["path"], encoding="utf-8"))
    assert saved["materials"][0]["text"] == "cap"
