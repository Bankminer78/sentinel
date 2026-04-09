"""Tests for sentinel.stats — scores, streaks, goals, summaries."""

import time
from datetime import datetime, timedelta

import pytest

from sentinel import db, stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_ts():
    """Midpoint-of-today timestamp (so it falls inside _day_bounds(today))."""
    today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    return today.timestamp()


def _ts_for(date_str, hour=12):
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hour)
    return d.timestamp()


def _insert_activity(conn, ts, domain, duration_s, app="chrome", title="", url=""):
    """Directly insert a row with a controlled timestamp."""
    conn.execute(
        "INSERT INTO activity_log (ts,app,title,url,domain,verdict,rule_id,duration_s) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (ts, app, title, url, domain, None, None, duration_s),
    )
    conn.commit()


def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# calculate_score
# ---------------------------------------------------------------------------


class TestCalculateScore:
    """Tests for stats.calculate_score."""

    def test_empty_log_returns_zero(self, conn):
        assert stats.calculate_score(conn) == 0.0

    def test_all_productive_returns_100(self, conn):
        db.save_seen(conn, "github.com", "work")
        _insert_activity(conn, _now_ts(), "github.com", 600)
        assert stats.calculate_score(conn) == 100.0

    def test_all_distracted_returns_zero(self, conn):
        db.save_seen(conn, "netflix.com", "streaming")
        _insert_activity(conn, _now_ts(), "netflix.com", 600)
        assert stats.calculate_score(conn) == 0.0

    def test_mixed_activity_returns_percentage(self, conn):
        db.save_seen(conn, "github.com", "work")
        db.save_seen(conn, "netflix.com", "streaming")
        _insert_activity(conn, _now_ts(), "github.com", 750)
        _insert_activity(conn, _now_ts(), "netflix.com", 250)
        # productive 750 / total 1000 = 75.0
        assert stats.calculate_score(conn) == 75.0

    def test_date_filter_excludes_other_days(self, conn):
        db.save_seen(conn, "github.com", "work")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        _insert_activity(conn, _ts_for(yesterday), "github.com", 500)
        # Today has nothing → 0.0
        assert stats.calculate_score(conn, _today_str()) == 0.0
        # Yesterday has a record → 100.0
        assert stats.calculate_score(conn, yesterday) == 100.0

    def test_unknown_domain_counts_as_productive(self, conn):
        # No seen_domains row → categorized as productive
        _insert_activity(conn, _now_ts(), "unknown.example.com", 300)
        assert stats.calculate_score(conn) == 100.0


# ---------------------------------------------------------------------------
# get_daily_breakdown
# ---------------------------------------------------------------------------


class TestGetDailyBreakdown:
    """Tests for stats.get_daily_breakdown."""

    def test_empty_returns_zero_buckets(self, conn):
        b = stats.get_daily_breakdown(conn)
        assert b == {"productive": 0.0, "distracting": 0.0, "neutral": 0.0, "total": 0.0}

    def test_categorizes_by_seen_domains(self, conn):
        db.save_seen(conn, "github.com", "work")
        db.save_seen(conn, "twitter.com", "social")
        _insert_activity(conn, _now_ts(), "github.com", 100)
        _insert_activity(conn, _now_ts(), "twitter.com", 200)
        b = stats.get_daily_breakdown(conn)
        assert b["productive"] == 100
        assert b["distracting"] == 200
        assert b["total"] == 300

    def test_unseen_domain_is_productive(self, conn):
        _insert_activity(conn, _now_ts(), "newsite.com", 50)
        b = stats.get_daily_breakdown(conn)
        assert b["productive"] == 50
        assert b["distracting"] == 0

    def test_handles_none_duration(self, conn):
        conn.execute(
            "INSERT INTO activity_log (ts,domain,duration_s) VALUES (?,?,?)",
            (_now_ts(), "github.com", None),
        )
        conn.commit()
        b = stats.get_daily_breakdown(conn)
        assert b["total"] == 0

    def test_respects_date_str_filter(self, conn):
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        _insert_activity(conn, _ts_for(yesterday), "github.com", 400)
        _insert_activity(conn, _now_ts(), "github.com", 100)
        b_today = stats.get_daily_breakdown(conn, _today_str())
        b_yday = stats.get_daily_breakdown(conn, yesterday)
        assert b_today["total"] == 100
        assert b_yday["total"] == 400


