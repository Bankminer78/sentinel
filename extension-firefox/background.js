// Sentinel Firefox background script (MV2)
const SENTINEL_URL = "http://localhost:9849";
const seenUrls = new Map(); // url -> timestamp
const CACHE_TTL_MS = 30 * 1000;
const api = (typeof browser !== "undefined") ? browser : chrome;

function shouldSkip(url) {
  if (!url) return true;
  if (!/^https?:\/\//i.test(url)) return true;
  const last = seenUrls.get(url);
  if (last && Date.now() - last < CACHE_TTL_MS) return true;
  return false;
}

async function reportActivity(url, tabId) {
  if (shouldSkip(url)) return null;
  seenUrls.set(url, Date.now());
  try {
    const res = await fetch(`${SENTINEL_URL}/activity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, tab_id: tabId, ts: Date.now() })
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

async function notifyDecision(action, url, tabId) {
  try {
    await fetch(`${SENTINEL_URL}/activity/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, url, tab_id: tabId, ts: Date.now() })
    });
  } catch (e) {}
}

api.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "loading" || !changeInfo.url) return;
  const verdict = await reportActivity(changeInfo.url, tabId);
  if (verdict && (verdict.verdict === "block" || verdict.verdict === "warn")) {
    try {
      await api.tabs.sendMessage(tabId, {
        command: "sentinelOverlay",
        verdict: verdict.verdict,
        url: changeInfo.url,
        reason: verdict.reason || "Blocked by Sentinel",
        category: verdict.category || "blocked"
      });
    } catch (e) {}
  }
});

api.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.command === "sentinelCheck") {
    reportActivity(msg.url, sender.tab && sender.tab.id).then(v => sendResponse(v || {}));
    return true;
  }
  if (msg.command === "blockConfirmed") {
    notifyDecision("block_confirmed", msg.url, sender.tab && sender.tab.id).then(() => {
      if (sender.tab) api.tabs.reload(sender.tab.id);
      sendResponse({ ok: true });
    });
    return true;
  }
  if (msg.command === "blockCancelled") {
    notifyDecision("block_cancelled", msg.url, sender.tab && sender.tab.id).then(() =>
      sendResponse({ ok: true })
    );
    return true;
  }
});
