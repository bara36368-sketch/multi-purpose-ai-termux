#!/usr/bin/env python3
"""cyberdeck.py — orchestrator for the 8-module cyberdeck monorepo.

Usage:
    python cyberdeck.py up                   # status table of all modules
    python cyberdeck.py doctor               # run every module's test suite
    python cyberdeck.py task "<prompt>"      # natural-language dispatch to a module
    python cyberdeck.py link <path-or-url>   # video-brain pipeline plan for a source
    python cyberdeck.py modules              # list modules + entry points
    python cyberdeck.py keys                 # free-API provider keys (vault + check)
    python cyberdeck.py ideas                # browse the 1000-idea database (IDEAS.md)

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
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))
CYBER_HOME = os.path.join(os.path.expanduser("~"), ".cyberdeck")
SESSIONS_PATH = os.path.join(CYBER_HOME, "sessions.json")
FLEET_PATH = os.path.join(CYBER_HOME, "fleet.json")
KEYS_PATH = os.path.join(CYBER_HOME, "keys.json")
IDEAS_PATH = os.path.join(REPO, "IDEAS.md")

# Free-API providers from IDEAS.md Group 1-2: (name, env var, signup URL,
# chat endpoint template, auth style, model). auth "query" puts the key in the
# URL (?key=...), "bearer" uses Authorization, None = no automated check.
FREE_PROVIDERS = [
    ("groq", "GROQ_API_KEY", "https://console.groq.com/keys",
     "https://api.groq.com/openai/v1/chat/completions", "bearer", "llama-3.3-70b-versatile"),
    ("cerebras", "CEREBRAS_API_KEY", "https://cloud.cerebras.ai",
     "https://api.cerebras.ai/v1/chat/completions", "bearer", "gpt-oss-120b"),
    ("gemini", "GEMINI_API_KEY", "https://aistudio.google.com/apikey",
     "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
     "query", None),
    ("mistral", "MISTRAL_API_KEY", "https://console.mistral.ai",
     "https://api.mistral.ai/v1/chat/completions", "bearer", "open-mistral-7b"),
    ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/settings/keys",
     "https://openrouter.ai/api/v1/chat/completions", "bearer", "meta-llama/llama-3.3-70b-instruct:free"),
    ("deepseek", "DEEPSEEK_API_KEY", "https://platform.deepseek.com",
     "https://api.deepseek.com/chat/completions", "bearer", "deepseek-chat"),
    ("together", "TOGETHER_API_KEY", "https://api.together.ai",
     "https://api.together.xyz/v1/chat/completions", "bearer", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    ("cohere", "COHERE_API_KEY", "https://dashboard.cohere.com",
     "https://api.cohere.com/v2/chat", "bearer", "command-r-plus"),
    ("github", "GITHUB_TOKEN", "https://github.com/settings/tokens",
     "https://models.inference.ai.azure.com/chat/completions", "bearer", "gpt-4o-mini"),
    ("nvidia", "NVIDIA_NIM_API_KEY", "https://build.nvidia.com",
     "https://integrate.api.nvidia.com/v1/chat/completions", "bearer", "meta/llama-3.3-70b-instruct"),
]

PROVIDER_BY_NAME = {p[0]: p for p in FREE_PROVIDERS}


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
    if getattr(args, "json", False):
        print(json.dumps({
            "modules": status_table(),
            "engine_rs_build": os.path.isdir(os.path.join(module_dir("engine-rs"), "target", "release")),
            "engine_rs_importable": _pyd_importable() == "yes",
            "cyberdeck_rs_importable": _HAS_RS,
        }, indent=2))
        return
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
    if getattr(args, "grep", None):
        q = args.grep.lower()
        sessions = [s for s in sessions
                    if q in s["prompt"].lower() or q in s.get("command", "").lower()]
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


# ------------------------------------------------------------------ agent

def agent01_path():
    """Path to the sibling agent-01 repo's CLI, or None."""
    env = os.environ.get("AGENT01_PATH")
    if env:
        return env
    cand = os.path.join(os.path.dirname(REPO), "agent-01", "agent01.py")
    return cand if os.path.isfile(cand) else None


def cmd_agent(args):
    path = agent01_path()
    if path is None:
        print("agent-01 not found (clone it next to this repo, or set AGENT01_PATH)")
        print("  git clone https://github.com/bara36368-sketch/agent-01 ../agent-01")
        return 2
    env = dict(os.environ)
    env["AGENT01_CYBERDECK"] = os.path.abspath(__file__)
    if args.chat or not args.prompt:
        cmd = [sys.executable, path, "--chat"]
    else:
        cmd = [sys.executable, path, args.prompt]
        if args.no_learn:
            cmd.append("--no-learn")
    try:
        proc = subprocess.run(cmd, env=env, cwd=os.path.dirname(path))
        return proc.returncode
    except OSError as exc:
        print("could not run agent-01: %s" % exc)
        return 1


