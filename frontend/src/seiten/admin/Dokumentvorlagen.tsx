/**
 * Entwurf 18 · Dokumentvorlagen: Infusionsplan, Patientendatenblatt, Schreiben und Vordrucke aus Blöcken (WYSIWYG).
 * Aufbau links, Seite in der Mitte, Eigenschaften des markierten Blocks rechts. Platzhalter nur aus der festen Liste
 * des Servers. Entwurf → Veröffentlichen; jede Version bleibt erhalten, freigegebene Pläne behalten ihr PDF.
 *
 * Vorlagen-Portal einfacher (F180): zuerst die Liste aller Vorlagen mit „Wofür?“, „Wo benutzt?“ und Stand; im Editor
 * der geführte Ablauf „1 Bearbeiten → 2 Vorschau prüfen → 3 Freigeben“, Live-Vorschau mit Testpatient neben den
 * Eigenschaften, Angaben aus der Akte per Klick aus einer lesbaren Liste, frühere Fassung ansehen/wiederherstellen,
 * „Als eigene Vorlage kopieren“. In der Oberfläche heißt eine Version „Fassung“ und Veröffentlichen „Freigeben“.
 */
import { Fragment, createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, api, apiDatei } from "@/lib/api";
import type { Seite as Seitenliste } from "@/lib/api";
import { useBriefkopf } from "@/lib/daten";
import { datum } from "@/lib/format";
import { Logo } from "@/components/layout/logo";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Ladekreis, Meldung, Segmente, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { Begriff } from "@/components/ui/Begriff";
import { Erklaerung } from "@/components/ui/erklaerung";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { useSortierbar, verschiebe } from "@/components/ui/sortierbar";
import { PdfLeser } from "@/components/PdfAnsicht";

type Art = "infusionsplan" | "patientendatenblatt" | "datenschutzinformation" | "einwilligung" | "schweigepflichtentbindung"
  // Schreiben mit E-Mail (Vorlagen von Alice Hessel, 09.10.2026; F172, F173)
  | "patientenaufnahme" | "terminbestaetigung" | "reisebescheinigung" | "patientenankuendigung"
  // eigene Schreiben, unter Vorlagen angelegt (F176)
  | `eigen-${string}`;
const SCHREIBEN_FEST: Art[] = ["patientenaufnahme", "terminbestaetigung", "reisebescheinigung", "patientenankuendigung"];
const istEigen = (art: Art) => art.startsWith("eigen-");
const mitEmailArt = (art: Art) => SCHREIBEN_FEST.includes(art) || istEigen(art);
type Optionen = {
  schrift?: "klein" | "normal" | "gross"; ausrichtung?: "links" | "mitte" | "rechts"; fett?: boolean; kursiv?: boolean;
  ausblenden_wenn_leer?: boolean; nicht_teilen?: boolean; ueberschrift?: boolean; linie_oben?: boolean;
  neben_vorherigem?: Breite; spalten?: 2 | 3;
};
type Breite = "drittel" | "haelfte" | "zwei_drittel";
type Eintrag = { label: string; wert: string };
export type Block = {
  id: string; typ: string; bezeichnung?: string; optionen?: Optionen;
  text?: string; zusatz_label?: string; zusatz?: string; spalten?: number; felder?: Eintrag[]; quelle?: string;
  linie?: string; hoehe_mm?: number; links?: string; rechts?: string; rechts_klein?: boolean;
  absender?: boolean; linienfarbe?: string; falzmarken?: boolean; mit_linie?: boolean;
  untertitel?: string; darstellung?: "paare" | "befund"; spaltenkoepfe?: boolean; neben_logo?: boolean;
  /** Block „E-Mail“ der Schreiben (F172): steht nicht auf der PDF */
  betreff?: string;
};
type Ausrichtung = "hoch" | "quer";
type Version = {
  id: number; version: number | null; status: "entwurf" | "aktiv" | "abgeloest"; notiz: string; erstellt_am: string;
  geaendert_am: string; geaendert_von: string | null; veroeffentlicht_am: string | null; veroeffentlicht_von: string | null;
  /** Seitenformat der Fassung (13.10.2026) und Firma einer eigenen Vorlage (leer = gemeinsam, 11.10.2026) */
  ausrichtung?: Ausrichtung; firma?: string | null;
};
/** Vorlagen je Firma (11.10.2026): nutzt die aktive Firma die gemeinsame Vorlage oder ihre eigene? */
type FirmaInfo = { aktiv: string | null; name: string | null; mehrere: boolean; eigene: boolean; gebunden: boolean; moeglich: boolean };
type Uebersicht = { art: Art; name: string; aktiv: Version; entwurf: Version | null; versionen: Version[];
  firma?: FirmaInfo; ausrichtung?: Ausrichtung; querformat_moeglich?: boolean;
  /** Vordrucke: Wasserzeichen „ENTWURF“ der Startvorlage, manuell abschaltbar (U17) */
  entwurfsmodus?: { moeglich: boolean; aktiv: boolean; aus: boolean };
  /** eigenes Schreiben (F176) */
  eigen?: { beschreibung: string; mit_termin: boolean; aktiv: boolean } | null;
  /** Vorlagen-Portal (F180): Gruppe der Liste, wofür die Vorlage ist und wo sie in der Praxis benutzt wird */
  gruppe?: Gruppe; wofuer?: string; wo?: string };
export type VorlagenUebersicht = Uebersicht;
type Gruppe = "schreiben" | "eigen" | "anforderungen" | "formulare" | "plaene" | "datenschutz";
type Datenfeld = { name: string; beschreibung: string; html: boolean; bezeichnung?: string; gruppe?: string };
type Aufbau = Uebersicht & {
  bausteine: { typ: string; name: string }[];
  felder: Datenfeld[];
  tabellen: { quelle: string; name: string; spalten: string[] }[];
};
type Entwurf = Version & { ist_entwurf: boolean; grundlage?: number; bloecke: Block[] };

const TYPNAME: Record<string, string> = {
  briefkopf: "Briefkopf", titel: "Titel", text: "Text", zweispaltig: "Zwei Spalten", datenfelder: "Datenfelder", tabelle: "Tabelle", trennlinie: "Trennlinie",
  leerraum: "Leerraum", unterschrift: "Unterschrift", seitenumbruch: "Seitenumbruch", fusszeile: "Fußzeile", kopfkarte: "Kopfkarte",
  email: "E-Mail",
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
  email: "Betreff und Text der E-Mail, mit der das Schreiben verschickt wird (die PDF hängt an). Steht nicht auf der PDF; im Dialog vor dem Versand änderbar.",
  fusszeile: "Steht auf jeder Seite unten (bis 8 Zeilen links, rechts z. B. die Seitenzahl). {Seite} und {Seiten} werden zur Seitenzahl.",
};
/** Bausteine aus dem Entwurf; Briefkopf, Titel und Fußzeile gibt es je Vorlage einmal */
const BAUSTEINE = ["text", "zweispaltig", "datenfelder", "tabelle", "kopfkarte", "trennlinie", "leerraum", "unterschrift", "seitenumbruch", "titel", "briefkopf", "fusszeile", "email"];
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
  if (typ === "email") Object.assign(b, { betreff: "Betreff", text: "{{Patient.Briefanrede}},\n\n" });
  return b;
}

/** Lesbare Namen der erlaubten Datenfelder (F180): Platzhalter erscheinen als „Briefanrede“ statt Patient.Briefanrede */
const FeldNamen = createContext<Map<string, Datenfeld> | null>(null);

/** Ein Platzhalter als Chip: lesbarer Name, technischer Name im Tooltip; unbekannte rot (der Server weist sie ab) */
function FeldChip({ name }: { name: string }) {
  const felder = useContext(FeldNamen);
  const f = felder?.get(name);
  if (felder && !f) return <span className="feldchip feldchip-unbekannt" title={`Unbekannte Angabe {{${name}}} – bitte aus der Liste rechts einfügen`}>{name}?</span>;
  return <span className="feldchip" title={f ? `{{${name}}} · ${f.beschreibung}` : undefined}>{f?.bezeichnung ?? name}</span>;
}

/** Text mit Platzhaltern als Chips (wie im Entwurf) */
function MitFeldern({ text }: { text?: string }) {
  const teile: ReactNode[] = [];
  let pos = 0;
  for (const m of (text ?? "").matchAll(PLATZHALTER)) {
    teile.push(text!.slice(pos, m.index));
    teile.push(<FeldChip key={m.index} name={m[1]} />);
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
          <Logo className="w-[9.375rem] h-[3.3125rem]" version={briefkopf.data?.logo.sha256} firma={briefkopf.data?.firma?.kuerzel} name={briefkopf.data?.firma?.name} />
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
      return <div className={cx("text-[1em] leading-relaxed", karte, b.optionen?.linie_oben && "border-t border-[#c9c8d4] pt-1", stil(b.optionen))}>{kopf}<div className={b.optionen?.spalten === 3 ? "columns-3 gap-3" : b.optionen?.spalten === 2 ? "columns-2 gap-4" : undefined}><MitFeldern text={b.text} /></div></div>;
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
                <td className="py-[0.1875rem] pr-2 text-[#666] border-b border-[#eee] align-top" style={{ width: `${36 / n}%` }}>{e.label}</td>
                <td className="py-[0.1875rem] pr-2 border-b border-[#eee] align-top"><MitFeldern text={e.wert} /></td>
              </Fragment>)}</tr>
            ))}
          </tbody></table>
          {b.typ === "unterschrift" ? <div className="mt-6 w-[12.5rem] border-t border-[#1b1932] pt-0.5 text-[0.85em] text-[#5d5b72]">{b.linie || "Unterschrift"}</div> : null}
        </div>
      );
    }
    case "tabelle": {
      const t = tabellen.find((x) => x.quelle === b.quelle);
      return (
        <div className={cx(karte, stil(b.optionen))}>
          {kopf}
          <table className="w-full border-collapse text-[1em]">
            <thead><tr>{(t?.spalten ?? []).map((s, i) => <th key={i} className="text-left font-semibold text-[#666] border-b border-[#ccc] py-[0.1875rem] pr-2">{s}</th>)}</tr></thead>
            <tbody><tr><td colSpan={t?.spalten.length ?? 1} className="py-[0.1875rem] text-[#888] italic">{t?.name ?? "unbekannte Tabelle"}</td></tr></tbody>
          </table>
        </div>
      );
    }
    case "trennlinie":
      return <hr className="border-0 border-t border-[#ccc] m-0" />;
    case "leerraum":
      return <div style={{ height: (b.hoehe_mm ?? 6) * 2.1 }} className="bg-[repeating-linear-gradient(45deg,transparent,transparent_4px,#f2f1f6_4px,#f2f1f6_8px)]" />;
    case "email":
      return (
        <div className="border border-dashed border-[#9a98b3] rounded-md px-2 py-1.5 text-[0.95em] bg-[#f7f7fb]">
          <div className="text-[0.85em] text-[#5d5b72] mb-0.5">E-Mail (nicht auf der PDF)</div>
          <div className="font-semibold"><MitFeldern text={b.betreff} /></div>
          <div className="line-clamp-6"><MitFeldern text={b.text} /></div>
        </div>
      );
    case "seitenumbruch":
      return <div className="text-center text-[0.9em] text-[#888] border-t border-dashed border-[#bbb] pt-0.5">Seitenumbruch</div>;
    default:
      return null;
  }
}

