#!/usr/bin/env python3
"""cyberdeck.py — orchestrator for the 8-module cyberdeck monorepo.

Usage:
    python cyberdeck.py up                   # status table of all modules
    python cyberdeck.py doctor               # run every module's test suite
    python cyberdeck.py task "<prompt>"      # natural-language dispatch to a module
    python cyberdeck.py link <path-or-url>   # video-brain pipeline plan for a source
    python cyberdeck.py modules              # list modules + entry points

`task` uses keyword intent matching (offline, deterministic). Pass --llm to
ask a reachable androidllm phone to classify the intent instead, with the
keyword matcher as fallback (ANDROIDLLM_URL env var or http://127.0.0.1:8000).

Intent dispatch, placeholder refusal, session ids/tails and fleet alert
detection run through the PyO3 extension `cyberdeck_rs` when built
(cd cyberdeck-rs && maturin build; pip install the wheel) with pure-Python
fallbacks otherwise — the CLI never hard-depends on a Rust build.

Imports: stdlib only (cyberdeck_rs optional). Python 3.8+.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
CYBER_HOME = os.path.join(os.path.expanduser("~"), ".cyberdeck")
SESSIONS_PATH = os.path.join(CYBER_HOME, "sessions.json")
FLEET_PATH = os.path.join(CYBER_HOME, "fleet.json")


def _load_rs():
    try:
        import cyberdeck_rs  # noqa: F401
        return sys.modules["cyberdeck_rs"]
    except ImportError:
        pass
    try:
        sys.path.insert(0, os.path.join(REPO, "cyberdeck-rs"))
        import cyberdeck_rs  # noqa: F401
        return sys.modules["cyberdeck_rs"]
    except ImportError:
        return None


_RS = _load_rs()
_HAS_RS = _RS is not None

MODULES = [
    {"dir": "gateway", "entry": "gateway.py", "what": "multi-channel agent gateway (router + telegram)"},
    {"dir": "phone-server", "entry": "install.sh", "what": "Termux deploy kit (install/run/monitor)"},
    {"dir": "bench", "entry": "runner.py", "what": "on-device model leaderboard"},
    {"dir": "clip-factory", "entry": "pipeline.py", "what": "CapCut automation (script -> draft)"},
    {"dir": "agent-brain", "entry": "answer.py", "what": "agent memory: sessions -> graph -> cited answers"},
    {"dir": "android-mcp", "entry": "server.py", "what": "Android phone capabilities as MCP tools"},
    {"dir": "video-brain", "entry": "ask.py", "what": "video/SRT -> timestamped Q&A"},
    {"dir": "engine-rs", "entry": "src/lib.rs", "what": "Rust inference hot path (PyO3)"},
]

INTENTS = [
    ("video", ("clip", "short", "reel", "youtube", "video", "edit", "caption", "vectcut", "tts"),
     "clip-factory",
     'python clip-factory/pipeline.py "topic"  # then director plan + SRT + VectCut draft'),
    ("learn", ("learn", "remember", "ask", "q&a", "summary", "summarize", "notes", "brain", "watch"),
     "video-brain",
     'python video-brain/ask.py "your question"  # after indexing an SRT'),
    ("phone", ("battery", "sms", "clipboard", "tts", "thermal", "phone", "mcp", "device"),
     "android-mcp",
     "start android-mcp/server.py  # stdio or HTTP MCP endpoint"),
    ("bench", ("bench", "speed", "tok/s", "tokens", "performance", "leaderboard", "heat"),
     "bench",
     "python bench/runner.py --model <id> --profile g85  # on the phone"),
    ("deploy", ("install", "deploy", "termux", "setup", "server", "24/7"),
     "phone-server",
     "bash phone-server/install.sh  # on the phone"),
    ("memory", ("memory", "graph", "entities", "ingest", "session", "who said"),
     "agent-brain",
     'python agent-brain/ingest.py <file>; python agent-brain/answer.py "question"'),
    ("gateway", ("telegram", "bot", "gateway", "route", "channel", "whatsapp"),
     "gateway",
     "python gateway/gateway.py  # router + telegram long-poll"),
    ("rust", ("rust", "engine", "sampling", "top-p", "min-p", "speed up", "pyo3"),
     "engine-rs",
     "cd engine-rs && maturin develop  # then python tests/test_sampling.py"),
]


def module_dir(name):
    return os.path.join(REPO, name)


def entry_exists(mod):
    return os.path.isfile(os.path.join(module_dir(mod["dir"]), mod["entry"]))


def test_path(mod):
    return os.path.join(module_dir(mod["dir"]), "tests")


def has_tests(mod):
    return os.path.isdir(test_path(mod))


# ------------------------------------------------------------------ status

def status_table():
    rows = []
    for m in MODULES:
        rows.append({
            "module": m["dir"],
            "entry": m["entry"],
            "entry_ok": entry_exists(m),
            "tests": has_tests(m),
        })
    return rows


def cmd_up(args):
    print("%-14s %-18s %-8s %s" % ("module", "entry", "entry", "tests"))
    print("-" * 60)
    for r in status_table():
        print("%-14s %-18s %-8s %s" % (
            r["module"], r["entry"],
            "ok" if r["entry_ok"] else "MISSING",
            "yes" if r["tests"] else "no"))
    rust = os.path.join(module_dir("engine-rs"), "target", "release")
    print()
    print("engine-rs release build: %s" % ("present" if os.path.isdir(rust) else "not built yet (cd engine-rs && cargo build --release)"))
    print("engine_rs.pyd importable: %s" % _pyd_importable())
    print("cyberdeck_rs importable:  %s" % ("yes" if _HAS_RS else "no (cd cyberdeck-rs && maturin build; pip install the wheel)"))


def _pyd_importable():
    try:
        sys.path.insert(0, module_dir("engine-rs"))
        import engine_rs  # noqa: F401
        return "yes"
    except Exception:
        return "no"


# ------------------------------------------------------------------ doctor

def run_tests(args, env=None):
    """Run pytest in every module that has tests. Returns (passed, failed, skipped)."""
    results = []
    for m in MODULES:
        if not has_tests(m):
            results.append({"module": m["dir"], "status": "no-tests"})
            continue
        try:
            out = subprocess.run(
                [sys.executable, "-m", "pytest", "tests", "-q"],
                cwd=module_dir(m["dir"]),
                capture_output=True, text=True, timeout=args.timeout,
                env=env)
            tail = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else (out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "?")
            results.append({"module": m["dir"], "status": "PASS" if out.returncode == 0 else "FAIL", "summary": tail})
        except subprocess.TimeoutExpired:
            results.append({"module": m["dir"], "status": "TIMEOUT", "summary": ">%ss" % args.timeout})
        except OSError as exc:
            results.append({"module": m["dir"], "status": "ERROR", "summary": str(exc)})
    return results


def cmd_doctor(args, env=None):
    print("running module test suites...")
    results = run_tests(args, env)
    print()
    print("%-14s %-8s %s" % ("module", "status", "summary"))
    print("-" * 60)
    n_pass = n_fail = 0
    for r in results:
        print("%-14s %-8s %s" % (r["module"], r["status"], r.get("summary", "")))
        if r["status"] == "PASS":
            n_pass += 1
        elif r["status"] == "no-tests":
            pass
        else:
            n_fail += 1
    print()
    total = sum(1 for r in results if r["status"] in ("PASS", "FAIL", "TIMEOUT", "ERROR"))
    print("%d suites, %d passing, %d failing" % (total, n_pass, n_fail))
    return 1 if n_fail else 0


# ------------------------------------------------------------------ task

def _py_classify_intent(prompt):
    """Pure-Python reference for classify_intent (parity-checked against Rust)."""
    text = prompt.lower()
    for name, keywords, module, command in INTENTS:
        if any(k.lower() in text for k in keywords):
            return name, module, command
    return None


def classify_intent(prompt):
    """Keyword dispatch over INTENTS. Returns (intent_name, module, command) or None."""
    if _HAS_RS:
        r = _RS.classify_intent(prompt, INTENTS)
        return tuple(r) if r else None
    return _py_classify_intent(prompt)


def llm_classify(prompt, env=None, timeout=10.0):
    """Ask a reachable androidllm server to classify the intent. Returns the
    parsed name + module, or raises on any failure (caller falls back)."""
    base = (env or os.environ).get("ANDROIDLLM_URL", "http://127.0.0.1:8000").rstrip("/")
    choices = ", ".join(i[0] for i in INTENTS)
    sys_prompt = (
        "You route a user request to exactly one of these intents: %s. "
        "Reply with a single JSON object: {\"intent\": \"<name>\", \"reason\": \"<one line>\"}" % choices
    )
    body = json.dumps({
        "model": "any",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 120,
    }).encode("utf-8")
    req = urllib.request.Request(
        base + "/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    raw = data["choices"][0]["message"]["content"]
    parsed = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    name = parsed["intent"].strip().lower()
    for intent in INTENTS:
        if intent[0] == name:
            return intent[0], intent[2], intent[3]
    raise ValueError("unrecognized intent: %r" % name)


def cmd_task(args, env=None):
    if not args.prompt:
        print("prompt required:  python cyberdeck.py task \"<what do you want>\"")
        return 2
    match = None
    source = "keywords"
    if args.llm:
        try:
            match = llm_classify(args.prompt, env)
            source = "androidllm"
        except Exception as exc:
            print("llm classify failed (%s) — falling back to keywords" % exc)
    if match is None:
        match = classify_intent(args.prompt)
        source = "keywords"
    if match is None:
        print("no intent matched. try one of: %s" % ", ".join(i[0] for i in INTENTS))
        return 1
    name, module, command = match
    print("intent:  %-12s (via %s)" % (name, source))
    print("module:  %s" % module)
    print("command: %s" % command)
    return 0


# ------------------------------------------------------------------ link

def cmd_link(args):
    src = args.source
    if os.path.isfile(src):
        ext = os.path.splitext(src)[1].lower()
        if ext in (".srt", ".vtt"):
            print("local transcript: index + ask without network")
            print("  python video-brain/index.py %s" % src)
            print('  python video-brain/ask.py "your question"')
            return 0
        print("local file (not an SRT/VTT transcript): transcribe first on the phone,")
        print("then re-run with the .srt. yt-dlp + whisper live in video-brain/transcribe.py")
        return 0
    print("remote source (%s): on-device pipeline" % src)
    print("  1. python video-brain/fetch.py %s" % src)
    print("  2. python video-brain/transcribe.py <audio/video>   # whisper, on the phone")
    print("  3. python video-brain/index.py <out.srt>")
    print('  4. python video-brain/ask.py "what did they say about X"')
    print()
    print("then feed the answer into agent-brain if it is worth remembering:")
    print("  python agent-brain/ingest.py <notes.ndjson>")
    return 0


# ------------------------------------------------------------------ sessions

SESSION_STATUS = ("running", "done", "failed", "timedout")


def _atomic_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load_sessions():
    try:
        with open(SESSIONS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_sessions(sessions):
    _atomic_json(SESSIONS_PATH, sessions)


def add_session(prompt, intent, module, command):
    sessions = load_sessions()
    sid = _RS.next_id(sessions) if _HAS_RS else ((sessions[-1]["id"] + 1) if sessions else 1)
    session = {
        "id": sid,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "prompt": prompt,
        "intent": intent,
        "module": module,
        "command": command,
        "status": "running",
        "exit_code": None,
        "duration_ms": None,
        "output_tail": "",
    }
    sessions.append(session)
    save_sessions(sessions)
    return session


def update_session(session, **fields):
    sessions = load_sessions()
    for s in sessions:
        if s["id"] == session["id"]:
            s.update(fields)
            break
    save_sessions(sessions)
    session.update(fields)


def _py_has_placeholders(command):
    """Pure-Python reference for has_placeholders."""
    return '"' in command or "<" in command or ">" in command


def has_placeholders(command):
    """Templates embed placeholders as \"topic\" or <...> — neither is safe
    to execute verbatim."""
    if _HAS_RS:
        return _RS.has_placeholders(command)
    return _py_has_placeholders(command)


def _py_tail(text, max_chars=1200):
    """Pure-Python reference for _tail (raw tail, no stripping — matches Rust)."""
    return "" if max_chars == 0 else text[-max_chars:]


def _tail(text, max_chars=1200):
    """Last max_chars characters, char-boundary safe."""
    if _HAS_RS:
        return _RS.tail(text, max_chars)
    return _py_tail(text, max_chars)


def run_command(command, timeout=300):
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or "") + (exc.stderr or "")


def cmd_task(args, env=None):
    if not args.prompt:
        print("prompt required:  python cyberdeck.py task \"<what do you want>\"")
        return 2
    match = None
    source = "keywords"
    if args.llm:
        try:
            match = llm_classify(args.prompt, env)
            source = "androidllm"
        except Exception as exc:
            print("llm classify failed (%s) — falling back to keywords" % exc)
    if match is None:
        match = classify_intent(args.prompt)
        source = "keywords"
    if match is None:
        print("no intent matched. try one of: %s" % ", ".join(i[0] for i in INTENTS))
        return 1
    name, module, command = match
    print("intent:  %-12s (via %s)" % (name, source))
    print("module:  %s" % module)
    print("command: %s" % command)
    if not args.run:
        print()
        print("tip:     add --run to execute it (recorded in ~/.cyberdeck/sessions.json)")
        return 0
    if has_placeholders(command):
        print("refusing: command has placeholders (<> or \"topic\") — run it manually, then:")
        print("          python cyberdeck.py task \"%s\" --run" % args.prompt)
        return 3
    print()
    print("running (timeout %ss)... %s" % (args.timeout, command))
    session = add_session(args.prompt, name, module, command)
    t0 = time.monotonic()
    rc, output = run_command(command, timeout=args.timeout)
    status = "done" if rc == 0 else ("timedout" if rc == 124 else "failed")
    update_session(session, status=status, exit_code=rc,
                   duration_ms=int((time.monotonic() - t0) * 1000),
                   output_tail=_tail(output))
    print("status:  %s (exit %s)" % (status, rc))
    tail = output.strip()
    if tail:
        print("output:")
        print(tail[-1200:])
    return 0 if rc == 0 else 1


def cmd_sessions(args):
    sessions = load_sessions()
    if args.status:
        sessions = [s for s in sessions if s["status"] == args.status]
    sessions = sessions[-args.limit:] if args.limit else sessions
    if not sessions:
        print("no sessions yet. run: python cyberdeck.py task \"<prompt>\" --run")
        return 0
    for s in reversed(sessions):
        print("#%-4d %-19s %-9s %-12s %s" % (
            s["id"], s["ts"], s["status"],
            s.get("intent", "?"), s["prompt"][:60]))
    print()
    print("redo: python cyberdeck.py redo <id>")


def cmd_redo(args):
    sessions = load_sessions()
    src = next((s for s in sessions if s["id"] == args.id), None)
    if src is None:
        print("no session #%d (see: python cyberdeck.py sessions)" % args.id)
        return 1
    if has_placeholders(src["command"]):
        print("refusing: session #%d command has placeholders — run it manually." % args.id)
        return 3
    print("redo #%d: %s" % (args.id, src["command"]))
    session = add_session("redo of #%d: %s" % (args.id, src["prompt"]),
                          src.get("intent", "redo"), src["module"], src["command"])
    session["rerun_of"] = args.id
    t0 = time.monotonic()
    rc, output = run_command(src["command"], timeout=args.timeout)
    status = "done" if rc == 0 else ("timedout" if rc == 124 else "failed")
    update_session(session, status=status, exit_code=rc,
                   duration_ms=int((time.monotonic() - t0) * 1000),
                   output_tail=_tail(output))
    print("status:  %s (exit %s)" % (status, rc))
    tail = output.strip()
    if tail:
        print(tail[-1200:])
    return 0 if rc == 0 else 1


# ------------------------------------------------------------------ fleet

def load_fleet(env=None):
    """List of {name, url, key?} phones. Defaults to the local phone."""
    try:
        with open(FLEET_PATH, encoding="utf-8") as f:
            phones = json.load(f).get("phones", [])
        if phones:
            return phones
    except (OSError, ValueError):
        pass
    env = env or os.environ
    base = env.get("ANDROIDLLM_URL", "http://127.0.0.1:8000").rstrip("/")
    return [{"name": "local", "url": base, "key": env.get("ANDROIDLLM_KEY") or ""}]


def save_fleet(phones):
    _atomic_json(FLEET_PATH, {"phones": phones})


def probe_phone(phone, timeout=3.0):
    """GET /health. Returns dict with name/status/latency_ms + server fields,
    or {'name', 'status': 'DOWN', 'error'}."""
    url = phone["url"].rstrip("/") + "/health"
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url)
        if phone.get("key"):
            req.add_header("Authorization", "Bearer " + phone["key"])
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
        data = json.loads(body) if body else {}
        data["name"] = phone["name"]
        data["status"] = "UP"
        data["latency_ms"] = int((time.monotonic() - t0) * 1000)
        return data
    except Exception as exc:
        return {"name": phone["name"], "url": phone["url"],
                "status": "DOWN", "error": str(exc)[:80]}


def probe_fleet(timeout=3.0):
    return [probe_phone(p, timeout) for p in load_fleet()]


def fmt_row(h, color):
    reset = "\x1b[0m" if color else ""
    name = "%-8s" % h.get("name", "?")
    if h["status"] == "UP":
        model = h.get("model") or h.get("active_model") or h.get("model_id") or "?"
        extra = " ".join("%s=%s" % (k, v) for k, v in sorted(h.items())
                         if k in ("ram_gb", "temp_c", "thermal", "tok_s", "uptime_s") and v not in (None, ""))
        return "%s%s%s UP   %4d ms  %-14s %s" % (color, name, reset, h.get("latency_ms", 0), model, extra)
    return "%s%s%s DOWN  %s" % (color, name, reset, h.get("error", ""))


def _py_fleet_alerts(prev, cur):
    """Pure-Python reference for fleet_alerts."""
    out = []
    p = {h["name"]: h for h in prev}
    for h in cur:
        old = p.get(h["name"])
        if old is None:
            continue
        if old["status"] != h["status"]:
            out.append("ALERT %s: %s -> %s" % (h["name"], old["status"], h["status"]))
            continue
        if h["status"] == "UP":
            om = old.get("model") or old.get("active_model")
            nm = h.get("model") or h.get("active_model")
            if om and nm and om != nm:
                out.append("ALERT %s: model swapped %s -> %s" % (h["name"], om, nm))
    return out


def fleet_alerts(prev, cur):
    """State-change lines: up/down flips, model swaps, thermal spikes."""
    if _HAS_RS:
        return list(_RS.fleet_alerts(prev, cur))
    return _py_fleet_alerts(prev, cur)


def cmd_fleet(args, env=None):
    sub = args.fleet_cmd
    if sub == "add":
        phones = load_fleet(env)
        for p in phones:
            if p["name"] == args.name:
                print("phone '%s' already in fleet" % args.name)
                return 1
        phones.append({"name": args.name, "url": args.url, "key": args.key or ""})
        save_fleet(phones)
        print("added %s (%s) — %d phone(s) in fleet" % (args.name, args.url, len(phones)))
        return 0
    if sub == "rm":
        phones = load_fleet(env)
        kept = [p for p in phones if p["name"] != args.name]
        if len(kept) == len(phones):
            print("no phone named '%s'" % args.name)
            return 1
        save_fleet(kept)
        print("removed %s — %d phone(s) left" % (args.name, len(kept)))
        return 0
    if sub == "ls":
        for i, p in enumerate(load_fleet(env)):
            print("%-8s %-28s key=%s" % (p["name"], p["url"], "set" if p.get("key") else "none"))
        return 0
    # status / watch share the polling loop
    return _fleet_loop(args, env)


def _render(snap, alerts, use_color):
    def c(code):
        return ("\x1b[%sm" % code) if use_color else ""
    rows = [fmt_row(h, c("32") if h["status"] == "UP" else c("31")) for h in snap]
    head = "%-8s %-7s %-8s %-14s extra" % ("phone", "state", "lat", "model")
    print("=" * 70)
    print("cyberdeck fleet watch   %s   (ctrl-c to quit)" % time.strftime("%H:%M:%S"))
    print("=" * 70)
    print(head)
    for r in rows:
        print(r)
    for a in alerts:
        print(c("33") + a + c("0"))


def _fleet_loop(args, env=None):
    interval = max(1, args.interval)
    tty = sys.stdout.isatty()
    use_color = tty and os.environ.get("NO_COLOR") is None
    prev = []
    try:
        while True:
            snap = probe_fleet(timeout=args.timeout)
            alerts = fleet_alerts(prev, snap)
            prev = snap
            if tty:
                sys.stdout.write("\x1b[2J\x1b[H")
                sys.stdout.flush()
            _render(snap, alerts, use_color)
            if not tty or args.once:
                return 0
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                return 0
    except KeyboardInterrupt:
        print()
        return 0


def cmd_modules(args):
    for m in MODULES:
        print("%-14s %-18s %s" % (m["dir"], m["entry"], m["what"]))


def main(argv=None):
    p = argparse.ArgumentParser(prog="cyberdeck.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("up", help="status table of all modules")
    doc = sub.add_parser("doctor", help="run every module's test suite")
    doc.add_argument("--timeout", type=int, default=120, help="per-suite timeout (s)")
    task = sub.add_parser("task", help="natural-language dispatch to a module")
    task.add_argument("prompt", nargs="?", default=None)
    task.add_argument("--llm", action="store_true", help="classify via androidllm phone, keyword fallback")
    task.add_argument("--run", action="store_true", help="execute the resolved command (recorded as a session)")
    task.add_argument("--timeout", type=int, default=300, help="run timeout in seconds")
    ses = sub.add_parser("sessions", help="list recent task sessions (journal)")
    ses.add_argument("--limit", type=int, default=10)
    ses.add_argument("--status", choices=SESSION_STATUS, default=None)
    redo = sub.add_parser("redo", help="re-run a finished session")
    redo.add_argument("id", type=int)
    redo.add_argument("--timeout", type=int, default=300)
    link = sub.add_parser("link", help="video-brain pipeline plan for a source")
    link.add_argument("source", help="path to an SRT/VTT, or a URL")
    fleet = sub.add_parser("fleet", help="manage + watch phones")
    fsub = fleet.add_subparsers(dest="fleet_cmd")
    fsub.add_parser("ls", help="list fleet")
    fadd = fsub.add_parser("add", help="add a phone")
    fadd.add_argument("name")
    fadd.add_argument("url")
    fadd.add_argument("--key", default=None)
    frm = fsub.add_parser("rm", help="remove a phone")
    frm.add_argument("name")
    fstatus = fsub.add_parser("status", help="one-shot health table")
    fstatus.add_argument("--timeout", type=float, default=3.0)
    fstatus.add_argument("--once", action="store_true")
    fstatus.add_argument("--interval", type=int, default=5, help="poll interval (s), watch mode")
    sub.add_parser("modules", help="list modules + entry points")
    args = p.parse_args(argv)

    if args.cmd == "up":
        cmd_up(args)
    elif args.cmd == "doctor":
        return cmd_doctor(args)
    elif args.cmd == "task":
        return cmd_task(args)
    elif args.cmd == "sessions":
        cmd_sessions(args)
    elif args.cmd == "redo":
        return cmd_redo(args)
    elif args.cmd == "fleet":
        return cmd_fleet(args)
    elif args.cmd == "link":
        cmd_link(args)
    elif args.cmd == "modules":
        cmd_modules(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
