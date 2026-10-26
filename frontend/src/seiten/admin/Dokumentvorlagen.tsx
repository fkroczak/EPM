/**
 * Entwurf 18 · Dokumentvorlagen: Infusionsplan, Patientendatenblatt, Schreiben und Vordrucke aus Blöcken (WYSIWYG).
 * Aufbau links, Seite in der Mitte, Eigenschaften des markierten Blocks rechts. Platzhalter nur aus der festen Liste
 * des Servers. Entwurf → Veröffentlichen; jede Version bleibt erhalten, freigegebene Pläne behalten ihr PDF.
 *
 * Vorlagen-Portal einfacher (F180): zuerst die Liste aller Vorlagen mit „Wofür?“, „Wo benutzt?“ und Stand; im Editor
 * der geführte Ablauf „1 Bearbeiten → 2 Vorschau prüfen → 3 Freigeben“, Live-Vorschau mit Testpatient neben den
 * Eigenschaften, Angaben aus der Akte per Klick aus einer lesbaren Liste, frühere Fassung ansehen/wiederherstellen,
 * „Als eigene Vorlage kopieren“. In der Oberfläche heißt eine Version „Fassung“ und Veröffentlichen „Freigeben“.
 *
 * Freie Gestaltung am Raster (14.10.2026): Blöcke mit der Maus auf der Seite verschieben und an 6 Spalten einrasten,
 * am Rand breiter oder schmaler ziehen, Bausteine aus der Leiste auf die Seite ziehen, Text per Doppelklick direkt auf
 * der Seite schreiben; Kopfband in Farbe und Form (eckig, schräg, wellig, Bogen) mit Fußband; Anschriftfeld nach
 * DIN 5008 für den Fensterumschlag per Schalter (vorlagenRaster.ts).
 */
import { Fragment, createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { createPortal } from "react-dom";
import type { CSSProperties, ComponentType, PointerEvent as ReactPointerEvent, ReactNode } from "react";
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
import {
  BAND_ABSTAND, BANDFARBEN, DIN, DIN_BREITE, DIN_HOEHE, DIN_INFO_BREITE, DIN_INFO_LINKS, DIN_LINKS, FORMEN, MM, RAND_LINKS,
  RAND_OBEN, SPALTE, SPALTEN, bandPfad, freierPlatz, imRaster, insRaster, ordne, rasterBreite, rasterLinks, schwung, setze,
  setzeRaster, vonBis, ziehRand, zeilen,
} from "./vorlagenRaster";
import type { Bandform, Ziel } from "./vorlagenRaster";
import type { AngabenZiel, Beschriftung, TextMitAngabenProps } from "@/components/TextMitAngaben";

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
  /** „raster“: in der Zeile des vorherigen Blocks; Drittel/Hälfte/zwei Drittel nur noch in älteren Vorlagen */
  neben_vorherigem?: "drittel" | "haelfte" | "zwei_drittel" | "raster"; spalten?: 2 | 3;
  /** 6-Spalten-Raster: von Spalte … bis Spalte (ohne Angabe die ganze Breite) */
  raster_von?: number; raster_bis?: number;
};
type Eintrag = { label: string; wert: string };
export type Block = {
  id: string; typ: string; bezeichnung?: string; optionen?: Optionen;
  text?: string; zusatz_label?: string; zusatz?: string; spalten?: number; felder?: Eintrag[]; quelle?: string;
  linie?: string; hoehe_mm?: number; links?: string; rechts?: string; rechts_klein?: boolean;
  absender?: boolean; linienfarbe?: string; falzmarken?: boolean; mit_linie?: boolean;
  /** Briefpapier einer Firma 1:1 (14.10.2026): „rgc“ = Bänder oben und unten wie auf dem Briefpapier der Klinik */
  briefpapier?: string;
  untertitel?: string; darstellung?: "paare" | "befund"; spaltenkoepfe?: boolean; neben_logo?: boolean;
  /** Block „E-Mail“ der Schreiben (F172): steht nicht auf der PDF */
  betreff?: string;
  /** Kopfband des Briefkopfs (14.10.2026) */
  kopfband?: Bandform | ""; bandfarbe?: string; textfarbe?: string; bandhoehe_mm?: number; band_seiten?: "alle" | "erste";
  logo_rechts?: boolean; fussband?: boolean;
  /** Fußzeile mit eigenem Band (14.10.2026); Farben in bandfarbe/textfarbe */
  band?: Bandform | "";
  /** Anschriftfeld nach DIN 5008: Form A/B, Rücksendeangabe (Anschrift in text, Informationsblock in rechts) */
  form?: "A" | "B"; ruecksendung?: string;
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
  /** vor dem Import der Altdaten ersetzt Freigeben die Fassung 1 (14.10.2026) */
  nur_fassung_1?: boolean; naechste_fassung?: number;
  /** Vordrucke: Wasserzeichen „ENTWURF“ der Startvorlage, manuell abschaltbar (U17) */
  entwurfsmodus?: { moeglich: boolean; aktiv: boolean; aus: boolean };
  /** eigenes Schreiben (F176) */
  eigen?: { beschreibung: string; mit_termin: boolean; aktiv: boolean } | null;
  /** Vorlagen-Portal (F180): Gruppe der Liste, wofür die Vorlage ist und wo sie in der Praxis benutzt wird */
  gruppe?: Gruppe; wofuer?: string; wo?: string };
export type VorlagenUebersicht = Uebersicht;
type Gruppe = "schreiben" | "eigen" | "anforderungen" | "formulare" | "fall" | "plaene" | "datenschutz";
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
  email: "E-Mail", anschriftfeld: "Anschriftfeld (DIN 5008)",
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
  anschriftfeld: "Für den Fensterumschlag: Rücksendeangabe und Anschrift links, Informationsblock rechts – an den festen Stellen nach DIN 5008 auf der ersten Seite. Der Text beginnt darunter.",
  fusszeile: "Steht auf jeder Seite unten, auf Wunsch auf einem eigenen farbigen Band (bis 8 Zeilen links, rechts z. B. die Seitenzahl). {Seite} und {Seiten} werden zur Seitenzahl.",
};
/** Bausteine aus dem Entwurf; Briefkopf, Titel und Fußzeile gibt es je Vorlage einmal */
const BAUSTEINE = ["text", "zweispaltig", "datenfelder", "tabelle", "kopfkarte", "trennlinie", "leerraum", "unterschrift", "seitenumbruch", "titel", "briefkopf", "fusszeile", "email"];
const PLATZHALTER = /\{\{\s*([^{}]+?)\s*\}\}/g;

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

/** Anschriftfeld nach DIN 5008 mit den Angaben, die es in dieser Vorlage gibt */
function neuesAnschriftfeld(bloecke: Block[], felder: Datenfeld[]): Block {
  const da = (n: string) => felder.some((f) => f.name === n);
  const nur = (...namen: string[]) => namen.filter(da).map((n) => `{{${n}}}`);
  const name = da("Patient.Vorname_Name") ? ["{{Patient.Vorname_Name}}"] : nur("Patient.Name");
  return {
    id: neueId("anschriftfeld", bloecke), typ: "anschriftfeld", bezeichnung: "Anschriftfeld", form: "B", falzmarken: true,
    ruecksendung: nur("Absender.Name", "Absender.Straße", "Absender.PLZ_Ort").join(" · "),
    text: [...name, ...nur("Patient.Straße", "Patient.PLZ_Ort")].join("\n") || "Empfänger",
    rechts: da("Heute") ? "Datum: {{Heute}}" : "",
  };
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
      if (b.briefpapier) return (
        <div className="-mx-2 -mt-2 px-4 pt-3 pb-5 rounded-b-[50%_1.5rem] bg-[#BDC9C2] text-[#23272C] flex justify-between items-start">
          <Logo className="w-[9.375rem] h-[3.3125rem]" version={briefkopf.data?.logo.sha256} firma="rg" name="Regeneration Clinic" />
          <div className="flex flex-col items-end text-[0.9em]">
            <span className="font-semibold">Regeneration Clinic SIA</span><span>Briefpapier der Klinik (auf jeder Seite, mit Fußband)</span>
          </div>
        </div>
      );
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
      return <div className={cx("flex justify-between gap-3 text-[0.8em] leading-snug", !b.band && "text-[#00325a]")}><span><MitFeldern text={b.text} /></span><span><MitFeldern text={b.rechts} /></span></div>;
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
          <div className="text-[0.85em] text-[#5d5b72] mb-0.5">E-Mail (nicht auf der PDF) · Doppelklick zum Bearbeiten</div>
          <div className="font-semibold"><MitFeldern text={b.betreff} /></div>
          <div className="line-clamp-6"><MitFeldern text={b.text} /></div>
        </div>
      );
    case "anschriftfeld": // im Querformat ohne feste Stelle, die Anschrift steht im Textfluss
      return <div className="text-[1em]"><MitFeldern text={b.text} /></div>;
    case "seitenumbruch":
      return <div className="text-center text-[0.9em] text-[#888] border-t border-dashed border-[#bbb] pt-0.5">Seitenumbruch</div>;
    default:
      return null;
  }
}

