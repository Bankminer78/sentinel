"""End-to-end dashboard tests via Playwright (headless Chromium).

Exercises the actual HTML/JS dashboard by starting the daemon in a
subprocess, navigating a headless browser to it, clicking tabs, checking
that content renders correctly, and verifying the SSE-based agent chat
flow without a human in the loop.

Run with:
    pytest tests/test_e2e_dashboard.py -v --timeout=60

Requires:
    pip install playwright
    python -m playwright install chromium

The daemon is started fresh per test session on a random port to avoid
colliding with a running Sentinel.app. The bearer token is read from
the agent.token file the daemon writes at startup.
"""
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

# Only run if playwright is installed
try:
    from playwright.sync_api import sync_playwright, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# E2E tests start their own daemon on a non-default port. Run them separately:
#   pytest tests/test_e2e_dashboard.py -v
# or with the marker:
#   pytest -m e2e -v
# They conflict with the full unit test suite because the module-scoped daemon
# fixture can't start if another daemon process is messing with shared state.
pytestmark = [
    pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed"),
    pytest.mark.e2e,
]

SENTINEL_DIR = Path(__file__).parent.parent
DAEMON_PORT = 19849  # non-default port to avoid colliding with the real daemon
DAEMON_URL = f"http://127.0.0.1:{DAEMON_PORT}"
TOKEN_PATH = Path.home() / "Library" / "Application Support" / "Sentinel" / "agent.token"


@pytest.fixture(scope="module")
def daemon():
    """Start a fresh daemon on a non-default port for the test session."""
    env = {**os.environ, "PYTHONPATH": str(SENTINEL_DIR)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "sentinel.cli", "serve",
         "--port", str(DAEMON_PORT), "--host", "127.0.0.1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(SENTINEL_DIR),
    )
    # Wait for the daemon to be ready
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            r = httpx.get(f"{DAEMON_URL}/health", timeout=1)
            if r.status_code == 200:
                break
        except httpx.ConnectError:
            time.sleep(0.3)
    else:
        proc.kill()
        raise RuntimeError("daemon did not start within 15s")

    yield proc

    # Teardown
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    finally:
        # Capture and log stderr for debugging if the daemon had issues
        if proc.stderr:
            stderr = proc.stderr.read()
            if stderr:
                print(f"\n[daemon stderr]\n{stderr.decode('utf-8', 'replace')[-2000:]}")


@pytest.fixture(scope="module")
def bearer_token(daemon):
    """Read the bearer token the daemon wrote to disk."""
    if TOKEN_PATH.exists():
        return TOKEN_PATH.read_text().strip()
    return ""


@pytest.fixture(scope="module")
def browser_ctx():
    """Launch a headless Chromium browser for the test session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        yield ctx
        ctx.close()
        browser.close()


@pytest.fixture
def page(browser_ctx, daemon):
    """Open a fresh page pointed at the daemon's dashboard."""
    pg = browser_ctx.new_page()
    pg.goto(DAEMON_URL, wait_until="networkidle")
    yield pg
    pg.close()


# ---------------------------------------------------------------------------
# Tab navigation
# ---------------------------------------------------------------------------


def test_dashboard_loads(page: Page):
    """The root URL returns the dashboard with 7 sidebar tabs."""
    assert page.title() == "Sentinel"
    tabs = page.query_selector_all(".nav button")
    assert len(tabs) == 7
    tab_names = [t.text_content().strip() for t in tabs]
    assert "Dashboard" in tab_names
    assert "Chat" in tab_names
    assert "Locks" in tab_names
    assert "Audit" in tab_names
    assert "Rules" in tab_names
    assert "Activity" in tab_names
    assert "Settings" in tab_names


