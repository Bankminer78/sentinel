"""Spotify integration — track current music as productivity signal."""
import subprocess, time


def _osascript(cmd: str) -> str:
    try:
        r = subprocess.run(["osascript", "-e", cmd], capture_output=True,
                           text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def get_current_track() -> dict:
    """Current Spotify track via AppleScript."""
    name = _osascript('tell application "Spotify" to name of current track')
    artist = _osascript('tell application "Spotify" to artist of current track')
    album = _osascript('tell application "Spotify" to album of current track')
    state = _osascript('tell application "Spotify" to player state as string')
    if not name:
        return {}
    return {"name": name, "artist": artist, "album": album, "state": state}


def is_focus_music(track: dict, focus_keywords: list = None) -> bool:
    """Heuristic: check if track matches focus music patterns."""
    if not track:
        return False
    keywords = focus_keywords or [
        "lo-fi", "lofi", "focus", "study", "concentration",
        "deep work", "instrumental", "ambient", "classical",
        "brain.fm", "noise", "piano", "chillhop",
    ]
    text = f"{track.get('name', '')} {track.get('album', '')}".lower()
    return any(k in text for k in keywords)


def pause_spotify() -> bool:
    result = _osascript('tell application "Spotify" to pause')
    return True


def play_spotify() -> bool:
    result = _osascript('tell application "Spotify" to play')
    return True


async def log_spotify_activity(conn) -> dict:
    """Log current track, return info."""
    track = get_current_track()
    if track:
        focus = is_focus_music(track)
        return {**track, "is_focus": focus}
    return {}
