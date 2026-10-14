/**
 * Freie Gestaltung am Raster (14.10.2026): 6-Spalten-Raster, Kopf- und Fußband, Anschriftfeld nach DIN 5008.
 * Dieselben Maße wie auf dem Server (backend/vorlagen/gestaltung.py), damit die Seite im Editor wie die PDF aussieht.
 *
 * Ein Block steht von Spalte raster_von bis raster_bis (ohne Angabe über die ganze Breite); neben_vorherigem „raster“
 * setzt ihn in die Zeile des vorherigen Blocks. Ältere Vorlagen (Drittel/Hälfte/zwei Drittel) rechnet insRaster um.
 */
export const SPALTEN = 6;
export const ABSTAND = 2.8; // % der Breite
export const SPALTE = (100 - (SPALTEN - 1) * ABSTAND) / SPALTEN;
/** 1 mm auf der Seite des Editors (A4 hoch = 35rem = 560 px) */
export const MM = 560 / 210;
export const RAND_LINKS = 17;
export const RAND_OBEN = 15;
export const BAND_ABSTAND = 6;

export const rasterLinks = (von: number) => (von - 1) * (SPALTE + ABSTAND);
export const rasterBreite = (von: number, bis: number) => (bis - von + 1) * SPALTE + (bis - von) * ABSTAND;

/** Diese Blöcke lassen sich im Raster schmaler setzen und nebeneinander stellen (wie auf dem Server) */
export const RASTER_TYPEN = ["text", "datenfelder", "tabelle", "unterschrift", "titel", "kopfkarte", "zweispaltig"];
const ALT: Record<string, number> = { drittel: 2, haelfte: 3, zwei_drittel: 4 };

type RasterOptionen = { neben_vorherigem?: string; raster_von?: number; raster_bis?: number };
type RasterBlock = { id: string; typ: string; optionen?: RasterOptionen };

export const imRaster = (b: RasterBlock) => RASTER_TYPEN.includes(b.typ);
export function vonBis(b: RasterBlock): [number, number] {
  return [b.optionen?.raster_von ?? 1, b.optionen?.raster_bis ?? SPALTEN];
}
const neben = (b: RasterBlock) => !!b.optionen?.neben_vorherigem;

/** Zeilen der Seite als Indizes: ein Block mit „neben_vorherigem“ gehört in die Zeile davor */
export function zeilen(bloecke: RasterBlock[]): number[][] {
  const z: number[][] = [];
  bloecke.forEach((b, i) => {
    if (neben(b) && z.length) z[z.length - 1].push(i);
    else z.push([i]);
  });
  return z;
}

function mitOptionen<T extends RasterBlock>(b: T, neu: RasterOptionen): T {
  const o: Record<string, unknown> = { ...b.optionen, ...neu };
  for (const k of Object.keys(o)) if (o[k] === undefined) delete o[k];
  if (o.raster_von === 1 && o.raster_bis === SPALTEN && !o.neben_vorherigem) { delete o.raster_von; delete o.raster_bis; }
  return { ...b, optionen: Object.keys(o).length ? o : undefined };
}

/** Ältere Vorlagen: „neben dem vorherigen, ein Drittel/die Hälfte/zwei Drittel breit“ → Spalten im Raster */
export function insRaster<T extends RasterBlock>(bloecke: T[]): T[] {
  const neu = [...bloecke];
  for (const z of zeilen(bloecke)) {
    if (!z.slice(1).some((i) => (bloecke[i].optionen?.neben_vorherigem ?? "") in ALT)) continue;
    let rechts = z.slice(1).map((i) => ALT[bloecke[i].optionen?.neben_vorherigem ?? ""] ?? 3);
    let erste = SPALTEN - rechts.reduce((x, y) => x + y, 0);
    if (erste < 1) { // zu schmal: gleich verteilen, wie bisher auf dem Server
      const w = Math.max(1, Math.floor(SPALTEN / z.length));
      rechts = rechts.map(() => w);
      erste = w;
    }
    let von = 1;
    [erste, ...rechts].forEach((w, j) => {
      neu[z[j]] = mitOptionen(neu[z[j]], { raster_von: von, raster_bis: Math.min(SPALTEN, von + w - 1), neben_vorherigem: j ? "raster" : undefined });
      von += w;
    });
  }
  return neu;
}

