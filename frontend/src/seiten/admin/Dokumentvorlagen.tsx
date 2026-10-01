/**
 * Entwurf 18 · Dokumentvorlagen: Infusionsplan und Patientendatenblatt aus Blöcken (WYSIWYG).
 * Aufbau links, Seite in der Mitte, Eigenschaften des markierten Blocks rechts. Platzhalter nur aus der festen Liste
 * des Servers. Entwurf → Veröffentlichen; jede Version bleibt erhalten, freigegebene Pläne behalten ihr PDF.
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, api, apiDatei } from "@/lib/api";
import type { Seite as Seitenliste } from "@/lib/api";
import { useBriefkopf } from "@/lib/daten";
import { datum, zeitpunkt } from "@/lib/format";
import { Logo } from "@/components/layout/logo";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, Segmente, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { useSortierbar, verschiebe } from "@/components/ui/sortierbar";
import { PdfLeser } from "@/components/PdfAnsicht";

type Art = "infusionsplan" | "patientendatenblatt";
type Optionen = {
  schrift?: "klein" | "normal" | "gross"; ausrichtung?: "links" | "mitte" | "rechts"; fett?: boolean; kursiv?: boolean;
  ausblenden_wenn_leer?: boolean; nicht_teilen?: boolean; ueberschrift?: boolean; linie_oben?: boolean;
  neben_vorherigem?: Breite;
};
type Breite = "drittel" | "haelfte" | "zwei_drittel";
type Eintrag = { label: string; wert: string };
export type Block = {
  id: string; typ: string; bezeichnung?: string; optionen?: Optionen;
  text?: string; zusatz_label?: string; zusatz?: string; spalten?: number; felder?: Eintrag[]; quelle?: string;
  linie?: string; hoehe_mm?: number; links?: string; rechts?: string; rechts_klein?: boolean;
  absender?: boolean; linienfarbe?: string; falzmarken?: boolean; mit_linie?: boolean;
  untertitel?: string; darstellung?: "paare" | "befund"; spaltenkoepfe?: boolean; neben_logo?: boolean;
};
type Version = {
  id: number; version: number | null; status: "entwurf" | "aktiv" | "abgeloest"; notiz: string; erstellt_am: string;
  geaendert_am: string; geaendert_von: string | null; veroeffentlicht_am: string | null; veroeffentlicht_von: string | null;
};
type Uebersicht = { art: Art; name: string; aktiv: Version; entwurf: Version | null; versionen: Version[] };
type Aufbau = Uebersicht & {
  bausteine: { typ: string; name: string }[];
  felder: { name: string; beschreibung: string; html: boolean }[];
  tabellen: { quelle: string; name: string; spalten: string[] }[];
};
type Entwurf = Version & { ist_entwurf: boolean; grundlage?: number; bloecke: Block[] };

const TYPNAME: Record<string, string> = {
  briefkopf: "Briefkopf", titel: "Titel", text: "Text", zweispaltig: "Zwei Spalten", datenfelder: "Datenfelder", tabelle: "Tabelle", trennlinie: "Trennlinie",
  leerraum: "Leerraum", unterschrift: "Unterschrift", seitenumbruch: "Seitenumbruch", fusszeile: "Fußzeile", kopfkarte: "Kopfkarte",
};
const HINWEIS: Record<string, string> = {
  briefkopf: "Logo (und auf Wunsch Absender) aus „Briefkopf und Logo“, auf Wunsch darunter eine farbige Linie; Falzmarken am linken Rand.",
  kopfkarte: "Kasten wie der Kopf der Akte in EPM: Name groß, darunter weitere Zeilen, rechts ein kleiner Text, unten Kennzahlen nebeneinander.",
  titel: "Überschrift des Dokuments, rechts daneben ein Zusatz wie „gültig ab“.",
  text: "Freier Text. Datenfelder werden beim Erzeugen eingesetzt; Zeilen ohne Wert entfallen.",
  zweispaltig: "Zwei Textspalten nebeneinander, z. B. Anschrift links und „Unsere Zeichen“ rechts. Zeilen ohne Wert entfallen.",
  datenfelder: "Bezeichnung links, Wert rechts. Mehrere Spalten setzen Paare nebeneinander. „Wie Laborbefund“: Menge rechtsbündig, Einheit in eigener Spalte.",
  tabelle: "Feste Spalten; die Zeilen kommen aus der Akte bzw. dem Plan.",
  trennlinie: "Waagerechte Linie.",
  leerraum: "Abstand in Millimetern.",
  unterschrift: "Angaben zur Freigabe und eine Linie für die Unterschrift.",
  seitenumbruch: "Alles danach beginnt auf einer neuen Seite.",
  fusszeile: "Steht auf jeder Seite unten (bis 8 Zeilen links, rechts z. B. die Seitenzahl). {Seite} und {Seiten} werden zur Seitenzahl.",
};
/** Bausteine aus dem Entwurf; Briefkopf, Titel und Fußzeile gibt es je Vorlage einmal */
const BAUSTEINE = ["text", "zweispaltig", "datenfelder", "tabelle", "kopfkarte", "trennlinie", "leerraum", "unterschrift", "seitenumbruch", "titel", "briefkopf", "fusszeile"];
/** Diese Blöcke lassen sich neben den vorherigen setzen (wie auf dem Server geprüft) */
const NEBENEINANDER = ["text", "datenfelder", "tabelle", "unterschrift"];
const BREITE: Record<Breite, number> = { drittel: 34, haelfte: 48.5, zwei_drittel: 63 };
const BREITE_TEXT: Record<Breite, string> = { drittel: "ein Drittel", haelfte: "die Hälfte", zwei_drittel: "zwei Drittel" };
const PLATZHALTER = /\{\{\s*([^{}]+?)\s*\}\}/g;

/** Breiten in % wie auf dem Server (pdf._nebeneinander): die rechten Blöcke nach Wahl, der erste den Rest */
function breitenFuer(gruppe: Block[]): number[] {
  const abstand = 4;
  let rechts = gruppe.slice(1).map((b) => BREITE[b.optionen?.neben_vorherigem ?? "haelfte"]);
  let erste = 100 - rechts.reduce((x, y) => x + y, 0) - abstand * (gruppe.length - 1);
  if (erste < 15) {
    rechts = rechts.map(() => (100 - abstand * (gruppe.length - 1)) / gruppe.length);
    erste = rechts[0];
  }
  return [erste, ...rechts];
}