/** Farbige Fläche des Kopf- oder Fußbands (gespiegelt unten), Maße in mm wie in der PDF */
function BandFlaeche({ b, breite, hoehe, fuss }: { b: Block; breite: number; hoehe: number; fuss?: boolean }) {
  return (
    <svg viewBox={`0 0 ${breite} ${hoehe}`} preserveAspectRatio="none" style={{ width: breite * MM, height: hoehe * MM }} className="block">
      <path fill={b.bandfarbe ?? "#E8E6F2"} d={bandPfad(b.kopfband || "gerade", breite, hoehe, schwung(hoehe, fuss))}
        transform={fuss ? `translate(0 ${hoehe}) scale(1 -1)` : undefined} />
    </svg>
  );
}

/** Kopfband mit Logo und Absender, wie es auf jeder (oder der ersten) Seite steht */
function KopfbandAnsicht({ b, breite }: { b: Block; breite: number }) {
  const briefkopf = useBriefkopf();
  const a = briefkopf.data ? briefkopf.data.absender[briefkopf.data.aktiv] : null;
  return (
    <div className="relative">
      <BandFlaeche b={b} breite={breite} hoehe={b.bandhoehe_mm ?? 38} />
      <div className={cx("absolute flex justify-between items-start gap-6", b.logo_rechts && "flex-row-reverse")}
        style={{ top: 7 * MM, left: RAND_LINKS * MM, right: RAND_LINKS * MM, color: b.textfarbe ?? "#1b1932" }}>
        <Logo className="w-[9.375rem] h-[3.3125rem]" version={briefkopf.data?.logo.sha256} firma={briefkopf.data?.firma?.kuerzel} name={briefkopf.data?.firma?.name} />
        {b.absender !== false && a ? (
          <div className={cx("flex flex-col text-[0.75rem] leading-snug", b.logo_rechts ? "items-start" : "items-end")}>
            <span>{a.strasse} · {a.plz} {a.ort}</span><span>Tel. {a.telefon}</span><span>{a.email}</span>
          </div>
        ) : null}
      </div>
      {b.band_seiten === "erste" ? <span className="absolute right-2 bottom-1 text-[0.625rem] px-1 rounded bg-white/80 text-[#3b3953]">nur erste Seite</span> : null}
    </div>
  );
}

/** Anschriftfeld nach DIN 5008: Rücksendeangabe oben (5 mm), Anschrift ab der Anschriftzone (nach 17,7 mm) */
function AnschriftfeldAnsicht({ b }: { b: Block }) {
  return (
    <div className="h-full overflow-hidden outline outline-1 outline-dashed outline-[#9a98b3] -outline-offset-1">
      <div className="text-[0.62rem] leading-tight text-[#3b3953] whitespace-nowrap overflow-hidden" style={{ height: 5 * MM, paddingTop: 1.5 * MM, paddingLeft: 2 }}>
        <span className="border-b border-[#3b3953]"><MitFeldern text={b.ruecksendung} /></span>
      </div>
      <div className="text-[0.95em] leading-tight" style={{ paddingTop: 12.7 * MM, paddingLeft: 2 }}><MitFeldern text={b.text} /></div>
    </div>
  );
}

