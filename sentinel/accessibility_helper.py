"""Accessibility helpers — screen reader support, ARIA labels, keyboard hints."""


def aria_label(text: str, role: str = None) -> str:
    """Generate ARIA-label attributes."""
    if role:
        return f'aria-label="{text}" role="{role}"'
    return f'aria-label="{text}"'


def sr_only(text: str) -> str:
    """Return screen-reader-only text."""
    return f'<span class="sr-only">{text}</span>'


def keyboard_hint(key: str, description: str) -> str:
    """Format a keyboard shortcut hint."""
    return f"[{key}] {description}"


def alt_text_for_score(score: float) -> str:
    if score >= 90:
        return f"Excellent productivity score of {score}"
    if score >= 70:
        return f"Good productivity score of {score}"
    if score >= 50:
        return f"Average productivity score of {score}"
    return f"Low productivity score of {score}"


def describe_trend(trend: str) -> str:
    descriptions = {
        "improving": "Your productivity is improving, keep it up",
        "declining": "Your productivity is declining, consider what might be changing",
        "stable": "Your productivity is stable",
        "gaining": "Trending upward",
        "losing": "Trending downward",
    }
    return descriptions.get(trend, trend)


def describe_streak(streak: int, category: str = "goal") -> str:
    if streak == 0:
        return f"No current streak for {category}. Start today."
    if streak == 1:
        return f"One day streak for {category}. Keep going."
    return f"{streak} day streak for {category}. Amazing consistency."


def describe_percentage(percent: float, label: str = "") -> str:
    p = round(percent, 1)
    if label:
        return f"{label}: {p} percent"
    return f"{p} percent"


def describe_time_saved(minutes: float) -> str:
    if minutes < 1:
        return "Less than a minute"
    if minutes < 60:
        return f"{int(minutes)} minutes"
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if mins == 0:
        return f"{hours} hours"
    return f"{hours} hours and {mins} minutes"


def get_sr_css() -> str:
    """CSS for screen-reader-only content."""
    return """
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
"""


def get_skip_to_content_link() -> str:
    return '<a href="#main" class="skip-link">Skip to main content</a>'


def landmark(role: str, label: str, content: str) -> str:
    """Wrap content in a landmark."""
    return f'<section role="{role}" aria-label="{label}">{content}</section>'


def announce_to_sr(text: str, priority: str = "polite") -> str:
    """Generate HTML for ARIA live region announcements."""
    return f'<div role="status" aria-live="{priority}">{text}</div>'


def high_contrast_check(bg: str, fg: str) -> bool:
    """Simple high-contrast check (placeholder)."""
    # A real implementation would parse hex and compute WCAG contrast ratio
    return bg != fg