# ---------------------------------------------------------------------------
# get_top_distractions
# ---------------------------------------------------------------------------


class TestGetTopDistractions:
    """Tests for stats.get_top_distractions."""

    def test_empty_log_returns_empty(self, conn):
        assert stats.get_top_distractions(conn) == []

    def test_only_distracting_returned(self, conn):
        db.save_seen(conn, "netflix.com", "streaming")
        db.save_seen(conn, "github.com", "work")
        _insert_activity(conn, _now_ts(), "netflix.com", 500)
        _insert_activity(conn, _now_ts(), "github.com", 800)
        out = stats.get_top_distractions(conn)
        assert len(out) == 1
        assert out[0]["domain"] == "netflix.com"
        assert out[0]["seconds"] == 500

    def test_ordered_by_total_time_desc(self, conn):
        db.save_seen(conn, "netflix.com", "streaming")
        db.save_seen(conn, "twitter.com", "social")
        db.save_seen(conn, "reddit.com", "social")
        _insert_activity(conn, _now_ts(), "netflix.com", 100)
        _insert_activity(conn, _now_ts(), "twitter.com", 500)
        _insert_activity(conn, _now_ts(), "reddit.com", 300)
        out = stats.get_top_distractions(conn)
        assert [r["domain"] for r in out] == ["twitter.com", "reddit.com", "netflix.com"]

    def test_limit_caps_results(self, conn):
        for name in ["a.com", "b.com", "c.com", "d.com"]:
            db.save_seen(conn, name, "social")
            _insert_activity(conn, _now_ts(), name, 100)
        out = stats.get_top_distractions(conn, limit=2)
        assert len(out) == 2

    def test_respects_days_window(self, conn):
        db.save_seen(conn, "netflix.com", "streaming")
        # Outside the 7-day window
        old_ts = time.time() - 30 * 86400
        _insert_activity(conn, old_ts, "netflix.com", 9999)
        # Inside window
        _insert_activity(conn, _now_ts(), "netflix.com", 100)
        out = stats.get_top_distractions(conn, days=7)
        assert len(out) == 1
        assert out[0]["seconds"] == 100

    def test_null_domain_ignored(self, conn):
        conn.execute(
            "INSERT INTO activity_log (ts,domain,duration_s) VALUES (?,?,?)",
            (_now_ts(), None, 300),
        )
        conn.commit()
        assert stats.get_top_distractions(conn) == []


# ---------------------------------------------------------------------------
# get_week_summary / get_month_summary
# ---------------------------------------------------------------------------


class TestRangeSummaries:
    """Tests for stats.get_week_summary and stats.get_month_summary."""

    def test_week_summary_empty(self, conn):
        s = stats.get_week_summary(conn)
        assert s["days"] == 7
        assert s["total"] == 0
        assert s["avg_score"] == 0.0

    def test_month_summary_empty(self, conn):
        s = stats.get_month_summary(conn)
        assert s["days"] == 30
        assert s["total"] == 0.0
        assert s["avg_score"] == 0.0

    def test_week_summary_accumulates(self, conn):
        db.save_seen(conn, "github.com", "work")
        db.save_seen(conn, "netflix.com", "streaming")
        _insert_activity(conn, _now_ts(), "github.com", 300)
        yest = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        _insert_activity(conn, _ts_for(yest), "netflix.com", 100)
        s = stats.get_week_summary(conn)
        assert s["productive"] == 300
        assert s["distracting"] == 100
        assert s["total"] == 400
        # Two days each with its own score: 100 and 0 → avg 50.0
        assert s["avg_score"] == 50.0

    def test_month_summary_avg_ignores_empty_days(self, conn):
        db.save_seen(conn, "github.com", "work")
        _insert_activity(conn, _now_ts(), "github.com", 100)
        s = stats.get_month_summary(conn)
        # Only one day has data → avg_score is that day's score (100.0)
        assert s["avg_score"] == 100.0


