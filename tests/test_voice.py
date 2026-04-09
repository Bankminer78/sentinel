"""Tests for sentinel.voice."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import voice


def test_voices_constant():
    assert "Samantha" in voice.VOICES
    assert len(voice.VOICES) >= 6


def test_speak_success():
    with patch("sentinel.voice.subprocess.run") as mock:
        assert voice.speak("hi") is True
        args = mock.call_args[0][0]
        assert args[0] == "say"
        assert "Samantha" in args
        assert "hi" in args


def test_speak_custom_voice_rate():
    with patch("sentinel.voice.subprocess.run") as mock:
        voice.speak("hello", voice="Alex", rate=150)
        args = mock.call_args[0][0]
        assert "Alex" in args
        assert "150" in args


def test_speak_empty_text():
    with patch("sentinel.voice.subprocess.run") as mock:
        assert voice.speak("") is False
        mock.assert_not_called()


def test_speak_exception():
    with patch("sentinel.voice.subprocess.run", side_effect=Exception("boom")):
        assert voice.speak("hi") is False


def test_speak_async():
    with patch("sentinel.voice.subprocess.Popen") as mock:
        voice.speak_async("hi")
        mock.assert_called_once()


def test_speak_async_empty():
    with patch("sentinel.voice.subprocess.Popen") as mock:
        voice.speak_async("")
        mock.assert_not_called()


def test_speak_async_exception():
    with patch("sentinel.voice.subprocess.Popen", side_effect=Exception("x")):
        voice.speak_async("hi")  # Should not raise


def test_list_voices_parses_output():
    fake = MagicMock()
    fake.stdout = "Samantha en_US # hi\nAlex en_US # hello\n"
    with patch("sentinel.voice.subprocess.run", return_value=fake):
        v = voice.list_voices()
        assert "Samantha" in v
        assert "Alex" in v


def test_list_voices_fallback():
    with patch("sentinel.voice.subprocess.run", side_effect=Exception("x")):
        v = voice.list_voices()
        assert "Samantha" in v


def test_set_and_get_default_voice(conn):
    assert voice.get_default_voice(conn) == "Samantha"
    voice.set_default_voice(conn, "Alex")
    assert voice.get_default_voice(conn) == "Alex"


def test_speak_notification_uses_default(conn):
    voice.set_default_voice(conn, "Victoria")
    with patch("sentinel.voice.speak", return_value=True) as mock:
        voice.speak_notification(conn, "Title", "Message")
        assert mock.call_args[1]["voice"] == "Victoria"
        assert "Title" in mock.call_args[0][0]


def test_speak_notification_explicit_voice(conn):
    with patch("sentinel.voice.speak", return_value=True) as mock:
        voice.speak_notification(conn, "T", "M", voice="Karen")
        assert mock.call_args[1]["voice"] == "Karen"


def test_speak_notification_no_title(conn):
    with patch("sentinel.voice.speak", return_value=True) as mock:
        voice.speak_notification(conn, "", "msg")
        assert mock.call_args[0][0] == "msg"