function neueId(typ: string, bloecke: Block[]): string {
  let i = 1;
  while (bloecke.some((b) => b.id === `${typ}-${i}`)) i += 1;
  return `${typ}-${i}`;
}

function neuerBlock(typ: string, bloecke: Block[], tabellen: Aufbau["tabellen"]): Block {
  const b: Block = { id: neueId(typ, bloecke), typ, bezeichnung: TYPNAME[typ] };
  if (typ === "titel") Object.assign(b, { text: "Titel", zusatz_label: "", zusatz: "" });
  if (typ === "text") b.text = "Text";
  if (typ === "fusszeile") Object.assign(b, { text: "{{Absender.Name}}", rechts: "{Seite}/{Seiten}" });
  if (typ === "zweispaltig") Object.assign(b, { links: "{{Patient.Name}}", rechts: "Patienten-Nr.: {{Patient.Nummer}}", rechts_klein: true });
  if (typ === "briefkopf") Object.assign(b, { absender: false, linienfarbe: "#EE8D4D", falzmarken: true, mit_linie: true });
  if (typ === "kopfkarte") Object.assign(b, { text: "{{Patient.Name}}", untertitel: "", rechts: "", felder: [{ label: "Patienten-Nr.", wert: "{{Patient.Nummer}}" }] });
  if (typ === "datenfelder") Object.assign(b, { spalten: 1, felder: [{ label: "Bezeichnung", wert: "{{Heute}}" }] });
  if (typ === "tabelle") b.quelle = tabellen[0]?.quelle;
  if (typ === "unterschrift") Object.assign(b, { felder: [], linie: "Unterschrift" });
  if (typ === "leerraum") b.hoehe_mm = 6;
  return b;
}

/** Text mit Platzhaltern als Chips (wie im Entwurf) */
function MitFeldern({ text }: { text?: string }) {
  const teile: ReactNode[] = [];
  let pos = 0;
  for (const m of (text ?? "").matchAll(PLATZHALTER)) {
    teile.push(text!.slice(pos, m.index));
    teile.push(<span key={m.index} className="feldchip">{m[1]}</span>);
    pos = (m.index ?? 0) + m[0].length;
  }
  teile.push((text ?? "").slice(pos));
  return <>{teile.map((t, i) => typeof t === "string" ? <Fragment key={`t${i}`}>{t.split("\n").map((z, j) => <Fragment key={j}>{j ? <br /> : null}{z}</Fragment>)}</Fragment> : t)}</>;
}

function stil(o?: Optionen): string {
  return cx(o?.fett && "font-semibold", o?.kursiv && "italic", o?.ausrichtung === "mitte" && "text-center",
    o?.ausrichtung === "rechts" && "text-right");
}

/** Grundschrift eines Blocks in der Seitenvorschau; alles im Block ist relativ dazu (em), wie im PDF (9,5 / 8 / 11,5 pt) */
const SCHRIFT_PX: Record<string, number> = { klein: 8.4, normal: 10, gross: 12.1 };

