"""Tests for sentinel.limits."""
import time
from sentinel import limits


def test_set_limit(conn):
    lid = limits.set_limit(conn, "social", "daily", 3600)
    assert lid > 0


def test_get_limits(conn):
    limits.set_limit(conn, "social", "daily", 3600)
    limits.set_limit(conn, "gaming", "weekly", 7200)
    assert len(limits.get_limits(conn)) == 2


def test_get_limits_empty(conn):
    assert limits.get_limits(conn) == []


def test_delete_limit(conn):
    lid = limits.set_limit(conn, "social", "daily", 3600)
    limits.delete_limit(conn, lid)
    assert limits.get_limits(conn) == []


def test_check_limit_no_limit(conn):
    r = limits.check_limit(conn, "social")
    assert r["limit"] == 0
    assert r["exceeded"] is False


def test_check_limit_not_exceeded(conn):
    limits.set_limit(conn, "social", "daily", 3600)
    r = limits.check_limit(conn, "social")
    assert r["limit"] == 3600
    assert r["exceeded"] is False
    assert r["remaining"] == 3600


def test_check_limit_with_usage(conn):
    limits.set_limit(conn, "social", "daily", 3600)
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (time.time(), "browser", "fb", "https://fb.com", "fb.com", "allow", 1000))
    conn.execute(
        "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
        ("fb.com", "social", time.time()))
    conn.commit()
    r = limits.check_limit(conn, "social")
    assert r["used"] == 1000
    assert r["remaining"] == 2600
    assert r["exceeded"] is False


def test_check_limit_exceeded(conn):
    limits.set_limit(conn, "social", "daily", 500)
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (time.time(), "browser", "fb", "https://fb.com", "fb.com", "allow", 1000))
    conn.execute(
        "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
        ("fb.com", "social", time.time()))
    conn.commit()
    r = limits.check_limit(conn, "social")
    assert r["exceeded"] is True
    assert r["remaining"] == 0


def test_get_all_limit_status(conn):
    limits.set_limit(conn, "social", "daily", 3600)
    limits.set_limit(conn, "gaming", "weekly", 7200)
    statuses = limits.get_all_limit_status(conn)
    assert len(statuses) == 2
    cats = {s["category"] for s in statuses}
    assert cats == {"social", "gaming"}


def test_get_all_limit_status_empty(conn):
    assert limits.get_all_limit_status(conn) == []


def test_weekly_period(conn):
    limits.set_limit(conn, "gaming", "weekly", 7200)
    r = limits.check_limit(conn, "gaming")
    assert r["limit"] == 7200


def test_old_activity_not_counted(conn):
    limits.set_limit(conn, "social", "daily", 3600)
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (time.time() - 86400 * 2, "browser", "fb", "https://fb.com", "fb.com", "allow", 1000))
    conn.execute(
        "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
        ("fb.com", "social", time.time()))
    conn.commit()
    r = limits.check_limit(conn, "social")
    assert r["used"] == 0


def test_multiple_limits_sum_usage(conn):
    limits.set_limit(conn, "social", "daily", 3600)
    now = time.time()
    for dur in (100, 200, 300):
        conn.execute(
            "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (now, "b", "t", "u", "fb.com", "allow", dur))
    conn.execute(
        "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
        ("fb.com", "social", now))
    conn.commit()
    r = limits.check_limit(conn, "social")
    assert r["used"] == 600
