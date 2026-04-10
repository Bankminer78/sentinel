// Sentinel popup — pulls the live status from /status and renders it.
// The daemon's /status returns: {current: {app, title, url, domain},
//                                 rules: [...], blocked: {domains, apps}}
const SENTINEL_URL = "http://127.0.0.1:9849";

function fmtTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString();
  } catch (e) {
    return "";
  }
}

function render(status, recent) {
  const current = document.getElementById("current");
  const rules = document.getElementById("rules");
  const blocks = document.getElementById("blocks");

  // Current activity from /status — try several fields the daemon returns
  const cur = status.current || {};
  if (cur.domain) {
    current.textContent = cur.domain + (cur.title ? " · " + cur.title : "");
  } else if (cur.app) {
    current.textContent = cur.app + (cur.title ? " · " + cur.title : "");
  } else {
    current.textContent = "(idle)";
  }

  // Active rules count
  const rulesList = status.rules || [];
  const activeCount = rulesList.filter((r) => r.active).length;
  rules.textContent = activeCount + " rules";

  // Currently blocked domains (this is the live block list, not "recent")
  const blockedDomains = (status.blocked && status.blocked.domains) || [];
  if (blockedDomains.length === 0) {
    blocks.textContent = "(nothing blocked right now)";
    return;
  }
  blocks.innerHTML = "";
  blockedDomains.slice(0, 10).forEach((d) => {
    const item = document.createElement("div");
    item.className = "block-item";
    const dEl = document.createElement("div");
    dEl.className = "block-domain";
    dEl.textContent = d;
    item.appendChild(dEl);
    blocks.appendChild(item);
  });

  // Append recent activity rows below the blocks if we have them
  if (recent && recent.length) {
    const sep = document.createElement("div");
    sep.className = "label";
    sep.style.marginTop = "10px";
    sep.textContent = "Recent activity";
    blocks.appendChild(sep);
    recent.slice(0, 8).forEach((a) => {
      const item = document.createElement("div");
      item.className = "block-item";
      const dEl = document.createElement("div");
      dEl.className = "block-domain";
      dEl.style.color = a.verdict === "block" ? "#f87171" : "#60a5fa";
      dEl.textContent = a.domain || a.url || "?";
      const tEl = document.createElement("div");
      tEl.className = "block-time";
      tEl.textContent = fmtTime((a.ts || 0) * 1000);
      item.appendChild(dEl);
      item.appendChild(tEl);
      blocks.appendChild(item);
    });
  }
}

async function load() {
  try {
    const [statusRes, actsRes] = await Promise.all([
      fetch(`${SENTINEL_URL}/status`),
      fetch(`${SENTINEL_URL}/activities?limit=20`),
    ]);
    if (!statusRes.ok) throw new Error("status fetch failed");
    const status = await statusRes.json();
    let recent = [];
    if (actsRes.ok) {
      try {
        recent = await actsRes.json();
      } catch (e) {
        recent = [];
      }
    }
    render(status, recent);
  } catch (e) {
    document.getElementById("current").innerHTML =
      '<span class="err">Sentinel daemon not reachable at ' + SENTINEL_URL + '</span>';
  }
}

load();
