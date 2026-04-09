"""Tests for sentinel.wifi."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import wifi, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_current_ssid():
    mock_output = "Current Wi-Fi Network: MyNetwork"
    with patch("sentinel.wifi.subprocess.run",
               return_value=MagicMock(returncode=0, stdout=mock_output)):
        assert wifi.get_current_ssid() == "MyNetwork"


def test_get_current_ssid_error():
    with patch("sentinel.wifi.subprocess.run", side_effect=Exception("fail")):
        assert wifi.get_current_ssid() == ""


def test_get_signal_strength():
    mock_output = " agrCtlRSSI: -55 "
    with patch("sentinel.wifi.subprocess.run",
               return_value=MagicMock(returncode=0, stdout=mock_output)):
        assert wifi.get_signal_strength() == -55


def test_is_wifi_connected():
    with patch("sentinel.wifi.get_current_ssid", return_value="Network"):
        assert wifi.is_wifi_connected() is True


def test_is_wifi_not_connected():
    with patch("sentinel.wifi.get_current_ssid", return_value=""):
        assert wifi.is_wifi_connected() is False


def test_log_wifi(conn):
    with patch("sentinel.wifi.get_current_ssid", return_value="Test"):
        with patch("sentinel.wifi.get_signal_strength", return_value=-60):
            wifi.log_wifi(conn)
    history = wifi.get_wifi_history(conn)
    assert len(history) == 1


def test_wifi_history_empty(conn):
    assert wifi.get_wifi_history(conn) == []


def test_most_common_networks(conn):
    with patch("sentinel.wifi.get_current_ssid", return_value="HomeWiFi"):
        with patch("sentinel.wifi.get_signal_strength", return_value=-50):
            wifi.log_wifi(conn)
            wifi.log_wifi(conn)
    with patch("sentinel.wifi.get_current_ssid", return_value="WorkWiFi"):
        with patch("sentinel.wifi.get_signal_strength", return_value=-50):
            wifi.log_wifi(conn)
    common = wifi.most_common_networks(conn)
    assert common[0]["ssid"] == "HomeWiFi"


def test_time_on_network(conn):
    with patch("sentinel.wifi.get_current_ssid", return_value="X"):
        with patch("sentinel.wifi.get_signal_strength", return_value=-50):
            wifi.log_wifi(conn)
    hours = wifi.time_on_network(conn, "X")
    assert hours >= 0


def test_most_common_empty(conn):
    assert wifi.most_common_networks(conn) == []
