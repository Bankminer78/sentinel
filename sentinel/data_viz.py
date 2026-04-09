"""ASCII data visualization for terminal output."""


def bar_chart(data: dict, width: int = 40, sort: bool = True) -> str:
    """Horizontal bar chart. data: {label: value}."""
    if not data:
        return "(no data)"
    items = sorted(data.items(), key=lambda x: x[1], reverse=True) if sort else list(data.items())
    max_val = max(v for _, v in items) if items else 1
    max_label = max(len(str(k)) for k, _ in items)
    lines = []
    for label, value in items:
        bar_len = int((value / max_val) * width) if max_val > 0 else 0
        bar = "█" * bar_len
        lines.append(f"{str(label):<{max_label}} │{bar} {value}")
    return "\n".join(lines)


def line_chart(values: list, width: int = 60, height: int = 10) -> str:
    """Simple ASCII line chart."""
    if not values:
        return "(no data)"
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return "─" * width
    # Sample to width
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values
    # Normalize to height rows
    grid = [[" "] * len(sampled) for _ in range(height)]
    for i, v in enumerate(sampled):
        row = int((1 - (v - min_v) / (max_v - min_v)) * (height - 1))
        grid[row][i] = "•"
    lines = []
    for row in grid:
        lines.append("".join(row))
    return "\n".join(lines)


def sparkline(values: list) -> str:
    """One-line unicode sparkline."""
    if not values:
        return ""
    chars = "▁▂▃▄▅▆▇█"
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return chars[0] * len(values)
    return "".join(chars[int((v - min_v) / (max_v - min_v) * (len(chars) - 1))] for v in values)


def heatmap(data: dict, cols: int = 7) -> str:
    """Heatmap grid (e.g., for weekly activity)."""
    if not data:
        return "(no data)"
    values = list(data.values())
    if not values:
        return "(no data)"
    max_v = max(values) or 1
    chars = " ░▒▓█"
    lines = []
    items = list(data.items())
    for i in range(0, len(items), cols):
        row = items[i:i + cols]
        line = ""
        labels = ""
        for label, v in row:
            c = chars[int((v / max_v) * (len(chars) - 1))]
            line += c + c
            labels += str(label)[:3].ljust(3)
        lines.append(line)
    return "\n".join(lines)


def table(rows: list, columns: list) -> str:
    """Format a simple table."""
    if not rows:
        return "(empty)"
    widths = {c: len(c) for c in columns}
    for row in rows:
        for c in columns:
            v = str(row.get(c, ""))
            widths[c] = max(widths[c], len(v))
    header = " | ".join(c.ljust(widths[c]) for c in columns)
    separator = "-+-".join("-" * widths[c] for c in columns)
    body = []
    for row in rows:
        body.append(" | ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))
    return "\n".join([header, separator] + body)


def progress_bar(value: float, total: float, width: int = 30) -> str:
    """Text progress bar."""
    if total <= 0:
        return "[" + " " * width + "]"
    pct = min(1.0, value / total)
    filled = int(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {int(pct * 100)}%"


def stem_leaf(values: list) -> str:
    """Simple stem-and-leaf plot."""
    if not values:
        return "(empty)"
    stems = {}
    for v in sorted(values):
        stem = int(v // 10)
        leaf = int(v % 10)
        stems.setdefault(stem, []).append(leaf)
    lines = []
    for stem, leaves in sorted(stems.items()):
        leaves_str = " ".join(str(l) for l in leaves)
        lines.append(f"{stem} | {leaves_str}")
    return "\n".join(lines)