const GRUPPEN: { gruppe: Gruppe; titel: string; leer?: string }[] = [
  { gruppe: "schreiben", titel: "Briefe und E-Mails an Patienten" },
  { gruppe: "eigen", titel: "Eigene Vorlagen",
    leer: "Noch keine eigenen Vorlagen. „+ Neue Vorlage“ legt z. B. ein Schreiben an Hausärzte an; „Als eigene Vorlage kopieren“ im Editor nimmt ein bestehendes Schreiben als Grundlage." },
  // mitgelieferte Vorlagen der Regeneration Clinic (13.10.2026), nur in der Firma RGC sichtbar
  { gruppe: "anforderungen", titel: "Anforderungen: Labor, Bildgebung, Funktionsdiagnostik" },
  { gruppe: "formulare", titel: "Aufklärungen, Erklärungen und Abrechnung" },
  { gruppe: "plaene", titel: "Pläne, Berichte und Unterlagen" },
  { gruppe: "datenschutz", titel: "Vordrucke zum Datenschutz" },
];

/** Gemeinsame oder eigene Vorlage der aktiven Firma (nur mit mehreren Firmen) */
function FirmaChip({ f }: { f?: FirmaInfo }) {
  if (!f || !f.mehrere) return null;
  if (f.gebunden) return <Chip art="neutral" title="Diese Vorlage gehört fest zu dieser Firma">nur {f.name}</Chip>;
  return f.eigene ? <Chip art="akzent" title={`Eigene Vorlage der ${f.name}; die anderen Firmen nutzen die gemeinsame`}>eigene Vorlage {f.name}</Chip>
    : <Chip art="neutral" title="Gilt in allen Firmen, solange keine eigene Vorlage angelegt ist">gemeinsam</Chip>;
}

/** Stand einer Vorlage in Alltagssprache (Liste und Kopf des Editors) */
export function vorlageStatus(u: Uebersicht): { text: string; art: "ok" | "warn" | "neutral" } {
  if (u.eigen && !u.eigen.aktiv) return { text: "deaktiviert", art: "neutral" };
  if (u.entwurf) return { text: "Änderungen noch nicht freigegeben", art: "warn" };
  if (u.entwurfsmodus?.aktiv) return { text: "Mustertext, noch nicht geprüft", art: "warn" };
  return { text: `in Gebrauch · Fassung ${u.aktiv.version}`, art: "ok" };
}

/** Schreiben, die sich als eigene Vorlage kopieren lassen (die Ankündigung hat eigene Datenfelder, F173) */
const kopierbar = (art: Art) => mitEmailArt(art) && art !== "patientenankuendigung";

/** Bereich „Dokumentvorlagen“ der Seite Vorlagen (wie Briefkopf, Auswahllisten, Grenzwerte). Ohne ``?art=`` die Liste
 *  aller Vorlagen, mit ``?art=…`` der Editor; die Knöpfe stehen oben rechts im Seitenkopf, wo die anderen Bereiche
 *  „Speichern“ haben. */
export function DokumentvorlagenBereich({ aktionenZiel, onGeaendert }: {
  aktionenZiel: HTMLElement | null; onGeaendert: (geaendert: boolean) => void;
}) {
  const [parameter, setParameter] = useSearchParams();
  const art = parameter.get("art") as Art | null;
  const waehle = (a: Art | null) => setParameter(a ? { art: a } : {});
  if (!art) return <VorlagenListe onWahl={waehle} />;
  return <EditorFuerArt key={art} art={art} onArt={waehle} aktionenZiel={aktionenZiel} onGeaendert={onGeaendert} />;
}

