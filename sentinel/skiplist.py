"""Domain skiplist — utility domains that should never be classified/blocked."""

SKIP_DOMAINS = {
    "google.com", "gmail.com", "docs.google.com", "drive.google.com", "calendar.google.com",
    "meet.google.com", "mail.google.com", "accounts.google.com", "cloud.google.com",
    "translate.google.com", "scholar.google.com", "aistudio.google.com",
    "github.com", "gist.github.com", "stackoverflow.com", "npmjs.com", "pypi.org",
    "claude.ai", "chatgpt.com", "openai.com", "platform.openai.com", "anthropic.com",
    "console.anthropic.com", "gemini.google.com", "perplexity.ai",
    "notion.so", "figma.com", "slack.com", "app.slack.com", "zoom.com", "app.zoom.us",
    "overleaf.com", "excalidraw.com", "linear.app", "vercel.com", "fly.io",
    "amazon.com", "aws.amazon.com", "stripe.com", "bankofamerica.com",
    "docs.aws.amazon.com", "console.cloud.google.com",
    "en.wikipedia.org", "arxiv.org", "kaggle.com", "leetcode.com",
    "developer.mozilla.org", "w3schools.com", "pytorch.org", "huggingface.co",
    "apple.com", "support.apple.com", "developer.apple.com",
    "microsoft.com", "learn.microsoft.com", "cursor.com",
    "booking.com", "airbnb.com", "united.com", "expedia.com",
    "getcoldturkey.com", "news.ycombinator.com", "ycombinator.com",
}

SKIP_PATTERNS = ("localhost", "127.0.0.1", "192.168.", "10.", "0.0.0.0")
SKIP_SUFFIXES = (".internal", ".local", ".fly.dev", ".vercel.app", ".genvidx.com")


def should_skip(domain: str) -> bool:
    """Check if domain should be skipped (never classified)."""
    if not domain:
        return True
    d = domain.lower()
    if d in SKIP_DOMAINS:
        return True
    if any(d.startswith(p) for p in SKIP_PATTERNS):
        return True
    if any(d.endswith(s) for s in SKIP_SUFFIXES):
        return True
    # Check parent domains: calendar.google.com -> google.com
    parts = d.split(".")
    for i in range(1, len(parts) - 1):
        if ".".join(parts[i:]) in SKIP_DOMAINS:
            return True
    return False
