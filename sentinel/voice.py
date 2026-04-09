"""Voice notifications via macOS 'say' command."""
import subprocess
from . import db

VOICES = ["Samantha", "Alex", "Fred", "Victoria", "Daniel", "Karen"]


def speak(text: str, voice: str = "Samantha", rate: int = 200) -> bool:
    if not text:
        return False
    try:
        subprocess.run(
            ["say", "-v", voice, "-r", str(rate), text],
            timeout=30, check=False)
        return True
    except Exception:
        return False


def speak_async(text: str, voice: str = "Samantha") -> None:
    if not text:
        return
    try:
        subprocess.Popen(["say", "-v", voice, text])
    except Exception:
        pass


def list_voices() -> list[str]:
    try:
        r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=5)
        voices = []
        for line in (r.stdout or "").splitlines():
            parts = line.split()
            if parts:
                voices.append(parts[0])
        return voices or list(VOICES)
    except Exception:
        return list(VOICES)


def set_default_voice(conn, voice: str) -> None:
    db.set_config(conn, "voice_default", voice)


def get_default_voice(conn) -> str:
    return db.get_config(conn, "voice_default") or "Samantha"


def speak_notification(conn, title: str, message: str, voice: str = None) -> bool:
    v = voice or get_default_voice(conn)
    text = f"{title}. {message}" if title else message
    return speak(text, voice=v)
