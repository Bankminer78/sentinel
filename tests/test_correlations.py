"""Tests for sentinel.correlations."""
import time
import datetime as _dt
from sentinel import correlations, habits, journal


def _log(conn, ts, domain, verdict, duration=60):
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, "app", "t", f"https://{domain}", domain, verdict, duration))
    conn.commit()


def _seed_productive_day(conn, date: _dt.date, productive=True):
    ts = _dt.datetime.combine(date, _dt.time(10, 0)).timestamp()
    if productive:
        _log(conn, ts, "work.com", "allow", duration=1800)
    else:
        conn.execute(
            "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
            ("yt.com", "social", time.time()))
        conn.commit()
        _log(conn, ts, "yt.com", "block", duration=1800)


def test_pearson_empty():
    assert correlations._pearson([], []) == 0.0


def test_pearson_perfect_correlation():
    r = correlations._pearson([1, 2, 3, 4], [1, 2, 3, 4])
    assert r == 1.0


def test_pearson_negative():
    r = correlations._pearson([1, 2, 3, 4], [4, 3, 2, 1])
    assert r == -1.0


def test_pearson_zero_variance():
    r = correlations._pearson([1, 1, 1], [2, 3, 4])
    assert r == 0.0


def test_correlate_sleep_productivity_empty(conn):
    assert correlations.correlate_sleep_productivity(conn) == 0.0


def test_correlate_sleep_productivity_some(conn):
    today = _dt.date.today()
    for i in range(5):
        d = today - _dt.timedelta(days=i)
        _seed_productive_day(conn, d, productive=True)
        # insert a journal row with mood for the date
        conn.execute(
            "CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY, date TEXT, "
            "content TEXT, mood INTEGER, tags TEXT, created_at REAL)")
        conn.execute(
            "INSERT INTO journal (date, content, mood, tags, created_at) VALUES (?, ?, ?, ?, ?)",
            (d.strftime("%Y-%m-%d"), "x", 5, "[]", time.time()))
        conn.commit()
    r = correlations.correlate_sleep_productivity(conn)
    assert isinstance(r, float)


def test_correlate_habit_productivity_empty(conn):
    hid = habits.add_habit(conn, "read")
    r = correlations.correlate_habit_productivity(conn, hid)
    assert r == 0.0


def test_correlate_habit_productivity_with_data(conn):
    hid = habits.add_habit(conn, "read")
    today = _dt.date.today()
    for i in range(5):
        d = today - _dt.timedelta(days=i)
        _seed_productive_day(conn, d, productive=(i % 2 == 0))
        if i % 2 == 0:
            habits.log_habit(conn, hid, d.isoformat())
    r = correlations.correlate_habit_productivity(conn, hid)
    assert isinstance(r, float)


def test_correlate_time_of_day_empty(conn):
    assert correlations.correlate_time_of_day_productivity(conn) == {}


def test_correlate_time_of_day_populated(conn):
    base = _dt.datetime(2024, 1, 1, 10, 0, 0).timestamp()
    _log(conn, base, "work.com", "allow")
    _log(conn, base + 10, "yt.com", "block")
    r = correlations.correlate_time_of_day_productivity(conn)
    assert 10 in r
    assert r[10] == 0.5


def test_correlate_domain_pairs_empty(conn):
    assert correlations.correlate_domain_pairs(conn) == []


def test_correlate_domain_pairs_basic(conn):
    now = time.time()
    _log(conn, now, "a.com", "allow")
    _log(conn, now + 10, "b.com", "allow")
    _log(conn, now + 20, "a.com", "allow")
    _log(conn, now + 30, "b.com", "allow")
    pairs = correlations.correlate_domain_pairs(conn)
    assert len(pairs) >= 1


def test_best_correlate_no_habits(conn):
    r = correlations.best_correlate_with_score(conn)
    assert "name" in r
    assert "correlation" in r


def test_best_correlate_with_habit(conn):
    habits.add_habit(conn, "h1")
    r = correlations.best_correlate_with_score(conn)
    assert r["name"] is not None


def test_time_of_day_only_productive(conn):
    base = _dt.datetime(2024, 1, 1, 9, 0, 0).timestamp()
    _log(conn, base, "work.com", "allow")
    r = correlations.correlate_time_of_day_productivity(conn)
    assert r[9] == 1.0
