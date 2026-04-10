"""SQLite — the box's storage substrate.

Only primitives live here. Features (pomodoro, focus, goals, streaks,
interventions, penalties, partners, allowances, chat history, audit log)
used to have their own tables; they're all gone because triggers + ai_store
can reproduce them. Module-local tables (ai_store, triggers) are created by
those modules on first use.
"""
import sqlite3, json, time
from pathlib import Path

DB_PATH = Path.home() / ".config" / "sentinel" / "sentinel.db"

def connect(path=None):
    p = path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False lets the single shared server connection be
    # used from FastAPI's worker threadpool. WAL + application-level single-
    # writer semantics keep this safe in practice.
    conn = sqlite3.connect(str(p), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY, text TEXT NOT NULL, parsed TEXT DEFAULT '{}',
            action TEXT DEFAULT 'block', active INTEGER DEFAULT 1,
            created_at REAL
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY, ts REAL, app TEXT, title TEXT,
            url TEXT, domain TEXT, verdict TEXT, rule_id INTEGER,
            duration_s REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS seen_domains (
            domain TEXT PRIMARY KEY, category TEXT, first_seen REAL
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY, value TEXT
        );
    """)
    # Backfill duration_s column for pre-existing databases.
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(activity_log)").fetchall()]
    if "duration_s" not in cols:
        conn.execute("ALTER TABLE activity_log ADD COLUMN duration_s REAL DEFAULT 0")
    return conn

# --- Rules ---
def add_rule(conn, text, parsed=None):
    cur = conn.execute("INSERT INTO rules (text, parsed) VALUES (?, ?)",
                       (text, json.dumps(parsed or {})))
    conn.commit()
    return cur.lastrowid

def get_rules(conn, active_only=True):
    q = "SELECT * FROM rules" + (" WHERE active=1" if active_only else "")
    return [dict(r) for r in conn.execute(q).fetchall()]

def toggle_rule(conn, rule_id):
    conn.execute("UPDATE rules SET active = NOT active WHERE id=?", (rule_id,))
    conn.commit()

def delete_rule(conn, rule_id):
    conn.execute("DELETE FROM rules WHERE id=?", (rule_id,))
    conn.commit()

def update_rule_parsed(conn, rule_id, parsed):
    conn.execute("UPDATE rules SET parsed=? WHERE id=?", (json.dumps(parsed), rule_id))
    conn.commit()

# --- Activity ---
def log_activity(conn, app, title, url, domain, verdict=None, rule_id=None):
    conn.execute("INSERT INTO activity_log (ts,app,title,url,domain,verdict,rule_id) VALUES (?,?,?,?,?,?,?)",
                 (time.time(), app, title, url, domain, verdict, rule_id))
    conn.commit()

def get_activities(conn, since=None, limit=100):
    if since:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM activity_log WHERE ts>? ORDER BY ts DESC LIMIT ?", (since, limit))]
    return [dict(r) for r in conn.execute(
        "SELECT * FROM activity_log ORDER BY ts DESC LIMIT ?", (limit,))]

# --- Seen domains ---
def get_seen(conn, domain):
    r = conn.execute("SELECT category FROM seen_domains WHERE domain=?", (domain,)).fetchone()
    return r["category"] if r else None

def save_seen(conn, domain, category):
    conn.execute("INSERT OR REPLACE INTO seen_domains (domain,category,first_seen) VALUES (?,?,?)",
                 (domain, category, time.time()))
    conn.commit()

# --- Config ---
def get_config(conn, key, default=None):
    r = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default

def set_config(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO config (key,value) VALUES (?,?)", (key, value))
    conn.commit()
