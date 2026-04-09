"""Tests for sentinel.zettelkasten."""
import pytest
from sentinel import zettelkasten as zk, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_zettel(conn):
    zid = zk.create_zettel(conn, "Test", "Content", ["tag1"])
    assert zid > 0


def test_get_zettel(conn):
    zid = zk.create_zettel(conn, "Test", "Content")
    z = zk.get_zettel(conn, zid)
    assert z["title"] == "Test"


def test_update_zettel(conn):
    zid = zk.create_zettel(conn, "Old", "Old content")
    zk.update_zettel(conn, zid, content="New content", title="New")
    z = zk.get_zettel(conn, zid)
    assert z["title"] == "New"


def test_delete_zettel(conn):
    zid = zk.create_zettel(conn, "Delete", "content")
    zk.delete_zettel(conn, zid)
    assert zk.get_zettel(conn, zid) is None


def test_list_zettels(conn):
    zk.create_zettel(conn, "Z1", "c1")
    zk.create_zettel(conn, "Z2", "c2")
    assert len(zk.list_zettels(conn)) == 2


def test_link_zettels(conn):
    z1 = zk.create_zettel(conn, "Z1", "c")
    z2 = zk.create_zettel(conn, "Z2", "c")
    lid = zk.link_zettels(conn, z1, z2)
    assert lid > 0


def test_get_links(conn):
    z1 = zk.create_zettel(conn, "Z1", "c")
    z2 = zk.create_zettel(conn, "Z2", "c")
    zk.link_zettels(conn, z1, z2)
    links = zk.get_links(conn, z1)
    assert len(links["outgoing"]) == 1


def test_search_zettels(conn):
    zk.create_zettel(conn, "Python", "About Python programming")
    results = zk.search_zettels(conn, "Python")
    assert len(results) == 1


def test_zettels_by_tag(conn):
    zk.create_zettel(conn, "Z1", "c", ["python"])
    zk.create_zettel(conn, "Z2", "c", ["js"])
    results = zk.zettels_by_tag(conn, "python")
    assert len(results) == 1


def test_extract_mentions():
    text = "See [[Other Note]] and [[Another]]"
    mentions = zk.extract_mentions(text)
    assert "Other Note" in mentions
    assert "Another" in mentions


def test_count_zettels(conn):
    zk.create_zettel(conn, "Z1", "c")
    zk.create_zettel(conn, "Z2", "c")
    assert zk.count_zettels(conn) == 2


def test_orphan_zettels(conn):
    zk.create_zettel(conn, "Orphan", "c")
    orphans = zk.orphan_zettels(conn)
    assert len(orphans) == 1
