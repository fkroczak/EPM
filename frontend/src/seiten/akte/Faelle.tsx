/**
 * Fälle der Akte (Regeneration Clinic, Anforderung vom 26.10.2026): Ein Behandlungsfall ist die Datenquelle für alle
 * Dokumente des Falls. Beim Anlegen entsteht je Kostenträgertyp automatisch ein Dokumentenpaket (Erklärungen, OP-Bericht,
 * Entlassungsbrief, Rechnung …).
 *
 * Lebenslauf eines Dokuments: Entwurf → erzeugt → final. Solange es nicht final ist, ändert man Falldaten bzw.
 * Rechnungspositionen und erzeugt die PDF neu (jede Erzeugung ist eine neue Fassung, die alte bleibt abrufbar). Final
 * wird es durch Signatur, hochgeladene signierte PDF, Scan der Papierunterschrift oder ausdrückliche Finalisierung.
 * Finale Rechnungen werden nur noch storniert.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, eingabeDatum, eingabeZahl, zahl, zeitpunkt } from "@/lib/format";
import { FACHBEREICHE, FALL_SPRACHEN, FINAL_WEGE } from "@/lib/typen";
import type { DokumentFassung, Fall, FallDokument, FinalWeg, Kooperationspartner, Kostentraegertyp, Leistung, PaketOption,
  Rechnungsposition, Unterzeichner } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Knopf, Laden, Leer, Meldung, Segmente, Textfeld, cx }
  from "@/components/ui/basis";
import { Dialog, Menue } from "@/components/ui/dialog";
import type { MenuEintrag } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { PdfDialog } from "@/components/PdfDialog";
import { Bestaetigen } from "@/components/Bestaetigen";
import { ZertifikatDialog } from "@/components/ZertifikatDialog";
import { useAkte } from "./Akte";
import { Abschnitt, Aktenseite, Detail, Eintrag, Eintragsliste, useWahl } from "./Aktenseite";

// ------------------------------------------------------------------ Hilfen
export function geld(wert: number | string | null | undefined): string {
  if (wert === null || wert === undefined || wert === "") return "—";
  return `${zahl(wert, 2)} €`;
}

/** Zahl für ein Eingabefeld: 1.5 → „1,5“ */
function zahlText(wert: number | string | null | undefined): string {
  if (wert === null || wert === undefined || wert === "") return "";
  return String(wert).replace(".", ",");
}

/** Stammdaten des Moduls (Kostenträgertypen, Partner, Unterschriftsberechtigte, Paket-Optionen) */
export function useStamm<T>(pfad: string, aktiv = true) {
  return useQuery({ queryKey: ["faelle-stamm", pfad], queryFn: () => api<T>(pfad), enabled: aktiv, staleTime: 60_000 });
}

/** Nach jeder Änderung: Fälle, Dokumente, Positionen und Akte (Zähler, Dokumente-Reiter) neu laden */
function useNeuLaden() {
  const { patient } = useAkte();
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["faelle", patient.id] });
    void qc.invalidateQueries({ queryKey: ["falldokumente"] });
    void qc.invalidateQueries({ queryKey: ["positionen"] });
    void qc.invalidateQueries({ queryKey: ["fassungen"] });
    void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    void qc.invalidateQueries({ queryKey: ["dokumente", patient.id] });
  };
}

function FallStatusChip({ fall }: { fall: Fall }) {
  return <Chip art={fall.status === "offen" ? "akzent" : undefined} data-testid="fall-status">{fall.status_name}</Chip>;
}

export function DokStatusChip({ dok }: { dok: FallDokument }) {
  if (dok.storniert_am) return <Chip art="fehler" data-testid="dok-status">storniert</Chip>;
  const text = dok.status === "entwurf" ? "Entwurf" : dok.status === "erzeugt" ? "erzeugt" : "final";
  return <Chip art={dok.status === "final" ? "ok" : dok.status === "erzeugt" ? "akzent" : undefined}
    title={dok.status_name} data-testid="dok-status">{text}</Chip>;
}

function stand(f: Fall) {
  const s = f.dokumente_stand;
  return [s.final ? `${s.final} final` : "", s.erzeugt ? `${s.erzeugt} erzeugt` : "", s.entwurf ? `${s.entwurf} Entwurf` : ""]
    .filter(Boolean).join(", ") || "keine Dokumente";
}

// ------------------------------------------------------------------ Falldaten: Felder je Abschnitt
type FeldArt = "text" | "lang" | "datum" | "typ" | "partner" | "arzt" | "sprache" | "fachbereich";
type FeldDef = { name: keyof Fall; label: string; art?: FeldArt; hinweis?: string; max?: number; pflicht?: boolean };
type Bereich = "kostentraeger" | "behandlung" | "op" | "entlass" | "konsil";

const BEREICHE: Record<Bereich, { titel: string; felder: FeldDef[] }> = {
  kostentraeger: {
    titel: "Kostenträger und Partner",
    felder: [
      { name: "titel", label: "Titel des Falls", hinweis: "z. B. Knie-TEP rechts", max: 200 },
      { name: "kostentraegertyp", label: "Kostenträgertyp", art: "typ", pflicht: true,
        hinweis: "Bestimmt das Dokumentenpaket. Fehlende Dokumente ergänzt „Paket ergänzen“." },
      { name: "kostentraeger", label: "Kostenträger", hinweis: "z. B. AOK Bayern, ÖGK Wien", max: 200 },
      { name: "land", label: "Land des Kostenträgers", max: 80 },
      { name: "versichertennummer", label: "Versichertennummer", max: 50 },
      { name: "aktenzeichen", label: "Aktenzeichen / Genehmigung", max: 100 },
      { name: "kooperationspartner", label: "Kooperationspartner", art: "partner" },
      { name: "sprache", label: "Sprache der Dokumente", art: "sprache" },
      { name: "fachbereich", label: "Fachbereich", art: "fachbereich", hinweis: "Wählt den Zusatzbogen zur Aufklärung." },
      { name: "rechnungsempfaenger", label: "Rechnungsempfänger", art: "lang", hinweis: "Leer: der Patient mit Anschrift aus der Akte." },
    ],
  },
  behandlung: {
    titel: "Behandlung",
    felder: [
      { name: "aufnahme", label: "Aufnahme", art: "datum" },
      { name: "entlassung", label: "Entlassung", art: "datum" },
      { name: "op_datum", label: "OP-Datum", art: "datum" },
      { name: "behandelnder_arzt", label: "Behandelnder Arzt", art: "arzt" },
      { name: "eingriff", label: "Eingriff", max: 300 },
      { name: "diagnose", label: "Diagnose", art: "lang" },
      { name: "bemerkung", label: "Bemerkung (intern)", art: "lang" },
    ],
  },
  op: {
    titel: "OP-Bericht",
    felder: [
      { name: "operateur", label: "Operateur", max: 200 },
      { name: "assistenz", label: "Assistenz", max: 200 },
      { name: "anaesthesie", label: "Anästhesie", max: 200 },
      { name: "op_indikation", label: "Indikation", art: "lang" },
      { name: "op_verlauf", label: "OP-Verlauf", art: "lang" },
      { name: "op_befund", label: "Befund / Ergebnis", art: "lang" },
    ],
  },
  entlass: {
    titel: "Entlassungsbrief",
    felder: [
      { name: "entlass_verlauf", label: "Verlauf", art: "lang" },
      { name: "entlass_befunde", label: "Befunde", art: "lang" },
      { name: "entlass_medikation", label: "Medikation bei Entlassung", art: "lang" },
      { name: "entlass_empfehlung", label: "Empfehlung / Procedere", art: "lang" },
    ],
  },
  konsil: {
    titel: "Konsiliarbericht",
    felder: [
      { name: "konsil_empfaenger", label: "Konsil an", max: 300 },
      { name: "konsil_fragestellung", label: "Fragestellung", art: "lang" },
      { name: "konsil_befund", label: "Befund", art: "lang" },
      { name: "konsil_beurteilung", label: "Beurteilung / Empfehlung", art: "lang" },
    ],
  },
};

const NEU_FELDER: FeldDef[] = [
  BEREICHE.kostentraeger.felder[1], BEREICHE.kostentraeger.felder[0],
  { name: "fachbereich", label: "Fachbereich", art: "fachbereich", hinweis: "Wählt den Zusatzbogen zur Aufklärung." },
  { name: "sprache", label: "Sprache der Dokumente", art: "sprache" },
  { name: "kooperationspartner", label: "Kooperationspartner", art: "partner" },
  { name: "behandelnder_arzt", label: "Behandelnder Arzt", art: "arzt" },
  { name: "aufnahme", label: "Aufnahme", art: "datum" },
  { name: "op_datum", label: "OP-Datum", art: "datum" },
  { name: "eingriff", label: "Eingriff", max: 300 },
];