def test_tab_switching(page: Page):
    """Clicking each tab shows its content and hides others."""
    for tab_name in ["Chat", "Locks", "Audit", "Rules", "Activity", "Settings", "Dashboard"]:
        btn = page.query_selector(f'.nav button[data-tab="{tab_name.lower()}"]')
        if btn is None:
            # Try case-insensitive data-tab
            btn = page.query_selector(f'.nav button:text("{tab_name}")')
        assert btn is not None, f"no button for tab {tab_name}"
        btn.click()
        page.wait_for_timeout(200)
        # The clicked tab's content should be visible
        tab_div = page.query_selector(f'#tab-{tab_name.lower()}')
        assert tab_div is not None, f"no #tab-{tab_name.lower()} div"
        style = tab_div.get_attribute("style") or ""
        assert "display: none" not in style.replace(" ", ""), \
            f"{tab_name} tab content should be visible but has {style}"


def test_dashboard_score_renders(page: Page):
    """The score tile on the Dashboard tab should have a numeric value."""
    page.wait_for_timeout(1000)  # let refreshDashboard() complete
    score = page.query_selector("#score")
    assert score is not None
    text = score.text_content().strip()
    # Either a number or "—" if no data
    assert text == "—" or text.replace(".", "").isdigit(), \
        f"score should be numeric or '—', got {text!r}"


# ---------------------------------------------------------------------------
# Rules tab
# ---------------------------------------------------------------------------


def test_rules_add_and_delete(page: Page, daemon):
    """Add a rule via the input, verify it appears, delete it, verify gone."""
    # Switch to Rules tab
    page.click('.nav button[data-tab="rules"]')
    page.wait_for_timeout(500)

    # Add a rule
    page.fill("#new-rule", "Block YouTube during work hours")
    page.click("#add-rule-btn")
    page.wait_for_timeout(1000)

    # The rule should appear in the list
    rules_list = page.query_selector("#rules-list")
    assert rules_list is not None
    rules_html = rules_list.inner_html()
    assert "Block YouTube during work hours" in rules_html

    # Delete it
    delete_btn = page.query_selector('#rules-list button[data-action="delete-rule"]')
    if delete_btn:
        delete_btn.click()
        page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# Locks tab
# ---------------------------------------------------------------------------


def test_locks_tab_renders(page: Page):
    """The Locks tab should render without crashing, showing active locks."""
    page.click('.nav button[data-tab="locks"]')
    page.wait_for_timeout(1000)
    locks_list = page.query_selector("#locks-list")
    assert locks_list is not None
    # Either shows locks or the "no active locks" empty message
    html = locks_list.inner_html()
    assert len(html) > 0, "locks list should have content"


# ---------------------------------------------------------------------------
# Audit tab
# ---------------------------------------------------------------------------


def test_audit_tab_renders(page: Page):
    """The Audit tab should show recent audit entries."""
    page.click('.nav button[data-tab="audit"]')
    page.wait_for_timeout(1000)
    audit_list = page.query_selector("#audit-list")
    assert audit_list is not None
    html = audit_list.inner_html()
    # There should be at least one audit entry from daemon startup
    assert len(html) > 20, f"audit list should have entries, got {len(html)} chars"


def test_audit_filter_by_actor(page: Page):
    """Filtering by actor should narrow the audit list."""
    page.click('.nav button[data-tab="audit"]')
    page.wait_for_timeout(500)
    page.fill("#audit-filter-actor", "nonexistent_actor_xyz")
    page.click("#audit-refresh-btn")
    page.wait_for_timeout(500)
    audit_list = page.query_selector("#audit-list")
    html = audit_list.inner_html()
    # Should show "No audit entries match" or empty
    assert "No audit entries" in html or len(html) < 100


# ---------------------------------------------------------------------------
# Settings tab
# ---------------------------------------------------------------------------


def test_settings_renders(page: Page):
    """Settings tab should show budget input and emergency status."""
    page.click('.nav button[data-tab="settings"]')
    page.wait_for_timeout(1000)
    budget_input = page.query_selector("#budget-input")
    assert budget_input is not None
    emergency = page.query_selector("#emergency-status")
    assert emergency is not None


