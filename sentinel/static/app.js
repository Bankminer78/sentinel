// Sentinel dashboard — vanilla JS, no framework, no build step.
// Phase 2 of the lockbox refactor: Chat tab streams from /api/agent SSE,
// Locks + Audit tabs are paginated read-only views, Settings has the
// daily token budget slider and the emergency-exit display.
//
// The bearer token for /api/agent/* endpoints is injected by the Swift
// menu-bar app via window.SENTINEL_TOKEN at page load. If the page is
// opened in a regular browser without the Swift app, agent calls will
// 401 with "missing bearer token" — that's expected.

'use strict';

const API = '';

// --- Auth + fetch helpers ---

function getAgentToken() {
  return window.SENTINEL_TOKEN || '';
}

async function api(path, method = 'GET', body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  return r.json();
}

async function agentFetch(path, method = 'GET', body) {
  const token = getAgentToken();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const opts = { method, headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const text = await r.text();
    throw new Error('HTTP ' + r.status + ': ' + text);
  }
  return r.json();
}

// --- Tab navigation ---

document.querySelectorAll('.nav button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.nav button').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    document.querySelectorAll('[id^="tab-"]').forEach(x => x.style.display = 'none');
    document.getElementById('tab-' + b.dataset.tab).style.display = 'block';
    const tab = b.dataset.tab;
    if (tab === 'dashboard') refreshDashboard();
    else if (tab === 'chat') refreshChat();
    else if (tab === 'locks') refreshLocks();
    else if (tab === 'audit') refreshAudit();
    else if (tab === 'rules') refreshRules();
    else if (tab === 'activity') refreshActivity();
    else if (tab === 'settings') refreshSettings();
  });
});

// --- Dashboard ---

async function refreshDashboard() {
  try {
    const stats = await api('/stats');
    document.getElementById('score').textContent = Math.round(stats.score || 0);
    const status = await api('/status');
    document.getElementById('rules-count').textContent =
      (status.rules || []).filter(r => r.active).length;
    // Locks and budget — best-effort, may fail without auth
    try {
      const locks = await api('/locks');
      document.getElementById('locks-count').textContent = (locks || []).length;
    } catch (e) {
      document.getElementById('locks-count').textContent = '—';
    }
    try {
      const budget = await agentFetch('/api/agent/budget');
      document.getElementById('budget-used').textContent =
        '$' + (budget.used_usd || 0).toFixed(3);
    } catch (e) {
      document.getElementById('budget-used').textContent = '—';
    }
    const cur = status.current || {};
    document.getElementById('current-activity').innerHTML = cur.app
      ? '<strong>' + escapeHtml(cur.app) + '</strong><br>' +
        '<span class="muted">' + escapeHtml(cur.title || cur.domain || '') + '</span>'
      : '<em>Idle</em>';
    const top = stats.top_distractions || [];
    if (top.length === 0) {
      document.getElementById('top-distractions').innerHTML =
        '<div class="empty">No distractions yet.</div>';
    } else {
      document.getElementById('top-distractions').innerHTML = top.slice(0, 5).map(d =>
        '<div class="activity-row"><span class="domain">' +
        escapeHtml(d.domain) + '</span><span class="verdict">' +
        Math.round((d.seconds || 0) / 60) + ' min</span></div>'
      ).join('');
    }
  } catch (e) {
    console.error('refreshDashboard:', e);
  }
}

// --- Chat tab (the agent surface) ---

let chatEventSource = null;

function refreshChat() {
  // Show the daily budget remaining
  agentFetch('/api/agent/budget').then(b => {
    document.getElementById('chat-budget').textContent =
      'Budget today: $' + (b.used_usd || 0).toFixed(3) +
      ' used of $' + (b.budget_usd || 0).toFixed(2) +
      ' (remaining: $' + (b.remaining_usd || 0).toFixed(3) + ')';
  }).catch(() => {
    document.getElementById('chat-budget').textContent =
      'Budget unavailable (no agent token loaded — run via Sentinel.app)';
  });
}

