"""Thin client over the VectCutAPI draft/editing endpoints (stdlib urllib).

Endpoints follow the public VectCut API shape:
  POST /api/drafts            create a draft
  POST /api/drafts/<id>/materials  add text/caption material
  GET  /api/drafts/<id>       inspect a draft

The same client has an --offline mode writing a local JSON manifest so the
pipeline is testable without the cloud API.
"""
import json
import os
import urllib.error
import urllib.request


class VectCutError(Exception):
    pass


class VectCut:
    def __init__(self, base_url=None, api_key=None, timeout=60):
        self.base_url = (base_url or os.environ.get("VECTCUT_URL") or "").rstrip("/")
        self.api_key = api_key or os.environ.get("VECTCUT_KEY")
        self.timeout = timeout

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.base_url + path, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise VectCutError(f"vectcut {path}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:200]}")

    def create_draft(self, name, aspect="9:16"):
        if not self.base_url:
            raise VectCutError("no VECTCUT_URL configured")
        return self._post("/api/drafts", {"name": name, "aspect": aspect})

    def add_caption_material(self, draft_id, text, start_ms, end_ms, style="default"):
        if not self.base_url:
            raise VectCutError("no VECTCUT_URL configured")
        return self._post(f"/api/drafts/{draft_id}/materials", {
            "type": "text", "text": text, "start_ms": start_ms,
            "end_ms": end_ms, "style": style})

    def export(self, draft_id, fmt="draft"):
        if not self.base_url:
            raise VectCutError("no VECTCUT_URL configured")
        return self._post(f"/api/drafts/{draft_id}/export", {"format": fmt})


class OfflineVectCut:
    """Writes a local JSON manifest instead of calling the API."""

    def __init__(self, out_dir):
        self.out_dir = out_dir
        self._drafts = {}

    def create_draft(self, name, aspect="9:16"):
        draft_id = f"draft-{len(self._drafts) + 1:03d}"
        self._drafts[draft_id] = {"name": name, "aspect": aspect, "materials": []}
        return {"id": draft_id}

    def add_caption_material(self, draft_id, text, start_ms, end_ms, style="default"):
        self._drafts[draft_id]["materials"].append(
            {"type": "text", "text": text, "start_ms": start_ms,
             "end_ms": end_ms, "style": style})
        return {"ok": True}

    def export(self, draft_id, fmt="draft"):
        d = self._drafts[draft_id]
        os.makedirs(self.out_dir, exist_ok=True)
        path = os.path.join(self.out_dir, f"{draft_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        return {"ok": True, "path": path}
