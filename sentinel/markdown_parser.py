"""Simple markdown-to-HTML converter for journal entries and reflections."""
import re


def parse_markdown(text: str) -> str:
    """Convert markdown to HTML. Simple implementation, no dependencies."""
    if not text:
        return ""
    html = text
    # Escape HTML
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Code blocks
    html = re.sub(r"```(.*?)```", r"<pre><code>\1</code></pre>", html, flags=re.DOTALL)
    # Inline code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    # Headers
    for level in range(6, 0, -1):
        prefix = "#" * level
        html = re.sub(f"^{prefix} (.+)$",
                       f"<h{level}>\\1</h{level}>", html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", html)
    # Italic
    html = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", html)
    html = re.sub(r"_([^_]+)_", r"<em>\1</em>", html)
    # Links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)
    # Lists
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*?</li>\n?)+", lambda m: f"<ul>{m.group(0)}</ul>", html)
    # Paragraphs
    lines = html.split("\n\n")
    html = "\n\n".join(f"<p>{l}</p>" if not l.startswith("<") else l
                        for l in lines if l.strip())
    return html


def strip_markdown(text: str) -> str:
    """Remove markdown formatting, return plain text."""
    if not text:
        return ""
    # Remove code blocks
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove headers
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # Remove links
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text.strip()


def extract_links(text: str) -> list:
    """Extract all markdown links from text."""
    return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)


def extract_headers(text: str) -> list:
    """Extract all headers with their levels."""
    headers = []
    for match in re.finditer(r"^(#+)\s+(.+)$", text, re.MULTILINE):
        level = len(match.group(1))
        text_content = match.group(2)
        headers.append({"level": level, "text": text_content})
    return headers


def word_count(text: str) -> int:
    stripped = strip_markdown(text)
    return len([w for w in stripped.split() if w])


def count_links(text: str) -> int:
    return len(extract_links(text))


def has_code_block(text: str) -> bool:
    return "```" in text


def estimate_read_time_minutes(text: str, wpm: int = 200) -> float:
    words = word_count(text)
    return round(words / wpm, 1)
