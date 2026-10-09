/**
 * Zugriff auf das Backend (/api). Sitzung über Cookie, CSRF-Token aus dem Cookie „epm_csrf“.
 * Fehler kommen als ApiFehler mit Status, Meldung und Feldfehlern.
 */

import { anfrageBeginnt } from "./laden";

export type Feldfehler = Record<string, string>;

export class ApiFehler extends Error {
  status: number;
  daten: unknown;
  felder: Feldfehler;

  constructor(status: number, meldung: string, daten: unknown, felder: Feldfehler) {
    super(meldung);
    this.status = status;
    this.daten = daten;
    this.felder = felder;
  }
}

function csrfToken(): string {
  const treffer = document.cookie.match(/(?:^|;\s*)epm_csrf=([^;]+)/);
  return treffer ? decodeURIComponent(treffer[1]) : "";
}

function text(wert: unknown): string {
  if (wert == null) return "";
  if (typeof wert === "string") return wert;
  if (Array.isArray(wert)) return wert.map(text).filter(Boolean).join(" ");
  if (typeof wert === "object") return Object.values(wert as Record<string, unknown>).map(text).filter(Boolean).join(" ");
  return String(wert);
}

/** Feldfehler flach machen: {"wiedervorlage": {"faellig_am": ["…"]}} → {"wiedervorlage.faellig_am": "…"} */
function flach(daten: unknown, praefix = ""): Feldfehler {
  const aus: Feldfehler = {};
  if (!daten || typeof daten !== "object" || Array.isArray(daten)) return aus;
  for (const [k, v] of Object.entries(daten as Record<string, unknown>)) {
    const schluessel = praefix ? `${praefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) Object.assign(aus, flach(v, schluessel));
    else aus[schluessel] = text(v);
  }
  return aus;
}

const MELDUNGEN: Record<number, string> = {
  401: "Nicht angemeldet.",
  403: "Dafür fehlt das Recht.",
  404: "Nicht gefunden.",
  409: "Die Akte ist abgeschlossen und kann nicht mehr geändert werden.",
  429: "Zu viele Versuche. Bitte kurz warten.",
};

export const ABGEMELDET = "epm:abgemeldet";
/** Rechte haben sich geändert (Kopf ``X-EPM-Rechte`` anders als bisher oder Anfrage wegen fehlenden Rechts abgelehnt):
 *  die Anwendung lädt die eigenen Rechte neu und blendet nicht mehr erlaubte Aktionen aus. */
export const RECHTE_GEAENDERT = "epm:rechte-geaendert";
/** Kurzer Hinweis unten rechts von außerhalb einer Komponente (``detail`` = Text) */
export const HINWEIS = "epm:hinweis";
/** Neutrale Meldung, wenn eine Aktion nicht (mehr) erlaubt ist – ohne Rechte und Rollen aufzuzählen */
export const NICHT_VERFUEGBAR = "Diese Aktion steht nicht mehr zur Verfügung. Die Ansicht wurde aktualisiert.";

let rechteStand: string | null = null;

function rechteStandPruefen(antwort: Response) {
  const stand = antwort.headers.get("X-EPM-Rechte");
  if (!stand) return;
  if (rechteStand && stand !== rechteStand) window.dispatchEvent(new Event(RECHTE_GEAENDERT));
  rechteStand = stand;
}

function rechtAbgelehnt(method: string) {
  window.dispatchEvent(new Event(RECHTE_GEAENDERT));
  if (method !== "GET") window.dispatchEvent(new CustomEvent(HINWEIS, { detail: NICHT_VERFUEGBAR }));
}

/** 403 wegen fehlenden Rechts (nicht wegen abgelaufener Anmeldung) */
function rechtFehlt(status: number, meldung: string) {
  return status === 403 && /fehlt das Recht|Als Admin nur bei Testpatienten/.test(meldung);
}
/** Bei 401/403 prüft die Anwendung den Anmeldestatus (z. B. Sitzung nach 30 Minuten abgelaufen) */
export const STATUS_PRUEFEN = "epm:status-pruefen";

type Optionen = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  form?: FormData;
  /** Rohdaten (application/octet-stream), z. B. ein Stück einer großen Datei */
  roh?: Blob;
  signal?: AbortSignal;
  /** 403 „Anmeldung erforderlich“ nicht als Abmeldung behandeln (z. B. bei der Anmeldung selbst) */
  ohneAbmeldeSignal?: boolean;
  /** Antwort als Blob (z. B. ein Bild); Fehler kommen weiter als JSON */
  alsBlob?: boolean;
};

export async function api<T = unknown>(pfad: string, opt: Optionen = {}): Promise<T> {
  const method = opt.method ?? (opt.body !== undefined || opt.form || opt.roh ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opt.form) {
    body = opt.form;
  } else if (opt.roh) {
    headers["Content-Type"] = "application/octet-stream";
    body = opt.roh;
  } else if (opt.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opt.body);
  }
  if (method !== "GET") headers["X-CSRFToken"] = csrfToken();
  const url = pfad.startsWith("/api/") ? pfad : `/api/${pfad.replace(/^\//, "")}`;
  const ende = anfrageBeginnt();   // Ladebalken am oberen Rand (F124)
  let antwort: Response;
  try {
    antwort = await fetch(url, { method, headers, body, credentials: "same-origin", signal: opt.signal });
  } finally {
    ende();
  }
  rechteStandPruefen(antwort);
  if (antwort.status === 204) return undefined as T;
  if (opt.alsBlob && antwort.ok) return (await antwort.blob()) as T;
  const art = antwort.headers.get("Content-Type") ?? "";
  const daten: unknown = art.includes("application/json") ? await antwort.json().catch(() => null) : await antwort.text();
  if (!antwort.ok) {
    const objekt = (daten && typeof daten === "object" ? daten : {}) as Record<string, unknown>;
    const meldung =
      text(objekt.fehler) || text(objekt.detail) || text(objekt.non_field_errors) || MELDUNGEN[antwort.status] || "";
    const felder = flach(objekt);
    delete felder.fehler;
    delete felder.detail;
    if (rechtFehlt(antwort.status, meldung)) {
      // Was jemand nicht darf, soll er nicht sehen: Rechte neu laden (Aktion verschwindet), bei Aktionen neutral melden
      rechtAbgelehnt(method);
      throw new ApiFehler(antwort.status, NICHT_VERFUEGBAR, daten, {});
    }
    const fehler = new ApiFehler(
      antwort.status,
      meldung || Object.values(felder)[0] || `Fehler ${antwort.status}`,
      daten,
      felder,
    );
    if ((antwort.status === 401 || antwort.status === 403) && !opt.ohneAbmeldeSignal) {
      window.dispatchEvent(new Event(/Anmeldung mit zweitem Faktor/.test(meldung) ? ABGEMELDET : STATUS_PRUEFEN));
    }
    throw fehler;
  }
  return daten as T;
}

/** Datei (z. B. PDF) holen – mit Antwortköpfen und denselben Fehlermeldungen wie ``api``. */
export async function apiDatei(pfad: string, opt: Optionen = {}): Promise<{ daten: Uint8Array; kopf: Headers }> {
  const method = opt.method ?? (opt.body !== undefined ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/pdf, application/json" };
  let body: BodyInit | undefined;
  if (opt.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opt.body);
  }
  if (method !== "GET") headers["X-CSRFToken"] = csrfToken();
  const url = pfad.startsWith("/api/") ? pfad : `/api/${pfad.replace(/^\//, "")}`;
  const ende = anfrageBeginnt();   // Ladebalken am oberen Rand (F124)
  let antwort: Response;
  try {
    antwort = await fetch(url, { method, headers, body, credentials: "same-origin", signal: opt.signal });
  } finally {
    ende();
  }
  rechteStandPruefen(antwort);
  if (!antwort.ok) {
    const daten: unknown = await antwort.json().catch(() => null);
    const objekt = (daten && typeof daten === "object" ? daten : {}) as Record<string, unknown>;
    const felder = flach(objekt);
    delete felder.fehler;
    delete felder.detail;
    const meldung = text(objekt.fehler) || text(objekt.detail) || Object.values(felder)[0] || MELDUNGEN[antwort.status] || `Fehler ${antwort.status}`;
    if (rechtFehlt(antwort.status, meldung)) {
      rechtAbgelehnt(method);
      throw new ApiFehler(antwort.status, NICHT_VERFUEGBAR, daten, {});
    }
    if ((antwort.status === 401 || antwort.status === 403) && !opt.ohneAbmeldeSignal) {
      window.dispatchEvent(new Event(/Anmeldung mit zweitem Faktor/.test(meldung) ? ABGEMELDET : STATUS_PRUEFEN));
    }
    throw new ApiFehler(antwort.status, meldung, daten, felder);
  }
  return { daten: new Uint8Array(await antwort.arrayBuffer()), kopf: antwort.headers };
}

export type Seite<T> = { count: number; next: string | null; previous: string | null; results: T[] };

/** Alle Seiten einer Liste holen (für kleine Mengen wie Gewichte einer Akte). */
export async function alle<T>(pfad: string): Promise<T[]> {
  const trenner = pfad.includes("?") ? "&" : "?";
  const erste = await api<Seite<T> | T[]>(`${pfad}${trenner}seitengroesse=2000`);
  if (Array.isArray(erste)) return erste;
  const ergebnis = [...erste.results];
  let naechste = erste.next;
  while (naechste) {
    const u = new URL(naechste, window.location.origin);
    const seite = await api<Seite<T>>(u.pathname + u.search);
    ergebnis.push(...seite.results);
    naechste = seite.next;
  }
  return ergebnis;
}

export function abfrage(werte: Record<string, string | number | boolean | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(werte)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}
