/**
 * Zugriff auf das Backend (/api). Sitzung über Cookie, CSRF-Token aus dem Cookie „epm_csrf“.
 * Fehler kommen als ApiFehler mit Status, Meldung und Feldfehlern.
 */

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

type Optionen = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  /** 403 „Anmeldung erforderlich“ nicht als Abmeldung behandeln (z. B. bei der Anmeldung selbst) */
  ohneAbmeldeSignal?: boolean;
};

export async function api<T = unknown>(pfad: string, opt: Optionen = {}): Promise<T> {
  const method = opt.method ?? (opt.body !== undefined || opt.form ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opt.form) {
    body = opt.form;
  } else if (opt.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opt.body);
  }
  if (method !== "GET") headers["X-CSRFToken"] = csrfToken();
  const url = pfad.startsWith("/api/") ? pfad : `/api/${pfad.replace(/^\//, "")}`;
  const antwort = await fetch(url, { method, headers, body, credentials: "same-origin", signal: opt.signal });
  if (antwort.status === 204) return undefined as T;
  const art = antwort.headers.get("Content-Type") ?? "";
  const daten: unknown = art.includes("application/json") ? await antwort.json().catch(() => null) : await antwort.text();
  if (!antwort.ok) {
    const objekt = (daten && typeof daten === "object" ? daten : {}) as Record<string, unknown>;
    const meldung =
      text(objekt.fehler) || text(objekt.detail) || text(objekt.non_field_errors) || MELDUNGEN[antwort.status] || "";
    const felder = flach(objekt);
    delete felder.fehler;
    delete felder.detail;
    const fehler = new ApiFehler(
      antwort.status,
      meldung || Object.values(felder)[0] || `Fehler ${antwort.status}`,
      daten,
      felder,
    );
    if (antwort.status === 403 && !opt.ohneAbmeldeSignal && /Anmeldung mit zweitem Faktor/.test(meldung)) {
      window.dispatchEvent(new Event(ABGEMELDET));
    }
    throw fehler;
  }
  return daten as T;
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