function appendChatEvent(kind, content) {
  const events = document.getElementById('chat-events');
  const div = document.createElement('div');
  div.className = 'chat-event ' + kind;
  div.innerHTML = content;
  events.appendChild(div);
  events.scrollTop = events.scrollHeight;
  return div;
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send-btn');
  const prompt = input.value.trim();
  if (!prompt) return;

  // Close any prior stream
  if (chatEventSource) {
    chatEventSource.close();
    chatEventSource = null;
  }

  appendChatEvent('user',
    '<div class="label">You</div>' + escapeHtml(prompt));
  input.value = '';
  sendBtn.disabled = true;
  sendBtn.textContent = 'Working…';

  let session_id;
  try {
    const start = await agentFetch('/api/agent', 'POST', { prompt });
    session_id = start.session_id;
  } catch (e) {
    appendChatEvent('error',
      '<div class="label">Error</div>' + escapeHtml(e.message));
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
    return;
  }

  // Open SSE stream. EventSource doesn't support custom headers, so we
  // need to pass the bearer token via a query param OR use fetch+ReadableStream.
  // We use fetch() so we can include the Authorization header properly.
  const token = getAgentToken();
  const resp = await fetch('/api/agent/' + encodeURIComponent(session_id) + '/events', {
    headers: token ? { 'Authorization': 'Bearer ' + token } : {},
  });
  if (!resp.ok || !resp.body) {
    appendChatEvent('error',
      '<div class="label">Stream error</div>HTTP ' + resp.status);
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // Parse SSE: events separated by blank lines
      while (true) {
        const idx = buf.indexOf('\n\n');
        if (idx === -1) break;
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        handleSseFrame(raw);
      }
    }
  } catch (e) {
    appendChatEvent('error',
      '<div class="label">Stream interrupted</div>' + escapeHtml(e.message));
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
    // Refresh the budget display after the session
    refreshChat();
  }
}

function handleSseFrame(raw) {
  // SSE frame is "data: <json>\n" possibly preceded by "event: <name>\n"
  let dataLine = '';
  for (const line of raw.split('\n')) {
    if (line.startsWith('data:')) dataLine += line.slice(5).trim();
  }
  if (!dataLine) return;
  let event;
  try {
    event = JSON.parse(dataLine);
  } catch (e) {
    return;
  }
  renderAgentEvent(event);
}

// Track the live streaming text block so we can append deltas to it in
// place. The SDK now sends:
//   assistant_text_start  → open a new text block (we create a div)
//   assistant_text_delta  → append delta text to that div
//   (no final assistant_text — the deltas already covered it)
//   result                → final cost stamp; we compare to streamedBuffer
//                           to know whether to re-render or just show "Done"
let lastAssistantText = '';
let streamingTextDiv = null;
let streamingBuffer = '';

function renderAgentEvent(event) {
  const t = event.type;
  if (t === 'session_started') {
    // Silent — no UI noise for session lifecycle
    lastAssistantText = '';
    streamingTextDiv = null;
    streamingBuffer = '';
  } else if (t === 'assistant_text_start') {
    streamingBuffer = '';
    streamingTextDiv = appendChatEvent('assistant',
      '<div class="text-content"></div>');
  } else if (t === 'assistant_text_delta') {
    if (!streamingTextDiv) {
      streamingTextDiv = appendChatEvent('assistant',
        '<div class="text-content"></div>');
      streamingBuffer = '';
    }
    streamingBuffer += event.delta || '';
    const target = streamingTextDiv.querySelector('.text-content');
    if (target) {
      target.textContent = streamingBuffer;
      // Scroll to bottom so the user sees the latest text as it arrives
      const events = document.getElementById('chat-events');
      events.scrollTop = events.scrollHeight;
    }
    lastAssistantText = streamingBuffer;
  } else if (t === 'assistant_text') {
    lastAssistantText = event.text || '';
    streamingTextDiv = null;
    streamingBuffer = '';
    appendChatEvent('assistant', escapeHtml(event.text));
  } else if (t === 'tool_use') {
    // A new tool call closes the current streaming text block.
    if (streamingTextDiv) {
      const tc = streamingTextDiv.querySelector('.text-content');
      if (tc) tc.classList.add('done');
    }
    streamingTextDiv = null;
    streamingBuffer = '';
    const inputStr = typeof event.input === 'string'
      ? event.input
      : JSON.stringify(event.input, null, 2);
    appendChatEvent('tool-use',
      '<span class="toggle-detail" data-action="toggle">' + escapeHtml(event.tool || 'Tool') + '</span>' +
      '<div class="detail"><pre>' + escapeHtml(inputStr) + '</pre></div>');
  } else if (t === 'tool_result') {
    const result = event.result || '';
    appendChatEvent('tool-result',
      '<span class="toggle-detail" data-action="toggle">Output</span>' +
      '<div class="detail"><pre>' + escapeHtml(result) + '</pre></div>');
  } else if (t === 'result') {
    // The SDK emits ResultMessage.result with the same text as the last
    // assistant block we already rendered (whether via deltas or full).
    // Only show the cost stamp + a "done" marker; suppress the duplicate
    // text. If the result text differs (e.g. no assistant text at all),
    // fall back to showing the full thing.
    if (streamingTextDiv) {
      const tc = streamingTextDiv.querySelector('.text-content');
      if (tc) tc.classList.add('done');
    }
    streamingTextDiv = null;
    streamingBuffer = '';
    const cost = event.cost_usd != null ? '$' + event.cost_usd.toFixed(4) : 'free';
    const resultText = event.result || '';
    const isDuplicate = resultText && resultText === lastAssistantText;
    if (isDuplicate) {
      // Just a tiny cost stamp, no duplicate text
      const stamp = document.createElement('div');
      stamp.className = 'chat-cost-stamp';
      stamp.textContent = cost;
      document.getElementById('chat-events').appendChild(stamp);
    } else {
      appendChatEvent('result', escapeHtml(resultText));
    }
  } else if (t === 'rate_limit') {
    // Silent — rate limit info is noisy and not actionable for the user
  } else if (t === 'budget_refused') {
    appendChatEvent('error',
      'Daily budget ($' + (event.budget_usd || 0).toFixed(2) +
      ') exhausted. Adjust in Settings or wait until tomorrow.');
  } else if (t === 'error') {
    appendChatEvent('error', escapeHtml(event.message || event.error_type || 'Error'));
  }
}

