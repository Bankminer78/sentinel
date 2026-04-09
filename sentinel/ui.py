"""Web UI — single-file SwiftUI-styled HTML for the macOS app's WKWebView."""

UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sentinel</title>
<style>
:root {
  --bg: #1a1a1c;
  --bg-2: #232325;
  --bg-3: #2c2c2e;
  --text: #ffffff;
  --text-muted: #8e8e93;
  --accent: #ff453a;
  --accent-2: #0a84ff;
  --green: #30d158;
  --border: rgba(255,255,255,0.08);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui;
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  -webkit-font-smoothing: antialiased;
}
.app { display: flex; height: 100vh; }
.sidebar {
  width: 200px;
  background: var(--bg-2);
  border-right: 1px solid var(--border);
  padding: 32px 0 16px;
  -webkit-app-region: drag;
}
.sidebar h1 { font-size: 14px; padding: 0 16px 12px; color: var(--text); font-weight: 600; }
.nav { display: flex; flex-direction: column; }
.nav button {
  background: transparent; border: none; color: var(--text-muted);
  padding: 7px 16px; text-align: left; font-size: 13px; cursor: pointer;
  -webkit-app-region: no-drag; font-family: inherit;
  display: flex; align-items: center; gap: 8px;
}
.nav button:hover { background: rgba(255,255,255,0.04); color: var(--text); }
.nav button.active { background: var(--accent); color: white; }
.main { flex: 1; overflow-y: auto; padding: 32px 40px; }
.main h2 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.main .sub { color: var(--text-muted); margin-bottom: 24px; font-size: 13px; }
.card {
  background: var(--bg-2); border: 1px solid var(--border);
  border-radius: 10px; padding: 20px; margin-bottom: 16px;
}
.card h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
.row { display: flex; gap: 12px; flex-wrap: wrap; }
.stat {
  flex: 1; min-width: 140px; background: var(--bg-3);
  padding: 16px; border-radius: 8px;
}
.stat .label { color: var(--text-muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; }
.stat .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
.stat .value.green { color: var(--green); }
.stat .value.red { color: var(--accent); }
input, textarea, select {
  background: var(--bg-3); border: 1px solid var(--border);
  border-radius: 6px; padding: 8px 12px; color: var(--text);
  font-family: inherit; font-size: 13px; width: 100%;
}
input:focus, textarea:focus { outline: none; border-color: var(--accent-2); }
button.primary {
  background: var(--accent); color: white; border: none;
  padding: 8px 16px; border-radius: 6px; cursor: pointer;
  font-family: inherit; font-size: 13px; font-weight: 500;
}
button.primary:hover { background: #ff5747; }
button.secondary {
  background: var(--bg-3); color: var(--text); border: 1px solid var(--border);
  padding: 8px 16px; border-radius: 6px; cursor: pointer;
  font-family: inherit; font-size: 13px;
}
button.secondary:hover { background: rgba(255,255,255,0.06); }
.rule {
  background: var(--bg-3); padding: 12px 16px; border-radius: 8px;
  margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;
}
.rule .text { flex: 1; }
.rule .actions { display: flex; gap: 8px; }
.toggle {
  width: 36px; height: 20px; background: rgba(255,255,255,0.1);
  border-radius: 10px; position: relative; cursor: pointer;
}
.toggle.on { background: var(--green); }
.toggle::after {
  content: ""; position: absolute; left: 2px; top: 2px;
  width: 16px; height: 16px; background: white; border-radius: 50%;
  transition: left 0.15s;
}
.toggle.on::after { left: 18px; }
.chat-msg {
  padding: 10px 14px; margin-bottom: 8px; border-radius: 12px;
  max-width: 80%; line-height: 1.5;
}
.chat-msg.user { background: var(--accent-2); color: white; margin-left: auto; }
.chat-msg.ai { background: var(--bg-3); }
.chat-input { display: flex; gap: 8px; margin-top: 16px; }
.chat-input input { flex: 1; }
.empty { color: var(--text-muted); font-style: italic; padding: 16px; text-align: center; }
.activity-row {
  padding: 8px 12px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; font-size: 12px;
}
.activity-row .domain { color: var(--text); }
.activity-row .verdict { color: var(--text-muted); }
.activity-row .verdict.block { color: var(--accent); }
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <h1>Sentinel</h1>
    <nav class="nav">
      <button class="active" data-tab="dashboard">Dashboard</button>
      <button data-tab="rules">Rules</button>
      <button data-tab="activity">Activity</button>
      <button data-tab="ask">Ask</button>
      <button data-tab="settings">Settings</button>
    </nav>
  </aside>
  <main class="main">
    <div id="tab-dashboard">
      <h2>Today</h2>
      <p class="sub">Your productivity at a glance.</p>
      <div class="row">
        <div class="stat"><div class="label">Score</div><div class="value green" id="score">—</div></div>
        <div class="stat"><div class="label">Active rules</div><div class="value" id="rules-count">—</div></div>
        <div class="stat"><div class="label">Blocks today</div><div class="value red" id="blocks-count">—</div></div>
      </div>
      <div class="card" style="margin-top:16px">
        <h3>Currently</h3>
        <div id="current-activity" class="empty">Loading…</div>
      </div>
      <div class="card">
        <h3>Top distractions (7 days)</h3>
        <div id="top-distractions" class="empty">Loading…</div>
      </div>
    </div>

    <div id="tab-rules" style="display:none">
      <h2>Rules</h2>
      <p class="sub">Write rules in plain English. The AI parses them.</p>
      <div class="card">
        <input id="new-rule" placeholder="e.g. Block YouTube during work hours" />
        <button class="primary" style="margin-top:8px" onclick="addRule()">Add rule</button>
      </div>
      <div id="rules-list"></div>
    </div>

    <div id="tab-activity" style="display:none">
      <h2>Activity</h2>
      <p class="sub">Your recent browsing and app usage.</p>
      <div class="card" id="activity-feed"></div>
    </div>

    <div id="tab-ask" style="display:none">
      <h2>Ask</h2>
      <p class="sub">Ask anything about your data.</p>
      <div class="card">
        <div id="chat-messages" style="min-height:300px;max-height:500px;overflow-y:auto"></div>
        <div class="chat-input">
          <input id="chat-input" placeholder="How much time on YouTube this week?" onkeydown="if(event.key==='Enter')sendChat()" />
          <button class="primary" onclick="sendChat()">Send</button>
        </div>
      </div>
    </div>

    <div id="tab-settings" style="display:none">
      <h2>Settings</h2>
      <p class="sub">Configure your Sentinel.</p>
      <div class="card">
        <h3>Gemini API key</h3>
        <input id="api-key" type="password" placeholder="AIza..." />
        <button class="primary" style="margin-top:8px" onclick="saveApiKey()">Save</button>
      </div>
      <div class="card">
        <h3>Privacy level</h3>
        <select id="privacy-level" onchange="setPrivacy(this.value)">
          <option value="minimal">Minimal — no LLM, nothing stored</option>
          <option value="balanced" selected>Balanced — LLM enabled, URLs stored</option>
          <option value="full">Full — everything stored</option>
        </select>
      </div>
      <div class="card">
        <h3>Backup</h3>
        <button class="secondary" onclick="createBackup()">Create backup now</button>
      </div>
    </div>
  </main>
</div>

<script>
const API = '';

async function api(path, method='GET', body) {
  const opts = { method, headers: {'Content-Type':'application/json'} };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  return r.json();
}

document.querySelectorAll('.nav button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.nav button').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  document.querySelectorAll('[id^="tab-"]').forEach(x => x.style.display='none');
  document.getElementById('tab-' + b.dataset.tab).style.display='block';
  if (b.dataset.tab === 'dashboard') refreshDashboard();
  if (b.dataset.tab === 'rules') refreshRules();
  if (b.dataset.tab === 'activity') refreshActivity();
  if (b.dataset.tab === 'settings') refreshSettings();
}));

