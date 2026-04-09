// Sentinel popup
const SENTINEL_URL = "http://localhost:9849";

function fmtTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString();
  } catch (e) {
    return "";
  }
}

function render(data) {
  const current = document.getElementById("current");
  const rules = document.getElementById("rules");
  const blocks = document.getElementById("blocks");

  current.textContent = data.current_activity || data.current || "(idle)";
  rules.textContent =
    (data.active_rules != null ? data.active_rules : (data.rules_count || 0)) + " rules";

  const recent = data.recent_blocks || [];
  if (!recent.length) {
    blocks.textContent = "(none)";
    return;
  }
  blocks.innerHTML = "";
  recent.slice(0, 10).forEach(function (b) {
    const item = document.createElement("div");
    item.className = "block-item";
    const d = document.createElement("div");
    d.className = "block-domain";
    d.textContent = b.domain || b.url || "unknown";
    const t = document.createElement("div");
    t.className = "block-time";
    t.textContent = fmtTime(b.ts || b.timestamp);
    item.appendChild(d);
    item.appendChild(t);
    blocks.appendChild(item);
  });
}

async function load() {
  try {
    const res = await fetch(`${SENTINEL_URL}/status`);
    if (!res.ok) throw new Error("bad status");
    const data = await res.json();
    render(data);
  } catch (e) {
    document.getElementById("current").innerHTML =
      '<span class="err">Sentinel not reachable at localhost:9849</span>';
  }
}

load();
