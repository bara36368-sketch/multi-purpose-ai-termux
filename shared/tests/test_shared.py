import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared import mem
from shared.atomic_json import read_json, write_json
from shared.paths import androidllm_dir, shard_dir, state_path


def test_tier_bounds():
    assert mem.tier(5.0) == 5
    assert mem.tier(6.4) == 6
    assert mem.tier(8.2) == 8
    assert mem.tier(11.9) == 10  # 12 requires >= 12
    assert mem.tier(16.5) == 16
    assert mem.tier(4.9) == None
    assert mem.tier(None) == None


def test_resident_and_fit():
    assert mem.resident_gb(7.6) == 3.01
    assert mem.fits(7.6, ram=5.0) is True
    assert mem.fits(14.8, ram=6.0) is False  # 5.53 > 4.8
    assert mem.fits(32.8, ram=12.0) is False  # 11.83 > 10.8
    assert mem.fits(32.8, ram=16.0) is True


def test_atomic_roundtrip(tmp_path):
    p = os.path.join(str(tmp_path), "sub", "state.json")
    write_json(p, {"a": 1, "b": [1, 2]})
    assert read_json(p) == {"a": 1, "b": [1, 2]}
    write_json(p, {"a": 2})
    assert read_json(p) == {"a": 2}
    assert read_json(os.path.join(str(tmp_path), "nope.json")) == {}


def test_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("ANDROIDLLM_DIR", str(tmp_path))
    assert androidllm_dir() == str(tmp_path)
    assert "models" in shard_dir("qwen15")
    assert state_path().startswith(str(tmp_path))
