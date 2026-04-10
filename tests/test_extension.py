"""Validation tests for the Sentinel Chrome extension.

These are not JS unit tests — they verify that the MV3 bundle at
``extension/`` is structurally valid and self-consistent so it can be
loaded unpacked without surprises.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

EXT_DIR = Path(__file__).resolve().parent.parent / "extension"


@pytest.fixture(scope="module")
def manifest() -> dict:
    path = EXT_DIR / "manifest.json"
    assert path.exists(), f"manifest.json missing at {path}"
    with path.open() as f:
        return json.load(f)


def test_extension_dir_exists():
    assert EXT_DIR.is_dir(), f"extension directory missing: {EXT_DIR}"


def test_manifest_is_valid_json():
    path = EXT_DIR / "manifest.json"
    with path.open() as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_manifest_v3_structure(manifest):
    assert manifest.get("manifest_version") == 3
    assert manifest.get("name")
    assert manifest.get("version")
    assert "background" in manifest
    assert "content_scripts" in manifest
    assert "action" in manifest


def test_permissions(manifest):
    perms = manifest.get("permissions", [])
    for required in ("activeTab", "storage", "tabs"):
        assert required in perms, f"missing permission: {required}"


def test_host_permissions_include_localhost_and_all_urls(manifest):
    hosts = manifest.get("host_permissions", [])
    assert "<all_urls>" in hosts
    assert any("localhost:9849" in h for h in hosts)


def test_background_script_reference_is_valid(manifest):
    bg = manifest.get("background", {})
    worker = bg.get("service_worker")
    assert worker, "background.service_worker missing"
    assert (EXT_DIR / worker).exists(), f"background script missing: {worker}"


def test_content_script_matches_all_urls(manifest):
    scripts = manifest.get("content_scripts", [])
    assert scripts, "no content_scripts defined"
    found = False
    for entry in scripts:
        if "<all_urls>" in entry.get("matches", []):
            for js in entry.get("js", []):
                assert (EXT_DIR / js).exists(), f"content script missing: {js}"
            found = True
    assert found, "no content_script with <all_urls> matches"


def test_action_popup_and_icons_exist(manifest):
    action = manifest.get("action", {})
    popup = action.get("default_popup")
    assert popup and (EXT_DIR / popup).exists(), f"popup missing: {popup}"
    icons = action.get("default_icon", {})
    for size, rel in icons.items():
        assert (EXT_DIR / rel).exists(), f"icon missing: {rel}"


def test_top_level_icons_exist(manifest):
    for size, rel in manifest.get("icons", {}).items():
        assert (EXT_DIR / rel).exists(), f"top-level icon missing: {rel}"


def test_required_files_present():
    for name in (
        "manifest.json",
        "background.js",
        "content.js",
        "popup.html",
        "popup.js",
        "icon16.png",
        "icon48.png",
        "icon128.png",
        "README.md",
    ):
        assert (EXT_DIR / name).exists(), f"missing file: {name}"


def test_popup_html_references_popup_js():
    html = (EXT_DIR / "popup.html").read_text()
    assert "popup.js" in html


def test_background_posts_to_activity_endpoint():
    bg = (EXT_DIR / "background.js").read_text()
    assert "/activity" in bg
    # Accept either localhost:9849 or 127.0.0.1:9849 — both resolve to the
    # same daemon. The 0.2.0 release switched to 127.0.0.1 for consistency
    # with the daemon's bind address.
    assert "localhost:9849" in bg or "127.0.0.1:9849" in bg


def test_background_sends_correct_activity_schema():
    """The 0.1.0 extension sent {url, tab_id, ts}; the daemon expects
    {url, title, domain}. Ensure the 0.2.0 fix is in place — the
    background script must send the correct fields."""
    bg = (EXT_DIR / "background.js").read_text()
    # Must extract domain client-side
    assert "extractDomain" in bg or "new URL" in bg
    # Must include domain in the POST body
    assert '"domain"' in bg or "domain," in bg or "domain:" in bg
    # Must include title in the POST body
    assert '"title"' in bg or "title," in bg or "title:" in bg


def test_content_script_has_overlay_and_countdown():
    content = (EXT_DIR / "content.js").read_text()
    assert "sentinel-overlay" in content
    assert "2147483647" in content
    assert "blockConfirmed" in content
    assert "blockCancelled" in content


def test_total_js_under_400_lines():
    total = 0
    for name in ("background.js", "content.js", "popup.js"):
        total += len((EXT_DIR / name).read_text().splitlines())
    assert total < 400, f"JS total is {total} lines, expected < 400"
