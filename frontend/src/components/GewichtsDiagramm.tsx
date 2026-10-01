/** Gewichtsverlauf als SVG (Entwurf 4): Messwerte, Verlauf (geglättet oder Linie), Vergleichswert. */
import { alsDatum, datum, kg, zahl } from "@/lib/format";

export type Messpunkt = { gemessen_am: string; gewicht_kg: number | string };
export type Zeitraum = "y1" | "y3" | "y5" | "alle";

const B = 700, H = 240, L = 44, R = 14, O = 14, U = 30;
const MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

export function imZeitraum<T extends Messpunkt>(werte: T[], zeitraum: Zeitraum): T[] {
  if (zeitraum === "alle") return werte;
  const jahre = zeitraum === "y1" ? 1 : zeitraum === "y3" ? 3 : 5;
  const grenze = new Date();
  grenze.setFullYear(grenze.getFullYear() - jahre);
  return werte.filter((w) => (alsDatum(w.gemessen_am)?.getTime() ?? 0) >= grenze.getTime());
}

/** Monotone kubische Interpolation (Fritsch–Carlson): glatte Linie genau durch die Messwerte, ohne Überschwingen */
function glattePfad(p: { x: number; y: number }[]): string {
  if (p.length < 3) return p.map((q, i) => `${i ? "L" : "M"}${q.x.toFixed(1)},${q.y.toFixed(1)}`).join(" ");
  const n = p.length;
  const d: number[] = [], m: number[] = new Array(n).fill(0);
  for (let i = 0; i < n - 1; i++) d.push((p[i + 1].y - p[i].y) / Math.max(p[i + 1].x - p[i].x, 1e-6));
  m[0] = d[0];
  m[n - 1] = d[n - 2];
  for (let i = 1; i < n - 1; i++) m[i] = d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2;
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i], s = a * a + b * b;
    if (s > 9) { const t = 3 / Math.sqrt(s); m[i] = t * a * d[i]; m[i + 1] = t * b * d[i]; }
  }
  let pfad = `M${p[0].x.toFixed(1)},${p[0].y.toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = (p[i + 1].x - p[i].x) / 3;
    pfad += ` C${(p[i].x + h).toFixed(1)},${(p[i].y + m[i] * h).toFixed(1)} ${(p[i + 1].x - h).toFixed(1)},${(p[i + 1].y - m[i + 1] * h).toFixed(1)} ${p[i + 1].x.toFixed(1)},${p[i + 1].y.toFixed(1)}`;
  }
  return pfad;
}

function schritt(spanne: number) {
  for (const s of [0.5, 1, 2, 5, 10, 20]) if (spanne / s <= 5) return s;
  return 50;
}

export function GewichtsDiagramm({ werte, zeitraum, geglaettet, vergleich, beschriftung }: {
  werte: Messpunkt[];
  zeitraum: Zeitraum;
  geglaettet: boolean;
  vergleich?: { am: string; kg: number | string } | null;
  beschriftung: string;
}) {
  const punkte = werte
    .map((w) => ({ t: alsDatum(w.gemessen_am)!.getTime(), kg: Number(w.gewicht_kg), am: w.gemessen_am }))
    .sort((a, b) => a.t - b.t);
  if (!punkte.length) {
    return <div className="h-[240px] flex items-center justify-center text-sm gedaempft border border-dashed border-rand rounded-lg">Keine Messwerte im Zeitraum.</div>;
  }
  const heute = Date.now();
  let t0 = punkte[0].t;
  if (zeitraum !== "alle") {
    const g = new Date();
    g.setFullYear(g.getFullYear() - (zeitraum === "y1" ? 1 : zeitraum === "y3" ? 3 : 5));
    t0 = g.getTime();
  }
  const t1 = Math.max(heute, punkte[punkte.length - 1].t);
  const alleKg = punkte.map((p) => p.kg).concat(vergleich ? [Number(vergleich.kg)] : []);
  let min = Math.min(...alleKg), max = Math.max(...alleKg);
  if (max - min < 2) { min -= 1; max += 1; }
  const st = schritt(max - min);
  min = Math.floor(min / st) * st;
  max = Math.ceil(max / st) * st;
  const x = (t: number) => L + ((t - t0) / Math.max(t1 - t0, 1)) * (B - L - R);
  const y = (v: number) => O + (1 - (v - min) / (max - min)) * (H - O - U);

  const yTicks: number[] = [];
  for (let v = min; v <= max + 1e-9; v += st) yTicks.push(Math.round(v * 10) / 10);
  // Monatsbeschriftung: höchstens 6 Marken
  const monate = (t1 - t0) / (30.4 * 86400000);
  const mSchritt = [1, 2, 3, 6, 12, 24, 36].find((s) => monate / s <= 6) ?? 60;
  const xTicks: { t: number; text: string }[] = [];
  const start = new Date(t0);
  const d = new Date(start.getFullYear(), start.getMonth() + 1, 1);
  while (d.getMonth() % mSchritt !== 0 && mSchritt <= 12) d.setMonth(d.getMonth() + 1);
  for (; d.getTime() <= t1; d.setMonth(d.getMonth() + mSchritt)) {
    xTicks.push({ t: d.getTime(), text: `${MONATE[d.getMonth()]} ${String(d.getFullYear()).slice(2)}` });
  }
  const xy = punkte.map((p) => ({ x: x(p.t), y: y(p.kg) }));
  const linie = geglaettet ? glattePfad(xy) : xy.map((q, i) => `${i ? "L" : "M"}${q.x.toFixed(1)},${q.y.toFixed(1)}`).join(" ");
  const vergleichT = vergleich ? alsDatum(vergleich.am)?.getTime() : undefined;
  const letzter = punkte[punkte.length - 1];

  return (
    <svg viewBox={`0 0 ${B} ${H}`} className="w-full h-auto" role="img" data-testid="gewichtsdiagramm"
      aria-label={`${beschriftung}, ${punkte.length} Messungen, zuletzt ${kg(letzter.kg)} am ${datum(letzter.am)}`}>
      {yTicks.map((v) => (
        <g key={v}>
          <line x1={L} x2={B - R} y1={y(v)} y2={y(v)} stroke="var(--rand)" strokeWidth="1" />
          <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize="11" className="font-mono" fill="var(--gedaempft)">{zahl(v)}</text>
        </g>
      ))}
      {xTicks.map((m) => (
        <text key={m.t} x={x(m.t)} y={H - 8} textAnchor="middle" fontSize="11" className="font-mono" fill="var(--gedaempft)">{m.text}</text>
      ))}
      <path d={linie} fill="none" stroke="var(--akzent)" strokeWidth="2.25" strokeLinejoin="round" strokeLinecap="round" />
      {punkte.map((p, i) => (
        <circle key={`${p.am}-${i}`} cx={xy[i].x} cy={xy[i].y} r={i === punkte.length - 1 ? 4 : 3}
          fill={i === punkte.length - 1 ? "var(--akzent)" : "var(--flaeche)"} stroke={i === punkte.length - 1 ? "var(--akzent)" : "var(--gedaempft)"} strokeWidth="1.5">
          <title>{`${datum(p.am)}: ${kg(p.kg)}`}</title>
        </circle>
      ))}
      {vergleich && vergleichT !== undefined && vergleichT >= t0 ? (
        <circle cx={x(vergleichT)} cy={y(Number(vergleich.kg))} r="6" fill="none" stroke="var(--warn)" strokeWidth="2">
          <title>{`Vergleichswert ${datum(vergleich.am)}: ${kg(vergleich.kg)}`}</title>
        </circle>
      ) : null}
    </svg>
  );
}
