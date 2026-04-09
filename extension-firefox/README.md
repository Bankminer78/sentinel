# Sentinel Firefox Extension

A Firefox Manifest V2 extension that monitors page visits and enforces blocks through the Sentinel server. This mirrors the Chrome MV3 build in `extension/` but uses MV2 since Firefox does not yet fully support MV3 service workers across all channels.

## Requirements

- Firefox 78+
- Sentinel server running locally on `http://localhost:9849`

## Installation (temporary)

1. Open `about:debugging#/runtime/this-firefox`.
2. Click **Load Temporary Add-on...**.
3. Select `extension-firefox/manifest.json`.
4. The Sentinel icon will appear in the toolbar.

Temporary add-ons are removed on Firefox restart; for permanent use, package with `web-ext build` and sign via [AMO](https://addons.mozilla.org).

## Key differences from the Chrome extension

- **Manifest V2** — uses `background.scripts` instead of a service worker.
- **`browser.*` API** — the scripts prefer `browser` (Firefox) and fall back to `chrome` so the same code runs on both engines.
- **`applications.gecko.id`** — required for Firefox to load the add-on (`sentinel@sentinel.local`).
- **`browser_action`** instead of MV3 `action`.
- **`host_permissions` merged into `permissions`** — MV2 keeps host matches in the single `permissions` array.

## Files

- `manifest.json` — MV2 manifest with gecko application id
- `background.js` — non-persistent background script
- `content.js` — injected overlay on every page
- `popup.html` / `popup.js` — toolbar popup
- `icon16.png` / `icon48.png` / `icon128.png` — icons (shared with the Chrome build)

## Server endpoints used

Same as the Chrome build — see `extension/README.md`.
