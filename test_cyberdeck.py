"""Tests for cyberdeck.py — module orchestrator (status/doctor/task/link)."""
import json
import os
import subprocess
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
    code = cd.cmd_task(type("A", (), {"prompt": "make a short", "llm": True,
                                      "run": False, "timeout": 10}), {})
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


# ------------------------------------------------------------------ sessions

def test_session_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "SESSIONS_PATH", str(tmp_path / "sessions.json"))
    s = cd.add_session("make a short", "video", "clip-factory", "echo hi")
    assert s["id"] == 1 and s["status"] == "running"
    cd.update_session(s, status="done", exit_code=0, duration_ms=10)
    loaded = cd.load_sessions()
    assert len(loaded) == 1
    assert loaded[0]["status"] == "done"
    s2 = cd.add_session("battery", "phone", "android-mcp", "echo bye")
    assert s2["id"] == 2  # monotonic ids


def test_session_persists_across_load(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "SESSIONS_PATH", str(tmp_path / "s.json"))
    cd.add_session("p", "learn", "video-brain", "true")
    assert cd.load_sessions()[0]["prompt"] == "p"


def test_has_placeholders():
    assert cd.has_placeholders('python clip-factory/pipeline.py "topic"')
    assert not cd.has_placeholders("python bench/runner.py --model x")


def test_run_command_ok_and_fail():
    rc, out = cd.run_command("echo hello", timeout=10)
    assert rc == 0 and "hello" in out
    rc, _ = cd.run_command("python -c \"import sys; sys.exit(3)\"", timeout=10)
    assert rc == 3


def test_redo_refuses_placeholder_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cd, "SESSIONS_PATH", str(tmp_path / "s.json"))
    cd.add_session("p", "video", "clip-factory", 'python pipeline.py "topic"')
    assert cd.cmd_redo(type("A", (), {"id": 1, "timeout": 10})) == 3
    assert "refusing" in capsys.readouterr().out


def test_task_run_records_session(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "SESSIONS_PATH", str(tmp_path / "s.json"))
    monkeypatch.setattr(cd, "classify_intent",
                        lambda p: ("test", "shared", "echo task-ok"))
    code = cd.cmd_task(type("A", (), {"prompt": "go", "llm": False, "run": True, "timeout": 10}))
    assert code == 0
    s = cd.load_sessions()[0]
    assert s["status"] == "done" and s["exit_code"] == 0
    assert "task-ok" in s["output_tail"]


# ------------------------------------------------------------------ fleet

def test_fleet_defaults_to_local(monkeypatch):
    monkeypatch.setattr(cd, "FLEET_PATH", str(monkeypatch_fail_path()))
    env = {"ANDROIDLLM_URL": "http://10.0.0.5:9000"}
    fleet = cd.load_fleet(env)
    assert fleet == [{"name": "local", "url": "http://10.0.0.5:9000", "key": ""}]


def monkeypatch_fail_path():
    import tempfile
    return os.path.join(tempfile.gettempdir(), "cyberdeck_nonexistent_fleet.json")


def test_fleet_load_and_add(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "FLEET_PATH", str(tmp_path / "fleet.json"))
    assert cd.load_fleet() == [{"name": "local", "url": "http://127.0.0.1:8000", "key": ""}]
    cd.cmd_fleet(type("A", (), {"fleet_cmd": "add", "name": "g85",
                                "url": "http://10.0.0.5:8000", "key": "sk-x"}), {})
    fleet = cd.load_fleet()
    assert fleet[-1] == {"name": "g85", "url": "http://10.0.0.5:8000", "key": "sk-x"}
    assert fleet[0]["name"] == "local"  # add appends, never drops existing


