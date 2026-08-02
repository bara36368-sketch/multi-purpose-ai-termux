"""Cloud -> local fallback router.

Routing policy (chain of providers, first healthy wins):
  1. cloud provider (if configured and healthy)
  2. androidllm local (if configured and healthy)
  3. ProviderError with a polite message

Health is re-checked per request with a short timeout and a small cache so
we don't hammer a down server on every message.
"""
import time

from providers import ProviderError


class Router:
    def __init__(self, providers, health_ttl=15.0):
        self.providers = list(providers)
        self._health_ttl = health_ttl
        self._health_cache = {}  # name -> (healthy, checked_at)

    def _healthy(self, p):
        now = time.time()
        cached = self._health_cache.get(p.name)
        if cached and now - cached[1] < self._health_ttl:
            return cached[0]
        ok = False
        try:
            ok = bool(p.health())
        except Exception:
            ok = False
        self._health_cache[p.name] = (ok, now)
        return ok

    def route(self, messages, **kwargs):
        """Return (provider_name, response_dict) from the first healthy provider."""
        errors = []
        for p in self.providers:
            if not self._healthy(p):
                errors.append(f"{p.name}: unhealthy")
                continue
            try:
                return p.name, p.chat(messages, **kwargs)
            except ProviderError as e:
                errors.append(str(e))
                continue
        raise ProviderError("all providers down: " + "; ".join(errors))

    def stats(self):
        return {name: state for name, state in self._health_cache.items()}
