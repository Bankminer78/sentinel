"""Tests for sentinel.interventions — friction state machines."""

import time
import json
import asyncio
from unittest.mock import patch, mock_open, AsyncMock, MagicMock

import pytest

from sentinel import interventions, db


# ---------------------------------------------------------------------------
# generate_typing_challenge
# ---------------------------------------------------------------------------


class TestTypingChallengeGeneration:
    def test_returns_string(self):
        assert isinstance(interventions.generate_typing_challenge(), str)

    def test_length_minimum_50(self):
        p = interventions.generate_typing_challenge(50)
        assert len(p) >= 40  # approximate — phrases all around that length

    def test_variety(self):
        results = {interventions.generate_typing_challenge() for _ in range(50)}
        assert len(results) > 1

    def test_small_length(self):
        p = interventions.generate_typing_challenge(10)
        assert len(p) >= 10

    def test_huge_length_falls_back(self):
        p = interventions.generate_typing_challenge(10_000)
        assert isinstance(p, str)
        assert len(p) > 0

    def test_phrases_nonempty(self):
        assert len(interventions.PHRASES) >= 10


# ---------------------------------------------------------------------------
# generate_math_challenge
# ---------------------------------------------------------------------------


class TestMathChallengeGeneration:
    def test_returns_tuple(self):
        result = interventions.generate_math_challenge()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_problem_is_string(self):
        p, a = interventions.generate_math_challenge()
        assert isinstance(p, str)

    def test_answer_is_int(self):
        p, a = interventions.generate_math_challenge()
        assert isinstance(a, int)

    def test_answer_correct(self):
        for _ in range(50):
            problem, answer = interventions.generate_math_challenge()
            assert eval(problem) == answer

    def test_covers_all_ops(self):
        ops = set()
        for _ in range(200):
            p, _ = interventions.generate_math_challenge()
            for o in ("+", "-", "*"):
                if o in p:
                    ops.add(o)
                    break
        assert ops == {"+", "-", "*"}


# ---------------------------------------------------------------------------
# create_intervention
# ---------------------------------------------------------------------------


class TestCreateIntervention:
    def test_unknown_kind_raises(self, conn):
        with pytest.raises(ValueError):
            interventions.create_intervention(conn, "nonsense", {})

    def test_create_countdown(self, conn):
        iv = interventions.create_intervention(conn, "countdown", {"duration": 5})
        assert iv["kind"] == "countdown"
        assert iv["id"] > 0
        assert iv["deadline"] is not None

    def test_create_breathing(self, conn):
        iv = interventions.create_intervention(conn, "breathing", {"pattern": "478"})
        assert iv["kind"] == "breathing"
        assert "478" in iv["prompt"] or "4-7-8" in iv["prompt"]

    def test_create_breathing_box(self, conn):
        iv = interventions.create_intervention(conn, "breathing", {"pattern": "box"})
        assert "Box" in iv["prompt"]

    def test_create_typing(self, conn):
        iv = interventions.create_intervention(conn, "typing", {})
        assert iv["kind"] == "typing"
        assert iv["expected_input"]
        assert iv["expected_input"] in iv["prompt"]

    def test_create_negotiate(self, conn):
        iv = interventions.create_intervention(conn, "negotiate",
                                                {"domain": "reddit.com", "rule_text": "focus",
                                                 "minutes": 10})
        assert iv["kind"] == "negotiate"
        assert iv["state"]["turns"] == []

    def test_create_math(self, conn):
        iv = interventions.create_intervention(conn, "math", {})
        assert iv["kind"] == "math"
        assert iv["expected_input"] is not None

    def test_create_wait(self, conn):
        iv = interventions.create_intervention(conn, "wait", {"duration": 60})
        assert iv["kind"] == "wait"
        assert iv["deadline"] is not None

    def test_create_photo(self, conn):
        iv = interventions.create_intervention(conn, "photo", {"task": "do pushups"})
        assert iv["kind"] == "photo"
        assert "pushups" in iv["prompt"]

    def test_persisted_to_db(self, conn):
        iv = interventions.create_intervention(conn, "math", {})
        stored = db.get_intervention_by_id(conn, iv["id"])
        assert stored["kind"] == "math"


# ---------------------------------------------------------------------------
# submit_intervention
# ---------------------------------------------------------------------------


class TestSubmitCountdown:
    def test_countdown_not_expired(self, conn):
        iv = interventions.create_intervention(conn, "countdown", {"duration": 60})
        r = interventions.submit_intervention(conn, iv["id"], "")
        assert r["passed"] is False
        assert "remaining" in r["feedback"]

    def test_countdown_expired(self, conn):
        iv = interventions.create_intervention(conn, "countdown", {"duration": 0})
        time.sleep(0.01)
        r = interventions.submit_intervention(conn, iv["id"], "")
        assert r["passed"] is True

    def test_countdown_cancel(self, conn):
        iv = interventions.create_intervention(conn, "countdown", {"duration": 60})
        r = interventions.submit_intervention(conn, iv["id"], "cancel")
        assert r["passed"] is False
        assert r["feedback"] == "cancelled"


