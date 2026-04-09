"""Tests for sentinel.penalties — $$ penalties for rule violations."""

import pytest

from sentinel import db, penalties


class TestPenaltyRules:
    def test_add_rule(self, conn):
        penalties.add_penalty_rule(conn, 1, 5.0)
        assert penalties.get_penalty_rule(conn, 1) == 5.0

    def test_add_rule_upserts(self, conn):
        penalties.add_penalty_rule(conn, 1, 5.0)
        penalties.add_penalty_rule(conn, 1, 10.0)
        assert penalties.get_penalty_rule(conn, 1) == 10.0

    def test_missing_rule_returns_none(self, conn):
        assert penalties.get_penalty_rule(conn, 99) is None

    def test_remove_penalty_rule(self, conn):
        penalties.add_penalty_rule(conn, 1, 5.0)
        penalties.remove_penalty_rule(conn, 1)
        assert penalties.get_penalty_rule(conn, 1) is None


class TestRecordViolation:
    def test_record_with_amount(self, conn):
        pid = penalties.record_violation(conn, 1, 2.5)
        assert pid >= 1

    def test_record_uses_penalty_rule(self, conn):
        penalties.add_penalty_rule(conn, 1, 7.5)
        pid = penalties.record_violation(conn, 1)
        pending = penalties.get_pending_penalties(conn)
        assert pending[0]["amount"] == 7.5
        assert pending[0]["id"] == pid

    def test_record_missing_rule_defaults_zero(self, conn):
        penalties.record_violation(conn, 42)
        pending = penalties.get_pending_penalties(conn)
        assert pending[0]["amount"] == 0.0


class TestPending:
    def test_empty(self, conn):
        assert penalties.get_pending_penalties(conn) == []

    def test_only_unpaid(self, conn):
        a = penalties.record_violation(conn, 1, 1.0)
        b = penalties.record_violation(conn, 1, 2.0)
        penalties.mark_penalty_paid(conn, a)
        pending = penalties.get_pending_penalties(conn)
        assert [p["id"] for p in pending] == [b]

    def test_all_penalties_includes_paid(self, conn):
        a = penalties.record_violation(conn, 1, 1.0)
        penalties.mark_penalty_paid(conn, a)
        assert len(penalties.get_all_penalties(conn)) == 1


class TestTotals:
    def test_total_owed_zero(self, conn):
        assert penalties.total_owed(conn) == 0.0

    def test_total_owed_sums_unpaid(self, conn):
        penalties.record_violation(conn, 1, 1.5)
        penalties.record_violation(conn, 1, 2.5)
        assert penalties.total_owed(conn) == 4.0

    def test_total_owed_excludes_paid(self, conn):
        a = penalties.record_violation(conn, 1, 3.0)
        penalties.record_violation(conn, 1, 4.0)
        penalties.mark_penalty_paid(conn, a)
        assert penalties.total_owed(conn) == 4.0

    def test_total_paid(self, conn):
        a = penalties.record_violation(conn, 1, 5.0)
        penalties.mark_penalty_paid(conn, a)
        assert penalties.total_paid(conn) == 5.0

    def test_mark_paid_idempotent(self, conn):
        a = penalties.record_violation(conn, 1, 1.0)
        penalties.mark_penalty_paid(conn, a)
        penalties.mark_penalty_paid(conn, a)
        assert penalties.total_owed(conn) == 0.0
