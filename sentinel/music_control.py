"""Music control — pause/play/change music during focus sessions."""
import subprocess

APPS = ["Spotify", "Music", "iTunes"]


def _osascript(cmd: str) -> str:
    try:
        r = subprocess.run(["osascript", "-e", cmd], capture_output=True,
                           text=True, timeout=3)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def get_current_player() -> str:
    """Returns the name of the currently-playing app, if any."""
    for app in APPS:
        state = _osascript(f'tell application "{app}" to player state as string')
        if state == "playing":
            return app
    return None


def play(app: str = "Spotify") -> bool:
    _osascript(f'tell application "{app}" to play')
    return True


def pause(app: str = "Spotify") -> bool:
    _osascript(f'tell application "{app}" to pause')
    return True


def next_track(app: str = "Spotify") -> bool:
    _osascript(f'tell application "{app}" to next track')
    return True


def previous_track(app: str = "Spotify") -> bool:
    _osascript(f'tell application "{app}" to previous track')
    return True


def get_now_playing(app: str = "Spotify") -> dict:
    name = _osascript(f'tell application "{app}" to name of current track')
    artist = _osascript(f'tell application "{app}" to artist of current track')
    if not name:
        return {}
    return {"app": app, "name": name, "artist": artist}


def set_volume(app: str, level: int) -> bool:
    level = max(0, min(100, level))
    _osascript(f'tell application "{app}" to set sound volume to {level}')
    return True


def focus_music_mode(conn) -> dict:
    """Pause all music players."""
    paused = []
    for app in APPS:
        state = _osascript(f'tell application "{app}" to player state as string')
        if state == "playing":
            pause(app)
            paused.append(app)
    return {"paused": paused}


def rest_music_mode(conn) -> dict:
    """Resume music."""
    resumed = []
    for app in APPS:
        state = _osascript(f'tell application "{app}" to player state as string')
        if state == "paused":
            play(app)
            resumed.append(app)
    return {"resumed": resumed}
