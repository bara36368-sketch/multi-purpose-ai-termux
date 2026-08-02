import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ask import answer, fmt_timestamp  # noqa: E402
from index import _terms, index_srt, search  # noqa: E402
from transcribe import srt_to_vtt  # noqa: E402

SRT = """1
00:00:00,000 --> 00:00:02,500
the phone runs the qwen15 model locally

2
00:00:02,600 --> 00:00:05,000
kv cache keeps memory small on low ram

3
00:00:05,100 --> 00:00:08,000
benchmark shows zero point seven tokens per second
"""


def _index(tmp_path):
    srt = os.path.join(str(tmp_path), "t.srt")
    open(srt, "w", encoding="utf-8").write(SRT)
    idx = os.path.join(str(tmp_path), "index.json")
    index_srt(srt, "test-video", idx)
    return idx


def test_index_and_search(tmp_path):
    idx = _index(tmp_path)
    index = json.load(open(idx, encoding="utf-8"))
    assert "qwen15" in index
    hits = search(index, "kv cache")
    assert hits and hits[0]["video"] == "test-video"
    assert hits[0]["start_ms"] == 2600


def test_terms():
    assert "tokens" in _terms("0.7 tokens per second, really!")
    assert all(t == t.lower() for t in _terms("MiXeD Case Words"))


def test_answer_citations(tmp_path):
    idx = _index(tmp_path)
    index = json.load(open(idx, encoding="utf-8"))
    a = answer(index, "tokens per second benchmark")
    assert a["known"] is True
    assert any(c["timestamp"] == "0:00:05" for c in a["citations"])
    unknown = answer(index, "quantum teleportation")
    assert unknown["known"] is False


def test_fmt_timestamp():
    assert fmt_timestamp(0) == "0:00:00"
    assert fmt_timestamp(3723000) == "1:02:03"
    assert fmt_timestamp(61000) == "0:01:01"


def test_srt_to_vtt(tmp_path):
    srt = os.path.join(str(tmp_path), "t.srt")
    open(srt, "w", encoding="utf-8").write(SRT)
    vtt = srt_to_vtt(srt)
    body = open(vtt, encoding="utf-8").read()
    assert body.startswith("WEBVTT")
    assert "00:00:00.000" in body