// Toggle detail visibility (event delegation — works for dynamically-added rows)
document.addEventListener('click', (e) => {
  if (e.target && e.target.dataset && e.target.dataset.action === 'toggle') {
    const detail = e.target.parentElement.querySelector('.detail');
    if (detail) detail.classList.toggle('open');
  }
});

document.getElementById('chat-send-btn').addEventListener('click', sendChat);
document.getElementById('chat-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); };
});

// --- Locks tab ---

async function refreshLocks() {
  const list = document.getElementById('locks-list');
  try {
    const locks = await api('/locks');
    if (!locks || locks.length === 0) {
      list.innerHTML = '<div class="empty">No active locks. Ask the agent to commit you to something.</div>';
      return;
    }
    list.innerHTML = locks.map(lk => {
      const remainingMs = (lk.until_ts * 1000) - Date.now();
      const remaining = humanDuration(remainingMs);
      const friction = lk.friction
        ? ('Friction: ' + escapeHtml(lk.friction.type) +
           (lk.friction.seconds ? ' (' + lk.friction.seconds + 's)' : '') +
           (lk.friction.chars ? ' (' + lk.friction.chars + ' chars)' : ''))
        : 'No early release';
      return '<div class="lock-row">' +
        '<div class="head">' +
        '<span class="name">' + escapeHtml(lk.name) + '</span>' +
        '<span class="kind">' + escapeHtml(lk.kind) + '</span>' +
        '</div>' +
        (lk.target ? '<div class="target">' + escapeHtml(lk.target) + '</div>' : '') +
        '<div class="meta">' + escapeHtml(remaining) + ' remaining · ' + escapeHtml(friction) + '</div>' +
        '</div>';
    }).join('');
  } catch (e) {
    list.innerHTML = '<div class="empty">Failed to load locks: ' + escapeHtml(e.message) + '</div>';
  }
}

function humanDuration(ms) {
  if (ms <= 0) return 'expired';
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return sec + 's';
  const min = Math.floor(sec / 60);
  if (min < 60) return min + 'm';
  const hr = Math.floor(min / 60);
  if (hr < 24) return hr + 'h ' + (min % 60) + 'm';
  const days = Math.floor(hr / 24);
  return days + 'd ' + (hr % 24) + 'h';
}

// --- Audit tab ---

async function refreshAudit() {
  const list = document.getElementById('audit-list');
  const actor = document.getElementById('audit-filter-actor').value.trim();
  const primitive = document.getElementById('audit-filter-primitive').value.trim();
  const params = new URLSearchParams({ limit: '100' });
  if (actor) params.set('actor', actor);
  if (primitive) params.set('primitive', primitive);
  try {
    const rows = await api('/audit?' + params.toString());
    if (!rows || rows.length === 0) {
      list.innerHTML = '<div class="empty">No audit entries match.</div>';
      return;
    }
    list.innerHTML = rows.map(r => {
      const ts = new Date(r.ts * 1000).toLocaleTimeString();
      const args = JSON.stringify(r.args_summary || {});
      const statusClass = r.result_status === 'error' ? 'error'
                       : r.result_status === 'locked' || r.result_status === 'budget_refused' ? 'locked'
                       : '';
      const rowClass = statusClass === 'error' ? ' error' : '';
      return '<div class="audit-row' + rowClass + '">' +
        '<span class="ts">' + escapeHtml(ts) + '</span>' +
        '<span class="actor">' + escapeHtml(r.actor || '') + '</span>' +
        '<span class="primitive">' + escapeHtml(r.primitive || '') + '</span>' +
        '<span class="status ' + statusClass + '">' + escapeHtml(r.result_status || '') + '</span>' +
        '<span class="args">' + escapeHtml(args) + '</span>' +
        '</div>';
    }).join('');
  } catch (e) {
    list.innerHTML = '<div class="empty">Failed to load audit: ' + escapeHtml(e.message) + '</div>';
  }
}