# ---------------------------------------------------------------------------
# update_streak / get_streak
# ---------------------------------------------------------------------------


class TestStreaks:
    """Tests for stats.update_streak and stats.get_streak."""

    def test_get_nonexistent_returns_zero(self, conn):
        s = stats.get_streak(conn, "nope")
        assert s == {"goal_name": "nope", "current": 0, "longest": 0, "last_date": None}

    def test_fresh_streak_met(self, conn):
        stats.update_streak(conn, "no-netflix", "2026-04-01", True)
        s = stats.get_streak(conn, "no-netflix")
        assert s["current"] == 1
        assert s["longest"] == 1
        assert s["last_date"] == "2026-04-01"

    def test_fresh_streak_missed(self, conn):
        stats.update_streak(conn, "no-netflix", "2026-04-01", False)
        s = stats.get_streak(conn, "no-netflix")
        assert s["current"] == 0
        assert s["longest"] == 0
        assert s["last_date"] == "2026-04-01"

    def test_streak_increments(self, conn):
        for i, date in enumerate(["2026-04-01", "2026-04-02", "2026-04-03"], 1):
            stats.update_streak(conn, "g", date, True)
        s = stats.get_streak(conn, "g")
        assert s["current"] == 3
        assert s["longest"] == 3

    def test_streak_resets_on_miss(self, conn):
        stats.update_streak(conn, "g", "2026-04-01", True)
        stats.update_streak(conn, "g", "2026-04-02", True)
        stats.update_streak(conn, "g", "2026-04-03", False)
        s = stats.get_streak(conn, "g")
        assert s["current"] == 0
        assert s["longest"] == 2

    def test_longest_preserved_after_reset(self, conn):
        for date in ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"]:
            stats.update_streak(conn, "g", date, True)
        stats.update_streak(conn, "g", "2026-04-05", False)
        stats.update_streak(conn, "g", "2026-04-06", True)
        s = stats.get_streak(conn, "g")
        assert s["current"] == 1
        assert s["longest"] == 4

    def test_multiple_goals_independent(self, conn):
        stats.update_streak(conn, "a", "2026-04-01", True)
        stats.update_streak(conn, "b", "2026-04-01", False)
        sa = stats.get_streak(conn, "a")
        sb = stats.get_streak(conn, "b")
        assert sa["current"] == 1
        assert sb["current"] == 0


# ---------------------------------------------------------------------------
# add_goal / get_goals / delete_goal
# ---------------------------------------------------------------------------


class TestGoalCRUD:
    """Tests for stats.add_goal, get_goals, delete_goal."""

    def test_add_goal_returns_id(self, conn):
        gid = stats.add_goal(conn, "limit streaming", "max_seconds", 1800, "streaming")
        assert isinstance(gid, int)
        assert gid > 0

    def test_get_goals_empty(self, conn):
        assert stats.get_goals(conn) == []

    def test_get_goals_returns_inserted(self, conn):
        stats.add_goal(conn, "g1", "max_seconds", 100, "social")
        stats.add_goal(conn, "g2", "min_seconds", 3600, "productive")
        goals = stats.get_goals(conn)
        assert len(goals) == 2
        assert {g["name"] for g in goals} == {"g1", "g2"}

    def test_add_goal_nullable_category(self, conn):
        gid = stats.add_goal(conn, "any", "max_visits", 50)
        g = [x for x in stats.get_goals(conn) if x["id"] == gid][0]
        assert g["category"] is None

    def test_delete_goal_removes_it(self, conn):
        gid = stats.add_goal(conn, "temp", "zero", 0, "social")
        stats.delete_goal(conn, gid)
        assert stats.get_goals(conn) == []

    def test_delete_nonexistent_goal_noop(self, conn):
        stats.delete_goal(conn, 9999)  # should not raise
        assert stats.get_goals(conn) == []

    def test_get_goals_ordered_by_id(self, conn):
        ids = [stats.add_goal(conn, f"g{i}", "max_seconds", 100) for i in range(3)]
        fetched = [g["id"] for g in stats.get_goals(conn)]
        assert fetched == ids


