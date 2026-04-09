"""Tests for sentinel.rituals — structured morning/evening routines."""
import pytest
from sentinel import rituals


class TestCreate:
    def test_create_returns_id(self, conn):
        rid = rituals.create_ritual(conn, "Morning", "morning", ["stretch", "meditate"])
        assert rid > 0

    def test_create_stores_items(self, conn):
        rid = rituals.create_ritual(conn, "Evening", "evening", ["journal", "plan"])
        all_r = rituals.get_rituals(conn)
        assert len(all_r) == 1
        assert all_r[0]["items"] == ["journal", "plan"]
        assert all_r[0]["time_of_day"] == "evening"

    def test_create_multiple(self, conn):
        rituals.create_ritual(conn, "A", "morning", ["a"])
        rituals.create_ritual(conn, "B", "evening", ["b"])
        assert len(rituals.get_rituals(conn)) == 2


class TestStart:
    def test_start_returns_dict(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["x", "y", "z"])
        r = rituals.start_ritual(conn, rid)
        assert r["ritual_id"] == rid
        assert r["items"] == ["x", "y", "z"]
        assert r["completed"] == []

    def test_start_missing_returns_none(self, conn):
        assert rituals.start_ritual(conn, 999) is None

    def test_start_resets_progress(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a", "b"])
        rituals.start_ritual(conn, rid)
        rituals.complete_ritual_item(conn, rid, 0)
        rituals.start_ritual(conn, rid)
        p = rituals.get_ritual_progress(conn, rid)
        assert p["completed"] == 0


class TestComplete:
    def test_complete_increments(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a", "b", "c"])
        rituals.start_ritual(conn, rid)
        rituals.complete_ritual_item(conn, rid, 0)
        p = rituals.get_ritual_progress(conn, rid)
        assert p["completed"] == 1

    def test_complete_all(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a", "b"])
        rituals.start_ritual(conn, rid)
        rituals.complete_ritual_item(conn, rid, 0)
        rituals.complete_ritual_item(conn, rid, 1)
        p = rituals.get_ritual_progress(conn, rid)
        assert p["completed"] == 2
        assert p["percent"] == 100.0

    def test_complete_no_duplicate(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a", "b"])
        rituals.start_ritual(conn, rid)
        rituals.complete_ritual_item(conn, rid, 0)
        rituals.complete_ritual_item(conn, rid, 0)
        p = rituals.get_ritual_progress(conn, rid)
        assert p["completed"] == 1


class TestProgress:
    def test_progress_none_for_missing(self, conn):
        assert rituals.get_ritual_progress(conn, 999) is None

    def test_progress_before_start(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a", "b"])
        p = rituals.get_ritual_progress(conn, rid)
        assert p["completed"] == 0
        assert p["total"] == 2

    def test_progress_percent_partial(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a", "b", "c", "d"])
        rituals.start_ritual(conn, rid)
        rituals.complete_ritual_item(conn, rid, 0)
        p = rituals.get_ritual_progress(conn, rid)
        assert p["percent"] == 25.0

    def test_progress_empty_items(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", [])
        p = rituals.get_ritual_progress(conn, rid)
        assert p["percent"] == 0.0


class TestHistory:
    def test_history_includes_today(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a"])
        rituals.start_ritual(conn, rid)
        rituals.complete_ritual_item(conn, rid, 0)
        h = rituals.ritual_history(conn, rid)
        assert len(h) == 1

    def test_history_empty(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a"])
        assert rituals.ritual_history(conn, rid) == []


class TestDelete:
    def test_delete_removes(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a"])
        rituals.delete_ritual(conn, rid)
        assert rituals.get_rituals(conn) == []

    def test_delete_removes_log(self, conn):
        rid = rituals.create_ritual(conn, "R", "morning", ["a"])
        rituals.start_ritual(conn, rid)
        rituals.complete_ritual_item(conn, rid, 0)
        rituals.delete_ritual(conn, rid)
        assert rituals.ritual_history(conn, rid) == []
