"""Tests for sentinel.pwa."""
import pytest
import json
from sentinel import pwa


def test_manifest_valid_json():
    manifest = pwa.get_manifest()
    data = json.loads(manifest)
    assert data["name"]
    assert data["short_name"]


def test_manifest_has_icons():
    manifest = json.loads(pwa.get_manifest())
    assert "icons" in manifest
    assert len(manifest["icons"]) >= 2


def test_manifest_has_colors():
    manifest = json.loads(pwa.get_manifest())
    assert "theme_color" in manifest
    assert "background_color" in manifest


def test_manifest_has_start_url():
    manifest = json.loads(pwa.get_manifest())
    assert manifest["start_url"] == "/"


def test_manifest_has_shortcuts():
    manifest = json.loads(pwa.get_manifest())
    assert "shortcuts" in manifest
    assert len(manifest["shortcuts"]) > 0


def test_service_worker_js():
    sw = pwa.get_service_worker_js()
    assert "CACHE_NAME" in sw
    assert "install" in sw
    assert "fetch" in sw


def test_offline_html():
    html = pwa.get_offline_html()
    assert "<!DOCTYPE html>" in html
    assert "offline" in html.lower()


def test_install_prompt_html():
    html = pwa.get_install_prompt_html()
    assert "install" in html.lower()
    assert "manifest" in html.lower()
