"""Focus mode patterns: pomodoro, 52-17, flowmodoro, ultradian, animedoro, deep_work."""
from sentinel import scheduler

MODES = {
    "pomodoro": {"work": 25, "break": 5, "long_break": 15, "cycles": 4},
    "52_17": {"work": 52, "break": 17, "long_break": 17, "cycles": 1},
    "flowmodoro": {"work": 90, "break": 20, "long_break": 20, "cycles": 1},
    "ultradian": {"work": 90, "break": 20, "long_break": 20, "cycles": 1},
    "animedoro": {"work": 40, "break": 20, "long_break": 20, "cycles": 1},
    "deep_work": {"work": 120, "break": 30, "long_break": 30, "cycles": 1},
}


def list_modes() -> list[dict]:
    """Return all available focus modes."""
    return [{"name": name, **cfg} for name, cfg in MODES.items()]


def get_mode(name: str) -> dict:
    """Return a focus mode config. Raises ValueError if unknown."""
    cfg = MODES.get(name)
    if not cfg:
        raise ValueError(f"unknown focus mode: {name}")
    return dict(cfg)


def start_mode(conn, mode_name: str) -> dict:
    """Start a focus mode — reuses pomodoro scheduler with mode-specific durations."""
    cfg = get_mode(mode_name)
    state = scheduler.start_pomodoro(conn, work_minutes=cfg["work"],
                                     break_minutes=cfg["break"], cycles=cfg["cycles"])
    state["mode"] = mode_name
    return state


def current_mode_state(conn) -> dict:
    """Return current focus mode state or empty dict."""
    s = scheduler.get_pomodoro_state(conn)
    if not s:
        return {}
    return dict(s)


def stop_current_mode(conn):
    """Stop whatever focus mode is active."""
    scheduler.stop_pomodoro(conn)
