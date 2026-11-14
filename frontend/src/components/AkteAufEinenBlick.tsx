/**
 * Akte › Übersicht: „Auf einen Blick“ (KI-Entwurf, 14.11.2026) – was seit dem letzten Termin dazugekommen ist, aus
 * freigegebenen Inhalten der Akte, jede Aussage mit Quellenangabe [n]. Nachts für Termine vorbereitet oder auf
 * Anforderung. Gegenprüfung wie beim Berichtsentwurf: unbelegte Werte, Sätze ohne Beleg, Bewertungen markiert.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, heuteIso, zeitpunkt } from "@/lib/format";
import type { KiFakt, KiPruefung, KiZusammenfassung } from "@/lib/ki";
import { Chip, Fehleranzeige, Karte, Knopf, Ladekreis, Meldung, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";

/** Reiter der Akte, auf die eine Quelle verweisen darf (App.tsx); Unbekanntes bleibt ohne Link */
const REITER = new Set(["kartei", "diagnosen", "medikamente", "therapie", "befunde", "kontakte", "plaene", "labor", "bia", "berichte",
  "faelle", "korrespondenz", "dokumente", "verlauf", "ki"]);
const BELEG = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

function merkerSchluessel(benutzer: number | undefined) { return `epm.akte.aufEinenBlick.zu.${benutzer ?? 0}`; }
function zuGemerkt(benutzer: number | undefined): boolean {
  try { return window.localStorage.getItem(merkerSchluessel(benutzer)) === "1"; } catch { return false; }
}

function tageSeit(iso: string): number {
  const a = Date.parse(`${iso.slice(0, 10)}T00:00:00Z`);
  const b = Date.parse(`${heuteIso()}T00:00:00Z`);
  return Number.isNaN(a) || Number.isNaN(b) ? 0 : Math.max(0, Math.round((b - a) / 86_400_000));
}

function quellLink(patient: number, f: KiFakt | undefined): string | null {
  return f?.link && REITER.has(f.link) ? `/patienten/${patient}/${f.link}` : null;
}

