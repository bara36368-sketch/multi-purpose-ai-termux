import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import Brain  # noqa: E402
from ingest import extract_entities, pages_from_lines, parse_line  # noqa: E402
from retrieve import answer, precision_at_k, retrieve  # noqa: E402

SESSIONS = [
    '{"ts": "2026-08-01T10:00:00", "chat": "primary", "who": "alice", "text": "we deployed the qwen15 model on the phone"}',
    '{"ts": "2026-08-01T10:01:00", "chat": "primary", "who": "bob", "text": "nice, what about the API key rotation?"}',
    '{"ts": "2026-08-01T10:02:00", "chat": "primary", "who": "alice", "text": "[[api key]] stored in ~/androidllm/api_key"}',
    '{"ts": "2026-08-02T09:00:00", "chat": "primary", "who": "bob", "text": "benchmark showed 0.7 tok/s on the Helio G85"}',
    '{"ts": "2026-08-02T09:05:00", "chat": "archived", "who": "carol", "text": "we tested clipboard mcp tool too"}',
]


def make_brain(tmp_path):
    b = Brain(str(tmp_path))
    for pid, page in pages_from_lines(SESSIONS).items():
        b.add_page(page)
    return b


def test_parse_line_both_formats():
    assert parse_line("alice: hello")["who"] == "alice"
    j = parse_line('{"who": "x", "text": "y"}')
    assert j["who"] == "x" and j["text"] == "y"


def test_extract_entities():
    e = extract_entities("ping @bob about [[api key]], cc Bob Smith")
    assert "bob" in e and "api key" in e and "Bob Smith" in e


def test_pages_grouped():
    pages = pages_from_lines(SESSIONS)
    assert len(pages) >= 2  # two days
    assert all(p["messages"] > 0 for p in pages.values())


def test_graph_edges_and_neighbors(tmp_path):
    b = make_brain(tmp_path)
    alice = b.node("participant", "alice")
    assert alice["pages"], "alice should link to pages"
    assert "entity:api key" in b.edges
    pages = b.search("tok/s")
    assert len(pages) == 1


def test_retrieve_ranks_and_p5(tmp_path):
    b = make_brain(tmp_path)
    expected = [pid for pid in b.search("api key")]
    assert precision_at_k(b, "api key rotation", expected, k=5) == 1.0
    hits = retrieve(b, "qwen15 phone")
    assert hits and hits[0][1] in b.search("qwen15")


def test_answer_citations_and_gaps(tmp_path):
    b = make_brain(tmp_path)
    a = answer(b, "where is the api key stored")
    assert a["known"] is True
    assert a["citations"], "must cite pages"
    assert any("api_key" in c["snippet"] for c in a["citations"])
    unknown = answer(b, "quantum teleportation notes")
    assert unknown["known"] is False and unknown["gaps"]
