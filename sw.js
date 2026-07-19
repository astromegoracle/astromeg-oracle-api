const CACHE_NAME = "astromeg-oracle-pwa-preview-v21-all-access-annual";
const APP_SHELL = [
  "./",
  "./index.html",
  "./styles.css?v=app-all-access-annual-v2",
  "./pricing-config.js?v=app-all-access-annual-v2",
  "./app.js?v=app-essential-annual-v1",
  "./manifest.webmanifest",
  "./assets/astromeg-oracle-logo-gold.png",
  "./assets/astromeg-oracle-pastel-logo-cropped.png",
  "./assets/astromeg-onboarding-01.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request).then((cached) =>
      cached || fetch(event.request).catch(() => caches.match("./index.html"))
    )
  );
});
