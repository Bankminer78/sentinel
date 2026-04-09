"""Tests for sentinel.accessibility_helper."""
import pytest
from sentinel import accessibility_helper as ah


def test_aria_label():
    result = ah.aria_label("Button")
    assert 'aria-label="Button"' in result


def test_aria_label_with_role():
    result = ah.aria_label("Button", "button")
    assert 'role="button"' in result


def test_sr_only():
    result = ah.sr_only("Hidden text")
    assert "sr-only" in result


def test_keyboard_hint():
    assert ah.keyboard_hint("Cmd+S", "Save") == "[Cmd+S] Save"


def test_alt_text_excellent():
    result = ah.alt_text_for_score(95)
    assert "Excellent" in result


def test_alt_text_good():
    result = ah.alt_text_for_score(75)
    assert "Good" in result


def test_alt_text_low():
    result = ah.alt_text_for_score(20)
    assert "Low" in result


def test_describe_trend():
    assert "improving" in ah.describe_trend("improving")
    assert "stable" in ah.describe_trend("stable")


def test_describe_streak_zero():
    assert "No current streak" in ah.describe_streak(0)


def test_describe_streak_one():
    assert "One day" in ah.describe_streak(1)


def test_describe_streak_many():
    assert "5 day" in ah.describe_streak(5)


def test_describe_percentage():
    assert "50 percent" in ah.describe_percentage(50)


def test_describe_time_saved():
    assert "Less than" in ah.describe_time_saved(0.5)
    assert "minutes" in ah.describe_time_saved(30)
    assert "hours" in ah.describe_time_saved(90)


def test_get_sr_css():
    css = ah.get_sr_css()
    assert ".sr-only" in css


def test_skip_to_content_link():
    link = ah.get_skip_to_content_link()
    assert "skip" in link.lower()


def test_landmark():
    result = ah.landmark("main", "Content", "<p>hello</p>")
    assert 'role="main"' in result


def test_announce_to_sr():
    result = ah.announce_to_sr("Update", "polite")
    assert 'aria-live="polite"' in result


def test_high_contrast_check():
    assert ah.high_contrast_check("#000", "#fff") is True
    assert ah.high_contrast_check("#000", "#000") is False
