/**
 * Administration › System (nur Admin, Recht „Systemverwaltung“, Wunsch 02.10.2026; Festlegungen S12–S14 vom 01.10.2026):
 * Auslastung des Servers, Ubuntu-Updates, Container, Sicherung; Tätigkeiten für die VM (über den Systemagenten auf dem
 * Server) und für das EPM (direkt im Backend); Hinweis an alle Benutzer; angemeldete Benutzer; Verlauf der Aufträge.
 * Update und Neustart: Bestätigung mit Admin-Passwort und 2FA, vorher automatische Sicherung, Benutzer werden gewarnt.
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ZeigerEreignis, ReactNode } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useIch } from "@/lib/auth";
import { dateigroesse, datum, relativ, uhrzeit, zahl, zeitpunkt } from "@/lib/format";
import { ROLLEN } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { useStufe } from "@/lib/stufen";
import type { Stufe } from "@/lib/stufen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Segmente, Seitenkopf,
  Textfeld, cx } from "@/components/ui/basis";
import { Bereich, Bereiche } from "@/components/ui/bereiche";
import { ZweiFaktorFehlt } from "@/components/ZweiFaktorFehlt";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";

export type Platte = { pfad: string; bezeichnung: string; gesamt: number; frei: number };
export type Speicher = { gesamt: number | null; verfuegbar: number | null; swap_gesamt: number | null; swap_frei: number | null } | null;
type Paket = { name: string; von: string; nach: string; sicherheit: boolean };
export type HostStatus = {
  zeit: string; alter_s: number | null; aktuell: boolean; trocken?: boolean;
  rechner?: string; system?: string; kernel?: string; laufzeit_s?: number | null;
  cpu?: { kerne: number | null; last: number[]; prozent: number | null };
  speicher?: Speicher; platten?: Platte[];
  groessen?: { dokumente: number; sicherungen: number; images: number };
  updates?: { verfuegbar: boolean; anzahl?: number; sicherheit?: number; pakete?: Paket[]; zurueckgehalten?: string[];
    listen_am?: string | null; hinweis?: string };
  neustart_noetig?: boolean; neustart_pakete?: string[];
  container?: { verfuegbar: boolean; liste: { dienst: string; name: string; zustand: string; gesundheit: string; image: string;
    status: string }[]; hinweis?: string };
  sicherung?: { verfuegbar: boolean; anzahl?: number; gesamt?: number; letzte_am?: string | null; letzte_groesse?: number };
  dienste?: Record<string, string>;
};
type Konto = { id: number; anzeigename: string; benutzername: string };
export type Aktion = { code: string; name: string; bestaetigung: "keine" | "einfach" | "2fa"; beschreibung: string; sichern: boolean;
  warnen: boolean; erlaubt: boolean };
type Aufgabe = { code: string; name: string; bestaetigung: "keine" | "einfach"; beschreibung: string };
export type Sitzung = { id: number; benutzer: number; name: string; benutzername: string; rolle: string; browser: string; ip: string | null;
  angemeldet_am: string; zuletzt_am: string; eigene: boolean };
export type Hinweis = { id: number; text: string; art: "info" | "warnung"; gueltig_bis: string | null; angelegt_am: string;
  angelegt_von_name: string | null; auftrag: number | null };
export type Uebersicht = {
  host: HostStatus | null;
  container: { kerne: number | null; last: number[] | null; speicher: Speicher; laufzeit_s: number | null; platten: Platte[] };
  agent: { verzeichnis: boolean; erreichbar: boolean };
  epm: {
    version: string; python: string; django: string; zeitzone: string;
    datenbank: { version: string; groesse: number; verbindungen: number; letzte_wartung: string | null; tote_zeilen: number;
      tabellen: { name: string; groesse: number; zeilen: number; tot: number }[] };
    migrationen_offen: number;
    schutz: { erwartet: number; vorhanden: number; fehlend: string[] };
    patienten: { in_betreuung: number; abgeschlossen: number; testpatienten: number };
    dokumente: { anzahl: number; groesse: number; ungeprueft: number; platz: { gesamt: number; frei: number } | null };
    konten: { aktiv: number; gesperrt: number; ohne_2fa: number; einmal_kennwort_offen: number; admins: number;
      zweiter_faktor?: "freiwillig" | "admins" | "alle"; ohne_2fa_konten?: Konto[]; einmal_kennwort_konten?: Konto[]; gesperrt_konten?: Konto[] };
  };
  angemeldet: Sitzung[];
  hinweis: Hinweis | null;
  aktionen: Aktion[];
  aufgaben: Aufgabe[];
  minuten: number[];
};
export type Auftrag = { id: number; kennung: string; ziel: "server" | "epm"; aktion: string; name: string;
  status: "wartet" | "laeuft" | "erledigt" | "fehler" | "abgebrochen"; status_name: string; offen: boolean;
  parameter: { minuten?: number; pruefsummen?: boolean }; angefordert_von_name: string | null; angefordert_am: string;
  begonnen_am: string | null; beendet_am: string | null; ergebnis: string; ausgabe: string; rueckgabe: number | null; probelauf: boolean };
type Zeitraum = "1h" | "3h" | "24h" | "7t" | "14t" | "1m" | "6m";
type Verlauf = { felder: string[]; punkte: (number | null)[][]; zeitraum: Zeitraum; name: string; schritt_s: number; von: number; bis: number;
  zeitraeume: { code: Zeitraum; name: string }[] };
const ZEITRAUM_KURZ: Record<Zeitraum, string> = { "1h": "1 h", "3h": "3 h", "24h": "24 h", "7t": "7 Tage", "14t": "14 Tage", "1m": "1 Monat", "6m": "6 Monate" };
const ZEITRAUM_MERKER = "epm-system-zeitraum";
/** Spalten des Rasters der Systemseite je Fensterstufe (S16, Entwurf 2: ab 1440 px 2, ab 1920 px 3, ab 2560 px 4) */
const SYSTEM_SPALTEN: Record<Stufe, number> = { eng: 1, schmal: 1, hd: 2, fhd: 3, qhd: 4 };