function VorlagenListe({ onWahl }: { onWahl: (a: Art) => void }) {
  const liste = useQuery({ queryKey: ["vorlagen", "liste"], queryFn: () => api<Uebersicht[]>("vorlagen/") });
  const [neu, setNeu] = useState(false);
  const [filter, setFilter] = useState("");
  const s = filter.trim().toLocaleLowerCase("de");
  const passend = (liste.data ?? []).filter((v) => !s || `${v.name} ${v.wofuer ?? ""}`.toLocaleLowerCase("de").includes(s));
  return (
    <div className="stapel flex flex-col gap-5" data-testid="vorlagenliste">
      <div className="flex items-center gap-3 flex-wrap">
        <Eingabe type="search" aria-label="Vorlage suchen" placeholder="Vorlage suchen …" value={filter}
          onChange={(e) => setFilter(e.target.value)} className="w-[18rem] max-w-full" />
        <Knopf icon="plus" onClick={() => setNeu(true)}>Neue Vorlage</Knopf>
        <span className="text-[0.8125rem] gedaempft">Vorlage anklicken, um Text und Aussehen zu ändern. Geändert wird erst, was Sie freigeben.</span>
      </div>
      <Fehleranzeige fehler={liste.error} />
      {liste.isLoading ? <Laden /> : null}
      {GRUPPEN.map((g) => {
        const eintraege = passend.filter((v) => (v.gruppe ?? "plaene") === g.gruppe);
        if (!eintraege.length && (s || !g.leer)) return null;
        return (
          <section key={g.gruppe} aria-label={g.titel} className="flex flex-col gap-2.5">
            <h2 className="lbl m-0">{g.titel}</h2>
            {eintraege.length ? (
              <ul className="m-0 p-0 list-none grid gap-3 grid-cols-1 md:grid-cols-2 2xl:grid-cols-3">
                {eintraege.map((v) => {
                  const st = vorlageStatus(v);
                  return (
                    <li key={v.art} className="flex min-w-0">
                      <button type="button" onClick={() => onWahl(v.art)} data-testid="vorlage-karte"
                        className="card flex-1 min-w-0 flex flex-col gap-1.5 px-4 py-3 text-left cursor-pointer border border-transparent hover:border-akzent bg-flaeche text-tinte font-[inherit]">
                        <span className="flex flex-wrap items-start justify-between gap-2 w-full">
                          <span className="font-semibold text-[0.9375rem] leading-snug min-w-0 [overflow-wrap:anywhere]">{v.name}</span>
                          <span className="flex gap-1.5 shrink-0"><FirmaChip f={v.firma} /><Chip art={st.art}>{st.text}</Chip></span>
                        </span>
                        {v.wofuer ? <span className="text-[0.8438rem] leading-normal">{v.wofuer}</span> : null}
                        {v.wo ? <span className="text-[0.7812rem] gedaempft leading-normal"><strong className="font-medium text-text2">Wo benutzt:</strong> {v.wo}</span> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : <span className="text-[0.8125rem] gedaempft">{g.leer}</span>}
          </section>
        );
      })}
      {s && !passend.length ? <span className="text-sm gedaempft">Keine Vorlage enthält „{filter.trim()}“.</span> : null}
      <EigeneVorlageDialog offen={neu} onOffen={setNeu} onAngelegt={onWahl} />
    </div>
  );
}

type Ansicht = "seite" | "vorschau";

function EditorFuerArt({ art, onArt, aktionenZiel, onGeaendert }: {
  art: Art; onArt: (a: Art | null) => void; aktionenZiel: HTMLElement | null; onGeaendert: (geaendert: boolean) => void;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const aufbau = useQuery({ queryKey: ["vorlagen", art], queryFn: () => api<Aufbau>(`vorlagen/${art}/`) });
  const entwurf = useQuery({ queryKey: ["vorlagen", art, "entwurf"], queryFn: () => api<Entwurf>(`vorlagen/${art}/entwurf/`) });
  const [bloecke, setBloecke] = useState<Block[] | null>(null);
  const [geladen, setGeladen] = useState("");
  const [auswahl, setAuswahl] = useState<string | null>(null);
  const [ansicht, setAnsicht] = useState<Ansicht>("seite");
  // Stand, der zuletzt in der Vorschau mit Testpatient zu sehen war (Schritt 2 „geprüft“)
  const [geprueft, setGeprueft] = useState("");
  const [freigabeFrage, setFreigabeFrage] = useState(false);
  const [verwerfen, setVerwerfen] = useState(false);
  const [modusFrage, setModusFrage] = useState(false);
  const [fassung, setFassung] = useState<number | null>(null);
  const [wiederherstellen, setWiederherstellen] = useState<number | null>(null);
  // eigene Schreiben (F176) und Kopie als eigene Vorlage (F180)
  const [eigenAendern, setEigenAendern] = useState(false);
  const [kopieren, setKopieren] = useState(false);
  // Seitenformat des Entwurfs (13.10.2026) – wird mit den Blöcken gespeichert
  const [ausrichtung, setAusrichtung] = useState<Ausrichtung | null>(null);
  // eigene Vorlage der aktiven Firma anlegen bzw. ablegen (11.10.2026)
  const [firmaFrage, setFirmaFrage] = useState<"anlegen" | "entfernen" | null>(null);
  const firmaM = useMutation({
    mutationFn: (eigene: boolean) => api<Uebersicht>(`vorlagen/${art}/firma/`, { body: { eigene } }),
    onSuccess: (u) => {
      setFirmaFrage(null);
      setBloecke(null);
      setAusrichtung(null);
      void qc.invalidateQueries({ queryKey: ["vorlagen"] });
      melden(u.firma?.eigene ? `Eigene Vorlage für ${u.firma.name} angelegt – Änderungen hier gelten nur dort.`
        : `Eigene Vorlage abgelegt. ${u.firma?.name ?? "Die Firma"} nutzt wieder die gemeinsame Vorlage (Fassung ${u.aktiv.version}).`);
    },
  });
  // Entwurfsmodus der Vordrucke manuell aus- bzw. wieder einschalten (Festlegung 03.10.2026, U17)
  const modus = useMutation({
    mutationFn: (aus: boolean) => api<Uebersicht>(`vorlagen/${art}/entwurfsmodus/`, { body: { aus } }),
    onSuccess: (u) => {
      void qc.invalidateQueries({ queryKey: ["vorlagen", art], exact: true });
      void qc.invalidateQueries({ queryKey: ["vorlagen"] });
      setModusFrage(false);
      melden(u.entwurfsmodus?.aus ? "Entwurfsmodus ausgeschaltet: Die PDFs tragen kein Wasserzeichen „ENTWURF“ mehr." : "Entwurfsmodus wieder eingeschaltet.");
    },
  });
  const fokus = useRef<{ setze: (feld: string) => void } | null>(null);
  const waehleBlock = (id: string | null) => {
    // das Einfügen gilt dem ersten Textfeld des neuen Blocks, bis in ein anderes geklickt wird (FeldText meldet sich an)
    if (id !== auswahl) fokus.current = null;
    setAuswahl(id);
  };

  useEffect(() => {
    if (entwurf.data && bloecke === null) {
      setBloecke(structuredClone(entwurf.data.bloecke));
      setAusrichtung(entwurf.data.ausrichtung ?? "hoch");
      setGeladen(JSON.stringify({ bloecke: entwurf.data.bloecke, ausrichtung: entwurf.data.ausrichtung ?? "hoch" }));
      setAuswahl(entwurf.data.bloecke[0]?.id ?? null);
    }
  }, [entwurf.data, bloecke]);

  const neuLaden = (b: Block[], a?: Ausrichtung) => {
    setBloecke(structuredClone(b));
    const neu = a ?? ausrichtung ?? "hoch";
    setAusrichtung(neu);
    setGeladen(JSON.stringify({ bloecke: b, ausrichtung: neu }));
  };
  const geaendert = bloecke !== null && JSON.stringify({ bloecke, ausrichtung: ausrichtung ?? "hoch" }) !== geladen;
  useEffect(() => { onGeaendert(geaendert); }, [geaendert, onGeaendert]);
  useEffect(() => () => onGeaendert(false), [onGeaendert]);
  const felderNach = useMemo(() => new Map((aufbau.data?.felder ?? []).map((f) => [f.name, f])), [aufbau.data]);

  const speichern = useMutation({
    mutationFn: () => api<Entwurf>(`vorlagen/${art}/entwurf/`, { method: "PUT", body: { bloecke, ausrichtung } }),
    onSuccess: (e) => {
      neuLaden(e.bloecke, e.ausrichtung);
      qc.setQueryData(["vorlagen", art, "entwurf"], e);
      void qc.invalidateQueries({ queryKey: ["vorlagen", art], exact: true });
      void qc.invalidateQueries({ queryKey: ["vorlagen", "liste"] });
      melden(`Gespeichert. In der Praxis gilt weiter Fassung ${aufbau.data?.aktiv.version} – zum Übernehmen „Freigeben“.`);
    },
  });
  const freigeben = useMutation({
    mutationFn: async () => {
      if (geaendert || !entwurf.data?.ist_entwurf) await api(`vorlagen/${art}/entwurf/`, { method: "PUT", body: { bloecke, ausrichtung } });
      return api<Uebersicht>(`vorlagen/${art}/veroeffentlichen/`, { method: "POST" });
    },
    onSuccess: (u) => {
      setFreigabeFrage(false);
      setBloecke(null);
      setAnsicht("seite");
      void qc.invalidateQueries({ queryKey: ["vorlagen"] });
      melden(`Fassung ${u.aktiv.version} freigegeben. Sie gilt ab sofort für neue PDFs und E-Mails.`);
    },
  });
  const verwerfenM = useMutation({
    mutationFn: () => api(`vorlagen/${art}/entwurf/`, { method: "DELETE" }),
    onSuccess: () => {
      setVerwerfen(false);
      setBloecke(null);
      void qc.invalidateQueries({ queryKey: ["vorlagen"] });
      melden(`Änderungen verworfen. Fassung ${aufbau.data?.aktiv.version} bleibt in Gebrauch.`);
    },
  });
  const wiederherstellenM = useMutation({
    mutationFn: (v: number) => api<Entwurf>(`vorlagen/${art}/versionen/${v}/wiederherstellen/`, { method: "POST" }),
    onSuccess: (e, v) => {
      setWiederherstellen(null);
      setFassung(null);
      neuLaden(e.bloecke, e.ausrichtung);
      setAuswahl(e.bloecke[0]?.id ?? null);
      qc.setQueryData(["vorlagen", art, "entwurf"], e);
      void qc.invalidateQueries({ queryKey: ["vorlagen", art], exact: true });
      void qc.invalidateQueries({ queryKey: ["vorlagen", "liste"] });
      melden(`Fassung ${v} wiederhergestellt und gespeichert. Bitte in der Vorschau prüfen und freigeben.`);
    },
  });
  const startvorlage = useMutation({
    mutationFn: () => api<{ bloecke: Block[] }>(`vorlagen/${art}/startvorlage/`),
    onSuccess: (v) => { setBloecke(structuredClone(v.bloecke)); setAuswahl(v.bloecke[0]?.id ?? null); melden("Mitgelieferte Startvorlage als Grundlage geladen – noch nicht gespeichert."); },
  });

  const sort = useSortierbar(bloecke ?? [], (neu) => setBloecke(neu));
  if (aufbau.error || entwurf.error) {
    return (
      <div className="flex flex-col gap-3 items-start">
        <Fehleranzeige fehler={aufbau.error ?? entwurf.error} />
        <Knopf icon="zurueck" onClick={() => onArt(null)}>Alle Vorlagen</Knopf>
      </div>
    );
  }
  if (!aufbau.data || !entwurf.data || !bloecke) return <Laden />;
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
  const entferne = (id: string) => { const neu = bloecke.filter((b) => b.id !== id); setBloecke(neu); waehleBlock(neu[0]?.id ?? null); };
  const hinzufuegen = (typ: string) => {
    const b = neuerBlock(typ, bloecke, a.tabellen);
    const nach = typ === "briefkopf" ? 0 : typ === "fusszeile" || typ === "email" ? bloecke.length : index >= 0 ? index + 1 : bloecke.length;
    const neu = [...bloecke];
    neu.splice(nach, 0, b);
    setBloecke(neu);
    waehleBlock(b.id);
  };
  const einfuegen = (name: string) => {
    if (fokus.current) fokus.current.setze(name);
    else melden(gewaehlt ? "Dieser Abschnitt hat kein Textfeld. Bitte einen Abschnitt mit Text markieren (z. B. „Text“)." : "Bitte zuerst einen Abschnitt markieren.");
  };
  // Blöcke mit „neben dem vorherigen“ in eine Zeile setzen, wie im PDF
  const gruppen: number[][] = [];
  bloecke.forEach((b, i) => {
    if (b.optionen?.neben_vorherigem && gruppen.length) gruppen[gruppen.length - 1].push(i);
    else gruppen.push([i]);
  });
  const rahmen = (b: Block, i: number) => (
    <div key={b.id} role="button" tabIndex={0} aria-label={`Block ${b.bezeichnung || TYPNAME[b.typ]}`}
      onClick={() => waehleBlock(b.id)} onKeyDown={(e) => { if (e.key === "Enter") waehleBlock(b.id); }}
      className={cx("relative px-2 py-1.5 rounded cursor-pointer", b.id === auswahl ? "outline outline-2 outline-[#251F53]" : "hover:outline hover:outline-1 hover:outline-[#c9c8d4]")}>
      {b.id === auswahl ? <>
        <span className="absolute -top-2.5 left-1.5 text-[0.625rem] bg-[#251F53] text-white px-1.5 rounded-sm">{b.bezeichnung || TYPNAME[b.typ]}</span>
        <span className="absolute -top-3 right-1 flex gap-0.5">
          <button type="button" aria-label="nach oben" title="nach oben" disabled={i === 0} onClick={(e) => { e.stopPropagation(); verschiebe(i, i - 1); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[0.6875rem] p-0 cursor-pointer">↑</button>
          <button type="button" aria-label="nach unten" title="nach unten" disabled={i === bloecke.length - 1} onClick={(e) => { e.stopPropagation(); verschiebe(i, i + 1); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[0.6875rem] p-0 cursor-pointer">↓</button>
          <button type="button" aria-label="entfernen" title="Abschnitt entfernen" onClick={(e) => { e.stopPropagation(); entferne(b.id); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[0.6875rem] p-0 cursor-pointer">×</button>
        </span>
      </> : null}
      <div style={{ fontSize: SCHRIFT_PX[b.optionen?.schrift ?? "normal"] }}><BlockAnsicht b={b} tabellen={a.tabellen} /></div>
    </div>
  );
  const einmal = (typ: string) => ["briefkopf", "fusszeile", "email"].includes(typ) && bloecke.some((b) => b.typ === typ);
  const serverFehler = [speichern.error, freigeben.error, wiederherstellenM.error].find((e) => e instanceof ApiFehler) as ApiFehler | undefined;
  const fehlerListe = serverFehler ? (Array.isArray((serverFehler.daten as { bloecke?: string[] })?.bloecke)
    ? (serverFehler.daten as { bloecke: string[] }).bloecke : [serverFehler.message]) : [];
  const freigebbar = geaendert || entwurf.data.ist_entwurf;
  const stand = JSON.stringify({ bloecke, ausrichtung });
  const naechste = Math.max(0, ...a.versionen.map((v) => v.version ?? 0)) + 1;
  const verInfo = geaendert ? "Ungespeicherte Änderungen"
    : entwurf.data.ist_entwurf ? "Gespeichert, noch nicht freigegeben"
    : `Fassung ${a.aktiv.version} ist in Gebrauch`;
  const schritt = ansicht === "vorschau" ? 2 : 1;
  const schrittKnopf = (nr: number, titel: string, unter: string, onClick: () => void, opt: { aktiv?: boolean; fertig?: boolean; aus?: boolean; titelHinweis?: string } = {}) => (
    <li className="flex-1 min-w-[12rem]">
      <button type="button" onClick={onClick} disabled={opt.aus} aria-current={opt.aktiv ? "step" : undefined} title={opt.titelHinweis}
        className={cx("w-full h-full flex items-center gap-2.5 px-3 py-2 rounded-lg border text-left cursor-pointer font-[inherit] disabled:cursor-not-allowed disabled:opacity-60",
          opt.aktiv ? "border-akzent bg-akzent-weich text-akzent-text" : "border-rand bg-flaeche text-tinte hover:border-akzent")}>
        <span className={cx("w-6 h-6 rounded-full inline-flex items-center justify-center text-[0.8125rem] font-semibold shrink-0",
          opt.fertig ? "bg-ok text-white" : opt.aktiv ? "bg-akzent text-auf-akzent" : "bg-fein text-text2")}>{opt.fertig ? <Icon name="haken" /> : nr}</span>
        <span className="flex flex-col min-w-0">
          <span className="font-medium text-[0.875rem]">{titel}</span>
          <span className="text-[0.75rem] gedaempft leading-snug">{unter}</span>
        </span>
      </button>
    </li>
  );

  return (
    <FeldNamen.Provider value={felderNach}>
    <div className="stapel flex flex-col gap-5" data-testid="dokumentvorlagen">
      {aktionenZiel ? createPortal(<>
        {(() => {
          const standText = <span className={cx("text-[0.8125rem]", geaendert ? "text-warn font-medium" : "gedaempft")} data-testid="vorlage-stand">{verInfo}</span>;
          return geaendert ? standText : <Begriff name={entwurf.data.ist_entwurf ? "entwurf" : "fassung"}>{standText}</Begriff>;
        })()}
        <Knopf laedt={speichern.isPending} disabled={!geaendert} onClick={() => speichern.mutate()}
          title="Speichert die Änderungen, ohne sie freizugeben – in der Praxis gilt weiter die bisherige Fassung.">Speichern</Knopf>
        <Knopf variante="pri" icon="haken" onClick={() => setFreigabeFrage(true)} disabled={!freigebbar}
          title={freigebbar ? "Änderungen für die Praxis übernehmen" : "Keine Änderungen zum Freigeben"}>Freigeben</Knopf>
      </>, aktionenZiel) : null}

      <div className="flex flex-col gap-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex flex-col gap-1 min-w-0 max-w-[52rem]">
            <button type="button" onClick={() => onArt(null)}
              className="self-start inline-flex items-center gap-1 bg-transparent border-0 p-0 cursor-pointer text-[0.8125rem] text-akzent-text font-[inherit]">
              <Icon name="zurueck" /> Alle Vorlagen</button>
            <h2 className="m-0 text-[1.125rem] font-semibold flex items-center gap-2 flex-wrap" data-testid="vorlage-name">
              {a.name} <Chip art={vorlageStatus(a).art}>{vorlageStatus(a).text}</Chip><FirmaChip f={a.firma} /></h2>
            {a.wofuer ? <span className="text-sm">{a.wofuer}</span> : null}
            {a.wo ? <span className="text-[0.8125rem] gedaempft"><strong className="font-medium text-text2">Wo benutzt:</strong> {a.wo}</span> : null}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {a.eigen ? <Knopf klein icon="stift" onClick={() => setEigenAendern(true)}>Name und Einstellungen</Knopf> : null}
            {kopierbar(art) ? <Knopf klein icon="kopieren" onClick={() => setKopieren(true)}>Als eigene Vorlage kopieren</Knopf> : null}
            {a.firma?.moeglich ? (a.firma.eigene
              ? <Knopf klein onClick={() => { firmaM.reset(); setFirmaFrage("entfernen"); }} data-testid="firma-entfernen">Eigene Vorlage entfernen</Knopf>
              : <Knopf klein onClick={() => { firmaM.reset(); setFirmaFrage("anlegen"); }} data-testid="firma-anlegen">Eigene Vorlage für {a.firma.name} anlegen</Knopf>) : null}
          </div>
        </div>
        {a.firma?.mehrere && !a.firma.gebunden ? (
          <span className="text-[0.8125rem] gedaempft" data-testid="firma-hinweis">
            {a.firma.eigene
              ? `Sie bearbeiten die eigene Vorlage der ${a.firma.name}. Die anderen Firmen nutzen weiter die gemeinsame Vorlage.`
              : `Diese Vorlage ist gemeinsam: Was Sie hier ändern und freigeben, gilt in allen Firmen. Soll nur die ${a.firma.name} etwas anderes bekommen, legen Sie eine eigene Vorlage an (Kopie der gemeinsamen).`}
          </span>
        ) : null}
        <ol className="m-0 p-0 list-none flex gap-2 flex-wrap" aria-label="So ändern Sie eine Vorlage" data-testid="schritte">
          {schrittKnopf(1, "1 · Bearbeiten", "Text und Aufbau ändern, dann „Speichern“", () => setAnsicht("seite"), { aktiv: schritt === 1 })}
          {schrittKnopf(2, "2 · Vorschau prüfen", "So sieht es mit einem Testpatienten aus", () => setAnsicht("vorschau"),
            { aktiv: schritt === 2, fertig: geprueft === stand && freigebbar })}
          {schrittKnopf(3, "3 · Freigeben", `Ab dann gilt es für alle neuen PDFs (Fassung ${naechste})`, () => setFreigabeFrage(true),
            { aus: !freigebbar, titelHinweis: freigebbar ? undefined : "Noch keine Änderungen – erst bearbeiten" })}
        </ol>
      </div>

      {a.eigen ? <EigeneVorlageDialog offen={eigenAendern} onOffen={setEigenAendern} vorlage={a} /> : null}
      <EigeneVorlageDialog offen={kopieren} onOffen={setKopieren} kopieVon={a} onAngelegt={(neu) => onArt(neu)} />
      {art !== "infusionsplan" && art !== "patientendatenblatt" && !mitEmailArt(art) && !a.aktiv.veroeffentlicht_von && a.entwurfsmodus?.moeglich ? (
        a.entwurfsmodus?.aus ? (
          <Meldung><span className="flex items-start justify-between gap-3 flex-wrap" data-testid="entwurfsmodus-aus">
            <span>Entwurfsmodus ausgeschaltet: Die PDFs dieser mitgelieferten Vorlage tragen kein Wasserzeichen „ENTWURF“ und keinen
              Hinweisblock mehr. Stellen in [eckigen Klammern] bleiben stehen, bis die Vorlage bearbeitet und freigegeben ist.</span>
            <Knopf klein laedt={modus.isPending} onClick={() => modus.mutate(false)}>Entwurfsmodus wieder einschalten</Knopf></span></Meldung>
        ) : (
          <Meldung art="warn"><span className="flex items-start justify-between gap-3 flex-wrap">
            <span data-testid="vorlage-ungeprueft">Diese Vorlage ist der mitgelieferte <Begriff name="entwurf">Entwurf</Begriff>: Stellen in [eckigen Klammern]
              sind von der Stiftung auszufüllen, der Text ist rechtlich zu prüfen. Bis sie hier bearbeitet und freigegeben ist,
              tragen die PDFs in den Akten das Wasserzeichen „ENTWURF“.</span>
            <Knopf klein onClick={() => { modus.reset(); setModusFrage(true); }}>Entwurfsmodus ausschalten</Knopf></span></Meldung>
        )
      ) : null}
      <Dialog offen={modusFrage} onOffen={setModusFrage} titel="Entwurfsmodus ausschalten" breite={540}
        beschreibung="Die PDFs dieses Vordrucks werden ohne Wasserzeichen „ENTWURF“ und ohne den Hinweisblock für die Bearbeiter erzeugt – mit dem Text der mitgelieferten Vorlage."
        fuss={<><Knopf onClick={() => setModusFrage(false)}>Abbrechen</Knopf>
          <Knopf variante="dng" laedt={modus.isPending} onClick={() => modus.mutate(true)}>Ausschalten</Knopf></>}>
        <div className="flex flex-col gap-3">
          <Meldung art="warn">Der Text ist nicht rechtlich geprüft, und Stellen in [eckigen Klammern] bleiben stehen. Bitte nur ausschalten,
            wenn die Stiftung den Vordruck so verwenden will. Die Änderung steht im Audit-Log; jederzeit wieder einschaltbar.</Meldung>
          <Fehleranzeige fehler={modus.error} />
        </div>
      </Dialog>
      <Dialog offen={firmaFrage === "anlegen"} onOffen={(o) => { if (!o) setFirmaFrage(null); }} titel={`Eigene Vorlage für ${a.firma?.name ?? ""} anlegen`} breite={540}
        beschreibung={`Kopie der gemeinsamen Vorlage (Fassung ${a.aktiv.version}), sofort in Gebrauch – nur in der ${a.firma?.name ?? "Firma"}. Die anderen Firmen nutzen weiter die gemeinsame Vorlage.`}
        fuss={<><Knopf onClick={() => setFirmaFrage(null)}>Abbrechen</Knopf>
          <Knopf variante="pri" laedt={firmaM.isPending} onClick={() => firmaM.mutate(true)}>Eigene Vorlage anlegen</Knopf></>}>
        <div className="flex flex-col gap-3">
          {geaendert || entwurf.data.ist_entwurf ? <Meldung art="warn">Nicht freigegebene Änderungen an der gemeinsamen Vorlage bleiben dort; die Kopie startet mit der freigegebenen Fassung.</Meldung> : null}
          <Fehleranzeige fehler={firmaM.error} />
        </div>
      </Dialog>
      <Dialog offen={firmaFrage === "entfernen"} onOffen={(o) => { if (!o) setFirmaFrage(null); }} titel="Eigene Vorlage entfernen" breite={540}
        beschreibung={`Die ${a.firma?.name ?? "Firma"} nutzt danach wieder die gemeinsame Vorlage. Die eigenen Fassungen bleiben abgelöst erhalten; ein nicht freigegebener Entwurf wird verworfen.`}
        fuss={<><Knopf onClick={() => setFirmaFrage(null)}>Abbrechen</Knopf>
          <Knopf variante="dng" laedt={firmaM.isPending} onClick={() => firmaM.mutate(false)}>Entfernen</Knopf></>}>
        <Fehleranzeige fehler={firmaM.error} />
      </Dialog>
      {fehlerListe.length ? <Meldung art="fehler"><ul className="m-0 pl-4" data-testid="vorlage-fehler">{fehlerListe.map((f) => <li key={f}>{f}</li>)}</ul></Meldung> : null}

      <div className="stapel grid grid-cols-1 xl:grid-cols-[13.75rem_minmax(0,1fr)_20rem] gap-5 items-start">
        <aside className="flex flex-col gap-3.5 min-w-0">
          <Karte className="p-2.5 flex flex-col gap-0.5" data-testid="aufbau">
            <span className="lbl px-1.5 pb-1.5 pt-1 flex items-center gap-1.5">Aufbau
              <Erklaerung titel="Aufbau der Vorlage">Die Vorlage besteht aus Abschnitten von oben nach unten (Briefkopf, Text, Tabelle …).
                Einen Abschnitt anklicken, um ihn rechts zu ändern. Reihenfolge per Ziehen am Griff oder mit ↑ ↓ am markierten Abschnitt.</Erklaerung></span>
            {bloecke.map((b, i) => (
              <div key={b.id} {...sort.zeile(i)} className={cx("flex items-center rounded-md", sort.ueber === i && "outline outline-2 outline-akzent")}>
                <button type="button" aria-current={b.id === auswahl ? "true" : undefined} onClick={() => waehleBlock(b.id)}
                  className={cx("flex-1 min-w-0 flex justify-between items-center gap-2 px-2.5 py-[0.4375rem] border-0 rounded-md text-[0.8438rem] text-left cursor-pointer",
                    b.id === auswahl ? "bg-akzent-weich text-akzent-text font-medium" : "bg-transparent hover:bg-fein")}>
                  <span className="truncate">{b.bezeichnung || TYPNAME[b.typ]}</span>
                  <span className="text-[0.7188rem] gedaempft shrink-0">{TYPNAME[b.typ]}</span>
                </button>
                <span tabIndex={0} {...sort.griff(i, b.bezeichnung || TYPNAME[b.typ], `vorlage-${art}`)} className="px-1 cursor-grab gedaempft"><Icon name="griff" /></span>
              </div>
            ))}
          </Karte>
          <Karte className="p-3 flex flex-col gap-2" data-testid="bausteine">
            <span className="lbl">Abschnitt hinzufügen</span>
            <div className="flex flex-wrap gap-1.5">
              {BAUSTEINE.filter((t) => a.bausteine.some((x) => x.typ === t)).map((t) => (
                <button key={t} type="button" disabled={einmal(t)} onClick={() => hinzufuegen(t)} title={HINWEIS[t]}
                  className="px-2.5 py-1.5 border border-dashed border-rand rounded-lg bg-flaeche text-[0.8125rem] cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
                  + {TYPNAME[t]}
                </button>
              ))}
            </div>
            <span className="text-xs gedaempft leading-normal">Der neue Abschnitt kommt hinter den markierten.</span>
          </Karte>
          <Karte className="p-3.5 flex flex-col gap-1.5" data-testid="versionen">
            <span className="lbl flex items-center gap-1.5">Frühere <Begriff name="fassung">Fassungen</Begriff>
              <Erklaerung titel="Fassungen">Bei jedem Freigeben entsteht eine neue Fassung; die alten bleiben erhalten. „Ansehen“ zeigt eine
                Fassung mit Testpatient, „Wiederherstellen“ übernimmt sie als Grundlage – in Gebrauch ist sie erst nach dem Freigeben.
                Jede PDF vermerkt, mit welcher Fassung sie erzeugt wurde.</Erklaerung></span>
            <ul className="m-0 p-0 list-none flex flex-col gap-1.5 text-[0.8125rem]">
              {a.entwurf ? <li className="text-warn"><strong className="font-medium"><Begriff name="entwurf">Noch nicht freigegeben</Begriff></strong> · {datum(a.entwurf.geaendert_am)}{a.entwurf.geaendert_von ? ` · ${a.entwurf.geaendert_von}` : ""}{a.entwurf.notiz ? ` · ${a.entwurf.notiz}` : ""}</li> : null}
              {a.versionen.map((v) => (
                <li key={v.id} className="flex flex-col gap-0.5" data-testid="fassung">
                  <span><strong className="font-medium">Fassung {v.version}</strong> · {v.status === "aktiv" ? `in Gebrauch seit ${datum(v.veroeffentlicht_am)}` : datum(v.veroeffentlicht_am)}
                    {v.veroeffentlicht_von ? ` · ${v.veroeffentlicht_von}` : ""}{v.notiz ? <span className="gedaempft"> · {v.notiz}</span> : null}</span>
                  <span className="flex gap-3">
                    <button type="button" className="text-xs underline bg-transparent border-0 cursor-pointer text-akzent-text p-0"
                      onClick={() => setFassung(v.version!)} aria-label={`Fassung ${v.version} ansehen`}>ansehen</button>
                    {v.status !== "aktiv" || a.entwurf ? (
                      <button type="button" className="text-xs underline bg-transparent border-0 cursor-pointer text-akzent-text p-0"
                        onClick={() => { wiederherstellenM.reset(); setWiederherstellen(v.version!); }} aria-label={`Fassung ${v.version} wiederherstellen`}>wiederherstellen</button>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
            <button type="button" className="self-start text-xs underline bg-transparent border-0 cursor-pointer text-akzent-text p-0 mt-1"
              onClick={() => startvorlage.mutate()} title="Aufbau, wie er mit EPM ausgeliefert wird, in den Editor laden">Mitgelieferte Startvorlage laden</button>
          </Karte>
        </aside>

        <div className="flex flex-col gap-2.5 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <Segmente label="Ansicht" wert={ansicht} onWahl={setAnsicht} className="self-start"
              werte={[{ wert: "seite", text: "Seite bearbeiten" }, { wert: "vorschau", text: "Vorschau mit Testpatient" }]} />
            {a.querformat_moeglich ? (
              <Segmente label="Seitenformat" wert={ausrichtung ?? "hoch"} onWahl={(w) => setAusrichtung(w)} className="self-start"
                werte={[{ wert: "hoch", text: "Hochformat" }, { wert: "quer", text: "Querformat" }]} />
            ) : null}
          </div>
          {ansicht === "seite" ? (
            <div className="py-6 bg-[#E6E5EE] rounded-xl overflow-auto min-w-0" data-testid="vorlage-seite">
              <div className={cx("mx-auto px-[2.375rem] py-[2.125rem] bg-white text-[#1a1a1a] shadow-md flex flex-col gap-2.5",
                ausrichtung === "quer" ? "w-[49.5rem] min-h-[35rem]" : "w-[35rem] min-h-[49.5rem]")}>
                {gruppen.map((g) => g.length === 1 ? rahmen(bloecke[g[0]], g[0]) : (
                  <div key={`paar-${bloecke[g[0]].id}`} className="flex justify-between items-start" data-testid="nebeneinander">
                    {g.map((i, j) => <div key={bloecke[i].id} style={{ width: `${breitenFuer(g.map((x) => bloecke[x]))[j]}%` }}>{rahmen(bloecke[i], i)}</div>)}
                  </div>
                ))}
              </div>
            </div>
          ) : <LiveVorschau art={art} bloecke={bloecke} ausrichtung={ausrichtung ?? "hoch"} onGeprueft={setGeprueft} />}
        </div>

        <aside className="flex flex-col gap-3.5 min-w-0">
          {gewaehlt ? <BlockEigenschaften key={gewaehlt.id} b={gewaehlt} aufbau={a} aendere={aendere} aendereOptionen={aendereOptionen} fokus={fokus} />
            : <Karte className="p-4 text-sm gedaempft">Abschnitt im Aufbau oder auf der Seite anklicken.</Karte>}
          <Feldeinfueger felder={a.felder} onWahl={einfuegen} />
          <div className="flex gap-2 p-3 rounded-lg bg-fein text-[0.7812rem] leading-normal text-text2">
            <Icon name="info" /><span>Änderungen gelten erst nach „Freigeben“. Schon erzeugte PDFs und freigegebene Pläne bleiben unverändert.</span>
          </div>
          {entwurf.data.ist_entwurf ? <Knopf variante="geist" onClick={() => setVerwerfen(true)}>Nicht freigegebene Änderungen verwerfen</Knopf> : null}
        </aside>
      </div>

      <Dialog offen={freigabeFrage} onOffen={setFreigabeFrage} titel={`${a.name}: Änderungen freigeben`} breite={540}
        beschreibung={`Wird Fassung ${naechste} und gilt ab sofort für alle neuen PDFs${mitEmailArt(art) ? " und E-Mails" : ""}. Fassung ${a.aktiv.version} bleibt erhalten und lässt sich wiederherstellen.`}
        fuss={<><Knopf onClick={() => setFreigabeFrage(false)}>Abbrechen</Knopf><Knopf variante="pri" laedt={freigeben.isPending} onClick={() => freigeben.mutate()}>Freigeben</Knopf></>}>
        <div className="flex flex-col gap-3">
          {geprueft !== stand ? (
            <Meldung art="warn"><span className="flex items-start justify-between gap-3 flex-wrap" data-testid="freigabe-ungeprueft">
              <span>Diesen Stand haben Sie noch nicht in der Vorschau mit Testpatient angesehen.</span>
              <Knopf klein onClick={() => { setFreigabeFrage(false); setAnsicht("vorschau"); }}>Erst Vorschau ansehen</Knopf></span></Meldung>
          ) : <Meldung art="ok">In der Vorschau geprüft.</Meldung>}
          <span className="text-sm">Bereits erzeugte PDFs und freigegebene Pläne behalten ihr Aussehen.</span>
          <Fehleranzeige fehler={freigeben.error} />
        </div>
      </Dialog>
      <Dialog offen={verwerfen} onOffen={setVerwerfen} titel="Nicht freigegebene Änderungen verwerfen" breite={480}
        beschreibung={`Fassung ${a.aktiv.version} bleibt unverändert in Gebrauch.`}
        fuss={<><Knopf onClick={() => setVerwerfen(false)}>Abbrechen</Knopf><Knopf variante="dng" laedt={verwerfenM.isPending} onClick={() => verwerfenM.mutate()}>Verwerfen</Knopf></>}>
        <Fehleranzeige fehler={verwerfenM.error} />
      </Dialog>
      <Dialog offen={wiederherstellen !== null} onOffen={(o) => { if (!o) setWiederherstellen(null); }} titel={`Fassung ${wiederherstellen} wiederherstellen`} breite={520}
        beschreibung="Die Fassung wird als Grundlage übernommen und gespeichert. In Gebrauch ist sie erst, wenn Sie sie danach freigeben."
        fuss={<><Knopf onClick={() => setWiederherstellen(null)}>Abbrechen</Knopf>
          <Knopf variante="pri" laedt={wiederherstellenM.isPending} onClick={() => wiederherstellenM.mutate(wiederherstellen!)}>Wiederherstellen</Knopf></>}>
        <div className="flex flex-col gap-3">
          {geaendert || entwurf.data.ist_entwurf ? <Meldung art="warn">Ihre noch nicht freigegebenen Änderungen werden dabei ersetzt.</Meldung> : null}
          <Fehleranzeige fehler={wiederherstellenM.error} />
        </div>
      </Dialog>
      <FassungDialog art={art} version={fassung} onZu={() => setFassung(null)}
        onWiederherstellen={a.versionen.find((v) => v.version === fassung)?.status === "aktiv" && !a.entwurf ? undefined
          : (v) => { wiederherstellenM.reset(); setWiederherstellen(v); }} />
    </div>
    </FeldNamen.Provider>
  );
}

/** Angaben aus der Akte per Klick einfügen (F180): verständliche Namen nach Gruppen, mit Suche; der Platzhalter
 *  ({{Patient.Briefanrede}}) steht nur im Tooltip und in der Bezeichnung des Knopfs für Tastatur und Vorlesen. */
function Feldeinfueger({ felder, onWahl }: { felder: Datenfeld[]; onWahl: (name: string) => void }) {
  const [suche, setSuche] = useState("");
  const s = suche.trim().toLocaleLowerCase("de");
  const passend = felder.filter((f) => !s || `${f.bezeichnung ?? ""} ${f.beschreibung} ${f.name}`.toLocaleLowerCase("de").includes(s));
  const gruppen: [string, Datenfeld[]][] = [];
  for (const f of passend) {
    const g = f.gruppe ?? "Angaben";
    const vorhanden = gruppen.find(([n]) => n === g);
    if (vorhanden) vorhanden[1].push(f);
    else gruppen.push([g, [f]]);
  }
  return (
    <Karte className="p-4 flex flex-col gap-2.5" data-testid="datenfelder">
      <span className="lbl flex items-center gap-1.5">Angabe aus der Akte einfügen
        <Erklaerung titel="Angaben aus der Akte">Erst in ein Textfeld des Abschnitts klicken, dann hier eine Angabe wählen. Sie erscheint im Text
          als <span className="feldchip">Briefanrede</span> und wird beim Erstellen durch die Daten des Patienten ersetzt, z. B.
          „Sehr geehrte Frau Muster“. Nur diese Angaben sind möglich – Tippfehler sind damit ausgeschlossen.</Erklaerung></span>
      {felder.length > 12 ? (
        <Eingabe type="search" aria-label="Angabe suchen" placeholder="Angabe suchen, z. B. Anrede, Termin …" value={suche}
          onChange={(e) => setSuche(e.target.value)} />
      ) : null}
      <div className="flex flex-col gap-2.5 max-h-[26rem] overflow-y-auto pr-1">
        {gruppen.map(([gruppe, liste]) => (
          <div key={gruppe} className="flex flex-col gap-1" role="group" aria-label={gruppe}>
            <span className="text-[0.75rem] font-medium gedaempft">{gruppe}</span>
            <div className="flex flex-wrap gap-1">
              {liste.map((f) => (
                <button key={f.name} type="button" title={`{{${f.name}}} · ${f.beschreibung}`} aria-label={`${f.bezeichnung ?? f.name} einfügen`}
                  onMouseDown={(e) => e.preventDefault()} onClick={() => onWahl(f.name)}
                  className="px-2 py-1 rounded-md bg-fein border border-transparent text-[0.7812rem] text-text2 cursor-pointer hover:bg-akzent-weich hover:border-akzent max-w-full text-left [overflow-wrap:anywhere]">
                  + {f.bezeichnung ?? f.name}</button>
              ))}
            </div>
          </div>
        ))}
        {!passend.length ? <span className="text-[0.8125rem] gedaempft">Keine Angabe passt zu „{suche.trim()}“.</span> : null}
      </div>
    </Karte>
  );
}

type Fokus = { current: { setze: (f: string) => void } | null };

/** Einsetzen an der Schreibmarke; war das Feld noch nie fokussiert, am Ende (F180: ohne vorher hineinzuklicken) */
function useEinsetzen(ref: { current: HTMLInputElement | HTMLTextAreaElement | null }, wert: string, onWert: (w: string) => void, fokus: Fokus) {
  const aktuellerWert = useRef(onWert);
  aktuellerWert.current = onWert;
  const benutzt = useRef(false);
  const ziel = useRef({
    setze: (feld: string) => {
      // aktuellen Inhalt aus dem Feld lesen, nicht den Stand beim Fokussieren
      const el = ref.current;
      const aktuell = el?.value ?? wert;
      const pos = benutzt.current ? el?.selectionStart ?? aktuell.length : aktuell.length;
      const ende = benutzt.current ? el?.selectionEnd ?? pos : pos;
      const einfuegen = `{{${feld}}}`;
      aktuellerWert.current(aktuell.slice(0, pos) + einfuegen + aktuell.slice(ende));
      requestAnimationFrame(() => { benutzt.current = true; el?.focus(); el?.setSelectionRange(pos + einfuegen.length, pos + einfuegen.length); });
    },
  });
  // abmelden, wenn das Feld verschwindet
  useEffect(() => () => { if (fokus.current === ziel.current) fokus.current = null; }, [fokus]);
  return {
    anmelden: () => { fokus.current = ziel.current; },
    onFocus: () => { benutzt.current = true; fokus.current = ziel.current; },
  };
}

/** Die Angaben im Text als lesbare Chips („Briefanrede“ statt {{Patient.Briefanrede}}) */
function AngabenImText({ text }: { text: string }) {
  const namen = [...new Set([...text.matchAll(PLATZHALTER)].map((m) => m[1]))];
  if (!namen.length) return null;
  return (
    <span className="flex flex-wrap items-center gap-1 text-[0.75rem] gedaempft" data-testid="angaben-im-text">
      Angaben: {namen.map((n) => <FeldChip key={n} name={n} />)}
    </span>
  );
}

/** Textfeld, in das „Angabe aus der Akte einfügen“ an der Schreibmarke einsetzt. Das erste Textfeld eines Blocks
 *  meldet sich gleich an, damit ein Klick auf eine Angabe auch ohne vorheriges Hineinklicken etwas einfügt. */
function FeldText({ label, wert, onWert, fokus, mehrzeilig }: {
  label: string; wert: string; onWert: (w: string) => void; fokus: Fokus; mehrzeilig?: boolean;
}) {
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null);
  const einsetzen = useEinsetzen(ref, wert, onWert, fokus);
  useEffect(() => { if (!fokus.current) einsetzen.anmelden(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="flex flex-col gap-1">
      <Feld label={label}>
        {(p) => mehrzeilig
          ? <Textfeld {...p} ref={ref} rows={5} value={wert} onFocus={einsetzen.onFocus} onChange={(e) => onWert(e.target.value)} className="text-[0.8438rem] leading-normal" />
          : <Eingabe {...p} ref={ref} value={wert} onFocus={einsetzen.onFocus} onChange={(e) => onWert(e.target.value)} className="text-[0.8438rem]" />}
      </Feld>
      <AngabenImText text={wert} />
    </div>
  );
}

function BlockEigenschaften({ b, aufbau, aendere, aendereOptionen, fokus }: {
  b: Block; aufbau: Aufbau; aendere: (n: Partial<Block>) => void; aendereOptionen: (n: Partial<Optionen>) => void;
  fokus: Fokus;
}) {
  const o = b.optionen ?? {};
  const eintraege = b.felder ?? [];
  const setzeEintrag = (i: number, neu: Partial<Eintrag>) => aendere({ felder: eintraege.map((e, j) => (j === i ? { ...e, ...neu } : e)) });
  // Reihenfolge der Felder: Ziehen am Griff, Pfeiltasten am Griff oder ▲ ▼
  const feldSort = useSortierbar(eintraege, (neu) => aendere({ felder: neu }));
  const textartig = !["briefkopf", "trennlinie", "leerraum", "seitenumbruch", "email"].includes(b.typ);
  return (
    <Karte className="p-4 flex flex-col gap-3" data-testid="block-eigenschaften">
      <div className="flex justify-between items-center"><span className="lbl">Abschnitt</span><Chip art="akzent">{TYPNAME[b.typ]}</Chip></div>
      <Feld label="Bezeichnung">{(p) => <Eingabe {...p} value={b.bezeichnung ?? ""} onChange={(e) => aendere({ bezeichnung: e.target.value })} />}</Feld>
      <span className="text-[0.7812rem] gedaempft leading-normal">{HINWEIS[b.typ]}</span>

      {b.typ === "titel" ? <>
        <FeldText label="Text" wert={b.text ?? ""} onWert={(w) => aendere({ text: w })} fokus={fokus} />
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-2">
          <Feld label="Zusatz">{(p) => <Eingabe {...p} value={b.zusatz_label ?? ""} onChange={(e) => aendere({ zusatz_label: e.target.value })} />}</Feld>
          <FeldText label="Wert" wert={b.zusatz ?? ""} onWert={(w) => aendere({ zusatz: w })} fokus={fokus} />
        </div>
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!b.neben_logo} onChange={(e) => aendere({ neben_logo: e.target.checked })} />Rechts neben dem Logo</label>
      </> : null}
      {b.typ === "text" || b.typ === "fusszeile" ? <FeldText label="Text" wert={b.text ?? ""} onWert={(w) => aendere({ text: w })} fokus={fokus} mehrzeilig /> : null}
      {b.typ === "email" ? <>
        <FeldText label="Betreff" wert={b.betreff ?? ""} onWert={(w) => aendere({ betreff: w })} fokus={fokus} />
        <FeldText label="Text" wert={b.text ?? ""} onWert={(w) => aendere({ text: w })} fokus={fokus} mehrzeilig />
      </> : null}
      {b.typ === "fusszeile" ? <FeldText label="Rechts" wert={b.rechts ?? ""} onWert={(w) => aendere({ rechts: w })} fokus={fokus} /> : null}
      {b.typ === "zweispaltig" ? <>
        <FeldText label="Links" wert={b.links ?? ""} onWert={(w) => aendere({ links: w })} fokus={fokus} mehrzeilig />
        <FeldText label="Rechts" wert={b.rechts ?? ""} onWert={(w) => aendere({ rechts: w })} fokus={fokus} mehrzeilig />
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!b.rechts_klein} onChange={(e) => aendere({ rechts_klein: e.target.checked })} />Rechte Spalte kleiner</label>
      </> : null}
      {b.typ === "briefkopf" ? <>
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={b.absender !== false} onChange={(e) => aendere({ absender: e.target.checked })} />Absender neben dem Logo</label>
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!b.falzmarken} onChange={(e) => aendere({ falzmarken: e.target.checked })} />Falzmarken am linken Rand</label>
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={b.mit_linie !== false} onChange={(e) => aendere({ mit_linie: e.target.checked })} />Linie unter dem Logo</label>
        {b.mit_linie !== false ? <label className="flex items-center gap-2 text-[0.8438rem]">Linienfarbe
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
          ? <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!b.spaltenkoepfe} onChange={(e) => aendere({ spaltenkoepfe: e.target.checked })} />Spaltenköpfe (Bestandteil, Menge, Einheit)</label>
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
                  className="h-[0.9375rem] w-5 p-0 border-0 bg-transparent text-[0.6875rem] leading-none cursor-pointer gedaempft disabled:opacity-30 disabled:cursor-default">▲</button>
                <button type="button" aria-label={`Feld ${i + 1} nach unten`} disabled={i === eintraege.length - 1} onClick={() => aendere({ felder: verschiebe(eintraege, i, i + 1) })}
                  className="h-[0.9375rem] w-5 p-0 border-0 bg-transparent text-[0.6875rem] leading-none cursor-pointer gedaempft disabled:opacity-30 disabled:cursor-default">▼</button>
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
            <Knopf aria-label="Fett" aria-pressed={!!o.fett} className={cx("w-[2.125rem] px-0 justify-center font-bold", o.fett && "bg-akzent-weich")} onClick={() => aendereOptionen({ fett: !o.fett })}>B</Knopf>
            <Knopf aria-label="Kursiv" aria-pressed={!!o.kursiv} className={cx("w-[2.125rem] px-0 justify-center italic", o.kursiv && "bg-akzent-weich")} onClick={() => aendereOptionen({ kursiv: !o.kursiv })}>I</Knopf>
          </div>
        </div>
        {b.typ === "titel" && b.neben_logo
          ? <span className="text-[0.7812rem] gedaempft">Ausrichtung: steht rechts neben dem Logo.</span>
          : <div className="flex flex-col gap-2"><span className="text-sm font-medium">Ausrichtung</span>
            <Segmente label="Ausrichtung" wert={o.ausrichtung ?? "links"} onWahl={(w) => aendereOptionen({ ausrichtung: w })}
              werte={[{ wert: "links", text: "Links" }, { wert: "mitte", text: "Mitte" }, { wert: "rechts", text: "Rechts" }]} />
          </div>}
      </> : null}
      {textartig && b.typ !== "fusszeile" && b.typ !== "titel" ? <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!o.ueberschrift} onChange={(e) => aendereOptionen({ ueberschrift: e.target.checked })} />Bezeichnung als Überschrift drucken</label> : null}
      {["text", "datenfelder", "tabelle"].includes(b.typ) ? <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!o.ausblenden_wenn_leer} onChange={(e) => aendereOptionen({ ausblenden_wenn_leer: e.target.checked })} />Ausblenden, wenn leer</label> : null}
      {!["fusszeile", "seitenumbruch", "email"].includes(b.typ) ? <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!o.nicht_teilen} onChange={(e) => aendereOptionen({ nicht_teilen: e.target.checked })} />Nicht über Seitenumbruch teilen</label> : null}
      {textartig && b.typ !== "fusszeile" ? <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!o.linie_oben} onChange={(e) => aendereOptionen({ linie_oben: e.target.checked })} />Linie darüber</label> : null}
      {b.typ === "text" ? (
        <Segmente label="Spalten" wert={String(o.spalten ?? 1)} onWahl={(w) => aendereOptionen({ spalten: w === "1" ? undefined : Number(w) as 2 | 3 })}
          werte={[{ wert: "1", text: "1" }, { wert: "2", text: "2" }, { wert: "3", text: "3" }]} />
      ) : null}
      {NEBENEINANDER.includes(b.typ) ? (
        <Feld label="Neben dem vorherigen Block">{(p) => <Auswahl {...p} value={o.neben_vorherigem ?? ""} onChange={(e) => aendereOptionen({ neben_vorherigem: (e.target.value || undefined) as Breite | undefined })}>
          <option value="">nein, darunter</option>
          {(Object.keys(BREITE_TEXT) as Breite[]).map((k) => <option key={k} value={k}>ja, dieser Block {BREITE_TEXT[k]} breit</option>)}</Auswahl>}</Feld>
      ) : null}
    </Karte>
  );
}

function FeldWert({ wert, onWert, fokus, nummer }: { wert: string; onWert: (w: string) => void; fokus: Fokus; nummer: number }) {
  const ref = useRef<HTMLInputElement>(null);
  const einsetzen = useEinsetzen(ref, wert, onWert, fokus);
  return (
    <Eingabe ref={ref} aria-label={`Wert ${nummer}`} value={wert} className="font-mono text-[0.7812rem]" onChange={(e) => onWert(e.target.value)}
      onFocus={einsetzen.onFocus} title={wert.includes("{{") ? wert : undefined} />
  );
}

/** Eigenes Schreiben anlegen (ohne ``vorlage``) oder Name, Beschreibung, Termin und aktiv ändern (F176); mit
 *  ``kopieVon`` als Kopie einer bestehenden Vorlage anlegen (F180). */
function EigeneVorlageDialog({ offen, onOffen, vorlage, kopieVon, onAngelegt }: {
  offen: boolean; onOffen: (o: boolean) => void; vorlage?: Uebersicht; kopieVon?: Uebersicht; onAngelegt?: (art: Art) => void;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [name, setName] = useState("");
  const [beschreibung, setBeschreibung] = useState("");
  const [mitTermin, setMitTermin] = useState(false);
  const [aktiv, setAktiv] = useState(true);
  const [gesetzt, setGesetzt] = useState(false);
  if (offen && !gesetzt) {
    setGesetzt(true);
    setName(vorlage?.name ?? (kopieVon ? `${kopieVon.name} (Kopie)` : ""));
    setBeschreibung(vorlage?.eigen?.beschreibung ?? (kopieVon?.eigen?.beschreibung ?? ""));
    setMitTermin(!!(vorlage?.eigen?.mit_termin ?? kopieVon?.eigen?.mit_termin ?? kopieVon?.art === "terminbestaetigung"));
    setAktiv(vorlage?.eigen?.aktiv ?? true);
  }
  if (!offen && gesetzt) setGesetzt(false);
  const speichern = useMutation({
    mutationFn: () => {
      const body = { name: name.trim(), beschreibung: beschreibung.trim(), mit_termin: mitTermin, ...(vorlage ? { aktiv } : {}) };
      return vorlage ? api<Uebersicht>(`vorlagen/${vorlage.art}/eigen/`, { method: "PATCH", body })
        : kopieVon ? api<Uebersicht>(`vorlagen/${kopieVon.art}/duplizieren/`, { body })
        : api<Uebersicht>("vorlagen/", { body });
    },
    onSuccess: (u) => {
      void qc.invalidateQueries({ queryKey: ["vorlagen"] });
      void qc.invalidateQueries({ queryKey: ["schreiben"] });
      melden(vorlage ? "Gespeichert." : `„${u.name}“ angelegt und in der Akte wählbar – jetzt Text anpassen, in der Vorschau prüfen und freigeben.`);
      onOffen(false);
      onAngelegt?.(u.art);
    },
  });
  const f = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={vorlage ? `„${vorlage.name}“ ändern` : kopieVon ? `„${kopieVon.name}“ als eigene Vorlage kopieren` : "Neue Vorlage (eigenes Schreiben)"}
      beschreibung={vorlage ? undefined : kopieVon
        ? `Die neue Vorlage startet mit Text und Aufbau der Fassung ${kopieVon.aktiv.version} von „${kopieVon.name}“ und steht in der Akte unter „Schreiben und E-Mail“ › „Eigene Vorlagen“. Das Original bleibt unverändert.${kopieVon.art === "reisebescheinigung" ? " Das ADAC-Attest hängt nur an der Reisebescheinigung selbst an." : ""}`
        : "Startet mit einem Brief an den Patienten (Briefkopf, Anrede, Text, Gruß) und einem E-Mail-Text. Danach wie jede Vorlage bearbeiten und freigeben."}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!name.trim()} onClick={() => speichern.mutate()}>
          {vorlage ? "Speichern" : kopieVon ? "Kopie anlegen" : "Anlegen"}</Knopf>
      </>}>
      <div className="flex flex-col gap-3">
        <Feld label="Name" fehler={f.name} pflicht>
          {(p) => <Eingabe {...p} value={name} maxLength={100} placeholder="z. B. Bitte um Laborwerte an den Hausarzt"
            onChange={(e) => setName(e.target.value)} />}
        </Feld>
        <Feld label="Beschreibung" fehler={f.beschreibung} hinweis="erscheint in der Akte bei der Auswahl des Schreibens">
          {(p) => <Eingabe {...p} value={beschreibung} maxLength={300} onChange={(e) => setBeschreibung(e.target.value)} />}
        </Feld>
        <label className="flex items-center gap-2 text-[0.8438rem]">
          <input type="checkbox" checked={mitTermin} onChange={(e) => setMitTermin(e.target.checked)} />
          Beim Erzeugen einen Termin wählen (Datenfelder Termin.Datum, Termin.Uhrzeit …)
        </label>
        {vorlage ? (
          <label className="flex items-center gap-2 text-[0.8438rem]">
            <input type="checkbox" checked={aktiv} onChange={(e) => setAktiv(e.target.checked)} />
            Aktiv (in der Akte wählbar)
          </label>
        ) : null}
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      </div>
    </Dialog>
  );
}

type Testpatient = { id: number; nachname: string; vorname: string; nummer: number };

/** Vorschau mit Testpatient als echte PDF (F180: neben dem Editor statt im Dialog). Folgt dem Stand im Editor – auch
 *  ungespeichert – kurz nach jeder Änderung; ``onGeprueft`` meldet, welcher Stand zu sehen war. */
function LiveVorschau({ art, bloecke, ausrichtung, onGeprueft, hoehe = "h-[72vh]" }: {
  art: Art; bloecke: Block[]; ausrichtung?: Ausrichtung; onGeprueft?: (stand: string) => void; hoehe?: string;
}) {
  const patienten = useQuery({
    queryKey: ["patienten", "testpatienten"],
    queryFn: () => api<Seitenliste<Testpatient>>(`patienten/${abfrage({ test: "nur", seitengroesse: 50 })}`),
  });
  const [patient, setPatient] = useState("");
  const stand = useMemo(() => JSON.stringify({ bloecke, ausrichtung }), [bloecke, ausrichtung]);
  const [schluessel, setSchluessel] = useState(stand);
  useEffect(() => {
    if (stand === schluessel) return;
    const t = window.setTimeout(() => setSchluessel(stand), 700);
    return () => window.clearTimeout(t);
  }, [stand, schluessel]);
  useEffect(() => {
    if (!patient && patienten.data?.results[0]) setPatient(String(patienten.data.results[0].id));
  }, [patienten.data, patient]);
  const pdf = useQuery({
    queryKey: ["vorlagen", art, "vorschau", patient, schluessel],
    queryFn: () => apiDatei(`vorlagen/${art}/vorschau/`, { method: "POST", body: { patient: Number(patient), ...JSON.parse(schluessel) } }),
    enabled: !!patient, gcTime: 0, retry: false, placeholderData: keepPreviousData,
  });
  const mitEmail = mitEmailArt(art) && bloecke.some((b) => b.typ === "email");
  const mail = useQuery({
    queryKey: ["vorlagen", art, "vorschau-mail", patient, schluessel],
    queryFn: () => api<{ betreff: string; text: string }>(`vorlagen/${art}/vorschau/`, { body: { patient: Number(patient),
      ...JSON.parse(schluessel), ausgabe: "email" } }),
    enabled: mitEmail && !!patient, gcTime: 0, retry: false, placeholderData: keepPreviousData,
  });
  const aktuell = !!pdf.data && !pdf.isPlaceholderData && !pdf.isFetching && schluessel === stand;
  useEffect(() => { if (aktuell) onGeprueft?.(schluessel); }, [aktuell, schluessel, onGeprueft]);
  return (
    <div className="flex flex-col gap-2.5 min-w-0" data-testid="vorlage-vorschau">
      <div className="flex items-end gap-3 flex-wrap">
        <Feld label="Testpatient" className="min-w-[16rem]">{(p) => (
          <Auswahl {...p} value={patient} onChange={(e) => setPatient(e.target.value)}>
            {(patienten.data?.results ?? []).map((t) => <option key={t.id} value={t.id}>{t.nachname}, {t.vorname} · Nr. {t.nummer}</option>)}
          </Auswahl>
        )}</Feld>
        <span className="text-[0.75rem] gedaempft pb-2 flex items-center gap-1.5" data-testid="vorschau-stand">
          {pdf.isFetching || schluessel !== stand ? <><Ladekreis groesse={12} /> wird aktualisiert …</>
            : aktuell ? "Zeigt den aktuellen Stand – auch ungespeicherte Änderungen. Wasserzeichen „ENTWURF“." : null}
        </span>
      </div>
      {patienten.data && !patienten.data.results.length ? <Meldung art="warn">Es gibt keine Testpatienten. Eine Vorschau braucht eine
        Akte, die als Testpatient markiert ist – echte Akten erscheinen hier nie.</Meldung> : null}
      <Fehleranzeige fehler={pdf.error} />
      {pdf.data ? (
        <PdfLeser url={`vorschau-${art}-${patient}-${pdf.dataUpdatedAt}`} laden={() => Promise.resolve(pdf.data.daten)} className={hoehe} />
      ) : pdf.isFetching ? <Laden text="PDF wird erzeugt …" /> : null}
      {mail.data ? (
        <div className="border border-rand rounded-lg px-3 py-2 text-[0.8438rem] bg-flaeche" data-testid="vorschau-email">
          <div className="lbl mb-1">E-Mail (wird beim Versand vorgeschlagen)</div>
          <div className="font-semibold mb-1">{mail.data.betreff}</div>
          <div className="whitespace-pre-wrap">{mail.data.text}</div>
        </div>
      ) : null}
    </div>
  );
}

/** Frühere Fassung ansehen (F180): PDF mit Testpatient, auf Wunsch wiederherstellen */
function FassungDialog({ art, version, onZu, onWiederherstellen }: {
  art: Art; version: number | null; onZu: () => void; onWiederherstellen?: (v: number) => void;
}) {
  const v = useQuery({
    queryKey: ["vorlagen", art, "versionen", version],
    queryFn: () => api<Entwurf>(`vorlagen/${art}/versionen/${version}/`),
    enabled: version !== null,
  });
  return (
    <Dialog offen={version !== null} onOffen={(o) => { if (!o) onZu(); }} titel={`Fassung ${version ?? ""} ansehen`} breite={1000}
      beschreibung={v.data ? `${v.data.status === "aktiv" ? "In Gebrauch" : "Freigegeben"} am ${datum(v.data.veroeffentlicht_am)}${v.data.veroeffentlicht_von ? ` von ${v.data.veroeffentlicht_von}` : ""}${v.data.notiz ? ` · ${v.data.notiz}` : ""}.` : undefined}
      fuss={<><Knopf onClick={onZu}>Schließen</Knopf>
        {onWiederherstellen && version !== null ? <Knopf variante="pri" onClick={() => onWiederherstellen(version)}>Diese Fassung wiederherstellen</Knopf> : null}</>}>
      <Fehleranzeige fehler={v.error} />
      {v.data ? <LiveVorschau art={art} bloecke={v.data.bloecke} ausrichtung={v.data.ausrichtung} hoehe="h-[60vh]" /> : <Laden />}
    </Dialog>
  );
}
