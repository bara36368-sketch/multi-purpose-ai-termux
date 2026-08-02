import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrics import (summarize, temp_delta, timed, tokens_per_joule,
                     tokens_per_second, watt_seconds)


def test_tps():
    assert tokens_per_second(100, 10) == 10.0
    assert tokens_per_second(100, 0) == 0.0
    assert tokens_per_second(0, 5) == 0.0


def test_tokens_per_joule():
    assert tokens_per_joule(100, 10) == 10.0
    assert tokens_per_joule(100, 0) is None


def test_watt_seconds():
    assert watt_seconds(1000, 3.85) == 13860.0
    assert watt_seconds(500, 4.2) == 7560.0


def test_temp_delta():
    assert temp_delta(40.0, 43.5) == 3.5
    assert temp_delta(None, 43.5) is None


def test_timed():
    calls = []

    def work():
        calls.append(1)
        return "x"

    results, seconds = timed(work, reps=3)
    assert results == ["x", "x", "x"]
    assert seconds >= 0


def test_summarize_shape():
    r = summarize({"tokens": 200, "seconds": 20.0, "joules": 1000.0,
                   "temp_before_c": 38.0, "temp_after_c": 41.0,
                   "model": "qwen15", "device": "g85", "ram_tier_gb": 4,
                   "timestamp": 1})
    assert r["tokens_per_sec"] == 10.0
    assert r["tokens_per_joule"] == 0.2
    assert r["temp_delta_c"] == 3.0
    assert r["model"] == "qwen15"