// ---------------------------------------------------------------- Hilfen
export function dauer(s: number | null | undefined) {
  if (s == null) return "—";
  const t = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return t ? `${t} T ${h} h` : h ? `${h} h ${m} min` : `${m} min`;
}
export function anteil(belegt: number | null | undefined, gesamt: number | null | undefined) {
  return belegt != null && gesamt ? Math.round((100 * belegt) / gesamt) : null;
}
export function stufe(p: number | null): "ok" | "warn" | "fehler" {
  return p == null || p < 75 ? "ok" : p < 90 ? "warn" : "fehler";
}
const STUFE_TEXT = { ok: "in Ordnung", warn: "hoch", fehler: "kritisch" };

/** Kennzahl mit Balken: Status nie nur über Farbe (Text „hoch“/„kritisch“ und Symbol) */
function Kennzahl({ titel, wert, unter, prozent, testid }: { titel: string; wert: ReactNode; unter?: ReactNode; prozent?: number | null;
  testid?: string }) {
  const s = stufe(prozent ?? null);
  return (
    <Karte className="px-4 py-3 flex flex-col gap-1.5 min-w-0" data-testid={testid}>
      <span className="text-[0.8125rem] gedaempft">{titel}</span>
      <span className="text-[1.375rem] font-semibold num leading-tight">{wert}</span>
      {prozent != null ? (
        <div className="flex items-center gap-2">
          <div className="grow h-1.5 rounded-full bg-fein overflow-hidden" role="meter" aria-valuemin={0} aria-valuemax={100}
            aria-valuenow={prozent} aria-label={`${titel}: ${prozent} %`}>
            <div className={cx("h-full rounded-full", s === "ok" ? "bg-akzent" : s === "warn" ? "bg-warn" : "bg-fehler")}
              style={{ width: `${Math.min(100, Math.max(2, prozent))}%` }} />
          </div>
          {s !== "ok" ? <span className={cx("text-xs flex items-center gap-1", s === "warn" ? "text-warn" : "text-fehler")}>
            <Icon name="warnung" groesse={12} />{STUFE_TEXT[s]}</span> : null}
        </div>
      ) : null}
      {unter ? <span className="text-xs gedaempft">{unter}</span> : null}
    </Karte>
  );
}

function Zeile({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(130px,42%)_1fr] gap-3 py-1 text-sm border-b border-rand last:border-b-0">
      <dt className="gedaempft">{label}</dt>
      <dd className="m-0 min-w-0 break-words">{children}</dd>
    </div>
  );
}