/** Hält die Zeilen gültig: „in derselben Zeile“ nur hinter einem Rasterblock und ohne Überdeckung */
export function ordne<T extends RasterBlock>(bloecke: T[]): T[] {
  let geaendert = false;
  const neu = bloecke.map((b, i) => {
    if (!neben(b)) return b;
    const vorher = bloecke[i - 1];
    const ok = vorher && imRaster(b) && imRaster(vorher) && vonBis(vorher)[1] < vonBis(b)[0];
    if (ok) return b;
    geaendert = true;
    return mitOptionen(b, { neben_vorherigem: undefined });
  });
  return geaendert ? neu : bloecke;
}

/** Wohin ein gezogener Block kommt: als neue Zeile vor einer Zeile (null = ans Ende) oder in eine Zeile an Spalten */
export type Ziel = { art: "zeile"; vorId: string | null } | { art: "neben"; zeileIds: string[]; von: number; bis: number };

/** Freier Platz in einer Zeile an Spalte ``spalte`` für einen Block der Breite ``breite`` → [von, bis] oder null */
export function freierPlatz(belegt: [number, number][], spalte: number, breite: number): [number, number] | null {
  const frei = (s: number) => s >= 1 && s <= SPALTEN && !belegt.some(([v, b]) => s >= v && s <= b);
  if (!frei(spalte)) return null;
  let links = spalte;
  while (frei(links - 1)) links -= 1;
  let rechts = spalte;
  while (frei(rechts + 1)) rechts += 1;
  const w = Math.min(breite, rechts - links + 1);
  let von = Math.max(links, Math.min(spalte, rechts - w + 1));
  if (von + w - 1 > rechts) von = rechts - w + 1;
  return [von, von + w - 1];
}

/** Block ``id`` (oder einen neuen Block) an das Ziel setzen */
export function setze<T extends RasterBlock>(bloecke: T[], id: string | null, neuerBlock: T | null, ziel: Ziel): T[] {
  let b = id ? bloecke.find((x) => x.id === id) : neuerBlock;
  if (!b) return bloecke;
  let liste = id ? bloecke.filter((x) => x.id !== id) : [...bloecke];
  liste = ordne(liste); // war der Block der erste einer Zeile, beginnt sie jetzt mit dem nächsten
  if (ziel.art === "zeile") {
    const nach = ziel.vorId ? liste.findIndex((x) => x.id === ziel.vorId) : -1;
    b = mitOptionen(b, { neben_vorherigem: undefined });
    liste.splice(nach >= 0 ? nach : liste.length, 0, b);
    return ordne(liste);
  }
  const mitglieder = ziel.zeileIds.filter((x) => x !== id);
  const stellen = mitglieder.map((m) => liste.findIndex((x) => x.id === m)).filter((i) => i >= 0).sort((x, y) => x - y);
  if (!stellen.length) return bloecke;
  // vor das erste Mitglied, das weiter rechts beginnt
  const davor = stellen.find((i) => vonBis(liste[i])[0] > ziel.von);
  const stelle = davor ?? stellen[stellen.length - 1] + 1;
  const erstes = stelle === stellen[0];
  b = mitOptionen(b, { raster_von: ziel.von, raster_bis: ziel.bis, neben_vorherigem: erstes ? undefined : "raster" });
  if (erstes) liste[stellen[0]] = mitOptionen(liste[stellen[0]], { neben_vorherigem: "raster" });
  liste.splice(stelle, 0, b);
  return ordne(liste);
}

