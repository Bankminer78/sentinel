"""Tests for sentinel.subscription_tracker."""
import pytest
from sentinel import subscription_tracker as st, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_subscription(conn):
    sid = st.add_subscription(conn, "Netflix", 15.99, "monthly")
    assert sid > 0


def test_get_subscriptions(conn):
    st.add_subscription(conn, "Netflix", 15.99)
    st.add_subscription(conn, "Spotify", 9.99)
    assert len(st.get_subscriptions(conn)) == 2


def test_cancel_subscription(conn):
    sid = st.add_subscription(conn, "Test", 10)
    st.cancel_subscription(conn, sid)
    assert len(st.get_subscriptions(conn, active_only=True)) == 0
    assert len(st.get_subscriptions(conn, active_only=False)) == 1


def test_delete_subscription(conn):
    sid = st.add_subscription(conn, "Test", 10)
    st.delete_subscription(conn, sid)
    assert st.get_subscriptions(conn, active_only=False) == []


def test_monthly_total(conn):
    st.add_subscription(conn, "Netflix", 15, "monthly")
    st.add_subscription(conn, "Amazon", 120, "yearly")
    total = st.monthly_total(conn)
    assert total == round(15 + 10, 2)  # 15 + 120/12


def test_yearly_total(conn):
    st.add_subscription(conn, "Netflix", 15, "monthly")
    yearly = st.yearly_total(conn)
    assert yearly == 180


def test_renewing_soon_empty(conn):
    assert st.renewing_soon(conn) == []


def test_mark_used(conn):
    sid = st.add_subscription(conn, "Test", 10)
    st.mark_used(conn, sid)
    subs = st.get_subscriptions(conn)
    assert subs[0]["last_used"]


def test_unused_subscriptions(conn):
    st.add_subscription(conn, "Test", 10)
    unused = st.unused_subscriptions(conn)
    assert len(unused) == 1


def test_by_category(conn):
    st.add_subscription(conn, "Netflix", 15, category="entertainment")
    st.add_subscription(conn, "Hulu", 10, category="entertainment")
    by_cat = st.by_category(conn)
    assert "entertainment" in by_cat
    assert by_cat["entertainment"]["count"] == 2
