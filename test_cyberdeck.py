"""Tests for cyberdeck.py — module orchestrator (status/doctor/task/link)."""
import glob
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
    monkeypatch.setattr(cd, "_custom_swarm_agents", lambda: [])
    monkeypatch.setattr(cd, "CYBER_HOME", str(tmp_path))
    code = cd.cmd_swarm(type("A", (), {
        "task": "review the fleet", "count": 3,
        "roles": ["lead", "architect", "security"],
        "timeout": 60, "no_learn": False,
        "list_agents": False, "json": False, "add_agent": None,
        "name": None, "no_swarm": False, "rm_agent": None}))
    assert code == 0
    assert len(spawned) == 3
    roles = [e.get("AGENT01_ROLE") for _, e in spawned]
    assert roles == ["lead", "architect", "security"]
    reports = glob.glob(str(tmp_path / "swarm" / "*.json"))
    assert len(reports) == 1
    data = json.load(open(reports[0], encoding="utf-8"))
    assert data["task"] == "review the fleet"
    assert len(data["agents"]) == 3


def test_swarm_includes_custom_agents(tmp_path, monkeypatch):
    spawned = []

    class FakeProc:
        def __init__(self, cmd, env=None, cwd=None, stdout=None, stderr=None, text=None, encoding=None, errors=None):
            spawned.append((cmd, env))
            self.returncode = 0

        def communicate(self, timeout=None):
            return "custom agent output", None

    monkeypatch.setattr(subprocess, "Popen", FakeProc)
    monkeypatch.setattr(cd, "agent01_path", lambda: "agent01.py")
    monkeypatch.setattr(cd, "CYBER_HOME", str(tmp_path))
    monkeypatch.setattr(cd, "_custom_swarm_agents",
                        lambda: [("agent-02", "battery-life specialist")])
    code = cd.cmd_swarm(type("A", (), {
        "task": "review the fleet", "count": 3,
        "roles": ["lead", "architect", "security"],
        "timeout": 60, "no_learn": False,
        "list_agents": False, "json": False, "add_agent": None,
        "name": None, "no_swarm": False, "rm_agent": None}))
    assert code == 0
    roles = [e.get("AGENT01_ROLE") for _, e in spawned]
    assert roles == ["lead", "architect", "security", "agent-02"]
    data = json.load(open(glob.glob(str(tmp_path / "swarm" / "*.json"))[0], encoding="utf-8"))
    assert data["agents"][-1]["agent"] == "agent-02"
    assert data["agents"][-1]["role"] == "battery-life specialist"


def test_swarm_agent_mgr_forwards(monkeypatch):
    calls = []
    monkeypatch.setattr(cd, "agent01_path", lambda: "agent01.py")
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, env=None, cwd=None: (calls.append((cmd, cwd)) or type(
            "P", (), {"returncode": 0})()))
    arc_ = type("A", (), {
        "list_agents": True, "json": False, "add_agent": None, "name": None,
        "no_swarm": False, "rm_agent": None, "task": None, "count": 3,
        "roles": None, "timeout": 60, "no_learn": False})
    assert cd.cmd_swarm(arc_) == 0
    cmd, cwd = calls[0]
    assert cmd[0] == sys.executable
    assert cmd[-2:] == ["agent01.py", "--agents"]


def test_swarm_agent_mgr_add_agent(monkeypatch):
    calls = []
    monkeypatch.setattr(cd, "agent01_path", lambda: "agent01.py")
    monkeypatch.setattr(
        subprocess, "run",
        lambda cmd, env=None, cwd=None: (calls.append(cmd) or type(
            "P", (), {"returncode": 0})()))
    args = type("A", (), {
        "list_agents": False, "json": False, "add_agent": "be the battery guy",
        "name": "agent-02", "no_swarm": False, "rm_agent": None,
        "task": None, "count": 3, "roles": None, "timeout": 60, "no_learn": False})
    assert cd.cmd_swarm(args) == 0
    assert calls[-1][0] == sys.executable
    assert calls[-1][1:] == ["agent01.py", "--add-agent", "be the battery guy",
                             "--name", "agent-02"]


# ------------------------------------------------------------------ keys

def test_mask_key_never_leaks():
    assert cd.mask_key("sk-1234567890abcd") == "...abcd"
    assert "sk-1234567890abcd" not in cd.mask_key("sk-1234567890abcd")
    assert cd.mask_key("") == ""
    assert cd.mask_key("abc") == "****"