/** Text direkt auf der Seite schreiben (Doppelklick); Angaben aus der Akte setzt der Feldeinfüger an der Schreibmarke ein */
function TextAufDerSeite({ wert, onWert, fokus, onFertig, einzeilig, gross }: {
  wert: string; onWert: (w: string) => void; fokus: Fokus; onFertig: () => void; einzeilig?: boolean; gross?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const einsetzen = useEinsetzen(ref, wert, onWert, fokus);
  // ausdrücklich anmelden: ein schon fokussiertes Feld meldet beim zweiten focus() kein onFocus mehr
  useEffect(() => { const el = ref.current; el?.focus(); el?.setSelectionRange(el.value.length, el.value.length); einsetzen.onFocus(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const el = ref.current; if (el) { el.style.height = "auto"; el.style.height = `${el.scrollHeight}px`; } }, [wert]);
  return (
    <textarea ref={ref} aria-label="Text auf der Seite" value={wert} rows={1} onFocus={einsetzen.onFocus} onBlur={onFertig}
      onChange={(e) => onWert(einzeilig ? e.target.value.replace(/\n/g, " ") : e.target.value)}
      onKeyDown={(e) => { if (e.key === "Escape" || (einzeilig && e.key === "Enter")) { e.preventDefault(); onFertig(); } }}
      className={cx("block w-full resize-none overflow-hidden border-0 outline-none bg-[#f3f2fa] rounded-sm p-0 font-[inherit] text-inherit",
        gross ? "text-[1.6em] font-semibold" : "text-[1em] leading-relaxed")} />
  );
}

/** Lage im 6-Spalten-Raster: Vorgaben zum Antippen, von/bis Spalte, in derselben Zeile wie der Block davor */
function RasterWahl({ b, vorher, aendere }: { b: Block; vorher?: Block; aendere: (n: Partial<Block>) => void }) {
  const [von, bis] = vonBis(b);
  const neben = b.optionen?.neben_vorherigem === "raster";
  const vorBis = vorher && imRaster(vorher) ? vonBis(vorher)[1] : SPALTEN;
  const min = neben ? vorBis + 1 : 1;
  const setzeLage = (v: number, bi: number, n = neben) => aendere({ optionen: setzeRaster(b, { raster_von: v, raster_bis: bi, neben_vorherigem: n ? "raster" : undefined }).optionen });
  const vorgaben: { text: string; v: number; b: number }[] = [
    { text: "Ganz", v: 1, b: 6 }, { text: "½ links", v: 1, b: 3 }, { text: "½ rechts", v: 4, b: 6 }, { text: "⅓ links", v: 1, b: 2 },
    { text: "⅓ Mitte", v: 3, b: 4 }, { text: "⅓ rechts", v: 5, b: 6 }, { text: "⅔ links", v: 1, b: 4 }, { text: "⅔ rechts", v: 3, b: 6 },
  ];
  return (
    <div className="flex flex-col gap-2" role="group" aria-label="Lage im Raster" data-testid="raster-wahl">
      <span className="text-sm font-medium">Lage im Raster ({SPALTEN} Spalten)</span>
      <div className="flex gap-[3px]" aria-hidden>
        {Array.from({ length: SPALTEN }, (_, n) => n + 1).map((n) => (
          <button key={n} type="button" tabIndex={-1} onClick={() => (n < von ? setzeLage(Math.max(min, n), bis) : setzeLage(von, n))}
            title={`Spalte ${n}`} className={cx("flex-1 h-5 rounded-sm border-0 cursor-pointer", n >= von && n <= bis ? "bg-akzent" : n < min ? "bg-fein opacity-50" : "bg-fein")} />
        ))}
      </div>
      <div className="flex flex-wrap gap-1">
        {vorgaben.map((x) => (
          <button key={x.text} type="button" disabled={x.v < min} onClick={() => setzeLage(x.v, x.b)} aria-pressed={x.v === von && x.b === bis}
            className={cx("px-2 py-0.5 rounded-md border text-[0.75rem] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed",
              x.v === von && x.b === bis ? "border-akzent bg-akzent-weich text-akzent-text" : "border-rand bg-flaeche")}>{x.text}</button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Feld label="Von Spalte">{(p) => <Auswahl {...p} value={von} onChange={(e) => setzeLage(Number(e.target.value), Math.max(bis, Number(e.target.value)))}>
          {Array.from({ length: SPALTEN }, (_, n) => n + 1).map((n) => <option key={n} value={n} disabled={n < min}>{n}</option>)}</Auswahl>}</Feld>
        <Feld label="Bis Spalte">{(p) => <Auswahl {...p} value={bis} onChange={(e) => setzeLage(Math.min(von, Number(e.target.value)), Number(e.target.value))}>
          {Array.from({ length: SPALTEN }, (_, n) => n + 1).map((n) => <option key={n} value={n} disabled={n < min}>{n}</option>)}</Auswahl>}</Feld>
      </div>
      <label className="flex items-center gap-2 text-[0.8438rem]">
        <input type="checkbox" checked={neben} disabled={!neben && (!vorher || !imRaster(vorher) || vorBis >= SPALTEN)}
          onChange={(e) => {
            if (!e.target.checked) return setzeLage(von, bis, false);
            const v = Math.max(von, vorBis + 1);
            setzeLage(v, Math.max(bis, v), true);
          }} />In derselben Zeile wie der Block davor</label>
    </div>
  );
}

const GRUPPEN: { gruppe: Gruppe; titel: string; leer?: string }[] = [
  { gruppe: "schreiben", titel: "Briefe und E-Mails an Patienten" },
  { gruppe: "eigen", titel: "Eigene Vorlagen",
    leer: "Noch keine eigenen Vorlagen. „+ Neue Vorlage“ legt z. B. ein Schreiben an Hausärzte an; „Als eigene Vorlage kopieren“ im Editor nimmt ein bestehendes Schreiben als Grundlage." },
  // mitgelieferte Vorlagen der Regeneration Clinic (13.10.2026), nur in der Firma RGC sichtbar
  { gruppe: "anforderungen", titel: "Anforderungen: Labor, Bildgebung, Funktionsdiagnostik" },
  { gruppe: "formulare", titel: "Aufklärungen, Erklärungen und Abrechnung" },
  // Dokumente der Behandlungsfälle der RGC (26.10.2026): OP-Bericht, Entlassungsbrief, Konsil, Rechnung je Sprache
  { gruppe: "fall", titel: "Dokumente der Behandlungsfälle" },
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
      // ältere Vorlagen (Drittel/Hälfte nebeneinander) erscheinen gleich im 6-Spalten-Raster
      const b = insRaster(entwurf.data.bloecke);
      setBloecke(structuredClone(b));
      setAusrichtung(entwurf.data.ausrichtung ?? "hoch");
      setGeladen(JSON.stringify({ bloecke: b, ausrichtung: entwurf.data.ausrichtung ?? "hoch" }));
      setAuswahl(entwurf.data.bloecke[0]?.id ?? null);
    }
  }, [entwurf.data, bloecke]);

  const neuLaden = (geladenBloecke: Block[], a?: Ausrichtung) => {
    const b = insRaster(geladenBloecke);
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
    onSuccess: (v) => { setBloecke(structuredClone(insRaster(v.bloecke))); setAuswahl(v.bloecke[0]?.id ?? null); melden("Mitgelieferte Startvorlage als Grundlage geladen – noch nicht gespeichert."); },
  });

  const sort = useSortierbar(bloecke ?? [], (neu) => setBloecke(ordne(neu)));
  // Gestaltung am Raster (14.10.2026): Text direkt auf der Seite, Ziehen mit Anzeige des Ziels, Raster einblenden
  const [bearbeitet, setBearbeitet] = useState<string | null>(null);
  const [zieht, setZieht] = useState<string | null>(null);
  const [anzeige, setAnzeige] = useState<{ ziel: Ziel; top: number; left: number; width: number; height: number } | null>(null);
  const [rasterZeigen, setRasterZeigen] = useState(true);
  // E-Mail der Schreiben im eigenen Fenster bearbeiten (14.10.2026)
  const [emailFenster, setEmailFenster] = useState(false);
  const inhaltRef = useRef<HTMLDivElement>(null);
  const gezogen = useRef(false);
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
  const aendereBlock = (id: string, neu: Partial<Block>) => setBloecke((alt) => ordne((alt ?? []).map((b) => (b.id === id ? { ...b, ...neu } : b))));
  const aendere = (neu: Partial<Block>) => { if (auswahl) aendereBlock(auswahl, neu); };
  const aendereOptionen = (neu: Partial<Optionen>) => aendere({ optionen: { ...gewaehlt?.optionen, ...neu } });
  const verschiebe = (i: number, nach: number) => {
    if (nach < 0 || nach >= bloecke.length) return;
    const neu = [...bloecke];
    const [x] = neu.splice(i, 1);
    neu.splice(nach, 0, x);
    setBloecke(neu);
  };
  const entferne = (id: string) => { const neu = ordne(bloecke.filter((b) => b.id !== id)); setBloecke(neu); waehleBlock(neu[0]?.id ?? null); };
  const reihen = zeilen(bloecke);
  const hinzufuegen = (typ: string) => {
    if (gezogen.current) return; // gerade auf die Seite gezogen
    const b = neuerBlock(typ, bloecke, a.tabellen);
    // hinter die Zeile des markierten Abschnitts, damit ein Nebeneinander nicht auseinanderfällt
    const ende = index >= 0 ? Math.max(...(reihen.find((z) => z.includes(index)) ?? [index])) + 1 : bloecke.length;
    const nach = typ === "briefkopf" ? 0 : typ === "fusszeile" || typ === "email" ? bloecke.length : ende;
    const neu = [...bloecke];
    neu.splice(nach, 0, b);
    setBloecke(ordne(neu));
    waehleBlock(b.id);
  };
  // Anschriftfeld nach DIN 5008 ein- und ausschalten: steht hinter dem Briefkopf, bringt eigene Falzmarken mit
  const dinBlock = bloecke.find((b) => b.typ === "anschriftfeld");
  const schalteDin = (an: boolean) => {
    if (!an) { if (dinBlock) entferne(dinBlock.id); return; }
    const feld = neuesAnschriftfeld(bloecke, a.felder);
    const kopf = bloecke.findIndex((b) => b.typ === "briefkopf");
    const neu = bloecke.map((b) => (b.typ === "briefkopf" && b.falzmarken ? { ...b, falzmarken: false } : b));
    neu.splice(kopf + 1, 0, feld);
    setBloecke(ordne(neu));
    waehleBlock(feld.id);
    // Abschnitte, die schon eine Anschrift enthalten (z. B. „Empfänger und Datum“), stünden sonst doppelt
    const doppelt = bloecke.filter((b) => b.typ !== "briefkopf" && /\{\{\s*(Patient\.Straße|Absender\.Straße)\s*\}\}/.test(
      [b.text, b.links, b.rechts].join(" "))).map((b) => `„${b.bezeichnung || TYPNAME[b.typ]}“`);
    melden(doppelt.length ? `Anschriftfeld eingefügt. ${doppelt.join(", ")} ${doppelt.length > 1 ? "enthalten" : "enthält"} ebenfalls eine Anschrift – bei Bedarf entfernen.`
      : "Anschriftfeld nach DIN 5008 eingefügt.");
  };

  /** Ziel unter dem Mauszeiger: neue Zeile zwischen zwei Zeilen oder ein freier Platz in einer Zeile */
  const zielAn = (x: number, y: number, ziehtId: string | null, raster: boolean, breite: number) => {
    const inhalt = inhaltRef.current;
    if (!inhalt) return null;
    const r0 = inhalt.getBoundingClientRect();
    if (x < r0.left - 60 || x > r0.right + 60 || y < r0.top - 120 || y > r0.bottom + 160) return null;
    const zeilenEl = [...inhalt.querySelectorAll<HTMLElement>("[data-zeile]")];
    const linie = (top: number, vorId: string | null) => ({ ziel: { art: "zeile", vorId } as Ziel, top: top - r0.top - 2, left: 0, width: r0.width, height: 4 });
    if (!zeilenEl.length) return linie(r0.top, null);
    const prozent = ((x - r0.left) / r0.width) * 100;
    const spalte = Math.min(SPALTEN, Math.max(1, Math.floor(prozent / (SPALTE + 2.8)) + 1));
    for (let n = 0; n < zeilenEl.length; n += 1) {
      const el = zeilenEl[n];
      const r = el.getBoundingClientRect();
      const ids = (el.dataset.zeile ?? "").split(" ");
      const naechste = zeilenEl[n + 1]?.dataset.zeile?.split(" ")[0] ?? null;
      if (y < r.top) return linie(r.top - 5, ids[0]);
      if (y > r.bottom) continue;
      const rel = (y - r.top) / Math.max(r.height, 1);
      const mitglieder = ids.map((id) => bloecke.find((b) => b.id === id)).filter((b): b is Block => !!b);
      const fuegbar = raster && mitglieder.every(imRaster) && mitglieder.some((b) => b.id !== ziehtId);
      if (fuegbar && rel > 0.2 && rel < 0.8) {
        const platz = freierPlatz(mitglieder.filter((b) => b.id !== ziehtId).map(vonBis), spalte, breite);
        if (platz) return { ziel: { art: "neben", zeileIds: ids, von: platz[0], bis: platz[1] } as Ziel, top: r.top - r0.top,
          height: Math.max(r.height, 24), left: (rasterLinks(platz[0]) / 100) * r0.width, width: (rasterBreite(platz[0], platz[1]) / 100) * r0.width };
      }
      return rel < 0.5 ? linie(r.top - 5, ids[0]) : linie(r.bottom + 5, naechste);
    }
    return linie(zeilenEl[zeilenEl.length - 1].getBoundingClientRect().bottom + 5, null);
  };
  /** Block (oder neuen Baustein) mit Maus, Stift oder Finger auf die Seite ziehen; ein Klick ohne Bewegung wählt nur */
  const ziehStart = (e: ReactPointerEvent, quelle: { id: string } | { typ: string }) => {
    if (e.button !== 0) return;
    const block = "id" in quelle ? bloecke.find((b) => b.id === quelle.id) ?? null : null;
    const typ = block?.typ ?? ("typ" in quelle ? quelle.typ : "");
    if (block && bearbeitet === block.id) return;
    const breite = block && imRaster(block) && block.optionen?.raster_von ? vonBis(block)[1] - vonBis(block)[0] + 1 : SPALTEN;
    const start = { x: e.clientX, y: e.clientY };
    let aktiv = false;
    let letztes: Ziel | null = null;
    const bewegen = (ev: PointerEvent) => {
      if (!aktiv && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 6) return;
      if (!aktiv) { aktiv = true; setZieht(block?.id ?? `neu:${typ}`); }
      ev.preventDefault();
      const t = zielAn(ev.clientX, ev.clientY, block?.id ?? null, imRaster({ id: "", typ }), breite);
      letztes = t?.ziel ?? null;
      setAnzeige(t);
    };
    const ende = (abbrechen: boolean) => {
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", hoch);
      window.removeEventListener("pointercancel", abbruch);
      setAnzeige(null);
      setZieht(null);
      if (!aktiv) return;
      gezogen.current = true;
      window.setTimeout(() => { gezogen.current = false; }, 0);
      if (abbrechen || !letztes) return;
      if (block) {
        if (letztes.art === "zeile" && letztes.vorId === block.id) return;
        setBloecke(setze(bloecke, block.id, null, letztes));
        waehleBlock(block.id);
      } else {
        const neu = neuerBlock(typ, bloecke, a.tabellen);
        setBloecke(setze(bloecke, null, neu, letztes));
        waehleBlock(neu.id);
      }
    };
    const hoch = () => ende(false);
    const abbruch = () => ende(true);
    window.addEventListener("pointermove", bewegen);
    window.addEventListener("pointerup", hoch);
    window.addEventListener("pointercancel", abbruch);
  };
  /** Breite am linken oder rechten Rand ziehen; rastet an den 6 Spalten ein */
  const randStart = (e: ReactPointerEvent, id: string, seite: "links" | "rechts") => {
    e.stopPropagation();
    e.preventDefault();
    setZieht("rand");
    const bewegen = (ev: PointerEvent) => {
      const r = inhaltRef.current?.getBoundingClientRect();
      if (r) setBloecke((alt) => (alt ? ziehRand(alt, id, seite, ((ev.clientX - r.left) / r.width) * 100) : alt));
    };
    const hoch = () => {
      window.removeEventListener("pointermove", bewegen);
      window.removeEventListener("pointerup", hoch);
      window.removeEventListener("pointercancel", hoch);
      setZieht(null);
      setBloecke((alt) => (alt ? ordne(alt) : alt));
    };
    window.addEventListener("pointermove", bewegen);
    window.addEventListener("pointerup", hoch);
    window.addEventListener("pointercancel", hoch);
  };
  const einfuegen = (name: string) => {
    if (fokus.current) fokus.current.setze(name);
    else melden(gewaehlt ? "Dieser Abschnitt hat kein Textfeld. Bitte einen Abschnitt mit Text markieren (z. B. „Text“)." : "Bitte zuerst einen Abschnitt markieren.");
  };
  const quer = ausrichtung === "quer";
  const kopfBlock = bloecke.find((b) => b.typ === "briefkopf");
  const band = kopfBlock && !kopfBlock.briefpapier && kopfBlock.kopfband ? kopfBlock : null;
  const din = !quer ? dinBlock : undefined;
  const seiteMm = quer ? { b: 297, h: 210 } : { b: 210, h: 297 };
  const oben = band ? (band.bandhoehe_mm ?? 38) + BAND_ABSTAND : RAND_OBEN;
  const fussBlock = bloecke.find((b) => b.typ === "fusszeile");
  const unten = Math.max(18, 10 + 3.6 * ((fussBlock?.text ?? "").split("\n").length));
  // Fußband: eigenes der Fußzeile, sonst (ältere Angabe) das des Kopfbands
  const fussband: Block | null = fussBlock?.band ? { ...fussBlock, kopfband: fussBlock.band } : band?.fussband ? band : null;
  // Kopfband, Anschriftfeld und Fußzeile stehen an festen Stellen der Seite, nicht im Textfluss
  const fest = (b: Block) => (b === band) || (b === din) || (b === fussBlock);
  const schreibbar = (b: Block) => b.typ === "text" || b.typ === "titel";
  const rahmen = (b: Block, i: number) => (
    <div key={b.id} role="button" tabIndex={0} aria-label={`Block ${b.bezeichnung || TYPNAME[b.typ]}`} data-block={b.id}
      onClick={() => waehleBlock(b.id)} onKeyDown={(e) => { if (e.key === "Enter" && bearbeitet !== b.id) waehleBlock(b.id); }}
      onDoubleClick={() => { if (schreibbar(b)) { waehleBlock(b.id); setBearbeitet(b.id); } else if (b.typ === "email") { waehleBlock(b.id); setEmailFenster(true); } }}
      onPointerDown={(e) => { if (e.pointerType === "mouse" && !fest(b)) ziehStart(e, { id: b.id }); }}
      title={schreibbar(b) ? "Ziehen zum Verschieben · Doppelklick zum Schreiben" : b.typ === "email" ? "Doppelklick: E-Mail bearbeiten" : "Ziehen zum Verschieben"}
      className={cx("relative px-2 py-1.5 rounded", bearbeitet === b.id ? "cursor-text" : "cursor-grab", zieht === b.id && "opacity-40",
        b.id === auswahl ? "outline outline-2 outline-[#251F53]" : "hover:outline hover:outline-1 hover:outline-[#c9c8d4]")}>
      {b.id === auswahl ? <>
        {/* Griff: Ziehen mit Finger oder Stift (die Maus zieht am ganzen Block) */}
        <span className="absolute -top-2.5 left-1.5 text-[0.625rem] bg-[#251F53] text-white px-1.5 rounded-sm cursor-grab touch-none select-none"
          onPointerDown={(e) => { if (e.pointerType !== "mouse") { e.stopPropagation(); ziehStart(e, { id: b.id }); } }}>⠿ {b.bezeichnung || TYPNAME[b.typ]}</span>
        {imRaster(b) && bearbeitet !== b.id ? (["links", "rechts"] as const).map((seite) => (
          <span key={seite} aria-hidden onPointerDown={(e) => randStart(e, b.id, seite)} title="Ziehen: Breite im Raster ändern"
            className={cx("absolute top-1/2 -translate-y-1/2 w-2.5 h-7 rounded-sm bg-[#251F53] cursor-ew-resize touch-none border-2 border-white",
              seite === "links" ? "-left-1.5" : "-right-1.5")} data-testid={`rand-${seite}`} />
        )) : null}
        <span className="absolute -top-3 right-1 flex gap-0.5">
          <button type="button" aria-label="nach oben" title="nach oben" disabled={i === 0} onClick={(e) => { e.stopPropagation(); verschiebe(i, i - 1); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[0.6875rem] p-0 cursor-pointer">↑</button>
          <button type="button" aria-label="nach unten" title="nach unten" disabled={i === bloecke.length - 1} onClick={(e) => { e.stopPropagation(); verschiebe(i, i + 1); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[0.6875rem] p-0 cursor-pointer">↓</button>
          <button type="button" aria-label="entfernen" title="Abschnitt entfernen" onClick={(e) => { e.stopPropagation(); entferne(b.id); }} className="w-5 h-5 border border-[#251F53] bg-white text-[#251F53] rounded text-[0.6875rem] p-0 cursor-pointer">×</button>
        </span>
      </> : null}
      <div style={{ fontSize: SCHRIFT_PX[b.optionen?.schrift ?? "normal"] }}>
        {bearbeitet === b.id && schreibbar(b)
          ? <TextAufDerSeite wert={b.text ?? ""} onWert={(w) => aendereBlock(b.id, { text: w })} fokus={fokus} einzeilig={b.typ === "titel"}
            onFertig={() => setBearbeitet(null)} gross={b.typ === "titel"} />
          : <BlockAnsicht b={b} tabellen={a.tabellen} />}
      </div>
    </div>
  );
  /** Eine Zeile der Seite: Blöcke an ihren Spalten wie im PDF (Breite und Abstand in % wie gestaltung.raster_zeile) */
  const zeile = (z: number[]) => {
    const ids = z.map((i) => bloecke[i].id).join(" ");
    const imGitter = z.some((i) => imRaster(bloecke[i]) && (bloecke[i].optionen?.raster_von || bloecke[i].optionen?.raster_bis || bloecke[i].optionen?.neben_vorherigem));
    if (!imGitter && z.length === 1) return <div key={ids} data-zeile={ids}>{rahmen(bloecke[z[0]], z[0])}</div>;
    let rechts = 0;
    return (
      <div key={ids} data-zeile={ids} className="flex items-start" data-testid={z.length > 1 ? "nebeneinander" : undefined}>
        {z.map((i) => {
          const [von, bis] = vonBis(bloecke[i]);
          const links = rasterLinks(von);
          const stil = { marginLeft: `${links - rechts}%`, width: `${rasterBreite(von, bis)}%`, flex: "none" };
          rechts = links + rasterBreite(von, bis);
          return <div key={bloecke[i].id} style={stil}>{rahmen(bloecke[i], i)}</div>;
        })}
      </div>
    );
  };
  const sichtbar = reihen.filter((z) => !(z.length === 1 && fest(bloecke[z[0]])));
  const dinStelle = din ? bloecke.indexOf(din) : -1;
  const festerRahmen = (b: Block, inhalt: ReactNode, stil: CSSProperties, testid: string) => (
    <div role="button" tabIndex={0} aria-label={`Block ${b.bezeichnung || TYPNAME[b.typ]}`} data-testid={testid} style={stil}
      onClick={() => waehleBlock(b.id)} onKeyDown={(e) => { if (e.key === "Enter") waehleBlock(b.id); }}
      className={cx("absolute cursor-pointer", b.id === auswahl ? "outline outline-2 outline-[#251F53] z-10" : "hover:outline hover:outline-1 hover:outline-[#c9c8d4]")}>
      {inhalt}
    </div>
  );
  const einmal = (typ: string) => ["briefkopf", "fusszeile", "email", "anschriftfeld"].includes(typ) && bloecke.some((b) => b.typ === typ);
  const serverFehler = [speichern.error, freigeben.error, wiederherstellenM.error].find((e) => e instanceof ApiFehler) as ApiFehler | undefined;
  const fehlerListe = serverFehler ? (Array.isArray((serverFehler.daten as { bloecke?: string[] })?.bloecke)
    ? (serverFehler.daten as { bloecke: string[] }).bloecke : [serverFehler.message]) : [];
  const freigebbar = geaendert || entwurf.data.ist_entwurf;
  const stand = JSON.stringify({ bloecke, ausrichtung });
  const naechste = a.naechste_fassung ?? Math.max(0, ...a.versionen.map((v) => v.version ?? 0)) + 1;
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
                <button key={t} type="button" disabled={einmal(t)} onClick={() => hinzufuegen(t)} title={`${HINWEIS[t]} – Klicken oder auf die Seite ziehen`}
                  onPointerDown={(e) => { if (!einmal(t) && ansicht === "seite") ziehStart(e, { typ: t }); }}
                  className="px-2.5 py-1.5 border border-dashed border-rand rounded-lg bg-flaeche text-[0.8125rem] cursor-grab touch-none disabled:opacity-50 disabled:cursor-not-allowed">
                  + {TYPNAME[t]}
                </button>
              ))}
            </div>
            <span className="text-xs gedaempft leading-normal">Ein Klick setzt den neuen Abschnitt hinter den markierten; oder auf die Seite ziehen.</span>
          </Karte>
          <Karte className="p-3.5 flex flex-col gap-1.5" data-testid="versionen">
            <span className="lbl flex items-center gap-1.5">Frühere <Begriff name="fassung">Fassungen</Begriff>
              <Erklaerung titel="Fassungen">Bei jedem Freigeben entsteht eine neue Fassung; die alten bleiben erhalten (bis zur Übernahme der Altdaten
                ersetzt Freigeben die Fassung 1). „Ansehen“ zeigt eine
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
            {a.bausteine.some((x) => x.typ === "anschriftfeld") ? (
              <span className="flex items-center gap-1.5 text-[0.8438rem]">
                <label className="flex items-center gap-2" title={quer ? "Nur im Hochformat" : undefined}>
                  <input type="checkbox" role="switch" checked={!!dinBlock} disabled={quer && !dinBlock} onChange={(e) => schalteDin(e.target.checked)} data-testid="din-schalter" />
                  DIN 5008: Anschriftfeld für Fensterumschlag</label>
                <Erklaerung titel="Anschriftfeld nach DIN 5008">Setzt Rücksendeangabe, Anschrift und Informationsblock an die festen Stellen für den
                  Fensterumschlag (Form B: Anschrift 45 mm vom oberen Rand, Form A: 27 mm), dazu Falz- und Lochmarke. Der Text beginnt darunter.
                  Für Pläne und Vordrucke, die nicht verschickt werden (z. B. den Infusionsplan), ausgeschaltet lassen.</Erklaerung>
              </span>
            ) : null}
            {bloecke.some((b) => b.typ === "email") ? (
              <Knopf klein icon="stift" data-testid="email-bearbeiten" onClick={() => { const e = bloecke.find((b) => b.typ === "email"); if (e) waehleBlock(e.id); setEmailFenster(true); }}>
                E-Mail bearbeiten</Knopf>
            ) : null}
            {ansicht === "seite" ? (
              <label className="flex items-center gap-2 text-[0.8438rem]">
                <input type="checkbox" checked={rasterZeigen} onChange={(e) => setRasterZeigen(e.target.checked)} />Raster zeigen</label>
            ) : null}
          </div>
          {ansicht === "seite" ? <span className="text-[0.75rem] gedaempft -mt-1" data-testid="raster-hinweis">
            Abschnitte mit der Maus verschieben – sie rasten an {SPALTEN} Spalten ein. Am Rand ziehen ändert die Breite, Doppelklick schreibt
            direkt auf der Seite. Bausteine lassen sich aus „Abschnitt hinzufügen“ auf die Seite ziehen.</span> : null}
          {ansicht === "seite" ? (
            <div className="py-6 bg-[#E6E5EE] rounded-xl overflow-auto min-w-0" data-testid="vorlage-seite">
              <div className="relative mx-auto bg-white text-[#1a1a1a] shadow-md"
                style={{ width: seiteMm.b * MM, minHeight: seiteMm.h * MM,
                  padding: `${oben * MM}px ${RAND_LINKS * MM}px ${(fussband ? unten + 6 : unten) * MM}px` }}>
                {band ? festerRahmen(band, <KopfbandAnsicht b={band} breite={seiteMm.b} />, { top: 0, left: 0 }, "kopfband") : null}
                {fussband ? <div className="absolute bottom-0 left-0 pointer-events-none" data-testid="fussband">
                  <BandFlaeche b={fussband} breite={seiteMm.b} hoehe={unten + 4} fuss /></div> : null}
                {fussBlock ? festerRahmen(fussBlock, <div style={{ fontSize: 10, color: fussband?.textfarbe }}><BlockAnsicht b={fussBlock} tabellen={a.tabellen} /></div>,
                  { top: `calc(100% - ${(unten - 4) * MM + 4}px)`, left: RAND_LINKS * MM - 4, right: RAND_LINKS * MM - 4, padding: 4 }, "fusszeile") : null}
                {din ? <>
                  {festerRahmen(din, <AnschriftfeldAnsicht b={din} />, { top: DIN[din.form ?? "B"].oben * MM, left: DIN_LINKS * MM,
                    width: DIN_BREITE * MM, height: DIN_HOEHE * MM }, "anschriftfeld")}
                  {din.rechts ? festerRahmen(din, <div className="text-[0.85em] leading-snug"><MitFeldern text={din.rechts} /></div>,
                    { top: DIN[din.form ?? "B"].info_oben * MM, left: DIN_INFO_LINKS * MM, width: DIN_INFO_BREITE * MM }, "informationsblock") : null}
                </> : null}
                <div ref={inhaltRef} className="relative flex flex-col gap-2.5" data-testid="seiteninhalt">
                  {rasterZeigen || zieht ? (
                    <div aria-hidden className="absolute -top-2 -bottom-2 inset-x-0 pointer-events-none" data-testid="raster">
                      {Array.from({ length: SPALTEN }, (_, n) => (
                        <div key={n} className={cx("absolute top-0 bottom-0 border-x border-dashed", zieht ? "bg-[#251F53]/[0.06] border-[#251F53]/25" : "bg-[#251F53]/[0.025] border-[#251F53]/10")}
                          style={{ left: `${rasterLinks(n + 1)}%`, width: `${SPALTE}%` }} />
                      ))}
                    </div>
                  ) : null}
                  {din ? <div className="flex flex-col gap-2.5" style={{ minHeight: Math.max(0, DIN[din.form ?? "B"].text_ab - oben) * MM }}>
                    {sichtbar.filter((z) => z[0] < dinStelle).map(zeile)}</div> : null}
                  {sichtbar.filter((z) => !din || z[0] > dinStelle).map(zeile)}
                  {anzeige ? <div aria-hidden data-testid="ziel-anzeige"
                    className={cx("absolute pointer-events-none rounded", anzeige.ziel.art === "neben" ? "border-2 border-dashed border-[#251F53] bg-[#251F53]/10" : "bg-[#251F53]")}
                    style={{ top: anzeige.top, left: anzeige.left, width: anzeige.width, height: anzeige.height }} /> : null}
                </div>
              </div>
            </div>
          ) : <LiveVorschau art={art} bloecke={bloecke} ausrichtung={ausrichtung ?? "hoch"} onGeprueft={setGeprueft} />}
        </div>

        <aside className="flex flex-col gap-3.5 min-w-0">
          {gewaehlt ? <BlockEigenschaften key={gewaehlt.id} b={gewaehlt} vorher={bloecke[index - 1]} aufbau={a} aendere={aendere} aendereOptionen={aendereOptionen} fokus={fokus} />
            : <Karte className="p-4 text-sm gedaempft">Abschnitt im Aufbau oder auf der Seite anklicken.</Karte>}
          <Feldeinfueger felder={a.felder} onWahl={einfuegen} />
          <div className="flex gap-2 p-3 rounded-lg bg-fein text-[0.7812rem] leading-normal text-text2">
            <Icon name="info" /><span>Änderungen gelten erst nach „Freigeben“. Schon erzeugte PDFs und freigegebene Pläne bleiben unverändert.</span>
          </div>
          {entwurf.data.ist_entwurf ? <Knopf variante="geist" onClick={() => setVerwerfen(true)}>Nicht freigegebene Änderungen verwerfen</Knopf> : null}
        </aside>
      </div>

      <Dialog offen={freigabeFrage} onOffen={setFreigabeFrage} titel={`${a.name}: Änderungen freigeben`} breite={540}
        beschreibung={a.nur_fassung_1
          ? `Ersetzt Fassung 1 (bis zur Übernahme der Altdaten gibt es nur sie) und gilt ab sofort für alle neuen PDFs${mitEmailArt(art) ? " und E-Mails" : ""}.`
          : `Wird Fassung ${naechste} und gilt ab sofort für alle neuen PDFs${mitEmailArt(art) ? " und E-Mails" : ""}. Fassung ${a.aktiv.version} bleibt erhalten und lässt sich wiederherstellen.`}
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
      {emailFenster && bloecke.some((b) => b.typ === "email") ? (
        <EmailFenster art={art} bloecke={bloecke} ausrichtung={ausrichtung ?? "hoch"} felder={a.felder} onZu={() => setEmailFenster(false)}
          onUebernehmen={(neu) => { const e = bloecke.find((b) => b.typ === "email"); if (e) aendereBlock(e.id, neu); setEmailFenster(false); }} />
      ) : null}
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

function BlockEigenschaften({ b, vorher, aufbau, aendere, aendereOptionen, fokus }: {
  b: Block; vorher?: Block; aufbau: Aufbau; aendere: (n: Partial<Block>) => void; aendereOptionen: (n: Partial<Optionen>) => void;
  fokus: Fokus;
}) {
  const o = b.optionen ?? {};
  const eintraege = b.felder ?? [];
  const setzeEintrag = (i: number, neu: Partial<Eintrag>) => aendere({ felder: eintraege.map((e, j) => (j === i ? { ...e, ...neu } : e)) });
  // Reihenfolge der Felder: Ziehen am Griff, Pfeiltasten am Griff oder ▲ ▼
  const feldSort = useSortierbar(eintraege, (neu) => aendere({ felder: neu }));
  const textartig = !["briefkopf", "trennlinie", "leerraum", "seitenumbruch", "email", "anschriftfeld"].includes(b.typ);
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
        <span className="text-[0.75rem] gedaempft">Bequemer: „E-Mail bearbeiten“ über der Seite oder Doppelklick auf die E-Mail öffnet ein großes Fenster.</span>
        <FeldText label="Betreff" wert={b.betreff ?? ""} onWert={(w) => aendere({ betreff: w })} fokus={fokus} />
        <FeldText label="Text" wert={b.text ?? ""} onWert={(w) => aendere({ text: w })} fokus={fokus} mehrzeilig />
      </> : null}
      {b.typ === "fusszeile" ? <>
        <FeldText label="Rechts" wert={b.rechts ?? ""} onWert={(w) => aendere({ rechts: w })} fokus={fokus} />
        <FusszeileWahl b={b} aendere={aendere} felder={aufbau.felder} />
      </> : null}
      {b.typ === "zweispaltig" ? <>
        <FeldText label="Links" wert={b.links ?? ""} onWert={(w) => aendere({ links: w })} fokus={fokus} mehrzeilig />
        <FeldText label="Rechts" wert={b.rechts ?? ""} onWert={(w) => aendere({ rechts: w })} fokus={fokus} mehrzeilig />
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!b.rechts_klein} onChange={(e) => aendere({ rechts_klein: e.target.checked })} />Rechte Spalte kleiner</label>
      </> : null}
      {b.typ === "briefkopf" ? <>
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!b.briefpapier} onChange={(e) => aendere(e.target.checked ? { briefpapier: "rgc", kopfband: "" } : { briefpapier: "" })} />Briefpapier der Regeneration Clinic (wie gedruckt, Bänder oben und unten auf jeder Seite)</label>
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={b.absender !== false} onChange={(e) => aendere({ absender: e.target.checked })} />{b.briefpapier ? "Absenderzeile, Kontakt und Datum auf der ersten Seite" : "Absender neben dem Logo"}</label>
      </> : null}
      {b.typ === "briefkopf" && !b.briefpapier ? <>
        <Segmente label="Gestaltung des Kopfs" wert={b.kopfband ? "band" : "linie"} className="self-start"
          onWahl={(w) => aendere(w === "band" ? { kopfband: "welle", bandfarbe: b.bandfarbe ?? "#BDC9C2", textfarbe: b.textfarbe ?? "#23272C", bandhoehe_mm: b.bandhoehe_mm ?? 38 } : { kopfband: "" })}
          werte={[{ wert: "linie", text: "Logo mit Linie" }, { wert: "band", text: "Farbiges Band" }]} />
        {b.kopfband ? <KopfbandWahl b={b} aendere={aendere} /> : <>
          <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={b.mit_linie !== false} onChange={(e) => aendere({ mit_linie: e.target.checked })} />Linie unter dem Logo</label>
          {b.mit_linie !== false ? <label className="flex items-center gap-2 text-[0.8438rem]">Linienfarbe
            <input type="color" aria-label="Linienfarbe" value={(b.linienfarbe ?? "#251F53").toLowerCase()} onChange={(e) => aendere({ linienfarbe: e.target.value.toUpperCase() })} /></label> : null}
        </>}
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!b.falzmarken} onChange={(e) => aendere({ falzmarken: e.target.checked })} />Falzmarken am linken Rand</label>
      </> : null}
      {b.typ === "anschriftfeld" ? <>
        <Segmente label="Form nach DIN 5008" wert={b.form ?? "B"} onWahl={(w) => aendere({ form: w })} className="self-start"
          werte={[{ wert: "B", text: "Form B (45 mm)" }, { wert: "A", text: "Form A (27 mm)" }]} />
        <FeldText label="Rücksendeangabe (eine Zeile)" wert={b.ruecksendung ?? ""} onWert={(w) => aendere({ ruecksendung: w })} fokus={fokus} />
        <FeldText label="Anschrift (bis 6 Zeilen)" wert={b.text ?? ""} onWert={(w) => aendere({ text: w })} fokus={fokus} mehrzeilig />
        <FeldText label="Informationsblock rechts" wert={b.rechts ?? ""} onWert={(w) => aendere({ rechts: w })} fokus={fokus} mehrzeilig />
        <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={b.falzmarken !== false} onChange={(e) => aendere({ falzmarken: e.target.checked })} />Falzmarken und Lochmarke</label>
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
      {!["fusszeile", "seitenumbruch", "email", "anschriftfeld"].includes(b.typ) ? <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!o.nicht_teilen} onChange={(e) => aendereOptionen({ nicht_teilen: e.target.checked })} />Nicht über Seitenumbruch teilen</label> : null}
      {textartig && b.typ !== "fusszeile" ? <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!o.linie_oben} onChange={(e) => aendereOptionen({ linie_oben: e.target.checked })} />Linie darüber</label> : null}
      {b.typ === "text" ? (
        <Segmente label="Spalten" wert={String(o.spalten ?? 1)} onWahl={(w) => aendereOptionen({ spalten: w === "1" ? undefined : Number(w) as 2 | 3 })}
          werte={[{ wert: "1", text: "1" }, { wert: "2", text: "2" }, { wert: "3", text: "3" }]} />
      ) : null}
      {imRaster(b) ? <RasterWahl b={b} vorher={vorher} aendere={aendere} /> : null}
    </Karte>
  );
}

