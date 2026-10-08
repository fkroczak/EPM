/**
 * Darstellung je Person (Entwurf 14 · Mein Konto): Schema, Akzent, Hintergrund, Dichte, Schrift.
 * Die Regeln für eigene Farben entsprechen der Prüfung im Backend (Kontrast ≥ 4,5:1, Hintergrund hell genug).
 */

export type Darstellung = {
  schema: "standard" | "individuell" | "kontrast" | "dunkel";
  auto_dunkel: boolean;
  akzent: string;
  akzent_eigen?: string;
  hintergrund: string;
  hintergrund_eigen?: string;
  dichte: "grosszuegig" | "normal" | "kompakt" | "sehrkompakt";
  schriftgroesse: "klein" | "normal" | "gross" | "sehrgross";
  schriftstaerke: "normal" | "kraeftig";
  /** Aufbau der Patientenakte (Wunsch 08.10.2026) */
  aktenansicht: Aktenansicht;
  /** Höhe des Aktenkopfs in der Ansicht „Kopfzeile“: nur Name, eine Zeile Kennzahlen oder alle Gruppen */
  aktenkopf: "minimal" | "kompakt" | "voll";
  /** Breite der Seitenleiste in der Ansicht „Seitenleiste“ (px) */
  aktenleiste_breite: number;
};

export type Aktenansicht = "kopfzeile" | "seitenleiste" | "karteikarte";

/** Grenzen und Einrastpunkte der Seitenleiste der Akte (wie im Backend: 240–480 px) */
export const AKTENLEISTE = { min: 240, max: 480, standard: 300, punkte: [240, 300, 360, 420, 480] };

export const STANDARD_DARSTELLUNG: Darstellung = {
  schema: "standard",
  auto_dunkel: false,
  akzent: "nachtblau",
  akzent_eigen: "",
  hintergrund: "hellgrau",
  hintergrund_eigen: "",
  dichte: "normal",
  schriftgroesse: "normal",
  schriftstaerke: "normal",
  aktenansicht: "kopfzeile",
  aktenkopf: "voll",
  aktenleiste_breite: AKTENLEISTE.standard,
};

export const AKZENTE: Record<string, [string, string]> = {
  nachtblau: ["Nachtblau", "#251F53"],
  petrol: ["Petrol", "#0A6A86"],
  blau: ["Blau", "#1F4E99"],
  gruen: ["Tannengrün", "#1F6B4F"],
  orange: ["Stiftungsorange", "#ED6D3C"],
  aubergine: ["Aubergine", "#5B2A5E"],
  schiefer: ["Schiefer", "#3F4A56"],
};

export const HINTERGRUENDE: Record<string, [string, string]> = {
  weissgrau: ["Weißgrau", "#FAFAFB"],
  hellgrau: ["Hellgrau", "#F3F4F6"],
  grau: ["Grau", "#EAEBEF"],
  kraeftig: ["Kräftig", "#E0E1E7"],
  blaugrau: ["Blaugrau", "#EAF0F2"],
  sand: ["Sand", "#F3F1EC"],
};

export const INK = "#1B1932";

function kanal(x: number) {
  const v = x / 255;
  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

export function luminanz(hex: string): number {
  const c = [1, 3, 5].map((i) => kanal(parseInt(hex.substr(i, 2), 16)));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

export function kontrast(a: string, b: string): number {
  const x = luminanz(a), y = luminanz(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

export function istHex(wert: string | undefined): wert is string {
  return !!wert && /^#[0-9A-Fa-f]{6}$/.test(wert);
}

function dunkler(hex: string, f: number) {
  return "#" + [1, 3, 5].map((i) => Math.round(parseInt(hex.substr(i, 2), 16) * f).toString(16).padStart(2, "0")).join("").toUpperCase();
}

function farbton(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.substr(i, 2), 16) / 255);
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  if (max === min) return 0;
  const d = max - min;
  let h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return Math.round(h * 60);
}

/** Schriftfarbe auf der Akzentfarbe (weiß oder dunkel) oder null, wenn keine lesbar ist */
export function aufAkzent(hex: string): string | null {
  if (kontrast(hex, "#FFFFFF") >= 4.5) return "#FFFFFF";
  if (kontrast(hex, INK) >= 4.5) return INK;
  return null;
}

export function akzentHex(d: Darstellung): string {
  return d.akzent === "eigen" && istHex(d.akzent_eigen) ? d.akzent_eigen : (AKZENTE[d.akzent] ?? AKZENTE.nachtblau)[1];
}

export function hintergrundHex(d: Darstellung): string {
  return d.hintergrund === "eigen" && istHex(d.hintergrund_eigen) ? d.hintergrund_eigen : (HINTERGRUENDE[d.hintergrund] ?? HINTERGRUENDE.hellgrau)[1];
}

/** CSS-Variablen für „Individuell“: Akzent, Hintergrund und dazu passend getönte Grautöne */
export function individuelleFarben(d: Darstellung): Record<string, string> {
  let roh = akzentHex(d);
  let auf = aufAkzent(roh);
  if (!auf) {
    roh = AKZENTE.nachtblau[1];
    auf = "#FFFFFF";
  }
  let text = roh;
  for (let f = 0.95; kontrast(text, "#FFFFFF") < 4.5 && f > 0.3; f -= 0.05) text = dunkler(roh, f);
  let grund = hintergrundHex(d);
  if (luminanz(grund) < 0.6) grund = HINTERGRUENDE.hellgrau[1];
  const h = farbton(roh);
  return {
    "--akzent": roh,
    "--akzent-text": text,
    "--akzent-hover": dunkler(roh, 0.8),
    "--akzent-weich": `hsl(${h} 45% 92%)`,
    "--auf-akzent": auf,
    "--grund": grund,
    "--tinte": `hsl(${h} 36% 13%)`,
    "--text2": `hsl(${h} 19% 26%)`,
    "--gedaempft": `hsl(${h} 12% 39%)`,
    "--rand": `hsl(${h} 15% 85%)`,
    "--fein": `hsl(${h} 22% 91%)`,
  };
}

const INDIVIDUELL_VARIABLEN = ["--akzent", "--akzent-text", "--akzent-hover", "--akzent-weich", "--auf-akzent", "--grund",
  "--tinte", "--text2", "--gedaempft", "--rand", "--fein"];

let dunkelAbfrage: MediaQueryList | null = null;
let aktuell: Darstellung = STANDARD_DARSTELLUNG;

function anwenden() {
  const wurzel = document.documentElement;
  const d = aktuell;
  const systemDunkel = dunkelAbfrage?.matches ?? false;
  const schema = d.auto_dunkel && systemDunkel ? "dunkel" : d.schema;
  wurzel.dataset.schema = schema;
  wurzel.dataset.dichte = d.dichte;
  wurzel.dataset.schrift = d.schriftgroesse;
  wurzel.dataset.staerke = d.schriftstaerke;
  for (const v of INDIVIDUELL_VARIABLEN) wurzel.style.removeProperty(v);
  if (schema === "individuell") {
    for (const [k, v] of Object.entries(individuelleFarben(d))) wurzel.style.setProperty(k, v);
  }
}

export function darstellungAnwenden(d: Partial<Darstellung> | null | undefined) {
  aktuell = { ...STANDARD_DARSTELLUNG, ...(d ?? {}) };
  if (!dunkelAbfrage && typeof window !== "undefined" && window.matchMedia) {
    dunkelAbfrage = window.matchMedia("(prefers-color-scheme: dark)");
    dunkelAbfrage.addEventListener("change", anwenden);
  }
  anwenden();
}