def test_keys_vault_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "KEYS_PATH", str(tmp_path / "keys.json"))
    cd.cmd_keys(type("A", (), {"keys_cmd": "add", "provider": "groq", "key": "sk-groq-1"}))
    assert cd.load_keys() == {"groq": "sk-groq-1"}
    assert cd.resolve_key("groq") == "sk-groq-1"
    assert cd.cmd_keys(type("A", (), {"keys_cmd": "rm", "provider": "groq"})) == 0
    assert cd.load_keys() == {}


def test_keys_unknown_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(cd, "KEYS_PATH", str(tmp_path / "keys.json"))
    assert cd.cmd_keys(type("A", (), {"keys_cmd": "add", "provider": "nope", "key": "x"})) == 2


def test_resolve_key_env_falls_back_to_vault(monkeypatch):
    monkeypatch.setattr(cd, "KEYS_PATH", str(monkeypatch_fail_path()))
    monkeypatch.setenv("GROQ_API_KEY", "env-groq-9")
    assert cd.resolve_key("groq") == "env-groq-9"


def test_check_key_missing(monkeypatch):
    monkeypatch.setattr(cd, "KEYS_PATH", str(monkeypatch_fail_path()))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    ok, detail = cd.check_key("groq")
    assert ok == "missing"
    assert "GROQ_API_KEY" in detail


def test_check_key_auth_and_429(monkeypatch):
    monkeypatch.setattr(cd, "KEYS_PATH", str(monkeypatch_fail_path()))
    monkeypatch.setenv("GROQ_API_KEY", "sk-test")

    def fake_urlopen(req, timeout=None):
        import urllib.error
        if req.full_url.endswith("/20"):
            raise urllib.error.HTTPError(req.full_url, 429, "Rate limited", None, None)
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", None, None)

    monkeypatch.setattr(urllib_request(), "urlopen", fake_urlopen)
    ok, detail = cd.check_key("groq")
    assert ok == "AUTH" and "401" in detail
    monkeypatch.setattr(urllib_request(), "urlopen",
                        lambda req, timeout=None: (_ for _ in ()).throw(
                            __import__("urllib.error").error.HTTPError(
                                req.full_url, 429, "x", None, None)))
    ok, _ = cd.check_key("groq")
    assert ok == "RATE"


# ------------------------------------------------------------------ ideas

def test_parse_ideas_100_groups_1000():
    groups = cd.parse_ideas()
    assert len(groups) == 100
    total = sum(len(g["ideas"]) for g in groups)
    assert total == 1000
    assert groups[0]["n"] == 1
    assert groups[-1]["n"] == 100
    assert groups[0]["title"] == "Free LLM API providers (permanent free tiers)"
    assert len(groups[0]["ideas"]) == 10


def test_parse_ideas_numbers_prefix():
    groups = cd.parse_ideas()
    for g in groups:
        assert len(g["ideas"]) == 10
    assert groups[0]["ideas"][0].startswith("Groq:")
    assert groups[41]["title"] == "Structured output ideas"


def test_cmd_ideas_show_and_search(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cd, "IDEAS_PATH", str(tmp_path.parent / "no-such-ideas.md"))
    assert cd.cmd_ideas(type("A", (), {"show": 1, "search": None})) == 1
    monkeypatch.setattr(cd, "IDEAS_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "IDEAS.md"))
    assert cd.cmd_ideas(type("A", (), {"show": 100, "search": None})) == 0
    out = capsys.readouterr().out
    assert "cyberdeck keys manager" in out
    assert cd.cmd_ideas(type("A", (), {"show": 0, "search": "rotation"})) == 0
    assert "rotation" in capsys.readouterr().out


# ------------------------------------------------------------------ up --json and sessions --grep

def test_cmd_up_json(monkeypatch, capsys):
    monkeypatch.setattr(cd, "_HAS_RS", False)
    monkeypatch.setattr(cd, "_pyd_importable", lambda: "no")
    code = cd.cmd_up(type("A", (), {"json": True}))
    assert code is None
    data = json.loads(capsys.readouterr().out)
    assert len(data["modules"]) == len(cd.MODULES)


def test_sessions_grep(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cd, "SESSIONS_PATH", str(tmp_path / "s.json"))
    cd.add_session("make a reel about the trip", "video", "clip-factory", "echo a")
    cd.add_session("battery level please", "phone", "android-mcp", "echo b")
    cd.cmd_sessions(type("A", (), {"status": None, "grep": "battery", "limit": 10}))
    out = capsys.readouterr().out
    assert "battery level" in out and "reel about the trip" not in out
