"""Simple forecasting based on historical patterns."""
import datetime as _dt
from . import stats


_DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday",
              "friday", "saturday", "sunday"]


def _daily_scores(conn, days: int) -> list:
    today = _dt.date.today()
    out = []
    for i in range(days):
        d = (today - _dt.timedelta(days=i)).strftime("%Y-%m-%d")
        b = stats.get_daily_breakdown(conn, d)
        if b["total"] > 0:
            sc = 100.0 * b["productive"] / b["total"]
            out.append((d, sc))
    return out


def weekday_averages(conn) -> dict:
    scores = _daily_scores(conn, 60)
    buckets = {n: [] for n in _DAY_NAMES}
    for ds, sc in scores:
        wd = _dt.date.fromisoformat(ds).weekday()
        buckets[_DAY_NAMES[wd]].append(sc)
    return {n: round(sum(v) / len(v), 2) if v else 0.0 for n, v in buckets.items()}


def _predict_for_weekday(conn, target_date: _dt.date) -> dict:
    avgs = weekday_averages(conn)
    name = _DAY_NAMES[target_date.weekday()]
    val = avgs.get(name, 0.0)
    scores = _daily_scores(conn, 14)
    confidence = min(1.0, len(scores) / 14.0)
    return {
        "predicted_score": round(val, 2),
        "confidence": round(confidence, 2),
        "based_on_days": len(scores),
        "date": target_date.strftime("%Y-%m-%d"),
        "weekday": name,
    }


def forecast_today(conn) -> dict:
    return _predict_for_weekday(conn, _dt.date.today())


def forecast_tomorrow(conn) -> dict:
    return _predict_for_weekday(conn, _dt.date.today() + _dt.timedelta(days=1))


def weekly_forecast(conn) -> list:
    today = _dt.date.today()
    return [_predict_for_weekday(conn, today + _dt.timedelta(days=i)) for i in range(7)]


def trend_direction(conn, days: int = 14) -> str:
    scores = _daily_scores(conn, days)
    if len(scores) < 4:
        return "stable"
    # scores is newest-first; split into recent half vs older half
    half = len(scores) // 2
    recent = [s for _, s in scores[:half]]
    older = [s for _, s in scores[half:]]
    if not recent or not older:
        return "stable"
    r = sum(recent) / len(recent)
    o = sum(older) / len(older)
    diff = r - o
    if diff > 3:
        return "improving"
    if diff < -3:
        return "declining"
    return "stable"
