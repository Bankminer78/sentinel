"""Local encryption — keep sensitive data encrypted at rest."""
import hashlib, hmac, os, base64
from . import db


def derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000, dklen=32)


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def encrypt_value(plaintext: str, password: str) -> str:
    salt = os.urandom(16)
    key = derive_key(password, salt)
    ct = _xor(plaintext.encode("utf-8"), key)
    mac = hmac.new(key, ct, hashlib.sha256).digest()[:16]
    return base64.b64encode(salt + mac + ct).decode("ascii")


def decrypt_value(ciphertext: str, password: str) -> str:
    try:
        raw = base64.b64decode(ciphertext.encode("ascii"))
    except Exception as e:
        raise ValueError("invalid ciphertext") from e
    if len(raw) < 32:
        raise ValueError("invalid ciphertext")
    salt, mac, ct = raw[:16], raw[16:32], raw[32:]
    key = derive_key(password, salt)
    expected = hmac.new(key, ct, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(mac, expected):
        raise ValueError("bad password or tampered ciphertext")
    return _xor(ct, key).decode("utf-8")


def encrypt_config_value(conn, key: str, value: str, password: str):
    enc = encrypt_value(value, password)
    db.set_config(conn, f"enc:{key}", enc)


def decrypt_config_value(conn, key: str, password: str) -> str:
    raw = db.get_config(conn, f"enc:{key}")
    if raw is None:
        return None
    return decrypt_value(raw, password)


def hash_password(password: str, salt: bytes = None) -> tuple:
    if salt is None:
        salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return base64.b64encode(h).decode("ascii"), salt


def verify_password(password: str, hash_str: str, salt: bytes) -> bool:
    computed, _ = hash_password(password, salt)
    return hmac.compare_digest(computed, hash_str)
