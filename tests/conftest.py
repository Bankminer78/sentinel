"""Shared fixtures for Sentinel test suite."""

import pytest
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def conn():
    """In-memory SQLite database, initialized with schema."""
    from sentinel import db

    c = db.connect(Path(":memory:"))
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _reset_blocker():
    """Reset blocker module state between tests."""
    from sentinel import blocker
    blocker._blocked_domains.clear()
    blocker._blocked_apps.clear()
    yield
    blocker._blocked_domains.clear()
    blocker._blocked_apps.clear()


@pytest.fixture(autouse=True)
def _reset_classifier_cache():
    """Reset classifier cache between tests."""
    from sentinel import classifier
    classifier._cache.clear()
    yield
    classifier._cache.clear()


@pytest.fixture(autouse=True)
def _reset_monitor():
    """Reset monitor state between tests."""
    from sentinel import monitor
    monitor._running = False
    monitor._browser_url = ""
    monitor._current = {"app": "", "title": "", "url": "", "domain": "", "bundle_id": ""}
    yield
    monitor._running = False
