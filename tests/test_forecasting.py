"""Tests for sentinel.forecasting."""
import time
import datetime as _dt
from sentinel import forecasting


def _log(conn, ts, domain, duration=60, verdict="allow"):
    conn.execute(
        "INSERT INTO activity_log (ts, app, title, url, domain, verdict, duration_s) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, "app", "t", f"https://{domain}", domain, verdict, duration))
    conn.commit()


def _seed_day(conn, date: _dt.date, productive_s=1800, distracting_s=0):
    ts = _dt.datetime.combine(date, _dt.time(10, 0)).timestamp()
    if productive_s:
        _log(conn, ts, "work.com", duration=productive_s)
    if distracting_s:
        conn.execute(
            "INSERT OR REPLACE INTO seen_domains (domain, category, first_seen) VALUES (?, ?, ?)",
            ("yt.com", "social", time.time()))
        conn.commit()
        _log(conn, ts + 1, "yt.com", duration=distracting_s, verdict="block")


def test_forecast_today_empty(conn):
    r = forecasting.forecast_today(conn)
    assert r["predicted_score"] == 0.0
    assert r["confidence"] == 0.0
    assert r["based_on_days"] == 0


def test_forecast_today_has_keys(conn):
    r = forecasting.forecast_today(conn)
    for k in ("predicted_score", "confidence", "based_on_days", "date", "weekday"):
        assert k in r


def test_forecast_tomorrow_empty(conn):
    r = forecasting.forecast_tomorrow(conn)
    assert r["predicted_score"] == 0.0


def test_forecast_tomorrow_date(conn):
    tomorrow = (_dt.date.today() + _dt.timedelta(days=1)).strftime("%Y-%m-%d")
    r = forecasting.forecast_tomorrow(conn)
    assert r["date"] == tomorrow


def test_weekly_forecast_length(conn):
    r = forecasting.weekly_forecast(conn)
    assert len(r) == 7


def test_weekly_forecast_sequential(conn):
    r = forecasting.weekly_forecast(conn)
    dates = [x["date"] for x in r]
    assert dates[0] == _dt.date.today().strftime("%Y-%m-%d")


def test_weekday_averages_empty(conn):
    r = forecasting.weekday_averages(conn)
    assert set(r.keys()) == {"monday", "tuesday", "wednesday", "thursday",
                             "friday", "saturday", "sunday"}
    assert all(v == 0.0 for v in r.values())


def test_weekday_averages_with_data(conn):
    today = _dt.date.today()
    _seed_day(conn, today)
    r = forecasting.weekday_averages(conn)
    name = ["monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"][today.weekday()]
    assert r[name] > 0


def test_trend_stable_insufficient(conn):
    assert forecasting.trend_direction(conn) == "stable"


def test_trend_improving(conn):
    today = _dt.date.today()
    # Older days: mostly distracting (low score)
    for i in range(7, 14):
        d = today - _dt.timedelta(days=i)
        _seed_day(conn, d, productive_s=100, distracting_s=900)
    # Recent days: mostly productive
    for i in range(0, 7):
        d = today - _dt.timedelta(days=i)
        _seed_day(conn, d, productive_s=900, distracting_s=100)
    assert forecasting.trend_direction(conn) == "improving"


def test_trend_declining(conn):
    today = _dt.date.today()
    for i in range(7, 14):
        d = today - _dt.timedelta(days=i)
        _seed_day(conn, d, productive_s=900, distracting_s=100)
    for i in range(0, 7):
        d = today - _dt.timedelta(days=i)
        _seed_day(conn, d, productive_s=100, distracting_s=900)
    assert forecasting.trend_direction(conn) == "declining"


def test_forecast_confidence_with_data(conn):
    today = _dt.date.today()
    for i in range(0, 14):
        d = today - _dt.timedelta(days=i)
        _seed_day(conn, d)
    r = forecasting.forecast_today(conn)
    assert r["confidence"] == 1.0
    assert r["based_on_days"] == 14


def test_predicted_score_reflects_history(conn):
    today = _dt.date.today()
    _seed_day(conn, today - _dt.timedelta(days=7))
    r = forecasting.forecast_today(conn)
    assert r["predicted_score"] > 0


def test_weekly_forecast_all_weekdays(conn):
    r = forecasting.weekly_forecast(conn)
    weekdays = {x["weekday"] for x in r}
    assert len(weekdays) == 7