function anzeigeWert(f: Fall, d: FeldDef): string {
  const w = f[d.name];
  switch (d.art) {
    case "datum": return w ? datum(w as string) : "";
    case "typ": return f.kostentraegertyp_name;
    case "partner": return f.kooperationspartner_name ?? "";
    case "arzt": return f.behandelnder_arzt_name ?? "";
    case "sprache": return FALL_SPRACHEN[f.sprache] ?? f.sprache;
    case "fachbereich": return f.fachbereich ? FACHBEREICHE[f.fachbereich] : "";
    default: return w == null ? "" : String(w);
  }
}

function startWert(f: Fall | null, d: FeldDef): string {
  if (!f) return d.art === "sprache" ? "de" : "";
  const w = f[d.name];
  if (w === null || w === undefined) return "";
  return d.art === "datum" ? datum(w as string) : String(w);
}

// ------------------------------------------------------------------ Dialog: Fall anlegen / Abschnitt bearbeiten
function FallDialog({ fall, bereich, offen, onOffen, onGespeichert }: {
  fall: Fall | null; bereich: Bereich; offen: boolean; onOffen: (o: boolean) => void; onGespeichert: (f: Fall) => void;
}) {
  const { patient } = useAkte();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const felder = fall ? BEREICHE[bereich].felder : NEU_FELDER;
  const typen = useStamm<Kostentraegertyp[]>("kostentraegertypen/?aktiv=true", offen);
  const partner = useStamm<Kooperationspartner[]>("kooperationspartner/?aktiv=true", offen);
  const aerzte = useStamm<Unterzeichner[]>("unterzeichner/?aktiv=true", offen);
  const [werte, setWerte] = useState<Record<string, string>>({});
  const [anfang, setAnfang] = useState<Record<string, string>>({});
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${fall?.id ?? "neu"}-${bereich}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    const start = Object.fromEntries(felder.map((d) => [d.name, startWert(fall, d)]));
    setGesetzt(schluessel);
    setWerte(start);
    setAnfang(start);
  }
  if (!offen && gesetzt) setGesetzt("");
  const geaendert = felder.some((d) => (werte[d.name] ?? "") !== (anfang[d.name] ?? ""));

  const speichern = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {};
      const fehler: Feldfehler = {};
      for (const d of felder) {
        const w = (werte[d.name] ?? "").trim();
        if (fall && w === (anfang[d.name] ?? "").trim()) continue;   // nur Geändertes senden
        if (d.art === "datum") {
          const iso = w ? eingabeDatum(w) : null;
          if (w && !iso) fehler[d.name] = "Bitte als TT.MM.JJJJ eingeben.";
          body[d.name] = iso;
        } else if (d.art === "typ" || d.art === "partner" || d.art === "arzt") {
          body[d.name] = w ? Number(w) : null;
        } else {
          body[d.name] = d.art === "lang" ? (werte[d.name] ?? "") : w;
        }
      }
      if (Object.keys(fehler).length) throw new ApiFehler(400, "", null, fehler);
      return fall
        ? api<Fall>(`faelle/${fall.id}/`, { method: "PATCH", body })
        : api<Fall>("faelle/", { body: { ...body, patient: patient.id } });
    },
    onSuccess: (f) => {
      neuLaden();
      if (!fall) melden(`Fall ${f.nummer} angelegt. Das Dokumentenpaket steht bereit.`);
      else melden(f.dokumente_stand.erzeugt ? "Gespeichert. Erzeugte Dokumente bitte neu erzeugen." : "Gespeichert.");
      onGespeichert(f);
      onOffen(false);
    },
  });
  const fe: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const { reset } = speichern;
  useEffect(() => { if (offen) reset(); }, [offen, reset]);
  const setz = (name: string, wert: string) => setWerte((w) => ({ ...w, [name]: wert }));
  const bereit = !felder.some((d) => d.pflicht && !(werte[d.name] ?? "").trim());

  // Auswahl mit ausgeblendetem, aber gesetztem Eintrag: den aktuellen Wert trotzdem anbieten
  const mitAktuellem = <T extends { id: number; name: string }>(liste: T[] | undefined, id: number | null | undefined,
    name: string | null | undefined) =>
    id && !(liste ?? []).some((e) => e.id === id) ? [...(liste ?? []), { id, name: `${name ?? id} (ausgeblendet)` }] : liste ?? [];

  const eingabe = (d: FeldDef, p: { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string }): ReactNode => {
    const w = werte[d.name] ?? "";
    const auf = (e: { target: { value: string } }) => setz(d.name, e.target.value);
    switch (d.art) {
      case "lang":
        return <Textfeld {...p} rows={5} value={w} maxLength={20000} onChange={auf} className="font-[inherit] leading-snug" />;
      case "datum":
        return <Eingabe {...p} className="num" placeholder="TT.MM.JJJJ" value={w} onChange={auf} />;
      case "typ":
        return (
          <Auswahl {...p} value={w} onChange={auf}>
            <option value="">— bitte wählen —</option>
            {mitAktuellem(typen.data, fall?.kostentraegertyp, fall?.kostentraegertyp_name).map((t) =>
              <option key={t.id} value={t.id}>{t.name}</option>)}
          </Auswahl>
        );
      case "partner":
        return (
          <Auswahl {...p} value={w} onChange={auf}>
            <option value="">— keiner —</option>
            {mitAktuellem(partner.data, fall?.kooperationspartner, fall?.kooperationspartner_name).map((t) =>
              <option key={t.id} value={t.id}>{t.name}</option>)}
          </Auswahl>
        );
      case "arzt":
        return (
          <Auswahl {...p} value={w} onChange={auf}>
            <option value="">— nicht festgelegt —</option>
            {mitAktuellem(aerzte.data, fall?.behandelnder_arzt, fall?.behandelnder_arzt_name).map((t) =>
              <option key={t.id} value={t.id}>{t.name}</option>)}
          </Auswahl>
        );
      case "sprache":
        return (
          <Auswahl {...p} value={w} onChange={auf}>
            {Object.entries(FALL_SPRACHEN).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
          </Auswahl>
        );
      case "fachbereich":
        return (
          <Auswahl {...p} value={w} onChange={auf}>
            {Object.entries(FACHBEREICHE).map(([k, t]) => <option key={k} value={k}>{k ? t : "— keiner —"}</option>)}
          </Auswahl>
        );
      default:
        return <Eingabe {...p} value={w} maxLength={d.max} onChange={auf} />;
    }
  };

  return (
    <Dialog offen={offen} onOffen={onOffen} breite={780} geaendert={geaendert}
      titel={fall ? `${BEREICHE[bereich].titel} bearbeiten` : "Neuer Fall"}
      beschreibung={fall ? `Fall ${fall.nummer}. Bereits erzeugte Dokumente danach neu erzeugen.`
        : "Das Dokumentenpaket des Kostenträgertyps wird automatisch als Entwurf angelegt. Alle Angaben lassen sich später ergänzen."}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!bereit || (!!fall && !geaendert)}
          onClick={() => speichern.mutate()} data-testid="fall-speichern">{fall ? "Speichern" : "Fall anlegen"}</Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-2 min-w-0" data-testid="fall-formular">
        {felder.map((d) => (
          <Feld key={d.name} label={d.label} hinweis={d.hinweis} fehler={fe[d.name]} pflicht={d.pflicht}
            className={d.art === "lang" ? "sm:col-span-2" : undefined}>
            {(p) => eingabe(d, p)}
          </Feld>
        ))}
      </div>
      {speichern.error && !felder.some((d) => fe[d.name]) ? <Fehleranzeige fehler={speichern.error} /> : null}
    </Dialog>
  );
}

