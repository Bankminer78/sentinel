"""Tests for sentinel.tags."""
import pytest
from sentinel import tags, db


def _mkrule(conn, text="block x.com"):
    return db.add_rule(conn, text)


def test_add_tag(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "social")
    assert tags.get_tags(conn, rid) == ["social"]


def test_add_tag_lowercases(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "Social")
    assert tags.get_tags(conn, rid) == ["social"]


def test_add_tag_strips(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "  work  ")
    assert tags.get_tags(conn, rid) == ["work"]


def test_add_empty_tag_ignored(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "   ")
    assert tags.get_tags(conn, rid) == []


def test_add_tag_idempotent(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "social")
    tags.add_tag(conn, rid, "social")
    assert tags.get_tags(conn, rid) == ["social"]


def test_multiple_tags(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "social")
    tags.add_tag(conn, rid, "work")
    assert sorted(tags.get_tags(conn, rid)) == ["social", "work"]


def test_remove_tag(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "social")
    tags.remove_tag(conn, rid, "social")
    assert tags.get_tags(conn, rid) == []


def test_remove_tag_case(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "social")
    tags.remove_tag(conn, rid, "Social")
    assert tags.get_tags(conn, rid) == []


def test_get_rules_by_tag(conn):
    r1 = _mkrule(conn, "rule1")
    r2 = _mkrule(conn, "rule2")
    tags.add_tag(conn, r1, "social")
    tags.add_tag(conn, r2, "social")
    results = tags.get_rules_by_tag(conn, "social")
    assert len(results) == 2


def test_get_rules_by_tag_empty(conn):
    assert tags.get_rules_by_tag(conn, "nothing") == []


def test_list_all_tags_empty(conn):
    assert tags.list_all_tags(conn) == []


def test_list_all_tags_counts(conn):
    r1 = _mkrule(conn)
    r2 = _mkrule(conn)
    tags.add_tag(conn, r1, "social")
    tags.add_tag(conn, r2, "social")
    tags.add_tag(conn, r1, "work")
    listed = tags.list_all_tags(conn)
    tag_map = {t["tag"]: t["count"] for t in listed}
    assert tag_map["social"] == 2
    assert tag_map["work"] == 1


def test_bulk_toggle_by_tag_off(conn):
    r1 = _mkrule(conn)
    r2 = _mkrule(conn)
    tags.add_tag(conn, r1, "social")
    tags.add_tag(conn, r2, "social")
    count = tags.bulk_toggle_by_tag(conn, "social", False)
    assert count == 2
    rules = db.get_rules(conn, active_only=False)
    for r in rules:
        assert r["active"] == 0


def test_bulk_toggle_by_tag_on(conn):
    r1 = _mkrule(conn)
    tags.add_tag(conn, r1, "social")
    tags.bulk_toggle_by_tag(conn, "social", False)
    tags.bulk_toggle_by_tag(conn, "social", True)
    rules = db.get_rules(conn, active_only=True)
    assert len(rules) == 1


def test_bulk_toggle_no_matches(conn):
    count = tags.bulk_toggle_by_tag(conn, "nothing", False)
    assert count == 0


def test_get_tags_sorted(conn):
    rid = _mkrule(conn)
    tags.add_tag(conn, rid, "zoo")
    tags.add_tag(conn, rid, "apple")
    assert tags.get_tags(conn, rid) == ["apple", "zoo"]
