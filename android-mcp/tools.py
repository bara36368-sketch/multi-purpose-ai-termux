"""Tool implementations. Phone data comes from Termux-API / sysfs; every
tool degrades gracefully on non-Android boxes (dev mode) so tests run
anywhere. Tool names stay lowercase_snake, args flat JSON.
"""
import json
import os
import subprocess
import sys

TOOLS = [
    {"name": "battery", "description": "Battery level percent + charging state",
     "schema": {"type": "object", "properties": {}}},
    {"name": "sms_send", "description": "Send an SMS (Termux-API)",
     "schema": {"type": "object", "properties": {"number": {"type": "string"},
                                                "text": {"type": "string"}},
                "required": ["number", "text"]}},
    {"name": "clipboard_get", "description": "Read the device clipboard (Termux-API)",
     "schema": {"type": "object", "properties": {}}},
    {"name": "tts_say", "description": "Speak text aloud (Termux-API TTS)",
     "schema": {"type": "object", "properties": {"text": {"type": "string"}},
                "required": ["text"]}},
    {"name": "thermal", "description": "CPU/battery thermal zone temperatures",
     "schema": {"type": "object", "properties": {}}},
    {"name": "device_info", "description": "Model, RAM tier, platform",
     "schema": {"type": "object", "properties": {}}},
]


def _termux(args, timeout=15):
    cmd = ["termux-" + args[0]] + list(args[1:])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"{cmd[0]} rc={r.returncode}: {r.stderr.strip()[:200]}")
        return r.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("termux-api not installed (pkg install termux-api)")


def _battery():
    try:
        out = _termux(["battery"])
        return out
    except RuntimeError as e:
        # fallback: sysfs
        for p in ("/sys/class/power_supply/battery/capacity",
                  "/sys/class/power_supply/BAT0/capacity"):
            try:
                with open(p, encoding="utf-8") as f:
                    return f"capacity: {f.read().strip()}% (sysfs)"
            except OSError:
                continue
        raise RuntimeError("no battery info available")


def _thermal():
    zones = []
    try:
        entries = sorted(os.listdir("/sys/class/thermal"))
    except OSError:
        entries = []
    for name in entries:
        if not name.startswith("thermal_zone"):
            continue
        try:
            with open(f"/sys/class/thermal/{name}/temp", encoding="utf-8") as f:
                v = int(f.read().strip().split()[0])
            zones.append(f"{name}: {v / 1000.0:.1f}C")
        except (OSError, ValueError):
            continue
    return "; ".join(zones) if zones else "no thermal zones (dev box?)"


def _device_info():
    model = None
    for p in ("/system/build.prop", "/proc/cpuinfo"):
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if p.endswith("build.prop") and line.startswith("ro.product.model"):
                        model = line.split("=", 1)[1].strip()
                        break
        except OSError:
            continue
    ram = None
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    ram = round(int(line.split()[1]) / 1024 / 1024, 1)
                    break
    except OSError:
        pass
    return json.dumps({"model": model, "ram_gb": ram,
                       "platform": sys.platform, "python": sys.version.split()[0]})


def call_tool(name, args):
    if name == "battery":
        return _battery()
    if name == "sms_send":
        return _termux(["sms-send", "-n", args["number"], args["text"]])
    if name == "clipboard_get":
        return _termux(["clipboard-get"])
    if name == "tts_say":
        return _termux(["tts-speak", args["text"]])
    if name == "thermal":
        return _thermal()
    if name == "device_info":
        return _device_info()
    raise KeyError(name)
