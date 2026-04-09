"""Tests for sentinel.i18n."""
import pytest
from sentinel import i18n, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_available_languages():
    langs = i18n.available_languages()
    assert "en" in langs
    assert len(langs) >= 2


def test_default_language(conn):
    # Default should be 'en' or similar
    lang = i18n.get_language(conn)
    assert lang  # Non-empty


def test_set_language(conn):
    i18n.set_language(conn, "es")
    assert i18n.get_language(conn) == "es"


def test_translate_default(conn):
    # Translating a known key should return something
    result = i18n.t(conn, "welcome")
    assert result  # Non-empty


def test_translate_unknown_key(conn):
    # Unknown key should return the key itself or empty
    result = i18n.t(conn, "nonexistent_key_xyz")
    assert result is not None


def test_add_translation():
    i18n.add_translation("en", "my_custom_key", "My Custom Value")
    # After adding, should be in translations
    from sentinel.i18n import TRANSLATIONS
    if "en" in TRANSLATIONS:
        assert TRANSLATIONS["en"].get("my_custom_key") == "My Custom Value"
