"""Tests for sentinel.ambient."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import ambient


@pytest.fixture(autouse=True)
def reset_state():
    ambient._current_sound = None
    ambient._start_time = None
    yield


def test_list_sounds():
    sounds = ambient.list_sounds()
    assert len(sounds) > 0
    assert all("id" in s and "name" in s for s in sounds)


def test_list_by_type_nature():
    nature = ambient.list_by_type("nature")
    assert len(nature) > 0
    assert all(s["type"] == "nature" for s in nature)


def test_list_by_type_noise():
    noise = ambient.list_by_type("noise")
    assert any(s["id"] == "brown_noise" for s in noise)


def test_play_sound():
    with patch("sentinel.ambient.subprocess.run", return_value=MagicMock(returncode=0)):
        assert ambient.play_sound("rain") is True
        assert ambient.is_playing() is True


def test_play_invalid():
    assert ambient.play_sound("nonexistent") is False


def test_stop_sound():
    with patch("sentinel.ambient.subprocess.run", return_value=MagicMock(returncode=0)):
        ambient.play_sound("rain")
    ambient.stop_sound()
    assert ambient.is_playing() is False


def test_current_playing():
    with patch("sentinel.ambient.subprocess.run", return_value=MagicMock(returncode=0)):
        ambient.play_sound("lofi")
    current = ambient.current()
    assert current["sound_id"] == "lofi"


def test_current_not_playing():
    assert ambient.current() == {}


def test_is_playing_false_initially():
    assert ambient.is_playing() is False


def test_recommend_coding():
    assert ambient.recommend_for_task("coding") == "lofi"


def test_recommend_unknown():
    assert ambient.recommend_for_task("unknown") == "lofi"  # Default


def test_recommend_writing():
    assert ambient.recommend_for_task("writing") == "classical"
