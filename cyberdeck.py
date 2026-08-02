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

Imports: stdlib only. Python 3.8+.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.abspath(__file__))

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

def classify_intent(prompt):
    """Keyword dispatch over INTENTS. Returns (intent_name, module, command) or None."""
    text = prompt.lower()
    for name, keywords, module, command in INTENTS:
        if any(k.lower() in text for k in keywords):
            return name, module, command
    return None


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
    link = sub.add_parser("link", help="video-brain pipeline plan for a source")
    link.add_argument("source", help="path to an SRT/VTT, or a URL")
    sub.add_parser("modules", help="list modules + entry points")
    args = p.parse_args(argv)

    if args.cmd == "up":
        cmd_up(args)
    elif args.cmd == "doctor":
        return cmd_doctor(args)
    elif args.cmd == "task":
        return cmd_task(args)
    elif args.cmd == "link":
        cmd_link(args)
    elif args.cmd == "modules":
        cmd_modules(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
