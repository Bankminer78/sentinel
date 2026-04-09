"""Tests for sentinel.spotify_signal."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import spotify_signal, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_current_track_empty():
    with patch("sentinel.spotify_signal._osascript", return_value=""):
        assert spotify_signal.get_current_track() == {}


def test_get_current_track_playing():
    results = ["Lo-Fi Beats", "Various", "Chillhop", "playing"]
    with patch("sentinel.spotify_signal._osascript", side_effect=results):
        track = spotify_signal.get_current_track()
        assert track["name"] == "Lo-Fi Beats"
        assert track["state"] == "playing"


def test_is_focus_music_lofi():
    track = {"name": "Lo-Fi Beats", "album": "Chillhop"}
    assert spotify_signal.is_focus_music(track) is True


def test_is_focus_music_classical():
    track = {"name": "Piano Sonata", "album": "Classical Collection"}
    assert spotify_signal.is_focus_music(track) is True


def test_is_focus_music_pop():
    track = {"name": "Party Anthem", "album": "Top Hits"}
    assert spotify_signal.is_focus_music(track) is False


def test_is_focus_music_empty():
    assert spotify_signal.is_focus_music({}) is False


def test_is_focus_music_custom_keywords():
    track = {"name": "Rain Sounds", "album": ""}
    assert spotify_signal.is_focus_music(track, ["rain"]) is True


def test_pause_spotify():
    with patch("sentinel.spotify_signal._osascript", return_value=""):
        assert spotify_signal.pause_spotify() is True


def test_play_spotify():
    with patch("sentinel.spotify_signal._osascript", return_value=""):
        assert spotify_signal.play_spotify() is True


@pytest.mark.asyncio
async def test_log_activity_with_track(conn):
    results = ["Lofi Study Beats", "Artist", "Album", "playing"]
    with patch("sentinel.spotify_signal._osascript", side_effect=results):
        result = await spotify_signal.log_spotify_activity(conn)
        assert result["is_focus"] is True


@pytest.mark.asyncio
async def test_log_activity_no_track(conn):
    with patch("sentinel.spotify_signal._osascript", return_value=""):
        result = await spotify_signal.log_spotify_activity(conn)
        assert result == {}


def test_is_focus_music_instrumental():
    track = {"name": "Instrumental Piece", "album": "Soundtrack"}
    assert spotify_signal.is_focus_music(track) is True
