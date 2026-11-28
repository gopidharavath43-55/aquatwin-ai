const APP_CACHE = 'aquatwin-ios27-liquid-v5';
const TILE_CACHE = 'aquatwin-tiles-v12';
const MAX_TILES = 4000;
const BLANK_TILE_B64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=';
const IS_LOCAL_HTTP = self.location.protocol === 'http:' && /^(127\.0\.0\.1|localhost)$/i.test(self.location.hostname);

function blankTileResponse() {
  const bin = atob(BLANK_TILE_B64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Response(bytes, { status: 200, headers: { 'Content-Type': 'image/png' } });
}

self.addEventListener('install', (e) => {
  self.skipWaiting();
  if (IS_LOCAL_HTTP) return;
  e.waitUntil(
    caches.open(APP_CACHE).then((c) =>
      c.addAll([
        './',
        './index.html',
        './styles/liquid-glass.css',
        './js/app.js',
        './aquatwin_assistant.js',
        './data.js',
        './ml_data.js',
        './ml_predictions.json',
        './icon.png',
        './fonts/InterVariable.woff2',
        './appfont.woff2'
      ]).catch(() => {})
    )
  );
});

self.addEventListener('activate', (e) => {
  if (IS_LOCAL_HTTP) {
    e.waitUntil(
      caches.keys()
        .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
        .then(() => self.registration.unregister())
        .then(() => self.clients.matchAll({ type: 'window' }))
        .then((clients) => clients.forEach((c) => { try { c.navigate(c.url); } catch (err) {} }))
    );
    return;
  }
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== APP_CACHE && k !== TILE_CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  if (IS_LOCAL_HTTP) return;
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.hostname.includes('arcgisonline.com') || url.hostname.includes('openstreetmap.org')) {
    e.respondWith(
      caches.open(TILE_CACHE).then(async (cache) => {
        const hit = await cache.match(req);
        if (hit) return hit;
        try {
          const resp = await fetch(req);
          if (resp && (resp.ok || resp.type === 'opaque')) {
            cache.put(req, resp.clone());
            cache.keys().then((ks) => {
              if (ks.length > MAX_TILES) ks.slice(0, ks.length - MAX_TILES).forEach((k) => cache.delete(k));
            });
          }
          return resp;
        } catch (err) {
          return hit || blankTileResponse();
        }
      })
    );
    return;
  }

  if (url.origin === self.location.origin || url.hostname.includes('unpkg.com') || url.hostname.includes('jsdelivr.net')) {
    e.respondWith(
      caches.open(APP_CACHE).then(async (cache) => {
        try {
          const resp = await fetch(req, { cache: 'no-cache' });
          if (resp && (resp.ok || resp.type === 'opaque')) cache.put(req, resp.clone());
          return resp;
        } catch (err) {
          const cached = await cache.match(req, { ignoreSearch: true });
          return cached || Response.error();
        }
      })
    );
  }
});
