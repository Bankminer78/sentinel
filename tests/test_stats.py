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
        s = stats.range_summary(conn, 7)
        assert s["days"] == 7
        assert s["total"] == 0
        assert s["avg_score"] == 0.0

    def test_month_summary_empty(self, conn):
        s = stats.range_summary(conn, 30)
        assert s["days"] == 30
        assert s["total"] == 0.0
        assert s["avg_score"] == 0.0

    def test_week_summary_accumulates(self, conn):
        db.save_seen(conn, "github.com", "work")
        db.save_seen(conn, "netflix.com", "streaming")
        _insert_activity(conn, _now_ts(), "github.com", 300)
        yest = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        _insert_activity(conn, _ts_for(yest), "netflix.com", 100)
        s = stats.range_summary(conn, 7)
        assert s["productive"] == 300
        assert s["distracting"] == 100
        assert s["total"] == 400
        # Two days each with its own score: 100 and 0 → avg 50.0
        assert s["avg_score"] == 50.0

    def test_month_summary_avg_ignores_empty_days(self, conn):
        db.save_seen(conn, "github.com", "work")
        _insert_activity(conn, _now_ts(), "github.com", 100)
        s = stats.range_summary(conn, 30)
        # Only one day has data → avg_score is that day's score (100.0)
        assert s["avg_score"] == 100.0