document.getElementById('audit-refresh-btn').addEventListener('click', refreshAudit);
document.getElementById('audit-filter-actor').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') refreshAudit();
});
document.getElementById('audit-filter-primitive').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') refreshAudit();
});

// --- Rules tab (existing) ---

async function refreshRules() {
  const rules = await api('/rules');
  const list = document.getElementById('rules-list');
  if (!rules || rules.length === 0) {
    list.innerHTML = '<div class="empty">No rules yet. Add one above.</div>';
    return;
  }
  list.innerHTML = rules.map(r =>
    '<div class="rule">' +
    '<div class="text">' + escapeHtml(r.text) + '</div>' +
    '<div class="actions">' +
    '<div class="toggle ' + (r.active ? 'on' : '') + '" data-action="toggle-rule" data-id="' + r.id + '"></div>' +
    '<button class="secondary" data-action="delete-rule" data-id="' + r.id + '">Delete</button>' +
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

document.getElementById('add-rule-btn').addEventListener('click', addRule);
document.addEventListener('click', async (e) => {
  if (!e.target || !e.target.dataset) return;
  const action = e.target.dataset.action;
  const id = e.target.dataset.id;
  if (action === 'toggle-rule' && id) {
    await api('/rules/' + id + '/toggle', 'POST');
    refreshRules();
  } else if (action === 'delete-rule' && id) {
    await api('/rules/' + id, 'DELETE');
    refreshRules();
  }
});

// --- Activity tab (existing) ---

async function refreshActivity() {
  const acts = await api('/activities?limit=50');
  const feed = document.getElementById('activity-feed');
  if (!acts || acts.length === 0) {
    feed.innerHTML = '<div class="empty">No activity yet.</div>';
    return;
  }
  feed.innerHTML = acts.map(a =>
    '<div class="activity-row">' +
    '<span class="domain">' + escapeHtml(a.domain || a.app || '—') + '</span>' +
    '<span class="verdict ' + (a.verdict === 'block' ? 'block' : '') + '">' +
    escapeHtml(a.verdict || '') + '</span>' +
    '</div>'
  ).join('');
}

// --- Settings tab ---

async function refreshSettings() {
  // Gemini key
  try {
    const k = await api('/config/gemini_api_key');
    if (k.value) {
      document.getElementById('api-key').value = '••••••••' + (k.value || '').slice(-4);
    }
  } catch (e) { /* ignore */ }
  // Privacy
  try {
    const p = await api('/privacy');
    if (p.level) document.getElementById('privacy-level').value = p.level;
  } catch (e) { /* ignore */ }
  // Daily budget
  try {
    const b = await agentFetch('/api/agent/budget');
    document.getElementById('budget-input').value = (b.budget_usd || 1.0).toFixed(2);
  } catch (e) {
    document.getElementById('budget-input').value = '';
  }
  // Emergency exit status
  try {
    const e = await api('/emergency-exit/status');
    document.getElementById('emergency-status').textContent =
      e.remaining + ' of ' + e.limit + ' remaining this month';
  } catch (e) { /* ignore */ }
}

async function saveApiKey() {
  const v = document.getElementById('api-key').value;
  if (!v.startsWith('•')) {
    await api('/config', 'POST', { key: 'gemini_api_key', value: v });
    refreshSettings();
  }
}

async function saveBudget() {
  const v = document.getElementById('budget-input').value;
  if (!v) return;
  await api('/config', 'POST', { key: 'daily_token_budget_usd', value: v });
  refreshSettings();
}

async function setPrivacy(level) {
  await api('/privacy', 'POST', { level });
}

async function createBackup() {
  const r = await api('/backup', 'POST');
  alert('Backup saved to ' + r.path);
}

document.getElementById('save-api-key-btn').addEventListener('click', saveApiKey);
document.getElementById('save-budget-btn').addEventListener('click', saveBudget);
document.getElementById('privacy-level').addEventListener('change', (e) => setPrivacy(e.target.value));
document.getElementById('backup-btn').addEventListener('click', createBackup);

// --- Helpers ---

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// --- Initial load ---

refreshDashboard();
setInterval(() => {
  const active = document.querySelector('.nav button.active');
  if (active && active.dataset.tab === 'dashboard') refreshDashboard();
}, 10000);
