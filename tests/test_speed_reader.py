"""Tests for sentinel.speed_reader."""
import pytest
from sentinel import speed_reader as sr, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_log_session(conn):
    sid = sr.log_session(conn, 400, 800, 120.0, 85)
    assert sid > 0


def test_get_sessions(conn):
    sr.log_session(conn, 300, 600, 120)
    sr.log_session(conn, 400, 800, 120)
    assert len(sr.get_sessions(conn)) == 2


def test_best_wpm_empty(conn):
    assert sr.best_wpm(conn) == 0


def test_best_wpm(conn):
    sr.log_session(conn, 300, 600, 120)
    sr.log_session(conn, 500, 1000, 120)
    assert sr.best_wpm(conn) == 500


def test_avg_wpm_empty(conn):
    assert sr.avg_wpm(conn) == 0


def test_avg_wpm(conn):
    sr.log_session(conn, 300, 600, 120)
    sr.log_session(conn, 400, 800, 120)
    assert sr.avg_wpm(conn) == 350.0


def test_total_words_read(conn):
    sr.log_session(conn, 300, 600, 120)
    sr.log_session(conn, 400, 800, 120)
    assert sr.total_words_read(conn) == 1400


def test_avg_comprehension(conn):
    sr.log_session(conn, 300, 600, 120, comprehension=80)
    sr.log_session(conn, 400, 800, 120, comprehension=90)
    assert sr.avg_comprehension(conn) == 85.0


def test_get_recommended_wpm_empty(conn):
    assert sr.get_recommended_wpm(conn) == 250


def test_get_recommended_wpm(conn):
    sr.log_session(conn, 300, 600, 120)
    assert sr.get_recommended_wpm(conn) == 325


def test_rsvp_split():
    result = sr.rsvp_split("one two three four", chunk_size=1)
    assert len(result) == 4


def test_rsvp_split_chunks():
    result = sr.rsvp_split("one two three four", chunk_size=2)
    assert len(result) == 2


def test_delay_for_wpm():
    assert sr.delay_for_wpm(300) == 0.2  # 60/300 = 0.2s


def test_estimate_finish_time():
    # 300 words at 300 WPM = 60 seconds
    assert sr.estimate_finish_time(300, 300) == 60.0


def test_delete_session(conn):
    sid = sr.log_session(conn, 300, 600, 120)
    sr.delete_session(conn, sid)
    assert sr.total_sessions(conn) == 0


def test_total_sessions(conn):
    sr.log_session(conn, 300, 600, 120)
    sr.log_session(conn, 400, 800, 120)
    assert sr.total_sessions(conn) == 2