/** Breite eines Blocks am Rand ändern; rastet an den Spalten ein und bleibt zwischen den Nachbarn der Zeile */
export function ziehRand<T extends RasterBlock>(bloecke: T[], id: string, seite: "links" | "rechts", prozent: number): T[] {
  const i = bloecke.findIndex((x) => x.id === id);
  if (i < 0) return bloecke;
  const z = zeilen(bloecke).find((r) => r.includes(i)) ?? [i];
  const j = z.indexOf(i);
  const [von, bis] = vonBis(bloecke[i]);
  const min = j > 0 ? vonBis(bloecke[z[j - 1]])[1] + 1 : 1;
  const max = j < z.length - 1 ? vonBis(bloecke[z[j + 1]])[0] - 1 : SPALTEN;
  const naechste = (pos: (n: number) => number) =>
    Array.from({ length: SPALTEN }, (_, n) => n + 1).reduce((best, n) => (Math.abs(pos(n) - prozent) < Math.abs(pos(best) - prozent) ? n : best), 1);
  const neu = [...bloecke];
  if (seite === "rechts") {
    const n = Math.min(max, Math.max(von, naechste((x) => rasterLinks(x) + SPALTE)));
    if (n === bis) return bloecke;
    neu[i] = mitOptionen(bloecke[i], { raster_von: von, raster_bis: n });
  } else {
    const n = Math.max(min, Math.min(bis, naechste(rasterLinks)));
    if (n === von) return bloecke;
    neu[i] = mitOptionen(bloecke[i], { raster_von: n, raster_bis: bis });
  }
  return neu;
}

export function setzeRaster<T extends RasterBlock>(b: T, neu: RasterOptionen): T {
  return mitOptionen(b, neu);
}

// ------------------------------------------------------------------------------------------------ Kopf- und Fußband
export type Bandform = "gerade" | "schraeg" | "welle" | "bogen";
export const FORMEN: { wert: Bandform; text: string }[] = [
  { wert: "gerade", text: "Eckig" }, { wert: "schraeg", text: "Schräg" }, { wert: "welle", text: "Wellig" }, { wert: "bogen", text: "Bogen" },
];
export const schwung = (hoehe: number, fuss = false) => Math.min(fuss ? 6 : 10, hoehe * 0.3);

/** Fläche von oben bis zur Unterkante (wie gestaltung.band_pfad) */
export function bandPfad(form: string, w: number, h: number, a: number): string {
  const f = (x: number) => x.toFixed(2);
  if (form === "schraeg") return `M0 0 H${w} V${f(h - a)} L0 ${h} Z`;
  if (form === "welle") {
    const m = h - a / 2, d = (a * 2) / 3;
    return `M0 0 H${w} V${f(m)} C${f((w * 5) / 6)} ${f(m + d)} ${f((w * 4) / 6)} ${f(m + d)} ${f(w / 2)} ${f(m)} S${f(w / 6)} ${f(m - d)} 0 ${f(m)} Z`;
  }
  if (form === "bogen") return `M0 0 H${w} V${f(h - a)} Q${f(w / 2)} ${f(h + a)} 0 ${f(h - a)} Z`;
  return `M0 0 H${w} V${h} H0 Z`;
}

/** Farben zum schnellen Wählen: Firmenfarben und ruhige Töne */
export const BANDFARBEN = ["#BDC9C2", "#251F53", "#EE8D4D", "#E8E6F2", "#00325A", "#F4EFE6"];

// ------------------------------------------------------------------------------------------------ DIN 5008
export const DIN = {
  A: { oben: 27, info_oben: 32, text_ab: 80.46 },
  B: { oben: 45, info_oben: 50, text_ab: 98.46 },
} as const;
export const DIN_LINKS = 20, DIN_BREITE = 85, DIN_HOEHE = 45, DIN_INFO_LINKS = 125, DIN_INFO_BREITE = 75;