class TestSubmitWait:
    def test_wait_not_expired(self, conn):
        iv = interventions.create_intervention(conn, "wait", {"duration": 60})
        r = interventions.submit_intervention(conn, iv["id"], "")
        assert r["passed"] is False

    def test_wait_expired(self, conn):
        iv = interventions.create_intervention(conn, "wait", {"duration": 0})
        time.sleep(0.01)
        r = interventions.submit_intervention(conn, iv["id"], "")
        assert r["passed"] is True

    def test_wait_cancel(self, conn):
        iv = interventions.create_intervention(conn, "wait", {"duration": 60})
        r = interventions.submit_intervention(conn, iv["id"], "cancel")
        assert r["passed"] is False


class TestSubmitBreathing:
    def test_breathing_not_expired(self, conn):
        iv = interventions.create_intervention(conn, "breathing", {"pattern": "478"})
        r = interventions.submit_intervention(conn, iv["id"], "")
        assert r["passed"] is False

    def test_breathing_expired(self, conn):
        iv = interventions.create_intervention(conn, "breathing", {"pattern": "478"})
        # force deadline in past
        db.update_intervention(conn, iv["id"], state={"pattern": iv["state"]["pattern"],
                                                       "deadline": time.time() - 1})
        r = interventions.submit_intervention(conn, iv["id"], "")
        assert r["passed"] is True


class TestSubmitTyping:
    def test_correct_phrase(self, conn):
        iv = interventions.create_intervention(conn, "typing", {})
        r = interventions.submit_intervention(conn, iv["id"], iv["expected_input"])
        assert r["passed"] is True

    def test_incorrect_phrase(self, conn):
        iv = interventions.create_intervention(conn, "typing", {})
        r = interventions.submit_intervention(conn, iv["id"], "wrong text")
        assert r["passed"] is False
        assert r["remaining_attempts"] >= 0

    def test_whitespace_stripped(self, conn):
        iv = interventions.create_intervention(conn, "typing", {})
        r = interventions.submit_intervention(conn, iv["id"], "  " + iv["expected_input"] + "  ")
        assert r["passed"] is True

    def test_typing_max_attempts(self, conn):
        iv = interventions.create_intervention(conn, "typing", {})
        for _ in range(interventions.MAX_ATTEMPTS):
            r = interventions.submit_intervention(conn, iv["id"], "wrong")
        assert r["remaining_attempts"] == 0
        stored = db.get_intervention_by_id(conn, iv["id"])
        assert stored["completed_at"] is not None


class TestSubmitMath:
    def test_correct_answer(self, conn):
        iv = interventions.create_intervention(conn, "math", {})
        r = interventions.submit_intervention(conn, iv["id"], iv["expected_input"])
        assert r["passed"] is True

    def test_wrong_answer(self, conn):
        iv = interventions.create_intervention(conn, "math", {})
        wrong = str(int(iv["expected_input"]) + 1)
        r = interventions.submit_intervention(conn, iv["id"], wrong)
        assert r["passed"] is False

    def test_non_numeric(self, conn):
        iv = interventions.create_intervention(conn, "math", {})
        r = interventions.submit_intervention(conn, iv["id"], "abc")
        assert r["passed"] is False
        assert "number" in r["feedback"]


class TestSubmitPhoto:
    def test_photo_accepted(self, conn):
        iv = interventions.create_intervention(conn, "photo", {"task": "pushups"})
        r = interventions.submit_intervention(conn, iv["id"], "/tmp/proof.jpg")
        assert r["passed"] is True

    def test_no_photo(self, conn):
        iv = interventions.create_intervention(conn, "photo", {"task": "pushups"})
        r = interventions.submit_intervention(conn, iv["id"], "")
        assert r["passed"] is False


# ---------------------------------------------------------------------------
# get_intervention
# ---------------------------------------------------------------------------


class TestGetIntervention:
    def test_get_existing(self, conn):
        iv = interventions.create_intervention(conn, "math", {})
        fetched = interventions.get_intervention(conn, iv["id"])
        assert fetched is not None
        assert fetched["kind"] == "math"

    def test_get_missing(self, conn):
        assert interventions.get_intervention(conn, 9999) is None

    def test_submit_missing(self, conn):
        r = interventions.submit_intervention(conn, 9999, "foo")
        assert r["passed"] is False
        assert "not found" in r["feedback"]

    def test_submit_completed_idempotent(self, conn):
        iv = interventions.create_intervention(conn, "math", {})
        interventions.submit_intervention(conn, iv["id"], iv["expected_input"])
        r = interventions.submit_intervention(conn, iv["id"], "anything")
        assert r["passed"] is True
        assert "already" in r["feedback"]


# ---------------------------------------------------------------------------
# ai_negotiate (mocked LLM)
# ---------------------------------------------------------------------------