/** TextMitAngaben (TipTap) erst laden, wenn das Fenster aufgeht – wie components/Editor.tsx ohne Suspense */
let textMitAngaben: ComponentType<TextMitAngabenProps> | null = null;
let textMitAngabenLaden: Promise<ComponentType<TextMitAngabenProps>> | null = null;
function useTextMitAngaben() {
  const [k, setK] = useState(() => textMitAngaben);
  useEffect(() => {
    if (k) return;
    textMitAngabenLaden ??= import("@/components/TextMitAngaben").then((m) => (textMitAngaben = m.default));
    void textMitAngabenLaden.then((x) => setK(() => x));
  }, [k]);
  return k;
}

/** E-Mail der Schreiben bearbeiten wie in Word: Betreff und Text mit Angaben als Chips, Vorschau mit Testpatient */
function EmailFenster({ art, bloecke, ausrichtung, felder, onZu, onUebernehmen }: {
  art: Art; bloecke: Block[]; ausrichtung: Ausrichtung; felder: Datenfeld[]; onZu: () => void;
  onUebernehmen: (neu: { betreff: string; text: string }) => void;
}) {
  const block = bloecke.find((b) => b.typ === "email")!;
  const [betreff, setBetreff] = useState(block.betreff ?? "");
  const [text, setText] = useState(block.text ?? "");
  const [ansicht, setAnsicht] = useState<"schreiben" | "vorschau">("schreiben");
  const ziel = useRef<AngabenZiel | null>(null);
  const Feld_ = useTextMitAngaben();
  const nachName = useMemo(() => new Map(felder.map((f) => [f.name, f])), [felder]);
  const beschrifte = (name: string): Beschriftung => {
    const f = nachName.get(name);
    return f ? { text: f.bezeichnung ?? name, titel: `{{${name}}} · ${f.beschreibung}`, unbekannt: false }
      : { text: `${name}?`, titel: `Unbekannte Angabe {{${name}}} – bitte aus der Liste einfügen`, unbekannt: true };
  };
  const geaendert = betreff !== (block.betreff ?? "") || text !== (block.text ?? "");
  const vorschauBloecke = useMemo(() => bloecke.map((b) => (b.id === block.id ? { ...b, betreff, text } : b)), [bloecke, block.id, betreff, text]);
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel="E-Mail bearbeiten" breite={1080}
      beschreibung="So kommt die E-Mail beim Patienten an, die PDF des Schreibens hängt an. Angaben aus der Akte rechts anklicken – sie werden beim Erstellen eingesetzt. Im Dialog „Schreiben und E-Mail“ lässt sich der Text vor dem Versand noch anpassen."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" icon="haken" disabled={!geaendert} onClick={() => onUebernehmen({ betreff, text })}>Übernehmen</Knopf></>}>
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_17rem] gap-4" data-testid="email-fenster">
        <div className="flex flex-col gap-2 min-w-0">
          <Segmente label="Ansicht der E-Mail" wert={ansicht} onWahl={setAnsicht} className="self-start"
            werte={[{ wert: "schreiben", text: "Schreiben" }, { wert: "vorschau", text: "Vorschau mit Testpatient" }]} />
          {ansicht === "schreiben" ? (
            <div className="border border-rand rounded-lg bg-white text-[#1a1a1a] shadow-sm overflow-hidden">
              <div className="grid grid-cols-[5rem_minmax(0,1fr)] items-center border-b border-rand text-[0.875rem]">
                <span className="px-3 py-2 gedaempft">An</span>
                <span className="px-3 py-2 gedaempft italic">E-Mail-Adresse aus der Akte</span>
              </div>
              <div className="grid grid-cols-[5rem_minmax(0,1fr)] items-center border-b border-rand text-[0.875rem]">
                <span className="px-3 py-2 gedaempft">Betreff</span>
                {Feld_ ? <Feld_ label="Betreff" wert={betreff} onWert={setBetreff} beschrifte={beschrifte} einzeilig className="px-3 py-2 font-medium"
                  onFokus={(z) => { ziel.current = z; }} /> : <span className="px-3 py-2"><Ladekreis groesse={12} /></span>}
              </div>
              <div className="grid grid-cols-[5rem_minmax(0,1fr)] items-center border-b border-rand text-[0.8125rem]">
                <span className="px-3 py-1.5 gedaempft">Anlage</span>
                <span className="px-3 py-1.5 flex items-center gap-1.5"><Icon name="dokument" /> PDF des Schreibens</span>
              </div>
              {/* der Text scrollt im Fenster, damit „Übernehmen“ sichtbar bleibt */}
              <div className="max-h-[48vh] overflow-y-auto">
                {Feld_ ? <Feld_ label="Text der E-Mail" wert={text} onWert={setText} beschrifte={beschrifte} autofokus minHoehe={280}
                  className="px-5 py-4 text-[0.9375rem] font-[inherit] [&_.ProseMirror]:outline-none" onFokus={(z) => { ziel.current = z; }} /> : <Laden />}
              </div>
            </div>
          ) : <EmailVorschau art={art} bloecke={vorschauBloecke} ausrichtung={ausrichtung} />}
          <span className="text-[0.75rem] gedaempft">Die E-Mail geht als reiner Text – ohne Fett oder Farben –, damit sie in jedem Postfach gleich aussieht.
            Leerzeilen und Absätze bleiben erhalten.</span>
        </div>
        <Feldeinfueger felder={felder} onWahl={(name) => { setAnsicht("schreiben"); ziel.current?.einfuegen(name); }} />
      </div>
    </Dialog>
  );
}

