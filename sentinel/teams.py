"""Teams — shared rules, goals, and scores across team members."""
import time
from . import db


def _ensure_tables(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY, name TEXT UNIQUE, created_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS team_members (
        team_id INTEGER, member_name TEXT, role TEXT DEFAULT 'member',
        joined_at REAL, PRIMARY KEY (team_id, member_name)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS team_rules (
        team_id INTEGER, rule_text TEXT, PRIMARY KEY (team_id, rule_text)
    )""")


def create_team(conn, name: str) -> int:
    _ensure_tables(conn)
    cur = conn.execute("INSERT OR IGNORE INTO teams (name, created_at) VALUES (?, ?)",
                       (name, time.time()))
    if cur.lastrowid == 0:
        r = conn.execute("SELECT id FROM teams WHERE name=?", (name,)).fetchone()
        conn.commit()
        return r["id"] if r else 0
    conn.commit()
    return cur.lastrowid


def add_member(conn, team_id: int, member_name: str, role: str = "member"):
    _ensure_tables(conn)
    conn.execute(
        "INSERT OR REPLACE INTO team_members (team_id, member_name, role, joined_at) VALUES (?,?,?,?)",
        (team_id, member_name, role, time.time()))
    conn.commit()


def remove_member(conn, team_id: int, member_name: str):
    _ensure_tables(conn)
    conn.execute("DELETE FROM team_members WHERE team_id=? AND member_name=?",
                 (team_id, member_name))
    conn.commit()


def get_team(conn, team_id: int) -> dict:
    _ensure_tables(conn)
    t = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
    if not t:
        return None
    members = [dict(r) for r in conn.execute(
        "SELECT * FROM team_members WHERE team_id=?", (team_id,)).fetchall()]
    return {**dict(t), "members": members}


def list_teams(conn) -> list:
    _ensure_tables(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM teams").fetchall()]


def delete_team(conn, team_id: int):
    _ensure_tables(conn)
    conn.execute("DELETE FROM teams WHERE id=?", (team_id,))
    conn.execute("DELETE FROM team_members WHERE team_id=?", (team_id,))
    conn.execute("DELETE FROM team_rules WHERE team_id=?", (team_id,))
    conn.commit()


def add_team_rule(conn, team_id: int, rule_text: str):
    _ensure_tables(conn)
    conn.execute("INSERT OR IGNORE INTO team_rules (team_id, rule_text) VALUES (?, ?)",
                 (team_id, rule_text))
    conn.commit()


def get_team_rules(conn, team_id: int) -> list:
    _ensure_tables(conn)
    return [r["rule_text"] for r in conn.execute(
        "SELECT rule_text FROM team_rules WHERE team_id=?", (team_id,)).fetchall()]


def apply_team_rules_to_local(conn, team_id: int) -> int:
    """Import team rules into local rules table."""
    count = 0
    for text in get_team_rules(conn, team_id):
        db.add_rule(conn, text)
        count += 1
    return count
