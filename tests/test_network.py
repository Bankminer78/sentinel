"""Tests for sentinel.network — subprocess mocked."""
import pytest
from unittest.mock import patch, MagicMock
from sentinel import network


def _mk_cp(returncode=0, stdout="", stderr=""):
    cp = MagicMock()
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


def test_flush_dns_success():
    with patch("sentinel.network.subprocess.run", return_value=_mk_cp(0)):
        assert network.flush_dns() is True


def test_flush_dns_failure():
    with patch("sentinel.network.subprocess.run", return_value=_mk_cp(1)):
        assert network.flush_dns() is False


def test_flush_dns_exception():
    with patch("sentinel.network.subprocess.run", side_effect=OSError):
        assert network.flush_dns() is False


def test_get_current_dns_parses():
    stdout = "nameserver[0] : 8.8.8.8\nnameserver[1] : 1.1.1.1\n"
    with patch("sentinel.network.subprocess.run",
               return_value=_mk_cp(0, stdout=stdout)):
        dns = network.get_current_dns()
        assert "8.8.8.8" in dns
        assert "1.1.1.1" in dns


def test_get_current_dns_error():
    with patch("sentinel.network.subprocess.run", return_value=_mk_cp(1)):
        assert network.get_current_dns() == []


def test_get_current_dns_exception():
    with patch("sentinel.network.subprocess.run", side_effect=OSError):
        assert network.get_current_dns() == []


def test_is_hosts_file_clean_matched_markers(tmp_path):
    content = "127.0.0.1 localhost\n# SENTINEL BLOCK START\n0.0.0.0 a.com\n# SENTINEL BLOCK END\n"
    with patch("sentinel.network.Path") as mp:
        mp.return_value.read_text.return_value = content
        assert network.is_hosts_file_clean() is True


def test_is_hosts_file_clean_unbalanced(tmp_path):
    content = "# SENTINEL BLOCK START\n0.0.0.0 a.com\n"
    with patch("sentinel.network.Path") as mp:
        mp.return_value.read_text.return_value = content
        assert network.is_hosts_file_clean() is False


def test_count_hosts_entries():
    content = "# comment\n\n127.0.0.1 localhost\n0.0.0.0 youtube.com\n"
    with patch("sentinel.network.Path") as mp:
        mp.return_value.read_text.return_value = content
        assert network.count_hosts_entries() == 2


def test_count_hosts_entries_error():
    with patch("sentinel.network.Path") as mp:
        mp.return_value.read_text.side_effect = OSError
        assert network.count_hosts_entries() == 0


def test_backup_hosts_success(tmp_path):
    with patch("sentinel.network.shutil.copy2") as mc, \
         patch("sentinel.network._BACKUP_DIR", tmp_path):
        path = network.backup_hosts()
        assert path.startswith(str(tmp_path))
        assert mc.called


def test_backup_hosts_failure(tmp_path):
    with patch("sentinel.network.shutil.copy2", side_effect=OSError), \
         patch("sentinel.network._BACKUP_DIR", tmp_path):
        assert network.backup_hosts() == ""


def test_restore_hosts_missing(tmp_path):
    assert network.restore_hosts_from_backup(str(tmp_path / "nope")) is False


def test_restore_hosts_success(tmp_path):
    backup = tmp_path / "hosts.bak"
    backup.write_text("content")
    with patch("sentinel.network.shutil.copy2") as mc:
        assert network.restore_hosts_from_backup(str(backup)) is True
        assert mc.called


def test_get_listening_ports_parses():
    stdout = ("COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME\n"
              "nginx 1234 root 3 IPv4 0t0 TCP *:80 (LISTEN)\n")
    with patch("sentinel.network.subprocess.run",
               return_value=_mk_cp(0, stdout=stdout)):
        ports = network.get_listening_ports()
        assert len(ports) == 1
        assert ports[0]["port"] == 80


def test_get_listening_ports_error():
    with patch("sentinel.network.subprocess.run", return_value=_mk_cp(1)):
        assert network.get_listening_ports() == []


def test_is_port_available_free():
    # Use a high-numbered port likely available
    assert isinstance(network.is_port_available(54321), bool)


def test_is_port_available_bound():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.listen(1)
    try:
        assert network.is_port_available(port) is False
    finally:
        s.close()
