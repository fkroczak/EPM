// Prüfserver wie Nginx im Betrieb (rollout/projekt/nginx/epm.conf): HTTP/2 + TLS, /assets/ 1 Jahr im Cache und gzip,
// index.html ohne Cache, /api an gunicorn. Aufruf: node server.mjs <dist> <port> <backendPort>
import http2 from "node:http2";
import http from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join, extname } from "node:path";

const [dist, port, backend] = process.argv.slice(2);
const TYPEN = { ".js": "application/javascript", ".css": "text/css", ".html": "text/html; charset=utf-8",
  ".svg": "image/svg+xml", ".woff2": "font/woff2", ".woff": "font/woff", ".png": "image/png", ".json": "application/json",
  ".mjs": "application/javascript", ".wasm": "application/wasm" };
const KOMPRIMIEREN = new Set([".js", ".css", ".html", ".svg", ".json", ".mjs"]);
const zwischen = new Map();

function datei(pfad) {
  if (zwischen.has(pfad)) return zwischen.get(pfad);
  const roh = readFileSync(pfad);
  const ext = extname(pfad);
  const e = { roh, gz: KOMPRIMIEREN.has(ext) && roh.length > 1024 ? gzipSync(roh, { level: 5 }) : null, typ: TYPEN[ext] ?? "application/octet-stream" };
  zwischen.set(pfad, e);
  return e;
}

const server = http2.createSecureServer({
  key: readFileSync("/var/tmp/mess/tls.key"), cert: readFileSync("/var/tmp/mess/tls.crt"), allowHTTP1: true,
}, (req, res) => {
  const url = req.url;
  if (url.startsWith("/api/")) {
    const kopf = { ...req.headers, host: req.headers[":authority"] ?? req.headers.host, "x-forwarded-proto": "https" };
    for (const k of Object.keys(kopf)) if (k.startsWith(":")) delete kopf[k];
    const p = http.request({ host: "127.0.0.1", port: backend, path: url, method: req.method, headers: kopf }, (a) => {
      const h = { ...a.headers };
      delete h.connection; delete h["transfer-encoding"]; delete h["keep-alive"];
      res.writeHead(a.statusCode, h);
      a.pipe(res);
    });
    p.on("error", () => { res.writeHead(502); res.end(); });
    req.pipe(p);
    return;
  }
  let pfad = join(dist, decodeURIComponent(url.split("?")[0]));
  let asset = url.startsWith("/assets/");
  if (!existsSync(pfad) || statSync(pfad).isDirectory()) { pfad = join(dist, "index.html"); asset = false; }
  const d = datei(pfad);
  const gz = d.gz && /gzip/.test(req.headers["accept-encoding"] ?? "");
  const h = { "content-type": d.typ, "cache-control": asset ? "max-age=31536000" : "no-cache" };
  if (gz) h["content-encoding"] = "gzip";
  res.writeHead(200, h);
  res.end(gz ? d.gz : d.roh);
});
server.listen(Number(port), "127.0.0.1");
