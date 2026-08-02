"""Zero-LLM entity graph over pages.

Edges are extracted from page structure alone:
  - page <-> participants   (participant)
  - page <-> entities       (mentions)
  - page <-> page           (co_participant when sharing a participant)
No embedding model, no LLM calls, append-only JSON edges.
"""
import json
import os


class Brain:
    def __init__(self, dirpath):
        self.dir = dirpath
        self.pages_path = os.path.join(dirpath, "pages.json")
        self.edges_path = os.path.join(dirpath, "edges.json")
        os.makedirs(dirpath, exist_ok=True)
        self.pages = self._load(self.pages_path)
        self.edges = self._load(self.edges_path)

    @staticmethod
    def _load(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, path, obj):
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, path)

    def add_page(self, page):
        self.pages[page["id"]] = page
        for ent in page.get("entities", []):
            self._edge("entity", ent, page["id"])
        for p in page.get("participants", []):
            self._edge("participant", p, page["id"])
        self._save(self.pages_path, self.pages)
        self._save(self.edges_path, self.edges)
        return page["id"]

    def _edge(self, kind, src, dst):
        key = f"{kind}:{src}"
        if key not in self.edges:
            self.edges[key] = {"kind": kind, "node": src, "pages": []}
        if dst not in self.edges[key]["pages"]:
            self.edges[key]["pages"].append(dst)

    def node(self, kind, name):
        return self.edges.get(f"{kind}:{name}", {"kind": kind, "node": name, "pages": []})

    def page(self, pid):
        return self.pages.get(pid)

    def neighbors(self, pid):
        """Pages sharing an entity or participant with pid (deduped)."""
        page = self.pages.get(pid, {})
        out = set()
        for ent in page.get("entities", []):
            out.update(self.node("entity", ent)["pages"])
        for p in page.get("participants", []):
            out.update(self.node("participant", p)["pages"])
        out.discard(pid)
        return sorted(out)

    def search(self, term):
        """Pages whose text contains term (case-insensitive)."""
        term = term.lower()
        return [pid for pid, p in self.pages.items() if term in p.get("text", "").lower()]