def test_probe_phone_up_and_down(monkeypatch):
    import json as _json

    def fake_urlopen(req, timeout=None):
        if "downhost" in req.full_url:
            raise OSError("connection refused")
        body = _json.dumps({"model": "qwen3-4b", "ram_gb": 8}).encode()

        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return body

        return R()

    monkeypatch.setattr(urllib_request(), "urlopen", fake_urlopen)
    up = cd.probe_phone({"name": "g85", "url": "http://up:8000"})
    assert up["status"] == "UP" and up["model"] == "qwen3-4b" and up["latency_ms"] >= 0
    down = cd.probe_phone({"name": "old", "url": "http://downhost:8000"})
    assert down["status"] == "DOWN"


# ------------------------------------------------------------------ rust parity
# These only assert when the PyO3 extension is built; the fallback path is
# covered by the tests above, so the suite stays green either way.

def test_rust_classify_matches_python():
    if not cd._HAS_RS:
        return
    for prompt in ("make me a reel from my vlog", "whats my battery level",
                   "remember this, summarize the meeting", "zzz plumbus frobnicate",
                   "MAKE A REEL ABOUT MY TRIP"):
        assert cd.classify_intent(prompt) == cd._py_classify_intent(prompt)


def test_rust_placeholders_match_python():
    if not cd._HAS_RS:
        return
    for cmd in ('python clip-factory/pipeline.py "topic"', "python bench/runner.py --model <id>",
                "echo hi", "start android-mcp/server.py"):
        assert cd.has_placeholders(cmd) == cd._py_has_placeholders(cmd)


def test_rust_tail_matches_python():
    if not cd._HAS_RS:
        return
    for text, n in (("hello world", 5), ("hello world", 1200), ("", 5),
                    ("héllo wörld", 6), ("  padded  ", 3), ("x", 0)):
        assert cd._tail(text, n) == cd._py_tail(text, n)


def test_rust_next_id_matches_python():
    if not cd._HAS_RS:
        return
    assert cd._RS.next_id([]) == 1
    assert cd._RS.next_id([{"id": 1}]) == 2
    assert cd._RS.next_id([{"id": 1}, {"id": 7}]) == 8


def test_rust_fleet_alerts_match_python():
    if not cd._HAS_RS:
        return
    prev = [{"name": "g85", "status": "UP", "model": "qwen3-4b"}]
    cur_swap = [{"name": "g85", "status": "UP", "model": "qwen3-8b"}]
    cur_down = [{"name": "g85", "status": "DOWN", "error": "x"}]
    assert cd.fleet_alerts(prev, cur_swap) == cd._py_fleet_alerts(prev, cur_swap)
    assert cd.fleet_alerts(prev, cur_down) == cd._py_fleet_alerts(prev, cur_down)
    assert cd.fleet_alerts(prev, prev) == []


def test_swarm_spawns_agents_with_roles(tmp_path, monkeypatch):
    spawned = []

    class FakeProc:
        def __init__(self, cmd, env=None, cwd=None, stdout=None, stderr=None, text=None, encoding=None, errors=None):
            spawned.append((cmd, env))
            self.returncode = 0

        def communicate(self, timeout=None):
            return "agent output here", None

    monkeypatch.setattr(subprocess, "Popen", FakeProc)
    monkeypatch.setattr(cd, "agent01_path", lambda: "agent01.py")
    monkeypatch.setattr(cd, "CYBER_HOME", str(tmp_path))
    code = cd.cmd_swarm(type("A", (), {
        "task": "review the fleet", "count": 3,
        "roles": ["lead", "architect", "security"],
        "timeout": 60, "no_learn": False}))
    assert code == 0
    assert len(spawned) == 3
    roles = [e.get("AGENT01_ROLE") for _, e in spawned]
    assert roles == ["lead", "architect", "security"]
    import glob
    reports = glob.glob(str(tmp_path / "swarm" / "*.json"))
    assert len(reports) == 1
    data = json.load(open(reports[0], encoding="utf-8"))
    assert data["task"] == "review the fleet"
    assert len(data["agents"]) == 3
