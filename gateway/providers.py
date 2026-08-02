"""Provider abstraction: any OpenAI-compatible endpoint, local or cloud.

No deps beyond stdlib (urllib). Two built-ins:
  - OpenAIProvider   (cloud or local OpenAI-compatible server)
  - AndroidLLM       (local androidllm with /health check)
"""
import json
import urllib.error
import urllib.request


class ProviderError(Exception):
    pass


class Provider:
    name = "base"

    def __init__(self, base_url, api_key=None, model="auto", timeout=60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def health(self):
        """True when the provider is reachable. Base: chat endpoint probe."""
        return self.chat("ping", max_tokens=1, _probe=True)

    def chat(self, messages, max_tokens=256, temperature=0.7, stream=False, _probe=False):
        payload = {
            "model": self.model,
            "messages": messages if isinstance(messages, list) else [
                {"role": "user", "content": messages}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if stream:
            return self._stream_chat(payload)
        return self._post("/v1/chat/completions", payload, _probe=_probe)

    def _post(self, path, payload, _probe=False):
        req = urllib.request.Request(
            self.base_url + path, data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if _probe:
                return None
            raise ProviderError(f"{self.name} HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
        except OSError as e:
            if _probe:
                return None
            raise ProviderError(f"{self.name} unreachable: {e}")

    def _stream_chat(self, payload):
        req = urllib.request.Request(
            self.base_url + "/v1/chat/completions", data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            for raw in r:
                line = raw.decode("utf-8").strip()
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data and data != "[DONE]":
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue

    def text_from(self, resp):
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError(f"{self.name} unexpected response shape")


class OpenAIProvider(Provider):
    name = "openai"


class AndroidLLM(Provider):
    name = "androidllm"

    def health(self):
        """/health is unauthenticated and fast on androidllm."""
        req = urllib.request.Request(self.base_url + "/health", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status == 200
        except OSError:
            return False
