"""Ambient sounds — focus music and environment sounds."""
import subprocess, time


# Curated ambient sound URLs (royalty-free or YouTube Music/Spotify playlist IDs)
AMBIENT_SOUNDS = {
    "rain": {"name": "Rain", "type": "nature"},
    "forest": {"name": "Forest", "type": "nature"},
    "ocean": {"name": "Ocean waves", "type": "nature"},
    "cafe": {"name": "Coffee shop", "type": "environment"},
    "library": {"name": "Library", "type": "environment"},
    "fireplace": {"name": "Fireplace", "type": "environment"},
    "brown_noise": {"name": "Brown noise", "type": "noise"},
    "white_noise": {"name": "White noise", "type": "noise"},
    "pink_noise": {"name": "Pink noise", "type": "noise"},
    "lofi": {"name": "Lo-Fi beats", "type": "music"},
    "classical": {"name": "Classical music", "type": "music"},
    "ambient": {"name": "Ambient electronic", "type": "music"},
}


_current_sound = None
_start_time = None


def list_sounds() -> list:
    return [{"id": k, **v} for k, v in AMBIENT_SOUNDS.items()]


def list_by_type(sound_type: str) -> list:
    return [{"id": k, **v} for k, v in AMBIENT_SOUNDS.items() if v["type"] == sound_type]


def play_sound(sound_id: str) -> bool:
    global _current_sound, _start_time
    if sound_id not in AMBIENT_SOUNDS:
        return False
    _current_sound = sound_id
    _start_time = time.time()
    # Open a YouTube search for the sound in the default browser
    query = AMBIENT_SOUNDS[sound_id]["name"] + " 1 hour"
    try:
        subprocess.run(["open", f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"],
                       timeout=5, check=False)
        return True
    except Exception:
        return False


def stop_sound() -> bool:
    global _current_sound, _start_time
    _current_sound = None
    _start_time = None
    return True


def current() -> dict:
    if not _current_sound:
        return {}
    elapsed = time.time() - _start_time if _start_time else 0
    return {
        "sound_id": _current_sound,
        **AMBIENT_SOUNDS[_current_sound],
        "elapsed_seconds": int(elapsed),
    }


def is_playing() -> bool:
    return _current_sound is not None


def recommend_for_task(task_type: str) -> str:
    """Recommend ambient sound for a task type."""
    recs = {
        "coding": "lofi",
        "writing": "classical",
        "reading": "library",
        "studying": "brown_noise",
        "relaxing": "forest",
        "sleeping": "rain",
    }
    return recs.get(task_type, "lofi")
