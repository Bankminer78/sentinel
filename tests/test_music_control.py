"""Tests for sentinel.music_control."""
import pytest
from unittest.mock import patch
from sentinel import music_control, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_current_player_none():
    with patch("sentinel.music_control._osascript", return_value=""):
        assert music_control.get_current_player() is None


def test_get_current_player_playing():
    # First app (Spotify) is playing
    def mock_osa(cmd):
        if "Spotify" in cmd and "player state" in cmd:
            return "playing"
        return ""
    with patch("sentinel.music_control._osascript", side_effect=mock_osa):
        assert music_control.get_current_player() == "Spotify"


def test_play():
    with patch("sentinel.music_control._osascript", return_value=""):
        assert music_control.play() is True


def test_pause():
    with patch("sentinel.music_control._osascript", return_value=""):
        assert music_control.pause() is True


def test_next_track():
    with patch("sentinel.music_control._osascript", return_value=""):
        assert music_control.next_track() is True


def test_previous_track():
    with patch("sentinel.music_control._osascript", return_value=""):
        assert music_control.previous_track() is True


def test_get_now_playing_empty():
    with patch("sentinel.music_control._osascript", return_value=""):
        assert music_control.get_now_playing() == {}


def test_get_now_playing_with_track():
    results = iter(["Track Name", "Artist Name"])
    with patch("sentinel.music_control._osascript", side_effect=lambda cmd: next(results)):
        track = music_control.get_now_playing()
        assert track["name"] == "Track Name"
        assert track["artist"] == "Artist Name"


def test_set_volume_clamped_low():
    with patch("sentinel.music_control._osascript", return_value="") as mock:
        music_control.set_volume("Spotify", -10)
        # Should clamp to 0
        assert "0" in mock.call_args[0][0]


def test_set_volume_clamped_high():
    with patch("sentinel.music_control._osascript", return_value="") as mock:
        music_control.set_volume("Spotify", 150)
        # Should clamp to 100
        assert "100" in mock.call_args[0][0]


def test_set_volume_normal():
    with patch("sentinel.music_control._osascript", return_value="") as mock:
        music_control.set_volume("Spotify", 50)
        assert "50" in mock.call_args[0][0]


def test_focus_music_mode(conn):
    def mock_osa(cmd):
        if "Spotify" in cmd and "player state" in cmd:
            return "playing"
        return ""
    with patch("sentinel.music_control._osascript", side_effect=mock_osa):
        result = music_control.focus_music_mode(conn)
        assert "Spotify" in result["paused"]


def test_rest_music_mode(conn):
    def mock_osa(cmd):
        if "Spotify" in cmd and "player state" in cmd:
            return "paused"
        return ""
    with patch("sentinel.music_control._osascript", side_effect=mock_osa):
        result = music_control.rest_music_mode(conn)
        assert "Spotify" in result["resumed"]


def test_focus_mode_nothing_playing(conn):
    with patch("sentinel.music_control._osascript", return_value="stopped"):
        result = music_control.focus_music_mode(conn)
        assert result["paused"] == []