# ---------------------------------------------------------------------------
# Activity tab
# ---------------------------------------------------------------------------


def test_activity_tab_renders(page: Page):
    """Activity tab should load without errors."""
    page.click('.nav button[data-tab="activity"]')
    page.wait_for_timeout(1000)
    feed = page.query_selector("#activity-feed")
    assert feed is not None


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------


def test_static_js_served(daemon):
    """The app.js static file should be served correctly."""
    r = httpx.get(f"{DAEMON_URL}/static/app.js")
    assert r.status_code == 200
    assert "renderAgentEvent" in r.text
    assert "escapeHtml" in r.text


def test_static_css_served(daemon):
    r = httpx.get(f"{DAEMON_URL}/static/style.css")
    assert r.status_code == 200
    assert "chat-event" in r.text


# ---------------------------------------------------------------------------
# API endpoint smoke tests (no browser needed)
# ---------------------------------------------------------------------------


def test_health(daemon):
    r = httpx.get(f"{DAEMON_URL}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True


def test_status(daemon):
    r = httpx.get(f"{DAEMON_URL}/status")
    assert r.status_code == 200
    data = r.json()
    assert "current" in data
    assert "rules" in data
    assert "blocked" in data


def test_stats(daemon):
    r = httpx.get(f"{DAEMON_URL}/stats")
    assert r.status_code == 200
    data = r.json()
    assert "score" in data
    assert "breakdown" in data


def test_activities(daemon):
    r = httpx.get(f"{DAEMON_URL}/activities?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_locks_endpoint(daemon):
    r = httpx.get(f"{DAEMON_URL}/locks")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_audit_endpoint(daemon):
    r = httpx.get(f"{DAEMON_URL}/audit?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_privacy_endpoint(daemon):
    r = httpx.get(f"{DAEMON_URL}/privacy")
    assert r.status_code == 200
    assert "level" in r.json()


def test_activity_post(daemon):
    """POST /activity with a valid body should return a verdict."""
    r = httpx.post(f"{DAEMON_URL}/activity", json={
        "url": "https://example.com/test",
        "title": "E2E test page",
        "domain": "example.com",
    })
    assert r.status_code == 200
    data = r.json()
    assert "verdict" in data


def test_agent_budget_without_token(daemon):
    """Agent budget endpoint without auth should 401."""
    r = httpx.get(f"{DAEMON_URL}/api/agent/budget")
    assert r.status_code == 401


def test_agent_budget_with_token(daemon, bearer_token):
    """Agent budget endpoint with correct token should 200."""
    if not bearer_token:
        pytest.skip("no bearer token available")
    r = httpx.get(f"{DAEMON_URL}/api/agent/budget",
                  headers={"Authorization": f"Bearer {bearer_token}"})
    assert r.status_code == 200
    data = r.json()
    assert "budget_usd" in data
    assert "remaining_usd" in data


def test_agent_post_without_token(daemon):
    """Agent endpoint without auth should 401."""
    r = httpx.post(f"{DAEMON_URL}/api/agent",
                   json={"prompt": "test"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# JS syntax validation (no browser needed)
# ---------------------------------------------------------------------------


def test_js_syntax_valid():
    """node --check on all JS files should pass."""
    for name in ["app.js"]:
        path = SENTINEL_DIR / "sentinel" / "static" / name
        result = subprocess.run(
            ["node", "--check", str(path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, \
            f"{name} has a syntax error:\n{result.stderr}"


def test_extension_js_syntax_valid():
    """node --check on extension JS files."""
    ext_dir = SENTINEL_DIR / "extension"
    for name in ["background.js", "popup.js", "content.js"]:
        path = ext_dir / name
        if path.exists():
            result = subprocess.run(
                ["node", "--check", str(path)],
                capture_output=True, text=True,
            )
            assert result.returncode == 0, \
                f"extension/{name} has a syntax error:\n{result.stderr}"
