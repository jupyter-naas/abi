/**
 * Minimal service worker for PWA install eligibility (Chrome/Android).
 * Network-only: Zen/Nexus requires live API and auth; no offline shell cache.
 */
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
