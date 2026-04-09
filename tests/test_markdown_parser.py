"""Tests for sentinel.markdown_parser."""
import pytest
from sentinel import markdown_parser as mp


def test_parse_empty():
    assert mp.parse_markdown("") == ""


def test_parse_bold():
    html = mp.parse_markdown("This is **bold**")
    assert "<strong>bold</strong>" in html


def test_parse_italic():
    html = mp.parse_markdown("This is *italic*")
    assert "<em>italic</em>" in html


def test_parse_headers():
    html = mp.parse_markdown("# Title")
    assert "<h1>Title</h1>" in html


def test_parse_h2():
    html = mp.parse_markdown("## Subtitle")
    assert "<h2>Subtitle</h2>" in html


def test_parse_inline_code():
    html = mp.parse_markdown("Use `print()` function")
    assert "<code>print()</code>" in html


def test_parse_link():
    html = mp.parse_markdown("Visit [GitHub](https://github.com)")
    assert '<a href="https://github.com">GitHub</a>' in html


def test_strip_markdown():
    text = "**Bold** and *italic* and `code`"
    plain = mp.strip_markdown(text)
    assert "Bold" in plain
    assert "**" not in plain


def test_strip_headers():
    assert mp.strip_markdown("# Title") == "Title"


def test_extract_links():
    links = mp.extract_links("[one](url1) and [two](url2)")
    assert len(links) == 2


def test_extract_headers():
    text = "# H1\n## H2\n### H3"
    headers = mp.extract_headers(text)
    assert len(headers) == 3
    assert headers[0]["level"] == 1


def test_word_count():
    assert mp.word_count("hello world") == 2
    assert mp.word_count("# Title with four words") == 4  # "Title with four words" = 4


def test_count_links():
    text = "[a](x) [b](y) [c](z)"
    assert mp.count_links(text) == 3


def test_has_code_block():
    assert mp.has_code_block("```python\nprint(1)\n```") is True
    assert mp.has_code_block("just text") is False


def test_estimate_read_time():
    # ~200 words should be 1 minute
    text = " ".join(["word"] * 200)
    assert mp.estimate_read_time_minutes(text) == 1.0


def test_parse_code_block():
    html = mp.parse_markdown("```\ncode\n```")
    assert "<pre>" in html or "<code>" in html
