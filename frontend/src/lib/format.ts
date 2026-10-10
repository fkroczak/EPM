/** Anzeige wie im Entwurf: deutsche Zahlen und Daten, Europe/Berlin. */

const TZ = "Europe/Berlin";

export function zahl(wert: number | string | null | undefined, stellen?: number): string {
  if (wert === null || wert === undefined || wert === "") return "—";
  const n = typeof wert === "string" ? Number(wert) : wert;
  if (Number.isNaN(n)) return String(wert);
  return n.toLocaleString("de-DE", stellen === undefined ? { maximumFractionDigits: 2 } : {
    minimumFractionDigits: stellen,
    maximumFractionDigits: stellen,
  });
}

export function kg(wert: number | string | null | undefined): string {
  return wert === null || wert === undefined || wert === "" ? "—" : `${zahl(wert, 1)} kg`;
}

export function prozent(wert: number | string | null | undefined, vorzeichen = true): string {
  if (wert === null || wert === undefined || wert === "") return "—";
  const n = Number(wert);
  const t = Math.abs(n).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (!vorzeichen) return `${t} %`;
  return `${n < 0 ? "−" : n > 0 ? "+" : "±"}${t} %`;
}

/** „2026-09-30“ oder ISO-Zeitpunkt → Date (Datum ohne Zeit als lokaler Tag) */
export function alsDatum(wert: string | Date | null | undefined): Date | null {
  if (!wert) return null;
  if (wert instanceof Date) return wert;
  if (/^\d{4}-\d{2}-\d{2}$/.test(wert)) {
    const [j, m, t] = wert.split("-").map(Number);
    return new Date(j, m - 1, t);
  }
  const d = new Date(wert);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function datum(wert: string | Date | null | undefined): string {
  const d = alsDatum(wert);
  if (!d) return "—";
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: istTag(wert) ? undefined : TZ });
}

function istTag(wert: string | Date | null | undefined) {
  return typeof wert === "string" && /^\d{4}-\d{2}-\d{2}$/.test(wert);
}

export function uhrzeit(wert: string | Date | null | undefined): string {
  if (typeof wert === "string" && /^\d{2}:\d{2}/.test(wert)) return wert.slice(0, 5);
  const d = alsDatum(wert);
  if (!d) return "";
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
}

export function zeitpunkt(wert: string | Date | null | undefined): string {
  const d = alsDatum(wert);
  if (!d) return "—";
  return `${datum(d)}, ${uhrzeit(d)}`;
}

function tagesSchluessel(d: Date) {
  return d.toLocaleDateString("sv-SE", { timeZone: TZ });
}

export function heuteIso(): string {
  return tagesSchluessel(new Date());
}

/** „heute, 09:14“, „gestern“, sonst Datum (mit Uhrzeit, falls gewünscht) */
export function relativ(wert: string | Date | null | undefined, mitZeit = false): string {
  const d = alsDatum(wert);
  if (!d) return "—";
  const heute = new Date();
  const gestern = new Date(heute.getTime() - 86400000);
  const tag = istTag(wert) ? (wert as string) : tagesSchluessel(d);
  if (tag === tagesSchluessel(heute)) return mitZeit && !istTag(wert) ? `heute, ${uhrzeit(d)}` : "heute";
  if (tag === tagesSchluessel(gestern)) return mitZeit && !istTag(wert) ? `gestern, ${uhrzeit(d)}` : "gestern";
  return mitZeit && !istTag(wert) ? zeitpunkt(d) : datum(d);
}

export function alter(geburtsdatum: string | null | undefined): number | null {
  const g = alsDatum(geburtsdatum);
  if (!g) return null;
  const h = new Date();
  let a = h.getFullYear() - g.getFullYear();
  if (h.getMonth() < g.getMonth() || (h.getMonth() === g.getMonth() && h.getDate() < g.getDate())) a -= 1;
  return a;
}

export function nummer(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : String(n).padStart(4, "0");
}

const WOCHENTAG = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

/** Für Termine: „Heute, 09:30“, „Do 01.10., 10:00“, „29.09., ganztägig“ */
export function terminZeit(faellig: string, uhr: string | null | undefined): string {
  const d = alsDatum(faellig);
  if (!d) return "—";
  const heute = heuteIso();
  const zeit = uhr ? uhr.slice(0, 5) : "ganztägig";
  if (faellig === heute) return `Heute, ${zeit}`;
  const kurz = d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  const inWoche = d.getTime() > Date.now() && d.getTime() - Date.now() < 7 * 86400000;
  return `${inWoche ? `${WOCHENTAG[d.getDay()]} ` : ""}${kurz}, ${zeit}`;
}

