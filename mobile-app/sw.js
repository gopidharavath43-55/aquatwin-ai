const APP_CACHE = 'aquatwin-shell-v3';
const TILE_CACHE = 'aquatwin-tiles-v3';
const MAX_TILES = 350;

self.addEventListener('install', (e) => {
  self.skipWaiting();
  e.waitUntil(
    caches.open(APP_CACHE).then((c) => c.addAll(['./', './index.html', './ml_data.js']).catch(() => {}))
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== APP_CACHE && k !== TILE_CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Cache satellite & map tiles aggressively for instant 120fps pan/zoom
  if (url.hostname.includes('arcgisonline.com') || url.hostname.includes('openstreetmap.org') || url.hostname.includes('cartocdn.com')) {
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
          return hit || Response.error();
        }
      })
    );
    return;
  }

  // Stale-while-revalidate for app shell & CDN JS/CSS/fonts
  if (url.origin === self.location.origin || url.hostname.includes('unpkg.com') || url.hostname.includes('jsdelivr.net') || url.hostname.includes('fonts.g')) {
    e.respondWith(
      caches.open(APP_CACHE).then(async (cache) => {
        const cached = await cache.match(req);
        const netPromise = fetch(req).then((resp) => {
          if (resp && (resp.ok || resp.type === 'opaque')) cache.put(req, resp.clone());
          return resp;
        }).catch(() => cached);
        return cached || netPromise;
      })
    );
  }
});
