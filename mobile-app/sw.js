const CACHE_CORE = "aquatwin-core-v1.149";
const CACHE_TILES = "aquatwin-tiles-v1";
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./data.js",
  "./ml_data.js",
  "./vendor/leaflet.css",
  "./vendor/leaflet.js",
  "./vendor/chart.umd.min.js",
  "./tiles/manifest.js"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_CORE)
      .then((cache) => Promise.allSettled(CORE_ASSETS.map((u) => cache.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_CORE && k !== CACHE_TILES).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Cache-First for bundled & ArcGIS map tiles -> zero buffering in Chrome
  if (url.pathname.includes("/tiles/") || url.hostname === "server.arcgisonline.com") {
    event.respondWith(
      caches.open(CACHE_TILES).then((cache) =>
        cache.match(req).then((cached) => {
          if (cached) return cached;
          return fetch(req).then((netRes) => {
            if (netRes && (netRes.ok || netRes.type === "opaque")) {
              cache.put(req, netRes.clone()).catch(() => {});
            }
            return netRes;
          }).catch(() => cached || Response.error());
        })
      )
    );
    return;
  }

  // Network-First with instant cache fallback for app shell & datasets
  if (url.origin === self.location.origin) {
    event.respondWith(
      fetch(req).then((netRes) => {
        if (netRes && netRes.ok) {
          caches.open(CACHE_CORE).then((c) => c.put(req, netRes.clone())).catch(() => {});
        }
        return netRes;
      }).catch(() => caches.match(req))
    );
  }
});
