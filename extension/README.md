# Sentinel Chrome Extension

A Chrome Manifest V3 extension that monitors page visits and enforces blocks through the Sentinel server.

## Requirements

- Google Chrome (or any Chromium-based browser supporting MV3)
- Sentinel server running locally on `http://localhost:9849`

## Installation

1. Open Chrome and navigate to `chrome://extensions`.
2. Toggle **Developer mode** (top right).
3. Click **Load unpacked** and select this `extension/` directory.
4. The Sentinel icon will appear in your toolbar.

## Features

- **Activity reporting** — every HTTP(S) page visit is sent to `POST /activity` on the Sentinel server.
- **Block overlay** — if the server responds with `{"verdict": "block"}` (or `"warn"`), a full-viewport overlay appears with a 5-second countdown and a Cancel button.
- **Auto-confirm** — if the user does not cancel, the extension sends `block_confirmed` to the server and reloads the tab (the Sentinel server typically adds the domain to `/etc/hosts`, so the reload fails to resolve).
- **Cancel path** — clicking Cancel sends `block_cancelled` to the server so it can skip the block for that URL.
- **Popup status** — click the toolbar icon to view current activity, active rules count, and recent blocks (polled from `GET /status`).
- **Duplicate suppression** — the background worker caches each URL for 30 seconds to avoid spamming the server.

## Files

- `manifest.json` — MV3 manifest
- `background.js` — service worker: tab listener, `/activity` reporting, decision messages
- `content.js` — injected into every page: shows the countdown overlay
- `popup.html` / `popup.js` — toolbar popup
- `icon16.png` / `icon48.png` / `icon128.png` — placeholder icons

## Server endpoints used

- `POST /activity` — request body `{url, tab_id, ts}`, response `{verdict, reason?, category?}`
- `POST /activity/decision` — request body `{action, url, tab_id, ts}` where `action` is `block_confirmed` or `block_cancelled`
- `GET /status` — returns popup payload (`current_activity`, `active_rules`, `recent_blocks`)
