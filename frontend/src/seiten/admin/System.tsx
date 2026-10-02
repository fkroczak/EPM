/**
 * Administration › System (nur Admin, Recht „Systemverwaltung“, Wunsch 02.10.2026; Festlegungen S12–S14 vom 01.10.2026):
 * Auslastung des Servers, Ubuntu-Updates, Container, Sicherung; Tätigkeiten für die VM (über den Systemagenten auf dem
 * Server) und für das EPM (direkt im Backend); Hinweis an alle Benutzer; angemeldete Benutzer; Verlauf der Aufträge.
 * Update und Neustart: Bestätigung mit Admin-Passwort und 2FA, vorher automatische Sicherung, Benutzer werden gewarnt.
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ZeigerEreignis, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useIch } from "@/lib/auth";
import { dateigroesse, datum, relativ, uhrzeit, zahl, zeitpunkt } from "@/lib/format";
import { ROLLEN } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Seitenkopf,
  Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";

type Platte = { pfad: string; bezeichnung: string; gesamt: number; frei: number };
type Speicher = { gesamt: number | null; verfuegbar: number | null; swap_gesamt: number | null; swap_frei: number | null } | null;
type Paket = { name: string; von: string; nach: string; sicherheit: boolean };
type HostStatus = {
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
type Aktion = { code: string; name: string; bestaetigung: "keine" | "einfach" | "2fa"; beschreibung: string; sichern: boolean;
  warnen: boolean; erlaubt: boolean };
type Aufgabe = { code: string; name: string; bestaetigung: "keine" | "einfach"; beschreibung: string };
type Sitzung = { id: number; benutzer: number; name: string; benutzername: string; rolle: string; browser: string; ip: string | null;
  angemeldet_am: string; zuletzt_am: string; eigene: boolean };
type Hinweis = { id: number; text: string; art: "info" | "warnung"; gueltig_bis: string | null; angelegt_am: string;
  angelegt_von_name: string | null; auftrag: number | null };
type Uebersicht = {
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
    konten: { aktiv: number; gesperrt: number; ohne_2fa: number; einmal_kennwort_offen: number; admins: number };
  };
  angemeldet: Sitzung[];
  hinweis: Hinweis | null;
  aktionen: Aktion[];
  aufgaben: Aufgabe[];
  minuten: number[];
};
type Auftrag = { id: number; kennung: string; ziel: "server" | "epm"; aktion: string; name: string;
  status: "wartet" | "laeuft" | "erledigt" | "fehler" | "abgebrochen"; status_name: string; offen: boolean;
  parameter: { minuten?: number; pruefsummen?: boolean }; angefordert_von_name: string | null; angefordert_am: string;
  begonnen_am: string | null; beendet_am: string | null; ergebnis: string; ausgabe: string; rueckgabe: number | null; probelauf: boolean };
type Verlauf = { felder: string[]; punkte: [number, number | null, number | null, number | null, number | null][] };

// ---------------------------------------------------------------- Hilfen
function dauer(s: number | null | undefined) {
  if (s == null) return "—";
  const t = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return t ? `${t} T ${h} h` : h ? `${h} h ${m} min` : `${m} min`;
}
function anteil(belegt: number | null | undefined, gesamt: number | null | undefined) {
  return belegt != null && gesamt ? Math.round((100 * belegt) / gesamt) : null;
}
function stufe(p: number | null): "ok" | "warn" | "fehler" {
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

// ---------------------------------------------------------------- Verlauf der Auslastung (24 h)
/** CPU und Arbeitsspeicher in % auf einer gemeinsamen Achse (0–100 %), mit Fadenkreuz und Werten beim Überfahren. */
function VerlaufDiagramm({ verlauf }: { verlauf: Verlauf }) {
  const [zeiger, setZeiger] = useState<number | null>(null);
  const flaeche = useRef<SVGSVGElement>(null);
  const punkte = verlauf.punkte;
  const B = 720, H = 180, L = 36, R = 64, O = 10, U = 24;
  if (punkte.length < 2) return <Leer>Noch kein Verlauf – der Systemagent misst jede Minute.</Leer>;
  const t0 = punkte[0][0], t1 = punkte[punkte.length - 1][0];
  const x = (t: number) => L + ((t - t0) / Math.max(1, t1 - t0)) * (B - L - R);
  const y = (p: number) => O + (1 - p / 100) * (H - O - U);
  const linie = (i: 1 | 2) => {
    let d = "";
    let offen = false;
    for (const p of punkte) {
      const v = p[i];
      if (v == null) { offen = false; continue; }
      d += `${offen ? "L" : "M"}${x(p[0]).toFixed(1)},${y(v).toFixed(1)}`;
      offen = true;
    }
    return d;
  };
  const letzte = punkte[punkte.length - 1];
  const zeit = (t: number) => uhrzeit(new Date(t * 1000));
  const p = zeiger != null ? punkte[zeiger] : null;
  const bewegen = (e: ZeigerEreignis<SVGSVGElement>) => {
    const r = flaeche.current?.getBoundingClientRect();
    if (!r) return;
    const t = t0 + ((((e.clientX - r.left) / r.width) * B - L) / (B - L - R)) * (t1 - t0);
    let best = 0;
    for (let i = 1; i < punkte.length; i++) if (Math.abs(punkte[i][0] - t) < Math.abs(punkte[best][0] - t)) best = i;
    setZeiger(best);
  };
  const reihen: { i: 1 | 2; name: string; farbe: string }[] = [
    { i: 1, name: "CPU", farbe: "var(--reihe-1)" }, { i: 2, name: "Arbeitsspeicher", farbe: "var(--reihe-2)" }];
  return (
    <div className="flex flex-col gap-2" data-testid="verlauf">
      <div className="flex items-center gap-4 text-xs text-text2" aria-hidden="true">
        {reihen.map((r) => <span key={r.i} className="flex items-center gap-1.5"><span className="w-4 h-0.5 rounded" style={{ background: r.farbe }} />{r.name}</span>)}
        <span className="gedaempft">letzte {Math.round((t1 - t0) / 3600)} h · Werte in %</span>
      </div>
      <div className="relative">
        <svg ref={flaeche} viewBox={`0 0 ${B} ${H}`} className="w-full h-auto touch-none" role="img"
          aria-label={`Auslastung: CPU zuletzt ${zahl(letzte[1])} %, Arbeitsspeicher ${zahl(letzte[2])} %`}
          onPointerMove={bewegen} onPointerLeave={() => setZeiger(null)}>
          {[0, 50, 100].map((g) => (
            <g key={g}>
              <line x1={L} x2={B - R} y1={y(g)} y2={y(g)} stroke="var(--rand)" strokeWidth={1} />
              <text x={L - 6} y={y(g) + 4} textAnchor="end" fontSize={11} fill="var(--gedaempft)">{g}</text>
            </g>
          ))}
          <text x={L} y={H - 6} fontSize={11} fill="var(--gedaempft)">{zeit(t0)}</text>
          <text x={B - R} y={H - 6} fontSize={11} fill="var(--gedaempft)" textAnchor="end">{zeit(t1)}</text>
          {reihen.map((r) => (
            <g key={r.i}>
              <path d={linie(r.i)} fill="none" stroke={r.farbe} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              {letzte[r.i] != null ? (
                <text x={x(t1) + 6} y={y(letzte[r.i]!) + 4} fontSize={11} fill="var(--text2)">{r.name === "CPU" ? "CPU" : "RAM"} {zahl(letzte[r.i], 0)}</text>
              ) : null}
            </g>
          ))}
          {p ? (
            <g>
              <line x1={x(p[0])} x2={x(p[0])} y1={O} y2={H - U} stroke="var(--gedaempft)" strokeWidth={1} strokeDasharray="3 3" />
              {reihen.map((r) => p[r.i] != null ? <circle key={r.i} cx={x(p[0])} cy={y(p[r.i]!)} r={4} fill={r.farbe}
                stroke="var(--flaeche)" strokeWidth={2} /> : null)}
            </g>
          ) : null}
        </svg>
        {p ? (
          <div className="card absolute top-1 px-2.5 py-1.5 text-xs pointer-events-none flex flex-col gap-0.5"
            style={{ left: `min(calc(${((x(p[0]) / B) * 100).toFixed(1)}% + 10px), calc(100% - 170px))` }}>
            <span className="font-medium">{zeitpunkt(new Date(p[0] * 1000))}</span>
            <span>CPU {p[1] != null ? `${zahl(p[1])} %` : "—"} · RAM {p[2] != null ? `${zahl(p[2])} %` : "—"}</span>
            <span className="gedaempft">Last {p[3] != null ? zahl(p[3]) : "—"} · Platte {p[4] != null ? `${zahl(p[4])} %` : "—"}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Bestätigen und ausführen
type Wahl = { art: "server"; aktion: Aktion } | { art: "epm"; aufgabe: Aufgabe };

function AusfuehrenDialog({ wahl, daten, onZu }: { wahl: Wahl | null; daten: Uebersicht; onZu: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
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
        <Knopf variante={zfa ? "dng" : "pri"} laedt={los.isPending} disabled={zfa && (!kennwort || !code)} onClick={() => los.mutate()}>
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
          <div className="grid grid-cols-2 gap-3">
            <Feld label="Ihr Passwort" fehler={f.kennwort} pflicht>
              {(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}
            </Feld>
            <Feld label="Code aus der Authenticator-App" hinweis="oder ein Notfall-Code" fehler={f.code} pflicht>
              {(p) => <Eingabe {...p} inputMode="text" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
            </Feld>
          </div>
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
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
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
      <form className="grid grid-cols-[minmax(0,1fr)_150px_170px_auto] gap-2.5 items-end" onSubmit={(e) => { e.preventDefault(); setzen.mutate(); }}>
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
    <Karte className="px-5 py-4 flex flex-col gap-2" data-testid="angemeldet">
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
    <Karte className="px-5 py-4 flex flex-col gap-2" data-testid="auftraege">
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

// ---------------------------------------------------------------- Seite
export function System() {
  const ich = useIch();
  const daten = useQuery({ queryKey: ["system", "uebersicht"], queryFn: () => api<Uebersicht>("system/uebersicht/"), refetchInterval: 60_000 });
  const auftraege = useQuery({
    queryKey: ["system", "auftraege"],
    queryFn: () => api<Auftrag[]>("system/auftraege/"),
    refetchInterval: (q) => ((q.state.data ?? []).some((a) => a.offen) ? 3000 : 30_000),
  });
  const verlauf = useQuery({ queryKey: ["system", "verlauf"], queryFn: () => api<Verlauf>("system/verlauf/"), refetchInterval: 60_000 });
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
        rechts={<Knopf icon="neustart" laedt={daten.isFetching} onClick={() => { void daten.refetch(); void auftraege.refetch(); void verlauf.refetch(); }}>
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

      <Karte className="px-5 py-4 flex flex-col gap-2">
        <KartenKopf titel="Auslastung der letzten 24 Stunden" unter="CPU und Arbeitsspeicher in Prozent, gemessen jede Minute vom Systemagenten" />
        {verlauf.data ? <VerlaufDiagramm verlauf={verlauf.data} /> : <Laden />}
      </Karte>

      <Taetigkeiten daten={d} offen={offen} onWahl={setWahl} />
      <Auftraege liste={auftraege.data ?? []} />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
        <Karte className="px-5 py-4 flex flex-col gap-2" data-testid="server-karte">
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

        <Karte className="px-5 py-4 flex flex-col gap-2" data-testid="epm-karte">
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
            <Zeile label="Konten">{d.epm.konten.aktiv} aktiv · {d.epm.konten.admins} Admins
              {d.epm.konten.gesperrt ? <> · <Chip art="fehler">{d.epm.konten.gesperrt} gesperrt</Chip></> : null}
              {d.epm.konten.ohne_2fa ? <> · <Chip art="warn">{d.epm.konten.ohne_2fa} ohne 2FA</Chip></> : null}
              {d.epm.konten.einmal_kennwort_offen ? <> · {d.epm.konten.einmal_kennwort_offen} mit offenem Einmal-Kennwort</> : null}</Zeile>
            <Zeile label="Zeitzone">{d.epm.zeitzone} · Serverzeit {h ? zeitpunkt(h.zeit) : "—"} · heute {datum(new Date())}</Zeile>
          </dl>
          <h3 className="m-0 mt-2 text-sm font-semibold">Größte Tabellen</h3>
          <table className="tabelle">
            <tbody>{d.epm.datenbank.tabellen.map((t) => (
              <tr key={t.name}><td className="td num text-[0.75rem]">{t.name}</td><td className="td num text-right text-[0.8125rem]">{dateigroesse(t.groesse)}</td>
                <td className="td num text-right text-[0.75rem] gedaempft">{zahl(t.zeilen)} Zeilen</td></tr>))}</tbody>
          </table>
        </Karte>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
        <HinweisKarte hinweis={d.hinweis} />
        <Angemeldet liste={d.angemeldet} />
      </div>
      <span className="text-xs gedaempft">Angemeldet als {ich.anzeigename}. Werte vom Server werden jede Minute aktualisiert.</span>
      <AusfuehrenDialog wahl={wahl} daten={d} onZu={() => setWahl(null)} />
    </Seite>
  );
}
