"""Retrieval: hybrid keyword + graph adjacency + source tier, then answer.

Scoring per page (simple, explainable):
    base = 1.0 per query term hit in text (title/entities weighted more)
    graph_boost = +0.5 for each neighbor that also matches the query
    tier = pages from 'primary' chats weigh more than 'archived'
"""
from graph import Brain


def _score(page, terms, neighbors):
    text = page.get("text", "").lower()
    title = page.get("id", "").lower()
    ents = " ".join(page.get("entities", [])).lower()
    base = 0.0
    for t in terms:
        if t in title or t in ents:
            base += 2.0
        elif t in text:
            base += 1.0
    if base == 0:
        return None
    graph = 0.5 * sum(1 for n in neighbors if any(t in n[1] for t in terms))
    tier = 1.0 if page.get("chat") == "primary" else 0.8
    return round((base + graph) * tier, 3)


def retrieve(brain, query, top_k=5):
    terms = [t for t in query.lower().split() if len(t) > 2]
    if not terms:
        return []
    hits = []
    for pid, page in brain.pages.items():
        neigh = [(n, brain.page(n) or {}) for n in brain.neighbors(pid)]
        s = _score(page, terms, neigh)
        if s is not None:
            hits.append((s, pid, page, neigh))
    hits.sort(key=lambda h: h[0], reverse=True)
    return hits[:top_k]


def answer(brain, query, top_k=3):
    """Template synthesis: citations + explicit gap analysis. No LLM."""
    hits = retrieve(brain, query, top_k=top_k)
    if not hits:
        return {"answer": "I don't have anything on that yet.",
                "citations": [], "gaps": [query], "known": False}
    lines, citations, gaps = [], [], []
    for s, pid, page, neigh in hits:
        snippet = page.get("text", "")[:200].strip()
        citations.append({"page": pid, "score": s, "snippet": snippet})
        lines.append(f"- {pid} (score {s}): {snippet}...")
    gaps = [t for t in query.lower().split() if len(t) > 2
            and not any(t in page.get("text", "").lower() for _, _, page, _ in hits)]
    body = "Here's what I found:\n" + "\n".join(lines)
    if gaps:
        body += f"\n\nNot confirmed yet: {', '.join(gaps)}"
    return {"answer": body, "citations": citations, "gaps": gaps, "known": True}


def precision_at_k(brain, query, expected_pids, k=5):
    got = [h[1] for h in retrieve(brain, query, top_k=k)]
    hits = len(set(got) & set(expected_pids))
    return hits / min(k, len(expected_pids))