/** Betreff und Text der E-Mail mit einem Testpatienten, wie im Dialog „Schreiben und E-Mail“ */
function EmailVorschau({ art, bloecke, ausrichtung }: { art: Art; bloecke: Block[]; ausrichtung: Ausrichtung }) {
  const patienten = useQuery({
    queryKey: ["patienten", "testpatienten"],
    queryFn: () => api<Seitenliste<Testpatient>>(`patienten/${abfrage({ test: "nur", seitengroesse: 50 })}`),
  });
  const [patient, setPatient] = useState("");
  useEffect(() => {
    if (!patient && patienten.data?.results[0]) setPatient(String(patienten.data.results[0].id));
  }, [patienten.data, patient]);
  const mail = useQuery({
    queryKey: ["vorlagen", art, "vorschau-mail", patient, JSON.stringify(bloecke)],
    queryFn: () => api<{ betreff: string; text: string }>(`vorlagen/${art}/vorschau/`, { body: { patient: Number(patient), bloecke, ausrichtung, ausgabe: "email" } }),
    enabled: !!patient, gcTime: 0, retry: false,
  });
  return (
    <div className="flex flex-col gap-2" data-testid="email-vorschau">
      <Feld label="Testpatient" className="max-w-[20rem]">{(p) => (
        <Auswahl {...p} value={patient} onChange={(e) => setPatient(e.target.value)}>
          {(patienten.data?.results ?? []).map((t) => <option key={t.id} value={t.id}>{t.nachname}, {t.vorname} · Nr. {t.nummer}</option>)}
        </Auswahl>
      )}</Feld>
      <Fehleranzeige fehler={mail.error} />
      {mail.data ? (
        <div className="border border-rand rounded-lg bg-white text-[#1a1a1a] px-5 py-4 text-[0.9375rem]">
          <div className="font-semibold mb-3">{mail.data.betreff}</div>
          <div className="whitespace-pre-wrap leading-relaxed">{mail.data.text}</div>
        </div>
      ) : mail.isFetching ? <Laden text="Vorschau wird erstellt …" /> : null}
    </div>
  );
}

