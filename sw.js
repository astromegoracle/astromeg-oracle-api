const CACHE_NAME = "astromeg-oracle-pwa-preview-v165-reading-list";
const APP_SHELL = [
  "./",
  "./index.html",
  "./styles.css?v=guided-video-luminous-v1",
  "./pricing-config.js?v=app-all-access-annual-v2",
  "./app.js?v=reading-list-v1",
  "./manifest.webmanifest",
  "./assets/astromeg-oracle-logo-gold.png",
  "./assets/astromeg-oracle-pastel-logo-cropped.png",
  "./assets/astromeg-onboarding-01.png",
  "./assets/onboarding-intro-glass.mp4",
  "./assets/onboarding-intro-glass.mov",
  "./assets/daily-challenge-reference.jpg",
  "./assets/guided-meditations-calm-loop-v2.mp4",
  "./assets/guided-meditation-banner-healing.mp4",
  "./assets/guided-meditation-banner-wealth.mp4",
  "./assets/guided-meditation-banner-vipassana.mp4",
  "./assets/guided-meditation-banner-relationship.mp4",
  "./assets/zodiac-playlist-aries.jpeg",
  "./assets/zodiac-playlist-taurus.jpeg",
  "./assets/zodiac-playlist-gemini.jpeg",
  "./assets/zodiac-playlist-cancer.jpeg",
  "./assets/zodiac-playlist-leo.jpeg",
  "./assets/zodiac-playlist-virgo.jpeg",
  "./assets/zodiac-playlist-libra.jpeg",
  "./assets/zodiac-playlist-scorpio.jpeg",
  "./assets/zodiac-playlist-sagittarius.jpeg",
  "./assets/zodiac-playlist-capricorn.jpeg",
  "./assets/zodiac-playlist-aquarius.jpeg",
  "./assets/zodiac-playlist-pisces.jpeg"
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
  const requestUrl = new URL(event.request.url);
  const isSameOrigin = requestUrl.origin === self.location.origin;

  if (event.request.mode === "navigate" || (isSameOrigin && requestUrl.pathname.endsWith(".html"))) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const responseCopy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put("./index.html", responseCopy));
          return response;
        })
        .catch(() => caches.match("./index.html"))
    );
    return;
  }

  event.respondWith(
    fetch(event.request).then((response) => {
      if (isSameOrigin) {
        const responseCopy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseCopy));
      }
      return response;
    }).catch(() =>
      caches.match(event.request).then((cached) => cached || caches.match("./index.html"))
    )
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const route = event.notification.data?.route || "today-sky";
  const targetUrl = new URL(`./#${route}`, self.location).href;

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      const sameOriginClient = clientList.find((client) => new URL(client.url).origin === self.location.origin);

      if (sameOriginClient) {
        return sameOriginClient.navigate(targetUrl).then((client) => (client || sameOriginClient).focus());
      }

      return clients.openWindow(targetUrl);
    })
  );
});