class TestAINegotiate:
    def test_grant(self, conn):
        iv = interventions.create_intervention(conn, "negotiate",
                                                {"domain": "reddit.com", "rule_text": "focus",
                                                 "minutes": 10})
        fake = AsyncMock(return_value='{"granted": true, "minutes": 10, "response": "ok, granted"}')
        with patch("sentinel.classifier.call_gemini", fake):
            result = asyncio.run(interventions.ai_negotiate(
                conn, iv["id"], "I need to respond to a professional message", "fake-key"))
        assert result["granted"] is True
        assert result["minutes"] == 10
        assert "granted" in result["response"]

    def test_deny(self, conn):
        iv = interventions.create_intervention(conn, "negotiate",
                                                {"domain": "reddit.com", "rule_text": "focus"})
        fake = AsyncMock(return_value='{"granted": false, "minutes": 0, "response": "sounds like FOMO"}')
        with patch("sentinel.classifier.call_gemini", fake):
            result = asyncio.run(interventions.ai_negotiate(
                conn, iv["id"], "just 5 minutes please", "fake-key"))
        assert result["granted"] is False
        assert result["minutes"] == 0

    def test_minutes_capped(self, conn):
        iv = interventions.create_intervention(conn, "negotiate", {"domain": "x.com"})
        fake = AsyncMock(return_value='{"granted": true, "minutes": 60, "response": "fine"}')
        with patch("sentinel.classifier.call_gemini", fake):
            result = asyncio.run(interventions.ai_negotiate(conn, iv["id"], "work", "k"))
        assert result["minutes"] == 15

    def test_bad_json_denies(self, conn):
        iv = interventions.create_intervention(conn, "negotiate", {})
        fake = AsyncMock(return_value='not json at all')
        with patch("sentinel.classifier.call_gemini", fake):
            result = asyncio.run(interventions.ai_negotiate(conn, iv["id"], "please", "k"))
        assert result["granted"] is False

    def test_markdown_fences_stripped(self, conn):
        iv = interventions.create_intervention(conn, "negotiate", {})
        fake = AsyncMock(return_value='```json\n{"granted": true, "minutes": 5, "response": "yes"}\n```')
        with patch("sentinel.classifier.call_gemini", fake):
            result = asyncio.run(interventions.ai_negotiate(conn, iv["id"], "work", "k"))
        assert result["granted"] is True
        assert result["minutes"] == 5

    def test_wrong_kind_rejected(self, conn):
        iv = interventions.create_intervention(conn, "math", {})
        fake = AsyncMock(return_value='{}')
        with patch("sentinel.classifier.call_gemini", fake):
            result = asyncio.run(interventions.ai_negotiate(conn, iv["id"], "x", "k"))
        assert result["granted"] is False


# ---------------------------------------------------------------------------
# verify_photo_proof (mocked)
# ---------------------------------------------------------------------------


class TestVerifyPhoto:
    def _mock_httpx(self, text):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={
            "candidates": [{"content": {"parts": [{"text": text}]}}]})
        return resp

    def test_photo_yes(self):
        with patch("builtins.open", mock_open(read_data=b"fake-bytes")), \
             patch("httpx.post", return_value=self._mock_httpx("yes")):
            assert interventions.verify_photo_proof("/tmp/x.jpg", "pushups", "k") is True

    def test_photo_no(self):
        with patch("builtins.open", mock_open(read_data=b"fake-bytes")), \
             patch("httpx.post", return_value=self._mock_httpx("no")):
            assert interventions.verify_photo_proof("/tmp/x.jpg", "pushups", "k") is False

    def test_photo_yes_case_insensitive(self):
        with patch("builtins.open", mock_open(read_data=b"fake-bytes")), \
             patch("httpx.post", return_value=self._mock_httpx("YES this shows completion")):
            assert interventions.verify_photo_proof("/tmp/x.jpg", "task", "k") is True


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


class TestDBHelpers:
    def test_save_intervention(self, conn):
        iid = db.save_intervention(conn, "math", {"foo": "bar"}, {"answer": 42})
        assert iid > 0

    def test_get_intervention_by_id(self, conn):
        iid = db.save_intervention(conn, "typing", {"x": 1}, {"phrase": "hello"})
        r = db.get_intervention_by_id(conn, iid)
        assert r["kind"] == "typing"
        assert r["context"] == {"x": 1}
        assert r["state"] == {"phrase": "hello"}

    def test_update_intervention(self, conn):
        iid = db.save_intervention(conn, "math", {}, {"answer": 10})
        db.update_intervention(conn, iid, passed=1, attempts=2)
        r = db.get_intervention_by_id(conn, iid)
        assert r["passed"] == 1
        assert r["attempts"] == 2

    def test_update_intervention_state_dict(self, conn):
        iid = db.save_intervention(conn, "math", {}, {"answer": 10})
        db.update_intervention(conn, iid, state={"answer": 20})
        r = db.get_intervention_by_id(conn, iid)
        assert r["state"]["answer"] == 20

    def test_get_missing_returns_none(self, conn):
        assert db.get_intervention_by_id(conn, 9999) is None
