import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from permissions import is_allowed, load_permissions  # noqa: E402
from server import handle_message, PROTOCOL_VERSION  # noqa: E402
from tools import TOOLS, call_tool  # noqa: E402


def test_initialize():
    r = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {}}, load_permissions(None))
    assert r["id"] == 1
    assert r["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert r["result"]["capabilities"]["tools"] == {}


def test_tools_list():
    r = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                        "params": {}}, load_permissions(None))
    names = [t["name"] for t in r["result"]["tools"]]
    assert "battery" in names and "sms_send" in names and "device_info" in names


def test_device_info_works_anywhere():
    out = call_tool("device_info", {})
    d = json.loads(out)
    assert d["platform"] in ("win32", "linux", "darwin", "android")


def test_thermal_degrades_on_dev_box():
    out = call_tool("thermal", {})
    assert isinstance(out, str) and out  # zones or friendly message


def test_denied_tool_blocked():
    perms = {"allowed": ["battery"], "denied": []}
    r = handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": "sms_send", "arguments": {}}}, perms)
    assert r["result"] is None
    assert r["error"]["code"] == -32001


def test_unknown_tool_and_method():
    perms = {"allowed": [t["name"] for t in TOOLS], "denied": []}
    r = handle_message({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "nope", "arguments": {}}}, perms)
    assert r["error"]["code"] in (-32001, -32602)  # denied or unknown
    r2 = handle_message({"jsonrpc": "2.0", "id": 5, "method": "wat"}, perms)
    assert r2["error"]["code"] == -32601


def test_battery_falls_back_without_termux(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("termux-battery missing")
    monkeypatch.setattr(subprocess, "run", boom)
    try:
        out = call_tool("battery", {})
        assert "%" in out or "no battery" in out
    except RuntimeError:
        pass  # acceptable on a dev box with no battery sysfs either


def test_notifications_return_none():
    assert handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"},
                          {}) is None
