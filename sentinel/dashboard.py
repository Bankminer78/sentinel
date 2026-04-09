"""Web dashboard — single HTML page served by FastAPI."""
import json

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sentinel Dashboard</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, system-ui, sans-serif; background: #09090b; color: #e4e4e7; padding: 20px; }
h1 { color: #ef4444; margin-bottom: 16px; font-size: 28px; }
h2 { color: #f4f4f5; margin: 12px 0 8px; font-size: 18px; }
.tabs { display: flex; gap: 4px; border-bottom: 1px solid #27272a; margin-bottom: 16px; }
.tab { padding: 10px 16px; background: transparent; border: none; color: #a1a1aa; cursor: pointer; font-size: 14px; }
.tab.active { color: #ef4444; border-bottom: 2px solid #ef4444; }
.panel { display: none; }
.panel.active { display: block; }
.card { background: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.score { font-size: 48px; color: #ef4444; font-weight: bold; }
.row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #27272a; }
.row:last-child { border-bottom: none; }
.muted { color: #71717a; font-size: 12px; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 12px; background: #27272a; color: #e4e4e7; font-size: 11px; }
.pill.bad { background: #450a0a; color: #fca5a5; }
.pill.good { background: #052e16; color: #86efac; }
pre { background: #27272a; padding: 10px; border-radius: 6px; overflow: auto; font-size: 12px; }
</style>
</head>
<body>
<h1>Sentinel Dashboard</h1>
<div class="tabs" id="tabs">
  <button class="tab active" data-tab="overview">Overview</button>
  <button class="tab" data-tab="rules">Rules</button>
  <button class="tab" data-tab="stats">Stats</button>
  <button class="tab" data-tab="goals">Goals</button>
  <button class="tab" data-tab="habits">Habits</button>
  <button class="tab" data-tab="challenges">Challenges</button>
</div>
<div class="panel active" id="panel-overview">
  <div class="card"><h2>Productivity Score</h2><div class="score" id="score">--</div></div>
  <div class="card"><h2>Current Activity</h2><div id="current"></div></div>
  <div class="card"><h2>Recent Blocks</h2><div id="blocks"></div></div>
  <div class="card"><h2>Achievements</h2><div id="achievements"></div></div>
</div>
<div class="panel" id="panel-rules"><div class="card"><h2>Active Rules</h2><div id="rules"></div></div></div>
<div class="panel" id="panel-stats"><div class="card"><h2>Statistics</h2><div id="stats"></div></div></div>
<div class="panel" id="panel-goals"><div class="card"><h2>Goals</h2><div id="goals"></div></div></div>
<div class="panel" id="panel-habits"><div class="card"><h2>Habits Today</h2><div id="habits"></div></div></div>
<div class="panel" id="panel-challenges"><div class="card"><h2>Challenges</h2><div id="challenges"></div></div></div>
<script>
async function j(p) { try { const r = await fetch(p); return await r.json(); } catch(e) { return null; } }
function esc(s) { return String(s ?? "").replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
async function load() {
  const status = await j("/status") || {};
  const stats = await j("/stats") || {};
  const score = await j("/stats/score") || {};
  const rules = await j("/rules") || [];
  const goals = await j("/goals") || [];
  const habits = await j("/habits/today") || [];
  const ach = await j("/achievements") || [];
  document.getElementById("score").textContent = (score.score ?? 0) + "/100";
  const cur = status.current_activity || {};
  document.getElementById("current").innerHTML =
    `<div class="row"><span>App</span><span>${esc(cur.app)}</span></div>` +
    `<div class="row"><span>Domain</span><span>${esc(cur.domain)}</span></div>` +
    `<div class="row"><span>Title</span><span>${esc(cur.title)}</span></div>`;
  document.getElementById("blocks").innerHTML =
    (status.blocked || []).map(b => `<div class="row"><span>${esc(b)}</span><span class="pill bad">blocked</span></div>`).join("") || '<span class="muted">none</span>';
  document.getElementById("achievements").innerHTML =
    (ach || []).map(a => `<span class="pill good">${esc(a.name || a.id)}</span>`).join(" ") || '<span class="muted">none unlocked</span>';
  document.getElementById("rules").innerHTML =
    rules.map(r => `<div class="row"><span>${esc(r.text)}</span><span class="pill">${r.active ? "on" : "off"}</span></div>`).join("") || '<span class="muted">no rules</span>';
  document.getElementById("stats").innerHTML =
    `<div class="row"><span>Total activities</span><span>${stats.total_activities ?? 0}</span></div>` +
    `<div class="row"><span>Blocked count</span><span>${stats.blocked_count ?? 0}</span></div>`;
  document.getElementById("goals").innerHTML =
    goals.map(g => `<div class="row"><span>${esc(g.name)}</span><span class="pill">${esc(g.target_type)}</span></div>`).join("") || '<span class="muted">no goals</span>';
  document.getElementById("habits").innerHTML =
    habits.map(h => `<div class="row"><span>${esc(h.name)}</span><span class="pill ${h.done ? 'good' : ''}">${h.done ? 'done' : 'todo'}</span></div>`).join("") || '<span class="muted">no habits</span>';
  const ch = await j("/challenges") || [];
  document.getElementById("challenges").innerHTML =
    (ch || []).map(c => `<div class="row"><span>${esc(c.name || c.id)}</span></div>`).join("") || '<span class="muted">none</span>';
}
document.getElementById("tabs").addEventListener("click", e => {
  if (!e.target.dataset.tab) return;
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  e.target.classList.add("active");
  document.getElementById("panel-" + e.target.dataset.tab).classList.add("active");
});
load();
setInterval(load, 10000);
</script>
</body>
</html>"""


def get_dashboard_html() -> str:
    """Return the static dashboard HTML page."""
    return DASHBOARD_HTML


def render_stats_fragment(data: dict) -> str:
    """Render a small HTML fragment showing stats — used for server-side composition."""
    score = data.get("score", 0)
    total = data.get("total_activities", 0)
    blocked = data.get("blocked_count", 0)
    return (
        '<div class="card">'
        f'<div class="score">{score}/100</div>'
        f'<div class="row"><span>Total</span><span>{total}</span></div>'
        f'<div class="row"><span>Blocked</span><span>{blocked}</span></div>'
        "</div>"
    )
