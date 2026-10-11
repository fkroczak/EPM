/**
 * Auslastung des Servers (CPU, Arbeitsspeicher, Platte) aus dem Verlauf des Systemagenten.
 *
 * Wunsch 10.10.2026: In Übersichten (Systemverwaltung, Administration › System) nur Kennzahl mit kleinem Verlauf; das
 * große Diagramm mit Zeitraum, Fadenkreuz und Spitzen öffnet sich erst mit „Größer anzeigen“ (oder Klick auf die
 * Karte) in einem Dialog.
 */
import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ZeigerEreignis } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { uhrzeit, zahl, zeitpunkt } from "@/lib/format";
import { Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { Sparkline } from "@/components/ui/sparkline";

export type Zeitraum = "1h" | "3h" | "24h" | "7t" | "14t" | "1m" | "6m";
export type Verlauf = { felder: string[]; punkte: (number | null)[][]; zeitraum: Zeitraum; name: string; schritt_s: number; von: number;
  bis: number; zeitraeume: { code: Zeitraum; name: string }[] };
export const ZEITRAUM_KURZ: Record<Zeitraum, string> = { "1h": "1 h", "3h": "3 h", "24h": "24 h", "7t": "7 Tage", "14t": "14 Tage",
  "1m": "1 Monat", "6m": "6 Monate" };
const ZEITRAUM_MERKER = "epm-system-zeitraum";

export function useVerlauf(zeitraum: Zeitraum, aktiv = true) {
  return useQuery({
    queryKey: ["system", "verlauf", zeitraum],
    queryFn: () => api<Verlauf>(`system/verlauf/?zeitraum=${zeitraum}`),
    refetchInterval: 60_000,
    enabled: aktiv,
    placeholderData: (vorher: Verlauf | undefined) => vorher,
  });
}

// ---------------------------------------------------------------- Verlauf der Auslastung
const WOCHENTAG = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const zwei = (n: number) => String(n).padStart(2, "0");

/**
 * CPU und Arbeitsspeicher in % auf einer gemeinsamen Achse (0–100 %), mit Fadenkreuz und Werten beim Überfahren.
 * Zeitraum wählbar (1 h bis 6 Monate, Fehlerliste 02.10.2026, 4.1): Die Zeitachse reicht immer über den ganzen Zeitraum,
 * auch wenn der Verlauf noch nicht so weit zurückreicht. Bei längeren Zeiträumen sind die Punkte Mittelwerte
 * (15 Minuten, 1 Stunde, 6 Stunden); die Spitzen in dieser Zeit stehen als dünne gestrichelte Linie dabei.
 * Das Diagramm füllt die Karte: Breite und Höhe folgen der eingestellten Größe der Karte.
 */
function VerlaufDiagramm({ verlauf }: { verlauf: Verlauf }) {
  const [zeiger, setZeiger] = useState<number | null>(null);
  const flaeche = useRef<SVGSVGElement>(null);
  const rahmen = useRef<HTMLDivElement>(null);
  const [mass, setMass] = useState({ b: 720, h: 200 });
  useEffect(() => {
    if (!rahmen.current || typeof ResizeObserver === "undefined") return;
    const beobachter = new ResizeObserver(([e]) => {
      const b = Math.max(280, Math.floor(e.contentRect.width)), h = Math.max(160, Math.floor(e.contentRect.height));
      setMass((m) => (m.b === b && m.h === h ? m : { b, h }));
    });
    beobachter.observe(rahmen.current);
    return () => beobachter.disconnect();
  }, []);
  const punkte = verlauf.punkte;
  const B = mass.b, H = mass.h, L = 36, R = 64, O = 10, U = 24;
  const spalte = (name: string) => verlauf.felder.indexOf(name);
  const iCpu = spalte("cpu"), iRam = spalte("ram"), iLast = spalte("last"), iPlatte = spalte("platte");
  const iCpuMax = spalte("cpu_max"), iRamMax = spalte("ram_max");
  const t0 = verlauf.von, t1 = Math.max(verlauf.bis, t0 + 1);
  const x = (t: number) => L + ((t - t0) / (t1 - t0)) * (B - L - R);
  const y = (p: number) => O + (1 - Math.min(100, Math.max(0, p)) / 100) * (H - O - U);
  // Lücken (Server aus, Agent pausiert) nicht überbrücken: ab dem Dreifachen des Messabstands neu ansetzen
  const luecke = Math.max(180, 3 * (verlauf.schritt_s || 60));
  const linie = (i: number) => {
    if (i < 0) return "";
    let d = "";
    let vorher: number | null = null;
    for (const p of punkte) {
      const v = p[i];
      if (v == null) { vorher = null; continue; }
      d += `${vorher != null && p[0]! - vorher <= luecke ? "L" : "M"}${x(p[0]!).toFixed(1)},${y(v).toFixed(1)}`;
      vorher = p[0]!;
    }
    return d;
  };
  const lang = t1 - t0 > 36 * 3600, sehrLang = t1 - t0 > 20 * 86400;
  const achse = (t: number) => {
    const d = new Date(t * 1000);
    return sehrLang ? `${zwei(d.getDate())}.${zwei(d.getMonth() + 1)}.` : lang ? `${WOCHENTAG[d.getDay()]} ${zwei(d.getDate())}.${zwei(d.getMonth() + 1)}.` : uhrzeit(d);
  };
  const marken = Math.max(2, Math.min(7, Math.floor((B - L - R) / 110)));
  const letzte = punkte.length ? punkte[punkte.length - 1] : null;
  const p = zeiger != null ? punkte[zeiger] ?? null : null;
  const bewegen = (e: ZeigerEreignis<SVGSVGElement>) => {
    const r = flaeche.current?.getBoundingClientRect();
    if (!r || !punkte.length) return;
    const t = t0 + ((((e.clientX - r.left) / r.width) * B - L) / (B - L - R)) * (t1 - t0);
    let best = 0;
    for (let i = 1; i < punkte.length; i++) if (Math.abs(punkte[i][0]! - t) < Math.abs(punkte[best][0]! - t)) best = i;
    setZeiger(best);
  };
  const reihen = [
    { i: iCpu, max: iCpuMax, name: "CPU", kurz: "CPU", farbe: "var(--reihe-1)" },
    { i: iRam, max: iRamMax, name: "Arbeitsspeicher", kurz: "RAM", farbe: "var(--reihe-2)" }].filter((r) => r.i >= 0);
  const mitSpitzen = iCpuMax >= 0 || iRamMax >= 0;
  const wert = (z: (number | null)[], i: number, einheit = " %") => (i >= 0 && z[i] != null ? `${zahl(z[i])}${einheit}` : "—");
  const mittel = verlauf.schritt_s >= 86400 / 4 ? "6 Stunden" : verlauf.schritt_s >= 3600 ? "1 Stunde" : verlauf.schritt_s >= 900 ? "15 Minuten" : "";
  return (
    <div className="flex flex-col gap-2 grow min-h-0" data-testid="verlauf" data-zeitraum={verlauf.zeitraum} data-punkte={punkte.length}>
      <div className="flex items-center gap-x-4 gap-y-1 flex-wrap text-xs text-text2" aria-hidden="true">
        {reihen.map((r) => <span key={r.i} className="flex items-center gap-1.5"><span className="w-4 h-0.5 rounded" style={{ background: r.farbe }} />{r.name}</span>)}
        {mitSpitzen ? <span className="flex items-center gap-1.5"><span className="w-4 border-t border-dashed border-current" />Spitze</span> : null}
        <span className="gedaempft">Werte in %{mittel ? ` · Mittel über ${mittel}` : ""}</span>
      </div>
      <div ref={rahmen} className="relative grow" style={{ minHeight: Math.round(Math.min(300, Math.max(180, B * 0.2))) }}>
        <svg ref={flaeche} viewBox={`0 0 ${B} ${H}`} className="absolute inset-0 w-full h-full touch-pan-y" role="img"
          aria-label={letzte ? `Auslastung, ${verlauf.name}: CPU zuletzt ${wert(letzte, iCpu)}, Arbeitsspeicher ${wert(letzte, iRam)}`
            : `Auslastung, ${verlauf.name}: noch keine Messwerte`}
          onPointerMove={bewegen} onPointerLeave={() => setZeiger(null)}>
          {[0, 25, 50, 75, 100].map((g) => (
            <g key={g}>
              <line x1={L} x2={B - R} y1={y(g)} y2={y(g)} stroke="var(--rand)" strokeWidth={1} strokeDasharray={g % 50 ? "2 4" : undefined} />
              {g % 50 === 0 || H > 220 ? <text x={L - 6} y={y(g) + 4} textAnchor="end" fontSize={11} fill="var(--gedaempft)">{g}</text> : null}
            </g>
          ))}
          {Array.from({ length: marken + 1 }, (_, k) => {
            const t = t0 + ((t1 - t0) * k) / marken;
            return (
              <g key={k}>
                {k > 0 && k < marken ? <line x1={x(t)} x2={x(t)} y1={O} y2={H - U} stroke="var(--rand)" strokeWidth={1} strokeDasharray="2 4" /> : null}
                <text x={x(t)} y={H - 6} fontSize={11} fill="var(--gedaempft)" textAnchor={k === 0 ? "start" : k === marken ? "end" : "middle"}>{achse(t)}</text>
              </g>
            );
          })}
          {reihen.map((r) => (
            <g key={r.i}>
              {r.max >= 0 ? <path d={linie(r.max)} fill="none" stroke={r.farbe} strokeWidth={1} strokeDasharray="3 3" opacity={0.7} /> : null}
              <path d={linie(r.i)} fill="none" stroke={r.farbe} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              {letzte && letzte[r.i] != null ? (
                <text x={x(letzte[0]!) + 6} y={y(letzte[r.i]!) + 4} fontSize={11} fill="var(--text2)">{r.kurz} {zahl(letzte[r.i], 0)}</text>
              ) : null}
            </g>
          ))}
          {p ? (
            <g>
              <line x1={x(p[0]!)} x2={x(p[0]!)} y1={O} y2={H - U} stroke="var(--gedaempft)" strokeWidth={1} strokeDasharray="3 3" />
              {reihen.map((r) => p[r.i] != null ? <circle key={r.i} cx={x(p[0]!)} cy={y(p[r.i]!)} r={4} fill={r.farbe}
                stroke="var(--flaeche)" strokeWidth={2} /> : null)}
            </g>
          ) : null}
        </svg>
        {punkte.length < 2 ? (
          <div className="absolute inset-0 flex items-center justify-center text-sm gedaempft text-center px-10 pointer-events-none" data-testid="verlauf-leer">
            {verlauf.schritt_s > 60 ? "Für diesen Zeitraum gibt es noch keine Werte – der Systemagent sammelt sie ab jetzt." : "Noch kein Verlauf – der Systemagent misst jede Minute."}
          </div>
        ) : null}
        {p ? (
          <div className="card absolute top-1 px-2.5 py-1.5 text-xs pointer-events-none flex flex-col gap-0.5"
            style={{ left: `min(calc(${((x(p[0]!) / B) * 100).toFixed(1)}% + 0.625rem), calc(100% - 11.875rem))` }}>
            <span className="font-medium">{zeitpunkt(new Date(p[0]! * 1000))}</span>
            <span>CPU {wert(p, iCpu)} · RAM {wert(p, iRam)}</span>
            {mitSpitzen ? <span>Spitze: CPU {wert(p, iCpuMax)} · RAM {wert(p, iRamMax)}</span> : null}
            <span className="gedaempft">Last {wert(p, iLast, "")} · Platte {wert(p, iPlatte)}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function gemerkterZeitraum(): Zeitraum {
  try {
    const w = window.localStorage.getItem(ZEITRAUM_MERKER);
    if (w && w in ZEITRAUM_KURZ) return w as Zeitraum;
  } catch { /* ohne Speicher: Standard */ }
  return "24h";
}


/** Großes Diagramm mit wählbarem Zeitraum im Dialog; die Wahl bleibt in diesem Browser gemerkt. */
export function AuslastungDialog({ offen, onZu }: { offen: boolean; onZu: () => void }) {
  const [zeitraum, setZeitraumRoh] = useState<Zeitraum>(gemerkterZeitraum);
  const setZeitraum = (z: Zeitraum) => {
    setZeitraumRoh(z);
    try { window.localStorage.setItem(ZEITRAUM_MERKER, z); } catch { /* nur bequem, nicht nötig */ }
  };
  const verlauf = useVerlauf(zeitraum, offen);
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) onZu(); }} breite={1040}
      titel={`Auslastung · ${verlauf.data?.name ?? ZEITRAUM_KURZ[zeitraum]}`}
      beschreibung="CPU und Arbeitsspeicher in Prozent, gemessen jede Minute vom Systemagenten">
      <div className="flex flex-col gap-3 min-h-[18rem]" data-testid="auslastung-dialog">
        <Segmente label="Zeitraum" wert={zeitraum} onWahl={setZeitraum} className="self-start flex-wrap"
          werte={(Object.keys(ZEITRAUM_KURZ) as Zeitraum[]).map((z) => ({ wert: z, text: ZEITRAUM_KURZ[z] }))} />
        <Fehleranzeige fehler={verlauf.error} />
        {verlauf.data ? <VerlaufDiagramm verlauf={verlauf.data} /> : verlauf.error ? null : <Laden />}
      </div>
    </Dialog>
  );
}

/** Eine Kennzahl mit kleinem Verlauf (24 Stunden) */
function Mini({ titel, wert, werte, farbe, testid }: { titel: string; wert: number | null; werte: (number | null)[]; farbe: string;
  testid: string }) {
  const s = wert == null || wert < 75 ? "" : wert < 90 ? "text-warn" : "text-fehler";
  return (
    <div className="flex flex-col gap-1 min-w-0" data-testid={testid}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[0.8125rem] gedaempft">{titel}</span>
        <span className={cx("num font-semibold", s)}>{wert != null ? `${zahl(wert, 0)} %` : "—"}
          {s ? <span className="text-xs font-normal"> {s === "text-warn" ? "hoch" : "kritisch"}</span> : null}</span>
      </div>
      <Sparkline werte={werte} max={100} farbe={farbe} label={`${titel}, letzte 24 Stunden`} />
    </div>
  );
}

/**
 * Karte „Auslastung“ für Übersichten: CPU, Arbeitsspeicher und Platte als Zahl mit kleinem Verlauf der letzten 24 Stunden;
 * „Größer anzeigen“ (oder Klick auf die Karte) öffnet das große Diagramm.
 */
export function AuslastungKarte({ jetzt }: { jetzt?: { cpu: number | null; ram: number | null; platte: number | null } }) {
  const [gross, setGross] = useState(false);
  const verlauf = useVerlauf("24h");
  const v = verlauf.data;
  const spalte = (name: string) => (v ? v.felder.indexOf(name) : -1);
  const reihe = (name: string) => {
    const i = spalte(name);
    return i < 0 || !v ? [] : v.punkte.map((p) => p[i] ?? null);
  };
  const letzter = (name: string) => {
    const r = reihe(name).filter((w): w is number => w != null);
    return r.length ? r[r.length - 1] : null;
  };
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3 min-h-0 cursor-pointer hover:border-akzent" data-testid="auslastung"
      onClick={(e) => { if (!(e.target as HTMLElement).closest("button")) setGross(true); }}>
      <KartenKopf titel="Auslastung · 24 h" unter="gemessen jede Minute vom Systemagenten"
        rechts={<Knopf klein icon="aktivitaet" onClick={() => setGross(true)} data-testid="auslastung-gross">Größer anzeigen</Knopf>} />
      <Fehleranzeige fehler={verlauf.error} />
      {v ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4" data-testid="auslastung-kompakt" data-punkte={v.punkte.length}>
          <Mini titel="CPU" wert={jetzt?.cpu ?? letzter("cpu")} werte={reihe("cpu")} farbe="var(--reihe-1)" testid="mini-cpu" />
          <Mini titel="Arbeitsspeicher" wert={jetzt?.ram ?? letzter("ram")} werte={reihe("ram")} farbe="var(--reihe-2)" testid="mini-ram" />
          <Mini titel="Platte" wert={jetzt?.platte ?? letzter("platte")} werte={reihe("platte")} farbe="var(--reihe-3, var(--akzent))" testid="mini-platte" />
        </div>
      ) : verlauf.error ? null : <Laden />}
      {v && v.punkte.length < 2 ? <span className="text-xs gedaempft">Noch kein Verlauf – der Systemagent misst jede Minute.</span> : null}
      <AuslastungDialog offen={gross} onZu={() => setGross(false)} />
    </Karte>
  );
}
