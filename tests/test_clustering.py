"""Tests for sentinel.clustering."""
import pytest
import time
from sentinel import clustering, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_k_means_empty():
    assert clustering.k_means_1d([]) == []


def test_k_means_basic():
    values = [1, 2, 3, 10, 11, 12, 20, 21, 22]
    clusters = clustering.k_means_1d(values, k=3)
    assert len(clusters) == 3


def test_k_means_single_cluster():
    clusters = clustering.k_means_1d([1, 2, 3, 4, 5], k=1)
    assert len(clusters) == 1
    assert len(clusters[0]) == 5


def test_cluster_by_hour_empty(conn):
    assert clustering.cluster_by_hour(conn) == {}


def test_cluster_by_hour(conn):
    db.log_activity(conn, "App", "", "", "test.com")
    result = clustering.cluster_by_hour(conn)
    assert len(result) >= 1


def test_cluster_by_domain_empty(conn):
    assert clustering.cluster_by_domain(conn) == []


def test_cluster_by_domain(conn):
    db.log_activity(conn, "", "", "", "a.com")
    db.log_activity(conn, "", "", "", "a.com")
    db.log_activity(conn, "", "", "", "b.com")
    result = clustering.cluster_by_domain(conn)
    assert result[0]["domain"] == "a.com"


def test_identify_peak_times_empty(conn):
    assert clustering.identify_peak_times(conn) == []


def test_identify_peak_times(conn):
    for _ in range(5):
        db.log_activity(conn, "", "", "", "test.com")
    peaks = clustering.identify_peak_times(conn)
    assert len(peaks) >= 1


def test_group_by_session_empty(conn):
    assert clustering.group_activities_by_session(conn) == []


def test_group_by_session(conn):
    db.log_activity(conn, "App", "", "", "test.com")
    db.log_activity(conn, "App", "", "", "test.com")
    sessions = clustering.group_activities_by_session(conn)
    assert len(sessions) >= 1


def test_session_stats_empty():
    stats = clustering.session_stats([])
    assert stats["count"] == 0


def test_session_stats():
    sessions = [[{"ts": 1}, {"ts": 2}], [{"ts": 3}]]
    stats = clustering.session_stats(sessions)
    assert stats["count"] == 2
    assert stats["total_activities"] == 3


def test_find_patterns(conn):
    patterns = clustering.find_patterns(conn)
    assert "by_hour" in patterns
    assert "top_domains" in patterns
    assert "peak_hours" in patterns
