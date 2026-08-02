"""Copy of gateway provider for self-contained bench runs on the phone."""
import json
import urllib.error
import urllib.request


class AndroidLLM:
    def __init__(self, base_url, api_key=None, model="auto", timeout=600):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def health(self):
        req = urllib.request.Request(self.base_url + "/health", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status == 200
        except OSError:
            return False

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def chat(self, messages, max_tokens=128, temperature=0.7, stream=False):
        payload = {"model": self.model, "messages": messages,
                   "max_tokens": max_tokens, "temperature": temperature,
                   "stream": stream}
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(), method="POST")
        if not stream:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            for raw in r:
                line = raw.decode("utf-8").strip()
                if line.startswith("data:") and line[5:].strip() not in ("", "[DONE]"):
                    try:
                        yield json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
