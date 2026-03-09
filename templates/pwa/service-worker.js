// NexusERP Service Worker - Odoo Enterprise Pattern
// Rendered as Django template for dynamic configuration
const CACHE_VERSION = 'nexuserp-v2';
const PRECACHE_NAME = CACHE_VERSION + '-precache';
const RUNTIME_NAME = CACHE_VERSION + '-runtime';
const OFFLINE_URL = '/offline/';

// Core assets to precache on install
const PRECACHE_URLS = [
  OFFLINE_URL,
  '/static/pwa/icons/icon-192x192.png',
  '/static/pwa/icons/icon-512x512.png',
];

// ========== INSTALL ==========
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(PRECACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// ========== ACTIVATE ==========
self.addEventListener('activate', (event) => {
  const currentCaches = [PRECACHE_NAME, RUNTIME_NAME];
  event.waitUntil(
    caches.keys()
      .then((cacheNames) =>
        cacheNames.filter((name) => !currentCaches.includes(name))
      )
      .then((cachesToDelete) =>
        Promise.all(cachesToDelete.map((name) => caches.delete(name)))
      )
      .then(() => self.clients.claim())
  );
});

// ========== FETCH STRATEGIES ==========

// Stale-while-revalidate for static assets
function staleWhileRevalidate(request) {
  return caches.open(RUNTIME_NAME).then((cache) =>
    cache.match(request).then((cached) => {
      const fetched = fetch(request).then((response) => {
        if (response.ok) {
          cache.put(request, response.clone());
        }
        return response;
      });
      return cached || fetched;
    })
  );
}

// Network-first for HTML pages
function networkFirst(request) {
  return fetch(request)
    .then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(RUNTIME_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    })
    .catch(() =>
      caches.match(request).then((cached) => cached || caches.match(OFFLINE_URL))
    );
}

// Cache-first for immutable assets (fonts, vendor CSS/JS)
function cacheFirst(request) {
  return caches.match(request).then((cached) => {
    if (cached) return cached;
    return fetch(request).then((response) => {
      if (response.ok) {
        const clone = response.clone();
        caches.open(RUNTIME_NAME).then((cache) => cache.put(request, clone));
      }
      return response;
    });
  });
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET and cross-origin
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Skip API calls - always network
  if (url.pathname.startsWith('/api/')) return;

  // Skip admin panel
  if (url.pathname.startsWith('/admin/')) return;

  // CDN / vendor assets (fonts, bootstrap) - cache-first
  if (
    url.pathname.includes('/vendor/') ||
    url.pathname.includes('fonts.googleapis') ||
    url.pathname.includes('cdn.jsdelivr')
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Static assets - stale-while-revalidate
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/media/')) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // HTML pages - network-first with offline fallback
  if (request.headers.get('Accept')?.includes('text/html')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Everything else - stale-while-revalidate
  event.respondWith(staleWhileRevalidate(request));
});

// ========== BACKGROUND SYNC (for future offline form support) ==========
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.keys().then((names) => names.forEach((name) => caches.delete(name)));
  }
});
