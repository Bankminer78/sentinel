"""Session manager — track user sessions with the Sentinel app."""
import time, uuid


_sessions = {}  # session_id -> {user, started, last_seen}


def create_session(user: str = "default", ttl_hours: int = 24) -> str:
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "user": user,
        "started": time.time(),
        "last_seen": time.time(),
        "ttl": ttl_hours * 3600,
        "data": {},
    }
    return session_id


def get_session(session_id: str) -> dict:
    return _sessions.get(session_id)


def is_valid(session_id: str) -> bool:
    s = _sessions.get(session_id)
    if not s:
        return False
    if time.time() - s["started"] > s["ttl"]:
        del _sessions[session_id]
        return False
    return True


def touch_session(session_id: str):
    if session_id in _sessions:
        _sessions[session_id]["last_seen"] = time.time()


def destroy_session(session_id: str):
    if session_id in _sessions:
        del _sessions[session_id]


def list_sessions(user: str = None) -> list:
    now = time.time()
    active = []
    for sid, s in list(_sessions.items()):
        if now - s["started"] > s["ttl"]:
            del _sessions[sid]
            continue
        if user and s["user"] != user:
            continue
        active.append({**s, "id": sid})
    return active


def set_data(session_id: str, key: str, value):
    if session_id in _sessions:
        _sessions[session_id]["data"][key] = value


def get_data(session_id: str, key: str, default=None):
    s = _sessions.get(session_id)
    if not s:
        return default
    return s["data"].get(key, default)


def purge_expired() -> int:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["started"] > s["ttl"]]
    for sid in expired:
        del _sessions[sid]
    return len(expired)


def session_count() -> int:
    return len(_sessions)


def sessions_for_user(user: str) -> list:
    return list_sessions(user=user)


def extend_session(session_id: str, hours: int = 24) -> bool:
    if session_id not in _sessions:
        return False
    _sessions[session_id]["ttl"] = hours * 3600
    _sessions[session_id]["started"] = time.time()
    return True


def clear_all():
    _sessions.clear()
