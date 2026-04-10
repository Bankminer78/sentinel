# Sentinel Activity Reporter (browser extension)

A Chromium Manifest V3 extension that posts every page navigation to the
local Sentinel daemon. The daemon classifies new domains via Gemini Flash,
applies your rules, and (optionally) blocks via `/etc/hosts`. The extension
itself does no LLM work and makes no blocking decisions — it's just the
data pipe.

Works in **Arc**, **Chrome**, **Brave**, **Edge**, **Vivaldi**, and any
other Chromium browser that supports Manifest V3.

## Why this exists

Without a browser extension, the Sentinel daemon's `activity_log` table
stays empty even when you're using the dashboard, because the macOS
foreground-app monitor (`sentinel/monitor.py`) only tracks which **app**
is in front, not which **URL** you're on inside that app. To get
domain-level data — what site you spent the most time on this week,
which Twitter handles you check obsessively, etc. — the browser has to
report it.

This extension is that reporter.

## Install

### Arc

1. Open Arc and navigate to `arc://extensions`.
2. Toggle **Developer mode** in the top-right.
3. Click **Load unpacked**.
4. Select this `extension/` directory (the one containing
   `manifest.json`).
5. The Sentinel icon appears in your toolbar.

### Chrome / Brave / Edge

1. Open `chrome://extensions` (or `brave://`, `edge://`).
2. Toggle **Developer mode** in the top-right.
3. Click **Load unpacked** and pick this `extension/` directory.

## Verify it's working

1. Make sure the Sentinel daemon is running (`Sentinel.app` from
   `/Applications`, or `python -m sentinel.cli serve` from a terminal).
2. Open the Sentinel dashboard (click the 🛡 menu bar icon).
3. Click the **Activity** tab — empty initially.
4. Browse to a few sites in your browser.
5. Refresh the **Activity** tab. You should see the domains appear.
6. Also check the **Audit** tab — every state-changing call lands there,
   including the new-domain classification calls the daemon makes when
   it sees an unfamiliar domain for the first time.

## What gets sent

For every HTTPS page load (and only HTTPS — `chrome://`, `arc://`, `file:`,
`data:`, etc. are skipped), the extension POSTs to
`http://127.0.0.1:9849/activity` with this body:

```json
{
  "url": "https://github.com/anthropics/...",
  "title": "anthropics/claude-agent-sdk-python",
  "domain": "github.com"
}
```

The daemon then:

1. Checks the static skiplist (`sentinel/skiplist.py`) — utility domains
   like `claude.ai`, `docs.google.com`, `mail.google.com` are ignored
   without any LLM call.
2. Checks if the domain is already known (cached in `seen_domains`). If
   yes, applies your rules deterministically. If no, calls Gemini Flash
   ONCE to classify it (streaming / social / adult / gaming / shopping /
   none) and caches the result forever.
3. Logs the visit to the `activity_log` table.
4. If a rule matches and says block, adds the domain to `/etc/hosts`
   (the daemon already has the sudo capability) and returns
   `{verdict: "block"}` to the extension.
5. The extension's content script then shows a 5-second countdown
   overlay so you have a chance to recognize what happened.

## What does NOT get sent

- **`chrome://`, `arc://`, `file://`, `data:`, `about:`, etc.** — the
  extension only reports HTTP(S) URLs.
- **The same URL twice within 30 seconds** — debounced client-side. Tab
  switches and reloads don't spam the daemon.
- **Form data, cookies, request bodies** — only the URL, page title,
  and extracted domain.
- **Anything to a third-party server** — `127.0.0.1:9849` is the only
  destination. The extension's `host_permissions` in `manifest.json`
  allow exactly two hosts: `localhost:9849` and `127.0.0.1:9849`.

## Privacy posture

This is a local-first, no-cloud extension. Every URL you visit goes to
your own daemon on `127.0.0.1`. The daemon stores it in a SQLite
database at `~/.config/sentinel/sentinel.db`. Nothing is sent to any
external service except the one Gemini Flash classification call per
new domain (which the daemon makes, not the extension), and any
explicit `http_fetch` calls Claude makes on your behalf when you ask
it to in the Chat tab.

If you're not comfortable with the extension reporting every URL to
your local daemon, just don't install it. The dashboard, the chat
agent, the locks layer, and the rules engine all still work — you'll
just have an empty activity log and Claude won't be able to answer
questions like "what's my most distracting site this week".

## Files

- `manifest.json` — MV3 manifest, host permissions, service worker config
- `background.js` — service worker: tab listener, debounced `/activity`
  POSTs, message bridge to the content script overlay
- `content.js` — injected into every page: shows the 5-second countdown
  overlay when the daemon returns `{verdict: "block"}`
- `popup.html` / `popup.js` — toolbar popup: current activity, active
  rules count, currently blocked domains, recent activity feed
- `icon{16,48,128}.png` — placeholder icons

## Endpoints used

| Endpoint | Method | When | Body / response |
|---|---|---|---|
| `POST /activity` | every page load | `{url, title, domain}` → `{verdict, category?, reason?}` |
| `GET /status` | popup open | — → `{current, rules, blocked}` |
| `GET /activities?limit=20` | popup open | — → recent activity rows |

That's the entire API surface the extension uses. No agent endpoints, no
auth required (the activity endpoint is unauthenticated by design — it's
read-write but only from localhost, and the data is purely informational).

## Changelog

### 0.2.0 — schema fix

The 0.1.0 extension was sending `{url, tab_id, ts}` but the daemon's
`/activity` endpoint expected `{url, title, domain}`. The mismatch
caused the daemon to short-circuit at the empty-domain check and never
log anything to `activity_log`. This release fixes the schema, extracts
the domain client-side, drops the dead `/activity/decision` calls, and
fixes the popup field names.

### 0.1.0 — initial

Original Cold-Turkey-style extension with the 5-second countdown overlay.
