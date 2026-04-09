"""Tests for sentinel.teams."""
import pytest
from sentinel import teams, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_create_team(conn):
    tid = teams.create_team(conn, "Engineering")
    assert tid > 0


def test_create_duplicate_team(conn):
    tid1 = teams.create_team(conn, "Eng")
    tid2 = teams.create_team(conn, "Eng")
    assert len(teams.list_teams(conn)) == 1


def test_list_teams_empty(conn):
    assert teams.list_teams(conn) == []


def test_add_member(conn):
    tid = teams.create_team(conn, "Eng")
    teams.add_member(conn, tid, "alice")
    team = teams.get_team(conn, tid)
    assert len(team["members"]) == 1


def test_add_member_with_role(conn):
    tid = teams.create_team(conn, "Eng")
    teams.add_member(conn, tid, "alice", role="admin")
    team = teams.get_team(conn, tid)
    assert team["members"][0]["role"] == "admin"


def test_remove_member(conn):
    tid = teams.create_team(conn, "Eng")
    teams.add_member(conn, tid, "alice")
    teams.remove_member(conn, tid, "alice")
    team = teams.get_team(conn, tid)
    assert len(team["members"]) == 0


def test_get_team_nonexistent(conn):
    assert teams.get_team(conn, 999) is None


def test_delete_team(conn):
    tid = teams.create_team(conn, "Eng")
    teams.add_member(conn, tid, "alice")
    teams.delete_team(conn, tid)
    assert teams.list_teams(conn) == []


def test_add_team_rule(conn):
    tid = teams.create_team(conn, "Eng")
    teams.add_team_rule(conn, tid, "Block YouTube")
    rules = teams.get_team_rules(conn, tid)
    assert "Block YouTube" in rules


def test_duplicate_team_rule(conn):
    tid = teams.create_team(conn, "Eng")
    teams.add_team_rule(conn, tid, "Rule")
    teams.add_team_rule(conn, tid, "Rule")
    assert len(teams.get_team_rules(conn, tid)) == 1


def test_apply_team_rules(conn):
    tid = teams.create_team(conn, "Eng")
    teams.add_team_rule(conn, tid, "Rule 1")
    teams.add_team_rule(conn, tid, "Rule 2")
    count = teams.apply_team_rules_to_local(conn, tid)
    assert count == 2
    assert len(db.get_rules(conn)) == 2


def test_apply_empty_team_rules(conn):
    tid = teams.create_team(conn, "Eng")
    count = teams.apply_team_rules_to_local(conn, tid)
    assert count == 0
