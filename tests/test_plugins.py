"""Tests for sentinel.plugins."""
import pytest
from pathlib import Path
from sentinel import plugins, db


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_register_plugin(conn):
    plugins.register_plugin(conn, "test_plugin", "/tmp/test.py")
    p_list = plugins.get_plugins(conn)
    assert len(p_list) == 1


def test_register_replaces(conn):
    plugins.register_plugin(conn, "my_plugin", "/tmp/old.py")
    plugins.register_plugin(conn, "my_plugin", "/tmp/new.py")
    p_list = plugins.get_plugins(conn)
    assert len(p_list) == 1
    assert p_list[0]["path"] == "/tmp/new.py"


def test_get_plugins_empty(conn):
    assert plugins.get_plugins(conn) == []


def test_enable_plugin(conn):
    plugins.register_plugin(conn, "test", "/tmp/x.py")
    plugins.disable_plugin(conn, "test")
    plugins.enable_plugin(conn, "test")
    p_list = plugins.get_plugins(conn)
    assert p_list[0]["enabled"] == 1


def test_disable_plugin(conn):
    plugins.register_plugin(conn, "test", "/tmp/x.py")
    plugins.disable_plugin(conn, "test")
    p_list = plugins.get_plugins(conn)
    assert p_list[0]["enabled"] == 0


def test_delete_plugin(conn):
    plugins.register_plugin(conn, "test", "/tmp/x.py")
    plugins.delete_plugin(conn, "test")
    assert plugins.get_plugins(conn) == []


def test_load_nonexistent_plugin():
    assert plugins.load_plugin("/nonexistent/path.py") is None


def test_load_valid_plugin(tmp_path):
    plugin_file = tmp_path / "test_plugin.py"
    plugin_file.write_text("def hello(): return 'world'")
    module = plugins.load_plugin(str(plugin_file), "test_plugin")
    assert module is not None
    assert module.hello() == "world"


def test_get_loaded():
    assert plugins.get_loaded("nonexistent") is None


def test_call_plugin_hook_nonexistent():
    assert plugins.call_plugin_hook("ghost", "on_activity") is None


def test_call_plugin_hook_valid(tmp_path):
    plugin_file = tmp_path / "hook_plugin.py"
    plugin_file.write_text("def on_event(data): return data * 2")
    plugins.load_plugin(str(plugin_file), "hook_plugin")
    result = plugins.call_plugin_hook("hook_plugin", "on_event", 5)
    assert result == 10


def test_broadcast_hook_empty(conn):
    results = plugins.broadcast_hook(conn, "on_event")
    assert results == []
