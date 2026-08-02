"""Tests for cyberdeck.py — module orchestrator (status/doctor/task/link)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cyberdeck as cd


def test_status_table_has_all_modules():
    rows = cd.status_table()
    assert {r["module"] for r in rows} == {m["dir"] for m in cd.MODULES}
    assert all(r["entry_ok"] for r in rows), [r for r in rows if not r["entry_ok"]]


def test_classify_intent_short_video():
    name, module, cmd = cd.classify_intent("make me a short from my vlog")
    assert name == "video"
    assert module == "clip-factory"


def test_classify_intent_phone():
    name, module, _ = cd.classify_intent("whats my battery level")
    assert module == "android-mcp"


def test_classify_intent_learning():
    name, module, _ = cd.classify_intent("remember this, summarize the meeting")
    assert module == "video-brain"


def test_classify_intent_unmatched():
    assert cd.classify_intent("zzz plumbus frobnicate") is None


def test_classify_case_insensitive():
    name, module, _ = cd.classify_intent("MAKE A REEL ABOUT MY TRIP")
    assert module == "clip-factory"


def test_llm_classify_parses(monkeypatch):
    def fake_urlopen(req, timeout=None):
        body = json.dumps({
            "choices": [{"message": {"content": '{"intent": "bench", "reason": "speed"}'}}],
        }).encode("utf-8")

        class R:
            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return R()

    monkeypatch.setattr(urllib_request(), "urlopen", fake_urlopen)
    name, module, _ = cd.llm_classify("how fast is it")
    assert name == "bench"
    assert module == "bench"


def test_cmd_task_llm_fallback(monkeypatch):
    def boom(prompt, env=None, timeout=10.0):
        raise RuntimeError("phone down")

    monkeypatch.setattr(cd, "llm_classify", boom)
    import io
    code = cd.cmd_task(type("A", (), {"prompt": "make a short", "llm": True}), {})
    assert code == 0  # falls back to keywords


def urllib_request():
    import urllib.request
    return urllib.request


def test_doctor_aggregates(monkeypatch):
    calls = []

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=120, env=None):
        calls.append((cmd, cwd))
        return type("P", (), {"returncode": 0, "stdout": "3 passed in 0.1s\n", "stderr": ""})()

    import subprocess
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(cd, "has_tests", lambda m: True)
    results = cd.run_tests(type("A", (), {"timeout": 120})())
    assert len(results) == len(cd.MODULES)
    assert all(r["status"] == "PASS" for r in results)
    assert len(calls) == len(cd.MODULES)


def test_doctor_marks_failure(monkeypatch):
    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=120, env=None):
        return type("P", (), {"returncode": 1, "stdout": "1 failed\n", "stderr": ""})()

    import subprocess
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(cd, "has_tests", lambda m: True)
    results = cd.run_tests(type("A", (), {"timeout": 120})())
    assert any(r["status"] == "FAIL" for r in results)