async function refreshDashboard() {
  try {
    const stats = await api('/stats');
    document.getElementById('score').textContent = Math.round(stats.score || 0);
    const status = await api('/status');
    document.getElementById('rules-count').textContent = (status.rules || []).filter(r => r.active).length;
    document.getElementById('blocks-count').textContent = (status.blocked.domains || []).length;
    const cur = status.current || {};
    document.getElementById('current-activity').innerHTML = cur.app
      ? '<strong>' + cur.app + '</strong><br><span style="color:var(--text-muted)">' + (cur.title || cur.domain || '') + '</span>'
      : '<em>Idle</em>';
    const top = stats.top_distractions || [];
    if (top.length === 0) {
      document.getElementById('top-distractions').innerHTML = '<div class="empty">No distractions yet.</div>';
    } else {
      document.getElementById('top-distractions').innerHTML = top.slice(0,5).map(d =>
        '<div class="activity-row"><span class="domain">' + d.domain + '</span><span class="verdict">' + Math.round((d.seconds||0)/60) + ' min</span></div>'
      ).join('');
    }
  } catch (e) { console.error(e); }
}

async function refreshRules() {
  const rules = await api('/rules');
  const list = document.getElementById('rules-list');
  if (rules.length === 0) {
    list.innerHTML = '<div class="empty">No rules yet. Add one above.</div>';
    return;
  }
  list.innerHTML = rules.map(r =>
    '<div class="rule">' +
    '<div class="text">' + r.text + '</div>' +
    '<div class="actions">' +
    '<div class="toggle ' + (r.active ? 'on' : '') + '" onclick="toggleRule(' + r.id + ')"></div>' +
    '<button class="secondary" onclick="deleteRule(' + r.id + ')">Delete</button>' +
    '</div></div>'
  ).join('');
}