// ------------------------------------------------------------------ Falldaten anzeigen
function Falldaten({ fall, bearbeitbar, onBearbeiten }: { fall: Fall; bearbeitbar: boolean; onBearbeiten: (b: Bereich) => void }) {
  return (
    <div className="flex flex-col gap-4" data-testid="falldaten">
      {(Object.keys(BEREICHE) as Bereich[]).map((b) => (
        <Abschnitt key={b} titel={BEREICHE[b].titel}
          rechts={bearbeitbar ? <Knopf klein icon="stift" onClick={() => onBearbeiten(b)} data-testid={`fall-bearbeiten-${b}`}>Bearbeiten</Knopf> : undefined}>
          <dl className="m-0 grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm border-b border-rand pb-3">
            {BEREICHE[b].felder.map((d) => {
              const w = anzeigeWert(fall, d);
              return (
                <div key={d.name} className="contents">
                  <dt className="gedaempft">{d.label}</dt>
                  <dd className={cx("m-0 break-words", d.art === "lang" && "whitespace-pre-wrap leading-relaxed", !w && "gedaempft")}>{w || "—"}</dd>
                </div>
              );
            })}
          </dl>
        </Abschnitt>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ Dokument-Dialoge
function ErzeugenDialog({ dok, offen, onOffen }: { dok: FallDokument | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [grund, setGrund] = useState("");
  const erzeugen = useMutation({
    mutationFn: () => api<FallDokument>(`falldokumente/${dok!.id}/erzeugen/`, { body: { grund: grund.trim() } }),
    onSuccess: (d) => {
      neuLaden();
      melden(`Fassung ${d.letzte_version?.nummer ?? ""} erzeugt.`.replace("  ", " "));
      onOffen(false);
    },
  });
  const { reset } = erzeugen;
  useEffect(() => { if (offen) { reset(); setGrund(""); } }, [offen, reset]);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="PDF neu erzeugen" beschreibung={dok?.titel}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={erzeugen.isPending} onClick={() => erzeugen.mutate()} data-testid="erzeugen-bestaetigen">Neu erzeugen</Knopf>
      </>}>
      <Feld label="Grund (freiwillig)" hinweis="z. B. „Diagnose ergänzt“ – steht bei der Fassung.">
        {(p) => <Eingabe {...p} value={grund} maxLength={300} onChange={(e) => setGrund(e.target.value)} autoFocus />}
      </Feld>
      <Meldung art="info">Es entsteht eine neue Fassung aus den aktuellen Falldaten. Die bisherigen Fassungen bleiben abrufbar.</Meldung>
      <Fehleranzeige fehler={erzeugen.error} />
    </Dialog>
  );
}

function FassungenDialog({ dok, offen, onOffen }: { dok: FallDokument | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const [pdf, setPdf] = useState<DokumentFassung | null>(null);
  const liste = useQuery({
    queryKey: ["fassungen", dok?.id],
    queryFn: () => api<DokumentFassung[]>(`falldokumente/${dok!.id}/versionen/`),
    enabled: offen && !!dok,
    staleTime: 0,
  });
  const url = (v: DokumentFassung) => `/api/falldokumente/${dok!.id}/pdf/?fassung=${v.nummer}`;
  return (
    <>
      <Dialog offen={offen} onOffen={onOffen} titel="Fassungen" beschreibung={dok?.titel} breite={680}
        fuss={<Knopf onClick={() => onOffen(false)}>Schließen</Knopf>}>
        {liste.isLoading ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
        {liste.data && !liste.data.length ? <Leer>Noch keine Fassung erzeugt.</Leer> : null}
        <ol className="m-0 p-0 list-none flex flex-col gap-2.5" data-testid="fassungen">
          {(liste.data ?? []).map((v) => (
            <li key={v.id} className="border-b border-rand pb-2 last:border-0 flex items-start justify-between gap-3 flex-wrap min-w-0">
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="text-sm font-medium flex items-center gap-2 flex-wrap">
                  Fassung {v.nummer} · {v.art_name}{v.final ? <Chip art="ok">final</Chip> : null}
                </span>
                <span className="text-[0.8125rem] gedaempft num">{zeitpunkt(v.erzeugt_am)}{v.erzeugt_von_name ? ` · ${v.erzeugt_von_name}` : ""}</span>
                {v.grund ? <span className="text-[0.8125rem] break-words">{v.grund}</span> : null}
                <span className="text-xs gedaempft num truncate" title={v.sha256}>SHA-256 {v.sha256.slice(0, 12)}…</span>
              </div>
              {v.mime === "application/pdf"
                ? <Knopf klein icon="dokument" onClick={() => setPdf(v)} data-testid="fassung-oeffnen">Öffnen</Knopf>
                : <a className="btn sec klein" href={url(v)} target="_blank" rel="noreferrer"><span>Öffnen</span></a>}
            </li>
          ))}
        </ol>
      </Dialog>
      <PdfDialog offen={!!pdf && !!dok} onOffen={(o) => { if (!o) setPdf(null); }}
        titel={dok && pdf ? `${dok.titel} · Fassung ${pdf.nummer}` : "Fassung"}
        pfad={dok && pdf ? `falldokumente/${dok.id}/pdf/?fassung=${pdf.nummer}` : ""}
        dateiname={`${dok?.titel ?? "Dokument"}-${patient.nummer}-Fassung-${pdf?.nummer ?? ""}.pdf`} />
    </>
  );
}

function FinalisierenDialog({ dok, offen, onOffen }: { dok: FallDokument | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { ich } = useAuth();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const personen = useStamm<Unterzeichner[]>("unterzeichner/?aktiv=true", offen);
  const [weg, setWeg] = useState<FinalWeg | "">("");
  const [person, setPerson] = useState("");
  const [kennwort, setKennwort] = useState("");
  const [datei, setDatei] = useState<File | null>(null);
  const [notiz, setNotiz] = useState("");
  const [zertifikat, setZertifikat] = useState(false);
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${dok?.id ?? ""}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setWeg(""); setPerson(dok?.unterzeichner ? String(dok.unterzeichner) : ""); setKennwort(""); setDatei(null); setNotiz("");
  }
  if (!offen && gesetzt) setGesetzt("");
  const alle = personen.data ?? [];
  const eigene = alle.filter((u) => u.benutzer === ich?.id);
  const auswahl = weg === "signatur" ? eigene : alle;
  const gewaehlt = alle.find((u) => String(u.id) === person);
  // Signatur: nur die eigene Person; ist genau eine verknüpft, gleich vorbelegen
  useEffect(() => {
    if (weg === "signatur" && eigene.length && !eigene.some((u) => String(u.id) === person)) setPerson(String(eigene[0].id));
  }, [weg, eigene, person]);
  const veraltetSperrt = !!dok?.veraltet && (weg === "signatur" || weg === "finalisiert");
  const mitDatei = weg === "signatur_extern" || weg === "scan";
  const bereit = !!weg && !veraltetSperrt
    && (weg !== "signatur" || (!!gewaehlt && gewaehlt.benutzer === ich?.id && gewaehlt.hat_zertifikat && !!kennwort))
    && (!mitDatei || !!datei) && (weg !== "scan" || !!person);

  const senden = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("weg", weg);
      if (person) form.append("unterzeichner", person);
      if (weg === "signatur") form.append("kennwort", kennwort);
      if (mitDatei && datei) form.append("datei", datei);
      if (notiz.trim()) form.append("notiz", notiz.trim());
      return api<FallDokument>(`falldokumente/${dok!.id}/finalisieren/`, { form });
    },
    onSuccess: (d) => {
      neuLaden();
      melden(`„${d.titel}“ ist final. Die PDF liegt in den Dokumenten der Akte.`);
      onOffen(false);
    },
  });
  const f: Feldfehler = senden.error instanceof ApiFehler ? senden.error.felder : {};
  const { reset } = senden;
  useEffect(() => { if (offen) reset(); }, [offen, reset]);

  return (
    <>
      <Dialog offen={offen} onOffen={onOffen} titel="Dokument finalisieren" beschreibung={dok?.titel} breite={620}
        fuss={<>
          <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
          <Knopf variante="pri" icon="haken" laedt={senden.isPending} disabled={!bereit} onClick={() => senden.mutate()}
            data-testid="finalisieren-bestaetigen">{weg === "signatur" ? "Signieren" : "Finalisieren"}</Knopf>
        </>}>
        <div className="flex flex-col gap-3.5 min-w-0" data-testid="finalisieren-dialog">
          <fieldset className="m-0 p-0 border-0 flex flex-col gap-2">
            <legend className="text-[0.8125rem] font-medium mb-1">Wie wird das Dokument final?</legend>
            {(Object.keys(FINAL_WEGE) as FinalWeg[]).map((w) => (
              <label key={w} className={cx("card px-3 py-2 flex items-start gap-2.5 cursor-pointer border", weg === w ? "border-akzent bg-akzent-weich" : "hover:bg-fein")}>
                <input type="radio" name="final-weg" className="mt-1" checked={weg === w} onChange={() => setWeg(w)} data-testid={`weg-${w}`} />
                <span className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium">{FINAL_WEGE[w].name}</span>
                  <span className="text-[0.8125rem] gedaempft">{FINAL_WEGE[w].text}</span>
                </span>
              </label>
            ))}
            {f.weg ? <span className="fehlertext" role="alert">{f.weg}</span> : null}
          </fieldset>
          {veraltetSperrt ? (
            <Meldung art="warn">Die Falldaten wurden nach der letzten Erzeugung geändert. Bitte zuerst die PDF neu erzeugen.</Meldung>
          ) : dok?.veraltet && mitDatei ? (
            <Meldung art="warn">Achtung: Die Falldaten wurden nach der letzten Erzeugung geändert. Die hochgeladene Datei gilt so, wie sie ist.</Meldung>
          ) : null}
          {weg ? <>
            {weg === "signatur" && personen.isSuccess && !eigene.length ? (
              <Meldung art="warn">Ihr Benutzerkonto ist mit keiner unterschriftsberechtigten Person verknüpft. Signieren kann nur die
                Person selbst. Bitte die Verwaltung (Fälle und Abrechnung) ansprechen oder einen anderen Weg wählen.</Meldung>
            ) : (
              <Feld label="Unterschriftsberechtigte Person" fehler={f.unterzeichner} pflicht={weg === "signatur" || weg === "scan"}
                hinweis={weg === "signatur_extern" || weg === "finalisiert" ? "freiwillig" : undefined}>
                {(p) => (
                  <Auswahl {...p} value={person} onChange={(e) => setPerson(e.target.value)} data-testid="final-unterzeichner">
                    <option value="">{weg === "signatur" || weg === "scan" ? "— bitte wählen —" : "— keine Angabe —"}</option>
                    {auswahl.map((u) => <option key={u.id} value={u.id}>{u.name}{u.funktion ? ` (${u.funktion})` : ""}</option>)}
                  </Auswahl>
                )}
              </Feld>
            )}
            {weg === "signatur" && gewaehlt && gewaehlt.benutzer === ich?.id ? (
              gewaehlt.hat_zertifikat ? <>
                <p className="m-0 text-[0.8125rem] gedaempft break-words">Zertifikat: {gewaehlt.zertifikat_info || "hinterlegt"}
                  {gewaehlt.zertifikat_bis ? ` · gültig bis ${datum(gewaehlt.zertifikat_bis)}` : ""}</p>
                <Feld label="Kennwort des Zertifikats" fehler={f.kennwort} pflicht>
                  {(p) => <Eingabe {...p} type="password" autoComplete="off" value={kennwort} onChange={(e) => setKennwort(e.target.value)}
                    data-testid="final-kennwort" />}
                </Feld>
                {gewaehlt.id !== dok?.unterzeichner && dok?.unterzeichner ? (
                  <Meldung art="info">Auf der PDF steht bisher {dok.unterzeichner_name}. Sie wird mit Ihrem Namen neu erzeugt und dann signiert.</Meldung>
                ) : null}
              </> : (
                <Meldung art="warn">
                  <span className="flex items-center justify-between gap-3 flex-wrap">
                    <span>Für Sie ist noch kein Zertifikat hinterlegt.</span>
                    <Knopf klein icon="hochladen" onClick={() => setZertifikat(true)}>Zertifikat hinterlegen</Knopf>
                  </span>
                </Meldung>
              )
            ) : null}
            {mitDatei ? (
              <Feld label={weg === "scan" ? "Scan (PDF, JPG oder PNG, höchstens 25 MB)" : "Signierte PDF (höchstens 25 MB)"} fehler={f.datei} pflicht>
                {(p) => <input {...p} type="file" className="text-sm" data-testid="final-datei"
                  accept={weg === "scan" ? ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" : ".pdf,application/pdf"}
                  onChange={(e) => setDatei(e.target.files?.[0] ?? null)} />}
              </Feld>
            ) : null}
            <Feld label="Notiz (freiwillig)" fehler={f.notiz} hinweis="Steht bei der finalen Fassung.">
              {(p) => <Eingabe {...p} value={notiz} maxLength={300} onChange={(e) => setNotiz(e.target.value)} />}
            </Feld>
            <Meldung art="warn">Danach ist das Dokument unveränderlich.{dok?.art === "rechnung" ? " Eine finale Rechnung lässt sich nur noch stornieren." : ""}</Meldung>
          </> : null}
          {senden.error && !Object.keys(f).length ? <Fehleranzeige fehler={senden.error} /> : null}
        </div>
      </Dialog>
      <ZertifikatDialog person={gewaehlt ?? null} offen={zertifikat && !!gewaehlt} onOffen={setZertifikat} />
    </>
  );
}

function StornierenDialog({ dok, offen, onOffen }: { dok: FallDokument | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [grund, setGrund] = useState("");
  const [neu, setNeu] = useState(true);
  const stornieren = useMutation({
    mutationFn: () => api<{ rechnung: FallDokument; storno: FallDokument; neu: FallDokument | null }>(
      `falldokumente/${dok!.id}/stornieren/`, { body: { grund: grund.trim(), neue_rechnung: neu } }),
    onSuccess: (r) => {
      neuLaden();
      melden(`Rechnung storniert. Stornorechnung ${r.storno.rechnungsnummer ?? ""} erzeugt${r.neu ? ", neue Rechnung als Entwurf angelegt" : ""}.`);
      onOffen(false);
    },
  });
  const f: Feldfehler = stornieren.error instanceof ApiFehler ? stornieren.error.felder : {};
  const { reset } = stornieren;
  useEffect(() => { if (offen) { reset(); setGrund(""); setNeu(true); } }, [offen, reset]);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Rechnung stornieren"
      beschreibung={dok ? `${dok.titel}${dok.rechnungsnummer ? ` ${dok.rechnungsnummer}` : ""} · ${geld(dok.summe)}` : undefined}
      fuss={<>
        <Knopf variante="dng" laedt={stornieren.isPending} disabled={!grund.trim()} onClick={() => stornieren.mutate()}
          data-testid="stornieren-bestaetigen">Stornieren</Knopf>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
      </>}>
      <div className="flex flex-col gap-3" data-testid="stornieren-dialog">
        <Feld label="Grund" fehler={f.storno_grund || f.grund} pflicht hinweis="Steht auf der Stornorechnung.">
          {(p) => <Eingabe {...p} value={grund} maxLength={300} onChange={(e) => setGrund(e.target.value)} autoFocus />}
        </Feld>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={neu} onChange={(e) => setNeu(e.target.checked)} data-testid="neue-rechnung" />
          Neue Rechnung als Entwurf anlegen (mit denselben Positionen zur Korrektur)
        </label>
        <Meldung art="warn">Es entsteht sofort eine Stornorechnung mit negativen Beträgen. Die Rechnung bleibt erhalten und wird als storniert markiert.</Meldung>
        {stornieren.error && !f.storno_grund && !f.grund ? <Fehleranzeige fehler={stornieren.error} /> : null}
      </div>
    </Dialog>
  );
}

function DokumentBearbeiten({ dok, offen, onOffen }: { dok: FallDokument | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const personen = useStamm<Unterzeichner[]>("unterzeichner/?aktiv=true", offen);
  const [w, setW] = useState({ titel: "", freitext: "", unterzeichner: "", rechnungsdatum: "", zahlungsziel_tage: "" });
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${dok?.id ?? ""}-${offen}`;
  if (offen && dok && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setW({ titel: dok.titel, freitext: dok.freitext, unterzeichner: dok.unterzeichner ? String(dok.unterzeichner) : "",
      rechnungsdatum: dok.rechnungsdatum ? datum(dok.rechnungsdatum) : "", zahlungsziel_tage: String(dok.zahlungsziel_tage ?? "") });
  }
  if (!offen && gesetzt) setGesetzt("");
  const rechnung = dok?.art === "rechnung" || dok?.art === "storno";
  const speichern = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { titel: w.titel.trim(), freitext: w.freitext,
        unterzeichner: w.unterzeichner ? Number(w.unterzeichner) : null };
      if (rechnung) {
        const iso = w.rechnungsdatum.trim() ? eingabeDatum(w.rechnungsdatum) : null;
        if (w.rechnungsdatum.trim() && !iso) throw new ApiFehler(400, "", null, { rechnungsdatum: "Bitte als TT.MM.JJJJ eingeben." });
        body.rechnungsdatum = iso;
        if (!/^\d{1,3}$/.test(w.zahlungsziel_tage.trim())) throw new ApiFehler(400, "", null, { zahlungsziel_tage: "Bitte die Zahl der Tage angeben." });
        body.zahlungsziel_tage = Number(w.zahlungsziel_tage);
      }
      return api<FallDokument>(`falldokumente/${dok!.id}/`, { method: "PATCH", body });
    },
    onSuccess: () => { neuLaden(); melden("Gespeichert."); onOffen(false); },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const { reset } = speichern;
  useEffect(() => { if (offen) reset(); }, [offen, reset]);
  const setz = (k: keyof typeof w) => (e: { target: { value: string } }) => setW((a) => ({ ...a, [k]: e.target.value }));
  const aktuell = dok?.unterzeichner && !(personen.data ?? []).some((u) => u.id === dok.unterzeichner);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Dokument bearbeiten" beschreibung={dok?.art_name} breite={640}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!w.titel.trim()} onClick={() => speichern.mutate()}
          data-testid="dokument-speichern">Speichern</Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-2 min-w-0" data-testid="dokument-formular">
        <Feld label="Titel" fehler={f.titel} pflicht className="sm:col-span-2">
          {(p) => <Eingabe {...p} value={w.titel} maxLength={200} onChange={setz("titel")} />}
        </Feld>
        <Feld label="Unterschrift" fehler={f.unterzeichner} className="sm:col-span-2" hinweis="Wer auf dem Dokument unterschreibt.">
          {(p) => (
            <Auswahl {...p} value={w.unterzeichner} onChange={setz("unterzeichner")}>
              <option value="">— nicht festgelegt —</option>
              {aktuell && dok ? <option value={dok.unterzeichner!}>{dok.unterzeichner_name} (ausgeblendet)</option> : null}
              {(personen.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.name}{u.funktion ? ` (${u.funktion})` : ""}</option>)}
            </Auswahl>
          )}
        </Feld>
        {rechnung ? <>
          <Feld label="Rechnungsdatum" fehler={f.rechnungsdatum} hinweis="Leer: Tag der Erzeugung.">
            {(p) => <Eingabe {...p} className="num" placeholder="TT.MM.JJJJ" value={w.rechnungsdatum} onChange={setz("rechnungsdatum")} />}
          </Feld>
          <Feld label="Zahlungsziel in Tagen" fehler={f.zahlungsziel_tage}>
            {(p) => <Eingabe {...p} className="num" inputMode="numeric" maxLength={3} value={w.zahlungsziel_tage}
              onChange={(e) => setW((a) => ({ ...a, zahlungsziel_tage: e.target.value.replace(/\D/g, "") }))} />}
          </Feld>
        </> : null}
        <Feld label="Zusätzlicher Text" fehler={f.freitext} className="sm:col-span-2"
          hinweis={rechnung ? "z. B. Hinweis auf der Rechnung." : "Erscheint zusätzlich auf dem Dokument."}>
          {(p) => <Textfeld {...p} rows={5} value={w.freitext} maxLength={20000} onChange={setz("freitext")} className="font-[inherit] leading-snug" />}
        </Feld>
      </div>
      {speichern.error && !Object.keys(f).length ? <Fehleranzeige fehler={speichern.error} /> : null}
    </Dialog>
  );
}

const FESTE_ARTEN: { wert: string; text: string }[] = [
  { wert: "op_bericht", text: "OP-Bericht" }, { wert: "entlassbrief", text: "Entlassungsbrief" },
  { wert: "konsil", text: "Konsiliarbericht" }, { wert: "rechnung", text: "Rechnung" },
];

function DokumentNeu({ fall, offen, onOffen }: { fall: Fall; offen: boolean; onOffen: (o: boolean) => void }) {
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const optionen = useStamm<PaketOption[]>("kostentraegertypen/optionen/", offen);
  const [wahl, setWahl] = useState("");
  const vorlagen = (optionen.data ?? []).filter((o) => o.wert.startsWith("eigen-"));
  const gruppen = [...new Set(vorlagen.map((o) => o.gruppe))];
  const anlegen = useMutation({
    mutationFn: () => api<FallDokument>("falldokumente/", {
      body: wahl.startsWith("eigen-") ? { fall: fall.id, art: "vorlage", vorlage: wahl } : { fall: fall.id, art: wahl } }),
    onSuccess: (d) => { neuLaden(); melden(`„${d.titel}“ als Entwurf angelegt.`); onOffen(false); },
  });
  const { reset } = anlegen;
  useEffect(() => { if (offen) { reset(); setWahl(""); } }, [offen, reset]);
  const f: Feldfehler = anlegen.error instanceof ApiFehler ? anlegen.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Dokument hinzufügen" beschreibung={`Fall ${fall.nummer}`}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={anlegen.isPending} disabled={!wahl} onClick={() => anlegen.mutate()} data-testid="dokument-anlegen">Hinzufügen</Knopf>
      </>}>
      <Feld label="Dokument" fehler={f.art || f.vorlage} pflicht>
        {(p) => (
          <Auswahl {...p} value={wahl} onChange={(e) => setWahl(e.target.value)} data-testid="dokument-art">
            <option value="">— bitte wählen —</option>
            <optgroup label="Dokumente des Falls">
              {FESTE_ARTEN.map((a) => <option key={a.wert} value={a.wert}>{a.text}</option>)}
            </optgroup>
            {gruppen.map((g) => (
              <optgroup key={g} label={g}>
                {vorlagen.filter((o) => o.gruppe === g).map((o) => <option key={o.wert} value={o.wert}>{o.name}</option>)}
              </optgroup>
            ))}
          </Auswahl>
        )}
      </Feld>
      {anlegen.error && !f.art && !f.vorlage ? <Fehleranzeige fehler={anlegen.error} /> : null}
    </Dialog>
  );
}

// ------------------------------------------------------------------ Rechnungspositionen
function PositionDialog({ dok, position, offen, onOffen }: {
  dok: FallDokument; position: Rechnungsposition | null; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const leer = { code: "", text: "", datum: "", menge: "1", einheit: "", einzelpreis: "", ust_satz: "0" };
  const [w, setW] = useState(leer);
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${position?.id ?? "neu"}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setW(position ? { code: position.code, text: position.text, datum: position.datum ? datum(position.datum) : "",
      menge: zahlText(position.menge), einheit: position.einheit, einzelpreis: zahlText(position.einzelpreis),
      ust_satz: zahlText(position.ust_satz) } : leer);
  }
  if (!offen && gesetzt) setGesetzt("");
  const speichern = useMutation({
    mutationFn: () => {
      const fehler: Feldfehler = {};
      const iso = w.datum.trim() ? eingabeDatum(w.datum) : null;
      if (w.datum.trim() && !iso) fehler.datum = "Bitte als TT.MM.JJJJ eingeben.";
      const menge = eingabeZahl(w.menge), preis = eingabeZahl(w.einzelpreis), ust = eingabeZahl(w.ust_satz || "0");
      if (!menge || menge === "ungueltig") fehler.menge = "Bitte eine Zahl angeben.";
      if (!preis || preis === "ungueltig") fehler.einzelpreis = "Bitte einen Preis angeben.";
      if (!ust || ust === "ungueltig") fehler.ust_satz = "Bitte eine Zahl angeben.";
      if (Object.keys(fehler).length) throw new ApiFehler(400, "", null, fehler);
      const body = { code: w.code.trim(), text: w.text.trim(), datum: iso, menge, einheit: w.einheit.trim(), einzelpreis: preis, ust_satz: ust };
      return position
        ? api<Rechnungsposition>(`rechnungspositionen/${position.id}/`, { method: "PATCH", body })
        : api<Rechnungsposition>("rechnungspositionen/", { body: { ...body, dokument: dok.id } });
    },
    onSuccess: () => { neuLaden(); melden(position ? "Position geändert." : "Position hinzugefügt."); onOffen(false); },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const { reset } = speichern;
  useEffect(() => { if (offen) reset(); }, [offen, reset]);
  const setz = (k: keyof typeof w) => (e: { target: { value: string } }) => setW((a) => ({ ...a, [k]: e.target.value }));
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={position ? "Position bearbeiten" : "Freie Position"} beschreibung={dok.titel} breite={640}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!w.text.trim()} onClick={() => speichern.mutate()}
          data-testid="position-speichern">Speichern</Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-3 min-w-0" data-testid="position-formular">
        <Feld label="Code" fehler={f.code}>{(p) => <Eingabe {...p} value={w.code} maxLength={30} onChange={setz("code")} />}</Feld>
        <Feld label="Leistungsdatum" fehler={f.datum}>
          {(p) => <Eingabe {...p} className="num" placeholder="TT.MM.JJJJ" value={w.datum} onChange={setz("datum")} />}
        </Feld>
        <div className="max-sm:hidden" />
        <Feld label="Text" fehler={f.text} pflicht className="sm:col-span-3">
          {(p) => <Eingabe {...p} value={w.text} maxLength={500} onChange={setz("text")} autoFocus={!position} />}
        </Feld>
        <Feld label="Menge" fehler={f.menge} pflicht>
          {(p) => <Eingabe {...p} className="num" inputMode="decimal" value={w.menge} onChange={setz("menge")} />}
        </Feld>
        <Feld label="Einheit" fehler={f.einheit}>{(p) => <Eingabe {...p} value={w.einheit} maxLength={30} onChange={setz("einheit")} />}</Feld>
        <Feld label="Einzelpreis (EUR)" fehler={f.einzelpreis} pflicht>
          {(p) => <Eingabe {...p} className="num" inputMode="decimal" value={w.einzelpreis} onChange={setz("einzelpreis")} />}
        </Feld>
        <Feld label="USt. %" fehler={f.ust_satz} hinweis="0 bei Heilbehandlung">
          {(p) => <Eingabe {...p} className="num" inputMode="decimal" value={w.ust_satz} onChange={setz("ust_satz")} />}
        </Feld>
      </div>
      {speichern.error && !Object.keys(f).length ? <Fehleranzeige fehler={speichern.error} /> : null}
    </Dialog>
  );
}

function Positionen({ dok, bearbeitbar }: { dok: FallDokument; bearbeitbar: boolean }) {
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [suche, setSuche] = useState("");
  const [dialog, setDialog] = useState<{ offen: boolean; position: Rechnungsposition | null }>({ offen: false, position: null });
  const [entfernen, setEntfernen] = useState<Rechnungsposition | null>(null);
  const liste = useQuery({
    queryKey: ["positionen", dok.id],
    queryFn: () => api<Rechnungsposition[]>(`rechnungspositionen/?dokument=${dok.id}`),
  });
  const begriff = suche.trim();
  const treffer = useQuery({
    queryKey: ["faelle-stamm", "leistungen-suche", begriff],
    queryFn: () => api<Leistung[]>(`leistungen/${abfrage({ aktiv: "true", search: begriff })}`),
    enabled: bearbeitbar && begriff.length >= 2,
  });
  const aufnehmen = useMutation({
    mutationFn: (l: Leistung) => api<Rechnungsposition>("rechnungspositionen/", { body: { dokument: dok.id, leistung: l.id } }),
    onSuccess: (p) => { neuLaden(); setSuche(""); melden(`„${p.text}“ hinzugefügt.`); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const loeschen = useMutation({
    mutationFn: (p: Rechnungsposition) => api(`rechnungspositionen/${p.id}/`, { method: "DELETE" }),
    onSuccess: () => { neuLaden(); setEntfernen(null); melden("Position entfernt."); },
  });
  const positionen = liste.data ?? [];
  const netto = positionen.reduce((s, p) => s + Number(p.betrag || 0), 0);
  const mitUst = positionen.some((p) => Number(p.ust_satz) > 0);

  return (
    <div className="flex flex-col gap-2.5 min-w-0" data-testid="positionen">
      {bearbeitbar ? (
        <div className="flex items-start gap-2 flex-wrap">
          <div className="relative grow min-w-[14rem] max-w-[28rem]">
            <Eingabe type="search" aria-label="Leistung im Katalog suchen" placeholder="Leistung suchen (Code oder Bezeichnung) …"
              value={suche} onChange={(e) => setSuche(e.target.value)} data-testid="leistung-suche" />
            {begriff.length >= 2 ? (
              <div className="card absolute z-20 left-0 right-0 mt-1 p-1 max-h-[18rem] overflow-y-auto flex flex-col" role="listbox"
                aria-label="Treffer im Leistungskatalog" data-testid="leistung-treffer">
                {treffer.isFetching && !treffer.data ? <Laden text="Suche …" /> : null}
                {treffer.data && !treffer.data.length ? <Leer>Keine Leistung gefunden.</Leer> : null}
                {(treffer.data ?? []).slice(0, 12).map((l) => (
                  <button key={l.id} type="button" role="option" aria-selected="false" disabled={aufnehmen.isPending}
                    className="text-left bg-transparent border-0 rounded-md px-2.5 py-1.5 cursor-pointer text-sm hover:bg-fein flex justify-between gap-3"
                    onClick={() => aufnehmen.mutate(l)}>
                    <span className="min-w-0"><span className="num gedaempft mr-2">{l.code}</span>{l.bezeichnung}</span>
                    <span className="num shrink-0">{geld(l.preis)}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          <Knopf icon="plus" onClick={() => setDialog({ offen: true, position: null })} data-testid="position-frei">Freie Position</Knopf>
        </div>
      ) : null}
      {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
      {liste.isSuccess && !positionen.length ? <Leer>Noch keine Positionen.{bearbeitbar ? " Leistung suchen oder eine freie Position anlegen." : ""}</Leer> : null}
      {positionen.length ? (
        <div className="overflow-x-auto">
          <table className="tabelle w-full text-sm" data-testid="positionen-tabelle">
            <thead>
              <tr><th className="num">Pos.</th><th>Code</th><th>Text</th><th>Datum</th><th className="num">Menge</th><th>Einheit</th>
                <th className="num">Einzelpreis</th>{mitUst ? <th className="num">USt.</th> : null}<th className="num">Betrag</th>{bearbeitbar ? <th /> : null}</tr>
            </thead>
            <tbody>
              {positionen.map((p, i) => (
                <tr key={p.id}>
                  <td className="num">{i + 1}</td>
                  <td className="num whitespace-nowrap">{p.code || "—"}</td>
                  <td className="break-words min-w-[12rem]">{p.text}</td>
                  <td className="num whitespace-nowrap">{p.datum ? datum(p.datum) : "—"}</td>
                  <td className="num">{zahl(p.menge)}</td>
                  <td>{p.einheit || "—"}</td>
                  <td className="num whitespace-nowrap">{geld(p.einzelpreis)}</td>
                  {mitUst ? <td className="num">{zahl(p.ust_satz)} %</td> : null}
                  <td className="num whitespace-nowrap">{geld(p.betrag)}</td>
                  {bearbeitbar ? (
                    <td className="text-right whitespace-nowrap">
                      <Knopf klein onClick={() => setDialog({ offen: true, position: p })}>Bearbeiten</Knopf>{" "}
                      <Knopf klein variante="geist" aria-label={`Position ${i + 1} entfernen`} title="Entfernen" icon="x"
                        onClick={() => { loeschen.reset(); setEntfernen(p); }} />
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
            <tfoot>
              {mitUst ? (
                <tr><td colSpan={mitUst ? 8 : 7} className="text-right gedaempft">Netto</td><td className="num whitespace-nowrap">{geld(netto)}</td>{bearbeitbar ? <td /> : null}</tr>
              ) : null}
              <tr className="font-semibold">
                <td colSpan={mitUst ? 8 : 7} className="text-right pr-3">Summe</td>
                <td className="num whitespace-nowrap" data-testid="positionen-summe">{geld(dok.summe ?? netto)}</td>{bearbeitbar ? <td /> : null}
              </tr>
            </tfoot>
          </table>
        </div>
      ) : null}
      {bearbeitbar ? <>
        <PositionDialog dok={dok} position={dialog.position} offen={dialog.offen} onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} />
        <Bestaetigen offen={!!entfernen} onOffen={(o) => { if (!o) setEntfernen(null); }} titel="Position entfernen" knopf="Entfernen"
          text={<>„{entfernen?.text}“ wird von der Rechnung entfernt.</>} laedt={loeschen.isPending} fehler={loeschen.error}
          onJa={() => entfernen && loeschen.mutate(entfernen)} />
      </> : null}
    </div>
  );
}

// ------------------------------------------------------------------ Dokumente des Falls
type DokDialog = "" | "vorschau" | "pdf" | "erzeugen" | "fassungen" | "finalisieren" | "stornieren" | "bearbeiten" | "loeschen";

function DokumentZeile({ dok, bearbeitbar, finalisieren, stornieren, positionenOffen, onPositionen, onDialog, onErzeugen, erzeugtGerade, onDocxHoch }: {
  dok: FallDokument; bearbeitbar: boolean; finalisieren: boolean; stornieren: boolean; positionenOffen: boolean; onPositionen: () => void;
  onDialog: (d: DokDialog) => void; onErzeugen: () => void; erzeugtGerade: boolean; onDocxHoch: () => void;
}) {
  const offen = dok.status !== "final";
  const rechnung = dok.art === "rechnung" || dok.art === "storno";
  const lv = dok.letzte_version;
  const menue: MenuEintrag[] = [
    ...(dok.versionen_anzahl ? [{ text: `Fassungen ansehen (${dok.versionen_anzahl})`, onClick: () => onDialog("fassungen") }] : []),
    ...(dok.versionen_anzahl ? [{ text: "Letzte Fassung öffnen", onClick: () => onDialog("pdf") }] : []),
    ...(bearbeitbar && offen ? [{ text: "Titel, Unterschrift, Text …", onClick: () => onDialog("bearbeiten") }] : []),
    ...(dok.hat_docx ? [{ text: "DOCX herunterladen", hinweis: "Freitexte in Word bearbeiten", onClick: () => {
      const a = document.createElement("a");
      a.href = `/api/falldokumente/${dok.id}/docx/`;
      a.download = "";
      a.click();
    } }] : []),
    ...(dok.hat_docx && bearbeitbar && offen ? [{ text: "Bearbeitete DOCX hochladen", hinweis: "Texte übernehmen, neue Fassung", onClick: onDocxHoch }] : []),
    ...(bearbeitbar && dok.status === "entwurf" ? [{ text: "Entwurf entfernen", gefaehrlich: true, onClick: () => onDialog("loeschen") }] : []),
  ];
  return (
    <li className={cx("card border px-3 py-2.5 flex flex-col gap-2 min-w-0", dok.veraltet && "border-warn")} data-testid="falldokument"
      data-art={dok.art} data-status={dok.status}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="flex items-center gap-2 flex-wrap min-w-0">
            <span className="text-sm font-medium break-words min-w-0">{dok.titel}</span>
            <DokStatusChip dok={dok} />
            {dok.veraltet ? <Chip art="warn" data-testid="dok-veraltet" title="Die Falldaten wurden nach der letzten Erzeugung geändert.">veraltet – neu erzeugen</Chip> : null}
          </span>
          <span className="text-[0.8125rem] gedaempft leading-snug break-words">
            {[dok.art === "vorlage" ? "Formular" : dok.art_name,
              dok.versionen_anzahl ? `${dok.versionen_anzahl} ${dok.versionen_anzahl === 1 ? "Fassung" : "Fassungen"}` : "noch keine PDF",
              lv ? `zuletzt ${zeitpunkt(lv.erzeugt_am)}${lv.erzeugt_von_name ? ` von ${lv.erzeugt_von_name}` : ""}` : "",
              dok.unterzeichner_name ? `Unterschrift: ${dok.unterzeichner_name}` : ""].filter(Boolean).join(" · ")}
          </span>
          {rechnung ? (
            <span className="text-[0.8125rem] num" data-testid="dok-rechnung">
              {dok.rechnungsnummer ? `Nr. ${dok.rechnungsnummer}` : "Nummer bei der ersten Erzeugung"}
              {dok.rechnungsdatum ? ` · ${datum(dok.rechnungsdatum)}` : ""} · Summe {geld(dok.summe)}
            </span>
          ) : null}
          {dok.status === "final" ? (
            <span className="text-[0.8125rem] text-ok">{dok.final_weg_name}{dok.final_am ? ` am ${zeitpunkt(dok.final_am)}` : ""}{dok.final_von_name ? ` von ${dok.final_von_name}` : ""}</span>
          ) : null}
          {dok.storniert_am ? (
            <span className="text-[0.8125rem] text-fehler break-words">Storniert am {datum(dok.storniert_am)}{dok.storniert_von_name ? ` von ${dok.storniert_von_name}` : ""}: {dok.storno_grund}</span>
          ) : null}
        </div>
        <div className="flex items-center gap-1.5 flex-wrap shrink-0 max-w-full">
          {offen ? <Knopf klein icon="auge" onClick={() => onDialog("vorschau")} data-testid="dok-vorschau">Vorschau</Knopf>
            : <Knopf klein icon="dokument" onClick={() => onDialog("pdf")} data-testid="dok-pdf">PDF öffnen</Knopf>}
          {bearbeitbar && offen ? (
            dok.status === "entwurf"
              ? <Knopf klein variante="pri" icon="dokument" laedt={erzeugtGerade} onClick={onErzeugen} data-testid="dok-erzeugen">PDF erzeugen</Knopf>
              : <Knopf klein variante={dok.veraltet ? "pri" : "sec"} icon="neustart" onClick={() => onDialog("erzeugen")} data-testid="dok-neu-erzeugen">Neu erzeugen</Knopf>
          ) : null}
          {finalisieren && dok.status === "erzeugt" ? (
            <Knopf klein icon="haken" onClick={() => onDialog("finalisieren")} data-testid="dok-finalisieren">Finalisieren</Knopf>
          ) : null}
          {stornieren && dok.art === "rechnung" && dok.status === "final" && !dok.storniert_am ? (
            <Knopf klein variante="dng" onClick={() => onDialog("stornieren")} data-testid="dok-stornieren">Stornieren</Knopf>
          ) : null}
          {rechnung ? (
            <Knopf klein aria-expanded={positionenOffen} onClick={onPositionen} data-testid="dok-positionen"
              icon={positionenOffen ? "hoch" : "runter"}>Positionen</Knopf>
          ) : null}
          {menue.length ? <Menue label="Weitere Aktionen" eintraege={menue} /> : null}
        </div>
      </div>
      {rechnung && positionenOffen ? <Positionen dok={dok} bearbeitbar={bearbeitbar && offen} /> : null}
    </li>
  );
}

function Dokumentliste({ fall, bearbeitbar, finalisieren }: { fall: Fall; bearbeitbar: boolean; finalisieren: boolean }) {
  const { patient } = useAkte();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [dialog, setDialog] = useState<{ art: DokDialog; dok: FallDokument | null }>({ art: "", dok: null });
  const [offenePositionen, setOffenePositionen] = useState<number | null>(null);
  const [neu, setNeu] = useState(false);
  const docxEingabe = useRef<HTMLInputElement>(null);
  const docxZiel = useRef<FallDokument | null>(null);
  const liste = useQuery({
    queryKey: ["falldokumente", fall.id],
    queryFn: () => api<FallDokument[]>(`falldokumente/?fall=${fall.id}`),
  });
  const dokumente = liste.data ?? [];
  const aktuell = dialog.dok ? dokumente.find((d) => d.id === dialog.dok!.id) ?? dialog.dok : null;
  const setz = (art: DokDialog, dok: FallDokument | null = dialog.dok) => setDialog({ art, dok });
  const zu = (o: boolean) => { if (!o) setDialog((d) => ({ ...d, art: "" })); };

  const erzeugen = useMutation({
    mutationFn: (d: FallDokument) => api<FallDokument>(`falldokumente/${d.id}/erzeugen/`, { body: {} }),
    onSuccess: (d) => { neuLaden(); melden(`„${d.titel}“ erzeugt (Fassung ${d.letzte_version?.nummer ?? 1}).`); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const paket = useMutation({
    mutationFn: () => api<{ neu: number; dokumente: FallDokument[] }>(`faelle/${fall.id}/paket/`, { body: {} }),
    onSuccess: (r) => { neuLaden(); melden(r.neu ? `${r.neu} ${r.neu === 1 ? "Dokument" : "Dokumente"} ergänzt.` : "Das Paket ist vollständig."); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const docxHoch = useMutation({
    mutationFn: ({ dok, datei }: { dok: FallDokument; datei: File }) => {
      const form = new FormData();
      form.append("datei", datei);
      return api<FallDokument>(`falldokumente/${dok.id}/docx/`, { form });
    },
    onSuccess: (d) => { neuLaden(); melden(`DOCX übernommen. Neue Fassung ${d.letzte_version?.nummer ?? ""} erzeugt.`); },
    onError: (e) => melden(e instanceof ApiFehler ? (e.felder.datei || e.message) : String(e), "fehler"),
  });
  const loeschen = useMutation({
    mutationFn: (d: FallDokument) => api(`falldokumente/${d.id}/`, { method: "DELETE" }),
    onSuccess: () => { neuLaden(); melden("Entwurf entfernt."); setDialog({ art: "", dok: null }); },
  });

  return (
    <div className="flex flex-col gap-2.5 min-w-0" data-testid="falldokumente">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="text-[0.8125rem] gedaempft">
          {dokumente.length} {dokumente.length === 1 ? "Dokument" : "Dokumente"} · {stand(fall)}
        </span>
        {bearbeitbar ? (
          <div className="flex items-center gap-2 flex-wrap">
            <Knopf klein icon="neustart" laedt={paket.isPending} onClick={() => paket.mutate()} data-testid="paket-ergaenzen"
              title="Fehlende Dokumente des Kostenträgertyps als Entwurf anlegen">Paket ergänzen</Knopf>
            <Knopf klein icon="plus" onClick={() => setNeu(true)} data-testid="dokument-hinzufuegen">Dokument hinzufügen</Knopf>
          </div>
        ) : null}
      </div>
      {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
      {liste.isSuccess && !dokumente.length ? <Leer>Noch keine Dokumente. „Paket ergänzen“ legt die Dokumente des Kostenträgertyps an.</Leer> : null}
      <ul className="m-0 p-0 list-none flex flex-col gap-2">
        {dokumente.map((d) => (
          <DokumentZeile key={d.id} dok={d} bearbeitbar={bearbeitbar} finalisieren={finalisieren}
            stornieren={finalisieren && fall.status === "offen"}
            positionenOffen={offenePositionen === d.id} onPositionen={() => setOffenePositionen((x) => (x === d.id ? null : d.id))}
            onDialog={(art) => setz(art, d)} erzeugtGerade={erzeugen.isPending && erzeugen.variables?.id === d.id}
            onErzeugen={() => erzeugen.mutate(d)}
            onDocxHoch={() => { docxZiel.current = d; docxEingabe.current?.click(); }} />
        ))}
      </ul>
      <input ref={docxEingabe} type="file" hidden aria-label="Bearbeitete DOCX hochladen"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={(e) => {
          const datei = e.target.files?.[0];
          if (datei && docxZiel.current) docxHoch.mutate({ dok: docxZiel.current, datei });
          e.target.value = "";
        }} />
      {docxHoch.isPending ? <Laden text="DOCX wird übernommen …" /> : null}

      <PdfDialog offen={(dialog.art === "vorschau" || dialog.art === "pdf") && !!aktuell} onOffen={zu}
        titel={aktuell ? `${aktuell.titel}${dialog.art === "vorschau" ? " (Vorschau)" : ""}` : "Dokument"}
        pfad={aktuell ? `falldokumente/${aktuell.id}/${dialog.art === "vorschau" ? "vorschau" : "pdf"}/` : ""}
        dateiname={`${aktuell?.titel ?? "Dokument"}-${patient.nummer}${dialog.art === "vorschau" ? "-Vorschau" : ""}.pdf`} />
      <FassungenDialog dok={aktuell} offen={dialog.art === "fassungen"} onOffen={zu} />
      {bearbeitbar ? <>
        <ErzeugenDialog dok={aktuell} offen={dialog.art === "erzeugen"} onOffen={zu} />
        <DokumentBearbeiten dok={aktuell} offen={dialog.art === "bearbeiten"} onOffen={zu} />
        <DokumentNeu fall={fall} offen={neu} onOffen={setNeu} />
        <Bestaetigen offen={dialog.art === "loeschen"} onOffen={(o) => { if (!o) zu(false); else loeschen.reset(); }}
          titel="Entwurf entfernen" knopf="Entfernen" text={<>Der Entwurf „{aktuell?.titel}“ wird entfernt.</>}
          laedt={loeschen.isPending} fehler={loeschen.error} onJa={() => aktuell && loeschen.mutate(aktuell)} />
      </> : null}
      {finalisieren ? <>
        <FinalisierenDialog dok={aktuell} offen={dialog.art === "finalisieren"} onOffen={zu} />
        <StornierenDialog dok={aktuell} offen={dialog.art === "stornieren"} onOffen={zu} />
      </> : null}
    </div>
  );
}

// ------------------------------------------------------------------ Reiter
export function Faelle() {
  const { patient, erfassen } = useAkte();
  const { darfBei } = useAuth();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [wahl, setWahl] = useWahl("fall");
  const [ansicht, setAnsicht] = useWahl("ansicht");
  const [formular, setFormular] = useState<{ offen: boolean; fall: Fall | null; bereich: Bereich }>({ offen: false, fall: null, bereich: "kostentraeger" });
  const [loeschenOffen, setLoeschenOffen] = useState(false);
  const finalisieren = !patient.ist_abgeschlossen && darfBei("dokumente_finalisieren", patient);

  const liste = useQuery({
    queryKey: ["faelle", patient.id],
    queryFn: () => api<Fall[]>(`faelle/?patient=${patient.id}`),
  });
  const alle = liste.data ?? [];
  const gewaehlt = alle.find((f) => String(f.id) === wahl) ?? alle[0];
  const bearbeitbar = erfassen && gewaehlt?.status === "offen";
  const ohneErzeugte = !!gewaehlt && gewaehlt.dokumente_stand.erzeugt + gewaehlt.dokumente_stand.final === 0;

  const status = useMutation({
    mutationFn: (f: Fall) => api<Fall>(`faelle/${f.id}/${f.status === "offen" ? "abschliessen" : "wieder-oeffnen"}/`, { body: {} }),
    onSuccess: (f) => { neuLaden(); melden(f.status === "offen" ? "Fall wieder geöffnet." : "Fall abgeschlossen."); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const loeschen = useMutation({
    mutationFn: (f: Fall) => api(`faelle/${f.id}/`, { method: "DELETE" }),
    onSuccess: () => { neuLaden(); melden("Fall entfernt."); setWahl(""); setLoeschenOffen(false); },
  });

  return (
    <>
      <Aktenseite
        testid="faelle"
        titel={alle.length === 1 ? "Fall" : "Fälle"}
        anzahl={alle.length}
        laedt={liste.isPending}
        aktion={erfassen
          ? <Knopf variante="pri" icon="plus" onClick={() => setFormular({ offen: true, fall: null, bereich: "kostentraeger" })}
            data-testid="fall-neu">Neuer Fall</Knopf>
          : undefined}
        kopfrechts={<Fehleranzeige fehler={liste.error} />}
        liste={
          <Eintragsliste name="Fälle" leer={alle.length ? undefined : "Noch kein Fall in dieser Akte."}>
            {alle.map((f) => (
              <Eintrag key={f.id} aktiv={gewaehlt?.id === f.id} onWahl={() => setWahl(String(f.id))}
                datum={f.nummer} merkmal={<FallStatusChip fall={f} />}
                zeile={<span className="break-words">{f.titel || f.eingriff || f.kostentraegertyp_name}</span>}
                unten={[f.kostentraegertyp_name, stand(f)].join(" · ")} />
            ))}
          </Eintragsliste>
        }
        fuss={<>Ein Fall ist die Datenquelle für alle seine Dokumente. Finale Dokumente sind unveränderlich.</>}
        detail={gewaehlt ? (
          <Detail testid="fall-detail"
            titel={<span className="flex items-center gap-2 flex-wrap min-w-0">
              <span className="break-words min-w-0">{gewaehlt.nummer}{gewaehlt.titel ? ` · ${gewaehlt.titel}` : ""}</span>
              <FallStatusChip fall={gewaehlt} /></span>}
            unter={[gewaehlt.kostentraegertyp_name, gewaehlt.kostentraeger, gewaehlt.kooperationspartner_name,
              `angelegt am ${datum(gewaehlt.erstellt_am)}${gewaehlt.erstellt_von_name ? ` von ${gewaehlt.erstellt_von_name}` : ""}`]
              .filter(Boolean).join(" · ")}
            aktionen={erfassen ? <>
              <Knopf klein icon={gewaehlt.status === "offen" ? "haken" : "neustart"} laedt={status.isPending}
                onClick={() => status.mutate(gewaehlt)} data-testid="fall-status-wechseln">
                {gewaehlt.status === "offen" ? "Fall abschließen" : "Wieder öffnen"}</Knopf>
              {ohneErzeugte && gewaehlt.status === "offen"
                ? <Knopf klein variante="dng" onClick={() => { loeschen.reset(); setLoeschenOffen(true); }} data-testid="fall-loeschen">Entfernen</Knopf> : null}
            </> : undefined}>
            {gewaehlt.status === "abgeschlossen" ? (
              <Meldung art="info">Der Fall ist abgeschlossen. Zum Ändern bitte wieder öffnen.</Meldung>
            ) : null}
            <Segmente label="Ansicht" className="self-start" wert={ansicht === "daten" ? "daten" : "dokumente"}
              onWahl={(w) => setAnsicht(w === "dokumente" ? "" : w)}
              werte={[{ wert: "dokumente", text: "Dokumente" }, { wert: "daten", text: "Falldaten" }]} />
            {ansicht === "daten"
              ? <Falldaten fall={gewaehlt} bearbeitbar={bearbeitbar}
                onBearbeiten={(b) => setFormular({ offen: true, fall: gewaehlt, bereich: b })} />
              : <Dokumentliste key={gewaehlt.id} fall={gewaehlt} bearbeitbar={bearbeitbar} finalisieren={finalisieren} />}
          </Detail>
        ) : null}
        leer="Links einen Fall wählen."
      />
      {erfassen ? <>
        <FallDialog fall={formular.fall} bereich={formular.bereich} offen={formular.offen}
          onOffen={(o) => setFormular((d) => ({ ...d, offen: o }))}
          onGespeichert={(f) => { if (!formular.fall) setWahl(String(f.id)); }} />
        <Bestaetigen offen={loeschenOffen} onOffen={setLoeschenOffen} titel="Fall entfernen" knopf="Entfernen"
          text={<>Fall {gewaehlt?.nummer} und seine Entwürfe werden entfernt.</>} laedt={loeschen.isPending} fehler={loeschen.error}
          onJa={() => gewaehlt && loeschen.mutate(gewaehlt)} />
      </> : null}
    </>
  );
}
