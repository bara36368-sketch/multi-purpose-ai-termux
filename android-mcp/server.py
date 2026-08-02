"""MCP server for Android phone capabilities.

Implements the Model Context Protocol over stdio (JSON-RPC 2.0):
    -> {"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
    <- {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":...,"capabilities":{"tools":{}}}}
    -> {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
    -> {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"battery","arguments":{}}}

Usage:
    python server.py                          # stdio mode
    python server.py --http 0.0.0.0:9000 --token sk-...   # remote mode
"""
import argparse
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools import TOOLS, call_tool  # noqa: E402
from permissions import is_allowed, load_permissions  # noqa: E402

PROTOCOL_VERSION = "2025-03-26"


def make_response(req_id, result=None, error=None):
    return {"jsonrpc": "2.0", "id": req_id, "result": result, "error": error}


def handle_message(msg, perms):
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}
    if method == "initialize":
        return make_response(req_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "android-mcp", "version": "0.1.0"},
        })
    if method == "tools/list":
        return make_response(req_id, {"tools": [
            {"name": t["name"], "description": t["description"],
             "inputSchema": t.get("schema", {"type": "object", "properties": {}})}
            for t in TOOLS]})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if not is_allowed(perms, name):
            return make_response(req_id, error={"code": -32001, "message": f"tool {name} not permitted"})
        if name not in {t["name"] for t in TOOLS}:
            return make_response(req_id, error={"code": -32602, "message": f"unknown tool {name}"})
        try:
            content = call_tool(name, args)
            return make_response(req_id, {"content": [{"type": "text", "text": content}]})
        except Exception as e:
            return make_response(req_id, error={"code": -32603, "message": str(e)})
    if method == "notifications/initialized":
        return None
    return make_response(req_id, error={"code": -32601, "message": f"unknown method {method}"})


def serve_stdio(perms):
    buf = ""
    for chunk in sys.stdin.buffer:
        buf += chunk.decode("utf-8", "replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            resp = handle_message(msg, perms)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()


class _HTTP(BaseHTTPRequestHandler):
    perms = None
    token = None

    def log_message(self, *a):
        pass

    def _ok(self, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.token:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {self.token}":
                self._ok({"jsonrpc": "2.0", "id": None,
                          "error": {"code": -32001, "message": "unauthorized"}})
                return
        length = int(self.headers.get("Content-Length", 0))
        try:
            msg = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            self._ok({"jsonrpc": "2.0", "id": None,
                      "error": {"code": -32700, "message": "parse error"}})
            return
        resp = handle_message(msg, self.perms)
        self._ok(resp if resp is not None else {"jsonrpc": "2.0", "id": None})

    def do_GET(self):
        self._ok({"name": "android-mcp", "ok": True})


def main(argv=None):
    ap = argparse.ArgumentParser(prog="android-mcp", description=__doc__)
    ap.add_argument("--http", help="host:port for HTTP transport (else stdio)")
    ap.add_argument("--token", help="bearer token for HTTP transport")
    ap.add_argument("--perms", help="permissions JSON (default: permissions.json)")
    args = ap.parse_args(argv)

    perms = load_permissions(args.perms)
    if args.http:
        host, _, port = args.http.rpartition(":")
        _HTTP.perms = perms
        _HTTP.token = args.token
        srv = ThreadingHTTPServer((host or "0.0.0.0", int(port)), _HTTP)
        print(f"android-mcp http on {host or '0.0.0.0'}:{port}", flush=True)
        srv.serve_forever()
    else:
        serve_stdio(perms)


if __name__ == "__main__":
    main()