async function addRule() {
  const text = document.getElementById('new-rule').value.trim();
  if (!text) return;
  await api('/rules', 'POST', { text });
  document.getElementById('new-rule').value = '';
  refreshRules();
}

async function toggleRule(id) {
  await api('/rules/' + id + '/toggle', 'POST');
  refreshRules();
}

async function deleteRule(id) {
  await api('/rules/' + id, 'DELETE');
  refreshRules();
}

async function refreshActivity() {
  const acts = await api('/activities?limit=50');
  const feed = document.getElementById('activity-feed');
  if (!acts || acts.length === 0) {
    feed.innerHTML = '<div class="empty">No activity yet.</div>';
    return;
  }
  feed.innerHTML = acts.map(a =>
    '<div class="activity-row">' +
    '<span class="domain">' + (a.domain || a.app || '—') + '</span>' +
    '<span class="verdict ' + (a.verdict === 'block' ? 'block' : '') + '">' + (a.verdict || '') + '</span>' +
    '</div>'
  ).join('');
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const q = input.value.trim();
  if (!q) return;
  const messages = document.getElementById('chat-messages');
  messages.innerHTML += '<div class="chat-msg user">' + q + '</div>';
  input.value = '';
  messages.scrollTop = messages.scrollHeight;
  try {
    const r = await api('/ask', 'POST', { question: q });
    messages.innerHTML += '<div class="chat-msg ai">' + (r.answer || 'No answer') + '</div>';
  } catch (e) {
    messages.innerHTML += '<div class="chat-msg ai">Error: ' + e.message + '</div>';
  }
  messages.scrollTop = messages.scrollHeight;
}

async function refreshSettings() {
  const k = await api('/config/gemini_api_key');
  if (k.value) document.getElementById('api-key').value = '••••••••' + (k.value || '').slice(-4);
  const p = await api('/privacy');
  if (p.level) document.getElementById('privacy-level').value = p.level;
}

async function saveApiKey() {
  const v = document.getElementById('api-key').value;
  if (!v.startsWith('•')) {
    await api('/config', 'POST', { key: 'gemini_api_key', value: v });
    refreshSettings();
  }
}

async function setPrivacy(level) {
  await api('/privacy', 'POST', { level });
}

async function createBackup() {
  const r = await api('/backup', 'POST');
  alert('Backup saved to ' + r.path);
}

refreshDashboard();
setInterval(() => {
  const active = document.querySelector('.nav button.active');
  if (active && active.dataset.tab === 'dashboard') refreshDashboard();
}, 10000);
</script>
</body>
</html>"""


def get_ui_html() -> str:
    return UI_HTML
