"""Tests for sentinel.battery."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import battery, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_get_battery_info_ac():
    mock_output = "Now drawing from 'AC Power'\n -InternalBattery-0 100%; charged;"
    with patch("sentinel.battery.subprocess.run",
               return_value=MagicMock(returncode=0, stdout=mock_output)):
        info = battery.get_battery_info()
        assert info["level"] == 100
        assert info["source"] == "ac"


def test_get_battery_info_battery():
    mock_output = "Now drawing from 'Battery Power'\n -InternalBattery-0 75%; discharging;"
    with patch("sentinel.battery.subprocess.run",
               return_value=MagicMock(returncode=0, stdout=mock_output)):
        info = battery.get_battery_info()
        assert info["level"] == 75
        assert info["source"] == "battery"


def test_get_battery_info_error():
    with patch("sentinel.battery.subprocess.run", side_effect=Exception("fail")):
        info = battery.get_battery_info()
        assert info["level"] == 100
        assert info["source"] == "unknown"


def test_is_on_battery():
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 50, "charging": False, "source": "battery"}):
        assert battery.is_on_battery() is True


def test_is_on_ac():
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 100, "charging": True, "source": "ac"}):
        assert battery.is_on_battery() is False


def test_is_low_battery_true():
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 15, "charging": False, "source": "battery"}):
        assert battery.is_low_battery() is True


def test_is_low_battery_false():
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 80, "charging": False, "source": "battery"}):
        assert battery.is_low_battery() is False


def test_critical_battery():
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 5, "charging": False, "source": "battery"}):
        assert battery.is_critical_battery() is True


def test_status_string_ac():
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 100, "charging": True, "source": "ac"}):
        assert "Plugged in" in battery.get_status_string()


def test_status_string_battery():
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 50, "charging": False, "source": "battery"}):
        s = battery.get_status_string()
        assert "50%" in s


def test_should_conserve():
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 25, "charging": False, "source": "battery"}):
        assert battery.should_conserve() is True


def test_log_battery(conn):
    with patch("sentinel.battery.get_battery_info",
               return_value={"level": 80, "charging": False, "source": "battery"}):
        battery.log_battery(conn)
        log = battery.get_battery_log(conn)
        assert len(log) == 1
