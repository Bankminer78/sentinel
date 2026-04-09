"""Progressive Web App support — manifest and service worker."""
import json


def get_manifest() -> str:
    """Returns the PWA manifest.json content."""
    manifest = {
        "name": "Sentinel — AI Accountability",
        "short_name": "Sentinel",
        "description": "The world's first AI-native accountability app",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#18181b",
        "theme_color": "#ef4444",
        "orientation": "portrait",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
        "shortcuts": [
            {"name": "Status", "url": "/status"},
            {"name": "Rules", "url": "/rules"},
            {"name": "Stats", "url": "/stats"},
        ],
    }
    return json.dumps(manifest, indent=2)


def get_service_worker_js() -> str:
    """Returns the service worker JS for offline support."""
    return """const CACHE_NAME = 'sentinel-v1';
const urlsToCache = ['/', '/mobile', '/status'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names => Promise.all(
      names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))
    ))
  );
});
"""


def get_offline_html() -> str:
    """HTML shown when offline."""
    return """<!DOCTYPE html>
<html><head><title>Sentinel Offline</title>
<style>body{font-family:sans-serif;max-width:600px;margin:100px auto;text-align:center;
background:#18181b;color:#fafafa;}h1{color:#ef4444}</style></head>
<body><h1>Sentinel is offline</h1><p>Check your connection to the Sentinel server.</p>
<p>The server normally runs on localhost:9849</p></body></html>"""


def get_install_prompt_html() -> str:
    """HTML with PWA install prompt."""
    return """<!DOCTYPE html>
<html><head><title>Install Sentinel</title>
<link rel="manifest" href="/manifest.json">
<style>body{font-family:sans-serif;padding:20px;background:#18181b;color:#fafafa;}
button{background:#ef4444;color:#fff;border:none;padding:15px 30px;border-radius:8px;
font-size:16px;cursor:pointer;}</style></head>
<body><h1>Install Sentinel</h1><p>Add Sentinel to your home screen for quick access.</p>
<button onclick="install()">Install</button>
<script>
let deferredPrompt;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferredPrompt = e; });
async function install() { if (deferredPrompt) { deferredPrompt.prompt(); deferredPrompt = null; } }
</script>
</body></html>"""
