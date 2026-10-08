/*
 * EPM – Service Worker für die Installation als App (PWA, Festlegung 08.10.2026).
 *
 * Datenschutz: Zwischengespeichert werden NUR die unveränderlichen Programmdateien (/assets/ mit Prüfsumme im Namen,
 * pdf.js-Dateien, Symbole) und die Seite „Keine Verbindung“. Antworten der API, Dokumente, PDFs, Sicherungen und
 * index.html werden nie gespeichert – auf dem Gerät liegen keine Patientendaten.
 *
 * Seiten (Navigation) kommen immer frisch vom Server; ohne Verbindung (kein VPN) erscheint /offline.html.
 */
const VERSION = "epm-pwa-1";
const STATISCH = `${VERSION}-statisch`;
const OFFLINE = "/offline.html";
const VORAB = [OFFLINE, "/icons/epm-192.png", "/favicon.svg"];
const HOECHSTENS = 300;   // Einträge im Zwischenspeicher; ältere Programmstände fallen heraus

self.addEventListener("install", (ereignis) => {
  ereignis.waitUntil(caches.open(STATISCH).then((c) => c.addAll(VORAB)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (ereignis) => {
  ereignis.waitUntil((async () => {
    for (const name of await caches.keys()) if (!name.startsWith(VERSION)) await caches.delete(name);
    await self.clients.claim();
  })());
});

function statisch(url) {
  return url.origin === self.location.origin
    && (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/pdfjs/") || url.pathname.startsWith("/icons/")
      || url.pathname === "/favicon.svg");
}

async function aufraeumen(cache) {
  const schluessel = await cache.keys();
  for (let i = 0; i < schluessel.length - HOECHSTENS; i++) await cache.delete(schluessel[i]);
}

self.addEventListener("fetch", (ereignis) => {
  const anfrage = ereignis.request;
  if (anfrage.method !== "GET") return;
  const url = new URL(anfrage.url);
  if (url.origin !== self.location.origin) return;

  if (anfrage.mode === "navigate") {
    // immer vom Server (Anmeldung, aktuelle Version); nur ohne Verbindung die Hinweisseite
    ereignis.respondWith(fetch(anfrage).catch(async () => (await caches.match(OFFLINE)) || Response.error()));
    return;
  }
  if (!statisch(url)) return;   // API, Dokumente, Manifest, sw.js: am Service Worker vorbei

  ereignis.respondWith((async () => {
    const cache = await caches.open(STATISCH);
    const vorhanden = await cache.match(anfrage);
    if (vorhanden) return vorhanden;
    const antwort = await fetch(anfrage);
    if (antwort.ok && antwort.type === "basic") {
      await cache.put(anfrage, antwort.clone());
      aufraeumen(cache);
    }
    return antwort;
  })());
});
