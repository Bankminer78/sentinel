"""Additional web UI pages — rules, stats, achievements as separate pages."""

_BASE_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,system-ui,sans-serif;background:#09090b;color:#e4e4e7;padding:20px}
h1{color:#ef4444;margin-bottom:16px;font-size:28px}
h2{color:#f4f4f5;margin:12px 0 8px;font-size:18px}
.nav{display:flex;gap:12px;margin-bottom:20px;border-bottom:1px solid #27272a;padding-bottom:10px}
.nav a{color:#a1a1aa;text-decoration:none;font-size:14px}
.nav a:hover{color:#ef4444}
.card{background:#18181b;border:1px solid #27272a;border-radius:8px;padding:16px;margin-bottom:12px}
.row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #27272a}
.row:last-child{border-bottom:none}
.pill{display:inline-block;padding:2px 8px;border-radius:12px;background:#27272a;color:#e4e4e7;font-size:11px}
.pill.good{background:#052e16;color:#86efac}
.pill.bad{background:#450a0a;color:#fca5a5}
.muted{color:#71717a;font-size:12px}
input,textarea,button{background:#27272a;color:#e4e4e7;border:1px solid #3f3f46;padding:8px;border-radius:6px;font-size:14px}
button{cursor:pointer;background:#ef4444;border-color:#ef4444}
"""

_NAV = ('<div class="nav">'
        '<a href="/">Overview</a><a href="/ui/rules">Rules</a><a href="/ui/stats">Stats</a>'
        '<a href="/ui/achievements">Achievements</a><a href="/ui/habits">Habits</a>'
        '<a href="/ui/chat">Chat</a></div>')

_EMPTY = '<p class="muted">{}</p>'


def _esc(s) -> str:
    return (str(s) if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_page(title: str, body: str) -> str:
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<title>{_esc(title)}</title><style>{_BASE_CSS}</style></head>'
            f'<body><h1>{_esc(title)}</h1>{_NAV}{body}</body></html>')


def _card(title: str, inner: str, empty_msg: str) -> str:
    content = inner if inner else _EMPTY.format(empty_msg)
    return f'<div class="card"><h2>{_esc(title)}</h2>{content}</div>'


def render_rules_page_html(rules: list) -> str:
    parts = []
    for r in (rules or []):
        active = bool(r.get("active"))
        cls = "good" if active else "bad"
        label = "active" if active else "off"
        parts.append(f'<div class="row"><span>{_esc(r.get("text", ""))}</span>'
                     f'<span class="pill {cls}">{label}</span></div>')
    return render_page("Rules", _card("Active Rules", "".join(parts), "No rules"))


def render_stats_page_html(stats: dict) -> str:
    stats = stats or {}
    parts = [f'<div class="row"><span>{_esc(k)}</span><span>{_esc(v)}</span></div>'
             for k, v in stats.items()]
    return render_page("Stats", _card("Statistics", "".join(parts), "No data"))


def render_achievements_page_html(unlocked: list, locked: list) -> str:
    def _row(a, cls, label):
        name = a.get("name", a) if isinstance(a, dict) else a
        return (f'<div class="row"><span>{_esc(name)}</span>'
                f'<span class="pill {cls}">{label}</span></div>')
    un = "".join(_row(a, "good", "unlocked") for a in (unlocked or []))
    lo = "".join(_row(a, "bad", "locked") for a in (locked or []))
    body = _card("Unlocked", un, "None yet") + _card("Locked", lo, "None")
    return render_page("Achievements", body)


def render_habits_page_html(habits: list) -> str:
    parts = [f'<div class="row"><span>{_esc(h.get("name", ""))}</span>'
             f'<span class="muted">{_esc(h.get("frequency", "daily"))}</span></div>'
             for h in (habits or [])]
    return render_page("Habits", _card("Habits", "".join(parts), "No habits"))


def render_chat_page_html() -> str:
    body = """<div class="card"><h2>Ask Sentinel</h2>
<textarea id="q" rows="3" style="width:100%" placeholder="Ask about your activity..."></textarea>
<button onclick="ask()">Ask</button><pre id="ans" class="muted" style="margin-top:12px"></pre></div>
<script>
async function ask(){const q=document.getElementById('q').value;
document.getElementById('ans').textContent='...';
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({q})});
const j=await r.json();document.getElementById('ans').textContent=j.answer||JSON.stringify(j);}
catch(e){document.getElementById('ans').textContent='error: '+e;}}
</script>"""
    return render_page("Chat", body)
