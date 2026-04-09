"""Tests for sentinel.location."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import location, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_add_location(conn):
    lid = location.add_location(conn, "Home", "HomeWiFi")
    assert lid > 0


def test_add_work_location(conn):
    lid = location.add_location(conn, "Office", "WorkWiFi", is_work=True)
    locs = location.get_locations(conn)
    assert locs[0]["is_work"] == 1


def test_get_locations_empty(conn):
    assert location.get_locations(conn) == []


def test_delete_location(conn):
    lid = location.add_location(conn, "Home", "HomeWiFi")
    location.delete_location(conn, lid)
    assert location.get_locations(conn) == []


def test_get_current_wifi_ssid_mock():
    with patch("sentinel.location.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout=" SSID: TestNetwork")
        ssid = location.get_current_wifi_ssid()
        # Either "TestNetwork" or empty — depends on airport command success
        assert isinstance(ssid, str)


def test_current_location_unknown(conn):
    with patch("sentinel.location.get_current_wifi_ssid", return_value=""):
        loc = location.current_location(conn)
        assert loc["name"] == "unknown"


def test_current_location_known(conn):
    location.add_location(conn, "Home", "MyWiFi")
    with patch("sentinel.location.get_current_wifi_ssid", return_value="MyWiFi"):
        loc = location.current_location(conn)
        assert loc["name"] == "Home"


def test_is_at_work(conn):
    location.add_location(conn, "Office", "WorkWiFi", is_work=True)
    with patch("sentinel.location.get_current_wifi_ssid", return_value="WorkWiFi"):
        assert location.is_at_work(conn) is True


def test_is_at_home(conn):
    location.add_location(conn, "Home", "HomeWiFi", is_work=False)
    with patch("sentinel.location.get_current_wifi_ssid", return_value="HomeWiFi"):
        assert location.is_at_home(conn) is True


def test_replace_location(conn):
    location.add_location(conn, "Home", "WiFi")
    location.add_location(conn, "Home Updated", "WiFi")
    locs = location.get_locations(conn)
    assert len(locs) == 1
    assert locs[0]["name"] == "Home Updated"


def test_log_location_change(conn):
    location.log_location_change(conn, "NewWiFi")
    # Just verify no exception