function AuftragStatus({ a }: { a: Auftrag }) {
  const art = a.status === "erledigt" ? "ok" : a.status === "fehler" ? "fehler" : a.status === "abgebrochen" ? undefined : "warn";
  return <Chip art={art}>{a.status === "laeuft" || a.status === "wartet" ? <Icon name="sanduhr" groesse={12} /> : null}{a.status_name}
    {a.probelauf ? " (Probelauf)" : ""}</Chip>;
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
        <svg ref={flaeche} viewBox={`0 0 ${B} ${H}`} className="absolute inset-0 w-full h-full touch-none" role="img"
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
            style={{ left: `min(calc(${((x(p[0]!) / B) * 100).toFixed(1)}% + 10px), calc(100% - 190px))` }}>
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

/** Karte „Auslastung“ mit wählbarem Zeitraum; die Wahl bleibt in diesem Browser gemerkt. */
function AuslastungKarte() {
  const [zeitraum, setZeitraumRoh] = useState<Zeitraum>(gemerkterZeitraum);
  const setZeitraum = (z: Zeitraum) => {
    setZeitraumRoh(z);
    try { window.localStorage.setItem(ZEITRAUM_MERKER, z); } catch { /* nur bequem, nicht nötig */ }
  };
  const verlauf = useQuery({
    queryKey: ["system", "verlauf", zeitraum],
    queryFn: () => api<Verlauf>(`system/verlauf/?zeitraum=${zeitraum}`),
    refetchInterval: 60_000,
    placeholderData: (vorher: Verlauf | undefined) => vorher,
  });
  return (
    <Karte className="px-5 py-4 flex flex-col gap-2.5 min-h-0" data-testid="auslastung">
      <KartenKopf titel={`Auslastung · ${verlauf.data?.name ?? ZEITRAUM_KURZ[zeitraum]}`}
        unter="CPU und Arbeitsspeicher in Prozent, gemessen jede Minute vom Systemagenten" />
      <Segmente label="Zeitraum" wert={zeitraum} onWahl={setZeitraum} className="self-start flex-wrap"
        werte={(Object.keys(ZEITRAUM_KURZ) as Zeitraum[]).map((z) => ({ wert: z, text: ZEITRAUM_KURZ[z] }))} />
      <Fehleranzeige fehler={verlauf.error} />
      {verlauf.data ? <VerlaufDiagramm verlauf={verlauf.data} /> : verlauf.error ? null : <Laden />}
    </Karte>
  );
}

// ---------------------------------------------------------------- Bestätigen und ausführen
export type Wahl = { art: "server"; aktion: Aktion } | { art: "epm"; aufgabe: Aufgabe };

export function AusfuehrenDialog({ wahl, daten, onZu }: { wahl: Wahl | null; daten: Uebersicht; onZu: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const ich = useIch();
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  const [minuten, setMinuten] = useState("0");
  const [text, setText] = useState("");
  const [pruefsummen, setPruefsummen] = useState(false);
  useEffect(() => { setKennwort(""); setCode(""); setMinuten(wahl && wahl.art === "server" && wahl.aktion.warnen ? "5" : "0"); setText(""); setPruefsummen(false); }, [wahl]);
  const los = useMutation({
    mutationFn: () => {
      if (!wahl) throw new Error("keine Auswahl");
      if (wahl.art === "epm") return api<Auftrag>("system/epm/", { body: { aufgabe: wahl.aufgabe.code, pruefsummen } });
      const a = wahl.aktion;
      return api<Auftrag>("system/auftraege/", { body: {
        aktion: a.code, ...(a.warnen ? { minuten: Number(minuten), hinweis: text.trim() || undefined } : {}),
        ...(a.bestaetigung === "2fa" ? { kennwort, code } : {}),
      } });
    },
    onSuccess: (a) => {
      void qc.invalidateQueries({ queryKey: ["system"] });
      void qc.invalidateQueries({ queryKey: ["systemhinweis"] });
      melden(a.ziel === "epm" ? `${a.name}: ${a.ergebnis}` : `${a.name}: Auftrag an den Server übergeben.`, a.status === "fehler" ? "fehler" : undefined);
      onZu();
    },
  });
  if (!wahl) return null;
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const name = wahl.art === "server" ? wahl.aktion.name : wahl.aufgabe.name;
  const a = wahl.art === "server" ? wahl.aktion : null;
  const andere = daten.angemeldet.filter((s) => !s.eigene);
  // je Person nur einmal nennen (eine Person kann an mehreren Geräten angemeldet sein)
  const namen = [...new Set(andere.map((s) => s.name))];
  const zfa = a?.bestaetigung === "2fa";
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel={name} breite={zfa ? 560 : 480}
      beschreibung={wahl.art === "server" ? wahl.aktion.beschreibung : wahl.aufgabe.beschreibung}
      fuss={<>
        <Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante={zfa ? "dng" : "pri"} laedt={los.isPending} disabled={zfa && (!ich.zweiter_faktor || !kennwort || !code)} onClick={() => los.mutate()}>
          {zfa ? "Bestätigen und ausführen" : "Ausführen"}</Knopf>
      </>}>
      <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); los.mutate(); }}>
        {a?.sichern ? <Meldung art="info">Vorher erstellt der Server automatisch eine Sicherung. Schlägt sie fehl, wird nichts verändert.</Meldung> : null}
        {a && !daten.agent.erreichbar ? (
          <Meldung art="warn">Der Systemagent auf dem Server meldet sich gerade nicht. Der Auftrag wartet, bis er wieder läuft.</Meldung>
        ) : null}
        {a?.warnen ? (
          <>
            <Feld label="Beginn" hinweis={namen.length ? `Angemeldet: ${namen.join(", ")} – sie sehen den Hinweis oben auf jeder Seite.`
              : "Gerade ist niemand sonst angemeldet."}>
              {(p) => (
                <Auswahl {...p} value={minuten} onChange={(e) => setMinuten(e.target.value)}>
                  {daten.minuten.map((m) => <option key={m} value={m}>{m === 0 ? "sofort" : `in ${m} Minuten`}</option>)}
                </Auswahl>
              )}
            </Feld>
            <Feld label="Hinweis an die Benutzer" hinweis="leer = Standardtext; Uhrzeit des Beginns wird angehängt" fehler={f.hinweis}>
              {(p) => <Textfeld {...p} rows={2} maxLength={400} value={text} onChange={(e) => setText(e.target.value)} />}
            </Feld>
          </>
        ) : null}
        {wahl.art === "epm" && wahl.aufgabe.code === "dokumente_pruefen" ? (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={pruefsummen} onChange={(e) => setPruefsummen(e.target.checked)} />
            mit Prüfsummen (liest jede Datei vollständig, dauert bei vielen Dokumenten länger)
          </label>
        ) : null}
        {wahl.art === "epm" && wahl.aufgabe.code === "alle_abmelden" ? (
          <Meldung art="warn">{andere.length} andere Anmeldungen werden beendet. Ungespeicherte Eingaben dieser Benutzer gehen verloren.</Meldung>
        ) : null}
        {zfa ? (
          <>
            <ZweiFaktorFehlt />
            <div className="grid grid-cols-2 gap-3">
              <Feld label="Ihr Passwort" fehler={f.kennwort} pflicht>
                {(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}
              </Feld>
              <Feld label="Code aus der Authenticator-App" hinweis="oder ein Notfall-Code" fehler={f.code} pflicht>
                {(p) => <Eingabe {...p} inputMode="text" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
              </Feld>
            </div>
          </>
        ) : null}
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        {f.minuten ? <Meldung art="fehler">{f.minuten}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------- Teile der Seite
function Taetigkeiten({ daten, offen, onWahl }: { daten: Uebersicht; offen: Set<string>; onWahl: (w: Wahl) => void }) {
  const knopf = (wahl: Wahl, name: string, gesperrt: boolean, laeuft: boolean) => (
    <Knopf klein variante={wahl.art === "server" && wahl.aktion.bestaetigung === "2fa" ? "dng" : "sec"} disabled={gesperrt || laeuft}
      laedt={laeuft} onClick={() => onWahl(wahl)} aria-label={name}>{laeuft ? "läuft" : "Ausführen"}</Knopf>
  );
  return (
    <Karte className="px-5 py-4 flex flex-col gap-4" data-testid="taetigkeiten">
      <KartenKopf titel="Tätigkeiten" unter="Jede Tätigkeit steht mit Person und Zeitpunkt im Audit-Log." />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,340px),1fr))] gap-6">
        <div className="flex flex-col gap-1">
          <h3 className="m-0 text-sm font-semibold flex items-center gap-2"><Icon name="server" />Server (Ubuntu-VM)</h3>
          <span className="text-xs gedaempft mb-1">ausgeführt vom Systemagenten auf dem Server – nur diese festen Tätigkeiten</span>
          {daten.aktionen.map((a) => (
            <div key={a.code} className="flex items-start justify-between gap-3 py-2 border-b border-rand last:border-b-0" data-testid={`aktion-${a.code}`}>
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="text-sm font-medium">{a.name}</span>
                <span className="text-xs gedaempft">{a.beschreibung}</span>
                <span className="flex gap-1.5 flex-wrap">
                  {a.bestaetigung === "2fa" ? <Chip art="warn"><Icon name="schloss" groesse={11} />Passwort + 2FA</Chip> : null}
                  {a.sichern ? <Chip><Icon name="backup" groesse={11} />vorher Sicherung</Chip> : null}
                  {a.warnen ? <Chip><Icon name="info" groesse={11} />warnt Benutzer</Chip> : null}
                  {!a.erlaubt ? <Chip>Recht „Sicherungen verwalten“ fehlt</Chip> : null}
                </span>
              </div>
              {knopf({ art: "server", aktion: a }, a.name, !a.erlaubt || !daten.agent.verzeichnis, offen.has(`server:${a.code}`))}
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-1">
          <h3 className="m-0 text-sm font-semibold flex items-center gap-2"><Icon name="aktivitaet" />EPM</h3>
          <span className="text-xs gedaempft mb-1">läuft direkt im EPM, Ergebnis sofort</span>
          {daten.aufgaben.map((a) => (
            <div key={a.code} className="flex items-start justify-between gap-3 py-2 border-b border-rand last:border-b-0" data-testid={`aufgabe-${a.code}`}>
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="text-sm font-medium">{a.name}</span>
                <span className="text-xs gedaempft">{a.beschreibung}</span>
              </div>
              {knopf({ art: "epm", aufgabe: a }, a.name, false, false)}
            </div>
          ))}
        </div>
      </div>
    </Karte>
  );
}

function HinweisKarte({ hinweis }: { hinweis: Hinweis | null }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [text, setText] = useState("");
  const [art, setArt] = useState<"info" | "warnung">("info");
  const [minuten, setMinuten] = useState("");
  const fertig = () => { void qc.invalidateQueries({ queryKey: ["system"] }); void qc.invalidateQueries({ queryKey: ["systemhinweis"] }); };
  const setzen = useMutation({
    mutationFn: () => api("system/hinweis/", { body: { text, art, minuten: minuten ? Number(minuten) : null } }),
    onSuccess: () => { fertig(); setText(""); melden("Hinweis an alle Benutzer gesetzt."); },
  });
  const beenden = useMutation({
    mutationFn: () => api("system/hinweis/", { method: "DELETE" }),
    onSuccess: () => { fertig(); melden("Hinweis beendet."); },
  });
  const f: Feldfehler = setzen.error instanceof ApiFehler ? setzen.error.felder : {};
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="hinweis-karte">
      <KartenKopf titel="Hinweis an alle Benutzer" unter="Erscheint oben auf jeder Seite, z. B. vor Wartungsarbeiten. Update und Neustart setzen ihn selbst." />
      {hinweis ? (
        <div className={cx("meldung flex items-start justify-between gap-3", hinweis.art === "warnung" ? "warn" : "info")} data-testid="aktiver-hinweis">
          <span>{hinweis.text}<br /><span className="text-xs opacity-80">seit {zeitpunkt(hinweis.angelegt_am)} · {hinweis.gueltig_bis
            ? `bis ${zeitpunkt(hinweis.gueltig_bis)}` : "bis er beendet wird"}</span></span>
          <Knopf klein laedt={beenden.isPending} onClick={() => beenden.mutate()}>Beenden</Knopf>
        </div>
      ) : <span className="text-sm gedaempft">Gerade ist kein Hinweis aktiv.</span>}
      <form className="flex flex-wrap gap-2.5 items-end [&>.feld]:grow [&>.feld:first-child]:basis-[260px]" onSubmit={(e) => { e.preventDefault(); setzen.mutate(); }}>
        <Feld label="Neuer Hinweis" fehler={f.text}>
          {(p) => <Eingabe {...p} maxLength={500} value={text} onChange={(e) => setText(e.target.value)} placeholder="z. B. Heute ab 18 Uhr Wartung" />}
        </Feld>
        <Feld label="Art">
          {(p) => <Auswahl {...p} value={art} onChange={(e) => setArt(e.target.value as "info" | "warnung")}>
            <option value="info">Information</option><option value="warnung">Warnung</option></Auswahl>}
        </Feld>
        <Feld label="Anzeigen">
          {(p) => <Auswahl {...p} value={minuten} onChange={(e) => setMinuten(e.target.value)}>
            <option value="">bis ich ihn beende</option><option value="60">1 Stunde</option><option value="240">4 Stunden</option>
            <option value="1440">1 Tag</option><option value="10080">1 Woche</option></Auswahl>}
        </Feld>
        <Knopf type="submit" variante="pri" laedt={setzen.isPending} disabled={!text.trim()}>Hinweis setzen</Knopf>
      </form>
      <Fehleranzeige fehler={setzen.error && !Object.keys(f).length ? setzen.error : beenden.error} />
    </Karte>
  );
}

function Angemeldet({ liste }: { liste: Sitzung[] }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const beenden = useMutation({
    mutationFn: (s: Sitzung) => api(`system/sitzungen/${s.id}/`, { method: "DELETE" }),
    onSuccess: (_d, s) => { void qc.invalidateQueries({ queryKey: ["system"] }); melden(`${s.name} abgemeldet.`); },
    onError: (e) => melden(e.message, "fehler"),
  });
  return (
    <Karte className="px-5 py-4 flex flex-col gap-2 overflow-x-auto" data-testid="angemeldet">
      <KartenKopf titel={`Angemeldet (${liste.length})`} unter="Alle gültigen Anmeldungen; nach 30 Minuten ohne Aktivität laufen sie ab." />
      {liste.length === 0 ? <Leer>Niemand angemeldet.</Leer> : (
        <table className="tabelle">
          <thead><tr><th className="th">Person</th><th className="th">Browser · Adresse</th><th className="th">angemeldet</th><th className="th">zuletzt aktiv</th><th className="th" /></tr></thead>
          <tbody>
            {liste.map((s) => (
              <tr key={s.id}>
                <td className="td"><span className="font-medium">{s.name}</span> <span className="text-xs gedaempft">{ROLLEN[s.rolle] ?? s.rolle}</span>
                  {s.eigene ? <Chip art="akzent" className="ml-1.5">diese Sitzung</Chip> : null}</td>
                <td className="td text-[0.8125rem]">{s.browser || "—"} · <span className="num">{s.ip ?? "—"}</span></td>
                <td className="td text-[0.8125rem]">{relativ(s.angemeldet_am, true)}</td>
                <td className="td text-[0.8125rem]">{relativ(s.zuletzt_am, true)}</td>
                <td className="td text-right">{s.eigene ? null : (
                  <Knopf klein laedt={beenden.isPending && beenden.variables?.id === s.id} onClick={() => beenden.mutate(s)}
                    aria-label={`${s.name} abmelden`}>Abmelden</Knopf>)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Karte>
  );
}

function Auftraege({ liste }: { liste: Auftrag[] }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [auf, setAuf] = useState<number | null>(null);
  const zurueck = useMutation({
    mutationFn: (a: Auftrag) => api<Auftrag>(`system/auftraege/${a.kennung}/abbrechen/`, { method: "POST" }),
    onSuccess: (a) => { void qc.invalidateQueries({ queryKey: ["system"] }); void qc.invalidateQueries({ queryKey: ["systemhinweis"] }); melden(`${a.name} zurückgezogen.`); },
    onError: (e) => melden(e.message, "fehler"),
  });
  return (
    <Karte className="px-5 py-4 flex flex-col gap-2 overflow-x-auto" data-testid="auftraege">
      <KartenKopf titel="Verlauf der Tätigkeiten" unter="Die letzten 30 – vollständig im Audit-Log (Gruppe „System“)." />
      {liste.length === 0 ? <Leer>Noch keine Tätigkeiten.</Leer> : (
        <table className="tabelle">
          <thead><tr><th className="th">Zeit</th><th className="th">Tätigkeit</th><th className="th">von</th><th className="th">Status</th><th className="th">Ergebnis</th><th className="th" /></tr></thead>
          <tbody>
            {liste.map((a) => (
              <Fragment key={a.id}>
                <tr data-testid="auftrag">
                  <td className="td text-[0.8125rem] whitespace-nowrap">{relativ(a.angefordert_am, true)}</td>
                  <td className="td"><span className="font-medium">{a.name}</span> <span className="text-xs gedaempft">{a.ziel === "server" ? "Server" : "EPM"}</span>
                    {a.parameter.minuten ? <span className="text-xs gedaempft"> · Beginn nach {a.parameter.minuten} Min.</span> : null}</td>
                  <td className="td text-[0.8125rem]">{a.angefordert_von_name ?? "—"}</td>
                  <td className="td"><AuftragStatus a={a} /></td>
                  <td className="td text-[0.8125rem] max-w-[420px]">{a.ergebnis || (a.status === "wartet" ? "wartet, bis der Server den Auftrag abholt" : "—")}</td>
                  <td className="td text-right whitespace-nowrap">
                    {a.status === "wartet" ? <Knopf klein laedt={zurueck.isPending} onClick={() => zurueck.mutate(a)}>Zurückziehen</Knopf> : null}
                    {a.ausgabe ? <Knopf klein variante="geist" onClick={() => setAuf(auf === a.id ? null : a.id)} aria-expanded={auf === a.id}>
                      {auf === a.id ? "Ausgabe zu" : "Ausgabe"}</Knopf> : null}
                  </td>
                </tr>
                {auf === a.id ? (
                  <tr>
                    <td colSpan={6} className="td">
                      <pre className="m-0 max-h-[360px] overflow-auto text-[0.75rem] leading-snug bg-grund rounded-lg p-3 whitespace-pre-wrap" data-testid="auftrag-ausgabe">{a.ausgabe}</pre>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </Karte>
  );
}

/** Direkter Weg zu den betroffenen Konten (Fehlerliste 02.10.2026, 4.2): das eigene Konto führt zu „Mein Konto“
 *  (dort wird die Zwei-Faktor-Anmeldung eingerichtet), alle anderen in die Benutzerverwaltung zu dieser Person. */
function KontenLinks({ konten, ich, zweifaktor }: { konten?: Konto[]; ich: number; zweifaktor?: boolean }) {
  if (!konten?.length) return null;
  return (
    <span className="text-[0.8125rem]">{" "}
      {konten.map((k, i) => (
        <Fragment key={k.id}>{i ? ", " : ""}
          {k.id === ich && zweifaktor ? <Link to="/konto#zwei-faktor" title="Zwei-Faktor-Anmeldung für mein Konto einrichten">{k.anzeigename} (jetzt einrichten)</Link>
            : <Link to={`/admin/benutzer?id=${k.id}`} title={`${k.anzeigename} in der Benutzerverwaltung öffnen`}>{k.anzeigename}</Link>}
        </Fragment>
      ))}
    </span>
  );
}

// ---------------------------------------------------------------- Seite
export function System() {
  const ich = useIch();
  const daten = useQuery({ queryKey: ["system", "uebersicht"], queryFn: () => api<Uebersicht>("system/uebersicht/"), refetchInterval: 60_000 });
  const auftraege = useQuery({
    queryKey: ["system", "auftraege"],
    queryFn: () => api<Auftrag[]>("system/auftraege/"),
    refetchInterval: (q) => ((q.state.data ?? []).some((a) => a.offen) ? 3000 : 30_000),
  });
  const fenster = useStufe();
  const [wahl, setWahl] = useState<Wahl | null>(null);
  const [pakete, setPakete] = useState(false);
  const qc = useQueryClient();
  // Ist ein Auftrag fertig geworden, die Übersicht neu laden (Updates, Sicherung, Status)
  const offenVorher = useRef<string>("");
  const offenJetzt = (auftraege.data ?? []).filter((a) => a.offen).map((a) => a.id).join(",");
  useEffect(() => {
    if (offenVorher.current && offenVorher.current !== offenJetzt) {
      void qc.invalidateQueries({ queryKey: ["system", "uebersicht"] });
      void qc.invalidateQueries({ queryKey: ["system", "verlauf"] });
      void qc.invalidateQueries({ queryKey: ["systemhinweis"] });
    }
    offenVorher.current = offenJetzt;
  }, [offenJetzt, qc]);
  const offen = useMemo(() => new Set((auftraege.data ?? []).filter((a) => a.offen).map((a) => `${a.ziel}:${a.aktion}`)), [auftraege.data]);

  const d = daten.data;
  if (!d) {
    return (
      <Seite pfad={[{ text: "Administration" }, { text: "System" }]}>
        <Seitenkopf titel="System" />
        {daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />}
      </Seite>
    );
  }
  const h = d.host && d.host.aktuell ? d.host : null;
  const cpu = h?.cpu?.prozent ?? null;
  const last = h?.cpu?.last ?? d.container.last;
  const kerne = h?.cpu?.kerne ?? d.container.kerne;
  const sp = h?.speicher ?? d.container.speicher;
  const ram = anteil(sp && sp.gesamt != null && sp.verfuegbar != null ? sp.gesamt - sp.verfuegbar : null, sp?.gesamt);
  const platten = h?.platten?.length ? h.platten : d.container.platten;
  const daten_platte = platten.find((p) => p.bezeichnung === "EPM-Daten") ?? platten[0];
  const platte = daten_platte ? anteil(daten_platte.gesamt - daten_platte.frei, daten_platte.gesamt) : null;
  const laufzeit = h?.laufzeit_s ?? d.container.laufzeit_s;
  const updates = h?.updates;
  const sicherung = h?.sicherung;
  const letzteSicherungAlt = sicherung?.letzte_am ? Date.now() - new Date(sicherung.letzte_am).getTime() > 36 * 3600 * 1000 : true;

  return (
    <Seite pfad={[{ text: "Administration" }, { text: "System" }]}>
      <Seitenkopf titel="System" unter="Server und EPM: Auslastung, Updates, Wartung. Standardmäßig nur für die Administration (Vertretung unter Benutzer › Rechte)."
        rechts={<Knopf icon="neustart" laedt={daten.isFetching} onClick={() => { void daten.refetch(); void auftraege.refetch(); void qc.invalidateQueries({ queryKey: ["system", "verlauf"] }); }}>
          Neu laden</Knopf>} />

      {!d.agent.verzeichnis ? (
        <Meldung art="fehler">Das Auftragsverzeichnis fehlt. Tätigkeiten für den Server sind erst möglich, wenn auf dem Server einmal
          <code> sudo epm-update</code> (bzw. <code>rollout/04-projekt.sh</code>) gelaufen ist – das richtet den Systemagenten ein.</Meldung>
      ) : !d.agent.erreichbar ? (
        <Meldung art="warn"><span data-testid="agent-fehlt">Der Systemagent auf dem Server meldet sich nicht{d.host ? ` (letzte Messung ${relativ(d.host.zeit, true)})` : ""}.
          Angezeigt wird, was EPM selbst messen kann; Aufträge an den Server warten, bis er wieder läuft
          (<code>systemctl status epm-systemstatus.timer epm-systemagent.path</code>).</span></Meldung>
      ) : null}
      {h?.trocken ? <Meldung art="info">Probelauf: Der Systemagent simuliert Updates, Neustart und Sicherung nur (Testumgebung).</Meldung> : null}
      {h?.neustart_noetig ? (
        <Meldung art="warn">Nach installierten Updates ist ein Neustart des Servers nötig{h.neustart_pakete?.length ? ` (${h.neustart_pakete.join(", ")})` : ""}.</Meldung>
      ) : null}
      {d.epm.migrationen_offen || d.epm.schutz.fehlend.length ? (
        <Meldung art="fehler">{d.epm.migrationen_offen ? `${d.epm.migrationen_offen} Datenbank-Migrationen fehlen. ` : ""}
          {d.epm.schutz.fehlend.length ? `${d.epm.schutz.fehlend.length} Tabellen ohne Schutz vor Änderungen – „Unveränderlichkeit prüfen“ ausführen.` : ""}</Meldung>
      ) : null}

      <div className="grid grid-cols-2 lg:grid-cols-3 hd:grid-cols-6 gap-3" data-testid="kennzahlen">
        <Kennzahl titel="CPU" testid="kennzahl-cpu" prozent={cpu} wert={cpu != null ? `${zahl(cpu, 0)} %` : last ? zahl(last[0]) : "—"}
          unter={`Last ${last ? last.map((x) => zahl(x)).join(" · ") : "—"} bei ${kerne ?? "?"} Kernen`} />
        <Kennzahl titel="Arbeitsspeicher" testid="kennzahl-ram" prozent={ram} wert={ram != null ? `${ram} %` : "—"}
          unter={sp?.gesamt ? `${dateigroesse((sp.gesamt ?? 0) - (sp.verfuegbar ?? 0))} von ${dateigroesse(sp.gesamt)}` : undefined} />
        <Kennzahl titel={`Platte (${daten_platte?.bezeichnung ?? "Daten"})`} testid="kennzahl-platte" prozent={platte}
          wert={platte != null ? `${platte} %` : "—"} unter={daten_platte ? `${dateigroesse(daten_platte.frei)} frei von ${dateigroesse(daten_platte.gesamt)}` : undefined} />
        <Kennzahl titel="Laufzeit seit Neustart" wert={dauer(laufzeit)} unter={h?.system ?? undefined} />
        <Kennzahl titel="Ubuntu-Updates" testid="kennzahl-updates"
          wert={updates?.verfuegbar ? zahl(updates.anzahl ?? 0) : "—"}
          unter={updates?.verfuegbar ? <>{updates.sicherheit ? <span className="text-fehler font-medium">{updates.sicherheit} Sicherheitsupdates · </span> : null}
            Paketlisten {relativ(updates.listen_am, true)}</> : h ? updates?.hinweis || "nicht ermittelt" : "kommt vom Systemagenten"} />
        <Kennzahl titel="Letzte Sicherung" wert={sicherung?.letzte_am ? relativ(sicherung.letzte_am, true) : "—"}
          unter={sicherung?.letzte_am ? <>{dateigroesse(sicherung.letzte_groesse ?? 0)} · {sicherung.anzahl} Sicherungen
            {letzteSicherungAlt ? <span className="text-warn"> · älter als 36 h</span> : null}</> : h ? "keine Sicherung gefunden" : "kommt vom Systemagenten"} />
      </div>

      {/* Karten im Raster (S16, Entwurf 2: ab 1440 px 2, ab 1920 px 3, ab 2560 px 4 Spalten); Breite und Höhe jeder
          Karte über das Menü „⋯“ einstellbar, je Person gespeichert (Fehlerliste 02.10.2026, 4.1) */}
      <Bereiche seite="system" spalten={SYSTEM_SPALTEN[fenster]} testid="system-karten">
        <Bereich id="verlauf" titel="Auslastung" standard={{ breite: 5 }}><AuslastungKarte /></Bereich>
        <Bereich id="taetigkeiten" titel="Tätigkeiten" standard={{ breite: 5 }}><Taetigkeiten daten={d} offen={offen} onWahl={setWahl} /></Bereich>
        <Bereich id="auftraege" titel="Verlauf der Tätigkeiten" standard={{ breite: 5 }}><Auftraege liste={auftraege.data ?? []} /></Bereich>
        <Bereich id="server" titel="Server">
        <Karte className="px-5 py-4 flex flex-col gap-2 overflow-x-auto" data-testid="server-karte">
          <KartenKopf titel="Server" unter={h ? `gemessen ${relativ(h.zeit, true)}` : "ohne Systemagent nur Werte aus dem Container"} />
          <dl className="m-0">
            <Zeile label="Rechner">{h?.rechner ?? "—"}</Zeile>
            <Zeile label="Betriebssystem">{h?.system ?? "—"}{h?.kernel ? <span className="gedaempft"> · Kernel {h.kernel}</span> : null}</Zeile>
            <Zeile label="Swap">{sp?.swap_gesamt ? `${dateigroesse((sp.swap_gesamt ?? 0) - (sp.swap_frei ?? 0))} von ${dateigroesse(sp.swap_gesamt)} belegt` : "keiner"}</Zeile>
            {platten.map((p) => (
              <Zeile key={p.pfad} label={`Platte ${p.bezeichnung}`}><span className="num">{dateigroesse(p.frei)}</span> frei von {dateigroesse(p.gesamt)}
                <span className="gedaempft"> · {p.pfad}</span></Zeile>
            ))}
            {h?.groessen ? <Zeile label="Belegt durch EPM">Dokumente {dateigroesse(h.groessen.dokumente)} · Sicherungen {dateigroesse(h.groessen.sicherungen)}
              · Image-Dateien {dateigroesse(h.groessen.images)}</Zeile> : null}
            {h?.dienste ? <Zeile label="Dienste">{Object.entries(h.dienste).map(([n, z]) => (
              <span key={n} className="inline-flex items-center gap-1 mr-3"><Chip art={z === "active" ? "ok" : "warn"}>{z === "active" ? "aktiv" : z}</Chip>{n}</span>))}</Zeile> : null}
          </dl>
          {h?.container ? (
            <>
              <h3 className="m-0 mt-2 text-sm font-semibold">Container</h3>
              {h.container.verfuegbar ? (
                <table className="tabelle" data-testid="container">
                  <thead><tr><th className="th">Dienst</th><th className="th">Zustand</th><th className="th">Image</th></tr></thead>
                  <tbody>{h.container.liste.map((c) => (
                    <tr key={c.name}><td className="td font-medium">{c.dienst}</td>
                      <td className="td"><Chip art={c.zustand === "running" && (!c.gesundheit || c.gesundheit === "healthy") ? "ok" : "fehler"}>
                        {c.zustand === "running" ? "läuft" : c.zustand}{c.gesundheit ? ` · ${c.gesundheit === "healthy" ? "gesund" : c.gesundheit}` : ""}</Chip>
                        <span className="text-xs gedaempft ml-1.5">{c.status}</span></td>
                      <td className="td num text-[0.75rem]">{c.image}</td></tr>))}</tbody>
                </table>
              ) : <span className="text-sm gedaempft">nicht abrufbar{h.container.hinweis ? `: ${h.container.hinweis}` : ""}</span>}
            </>
          ) : null}
          {updates?.verfuegbar && (updates.pakete?.length ?? 0) > 0 ? (
            <>
              <button type="button" className="mt-2 self-start text-sm bg-transparent border-0 p-0 cursor-pointer font-semibold flex items-center gap-1.5"
                aria-expanded={pakete} onClick={() => setPakete(!pakete)}>
                <Icon name={pakete ? "runter" : "pfeilRechts"} groesse={14} />Ausstehende Pakete ({updates.anzahl})
              </button>
              {pakete ? (
                <table className="tabelle" data-testid="paketliste">
                  <thead><tr><th className="th">Paket</th><th className="th">installiert</th><th className="th">neu</th><th className="th" /></tr></thead>
                  <tbody>{updates.pakete!.map((p) => (
                    <tr key={p.name}><td className="td num text-[0.8125rem]">{p.name}</td><td className="td num text-[0.75rem] gedaempft">{p.von || "neu"}</td>
                      <td className="td num text-[0.75rem]">{p.nach}</td><td className="td">{p.sicherheit ? <Chip art="fehler">Sicherheit</Chip> : null}</td></tr>))}</tbody>
                </table>
              ) : null}
              {updates.zurueckgehalten?.length ? <span className="text-xs gedaempft">Zurückgehalten: {updates.zurueckgehalten.join(", ")}</span> : null}
            </>
          ) : null}
        </Karte>
        </Bereich>

        <Bereich id="epm" titel="EPM">
        <Karte className="px-5 py-4 flex flex-col gap-2 overflow-x-auto" data-testid="epm-karte">
          <KartenKopf titel="EPM" unter={`Version ${d.epm.version}`} />
          <dl className="m-0">
            <Zeile label="Software">Django {d.epm.django} · Python {d.epm.python} · PostgreSQL {d.epm.datenbank.version}</Zeile>
            <Zeile label="Datenbank"><span className="num">{dateigroesse(d.epm.datenbank.groesse)}</span> · {d.epm.datenbank.verbindungen} Verbindungen</Zeile>
            <Zeile label="Letzte Datenbankpflege">{d.epm.datenbank.letzte_wartung ? relativ(d.epm.datenbank.letzte_wartung, true) : "—"}
              <span className="gedaempft"> · {zahl(d.epm.datenbank.tote_zeilen)} nicht mehr benötigte Zeilen</span></Zeile>
            <Zeile label="Migrationen">{d.epm.migrationen_offen ? <Chip art="fehler">{d.epm.migrationen_offen} fehlen</Chip> : <Chip art="ok">vollständig</Chip>}</Zeile>
            <Zeile label="Unveränderlichkeit">{d.epm.schutz.fehlend.length ? <Chip art="fehler">{d.epm.schutz.fehlend.length} Tabellen ungeschützt</Chip>
              : <Chip art="ok">{d.epm.schutz.vorhanden} von {d.epm.schutz.erwartet} Tabellen geschützt</Chip>}</Zeile>
            <Zeile label="Patienten">{d.epm.patienten.in_betreuung} in Betreuung · {d.epm.patienten.abgeschlossen} abgeschlossen · {d.epm.patienten.testpatienten} Testpatienten</Zeile>
            <Zeile label="Dokumente">{zahl(d.epm.dokumente.anzahl)} Dateien · {dateigroesse(d.epm.dokumente.groesse)}
              {d.epm.dokumente.ungeprueft ? <span className="gedaempft"> · {d.epm.dokumente.ungeprueft} Altdokumente ungeprüft</span> : null}
              {d.epm.dokumente.platz ? <span className="gedaempft"> · {dateigroesse(d.epm.dokumente.platz.frei)} frei</span> : null}</Zeile>
            <Zeile label="Konten"><span data-testid="konten-zeile">{d.epm.konten.aktiv} aktiv · {d.epm.konten.admins} Admins
              {d.epm.konten.gesperrt ? <> · <Chip art="fehler">{d.epm.konten.gesperrt} gesperrt</Chip>
                <KontenLinks konten={d.epm.konten.gesperrt_konten} ich={ich.id} /></> : null}
              {d.epm.konten.ohne_2fa ? <> · <Chip art={d.epm.konten.zweiter_faktor === "freiwillig" ? undefined : "warn"}>{d.epm.konten.ohne_2fa} ohne 2FA</Chip>
                <KontenLinks konten={d.epm.konten.ohne_2fa_konten} ich={ich.id} zweifaktor /></> : null}
              {d.epm.konten.einmal_kennwort_offen ? <> · {d.epm.konten.einmal_kennwort_offen} mit offenem Einmal-Kennwort
                <KontenLinks konten={d.epm.konten.einmal_kennwort_konten} ich={ich.id} /></> : null}</span></Zeile>
            <Zeile label="Zwei-Faktor-Anmeldung">{d.epm.konten.zweiter_faktor === "alle" ? "Pflicht für alle" : d.epm.konten.zweiter_faktor === "admins"
              ? "Pflicht für Admins, sonst freiwillig" : "freiwillig"} · <Link to="/admin/benutzer#anmeldung">ändern</Link></Zeile>
            <Zeile label="Zeitzone">{d.epm.zeitzone} · Serverzeit {h ? zeitpunkt(h.zeit) : "—"} · heute {datum(new Date())}</Zeile>
          </dl>
          <h3 className="m-0 mt-2 text-sm font-semibold">Größte Tabellen</h3>
          <table className="tabelle">
            <tbody>{d.epm.datenbank.tabellen.map((t) => (
              <tr key={t.name}><td className="td num text-[0.75rem]">{t.name}</td><td className="td num text-right text-[0.8125rem]">{dateigroesse(t.groesse)}</td>
                <td className="td num text-right text-[0.75rem] gedaempft">{zahl(t.zeilen)} Zeilen</td></tr>))}</tbody>
          </table>
        </Karte>
        </Bereich>
        <Bereich id="hinweis" titel="Hinweis an alle Benutzer"><HinweisKarte hinweis={d.hinweis} /></Bereich>
        <Bereich id="angemeldet" titel="Angemeldet"><Angemeldet liste={d.angemeldet} /></Bereich>
      </Bereiche>
      <span className="text-xs gedaempft">Angemeldet als {ich.anzeigename}. Werte vom Server werden jede Minute aktualisiert.</span>
      <AusfuehrenDialog wahl={wahl} daten={d} onZu={() => setWahl(null)} />
    </Seite>
  );
}