export function AkteAufEinenBlick({ patient }: { patient: number }) {
  const { darf, ich } = useAuth();
  const qc = useQueryClient();
  const [zu, setZu] = useState(() => zuGemerkt(ich?.id));
  const umschalten = () => {
    const neu = !zu;
    setZu(neu);
    try { window.localStorage.setItem(merkerSchluessel(ich?.id), neu ? "1" : "0"); } catch { /* ohne Speicher: nur für diese Sitzung */ }
  };
  const q = useQuery({
    queryKey: ["ki", "zusammenfassungen", patient],
    queryFn: () => api<KiZusammenfassung[]>(`ki/zusammenfassungen/${abfrage({ patient })}`, { hintergrund: true }),
    enabled: darf("ki_ansehen") && !zu,
    refetchInterval: (a) => ((a.state.data ?? []).some((z) => z.status === "wartet" || z.status === "laeuft") ? 3000 : false),
  });
  const neu = useMutation({
    mutationFn: () => api<KiZusammenfassung>("ki/zusammenfassungen/", { body: { patient } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ki", "zusammenfassungen", patient] }),
  });
  if (!darf("ki_ansehen")) return null;
  const liste = q.data ?? [];
  const arbeitet = liste.some((z) => z.status === "wartet" || z.status === "laeuft");
  // gezeigt wird die neueste fertige (oder fehlgeschlagene); eine neue in Arbeit läuft daneben als Ladeanzeige
  const z = liste.find((x) => x.status === "fertig") ?? liste.find((x) => x.status === "fehler");
  const kopfId = `auf-einen-blick-${patient}`;
  return (
    <Karte className="px-4 py-3 flex flex-col gap-2.5" data-testid="akte-auf-einen-blick" aria-labelledby={kopfId}>
      <div className="flex items-center gap-2 flex-wrap">
        <button type="button" className="flex items-center gap-1.5 bg-transparent border-0 p-0 cursor-pointer text-left min-w-0"
          aria-expanded={!zu} aria-controls={`${kopfId}-inhalt`} onClick={umschalten}>
          <Icon name={zu ? "runter" : "hoch"} groesse={14} aria-hidden="true" />
          <h2 id={kopfId} className="lbl m-0 text-[0.9375rem]">Auf einen Blick</h2>
        </button>
        <Chip art="warn" title="Von der KI aus freigegebenen Inhalten der Akte zusammengestellt – keine Bewertung, keine Empfehlung">KI-Entwurf</Chip>
        {!zu && z?.von ? <span className="text-[0.8125rem] gedaempft">{seitText(z)}</span> : null}
        <span className="flex-1" />
        {!zu && arbeitet ? <span className="flex items-center gap-1.5 text-[0.8125rem] gedaempft" role="status"><Ladekreis groesse={14} />wird erstellt …</span> : null}
        {!zu && darf("ki_berichte") && z ? (
          <Knopf klein variante="geist" icon="neustart" laedt={neu.isPending} disabled={arbeitet} onClick={() => neu.mutate()}>Neu erstellen</Knopf>) : null}
      </div>
      {zu ? null : (
        <div id={`${kopfId}-inhalt`} className="flex flex-col gap-2.5 min-w-0">
          {q.isLoading ? <div className="flex items-center gap-2 text-sm gedaempft"><Ladekreis /> Wird geladen …</div> : null}
          {q.data && !z ? (
            <div className="flex items-center gap-3 flex-wrap text-sm">
              <span className="gedaempft">{arbeitet ? "Die Zusammenfassung wird im KI-Dienst erstellt – das kann einige Minuten dauern."
                : "Noch keine Zusammenfassung für diese Akte."}</span>
              {darf("ki_berichte") && !arbeitet ? (
                <Knopf klein variante="pri" laedt={neu.isPending} onClick={() => neu.mutate()}>Jetzt erstellen</Knopf>) : null}
            </div>) : null}
          {z ? <Inhalt z={z} /> : null}
          <Fehleranzeige fehler={q.error ?? neu.error} />
        </div>)}
    </Karte>
  );
}

function seitText(z: KiZusammenfassung): string {
  const n = tageSeit(z.von);
  const tage = `(${n} ${n === 1 ? "Tag" : "Tage"})`;
  if (z.von_grund === "termin") return `seit dem letzten Termin am ${datum(z.von)} ${tage}`;
  if (z.von_grund === "kontakt") return `seit dem letzten Kontakt am ${datum(z.von)} ${tage}`;
  return `seit dem ${datum(z.von)} ${tage}`;
}

function Inhalt({ z }: { z: KiZusammenfassung }) {
  const [quellenOffen, setQuellenOffen] = useState(false);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const p: KiPruefung = z.pruefung ?? {};
  const fakten = new Map(z.fakten.map((f) => [f.nr, f]));
  const auswahl = gewaehlt != null ? fakten.get(gewaehlt) : undefined;
  const link = quellLink(z.patient, auswahl);
  const listeId = `auf-einen-blick-quellen-${z.id}`;
  if (z.status === "fehler") {
    return <Meldung art="warn">Die Zusammenfassung konnte nicht erstellt werden{z.fehler ? `: ${z.fehler}` : "."}</Meldung>;
  }
  const absaetze = z.entwurf.trim().split(/\n\s*\n/).filter((a) => a.trim());
  const pruefungHinweise = [
    p.unbelegte_werte?.length ? `Zahlen/Daten ohne Beleg: ${p.unbelegte_werte.join(", ")}` : "",
    p.saetze_ohne_beleg?.length ? `${p.saetze_ohne_beleg.length} ${p.saetze_ohne_beleg.length === 1 ? "Satz" : "Sätze"} ohne Quellenangabe` : "",
    p.unbekannte_belege?.length ? `Verweise auf nicht vorhandene Quellen: ${p.unbekannte_belege.map((n) => `[${n}]`).join(", ")}` : "",
    p.empfehlung_oder_bewertung?.length ? "klingt teils nach Empfehlung oder Bewertung" : "",
  ].filter(Boolean);
  return (
    <>
      {p.ok === false && pruefungHinweise.length ? (
        <Meldung art="warn" className="text-[0.8125rem]">
          <strong>Gegenprüfung:</strong> {pruefungHinweise.join(" · ")}. Betroffene Stellen sind markiert.
        </Meldung>) : null}
      <div className="text-sm flex flex-col gap-2 max-h-[22rem] overflow-y-auto pr-1" data-testid="auf-einen-blick-text">
        {absaetze.map((a, i) => (
          <p key={i} className="m-0 leading-relaxed">
            {a.split("\n").map((zeile, j) => (
              <span key={j}>{j > 0 ? <br /> : null}<Zeile text={zeile} erste={j === 0} pruefung={p} fakten={fakten}
                gewaehlt={gewaehlt} onBeleg={(n) => setGewaehlt(n === gewaehlt ? null : n)} /></span>))}
          </p>))}
      </div>
      {gewaehlt != null ? (
        <div className="text-[0.8125rem] rounded bg-fein px-2.5 py-1.5 flex items-start gap-2" role="status">
          <span className="font-medium">[{gewaehlt}]</span>
          <span className="flex-1 min-w-0">{auswahl ? <>{auswahl.text}{auswahl.datum ? <span className="gedaempft"> · {datum(auswahl.datum)}</span> : null}
            {link ? <> · <Link to={link}>öffnen</Link></> : null}</> : <span className="text-fehler">Diese Quelle gibt es nicht.</span>}</span>
          <button type="button" className="bg-transparent border-0 p-0 cursor-pointer gedaempft" aria-label="Quelle schließen" onClick={() => setGewaehlt(null)}>
            <Icon name="x" groesse={14} aria-hidden="true" /></button>
        </div>) : null}
      <div className="text-[0.8125rem]">
        <button type="button" className="bg-transparent border-0 p-0 cursor-pointer flex items-center gap-1 text-[0.8125rem]"
          aria-expanded={quellenOffen} aria-controls={listeId} onClick={() => setQuellenOffen(!quellenOffen)}>
          <Icon name={quellenOffen ? "hoch" : "runter"} groesse={12} aria-hidden="true" />Quellen ({z.fakten.length})
        </button>
        {quellenOffen ? (
          <ol id={listeId} className="m-0 mt-1 pl-1 list-none flex flex-col gap-0.5">
            {z.fakten.map((f) => {
              const l = quellLink(z.patient, f);
              return (
                <li key={f.nr} value={f.nr} className={cx("flex gap-1.5", gewaehlt === f.nr && "bg-akzent-weich rounded")}>
                  <span className="num gedaempft shrink-0 min-w-[2.2em] text-right">[{f.nr}]</span>
                  <span>{l ? <Link to={l}>{f.text}</Link> : f.text}
                  {f.datum ? <span className="gedaempft"> · {datum(f.datum)}</span> : null}</span>
                </li>);
            })}
          </ol>) : null}
      </div>
      <div className="text-[0.75rem] gedaempft">
        Erstellt {zeitpunkt(z.fertig_am ?? z.erstellt_am)}{" "}
        {z.grund === "termin" ? `(nachts${z.termin_datum ? ` für den Termin am ${datum(z.termin_datum)}` : ""})`
          : `(auf Anforderung${z.angefordert_von_name ? ` von ${z.angefordert_von_name}` : ""})`}
        {z.modell ? ` · Modell: ${z.modell}` : " · ohne KI-Modell direkt aus den Fakten"}
        {" · "}Entscheidungshilfe, keine medizinische Bewertung.
      </div>
    </>
  );
}

/** Leerzeichen vereinheitlichen, damit Sätze der Gegenprüfung (auf 160 Zeichen gekürzt) wiedergefunden werden */
function norm(s: string) { return s.replace(/\s+/g, " ").trim(); }

function satzTrifft(satz: string, liste: string[] | undefined): boolean {
  if (!liste?.length) return false;
  const s = norm(satz);
  if (s.length < 3) return false;
  return liste.some((x) => { const n = norm(x); return n.length > 0 && (s.startsWith(n) || n.startsWith(s)); });
}

/** unbelegter Wert als Muster: Daten mit oder ohne führende Null, Kommazahlen auch mit Punkt */
function wertMuster(werte: string[] | undefined): RegExp | null {
  const teile = (werte ?? []).filter(Boolean).map((w) => {
    const d = /^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$/.exec(w);
    if (d) return `0?${d[1]}\\.0?${d[2]}\\.${d[3]}`;
    return w.split(",").map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("[.,]");
  });
  if (!teile.length) return null;
  return new RegExp(`(?<![\\d.,])(?:${teile.join("|")})(?![\\d]|[.,]\\d)`, "g");
}

function Zeile({ text, erste, pruefung, fakten, gewaehlt, onBeleg }: {
  text: string; erste: boolean; pruefung: KiPruefung; fakten: Map<number, KiFakt>; gewaehlt: number | null; onBeleg: (n: number) => void;
}) {
  // Stichwort am Absatzanfang („Labor:“, „Infusionsplan:“ …) hervorheben
  let rest = text;
  let stichwort: ReactNode = null;
  const m = erste ? /^([A-ZÄÖÜ][\wäöüßÄÖÜ/ -]{1,30}:)(\s)/.exec(text) : null;
  if (m) { stichwort = <strong>{m[1]}</strong>; rest = text.slice(m[1].length); }
  const muster = wertMuster(pruefung.unbelegte_werte);
  const saetze = rest.split(/(?<=[.!?])(\s+)/);
  return (
    <>
      {stichwort}
      {saetze.map((satz, i) => {
        if (!satz || /^\s+$/.test(satz)) return satz;
        const ohneBeleg = satzTrifft(satz, pruefung.saetze_ohne_beleg);
        const bewertung = satzTrifft(satz, pruefung.empfehlung_oder_bewertung);
        const inhalt = <SatzInhalt satz={satz} muster={muster} fakten={fakten} gewaehlt={gewaehlt} onBeleg={onBeleg} />;
        if (!ohneBeleg && !bewertung) return <span key={i}>{inhalt}</span>;
        const titel = [ohneBeleg ? "Satz ohne Quellenangabe" : "", bewertung ? "klingt nach Empfehlung oder Bewertung" : ""].filter(Boolean).join(" · ");
        return (
          <mark key={i} className={cx("rounded-sm px-0.5 text-inherit underline decoration-dotted underline-offset-2",
            bewertung ? "bg-fehler-bg" : "bg-warn-bg")} title={titel}>
            {inhalt}<span className="sr-only"> ({titel})</span>
          </mark>);
      })}
    </>
  );
}

function SatzInhalt({ satz, muster, fakten, gewaehlt, onBeleg }: {
  satz: string; muster: RegExp | null; fakten: Map<number, KiFakt>; gewaehlt: number | null; onBeleg: (n: number) => void;
}) {
  const aus: ReactNode[] = [];
  let pos = 0;
  for (const b of satz.matchAll(BELEG)) {
    const idx = b.index ?? 0;
    if (idx > pos) aus.push(<Werte key={`t${pos}`} text={satz.slice(pos, idx)} muster={muster} />);
    const nummern = b[1].split(/\s*,\s*/).map(Number);
    aus.push(
      <span key={`b${idx}`} className="whitespace-nowrap">
        {nummern.map((n) => {
          const f = fakten.get(n);
          return (
            <button key={n} type="button" onClick={() => onBeleg(n)} aria-pressed={gewaehlt === n}
              title={f ? `[${n}] ${f.text}${f.datum ? ` (${datum(f.datum)})` : ""}` : `[${n}] Quelle nicht vorhanden`}
              aria-label={f ? `Quelle ${n}: ${f.text}` : `Quelle ${n} nicht vorhanden`}
              className={cx("inline-block align-super text-[0.6875rem] leading-none mx-px px-1 py-0.5 rounded border cursor-pointer",
                f ? "border-rand bg-fein text-akzent-text" : "border-fehler bg-fehler-bg text-fehler",
                gewaehlt === n && "bg-akzent-weich")}>{n}</button>);
        })}
      </span>);
    pos = idx + b[0].length;
  }
  if (pos < satz.length) aus.push(<Werte key={`t${pos}`} text={satz.slice(pos)} muster={muster} />);
  return <>{aus}</>;
}

function Werte({ text, muster }: { text: string; muster: RegExp | null }) {
  if (!muster) return <>{text}</>;
  const aus: ReactNode[] = [];
  let pos = 0;
  for (const m of text.matchAll(muster)) {
    const idx = m.index ?? 0;
    if (idx > pos) aus.push(text.slice(pos, idx));
    aus.push(<mark key={idx} className="rounded-sm px-0.5 bg-warn-bg text-inherit font-medium outline outline-1 outline-warn"
      title="Wert ohne Beleg in den Quellen">{m[0]}<span className="sr-only"> (ohne Beleg)</span></mark>);
    pos = idx + m[0].length;
  }
  if (pos < text.length) aus.push(text.slice(pos));
  return <>{aus}</>;
}