/** Kopfband frei gestalten: Form, Farben, Höhe, Seiten, Logo rechts, Fußband */
function KopfbandWahl({ b, aendere }: { b: Block; aendere: (n: Partial<Block>) => void }) {
  const hoehe = b.bandhoehe_mm ?? 38;
  return (
    <div className="flex flex-col gap-2.5" data-testid="kopfband-wahl">
      <FormWahl wert={b.kopfband ?? ""} farbe={b.bandfarbe ?? "#BDC9C2"} onWert={(w) => aendere({ kopfband: w })} />
      <FarbWahl label="Farbe des Bands" wert={b.bandfarbe ?? "#BDC9C2"} onWert={(w) => aendere({ bandfarbe: w })} vorschlaege={BANDFARBEN} />
      <FarbWahl label="Schriftfarbe" wert={b.textfarbe ?? "#23272C"} onWert={(w) => aendere({ textfarbe: w })} vorschlaege={["#23272C", "#FFFFFF", "#251F53"]} />
      <label className="flex flex-col gap-1 text-[0.8125rem]">Höhe: {hoehe} mm
        <input type="range" min={20} max={80} step={1} value={hoehe} aria-label="Höhe des Bands" onChange={(e) => aendere({ bandhoehe_mm: Number(e.target.value) })} />
      </label>
      <Segmente label="Band auf" wert={b.band_seiten ?? "alle"} onWahl={(w) => aendere({ band_seiten: w })} className="self-start"
        werte={[{ wert: "alle", text: "jeder Seite" }, { wert: "erste", text: "nur der ersten Seite" }]} />
      <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked={!!b.logo_rechts} onChange={(e) => aendere({ logo_rechts: e.target.checked })} />Logo rechts, Absender links</label>
      {b.fussband ? <label className="flex items-center gap-2 text-[0.8438rem]"><input type="checkbox" checked onChange={() => aendere({ fussband: false })} />Fußband in derselben Farbe</label>
        : <span className="text-[0.75rem] gedaempft">Ein Band unten gestalten Sie beim Abschnitt „Fußzeile“.</span>}
    </div>
  );
}

