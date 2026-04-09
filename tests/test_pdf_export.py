"""Tests for sentinel.pdf_export."""
import pytest
from sentinel import pdf_export, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_generate_text(conn):
    text = pdf_export.generate_report_text(conn)
    assert "Sentinel Report" in text
    assert "score" in text.lower()


def test_generate_html(conn):
    html = pdf_export.generate_report_html(conn)
    assert "<!DOCTYPE html>" in html
    assert "Sentinel Report" in html
    assert "</html>" in html


def test_generate_html_with_data(conn):
    db.save_seen(conn, "youtube.com", "streaming")
    import time
    conn.execute(
        "INSERT INTO activity_log (ts, domain, duration_s, verdict) VALUES (?, 'youtube.com', 3600, 'block')",
        (time.time(),))
    conn.commit()
    html = pdf_export.generate_report_html(conn)
    assert "youtube.com" in html


def test_generate_weekly(conn):
    text = pdf_export.generate_weekly_report(conn)
    assert "Weekly" in text or "weekly" in text.lower()


def test_generate_monthly(conn):
    text = pdf_export.generate_monthly_report(conn)
    assert "Monthly" in text or "monthly" in text.lower()


def test_save_report_html(conn, tmp_path):
    path = str(tmp_path / "report.html")
    result = pdf_export.save_report(conn, path, "html")
    assert result == path
    assert Path(path).exists()
    content = Path(path).read_text()
    assert "<html>" in content or "<!DOCTYPE html>" in content


def test_save_report_text(conn, tmp_path):
    path = str(tmp_path / "report.txt")
    pdf_export.save_report(conn, path, "text")
    assert Path(path).exists()


def test_html_has_css(conn):
    html = pdf_export.generate_report_html(conn)
    assert "<style>" in html


def test_text_has_date(conn):
    text = pdf_export.generate_report_text(conn)
    from datetime import datetime
    assert datetime.now().strftime("%Y-%m-%d") in text


def test_html_has_stats(conn):
    html = pdf_export.generate_report_html(conn)
    assert "stat" in html.lower()
