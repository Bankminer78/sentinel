"""Voice input — speech-to-text for rule creation."""
import subprocess
import tempfile
import os
from . import db, classifier


def is_speech_available() -> bool:
    """Check if speech recognition is available."""
    for cmd in ("whisper", "rec", "sox"):
        try:
            r = subprocess.run(
                ["which", cmd], capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and (r.stdout or "").strip():
                return True
        except Exception:
            continue
    return False


def transcribe_audio_file(path: str) -> str:
    """Transcribe an audio file using whisper or macOS dictation."""
    if not path or not os.path.exists(path):
        return ""
    try:
        r = subprocess.run(
            ["whisper", path, "--model", "base", "--output_format", "txt"],
            capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            return (r.stdout or "").strip()
    except Exception:
        pass
    return ""


def record_and_transcribe(duration: int = 5) -> str:
    """Record from mic for N seconds, then transcribe."""
    if duration <= 0:
        return ""
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        subprocess.run(
            ["rec", "-q", tmp, "trim", "0", str(duration)],
            timeout=duration + 10, check=False)
        return transcribe_audio_file(tmp)
    except Exception:
        return ""
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


async def voice_add_rule(conn, api_key: str) -> str:
    """Record voice -> transcribe -> create rule via LLM parse."""
    text = record_and_transcribe(duration=5)
    if not text:
        return ""
    parsed = {}
    if api_key:
        try:
            parsed = await classifier.parse_rule(api_key, text) or {}
        except Exception:
            parsed = {}
    db.add_rule(conn, text, parsed=parsed)
    return text
