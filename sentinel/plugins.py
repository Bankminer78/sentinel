"""Plugin system — load and manage third-party plugins."""
import importlib, importlib.util, time
from pathlib import Path


PLUGIN_DIR = Path.home() / ".config" / "sentinel" / "plugins"
_loaded = {}  # name -> module


def _ensure_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS plugins (
        name TEXT PRIMARY KEY, path TEXT, enabled INTEGER DEFAULT 1,
        installed_at REAL
    )""")


def list_available_plugins() -> list:
    """Scan plugin dir for available plugins."""
    if not PLUGIN_DIR.exists():
        return []
    return [f.stem for f in PLUGIN_DIR.glob("*.py") if not f.stem.startswith("_")]


def register_plugin(conn, name: str, path: str) -> int:
    _ensure_table(conn)
    conn.execute(
        "INSERT OR REPLACE INTO plugins (name, path, enabled, installed_at) VALUES (?, ?, 1, ?)",
        (name, path, time.time()))
    conn.commit()
    return 1


def get_plugins(conn) -> list:
    _ensure_table(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM plugins").fetchall()]


def enable_plugin(conn, name: str):
    _ensure_table(conn)
    conn.execute("UPDATE plugins SET enabled=1 WHERE name=?", (name,))
    conn.commit()


def disable_plugin(conn, name: str):
    _ensure_table(conn)
    conn.execute("UPDATE plugins SET enabled=0 WHERE name=?", (name,))
    conn.commit()


def delete_plugin(conn, name: str):
    _ensure_table(conn)
    conn.execute("DELETE FROM plugins WHERE name=?", (name,))
    conn.commit()
    if name in _loaded:
        del _loaded[name]


def load_plugin(path: str, name: str = None):
    """Load a plugin from path. Returns the module."""
    p = Path(path)
    if not p.exists():
        return None
    plugin_name = name or p.stem
    try:
        spec = importlib.util.spec_from_file_location(plugin_name, str(p))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded[plugin_name] = module
        return module
    except Exception:
        return None


def get_loaded(name: str):
    return _loaded.get(name)


def call_plugin_hook(name: str, hook: str, *args, **kwargs):
    """Call a hook function on a plugin."""
    m = _loaded.get(name)
    if m and hasattr(m, hook):
        try:
            return getattr(m, hook)(*args, **kwargs)
        except Exception:
            return None
    return None


def broadcast_hook(conn, hook: str, *args, **kwargs) -> list:
    """Call a hook on all enabled plugins."""
    results = []
    for p in get_plugins(conn):
        if p["enabled"]:
            result = call_plugin_hook(p["name"], hook, *args, **kwargs)
            if result is not None:
                results.append({"plugin": p["name"], "result": result})
    return results
