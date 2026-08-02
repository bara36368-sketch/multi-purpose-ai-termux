"""Router tests with a fake healthy/unhealthy provider pair."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from providers import AndroidLLM, OpenAIProvider, ProviderError
from router import Router


class Fake(OpenAIProvider):
    def __init__(self, name, healthy, reply=None):
        super().__init__("http://fake")
        self.name = name
        self.healthy = healthy
        self.reply = reply or {"choices": [{"message": {"content": f"from {name}"}}]}
        self.calls = 0

    def health(self):
        return self.healthy

    def chat(self, messages, **kwargs):
        self.calls += 1
        return self.reply


def test_prefers_healthy_cloud():
    cloud, local = Fake("openai", True), Fake("androidllm", True)
    r = Router([cloud, local])
    name, resp = r.route([{"role": "user", "content": "hi"}])
    assert name == "openai"
    assert cloud.calls == 1 and local.calls == 0


def test_falls_back_to_local_when_cloud_down():
    cloud, local = Fake("openai", False), Fake("androidllm", True)
    r = Router([cloud, local])
    name, resp = r.route([{"role": "user", "content": "hi"}])
    assert name == "androidllm"
    assert r.stats()["openai"] == (False, r.stats()["openai"][1])


def test_all_down_raises():
    r = Router([Fake("openai", False), Fake("androidllm", False)])
    with pytest.raises(ProviderError):
        r.route([{"role": "user", "content": "hi"}])


def test_androidllm_health_hits_health_endpoint():
    class Ok:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass
    import urllib.request as u
    orig = u.urlopen
    seen = []
    def fake_urlopen(req, timeout=5):
        seen.append(req.full_url)
        return Ok()
    u.urlopen = fake_urlopen
    try:
        assert AndroidLLM("http://127.0.0.1:8080").health() is True
        assert seen == ["http://127.0.0.1:8080/health"]
    finally:
        u.urlopen = orig


def test_health_cache_avoids_reprobe():
    cloud, local = Fake("openai", False), Fake("androidllm", True)
    r = Router([cloud, local])
    r.route([{"role": "user", "content": "a"}])
    r.route([{"role": "user", "content": "b"}])
    assert cloud.calls == 0 and local.calls == 2