# ------------------------------------------------------------------ swarm

SWARM_ROLES = [
    ("lead", "Lead agent — own the answer, integrate everyone else's findings"),
    ("architect", "System architecture — structure, layering, dependency analysis"),
    ("code-reviewer", "Code review — bugs, correctness, edge cases, smells"),
    ("security", "Security — auth, injection, secrets, SSRF, OWASP Top 10"),
    ("performance", "Performance — hot paths, latency, memory, token budget"),
    ("reliability", "Reliability — crash loops, restart storms, error handling"),
    ("testing", "Testing — coverage gaps, flaky tests, missing cases"),
    ("docs", "Documentation — README, comments, usage completeness"),
    ("deploy", "Deployment — phone/Termux fit, startup, supervision"),
    ("data", "Data — schema, journaling, backup, retention"),
    ("ux", "UX — CLI ergonomics, messages, defaults"),
    ("edge", "Edge advocate — challenge the plan; play devil's advocate"),
]


def _swarm_report_path():
    d = os.path.join(CYBER_HOME, "swarm")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, time.strftime("%Y%m%d-%H%M%S.json"))


def _custom_swarm_agents():
    """(name, role) pairs from the agent-01 custom-agent registry that are
    flagged for swarm inclusion. Empty when agent-01 is missing or the
    registry has no swarm members."""
    path = agent01_path()
    if path is None:
        return []
    try:
        proc = subprocess.run(
            [sys.executable, path, "--agents", "--json", "--swarm-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=os.path.dirname(os.path.realpath(path)), timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        return []
    return [(a["name"], a["role"]) for a in data.get("custom", [])]


def cmd_agent_mgr(args):
    """custom-agent management: --list-agents / --add-agent / --rm-agent.
    Forwards directly to agent-01's CLI so the registry stays single-sourced."""
    path = agent01_path()
    if path is None:
        print("agent-01 not found (clone it next to this repo, or set AGENT01_PATH)")
        return 2
    if args.list_agents:
        cmd = [sys.executable, path, "--agents"]
        if args.json:
            cmd.append("--json")
            cmd.append("--swarm-only")
    elif args.add_agent:
        cmd = [sys.executable, path, "--add-agent", args.add_agent]
        if args.name:
            cmd += ["--name", args.name]
        if args.no_swarm:
            cmd.append("--no-swarm")
    elif args.rm_agent:
        cmd = [sys.executable, path, "--rm-agent", args.rm_agent]
    else:
        return None
    try:
        proc = subprocess.run(cmd, env=dict(os.environ),
                              cwd=os.path.dirname(os.path.realpath(path)))
        return proc.returncode
    except OSError as exc:
        print("could not run agent-01: %s" % exc)
        return 1


def cmd_swarm(args):
    path = agent01_path()
    if path is None:
        print("agent-01 not found (clone it next to this repo, or set AGENT01_PATH)")
        print("  git clone https://github.com/bara36368-sketch/agent-01 ../agent-01")
        return 2
    mgr = cmd_agent_mgr(args)
    if mgr is not None:
        return mgr
    if not args.task:
        print("swarm: no task given")
        print("  python cyberdeck.py swarm '<task>'                # run the swarm")
        print("  python cyberdeck.py swarm --list-agents           # list custom agents")
        print("  python cyberdeck.py swarm --add-agent '<prompt>'  # create agent-02 by prompt")
        return 1
    roles = SWARM_ROLES if args.roles is None else [
        r for r in SWARM_ROLES if r[0] in args.roles]
    roles = (roles or SWARM_ROLES)[: args.count]
    custom = [(n, r) for n, r in _custom_swarm_agents()
              if n not in {x[0] for x in roles}]
    roles = roles + custom
    if not args.roles and args.count:
        roles = roles[: args.count]
    print("swarm: %d agents on: %s" % (len(roles), args.task))
    print("-" * 60)
    env = dict(os.environ)
    env["AGENT01_CYBERDECK"] = os.path.abspath(__file__)
    proc = {}
    for name, _ in roles:
        e = dict(env)
        e["AGENT01_ROLE"] = name
        cmd = [sys.executable, path, args.task]
        if args.no_learn:
            cmd.append("--no-learn")
        proc[name] = subprocess.Popen(
            cmd, env=e, cwd=os.path.dirname(path),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace")
    results = []
    for name, role in roles:
        out, _ = proc[name].communicate(timeout=args.timeout)
        tail = out.strip()[-400:]
        results.append({"agent": name, "role": role, "rc": proc[name].returncode,
                        "output_tail": tail})
        print("[%s] rc=%d %s" % (name, proc[name].returncode,
                                 tail.replace("\n", " ")[:120]))
    report = {"task": args.task, "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
              "agents": results}
    rp = _swarm_report_path()
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print()
    print("swarm report: %s" % rp)
    print()
    print("=== synthesis (lead) ===")
    lead = next((r for r in results if r["agent"] == "lead"), results[0])
    print(lead["output_tail"])
    return 0


def cmd_modules(args):
    for m in MODULES:
        print("%-14s %-18s %s" % (m["dir"], m["entry"], m["what"]))


# ------------------------------------------------------------------ keys

def mask_key(key):
    """Show only the last 4 chars — never print full keys (Group 3 #5, 24 #7)."""
    if not key:
        return ""
    if len(key) <= 4:
        return "****"
    return "...%s" % key[-4:]


def load_keys():
    try:
        with open(KEYS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_keys(keys):
    _atomic_json(KEYS_PATH, keys)
    try:
        os.chmod(KEYS_PATH, 0o600)  # posix-only; ignored on Windows
    except OSError:
        pass


def resolve_key(provider):
    """Key for a provider: vault first, then env var (Group 3 #3, #9)."""
    keys = load_keys()
    name, env, _signup, _url, _auth, _model = PROVIDER_BY_NAME[provider]
    if keys.get(provider):
        return keys[provider]
    env_key = os.environ.get(env, "") or os.environ.get("%s_API_KEY" % name.upper(), "")
    return env_key or os.environ.get(name.upper(), "")


def check_key(provider, timeout=6.0):
    """Probe a provider with a 1-token request. Returns
    (status, detail) with status in OK/401/429/ERR or None if not checkable."""
    name, env, _signup, url, auth, model = PROVIDER_BY_NAME[provider]
    key = resolve_key(provider)
    if not key:
        return ("missing", "no key (vault or %s)" % env)
    if not url or not auth:
        return ("nocheck", "no automated check endpoint")
    body = None
    req_url = url.format(key=key) if auth == "query" else url
    headers = {"Content-Type": "application/json"}
    if auth == "bearer":
        headers["Authorization"] = "Bearer " + key
    if model:
        body = json.dumps({"model": model, "messages": [{"role": "user",
                                                         "content": "ping"}],
                           "max_tokens": 1}).encode("utf-8")
    req = urllib.request.Request(req_url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return ("OK", "HTTP %d" % r.status)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return ("AUTH", "HTTP %d — key invalid/revoked" % exc.code)
        code = exc.code
        detail = "HTTP %d" % code
        try:
            err = json.loads(exc.read().decode("utf-8", "replace"))
            de = err.get("error", {})
            detail += " — " + str(de.get("rate_limited", de.get("message", "")))[:80]
        except Exception:
            pass
        return ("RATE" if code == 429 else "ERR", detail)
    except Exception as exc:
        return ("ERR", str(exc)[:80])


def cmd_keys(args):
    sub = args.keys_cmd
    if sub == "list":
        print("%-12s %-10s %-30s %s" % ("provider", "source", "env var", "key"))
        print("-" * 70)
        for name, env, _signup, _url, _auth, _model in FREE_PROVIDERS:
            key = resolve_key(name)
            src = "vault" if load_keys().get(name) else ("env" if key else "none")
            show = mask_key(key) if key else "-"
            print("%-12s %-10s %-30s %s" % (name, src, env, show))
        return 0
    if sub == "add":
        name = args.provider.lower()
        if name not in PROVIDER_BY_NAME:
            print("unknown provider '%s' (see: cyberdeck.py keys list)" % args.provider)
            return 2
        keys = load_keys()
        keys[name] = args.key
        save_keys(keys)
        print("stored %s -> ~/.cyberdeck/keys.json (%s)" % (name, mask_key(args.key)))
        return 0
    if sub == "rm":
        keys = load_keys()
        if args.provider not in keys:
            print("no stored key for %s" % args.provider)
            return 1
        del keys[args.provider]
        save_keys(keys)
        print("removed %s from vault (env var still works)" % args.provider)
        return 0
    if sub == "check":
        bad = 0
        print("%-12s %-8s %s" % ("provider", "state", "detail"))
        print("-" * 70)
        for name in sorted(PROVIDER_BY_NAME):
            ok, detail = check_key(name)
            if ok not in ("OK", "nocheck"):
                bad += 1
            print("%-12s %-8s %s" % (name, ok, detail))
        print()
        print("nocheck = no automated endpoint (add your own). %d degraded/missing" % bad)
        return 0 if bad == 0 else 1
    print(__doc__)
    return 0


# ------------------------------------------------------------------ ideas

def _safe_print(text):
    """Print UTF-8 content even on legacy consoles (cp1252 etc.): replace
    characters the terminal can't encode instead of crashing."""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))


def parse_ideas(path=None):
    """Parse IDEAS.md into [{"n": 1, "title": "…", "ideas": ["…", …]}, …]."""
    if path is None:
        path = IDEAS_PATH
    groups = []
    cur = None
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                m = re.match(r"^## Group (\d+) \u2014 (.+)$", line)
                if m:
                    cur = {"n": int(m.group(1)), "title": m.group(2), "ideas": []}
                    groups.append(cur)
                    continue
                im = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
                if cur is not None and im:
                    cur["ideas"].append(im.group(2))
    except OSError:
        return []
    return groups


def cmd_ideas(args):
    groups = parse_ideas()
    if not groups:
        print("IDEAS.md not found next to cyberdeck.py — clone it or restore it")
        return 1
    if args.show:
        g = next((x for x in groups if x["n"] == args.show), None)
        if g is None:
            print("no group %d (1-%d)" % (args.show, len(groups)))
            return 1
        print("## Group %d — %s" % (g["n"], g["title"]))
        for i, idea in enumerate(g["ideas"], 1):
            _safe_print("%2d. %s" % (i, idea))
        return 0
    if args.search:
        q = args.search.lower()
        hits = []
        for g in groups:
            for idea in g["ideas"]:
                if q in idea.lower():
                    hits.append((g["n"], g["title"], idea))
        print("%d matches for %r" % (len(hits), args.search))
        for n, title, idea in hits[:50]:
            _safe_print("  G%-3d %-24s %s" % (n, title[:24], idea))
        return 0
    print("%d groups x 10 = %d ideas (from GitHub research)" % (len(groups), sum(len(g["ideas"]) for g in groups)))
    for g in groups:
        print("G%-3d %s" % (g["n"], g["title"]))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="cyberdeck.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("up", help="status table of all modules").add_argument(
        "--json", action="store_true", help="machine-readable output")
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
    ses.add_argument("--grep", default=None, help="filter by keyword in prompt/command")
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
    agent = sub.add_parser("agent", help="ask agent-01 (self-improving agent) — needs the sibling repo")
    agent.add_argument("prompt", nargs="?", default=None, help="question to ask (omitted = interactive chat)")
    agent.add_argument("--no-learn", action="store_true", help="don't record/learn from this turn")
    agent.add_argument("--chat", action="store_true", help="interactive agent-01 session")
    swarm = sub.add_parser("swarm", help="run a dozen role-specialized agents (agent-01 lead + 11 roles + custom agents)")
    swarm.add_argument("task", nargs="?", default=None, help="the task to swarm")
    swarm.add_argument("--count", type=int, default=12, help="max agents to spawn (default 12)")
    swarm.add_argument("--roles", nargs="*", default=None, help="subset of roles (lead architect security ...)")
    swarm.add_argument("--timeout", type=int, default=600, help="per-agent timeout (s)")
    swarm.add_argument("--no-learn", action="store_true", help="agents don't record/learn")
    swarm.add_argument("--list-agents", action="store_true", help="list custom agents registered for swarm")
    swarm.add_argument("--json", action="store_true", help="with --list-agents: machine-readable output")
    swarm.add_argument("--add-agent", metavar="PROMPT", default=None,
                       help="create a custom agent from a role prompt (auto-numbered agent-02, ...)")
    swarm.add_argument("--name", default=None, help="with --add-agent: explicit name (e.g. agent-07)")
    swarm.add_argument("--no-swarm", action="store_true", help="with --add-agent: keep out of swarm runs")
    swarm.add_argument("--rm-agent", default=None, help="delete a custom agent by name")
    sub.add_parser("modules", help="list modules + entry points")
    keys = sub.add_parser("keys", help="manage free-API provider keys (vault in ~/.cyberdeck)")
    keysub = keys.add_subparsers(dest="keys_cmd")
    keysub.add_parser("list", help="providers, source, env vars (keys masked)")
    kadd = keysub.add_parser("add", help="store a key in the vault")
    kadd.add_argument("provider")
    kadd.add_argument("key")
    krm = keysub.add_parser("rm", help="remove a key from the vault")
    krm.add_argument("provider")
    keysub.add_parser("check", help="probe each provider with a 1-token request (live)")
    ideas = sub.add_parser("ideas", help="browse the 1000-idea database (IDEAS.md)")
    ideas.add_argument("--show", type=int, default=0, help="show one group, e.g. --show 100")
    ideas.add_argument("--search", default=None, help="keyword search across all ideas")
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
    elif args.cmd == "agent":
        return cmd_agent(args)
    elif args.cmd == "swarm":
        return cmd_swarm(args)
    elif args.cmd == "link":
        cmd_link(args)
    elif args.cmd == "modules":
        cmd_modules(args)
    elif args.cmd == "keys":
        return cmd_keys(args)
    elif args.cmd == "ideas":
        return cmd_ideas(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