/** Farbe aus Vorschlägen oder frei wählen */
function FarbWahl({ label, wert, onWert, vorschlaege }: { label: string; wert: string; onWert: (w: string) => void; vorschlaege: string[] }) {
  return (
    <div className="flex flex-col gap-1" role="group" aria-label={label}>
      <span className="text-[0.8125rem]">{label}</span>
      <div className="flex items-center gap-1.5 flex-wrap">
        {vorschlaege.map((f) => (
          <button key={f} type="button" aria-label={`${label} ${f}`} aria-pressed={wert.toUpperCase() === f} onClick={() => onWert(f)} title={f}
            className={cx("w-6 h-6 rounded-full border cursor-pointer p-0", wert.toUpperCase() === f ? "outline outline-2 outline-offset-1 outline-akzent border-transparent" : "border-rand")}
            style={{ background: f }} />
        ))}
        <input type="color" aria-label={`${label} wählen`} value={wert.toLowerCase()} onChange={(e) => onWert(e.target.value.toUpperCase())} />
      </div>
    </div>
  );
}

/** Form der Kante eines Bands (oben beim Fußband gespiegelt) */
function FormWahl({ wert, farbe, onWert, fuss }: { wert: string; farbe: string; onWert: (w: Bandform) => void; fuss?: boolean }) {
  return (
    <div className="flex flex-col gap-1" role="group" aria-label="Form des Bands">
      <span className="text-[0.8125rem]">{fuss ? "Form der Oberkante" : "Form der Unterkante"}</span>
      <div className="grid grid-cols-4 gap-1">
        {FORMEN.map((f) => (
          <button key={f.wert} type="button" aria-pressed={wert === f.wert} onClick={() => onWert(f.wert)}
            className={cx("flex flex-col items-center gap-0.5 p-1 rounded-md border text-[0.7188rem] cursor-pointer",
              wert === f.wert ? "border-akzent bg-akzent-weich text-akzent-text" : "border-rand bg-flaeche")}>
            <svg viewBox="0 0 210 50" className="w-full h-5" preserveAspectRatio="none" aria-hidden>
              <path fill={farbe} d={bandPfad(f.wert, 210, 40, 10)} transform={fuss ? "translate(0 50) scale(1 -1)" : undefined} /></svg>
            {f.text}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Fußzeile frei gestalten wie die Kopfzeile: eigenes Band, Farben, Zeilen für Vorstand und Bankverbindung */
function FusszeileWahl({ b, aendere, felder }: { b: Block; aendere: (n: Partial<Block>) => void; felder: Datenfeld[] }) {
  const text = b.text ?? "";
  const zeile = (feld: string, label: string) => {
    if (!felder.some((f) => f.name === feld)) return null;
    const muster = new RegExp(`\\{\\{\\s*${feld.replace(".", "\\.")}\\s*\\}\\}`);
    const an = muster.test(text);
    return (
      <label key={feld} className="flex items-center gap-2 text-[0.8438rem]">
        <input type="checkbox" checked={an} disabled={!an && text.split("\n").length >= 8}
          onChange={(e) => aendere({ text: e.target.checked ? `${text}${text ? "\n" : ""}${label}: {{${feld}}}`
            : text.split("\n").filter((z) => !muster.test(z)).join("\n") })} />Zeile „{label}“</label>
    );
  };
  return (
    <div className="flex flex-col gap-2.5" data-testid="fusszeile-wahl">
      <div className="flex flex-col gap-1.5">
        {zeile("Absender.Vorstand", "Vorstand")}
        {zeile("Absender.Bankverbindung", "Spendenkonto")}
        <span className="text-[0.75rem] gedaempft">Vorstand und Bankverbindung pflegen Sie zentral unter Vorlagen › Briefkopf und Logo.</span>
      </div>
      <Segmente label="Gestaltung der Fußzeile" wert={b.band ? "band" : "text"} className="self-start"
        onWahl={(w) => aendere(w === "band" ? { band: "welle", bandfarbe: b.bandfarbe ?? "#BDC9C2", textfarbe: b.textfarbe ?? "#23272C" } : { band: "" })}
        werte={[{ wert: "text", text: "Nur Text" }, { wert: "band", text: "Farbiges Band" }]} />
      {b.band ? <>
        <FormWahl wert={b.band} farbe={b.bandfarbe ?? "#BDC9C2"} onWert={(w) => aendere({ band: w })} fuss />
        <FarbWahl label="Farbe des Bands" wert={b.bandfarbe ?? "#BDC9C2"} onWert={(w) => aendere({ bandfarbe: w })} vorschlaege={BANDFARBEN} />
        <FarbWahl label="Schriftfarbe" wert={b.textfarbe ?? "#23272C"} onWert={(w) => aendere({ textfarbe: w })} vorschlaege={["#23272C", "#FFFFFF", "#251F53"]} />
      </> : null}
    </div>
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
