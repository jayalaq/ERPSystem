// NexusERP Service Worker - Peru E-Invoicing PWA
// Facturacion Electronica SUNAT - Odoo Enterprise Pattern
const CACHE_VERSION = 'nexuserp-v3';
const PRECACHE_NAME = CACHE_VERSION + '-precache';
const RUNTIME_NAME = CACHE_VERSION + '-runtime';
const INVOICING_NAME = CACHE_VERSION + '-invoicing';
const OFFLINE_URL = '/offline/';

// IndexedDB for offline invoice queue
const DB_NAME = 'nexuserp_offline';
const DB_VERSION = 1;
const QUEUE_STORE = 'invoice_queue';
const DRAFT_STORE = 'invoice_drafts';

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(DRAFT_STORE)) {
        db.createObjectStore(DRAFT_STORE, { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// Save failed POST requests for later retry
async function saveToQueue(url, body, headers) {
  const db = await openDB();
  const tx = db.transaction(QUEUE_STORE, 'readwrite');
  tx.objectStore(QUEUE_STORE).add({
    url: url,
    body: body,
    headers: Object.fromEntries(headers.entries()),
    timestamp: Date.now(),
  });
  return new Promise((resolve) => { tx.oncomplete = resolve; });
}

// Replay queued requests when back online
async function replayQueue() {
  const db = await openDB();
  const tx = db.transaction(QUEUE_STORE, 'readonly');
  const store = tx.objectStore(QUEUE_STORE);
  const items = await new Promise((resolve) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
  });

  for (const item of items) {
    try {
      const response = await fetch(item.url, {
        method: 'POST',
        headers: item.headers,
        body: item.body,
      });
      if (response.ok) {
        const deleteTx = db.transaction(QUEUE_STORE, 'readwrite');
        deleteTx.objectStore(QUEUE_STORE).delete(item.id);
      }
    } catch (e) {
      // Still offline, stop trying
      break;
    }
  }

  // Notify all clients about sync results
  const clients = await self.clients.matchAll();
  clients.forEach((client) => {
    client.postMessage({ type: 'QUEUE_SYNCED', remaining: items.length });
  });
}

// Core assets to precache on install
const PRECACHE_URLS = [
  OFFLINE_URL,
  '/static/pwa/icons/icon-192x192.png',
  '/static/pwa/icons/icon-512x512.png',
];

// Critical invoicing pages to cache proactively
const INVOICING_URLS = [
  '/accounting/invoices/',
  '/accounting/invoices/new/',
  '/pos/',
  '/accounting/document-series/',
];

// ========== INSTALL ==========
self.addEventListener('install', (event) => {
  event.waitUntil(
    Promise.all([
      caches.open(PRECACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)),
      caches.open(INVOICING_NAME).then((cache) => {
        // Best-effort cache invoicing pages (may fail if not logged in)
        return Promise.allSettled(
          INVOICING_URLS.map((url) =>
            fetch(url, { credentials: 'same-origin' })
              .then((r) => r.ok ? cache.put(url, r) : null)
              .catch(() => null)
          )
        );
      }),
    ]).then(() => self.skipWaiting())
  );
});

// ========== ACTIVATE ==========
self.addEventListener('activate', (event) => {
  const currentCaches = [PRECACHE_NAME, RUNTIME_NAME, INVOICING_NAME];
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
      caches.match(request)
        .then((cached) => cached || caches.open(INVOICING_NAME).then((c) => c.match(request)))
        .then((cached) => cached || caches.match(OFFLINE_URL))
    );
}

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

  // Handle offline POST queue for invoicing operations
  if (request.method === 'POST' && url.origin === self.location.origin) {
    // Queue SUNAT and invoice POSTs when offline
    if (
      url.pathname.includes('/send-sunat/') ||
      url.pathname.includes('/process-sale/') ||
      url.pathname.includes('/invoices/new/')
    ) {
      event.respondWith(
        fetch(request.clone()).catch(async () => {
          const body = await request.text();
          await saveToQueue(url.href, body, request.headers);
          return new Response(
            JSON.stringify({
              status: 'queued',
              message: 'Sin conexion. La operacion se enviara automaticamente cuando vuelvas a estar en linea.',
            }),
            {
              status: 202,
              headers: { 'Content-Type': 'application/json' },
            }
          );
        })
      );
      return;
    }
    return;
  }

  // Skip non-GET and cross-origin
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  // Skip admin panel
  if (url.pathname.startsWith('/admin/')) return;

  // API calls - network only with offline queue notification
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request).catch(() =>
        new Response(
          JSON.stringify({ error: 'offline', message: 'Sin conexion a Internet' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        )
      )
    );
    return;
  }

  // SUNAT endpoints - network-first (critical, can't serve stale data)
  if (url.pathname.startsWith('/sunat/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Invoicing pages - network-first with invoicing cache fallback
  if (url.pathname.startsWith('/accounting/') || url.pathname.startsWith('/pos/')) {
    event.respondWith(networkFirst(request));
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

// ========== BACKGROUND SYNC ==========
self.addEventListener('sync', (event) => {
  if (event.tag === 'invoice-queue-sync') {
    event.waitUntil(replayQueue());
  }
});

// ========== MESSAGE HANDLER ==========
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.keys().then((names) => names.forEach((name) => caches.delete(name)));
  }
  if (event.data && event.data.type === 'REPLAY_QUEUE') {
    replayQueue();
  }
  if (event.data && event.data.type === 'GET_QUEUE_COUNT') {
    openDB().then((db) => {
      const tx = db.transaction(QUEUE_STORE, 'readonly');
      const req = tx.objectStore(QUEUE_STORE).count();
      req.onsuccess = () => {
        event.source.postMessage({ type: 'QUEUE_COUNT', count: req.result });
      };
    });
  }
});

// ========== ONLINE RECOVERY ==========
// When connection is restored, auto-replay queued invoices
self.addEventListener('online', () => {
  replayQueue();
});