# ---------------------------------------------------------------------------
# check_goal_progress
# ---------------------------------------------------------------------------


class TestCheckGoalProgress:
    """Tests for stats.check_goal_progress across every target_type."""

    def test_nonexistent_goal_returns_none(self, conn):
        assert stats.check_goal_progress(conn, 9999) is None

    def test_max_seconds_met_when_under(self, conn):
        db.save_seen(conn, "twitter.com", "social")
        _insert_activity(conn, _now_ts(), "twitter.com", 100)
        gid = stats.add_goal(conn, "limit-social", "max_seconds", 500, "social")
        r = stats.check_goal_progress(conn, gid)
        assert r["met"] is True
        assert r["value"] == 100

    def test_max_seconds_exceeded(self, conn):
        db.save_seen(conn, "twitter.com", "social")
        _insert_activity(conn, _now_ts(), "twitter.com", 1000)
        gid = stats.add_goal(conn, "limit-social", "max_seconds", 500, "social")
        r = stats.check_goal_progress(conn, gid)
        assert r["met"] is False
        assert r["value"] == 1000

    def test_max_seconds_with_distracting_category(self, conn):
        db.save_seen(conn, "netflix.com", "streaming")
        _insert_activity(conn, _now_ts(), "netflix.com", 200)
        gid = stats.add_goal(conn, "limit-stream", "max_seconds", 300, "streaming")
        r = stats.check_goal_progress(conn, gid)
        assert r["value"] == 200
        assert r["met"] is True

    def test_min_seconds_met_when_enough(self, conn):
        db.save_seen(conn, "github.com", "work")
        _insert_activity(conn, _now_ts(), "github.com", 7200)
        gid = stats.add_goal(conn, "work-2h", "min_seconds", 3600, "productive")
        r = stats.check_goal_progress(conn, gid)
        assert r["met"] is True
        assert r["value"] == 7200

    def test_min_seconds_not_met(self, conn):
        db.save_seen(conn, "github.com", "work")
        _insert_activity(conn, _now_ts(), "github.com", 100)
        gid = stats.add_goal(conn, "work-1h", "min_seconds", 3600, "productive")
        r = stats.check_goal_progress(conn, gid)
        assert r["met"] is False

    def test_max_visits_with_category(self, conn):
        db.save_seen(conn, "twitter.com", "social")
        for _ in range(3):
            _insert_activity(conn, _now_ts(), "twitter.com", 10)
        gid = stats.add_goal(conn, "few-social", "max_visits", 5, "social")
        r = stats.check_goal_progress(conn, gid)
        assert r["value"] == 3
        assert r["met"] is True

    def test_max_visits_exceeded(self, conn):
        db.save_seen(conn, "twitter.com", "social")
        for _ in range(10):
            _insert_activity(conn, _now_ts(), "twitter.com", 5)
        gid = stats.add_goal(conn, "few-social", "max_visits", 5, "social")
        r = stats.check_goal_progress(conn, gid)
        assert r["value"] == 10
        assert r["met"] is False

    def test_max_visits_no_category_counts_all(self, conn):
        for _ in range(4):
            _insert_activity(conn, _now_ts(), "anysite.com", 10)
        gid = stats.add_goal(conn, "total", "max_visits", 5)
        r = stats.check_goal_progress(conn, gid)
        assert r["value"] == 4
        assert r["met"] is True

    def test_zero_met_when_no_activity(self, conn):
        db.save_seen(conn, "reddit.com", "social")
        gid = stats.add_goal(conn, "no-reddit", "zero", 0, "social")
        r = stats.check_goal_progress(conn, gid)
        assert r["met"] is True
        assert r["value"] == 0

    def test_zero_not_met_when_activity_present(self, conn):
        db.save_seen(conn, "reddit.com", "social")
        _insert_activity(conn, _now_ts(), "reddit.com", 1)
        gid = stats.add_goal(conn, "no-reddit", "zero", 0, "social")
        r = stats.check_goal_progress(conn, gid)
        assert r["met"] is False

    def test_returns_all_fields(self, conn):
        gid = stats.add_goal(conn, "named", "max_seconds", 100, "social")
        r = stats.check_goal_progress(conn, gid)
        assert set(r.keys()) == {"goal_id", "name", "value", "target", "target_type", "met"}
        assert r["goal_id"] == gid
        assert r["name"] == "named"
        assert r["target"] == 100
        assert r["target_type"] == "max_seconds"


