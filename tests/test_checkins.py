"""Tests for sentinel.checkins — periodic focus check-ins."""
import time
import pytest
from sentinel import checkins


class TestSchedule:
    def test_schedule_returns_id(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        assert isinstance(cid, int)
        assert cid > 0

    def test_schedule_creates_active_entry(self, conn):
        checkins.schedule_checkin(conn, 45)
        active = checkins.get_active_checkins(conn)
        assert len(active) == 1
        assert active[0]["interval_minutes"] == 45

    def test_multiple_schedules(self, conn):
        checkins.schedule_checkin(conn, 30)
        checkins.schedule_checkin(conn, 60)
        assert len(checkins.get_active_checkins(conn)) == 2


class TestCancel:
    def test_cancel_marks_inactive(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        checkins.cancel_checkin(conn, cid)
        assert checkins.get_active_checkins(conn) == []

    def test_cancel_one_keeps_others(self, conn):
        a = checkins.schedule_checkin(conn, 30)
        checkins.schedule_checkin(conn, 60)
        checkins.cancel_checkin(conn, a)
        active = checkins.get_active_checkins(conn)
        assert len(active) == 1
        assert active[0]["interval_minutes"] == 60


class TestResponses:
    def test_record_response_returns_id(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        rid = checkins.record_response(conn, cid, 4, "feeling good")
        assert rid > 0

    def test_record_response_stored(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        checkins.record_response(conn, cid, 4, "focused")
        hist = checkins.get_checkin_history(conn)
        assert len(hist) == 1
        assert hist[0]["mood"] == 4
        assert hist[0]["note"] == "focused"

    def test_record_response_default_note(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        checkins.record_response(conn, cid, 3)
        hist = checkins.get_checkin_history(conn)
        assert hist[0]["note"] == ""

    def test_history_orders_desc(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        checkins.record_response(conn, cid, 2)
        time.sleep(0.01)
        checkins.record_response(conn, cid, 5)
        hist = checkins.get_checkin_history(conn)
        assert hist[0]["mood"] == 5

    def test_history_limit(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        for i in range(5):
            checkins.record_response(conn, cid, i)
        hist = checkins.get_checkin_history(conn, limit=3)
        assert len(hist) == 3


class TestTiming:
    def test_time_until_no_active(self, conn):
        assert checkins.time_until_next_checkin(conn) == -1

    def test_time_until_positive(self, conn):
        checkins.schedule_checkin(conn, 30)
        t = checkins.time_until_next_checkin(conn)
        assert t > 0
        assert t <= 30 * 60

    def test_time_until_picks_soonest(self, conn):
        checkins.schedule_checkin(conn, 60)
        checkins.schedule_checkin(conn, 10)
        t = checkins.time_until_next_checkin(conn)
        assert t <= 10 * 60

    def test_should_checkin_now_false_fresh(self, conn):
        checkins.schedule_checkin(conn, 30)
        assert checkins.should_checkin_now(conn) is False

    def test_should_checkin_now_true_expired(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        # Force last_triggered into the past
        conn.execute("UPDATE checkins SET last_triggered=? WHERE id=?",
                     (time.time() - 3600, cid))
        conn.commit()
        assert checkins.should_checkin_now(conn) is True

    def test_record_updates_last_triggered(self, conn):
        cid = checkins.schedule_checkin(conn, 30)
        conn.execute("UPDATE checkins SET last_triggered=? WHERE id=?",
                     (time.time() - 3600, cid))
        conn.commit()
        checkins.record_response(conn, cid, 5)
        assert checkins.should_checkin_now(conn) is False
