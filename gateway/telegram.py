"""Telegram channel: long-polling Bot API client (stdlib only)."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"


class Telegram:
    def __init__(self, token, timeout=25, poll_interval=1.0):
        self.token = token
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._offset = 0

    def _call(self, method, payload=None):
        data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(API.format(token=self.token, method=method),
                                     data=data,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"telegram {method} failed: {e.code} {body[:200]}")

    def get_updates(self):
        out = []
        for batch in self._poll():
            for u in batch:
                self._offset = max(self._offset, u["update_id"] + 1)
                out.append(u)
        return out

    def _poll(self):
        payload = {"timeout": 5, "offset": self._offset}
        resp = self._call("getUpdates", payload)
        if resp.get("ok"):
            yield resp.get("result", [])
        time.sleep(self.poll_interval)

    def send(self, chat_id, text, parse_mode="HTML"):
        return self._call("sendMessage", {"chat_id": chat_id, "text": text,
                                          "parse_mode": parse_mode})

    @staticmethod
    def text_of(update):
        msg = update.get("message") or {}
        return msg.get("text") or msg.get("caption") or ""

    @staticmethod
    def chat_id_of(update):
        return (update.get("message") or {}).get("chat", {}).get("id")

    @staticmethod
    def name_of(update):
        msg = update.get("message") or {}
        u = msg.get("from") or {}
        return u.get("username") or u.get("first_name") or "anon"
