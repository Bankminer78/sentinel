"""Theme management — UI theme configuration."""
from . import db


THEMES = {
    "dark": {
        "name": "Dark",
        "bg": "#18181b",
        "bg_secondary": "#27272a",
        "bg_tertiary": "#3f3f46",
        "text": "#fafafa",
        "text_muted": "#a1a1aa",
        "primary": "#ef4444",
        "secondary": "#1d4ed8",
        "success": "#4d7c0f",
        "warning": "#d97706",
        "error": "#dc2626",
    },
    "light": {
        "name": "Light",
        "bg": "#ffffff",
        "bg_secondary": "#f4f4f5",
        "bg_tertiary": "#e4e4e7",
        "text": "#18181b",
        "text_muted": "#71717a",
        "primary": "#dc2626",
        "secondary": "#1d4ed8",
        "success": "#15803d",
        "warning": "#b45309",
        "error": "#b91c1c",
    },
    "high_contrast": {
        "name": "High Contrast",
        "bg": "#000000",
        "bg_secondary": "#0a0a0a",
        "bg_tertiary": "#1a1a1a",
        "text": "#ffffff",
        "text_muted": "#cccccc",
        "primary": "#ff0000",
        "secondary": "#00ffff",
        "success": "#00ff00",
        "warning": "#ffff00",
        "error": "#ff0000",
    },
    "solarized_dark": {
        "name": "Solarized Dark",
        "bg": "#002b36",
        "bg_secondary": "#073642",
        "bg_tertiary": "#586e75",
        "text": "#839496",
        "text_muted": "#586e75",
        "primary": "#dc322f",
        "secondary": "#268bd2",
        "success": "#859900",
        "warning": "#b58900",
        "error": "#dc322f",
    },
    "nord": {
        "name": "Nord",
        "bg": "#2e3440",
        "bg_secondary": "#3b4252",
        "bg_tertiary": "#434c5e",
        "text": "#eceff4",
        "text_muted": "#d8dee9",
        "primary": "#bf616a",
        "secondary": "#81a1c1",
        "success": "#a3be8c",
        "warning": "#ebcb8b",
        "error": "#bf616a",
    },
}


def list_themes() -> list:
    return [{"id": k, **v} for k, v in THEMES.items()]


def get_theme(theme_id: str) -> dict:
    return THEMES.get(theme_id)


def set_current_theme(conn, theme_id: str) -> bool:
    if theme_id not in THEMES:
        return False
    db.set_config(conn, "theme", theme_id)
    return True


def get_current_theme(conn) -> str:
    return db.get_config(conn, "theme", "dark") or "dark"


def get_current_theme_data(conn) -> dict:
    tid = get_current_theme(conn)
    return {"id": tid, **THEMES.get(tid, THEMES["dark"])}


def generate_css(theme_id: str = "dark") -> str:
    theme = THEMES.get(theme_id, THEMES["dark"])
    css = ":root {\n"
    for key, value in theme.items():
        if key != "name":
            css += f"  --{key.replace('_', '-')}: {value};\n"
    css += "}\n"
    return css


def theme_count() -> int:
    return len(THEMES)
