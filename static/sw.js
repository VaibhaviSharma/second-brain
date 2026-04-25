/**
 * sw.js — Second Brain service worker
 *
 * Strategy:
 *  • Install:  pre-cache the app shell (HTML + CSS + JS + icons).
 *  • Activate: delete any stale caches from older versions.
 *  • Fetch:
 *      /api/*  → network-only   (never cache live data)
 *      rest    → cache-first, update cache in background (stale-while-revalidate)
 *
 * Bump CACHE_NAME whenever you change static assets so clients get fresh files.
 */

const CACHE_NAME = 'brain-v1';

const PRECACHE = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/icon-apple.png',
];

// ── Install: warm the cache ───────────────────────────────────────────────────

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())   // activate immediately, don't wait
  );
});

// ── Activate: prune old caches ────────────────────────────────────────────────

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())   // take control of existing tabs
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // Only handle same-origin requests
  if (url.origin !== self.location.origin) return;

  // API calls: always go to the network, never serve stale data
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(() => new Response(
        JSON.stringify({ error: 'offline' }),
        { status: 503, headers: { 'Content-Type': 'application/json' } }
      ))
    );
    return;
  }

  // App shell: cache-first, revalidate in background
  event.respondWith(
    caches.open(CACHE_NAME).then(async cache => {
      const cached = await cache.match(request);

      const networkFetch = fetch(request).then(response => {
        if (response.ok) {
          cache.put(request, response.clone());
        }
        return response;
      }).catch(() => null);

      // Return cached version immediately if available;
      // fire the network request in parallel to keep cache fresh
      return cached ?? await networkFetch ?? new Response(
        offlinePage(),
        { headers: { 'Content-Type': 'text/html' } }
      );
    })
  );
});

// ── Offline fallback page ─────────────────────────────────────────────────────

function offlinePage() {
  return `<!DOCTYPE html>
<html data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Brain — Offline</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
    background:#0d1117;color:#c9d1d9;display:flex;align-items:center;
    justify-content:center;min-height:100vh;text-align:center;padding:24px}
  .wrap{max-width:320px}
  .icon{font-size:56px;margin-bottom:20px}
  h1{font-size:20px;font-weight:700;color:#f0f6fc;margin-bottom:8px}
  p{font-size:14px;color:#8b949e;line-height:1.6;margin-bottom:20px}
  button{padding:10px 20px;background:#58a6ff;border:none;border-radius:8px;
    color:#0d1117;font-size:14px;font-weight:600;cursor:pointer}
</style>
</head>
<body>
<div class="wrap">
  <div class="icon">🧠</div>
  <h1>Brain is offline</h1>
  <p>The local server isn't running.<br>
  Start it on your Mac, then tap Retry.</p>
  <button onclick="location.reload()">Retry</button>
</div>
</body>
</html>`;
}
