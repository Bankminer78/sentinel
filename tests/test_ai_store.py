"""Tests for sentinel.ai_store."""
import pytest
from sentinel import ai_store, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


# --- KV tests ---

def test_kv_set_get(conn):
    ai_store.kv_set(conn, "habits", "meditation_streak", 5)
    assert ai_store.kv_get(conn, "habits", "meditation_streak") == 5


def test_kv_get_default(conn):
    assert ai_store.kv_get(conn, "ns", "missing", default="X") == "X"


def test_kv_complex_value(conn):
    val = {"name": "alice", "tags": ["a", "b"], "count": 3}
    ai_store.kv_set(conn, "users", "alice", val)
    assert ai_store.kv_get(conn, "users", "alice") == val


def test_kv_overwrite(conn):
    ai_store.kv_set(conn, "ns", "k", 1)
    ai_store.kv_set(conn, "ns", "k", 2)
    assert ai_store.kv_get(conn, "ns", "k") == 2


def test_kv_delete(conn):
    ai_store.kv_set(conn, "ns", "k", "v")
    ai_store.kv_delete(conn, "ns", "k")
    assert ai_store.kv_get(conn, "ns", "k") is None


def test_kv_list(conn):
    ai_store.kv_set(conn, "habits", "a", 1)
    ai_store.kv_set(conn, "habits", "b", 2)
    ai_store.kv_set(conn, "other", "c", 3)
    result = ai_store.kv_list(conn, "habits")
    assert result == {"a": 1, "b": 2}


def test_kv_namespaces(conn):
    ai_store.kv_set(conn, "ns1", "k", "v")
    ai_store.kv_set(conn, "ns2", "k", "v")
    namespaces = ai_store.kv_namespaces(conn)
    assert "ns1" in namespaces
    assert "ns2" in namespaces


def test_kv_clear_namespace(conn):
    ai_store.kv_set(conn, "ns", "a", 1)
    ai_store.kv_set(conn, "ns", "b", 2)
    ai_store.kv_clear_namespace(conn, "ns")
    assert ai_store.kv_list(conn, "ns") == {}


# --- Doc tests ---

def test_doc_add(conn):
    did = ai_store.doc_add(conn, "journal", {"text": "Today was good"})
    assert did > 0


def test_doc_get(conn):
    did = ai_store.doc_add(conn, "journal", {"text": "Test"})
    d = ai_store.doc_get(conn, did)
    assert d["doc"]["text"] == "Test"


def test_doc_list(conn):
    ai_store.doc_add(conn, "habits", {"name": "meditate"})
    ai_store.doc_add(conn, "habits", {"name": "exercise"})
    docs = ai_store.doc_list(conn, "habits")
    assert len(docs) == 2


def test_doc_delete(conn):
    did = ai_store.doc_add(conn, "ns", {"x": 1})
    ai_store.doc_delete(conn, did)
    assert ai_store.doc_get(conn, did) is None


def test_doc_search(conn):
    ai_store.doc_add(conn, "journal", {"text": "Today I learned Python"})
    ai_store.doc_add(conn, "journal", {"text": "Today I cooked"})
    results = ai_store.doc_search(conn, "Python")
    assert len(results) == 1


def test_doc_search_namespace(conn):
    ai_store.doc_add(conn, "journal", {"text": "Python is fun"})
    ai_store.doc_add(conn, "notes", {"text": "Python tips"})
    results = ai_store.doc_search(conn, "Python", namespace="journal")
    assert len(results) == 1


def test_doc_with_tags(conn):
    did = ai_store.doc_add(conn, "ns", {"x": 1}, tags=["important", "work"])
    d = ai_store.doc_get(conn, did)
    assert d["tags"] == ["important", "work"]


def test_doc_namespaces(conn):
    ai_store.doc_add(conn, "ns1", {})
    ai_store.doc_add(conn, "ns2", {})
    ns = ai_store.doc_namespaces(conn)
    assert "ns1" in ns
    assert "ns2" in ns


def test_doc_count(conn):
    ai_store.doc_add(conn, "ns", {})
    ai_store.doc_add(conn, "ns", {})
    assert ai_store.doc_count(conn, "ns") == 2


def test_doc_count_all(conn):
    ai_store.doc_add(conn, "a", {})
    ai_store.doc_add(conn, "b", {})
    assert ai_store.doc_count(conn) == 2


def test_doc_clear_namespace(conn):
    ai_store.doc_add(conn, "ns", {})
    ai_store.doc_add(conn, "ns", {})
    ai_store.doc_clear_namespace(conn, "ns")
    assert ai_store.doc_count(conn, "ns") == 0


def test_summary(conn):
    ai_store.kv_set(conn, "k_ns", "k", 1)
    ai_store.doc_add(conn, "d_ns", {})
    s = ai_store.summary(conn)
    assert s["kv_total"] == 1
    assert s["doc_total"] == 1
    assert "k_ns" in s["kv_namespaces"]
    assert "d_ns" in s["doc_namespaces"]
