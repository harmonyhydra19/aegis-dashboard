const CACHE_NAME = 'aegis-cache-v1';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  // Pass-through agar tetap online realtime ke Supabase
  e.respondWith(fetch(e.request).catch(() => new Response('Offline Mode')));
});