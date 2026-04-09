"""SQLite database — single file, all state."""
import sqlite3, json, time
from pathlib import Path

DB_PATH = Path.home() / ".config" / "sentinel" / "sentinel.db"

def connect(path=None):
    p = path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
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
        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INTEGER PRIMARY KEY, start_ts REAL,
            work_minutes INTEGER, break_minutes INTEGER,
            total_cycles INTEGER, current_cycle INTEGER DEFAULT 1,
            state TEXT DEFAULT 'work', ended_at REAL
        );
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY, start_ts REAL,
            duration_minutes INTEGER, locked INTEGER DEFAULT 1,
            ended_at REAL
        );
        CREATE TABLE IF NOT EXISTS allowance_log (
            id INTEGER PRIMARY KEY, rule_id INTEGER,
            date TEXT, seconds_used INTEGER DEFAULT 0,
            UNIQUE(rule_id, date)
        );
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY, kind TEXT, context TEXT, state TEXT,
            created_at REAL, completed_at REAL, passed INTEGER, attempts INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY, name TEXT, target_type TEXT,
            target_value INTEGER, category TEXT, created_at REAL
        );
        CREATE TABLE IF NOT EXISTS streaks (
            goal_name TEXT PRIMARY KEY, current INTEGER DEFAULT 0,
            longest INTEGER DEFAULT 0, last_date TEXT
        );
        CREATE TABLE IF NOT EXISTS partners (
            id INTEGER PRIMARY KEY, name TEXT, contact TEXT,
            method TEXT DEFAULT 'webhook', created_at REAL
        );
        CREATE TABLE IF NOT EXISTS penalties (
            id INTEGER PRIMARY KEY, rule_id INTEGER, amount REAL,
            created_at REAL, paid INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS penalty_rules (
            rule_id INTEGER PRIMARY KEY, amount REAL
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

# --- Pomodoro ---
def save_pomodoro(conn, start_ts, work_minutes, break_minutes, total_cycles):
    cur = conn.execute(
        "INSERT INTO pomodoro_sessions (start_ts,work_minutes,break_minutes,total_cycles) VALUES (?,?,?,?)",
        (start_ts, work_minutes, break_minutes, total_cycles))
    conn.commit()
    return cur.lastrowid

def get_active_pomodoro(conn):
    r = conn.execute(
        "SELECT * FROM pomodoro_sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(r) if r else None

def update_pomodoro(conn, pid, **fields):
    if not fields:
        return
    cols = ",".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE pomodoro_sessions SET {cols} WHERE id=?", (*fields.values(), pid))
    conn.commit()

# --- Focus sessions ---
def save_focus_session(conn, start_ts, duration_minutes, locked):
    cur = conn.execute(
        "INSERT INTO focus_sessions (start_ts,duration_minutes,locked) VALUES (?,?,?)",
        (start_ts, duration_minutes, 1 if locked else 0))
    conn.commit()
    return cur.lastrowid

def get_active_focus(conn):
    r = conn.execute(
        "SELECT * FROM focus_sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return dict(r) if r else None

def end_focus(conn, session_id, ended_at):
    conn.execute("UPDATE focus_sessions SET ended_at=? WHERE id=?", (ended_at, session_id))
    conn.commit()

# --- Allowance log ---
def add_allowance_use(conn, rule_id, date, seconds):
    conn.execute(
        "INSERT INTO allowance_log (rule_id,date,seconds_used) VALUES (?,?,?) "
        "ON CONFLICT(rule_id,date) DO UPDATE SET seconds_used = seconds_used + ?",
        (rule_id, date, seconds, seconds))
    conn.commit()

def get_allowance_used(conn, rule_id, date):
    r = conn.execute(
        "SELECT seconds_used FROM allowance_log WHERE rule_id=? AND date=?",
        (rule_id, date)).fetchone()
    return r["seconds_used"] if r else 0

# --- Interventions ---
def save_intervention(conn, kind, context, state):
    cur = conn.execute(
        "INSERT INTO interventions (kind,context,state,created_at,attempts) VALUES (?,?,?,?,0)",
        (kind, json.dumps(context), json.dumps(state), time.time()))
    conn.commit()
    return cur.lastrowid

def update_intervention(conn, iid, **fields):
    if not fields:
        return
    if "state" in fields and not isinstance(fields["state"], str):
        fields["state"] = json.dumps(fields["state"])
    if "context" in fields and not isinstance(fields["context"], str):
        fields["context"] = json.dumps(fields["context"])
    cols = ",".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE interventions SET {cols} WHERE id=?", (*fields.values(), iid))
    conn.commit()

def get_intervention_by_id(conn, iid):
    r = conn.execute("SELECT * FROM interventions WHERE id=?", (iid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["context"] = json.loads(d["context"]) if d["context"] else {}
    d["state"] = json.loads(d["state"]) if d["state"] else {}
    return d