export function langesDatum(d = new Date()): string {
  return d.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: TZ });
}

/**
 * Eingabe „14.03.1968“ oder „1968-03-14“ → „1968-03-14“ (sonst null).
 * Nachsichtig wie auf Papier (Bedienung für Pflegekräfte, 10.10.2026): auch „14,3,68“ (Komma vom Ziffernblock),
 * „14/3/1968“, „14-3-1968“, „14 3 1968“, nur Ziffern „14031968“ bzw. „140368“ und die Wörter „heute“ und „gestern“.
 */
export function eingabeDatum(text: string): string | null {
  const t = text.trim().toLowerCase();
  if (/^\d{4}-\d{2}-\d{2}$/.test(t)) return t;
  if (t === "heute" || t === "gestern") {
    const d = new Date();
    if (t === "gestern") d.setDate(d.getDate() - 1);
    return tagesSchluessel(d);
  }
  const m = t.match(/^(\d{1,2})\s*[.,/\- ]\s*(\d{1,2})\s*[.,/\- ]\s*(\d{2}|\d{4})\.?$/)
    ?? t.match(/^(\d{2})(\d{2})(\d{4}|\d{2})$/);
  if (!m) return null;
  let jahr = Number(m[3]);
  if (m[3].length === 2) jahr += jahr > Number(String(new Date().getFullYear()).slice(2)) ? 1900 : 2000;
  const tag = Number(m[1]), monat = Number(m[2]);
  const d = new Date(jahr, monat - 1, tag);
  if (d.getFullYear() !== jahr || d.getMonth() !== monat - 1 || d.getDate() !== tag) return null;
  return `${jahr}-${String(monat).padStart(2, "0")}-${String(tag).padStart(2, "0")}`;
}

/** Uhrzeit „10:30“, auch „10.30“, „10,30“, „1030“, „930“ oder nur „10“ → „10:30“ bzw. „10:00“ (sonst null) */
export function eingabeUhrzeit(text: string): string | null {
  const t = text.trim().replace(/\s*uhr$/i, "");
  const m = t.match(/^(\d{1,2})(?:\s*[:.,h]\s*(\d{2}))?$/) ?? t.match(/^(\d{1,2})(\d{2})$/);
  if (!m) return null;
  const h = Number(m[1]), min = Number(m[2] ?? "0");
  if (h > 23 || min > 59) return null;
  return `${String(h).padStart(2, "0")}:${String(min).padStart(2, "0")}`;
}

/** Dezimaleingabe mit Komma → Zahl als String für die API („54,6“ → „54.6“) */
export function eingabeZahl(text: string): string | null {
  const t = text.trim().replace(/\s/g, "").replace(",", ".");
  if (t === "") return null;
  return /^-?\d+(\.\d+)?$/.test(t) ? t : "ungueltig";
}

export function dateigroesse(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${zahl(bytes / 1024 / 1024, 1)} MB`;
}

export function initialen(name: string): string {
  const teile = name.replace(/(Prof\.|Dr\.|med\.|Dipl\.-[^ ]+)/g, "").trim().split(/\s+/).filter(Boolean);
  return ((teile[0]?.[0] ?? "") + (teile.length > 1 ? teile[teile.length - 1][0] : "")).toUpperCase();
}

/** „vor 4 Monaten“, „vor 12 Tagen“, „heute“ – für den letzten Kontakt (Wiedereinbestellung, Schnellerfassung) */
export function vorZeit(wert: string | Date | null | undefined): string {
  const d = alsDatum(wert);
  if (!d) return "—";
  const tage = Math.floor((Date.now() - d.getTime()) / 86400000);
  if (tage < 1) return "heute";
  if (tage < 2) return "gestern";
  if (tage < 45) return `vor ${tage} Tagen`;
  const monate = Math.round((tage / 30.44) * 2) / 2;
  if (monate < 12) return `vor ${String(monate).replace(".5", "½")} Monaten`;
  const jahre = Math.floor(tage / 365.25);
  return jahre === 1 ? "vor über einem Jahr" : `vor über ${jahre} Jahren`;
}

/** Datum in ``tage`` Tagen als „TT.MM.JJJJ“ (Vorschläge für Wiedervorlagen) */
export function inTagen(tage: number): string {
  const d = new Date();
  d.setDate(d.getDate() + tage);
  return datum(d);
}

/** Datum in ``monate`` Monaten als „TT.MM.JJJJ“ */
export function inMonaten(monate: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() + monate);
  return datum(d);
}
