"""Tests for sentinel.encryption."""
import pytest
from sentinel import encryption, db
from pathlib import Path


@pytest.fixture
def conn():
    c = db.connect(Path(":memory:"))
    yield c
    c.close()


def test_encrypt_decrypt_roundtrip():
    password = "my-password"
    plaintext = "secret data"
    encrypted = encryption.encrypt_value(plaintext, password)
    decrypted = encryption.decrypt_value(encrypted, password)
    assert decrypted == plaintext


def test_encrypt_different_salts():
    """Same plaintext should produce different ciphertexts (random salt)."""
    pw = "pw"
    c1 = encryption.encrypt_value("same", pw)
    c2 = encryption.encrypt_value("same", pw)
    assert c1 != c2


def test_decrypt_wrong_password():
    encrypted = encryption.encrypt_value("data", "correct")
    with pytest.raises(ValueError):
        encryption.decrypt_value(encrypted, "wrong")


def test_decrypt_tampered():
    encrypted = encryption.encrypt_value("data", "pw")
    # Corrupt the ciphertext
    tampered = encrypted[:-4] + "XXXX"
    with pytest.raises(ValueError):
        encryption.decrypt_value(tampered, "pw")


def test_decrypt_invalid_base64():
    with pytest.raises(ValueError):
        encryption.decrypt_value("not-base64!!!", "pw")


def test_decrypt_too_short():
    with pytest.raises(ValueError):
        encryption.decrypt_value("c2hvcnQ=", "pw")  # "short" base64


def test_hash_password():
    hash_str, salt = encryption.hash_password("password123")
    assert hash_str
    assert len(salt) == 16


def test_verify_password_correct():
    hash_str, salt = encryption.hash_password("password123")
    assert encryption.verify_password("password123", hash_str, salt) is True


def test_verify_password_wrong():
    hash_str, salt = encryption.hash_password("password123")
    assert encryption.verify_password("wrong", hash_str, salt) is False


def test_hash_with_provided_salt():
    salt = b"1234567890123456"
    h1, _ = encryption.hash_password("pw", salt)
    h2, _ = encryption.hash_password("pw", salt)
    assert h1 == h2  # Deterministic with same salt


def test_encrypt_config_value(conn):
    encryption.encrypt_config_value(conn, "api_secret", "sk-12345", "pw")
    decrypted = encryption.decrypt_config_value(conn, "api_secret", "pw")
    assert decrypted == "sk-12345"


def test_decrypt_config_missing(conn):
    assert encryption.decrypt_config_value(conn, "nonexistent", "pw") is None


def test_encrypt_unicode():
    pw = "pw"
    plaintext = "unicode: 日本語 🎉"
    encrypted = encryption.encrypt_value(plaintext, pw)
    decrypted = encryption.decrypt_value(encrypted, pw)
    assert decrypted == plaintext


def test_encrypt_empty_string():
    pw = "pw"
    encrypted = encryption.encrypt_value("", pw)
    decrypted = encryption.decrypt_value(encrypted, pw)
    assert decrypted == ""


def test_derive_key_deterministic():
    salt = b"1234567890123456"
    k1 = encryption.derive_key("pw", salt)
    k2 = encryption.derive_key("pw", salt)
    assert k1 == k2
    assert len(k1) == 32