# ---------------------------------------------------------------------------
# evaluate_all_goals_today
# ---------------------------------------------------------------------------


class TestEvaluateAllGoalsToday:
    """Tests for stats.evaluate_all_goals_today."""

    def test_empty_goals_returns_empty(self, conn):
        assert stats.evaluate_all_goals_today(conn) == []

    def test_evaluates_each_goal(self, conn):
        db.save_seen(conn, "netflix.com", "streaming")
        _insert_activity(conn, _now_ts(), "netflix.com", 600)
        g1 = stats.add_goal(conn, "limit-stream", "max_seconds", 300, "streaming")
        g2 = stats.add_goal(conn, "no-stream", "zero", 0, "streaming")
        out = stats.evaluate_all_goals_today(conn)
        assert len(out) == 2
        by_id = {r["goal_id"]: r for r in out}
        assert by_id[g1]["met"] is False  # 600 > 300
        assert by_id[g2]["met"] is False  # has activity

    def test_all_met_reported(self, conn):
        stats.add_goal(conn, "easy", "max_seconds", 10_000, "social")
        out = stats.evaluate_all_goals_today(conn)
        assert len(out) == 1
        assert out[0]["met"] is True


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Miscellaneous edge cases."""

    def test_invalid_date_str_raises_value_error(self, conn):
        with pytest.raises(ValueError):
            stats.get_daily_breakdown(conn, "not-a-date")

    def test_calculate_score_with_only_neutral(self, conn):
        # No data (neutral only comes from _categorize returning "neutral"
        # for empty domain). Since _categorize returns "neutral" only on
        # empty domain, insert a row with empty string domain.
        conn.execute(
            "INSERT INTO activity_log (ts,domain,duration_s) VALUES (?,?,?)",
            (_now_ts(), "", 500),
        )
        conn.commit()
        b = stats.get_daily_breakdown(conn)
        assert b["neutral"] == 500
        # productive = 0, total = 500 → score 0.0
        assert stats.calculate_score(conn) == 0.0

    def test_productive_vs_distracted_hours(self, conn):
        db.save_seen(conn, "github.com", "work")
        db.save_seen(conn, "netflix.com", "streaming")
        _insert_activity(conn, _now_ts(), "github.com", 7200)  # 2h
        _insert_activity(conn, _now_ts(), "netflix.com", 1800)  # 0.5h
        r = stats.productive_vs_distracted_hours(conn)
        assert r["productive_hours"] == 2.0
        assert r["distracted_hours"] == 0.5

    def test_check_goal_progress_unknown_target_type(self, conn):
        # Insert a goal with an unknown target_type directly
        conn.execute(
            "INSERT INTO goals (name,target_type,target_value,category,created_at) "
            "VALUES (?,?,?,?,?)",
            ("weird", "frobnicate", 5, None, time.time()),
        )
        conn.commit()
        gid = conn.execute("SELECT id FROM goals WHERE name='weird'").fetchone()["id"]
        r = stats.check_goal_progress(conn, gid)
        assert r["met"] is False