function BlockAnsicht({ b, tabellen }: { b: Block; tabellen: Aufbau["tabellen"] }) {
  const briefkopf = useBriefkopf();
  const a = briefkopf.data ? briefkopf.data.absender[briefkopf.data.aktiv] : null;
  const kopf = b.optionen?.ueberschrift && b.bezeichnung
    ? <div className="text-[1.05em] font-semibold pb-1 mb-1 border-b border-[#e6e5ee]">{b.bezeichnung}</div> : null;
  // Bereiche mit Überschrift erscheinen im PDF als Karte wie in der Oberfläche
  const karte = b.optionen?.ueberschrift && b.bezeichnung ? "border border-[#d9d8e3] rounded-md px-2 py-1.5" : "";
  switch (b.typ) {
    case "briefkopf":
      return (
        <div className={cx("flex justify-between items-end pb-2", b.mit_linie !== false && "border-b-2")} style={{ borderColor: /^#[0-9a-f]{6}$/i.test(b.linienfarbe ?? "") ? b.linienfarbe : "#251F53" }}>
          <Logo className="w-[150px] h-[53px]" version={briefkopf.data?.logo.sha256} />
          {b.absender !== false ? <div className="flex flex-col items-end text-[0.9em] text-[#555]">
            {a ? <><span>{a.strasse} · {a.plz} {a.ort}</span><span>Tel. {a.telefon}</span><span>{a.email}</span></> : null}
          </div> : null}
        </div>
      );
    case "titel":
      return (
        <div className={cx("flex", b.neben_logo || b.optionen?.ausrichtung === "rechts" ? "flex-col items-end"
          : b.optionen?.ausrichtung === "mitte" ? "flex-col items-center" : "justify-between items-baseline", stil(b.optionen))}>
          <span className="text-[1.6em] font-semibold"><MitFeldern text={b.text} /></span>
          <span className="text-[1em] text-[#555]">{b.zusatz_label} <MitFeldern text={b.zusatz} /></span>
        </div>
      );
    case "text":
      return <div className={cx("text-[1em] leading-relaxed", karte, b.optionen?.linie_oben && "border-t border-[#c9c8d4] pt-1", stil(b.optionen))}>{kopf}<MitFeldern text={b.text} /></div>;
    case "kopfkarte":
      return (
        <div className={stil(b.optionen)}>{kopf}<div className="border border-[#d9d8e3] rounded-md px-2.5 py-2 text-[1em]">
          <div className="flex justify-between gap-3 items-start">
            <div><div className="text-[1.3em] font-semibold"><MitFeldern text={b.text} /></div>
              {b.untertitel ? <div className="text-[#3b3953]"><MitFeldern text={b.untertitel} /></div> : null}</div>
            {b.rechts ? <div className="text-right text-[0.8em] text-[#00325a]"><MitFeldern text={b.rechts} /></div> : null}
          </div>
          {b.felder?.length ? <div className="flex mt-1.5 pt-1 border-t border-[#ececf2]">
            {b.felder.map((e, i) => <div key={i} className={cx("flex flex-col px-2 min-w-0", i ? "border-l border-[#e1e0ea]" : "pl-0")}>
              <span className="text-[0.8em] text-[#5d5b72]">{e.label}</span><span className="truncate"><MitFeldern text={e.wert} /></span></div>)}
          </div> : null}
        </div></div>
      );
    case "fusszeile":
      return <div className="flex justify-between gap-3 text-[0.8em] text-[#00325a] leading-snug"><span><MitFeldern text={b.text} /></span><span><MitFeldern text={b.rechts} /></span></div>;
    case "zweispaltig":
      return (
        <div className={cx("flex justify-between gap-4 text-[1em]", stil(b.optionen))}>
          <div><MitFeldern text={b.links} /></div>
          <div className={cx("text-right text-[#00325a]", b.rechts_klein && "text-[0.85em]")}><MitFeldern text={b.rechts} /></div>
        </div>
      );
    case "datenfelder":
    case "unterschrift": {
      if (b.typ === "datenfelder" && b.darstellung === "befund") {
        return (
          <div className={cx(karte, stil(b.optionen))}>
            {kopf}
            <table className="w-full border-collapse text-[1em]">
              {b.spaltenkoepfe ? <thead><tr>{["Bestandteil", "Menge", "Einheit"].map((t, i) => <th key={t} className={cx("font-medium text-[0.8em] text-[#666] border-b border-[#ccc] py-[2px] px-1.5", i === 1 ? "text-right" : "text-left")}>{t}</th>)}</tr></thead> : null}
              <tbody>{(b.felder ?? []).map((e, i) => (
                <tr key={i}><td className="py-[2px] px-1.5 border-b border-[#eee] align-top">{e.label}</td>
                  <td colSpan={2} className="py-[2px] px-1.5 border-b border-[#eee] align-top text-right"><MitFeldern text={e.wert} /></td></tr>
              ))}</tbody>
            </table>
          </div>
        );
      }
      const n = b.typ === "unterschrift" ? Math.min(Math.max(b.felder?.length ?? 1, 1), 4) : b.spalten ?? 1;
      const felder = b.felder ?? [];
      const zeilen = Array.from({ length: Math.ceil(felder.length / n) }, (_, i) => felder.slice(i * n, i * n + n));
      return (
        <div className={cx(karte, stil(b.optionen))}>
          {kopf}
          <table className="w-full border-collapse text-[1em]"><tbody>
            {zeilen.map((z, i) => (
              <tr key={i}>{z.map((e, j) => <Fragment key={j}>
                <td className="py-[3px] pr-2 text-[#666] border-b border-[#eee] align-top" style={{ width: `${36 / n}%` }}>{e.label}</td>
                <td className="py-[3px] pr-2 border-b border-[#eee] align-top"><MitFeldern text={e.wert} /></td>
              </Fragment>)}</tr>
            ))}
          </tbody></table>
          {b.typ === "unterschrift" ? <div className="mt-6 w-[200px] border-t border-[#1b1932] pt-0.5 text-[0.85em] text-[#5d5b72]">{b.linie || "Unterschrift"}</div> : null}
        </div>
      );
    }
    case "tabelle": {
      const t = tabellen.find((x) => x.quelle === b.quelle);
      return (
        <div className={cx(karte, stil(b.optionen))}>
          {kopf}
          <table className="w-full border-collapse text-[1em]">
            <thead><tr>{(t?.spalten ?? []).map((s, i) => <th key={i} className="text-left font-semibold text-[#666] border-b border-[#ccc] py-[3px] pr-2">{s}</th>)}</tr></thead>
            <tbody><tr><td colSpan={t?.spalten.length ?? 1} className="py-[3px] text-[#888] italic">{t?.name ?? "unbekannte Tabelle"}</td></tr></tbody>
          </table>
        </div>
      );
    }
    case "trennlinie":
      return <hr className="border-0 border-t border-[#ccc] m-0" />;
    case "leerraum":
      return <div style={{ height: (b.hoehe_mm ?? 6) * 2.1 }} className="bg-[repeating-linear-gradient(45deg,transparent,transparent_4px,#f2f1f6_4px,#f2f1f6_8px)]" />;
    case "seitenumbruch":
      return <div className="text-center text-[0.9em] text-[#888] border-t border-dashed border-[#bbb] pt-0.5">Seitenumbruch</div>;
    default:
      return null;
  }
}

/** Bereich „Dokumentvorlagen“ der Seite Vorlagen (wie Briefkopf, Auswahllisten, Grenzwerte). Die Knöpfe stehen oben
 *  rechts im Seitenkopf, wo die anderen Bereiche „Speichern“ haben. */
export function DokumentvorlagenBereich({ aktionenZiel, onGeaendert }: {
  aktionenZiel: HTMLElement | null; onGeaendert: (geaendert: boolean) => void;
}) {
  const [art, setArt] = useState<Art>("infusionsplan");
  return <EditorFuerArt key={art} art={art} setArt={setArt} aktionenZiel={aktionenZiel} onGeaendert={onGeaendert} />;
}

function EditorFuerArt({ art, setArt, aktionenZiel, onGeaendert }: {
  art: Art; setArt: (a: Art) => void; aktionenZiel: HTMLElement | null; onGeaendert: (geaendert: boolean) => void;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const aufbau = useQuery({ queryKey: ["vorlagen", art], queryFn: () => api<Aufbau>(`vorlagen/${art}/`) });
  const entwurf = useQuery({ queryKey: ["vorlagen", art, "entwurf"], queryFn: () => api<Entwurf>(`vorlagen/${art}/entwurf/`) });
  const [bloecke, setBloecke] = useState<Block[] | null>(null);
  const [geladen, setGeladen] = useState("");
  const [auswahl, setAuswahl] = useState<string | null>(null);
  const [vorschau, setVorschau] = useState(false);
  const [veroeffentlichen, setVeroeffentlichen] = useState(false);
  const [verwerfen, setVerwerfen] = useState(false);
  const fokus = useRef<{ setze: (feld: string) => void } | null>(null);

  useEffect(() => {
    if (entwurf.data && bloecke === null) {
      setBloecke(structuredClone(entwurf.data.bloecke));
      setGeladen(JSON.stringify(entwurf.data.bloecke));
      setAuswahl(entwurf.data.bloecke[0]?.id ?? null);
    }
  }, [entwurf.data, bloecke]);

  const neuLaden = (b: Block[]) => { setBloecke(structuredClone(b)); setGeladen(JSON.stringify(b)); };
  const geaendert = bloecke !== null && JSON.stringify(bloecke) !== geladen;
  useEffect(() => { onGeaendert(geaendert); }, [geaendert, onGeaendert]);

  const speichern = useMutation({
    mutationFn: () => api<Entwurf>(`vorlagen/${art}/entwurf/`, { method: "PUT", body: { bloecke } }),
    onSuccess: (e) => {
      neuLaden(e.bloecke);
      qc.setQueryData(["vorlagen", art, "entwurf"], e);
      void qc.invalidateQueries({ queryKey: ["vorlagen", art], exact: true });
      melden("Entwurf gespeichert.");
    },
  });
  const freigeben = useMutation({
    mutationFn: async () => {
      if (geaendert || !entwurf.data?.ist_entwurf) await api(`vorlagen/${art}/entwurf/`, { method: "PUT", body: { bloecke } });
      return api<Uebersicht>(`vorlagen/${art}/veroeffentlichen/`, { method: "POST" });
    },
    onSuccess: (u) => {
      setVeroeffentlichen(false);
      setBloecke(null);
      void qc.invalidateQueries({ queryKey: ["vorlagen"] });
      melden(`Version ${u.aktiv.version} veröffentlicht. Sie gilt ab sofort für neue PDFs.`);
    },
  });
  const verwerfenM = useMutation({
    mutationFn: () => api(`vorlagen/${art}/entwurf/`, { method: "DELETE" }),
    onSuccess: () => {
      setVerwerfen(false);
      setBloecke(null);
      void qc.invalidateQueries({ queryKey: ["vorlagen"] });
      melden("Entwurf verworfen.");
    },
  });
  const uebernehmen = useMutation({
    mutationFn: (v: number) => api<Entwurf>(`vorlagen/${art}/versionen/${v}/`),
    onSuccess: (v) => { setBloecke(structuredClone(v.bloecke)); setAuswahl(v.bloecke[0]?.id ?? null); melden(`Version ${v.version} als Grundlage geladen – noch nicht gespeichert.`); },
  });
  const startvorlage = useMutation({
    mutationFn: () => api<{ bloecke: Block[] }>(`vorlagen/${art}/startvorlage/`),
    onSuccess: (v) => { setBloecke(structuredClone(v.bloecke)); setAuswahl(v.bloecke[0]?.id ?? null); melden("Mitgelieferte Startvorlage als Grundlage geladen – noch nicht gespeichert."); },
  });

  const sort = useSortierbar(bloecke ?? [], (neu) => setBloecke(neu));
  if (!aufbau.data || !entwurf.data || !bloecke) return <><Fehleranzeige fehler={aufbau.error ?? entwurf.error} /><Laden /></>;
  const a = aufbau.data;
  const gewaehlt = bloecke.find((b) => b.id === auswahl) ?? null;
  const index = gewaehlt ? bloecke.indexOf(gewaehlt) : -1;
  const aendere = (neu: Partial<Block>) => setBloecke((alt) => (alt ?? []).map((b) => (b.id === auswahl ? { ...b, ...neu } : b)));
  const aendereOptionen = (neu: Partial<Optionen>) => aendere({ optionen: { ...gewaehlt?.optionen, ...neu } });
  const verschiebe = (i: number, nach: number) => {
    if (nach < 0 || nach >= bloecke.length) return;
    const neu = [...bloecke];
    const [x] = neu.splice(i, 1);
    neu.splice(nach, 0, x);
    setBloecke(neu);
  };
  const entferne = (id: string) => { const neu = bloecke.filter((b) => b.id !== id); setBloecke(neu); setAuswahl(neu[0]?.id ?? null); };
  const hinzufuegen = (typ: string) => {
    const b = neuerBlock(typ, bloecke, a.tabellen);
    const nach = typ === "briefkopf" ? 0 : typ === "fusszeile" ? bloecke.length : index >= 0 ? index + 1 : bloecke.length;
    const neu = [...bloecke];
    neu.splice(nach, 0, b);
    setBloecke(neu);
    setAuswahl(b.id);
  };
  // Blöcke mit „neben dem vorherigen“ in eine Zeile setzen, wie im PDF
  const gruppen: number[][] = [];
  bloecke.forEach((b, i) => {
    if (b.optionen?.neben_vorherigem && gruppen.length) gruppen[gruppen.length - 1].push(i);
    else gruppen.push([i]);
  });
  const rahmen = (b: Block, i: number) => (
    <div key={b.id} role="button" tabIndex={0} aria-label={`Block ${b.bezeichnung || TYPNAME[b.typ]}`}
      onClick={() => setAuswahl(b.id)} onKeyDown={(e) => { if (e.key === "Enter") setAuswahl(b.id); }}
      className={cx("relative px-2 py-1.5 rounded cursor-pointer", b.id === auswahl ? "outline outline-2 outline-[#251F53]" : "hover:outline hover:outline-1 hover:outline-[#c9c8d4]")}>
      {b.id === auswahl ? <>
        <span className="absolute -top-2.5 left-1.5 text-[10px] bg-[#251F53] text-white px-1.5 rounded-sm">{b.bezeichnung || TYPNAME[b.typ]}</span>
        <span className="absolute -top-3 right-1 flex gap-0.5">
          <button type="button" aria-label="nach oben" disabled={i === 0} onClick={(e) => { e.stopPropagation(); verschiebe(i, i - 1); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[11px] p-0 cursor-pointer">↑</button>
          <button type="button" aria-label="nach unten" disabled={i === bloecke.length - 1} onClick={(e) => { e.stopPropagation(); verschiebe(i, i + 1); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[11px] p-0 cursor-pointer">↓</button>
          <button type="button" aria-label="entfernen" onClick={(e) => { e.stopPropagation(); entferne(b.id); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[11px] p-0 cursor-pointer">×</button>
        </span>
      </> : null}
      <div style={{ fontSize: SCHRIFT_PX[b.optionen?.schrift ?? "normal"] }}><BlockAnsicht b={b} tabellen={a.tabellen} /></div>
    </div>
  );
  const einmal = (typ: string) => ["briefkopf", "fusszeile"].includes(typ) && bloecke.some((b) => b.typ === typ);
  const serverFehler = [speichern.error, freigeben.error].find((e) => e instanceof ApiFehler) as ApiFehler | undefined;
  const fehlerListe = serverFehler ? (Array.isArray((serverFehler.daten as { bloecke?: string[] })?.bloecke)
    ? (serverFehler.daten as { bloecke: string[] }).bloecke : [serverFehler.message]) : [];
  const verInfo = geaendert ? "Ungespeicherte Änderungen"
    : entwurf.data.ist_entwurf ? `Entwurf · gespeichert ${zeitpunkt(entwurf.data.geaendert_am)}`
    : `Version ${a.aktiv.version} ist aktiv`;

  return (
    <div className="flex flex-col gap-5" data-testid="dokumentvorlagen">
      {aktionenZiel ? createPortal(<>
        <span className="text-[0.8125rem] gedaempft" data-testid="vorlage-stand">{verInfo}</span>
        <Knopf icon="dokument" onClick={() => setVorschau(true)}>Vorschau mit Testpatient</Knopf>
        <Knopf laedt={speichern.isPending} disabled={!geaendert} onClick={() => speichern.mutate()}>Entwurf speichern</Knopf>
        <Knopf variante="pri" icon="haken" onClick={() => setVeroeffentlichen(true)} disabled={!geaendert && !entwurf.data.ist_entwurf}>Veröffentlichen</Knopf>
      </>, aktionenZiel) : null}
      <Segmente label="Vorlage" wert={art} onWahl={(w) => { if (!geaendert || window.confirm("Ungespeicherte Änderungen verwerfen?")) setArt(w); }}
        werte={[{ wert: "infusionsplan", text: "Infusionsplan" }, { wert: "patientendatenblatt", text: "Patientendatenblatt" }]} className="self-start" />
      {fehlerListe.length ? <Meldung art="fehler"><ul className="m-0 pl-4" data-testid="vorlage-fehler">{fehlerListe.map((f) => <li key={f}>{f}</li>)}</ul></Meldung> : null}

      <div className="grid grid-cols-1 xl:grid-cols-[220px_minmax(0,1fr)_300px] gap-5 items-start">
        <aside className="flex flex-col gap-3.5 min-w-0">
          <Karte className="p-2.5 flex flex-col gap-0.5" data-testid="aufbau">
            <span className="lbl px-1.5 pb-1.5 pt-1">Aufbau</span>
            {bloecke.map((b, i) => (
              <div key={b.id} {...sort.zeile(i)} className={cx("flex items-center rounded-md", sort.ueber === i && "outline outline-2 outline-akzent")}>
                <button type="button" aria-current={b.id === auswahl ? "true" : undefined} onClick={() => setAuswahl(b.id)}
                  className={cx("flex-1 flex justify-between items-center gap-2 px-2.5 py-[7px] border-0 rounded-md text-[13.5px] text-left cursor-pointer",
                    b.id === auswahl ? "bg-akzent-weich text-akzent-text font-medium" : "bg-transparent hover:bg-fein")}>
                  <span className="truncate">{b.bezeichnung || TYPNAME[b.typ]}</span>
                  <span className="text-[11.5px] gedaempft shrink-0">{TYPNAME[b.typ]}</span>
                </button>
                <span tabIndex={0} {...sort.griff(i, b.bezeichnung || TYPNAME[b.typ], `vorlage-${art}`)} className="px-1 cursor-grab gedaempft"><Icon name="griff" /></span>
              </div>
            ))}
          </Karte>
          <Karte className="p-3 flex flex-col gap-2" data-testid="bausteine">
            <span className="lbl">Bausteine</span>
            <div className="flex flex-wrap gap-1.5">
              {BAUSTEINE.filter((t) => a.bausteine.some((x) => x.typ === t)).map((t) => (
                <button key={t} type="button" disabled={einmal(t)} onClick={() => hinzufuegen(t)}
                  className="px-2.5 py-1.5 border border-dashed border-rand rounded-lg bg-flaeche text-[13px] cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
                  + {TYPNAME[t]}
                </button>
              ))}
            </div>
            <span className="text-xs gedaempft leading-normal">Neuer Block kommt hinter den markierten. Reihenfolge per Ziehen im Aufbau, mit den Pfeiltasten am Griff oder mit ↑ ↓ am markierten Block.</span>
          </Karte>
          <Karte className="p-3.5 flex flex-col gap-1.5" data-testid="versionen">
            <span className="lbl">Versionen</span>
            <ul className="m-0 p-0 list-none flex flex-col gap-1 text-[13px]">
              {a.entwurf ? <li><strong>Entwurf</strong> · {datum(a.entwurf.geaendert_am)}{a.entwurf.geaendert_von ? ` · ${a.entwurf.geaendert_von}` : ""}</li> : null}
              {a.versionen.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-2">
                  <span>v{v.version} · {v.status === "aktiv" ? `aktiv seit ${datum(v.veroeffentlicht_am)}` : datum(v.veroeffentlicht_am)}{v.notiz ? ` · ${v.notiz}` : ""}</span>
                  <button type="button" className="text-xs underline bg-transparent border-0 cursor-pointer text-akzent-text p-0"
                    onClick={() => uebernehmen.mutate(v.version!)} title="Blöcke dieser Version in den Editor laden">laden</button>
                </li>
              ))}
            </ul>
            <button type="button" className="self-start text-xs underline bg-transparent border-0 cursor-pointer text-akzent-text p-0 mt-1"
              onClick={() => startvorlage.mutate()} title="Aufbau, wie er mit EPM ausgeliefert wird, in den Editor laden">Mitgelieferte Startvorlage laden</button>
          </Karte>
        </aside>

        <div className="py-6 bg-[#E6E5EE] rounded-xl overflow-auto min-w-0" data-testid="vorlage-seite">
          <div className="w-[560px] min-h-[792px] mx-auto px-[38px] py-[34px] bg-white text-[#1a1a1a] shadow-md flex flex-col gap-2.5">
            {gruppen.map((g) => g.length === 1 ? rahmen(bloecke[g[0]], g[0]) : (
              <div key={`paar-${bloecke[g[0]].id}`} className="flex justify-between items-start" data-testid="nebeneinander">
                {g.map((i, j) => <div key={bloecke[i].id} style={{ width: `${breitenFuer(g.map((x) => bloecke[x]))[j]}%` }}>{rahmen(bloecke[i], i)}</div>)}
              </div>
            ))}
          </div>
        </div>

        <aside className="flex flex-col gap-3.5 min-w-0">
          {gewaehlt ? <BlockEigenschaften b={gewaehlt} aufbau={a} aendere={aendere} aendereOptionen={aendereOptionen} fokus={fokus} /> : <Karte className="p-4 text-sm gedaempft">Block im Aufbau oder auf der Seite markieren.</Karte>}
          <Karte className="p-4 flex flex-col gap-2" data-testid="datenfelder">
            <span className="lbl">Datenfeld einfügen</span>
            <div className="flex flex-wrap gap-1">
              {a.felder.map((f) => (
                <button key={f.name} type="button" title={f.beschreibung} onMouseDown={(e) => e.preventDefault()}
                  onClick={() => fokus.current?.setze(f.name)}
                  className="px-1.5 py-0.5 rounded bg-fein border-0 text-[12px] font-mono text-text2 cursor-pointer hover:bg-akzent-weich">{f.name}</button>
              ))}
            </div>
            <span className="text-xs gedaempft">Nur diese Felder sind erlaubt. Tippfehler in Platzhaltern sind damit ausgeschlossen. Zuerst in ein Textfeld des Blocks klicken.</span>
          </Karte>
          <div className="flex gap-2 p-3 rounded-lg bg-fein text-[12.5px] leading-normal text-text2">
            <Icon name="info" /><span>Neue Version gilt ab Veröffentlichung. Bereits freigegebene Pläne behalten ihr PDF unverändert.</span>
          </div>
          {entwurf.data.ist_entwurf ? <Knopf variante="geist" onClick={() => setVerwerfen(true)}>Entwurf verwerfen</Knopf> : null}
        </aside>
      </div>

      <VorschauDialog art={art} bloecke={bloecke} offen={vorschau} onOffen={setVorschau} />
      <Dialog offen={veroeffentlichen} onOffen={setVeroeffentlichen} titel={`${a.name}: neue Version veröffentlichen`} breite={520}
        beschreibung={`Wird Version ${Math.max(0, ...a.versionen.map((v) => v.version ?? 0)) + 1}. Sie gilt ab sofort für neue PDFs; Version ${a.aktiv.version} bleibt erhalten.`}
        fuss={<><Knopf onClick={() => setVeroeffentlichen(false)}>Abbrechen</Knopf><Knopf variante="pri" laedt={freigeben.isPending} onClick={() => freigeben.mutate()}>Veröffentlichen</Knopf></>}>
        <span className="text-sm">Bereits freigegebene Pläne behalten ihr PDF unverändert.</span>
        <Fehleranzeige fehler={freigeben.error} />
      </Dialog>
      <Dialog offen={verwerfen} onOffen={setVerwerfen} titel="Entwurf verwerfen" breite={480}
        beschreibung={`Die aktive Version ${a.aktiv.version} bleibt unverändert.`}
        fuss={<><Knopf onClick={() => setVerwerfen(false)}>Abbrechen</Knopf><Knopf variante="dng" laedt={verwerfenM.isPending} onClick={() => verwerfenM.mutate()}>Verwerfen</Knopf></>}>
        <Fehleranzeige fehler={verwerfenM.error} />
      </Dialog>
    </div>
  );
}

/** Textfeld, in das „Datenfeld einfügen“ an der Schreibmarke einsetzt */
function FeldText({ label, wert, onWert, fokus, mehrzeilig }: {
  label: string; wert: string; onWert: (w: string) => void; fokus: { current: { setze: (f: string) => void } | null }; mehrzeilig?: boolean;
}) {
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null);
  const aktuellerWert = useRef(onWert);
  aktuellerWert.current = onWert;
  const merken = () => {
    fokus.current = {
      setze: (feld) => {
        // aktuellen Inhalt aus dem Feld lesen, nicht den Stand beim Fokussieren
        const el = ref.current;
        const aktuell = el?.value ?? wert;
        const pos = el?.selectionStart ?? aktuell.length;
        const ende = el?.selectionEnd ?? pos;
        const einfuegen = `{{${feld}}}`;
        aktuellerWert.current(aktuell.slice(0, pos) + einfuegen + aktuell.slice(ende));
        requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(pos + einfuegen.length, pos + einfuegen.length); });
      },
    };
  };
  return (
    <Feld label={label}>
      {(p) => mehrzeilig
        ? <Textfeld {...p} ref={ref} rows={4} value={wert} onFocus={merken} onChange={(e) => onWert(e.target.value)} className="font-mono text-[13px]" />
        : <Eingabe {...p} ref={ref} value={wert} onFocus={merken} onChange={(e) => onWert(e.target.value)} className="font-mono text-[13px]" />}
    </Feld>
  );
}

function BlockEigenschaften({ b, aufbau, aendere, aendereOptionen, fokus }: {
  b: Block; aufbau: Aufbau; aendere: (n: Partial<Block>) => void; aendereOptionen: (n: Partial<Optionen>) => void;
  fokus: { current: { setze: (f: string) => void } | null };
}) {
  const o = b.optionen ?? {};
  const eintraege = b.felder ?? [];
  const setzeEintrag = (i: number, neu: Partial<Eintrag>) => aendere({ felder: eintraege.map((e, j) => (j === i ? { ...e, ...neu } : e)) });
  // Reihenfolge der Felder: Ziehen am Griff, Pfeiltasten am Griff oder ▲ ▼
  const feldSort = useSortierbar(eintraege, (neu) => aendere({ felder: neu }));
  const textartig = !["briefkopf", "trennlinie", "leerraum", "seitenumbruch"].includes(b.typ);
  return (
    <Karte className="p-4 flex flex-col gap-3" data-testid="block-eigenschaften">
      <div className="flex justify-between items-center"><span className="lbl">Block</span><Chip art="akzent">{TYPNAME[b.typ]}</Chip></div>
      <Feld label="Bezeichnung">{(p) => <Eingabe {...p} value={b.bezeichnung ?? ""} onChange={(e) => aendere({ bezeichnung: e.target.value })} />}</Feld>
      <span className="text-[12.5px] gedaempft leading-normal">{HINWEIS[b.typ]}</span>

      {b.typ === "titel" ? <>
        <FeldText label="Text" wert={b.text ?? ""} onWert={(w) => aendere({ text: w })} fokus={fokus} />
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-2">
          <Feld label="Zusatz">{(p) => <Eingabe {...p} value={b.zusatz_label ?? ""} onChange={(e) => aendere({ zusatz_label: e.target.value })} />}</Feld>
          <FeldText label="Wert" wert={b.zusatz ?? ""} onWert={(w) => aendere({ zusatz: w })} fokus={fokus} />
        </div>
        <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={!!b.neben_logo} onChange={(e) => aendere({ neben_logo: e.target.checked })} />Rechts neben dem Logo</label>
      </> : null}
      {b.typ === "text" || b.typ === "fusszeile" ? <FeldText label="Text" wert={b.text ?? ""} onWert={(w) => aendere({ text: w })} fokus={fokus} mehrzeilig /> : null}
      {b.typ === "fusszeile" ? <FeldText label="Rechts" wert={b.rechts ?? ""} onWert={(w) => aendere({ rechts: w })} fokus={fokus} /> : null}
      {b.typ === "zweispaltig" ? <>
        <FeldText label="Links" wert={b.links ?? ""} onWert={(w) => aendere({ links: w })} fokus={fokus} mehrzeilig />
        <FeldText label="Rechts" wert={b.rechts ?? ""} onWert={(w) => aendere({ rechts: w })} fokus={fokus} mehrzeilig />
        <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={!!b.rechts_klein} onChange={(e) => aendere({ rechts_klein: e.target.checked })} />Rechte Spalte kleiner</label>
      </> : null}
      {b.typ === "briefkopf" ? <>
        <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={b.absender !== false} onChange={(e) => aendere({ absender: e.target.checked })} />Absender neben dem Logo</label>
        <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={!!b.falzmarken} onChange={(e) => aendere({ falzmarken: e.target.checked })} />Falzmarken am linken Rand</label>
        <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={b.mit_linie !== false} onChange={(e) => aendere({ mit_linie: e.target.checked })} />Linie unter dem Logo</label>
        {b.mit_linie !== false ? <label className="flex items-center gap-2 text-[13.5px]">Linienfarbe
          <input type="color" aria-label="Linienfarbe" value={(b.linienfarbe ?? "#251F53").toLowerCase()} onChange={(e) => aendere({ linienfarbe: e.target.value.toUpperCase() })} /></label> : null}
      </> : null}
      {b.typ === "kopfkarte" ? <>
        <FeldText label="Name (groß)" wert={b.text ?? ""} onWert={(w) => aendere({ text: w })} fokus={fokus} />
        <FeldText label="Zeilen darunter" wert={b.untertitel ?? ""} onWert={(w) => aendere({ untertitel: w })} fokus={fokus} mehrzeilig />
        <FeldText label="Rechts (klein)" wert={b.rechts ?? ""} onWert={(w) => aendere({ rechts: w })} fokus={fokus} mehrzeilig />
      </> : null}
      {b.typ === "datenfelder" ? <>
        <Feld label="Darstellung">{(p) => <Auswahl {...p} value={b.darstellung ?? "paare"} onChange={(e) => aendere({ darstellung: e.target.value as Block["darstellung"] })}>
          <option value="paare">Bezeichnung und Wert, auch nebeneinander</option>
          <option value="befund">Wie Laborbefund (Menge rechtsbündig, Einheit eigene Spalte)</option></Auswahl>}</Feld>
        {b.darstellung === "befund"
          ? <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={!!b.spaltenkoepfe} onChange={(e) => aendere({ spaltenkoepfe: e.target.checked })} />Spaltenköpfe (Bestandteil, Menge, Einheit)</label>
          : <Feld label="Spalten">{(p) => <Auswahl {...p} value={b.spalten ?? 1} onChange={(e) => aendere({ spalten: Number(e.target.value) })}>
            {[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}</Auswahl>}</Feld>}
      </> : null}
      {b.typ === "datenfelder" || b.typ === "unterschrift" || b.typ === "kopfkarte" ? (
        <div className="flex flex-col gap-2" role="group" aria-label="Felder">
          <span className="text-sm font-medium">{b.typ === "kopfkarte" ? "Kennzahlen" : "Felder"}</span>
          {eintraege.map((e, i) => (
            <div key={i} {...feldSort.zeile(i)} draggable={false} data-testid="feldzeile"
              className={cx("grid grid-cols-[auto_minmax(0,0.8fr)_minmax(0,1.2fr)_auto_auto] gap-1 items-center rounded-md", feldSort.ueber === i && "outline outline-2 outline-akzent")}>
              {/* nur der Griff zieht, damit Text in den Eingabefeldern markierbar bleibt */}
              <span tabIndex={0} draggable {...feldSort.griff(i, e.label || `Feld ${i + 1}`, `felder-${b.id}`)} className="cursor-grab gedaempft px-0.5"><Icon name="griff" /></span>
              <Eingabe aria-label={`Bezeichnung ${i + 1}`} value={e.label} onChange={(ev) => setzeEintrag(i, { label: ev.target.value })} />
              <FeldWert wert={e.wert} onWert={(w) => setzeEintrag(i, { wert: w })} fokus={fokus} nummer={i + 1} />
              <span className="flex flex-col">
                <button type="button" aria-label={`Feld ${i + 1} nach oben`} disabled={i === 0} onClick={() => aendere({ felder: verschiebe(eintraege, i, i - 1) })}
                  className="h-[15px] w-5 p-0 border-0 bg-transparent text-[11px] leading-none cursor-pointer gedaempft disabled:opacity-30 disabled:cursor-default">▲</button>
                <button type="button" aria-label={`Feld ${i + 1} nach unten`} disabled={i === eintraege.length - 1} onClick={() => aendere({ felder: verschiebe(eintraege, i, i + 1) })}
                  className="h-[15px] w-5 p-0 border-0 bg-transparent text-[11px] leading-none cursor-pointer gedaempft disabled:opacity-30 disabled:cursor-default">▼</button>
              </span>
              <Knopf klein variante="geist" icon="x" aria-label={`Feld ${i + 1} entfernen`} onClick={() => aendere({ felder: eintraege.filter((_, j) => j !== i) })} />
            </div>
          ))}
          <Knopf klein icon="plus" onClick={() => aendere({ felder: [...eintraege, { label: "", wert: "" }] })}>Feld hinzufügen</Knopf>
        </div>
      ) : null}
      {b.typ === "unterschrift" ? <Feld label="Text unter der Linie">{(p) => <Eingabe {...p} value={b.linie ?? ""} onChange={(e) => aendere({ linie: e.target.value })} />}</Feld> : null}
      {b.typ === "tabelle" ? (
        <Feld label="Tabelle">{(p) => <Auswahl {...p} value={b.quelle ?? ""} onChange={(e) => aendere({ quelle: e.target.value })}>
          {aufbau.tabellen.map((t) => <option key={t.quelle} value={t.quelle}>{t.name}</option>)}</Auswahl>}</Feld>
      ) : null}
      {b.typ === "leerraum" ? (
        <Feld label="Höhe (mm)">{(p) => <Eingabe {...p} inputMode="numeric" value={b.hoehe_mm ?? 6} onChange={(e) => aendere({ hoehe_mm: Number(e.target.value) || 1 })} />}</Feld>
      ) : null}

      {textartig ? <>
        <div className="flex flex-col gap-2"><span className="text-sm font-medium">Schrift</span>
          <div className="flex gap-1.5">
            <Auswahl aria-label="Schriftgröße" value={o.schrift ?? "normal"} onChange={(e) => aendereOptionen({ schrift: e.target.value as Optionen["schrift"] })}>
              <option value="klein">Klein</option><option value="normal">Normal</option><option value="gross">Groß</option>
            </Auswahl>
            <Knopf aria-label="Fett" aria-pressed={!!o.fett} className={cx("w-[34px] px-0 justify-center font-bold", o.fett && "bg-akzent-weich")} onClick={() => aendereOptionen({ fett: !o.fett })}>B</Knopf>
            <Knopf aria-label="Kursiv" aria-pressed={!!o.kursiv} className={cx("w-[34px] px-0 justify-center italic", o.kursiv && "bg-akzent-weich")} onClick={() => aendereOptionen({ kursiv: !o.kursiv })}>I</Knopf>
          </div>
        </div>
        {b.typ === "titel" && b.neben_logo
          ? <span className="text-[12.5px] gedaempft">Ausrichtung: steht rechts neben dem Logo.</span>
          : <div className="flex flex-col gap-2"><span className="text-sm font-medium">Ausrichtung</span>
            <Segmente label="Ausrichtung" wert={o.ausrichtung ?? "links"} onWahl={(w) => aendereOptionen({ ausrichtung: w })}
              werte={[{ wert: "links", text: "Links" }, { wert: "mitte", text: "Mitte" }, { wert: "rechts", text: "Rechts" }]} />
          </div>}
      </> : null}
      {textartig && b.typ !== "fusszeile" && b.typ !== "titel" ? <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={!!o.ueberschrift} onChange={(e) => aendereOptionen({ ueberschrift: e.target.checked })} />Bezeichnung als Überschrift drucken</label> : null}
      {["text", "datenfelder", "tabelle"].includes(b.typ) ? <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={!!o.ausblenden_wenn_leer} onChange={(e) => aendereOptionen({ ausblenden_wenn_leer: e.target.checked })} />Ausblenden, wenn leer</label> : null}
      {b.typ !== "fusszeile" && b.typ !== "seitenumbruch" ? <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={!!o.nicht_teilen} onChange={(e) => aendereOptionen({ nicht_teilen: e.target.checked })} />Nicht über Seitenumbruch teilen</label> : null}
      {textartig && b.typ !== "fusszeile" ? <label className="flex items-center gap-2 text-[13.5px]"><input type="checkbox" checked={!!o.linie_oben} onChange={(e) => aendereOptionen({ linie_oben: e.target.checked })} />Linie darüber</label> : null}
      {NEBENEINANDER.includes(b.typ) ? (
        <Feld label="Neben dem vorherigen Block">{(p) => <Auswahl {...p} value={o.neben_vorherigem ?? ""} onChange={(e) => aendereOptionen({ neben_vorherigem: (e.target.value || undefined) as Breite | undefined })}>
          <option value="">nein, darunter</option>
          {(Object.keys(BREITE_TEXT) as Breite[]).map((k) => <option key={k} value={k}>ja, dieser Block {BREITE_TEXT[k]} breit</option>)}</Auswahl>}</Feld>
      ) : null}
    </Karte>
  );
}

function FeldWert({ wert, onWert, fokus, nummer }: { wert: string; onWert: (w: string) => void; fokus: { current: { setze: (f: string) => void } | null }; nummer: number }) {
  const ref = useRef<HTMLInputElement>(null);
  const aktuellerWert = useRef(onWert);
  aktuellerWert.current = onWert;
  return (
    <Eingabe ref={ref} aria-label={`Wert ${nummer}`} value={wert} className="font-mono text-[12.5px]" onChange={(e) => onWert(e.target.value)}
      onFocus={() => {
        fokus.current = {
          setze: (feld) => {
            const aktuell = ref.current?.value ?? wert;
            const pos = ref.current?.selectionStart ?? aktuell.length;
            const ende = ref.current?.selectionEnd ?? pos;
            aktuellerWert.current(`${aktuell.slice(0, pos)}{{${feld}}}${aktuell.slice(ende)}`);
          },
        };
      }} />
  );
}

type Testpatient = { id: number; nachname: string; vorname: string; nummer: number };

function VorschauDialog({ art, bloecke, offen, onOffen }: { art: Art; bloecke: Block[]; offen: boolean; onOffen: (o: boolean) => void }) {
  const patienten = useQuery({
    queryKey: ["patienten", "testpatienten"],
    queryFn: () => api<Seitenliste<Testpatient>>(`patienten/${abfrage({ test: "nur", seitengroesse: 50 })}`),
    enabled: offen,
  });
  const [patient, setPatient] = useState("");
  const [schluessel, setSchluessel] = useState("");
  const stand = useMemo(() => JSON.stringify(bloecke), [bloecke]);
  const pdf = useQuery({
    queryKey: ["vorlagen", art, "vorschau", patient, schluessel],
    queryFn: () => apiDatei(`vorlagen/${art}/vorschau/`, { method: "POST", body: { patient: Number(patient), bloecke: JSON.parse(schluessel) } }),
    enabled: offen && !!patient && !!schluessel,
    gcTime: 0,
  });
  useEffect(() => { if (offen) setSchluessel(stand); }, [offen, stand]);
  useEffect(() => {
    if (!patient && patienten.data?.results[0]) setPatient(String(patienten.data.results[0].id));
  }, [patienten.data, patient]);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Vorschau mit Testpatient" breite={1000}
      beschreibung="Aus dem aktuellen Stand im Editor, auch ungespeichert. Wasserzeichen „ENTWURF“.">
      <div className="flex flex-col gap-3" data-testid="vorlage-vorschau">
        <Feld label="Testpatient">{(p) => (
          <Auswahl {...p} value={patient} onChange={(e) => setPatient(e.target.value)}>
            {(patienten.data?.results ?? []).map((t) => <option key={t.id} value={t.id}>{t.nachname}, {t.vorname} · Nr. {t.nummer}</option>)}
          </Auswahl>
        )}</Feld>
        {patienten.data && !patienten.data.results.length ? <Meldung art="warn">Es gibt keine Testpatienten.</Meldung> : null}
        <Fehleranzeige fehler={pdf.error} />
        {pdf.isFetching ? <Laden text="PDF wird erzeugt …" /> : pdf.data ? (
          <PdfLeser url={`vorschau-${art}-${patient}-${pdf.dataUpdatedAt}`} laden={() => Promise.resolve(pdf.data.daten)} className="h-[64vh]" />
        ) : null}
      </div>
    </Dialog>
  );
}
