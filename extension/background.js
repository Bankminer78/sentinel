// Sentinel activity reporter — service worker.
//
// Listens to tab updates and POSTs each navigation to the local Sentinel
// daemon's /activity endpoint. The daemon handles classification (Gemini
// Flash), rule evaluation, and blocking via /etc/hosts. The extension is
// just the data pipe — no LLM in here, no client-side blocking decisions.
//
// Schema sent (matches sentinel/server.py ActivityReport):
//   { url: string, title: string, domain: string }
//
// The daemon's response may include {verdict: "block"|"warn"|"allow"}; on
// block/warn we ask the content script to show a 5-second countdown
// overlay (legacy Cold-Turkey-style UX, kept because the daemon's hosts-
// file block can take a beat to propagate via dscacheutil).

const SENTINEL_URL = "http://127.0.0.1:9849";
const seenUrls = new Map(); // url -> timestamp
const CACHE_TTL_MS = 30 * 1000;

function shouldSkip(url) {
  if (!url) return true;
  // Only HTTP(S) — skip chrome://, arc://, file://, data:, about:, etc.
  if (!/^https?:\/\//i.test(url)) return true;
  const last = seenUrls.get(url);
  if (last && Date.now() - last < CACHE_TTL_MS) return true;
  return false;
}

function extractDomain(url) {
  try {
    const u = new URL(url);
    // Strip leading "www." for consistency with the daemon's skiplist
    // (which lists `youtube.com`, not `www.youtube.com`).
    return u.hostname.replace(/^www\./, "");
  } catch (e) {
    return "";
  }
}

async function reportActivity(url, title, tabId) {
  if (shouldSkip(url)) return null;
  const domain = extractDomain(url);
  if (!domain) return null;
  seenUrls.set(url, Date.now());
  try {
    const res = await fetch(`${SENTINEL_URL}/activity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        title: title || "",
        domain,
      }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    // Daemon offline — silently fail. Don't break the user's browsing.
    return null;
  }
}

// We listen to tabs.onUpdated rather than webNavigation.onCompleted because
// we want both the URL AND the title in one shot, and tabs.onUpdated fires
// once status flips to "complete" with tab.title populated.
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  // Only report once per page load — fire on `complete` so the title is set.
  if (changeInfo.status !== "complete") return;
  if (!tab || !tab.url) return;

  const verdict = await reportActivity(tab.url, tab.title || "", tabId);
  if (verdict && (verdict.verdict === "block" || verdict.verdict === "warn")) {
    try {
      await chrome.tabs.sendMessage(tabId, {
        command: "sentinelOverlay",
        verdict: verdict.verdict,
        url: tab.url,
        reason: verdict.reason || `Sentinel: ${verdict.category || "blocked"}`,
        category: verdict.category || "blocked",
      });
    } catch (e) {
      // Content script not loaded (e.g. extension store page) — ignore
    }
  }
});

// The content script can also push a check on its own init — useful for
// pages that finish loading before the extension's listener attaches.
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.command === "sentinelCheck") {
    const tabId = sender.tab && sender.tab.id;
    const title = (sender.tab && sender.tab.title) || msg.title || "";
    reportActivity(msg.url, title, tabId).then((v) => sendResponse(v || {}));
    return true;
  }
  // Legacy decision messages from the content script's countdown overlay.
  // The current daemon doesn't have a /activity/decision endpoint — the
  // block has already happened in /etc/hosts by the time the overlay
  // fires. We just acknowledge so the content script can dismiss the
  // overlay and let the user move on.
  if (msg && (msg.command === "blockConfirmed" || msg.command === "blockCancelled")) {
    if (msg.command === "blockConfirmed" && sender.tab) {
      // Reload the tab so the user sees the daemon's hosts-file block
      // (now they'll get ERR_NAME_NOT_RESOLVED instead of the live page).
      chrome.tabs.reload(sender.tab.id);
    }
    sendResponse({ ok: true });
    return false;
  }
});

// Garbage-collect the seen-urls cache so it doesn't grow forever.
setInterval(() => {
  const cutoff = Date.now() - CACHE_TTL_MS * 4;
  for (const [url, ts] of seenUrls) {
    if (ts < cutoff) seenUrls.delete(url);
  }
}, 60 * 1000);
