"""macOS notification + dialog effectors via osascript.

Both functions return after the action; ``dialog`` blocks until the user
clicks a button (and returns which one), ``notify`` is fire-and-forget.

These are OS-level effectors the agent can call from any trigger:
- notify(title, body)         — banner notification, non-blocking
- dialog(title, body, buttons) — modal popup, blocking, returns clicked button

Use ``dialog`` for "are you sure?" friction. Use ``notify`` for soft nudges.
"""
from __future__ import annotations

import subprocess


def _quote_for_applescript(s: str) -> str:
    """Escape a string for safe AppleScript string literal interpolation."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, body: str = "", subtitle: str = "") -> dict:
    """Show a macOS banner notification. Non-blocking, fire-and-forget."""
    title_q = _quote_for_applescript(title or "Sentinel")
    body_q = _quote_for_applescript(body or "")
    parts = [f'display notification "{body_q}" with title "{title_q}"']
    if subtitle:
        parts[0] += f' subtitle "{_quote_for_applescript(subtitle)}"'
    try:
        r = subprocess.run(["osascript", "-e", parts[0]],
                           capture_output=True, timeout=5)
        return {"ok": r.returncode == 0,
                "stderr": r.stderr.decode("utf-8", "ignore") if r.returncode else None}
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}


def dialog(title: str, body: str = "", buttons: list[str] | None = None,
           default_button: str | None = None,
           timeout_seconds: int | None = None) -> dict:
    """Show a modal dialog. Blocks until the user clicks a button.

    Returns:
        {"ok": True, "button": "<clicked label>"} on click
        {"ok": False, "error": "user cancelled"|"timeout"|...} otherwise
    """
    buttons = buttons or ["OK"]
    title_q = _quote_for_applescript(title or "Sentinel")
    body_q = _quote_for_applescript(body or "")
    btns_q = ", ".join(f'"{_quote_for_applescript(b)}"' for b in buttons)
    script = f'display dialog "{body_q}" with title "{title_q}" buttons {{{btns_q}}}'
    if default_button and default_button in buttons:
        script += f' default button "{_quote_for_applescript(default_button)}"'
    if timeout_seconds is not None:
        script += f' giving up after {int(timeout_seconds)}'
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True,
            timeout=(timeout_seconds + 5) if timeout_seconds else 300)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}
    if r.returncode != 0:
        # User cancelled (Cmd+Period or hit Cancel) — osascript returns non-zero
        return {"ok": False, "error": "cancelled or dismissed",
                "stderr": r.stderr.strip()}
    # osascript prints "button returned:Foo, gave up:false"
    out = r.stdout.strip()
    button = None
    for part in out.split(", "):
        if part.startswith("button returned:"):
            button = part.split(":", 1)[1]
        if part.startswith("gave up:") and "true" in part:
            return {"ok": False, "error": "timeout"}
    return {"ok": True, "button": button}
