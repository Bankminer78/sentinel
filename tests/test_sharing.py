"""Tests for sentinel.sharing."""
import pytest
from sentinel import sharing, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_rule_share_code(conn):
    db.add_rule(conn, "Block YouTube")
    code = sharing.create_share_code(conn, "rule")
    assert code.startswith("R-")


def test_create_goal_share_code(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY, name TEXT, target_type TEXT,
        target_value INTEGER, category TEXT, created_at REAL)""")
    conn.execute("INSERT INTO goals (name, target_type, target_value) VALUES (?,?,?)",
                 ("Test goal", "max_seconds", 1800))
    conn.commit()
    code = sharing.create_share_code(conn, "goal")
    assert code.startswith("G-")


def test_get_share_bundle(conn):
    db.add_rule(conn, "Rule")
    code = sharing.create_share_code(conn, "rule")
    bundle = sharing.get_share_bundle(conn, code)
    assert bundle is not None
    assert bundle["content_type"] == "rule"


def test_get_nonexistent_share(conn):
    assert sharing.get_share_bundle(conn, "R-ghost") is None


def test_apply_rule_share_code(conn):
    db.add_rule(conn, "Original rule")
    code = sharing.create_share_code(conn, "rule")
    bundle = sharing.get_share_bundle(conn, code)
    # Clear and re-apply
    db.delete_rule(conn, 1)
    result = sharing.apply_share_code(conn, code, bundle)
    assert result["added"] >= 1


def test_list_my_shares(conn):
    db.add_rule(conn, "Rule")
    sharing.create_share_code(conn, "rule")
    sharing.create_share_code(conn, "rule")
    shares = sharing.list_my_shares(conn)
    assert len(shares) == 2


def test_revoke_share(conn):
    db.add_rule(conn, "Rule")
    code = sharing.create_share_code(conn, "rule")
    sharing.revoke_share(conn, code)
    assert sharing.get_share_bundle(conn, code) is None


def test_export_share_bundle():
    content = {"rules": [{"text": "Test"}]}
    encoded = sharing.export_share_bundle(content)
    assert encoded


def test_import_share_bundle():
    content = {"rules": [{"text": "Test"}]}
    encoded = sharing.export_share_bundle(content)
    decoded = sharing.import_share_bundle(encoded)
    assert decoded == content


def test_import_invalid_bundle():
    assert sharing.import_share_bundle("not-valid") == {}


def test_create_all_share(conn):
    db.add_rule(conn, "Rule")
    code = sharing.create_share_code(conn, "all")
    assert code.startswith("A-")


def test_share_code_unique(conn):
    db.add_rule(conn, "Rule")
    import time
    code1 = sharing.create_share_code(conn, "rule")
    time.sleep(0.001)
    code2 = sharing.create_share_code(conn, "rule")
    assert code1 != code2


def test_shares_ordered_by_recency(conn):
    db.add_rule(conn, "R1")
    import time
    sharing.create_share_code(conn, "rule")
    time.sleep(0.001)
    sharing.create_share_code(conn, "rule")
    shares = sharing.list_my_shares(conn)
    assert shares[0]["created_at"] >= shares[1]["created_at"]


def test_habit_share(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY, name TEXT, created_at REAL)""")
    conn.execute("INSERT INTO habits (name) VALUES (?)", ("Meditate",))
    conn.commit()
    code = sharing.create_share_code(conn, "habit")
    assert code.startswith("H-")
