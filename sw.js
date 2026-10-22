// Service Worker für Gravelfinder Big Enduro.
// Hält nur die App selbst (Seite, Symbole, Leaflet) vor, damit sie auch ohne Netz startet.
// Karten-Kacheln, Schotter-Daten, Overpass und BRouter laufen unverändert übers Netz
// (die Schotter-Daten speichert die App ohnehin selbst in IndexedDB).
var CACHE = 'gravelfinder-app-v1';
var SHELL = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './icon-maskable-512.png', './apple-touch-icon.png'];
var LEAFLET = 'https://unpkg.com/leaflet@1.9.4/';

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);

  // Leaflet: einmal laden, danach aus dem Speicher (Version ist fix)
  if (req.url.indexOf(LEAFLET) === 0) {
    e.respondWith(caches.match(req).then(function (hit) {
      return hit || fetch(req).then(function (res) {
        if (res.ok) { var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req, copy); }); }
        return res;
      });
    }));
    return;
  }

  // Eigene App-Dateien: zuerst Netz (immer aktuell), ohne Netz die gespeicherte Fassung
  var scope = new URL(self.registration.scope);
  if (url.origin !== scope.origin || url.pathname.indexOf(scope.pathname) !== 0) return;
  var rel = url.pathname.slice(scope.pathname.length);
  if (rel.indexOf('data/') === 0) return; // Schotter-Daten: nicht anfassen
  var isShell = req.mode === 'navigate' || SHELL.indexOf('./' + rel) >= 0 || rel === '';
  if (!isShell) return;
  e.respondWith(fetch(req).then(function (res) {
    if (res.ok) { var copy = res.clone(); caches.open(CACHE).then(function (c) { c.put(req.mode === 'navigate' ? './index.html' : req, copy); }); }
    return res;
  }).catch(function () {
    return caches.match(req.mode === 'navigate' ? './index.html' : req).then(function (hit) { return hit || caches.match('./'); });
  }));
});
