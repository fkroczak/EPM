/**
 * Scan einem Patienten zuordnen – mit Prüfansicht der erkannten Werte (F163, F166).
 *
 * Links bleibt die Seite stehen: Wer eine Zeile anklickt oder ein Feld bearbeitet, sieht die Stelle im Original
 * markiert. Nichts wird ohne Bestätigung übernommen; Vorschläge mit unsicherer Erkennung oder unplausiblem Wert sind
 * nicht vorgewählt. Alles entsteht in einem Schritt: das Dokument (durchsuchbare PDF mit Text) und auf Wunsch
 * Laborbefund, BIA-Messung, Diagnosen und Ergänzungen der Textfelder.
 *
 * Laborbefund und BIA-Messung lassen sich auch dann übernehmen, wenn die Art nicht erkannt wurde (anderes Gerät,
 * anderes Layout): Abschnitt einschalten, Feld anklicken und dann den Wert im Bild links anklicken – oder tippen.
 * Laborwerte lassen sich mit „+ Wert“ ergänzen (09.10.2026).
 *
 * Texterkennung lernt mit (F182): Mit dem Zuordnen geht an den Server, welche Zeile der Erkennung zu welchem
 * übernommenen Wert gehört bzw. wo ein von Hand ergänzter Wert im Bild steht („herkunft“). Daraus lernt er Bezeichnungen;
 * gelernte Zuordnungen sind hier mit „gelernt“ gekennzeichnet. Der Patient wird vorgeschlagen, nie selbst gewählt (F183).
 *
 * Erkennung verbessern (F189): Jede erkannte Zeile hat „Falsch erkannt“ (mit Grund; wirkt sofort, der Server lernt
 * daraus), „Bereich markieren“ liest nur einen im Bild aufgezogenen Rahmen neu – die Zeilen darin kommen als neue
 * Werte dazu. Der Hinweis „So helfen Sie EPM, besser zu lesen“ erscheint einmal und ist über „?“ wieder abrufbar.
 */
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuswahl, useDiagnoseliste, useLaborparameter } from "@/lib/daten";
import { datum, eingabeZahl, nummer } from "@/lib/format";
import type { PatientZeile, Scan, ScanBiaWert, ScanDiagnose, ScanLaborwert, ScanVorschlag } from "@/lib/typen";
import { PatientWahl } from "@/components/PatientWahl";
import { Auswahl, Chip, Eingabe, Feld, Knopf, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { useHinweis } from "@/components/ui/hinweise";
import { ARTEN, UNSICHER } from "./hilfen";
import { PatientVorschlag } from "./PatientVorschlag";
import { BereichKnopf, FalschKnopf, GRUND_TEXT, VerbessernHinweis } from "./Verbessern";
import type { Grund } from "./Verbessern";
import { Begriff } from "@/components/ui/Begriff";

export type Stelle = { seite: number; box: number[] } | null;
/** Gewähltes Feld: Ein Klick auf ein Wort im Bild schreibt dessen Text hinein */
export type Ziel = { schluessel: string; name: string; setzen: (text: string, stelle: Stelle) => void } | null;

type Wahl = { id: number; nummer: number; nachname: string; vorname: string; geburtsdatum: string | null; ist_test: boolean };

type LaborZeile = { an: boolean; parameter: number | null; freitext_name: string; wert: string; wert_text: string;
  einheit: string; referenz_von: string; referenz_bis: string; quelle: ScanLaborwert | null; stelle?: Stelle;
  /** Nummer der Zeile in der Erkennung (null = von Hand ergänzt) – für das Lernen (F182) */
  index: number | null };

function GelerntChip({ zuordnung }: { zuordnung?: string }) {
  if (zuordnung === "liste" || zuordnung === "liste_vorschlag") {
    // Diagnose ohne Code im Brief: Code aus Vorlagen › Diagnosen (Kundenwunsch 14.10.2026)
    return (
      <Chip art={zuordnung === "liste" ? "akzent" : "warn"} className="ml-1" data-testid="chip-liste"
        title={zuordnung === "liste" ? "ohne ICD-Code im Brief – Code aus der Diagnoseliste" : "ohne ICD-Code im Brief – ähnlicher Eintrag der Diagnoseliste, bitte prüfen"}>
        Liste{zuordnung === "liste_vorschlag" ? "?" : ""}
      </Chip>
    );
  }
  if (zuordnung !== "gelernt" && zuordnung !== "gelernt_vorschlag") return null;
  return (
    <Chip art={zuordnung === "gelernt" ? "akzent" : "warn"} className="ml-1" data-testid="chip-gelernt"
      title={zuordnung === "gelernt" ? "aus früheren Korrekturen gelernt" : "gelernt, aber erst einmal bestätigt – bitte prüfen"}>
      gelernt{zuordnung === "gelernt_vorschlag" ? "?" : ""}
    </Chip>
  );
}

function alsWahl(v: ScanVorschlag): Wahl {
  const [nach, ...vor] = v.name.split(", ");
  return { id: v.id, nummer: v.nummer, nachname: v.nachname ?? nach, vorname: v.vorname ?? vor.join(", "),
    geburtsdatum: v.geburtsdatum, ist_test: v.ist_test };
}

const BIA_FELDER: [keyof NonNullable<Scan["auswertung"]["bia"]>["werte"], string, string][] = [
  ["gewicht_kg", "Gewicht", "kg"], ["bcm_kg", "BCM", "kg"], ["fettmasse_kg", "Fettmasse", "kg"],
  ["ecw_prozent", "ECW", "%"], ["koerperwasser_l", "Körperwasser", "l"], ["bmi", "BMI", "kg/m²"],
];

const TEXTFELDER = [["diagnose", "Diagnose (Freitext)"], ["therapie", "Therapie"], ["empfehlung", "Empfehlung"]] as const;
type Textfeldname = (typeof TEXTFELDER)[number][0];

function komma(v: string | null | undefined): string {
  return v == null ? "" : String(v).replace(".", ",");
}

/** Zahl aus einem angeklickten Wort („3,21“, „138mmol/l“, „<0.5“ → „3,21“, „138“, „0,5“) */
function zahlAus(text: string): string {
  const m = text.replace(/\s/g, "").match(/[-+]?\d+(?:[.,]\d+)?/);
  return m ? m[0].replace(".", ",") : text.trim();
}

/** Referenzbereich aus einem Wort („3,5-5,1“) → [von, bis]; sonst nur eine Zahl */
function bereichAus(text: string): [string, string] | null {
  const m = text.replace(/\s/g, "").match(/(\d+(?:[.,]\d+)?)[-–](\d+(?:[.,]\d+)?)/);
  return m ? [m[1].replace(".", ","), m[2].replace(".", ",")] : null;
}

function html(text: string): string {
  return text.split(/\n+/).filter((z) => z.trim()).map((z) =>
    `<p>${z.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p>`).join("");
}

function Sicherheit({ c, hinweise }: { c: number; hinweise?: string[] }) {
  const unsicher = c < UNSICHER;
  return (
    <span className={cx("num text-xs", unsicher ? "text-warn font-medium" : "gedaempft")} title={hinweise?.join("\n")}>
      {Math.round(c * 100)} %
    </span>
  );
}

function Abschnitt({ titel, an, onAn, zahl, children, testid }: {
  titel: string; an: boolean; onAn: (an: boolean) => void; zahl?: string; children: ReactNode; testid: string;
}) {
  return (
    <section className="border border-rand rounded-lg overflow-hidden" data-testid={testid}>
      <label className="flex items-center gap-2.5 px-3.5 py-2.5 bg-fein cursor-pointer">
        <input type="checkbox" checked={an} onChange={(e) => onAn(e.target.checked)} />
        <span className="font-semibold text-[0.9375rem]">{titel}</span>
        {zahl ? <span className="text-[0.8125rem] gedaempft">{zahl}</span> : null}
      </label>
      {an ? <div className="p-3.5 flex flex-col gap-3">{children}</div> : null}
    </section>
  );
}

export function Zuordnen({ scan, onStelle, onFertig, onAbbrechen, ziel = null, onZiel = () => {}, startPatient = null,
  bereichAktiv = false, bereichLaedt = false, onBereich, neueWerte = null }: {
  scan: Scan; onStelle: (s: Stelle) => void; onFertig: (patientId: number, dokumentId: number) => void; onAbbrechen: () => void;
  ziel?: Ziel; onZiel?: (z: Ziel) => void;
  /** in der Scan-Ansicht mit einem Klick übernommener Vorschlag (F183) */
  startPatient?: ScanVorschlag | null;
  /** F189: „Bereich markieren“ – der Rahmen wird in der Seitenansicht aufgezogen (ScanDetail) */
  bereichAktiv?: boolean; bereichLaedt?: boolean; onBereich?: () => void;
  /** F189: Nummern der Laborwerte, die der markierte Bereich ergeben hat (``nr`` wechselt mit jedem Bereich) */
  neueWerte?: { nr: number; indices: number[] } | null;
}) {
  const a = scan.auswertung ?? {};
  const arten = a.arten ?? [];
  const { darf, darfBei, ich } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const katalog = useLaborparameter();
  const typen = useAuswahl("dokumenttyp");

  // Arbeitskopie eines Akte-Dokuments (F171): Patient steht fest, es entsteht kein neues Dokument
  const quelle = scan.quelle ?? null;
  const [patient, setPatient] = useState<Wahl | null>(quelle ? { ...quelle.patient } : startPatient ? alsWahl(startPatient) : null);
  const [titel, setTitel] = useState(scan.titel);
  const [typ, setTyp] = useState("");
  const [dokDatum, setDokDatum] = useState(scan.dokumentdatum ?? "");
  const [notiz, setNotiz] = useState("");
  const [original, setOriginal] = useState(false);

  const [laborAn, setLaborAn] = useState(arten.includes("labor"));
  const [abnahme, setAbnahme] = useState(a.datum_quelle === "abnahme" || a.datum_quelle === "befund" ? a.datum ?? "" : a.datum ?? "");
  const [laborName, setLaborName] = useState(a.labor?.name ?? "");
  const [beurteilung, setBeurteilung] = useState(arten.includes("labor") ? a.abschnitte?.verlauf ?? "" : "");
  const [werte, setWerte] = useState<LaborZeile[]>(() => (a.labor?.werte ?? []).map((w, i) => ({
    an: w.vorschlag, parameter: w.parameter, freitext_name: w.freitext_name, wert: komma(w.wert), wert_text: w.wert_text,
    einheit: w.einheit, referenz_von: komma(w.referenz_von), referenz_bis: komma(w.referenz_bis), quelle: w, index: i,
  })).filter((z) => !z.quelle?.verworfen));

  // „Falsch erkannt“ angemerkte BIA-Werte (F189) erscheinen nicht mehr als „gelesen“
  const [biaWeg, setBiaWeg] = useState<string[]>([]);
  const biaQuelle = Object.fromEntries(Object.entries(a.bia?.werte ?? {})
    .filter(([k, v]) => v && !v.verworfen && !biaWeg.includes(k))) as NonNullable<NonNullable<typeof a.bia>["werte"]>;
  const [biaAn, setBiaAn] = useState(arten.includes("bia"));
  const [gemessen, setGemessen] = useState(arten.includes("bia") ? a.datum ?? "" : "");
  const [bia, setBia] = useState<Record<string, string>>(() => Object.fromEntries(
    BIA_FELDER.map(([k]) => [k, (biaQuelle[k]?.vorschlag ?? false) ? komma(biaQuelle[k]?.wert) : ""])));
  // Stelle im Bild, an der ein BIA-Wert angeklickt wurde (zum Lernen der Bezeichnung daneben)
  const [biaStellen, setBiaStellen] = useState<Record<string, Stelle>>({});
  const [gewichtUebernehmen, setGewichtUebernehmen] = useState(true);
  const [biaBeurteilung, setBiaBeurteilung] = useState(() => (a.bia?.weitere ?? [])
    .map((w) => `${w.name}: ${komma(w.wert)}${w.einheit ? ` ${w.einheit}` : ""}`).join("\n"));

  const darfAkte = darf("akten_bearbeiten");
  const [diagnosen, setDiagnosen] = useState<(ScanDiagnose & { an: boolean; index: number })[]>(() =>
    (a.diagnosen ?? []).map((d, i) => ({ ...d, an: d.vorschlag && darfAkte, index: i })).filter((d) => !d.verworfen));
  const [texte, setTexte] = useState<Record<Textfeldname, { an: boolean; text: string }>>(() => ({
    diagnose: { an: false, text: a.abschnitte?.diagnosen ?? "" },
    therapie: { an: false, text: a.abschnitte?.therapie ?? "" },
    empfehlung: { an: false, text: a.abschnitte?.procedere ?? "" },
  }));

  // Vorschläge für den Patienten (F183): nie selbst wählen – die Pflegekraft übernimmt mit einem Klick
  const vorschlaege = scan.vorschlaege ?? [];

  // F189: Zeilen aus einem markierten Bereich hinten anfügen (vorgewählt, wenn ein Laborwert erkannt wurde)
  useEffect(() => {
    if (!neueWerte) return;
    const liste = scan.auswertung?.labor?.werte ?? [];
    setWerte((alt) => {
      const da = new Set(alt.map((z) => z.index));
      const neu = neueWerte.indices.filter((i) => !da.has(i) && liste[i]).map((i): LaborZeile => {
        const w = liste[i];
        return { an: !!w.parameter && w.vorschlag, parameter: w.parameter, freitext_name: w.freitext_name, wert: komma(w.wert),
          wert_text: w.wert_text, einheit: w.einheit, referenz_von: komma(w.referenz_von), referenz_bis: komma(w.referenz_bis),
          quelle: w, index: i };
      });
      return [...alt, ...neu];
    });
    setLaborAn(true);
    melden(neueWerte.indices.length
      ? `${neueWerte.indices.length === 1 ? "Eine Zeile" : `${neueWerte.indices.length} Zeilen`} aus dem markierten Bereich gelesen – bitte prüfen.`
      : "Im markierten Bereich wurde kein Text gefunden. Bitte einen etwas größeren Rahmen ziehen.", neueWerte.indices.length ? "ok" : "fehler");
  }, [neueWerte?.nr]); // eslint-disable-line react-hooks/exhaustive-deps

  // F189: „Falsch erkannt“ – sofort verwerfen, der Server lernt daraus
  const falsch = useMutation({
    mutationFn: (x: { art: "labor" | "bia" | "diagnose"; index: number | string; grund: Grund }) =>
      api<{ gelernt: string }>(`scans/${scan.id}/falsch/`, { body: x }),
    onSuccess: (e, x) => {
      if (x.art === "labor") setWerte((alt) => alt.filter((z) => z.index !== x.index));
      if (x.art === "bia") {
        setBiaWeg((alt) => [...alt, String(x.index)]);
        setBia((alt) => ({ ...alt, [String(x.index)]: "" }));
      }
      if (x.art === "diagnose") setDiagnosen((alt) => alt.filter((d) => d.index !== x.index));
      const folge = { ignorieren: " EPM lässt diese Zeile bei diesem Labor künftig weg.",
        gesperrt: " EPM ordnet diese Bezeichnung bei diesem Labor nicht mehr so zu.",
        widersprochen: " Die gelernte Zuordnung zählt jetzt weniger." }[e.gelernt] ?? "";
      melden(`Verworfen (${GRUND_TEXT[x.grund]}).${folge}`);
      void qc.invalidateQueries({ queryKey: ["scans", "gelernt"] });
    },
    onError: (e) => melden(e instanceof Error ? e.message : String(e), "fehler"),
  });

  const pruefung = useQuery({
    queryKey: ["scan", scan.id, "pruefen", patient?.id],
    queryFn: () => api<{ hinweise: string[] }>(`scans/${scan.id}/pruefen/?patient=${patient!.id}`),
    enabled: !!patient,
  });

  const katalogNamen = useMemo(() => new Map((katalog.data ?? []).map((p) => [p.id, p])), [katalog.data]);
  // übernommen werden angehakte Zeilen mit Wert und Parameter (bzw. Freitext-Namen)
  const gewaehlteWerte = werte.filter((w) => w.an && (w.wert.trim() || w.wert_text.trim()) && (w.parameter || w.freitext_name.trim()));
  const biaGewaehlt = BIA_FELDER.filter(([k]) => bia[k]?.trim());
  const diagnosenGewaehlt = diagnosen.filter((d) => d.an);
  // der ICD-Code ist Pflicht: angehakte Diagnosen ohne Code (Freitext im Brief) halten das Übernehmen an
  const diagnosenOhneCode = diagnosenGewaehlt.filter((d) => !d.icd_code.trim());
  const diagnoseliste = useDiagnoseliste();
  /** Bezeichnung geändert: aus der Diagnoseliste gewählt → Code gleich mit übernehmen */
  const bezeichnungSetzen = (i: number, text: string) => {
    const treffer = (diagnoseliste.data ?? []).find((v) => v.bezeichnung === text);
    setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, bezeichnung: text, ...(treffer ? { icd_code: treffer.icd_code } : {}) } : x)));
  };
  const texteGewaehlt = TEXTFELDER.filter(([k]) => texte[k].an && texte[k].text.trim());
  const etwasGewaehlt = (laborAn && gewaehlteWerte.length > 0) || (biaAn && biaGewaehlt.length > 0)
    || diagnosenGewaehlt.length > 0 || texteGewaehlt.length > 0;

  const zuordnen = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = quelle ? { patient: patient!.id }
        : { patient: patient!.id, titel, typ: typ || null, datum: dokDatum || null, notiz, original };
      if (laborAn && gewaehlteWerte.length) {
        body.labor = {
          abgenommen_am: abnahme || null, labor: laborName, beurteilung: beurteilung ? html(beurteilung) : "",
          werte: gewaehlteWerte.map((w, i) => {
            const zahlWert = w.wert_text ? null : eingabeZahl(w.wert);
            return {
              parameter: w.parameter, freitext_name: w.parameter ? "" : w.freitext_name,
              wert: zahlWert, wert_text: w.wert_text, einheit: w.einheit,
              referenz_von: eingabeZahl(w.referenz_von), referenz_bis: eingabeZahl(w.referenz_bis), reihenfolge: i,
            };
          }),
        };
      }
      if (biaAn && biaGewaehlt.length) {
        body.bia = {
          gemessen_am: gemessen || null, gewicht_uebernehmen: gewichtUebernehmen, beurteilung: biaBeurteilung ? html(biaBeurteilung) : "",
          ...Object.fromEntries(biaGewaehlt.map(([k]) => [k, eingabeZahl(bia[k])])),
        };
      }
      if (diagnosenGewaehlt.length) {
        body.diagnosen = diagnosenGewaehlt.map((d) => ({ bezeichnung: d.bezeichnung, icd_code: d.icd_code, kennzeichen: d.kennzeichen }));
      }
      if (texteGewaehlt.length) body.texte = Object.fromEntries(texteGewaehlt.map(([k]) => [k, texte[k].text]));
      // Woher die Werte stammen – daraus lernt die Erkennung Bezeichnungen (F182); Werte selbst lernt sie nicht
      body.herkunft = {
        labor: laborAn ? gewaehlteWerte.map((w) => ({ index: w.index, stelle: w.stelle ?? null })) : [],
        bia: biaAn ? Object.fromEntries(biaGewaehlt.map(([k]) => [k, biaStellen[k] ?? null])) : {},
        diagnosen: diagnosenGewaehlt.map((d) => d.index),
      };
      return api<{ dokument: number; patient: number; laborbefund?: number; bia?: number; diagnosen?: number[] }>(
        `scans/${scan.id}/zuordnen/`, { body });
    },
    onSuccess: (e) => {
      const teile = [e.laborbefund ? `${gewaehlteWerte.length} Laborwerte` : "", e.bia ? "BIA-Messung" : "",
        e.diagnosen?.length ? `${e.diagnosen.length} Diagnosen` : ""].filter(Boolean);
      melden(quelle ? `Übernommen: ${teile.join(", ") || "Texte"} – verknüpft mit „${quelle.titel}“.`
        : `Als Dokument in die Akte gelegt${teile.length ? ` – übernommen: ${teile.join(", ")}` : ""}.`);
      void qc.invalidateQueries({ queryKey: ["scans"] });
      void qc.invalidateQueries({ queryKey: ["patient", e.patient] });
      onFertig(e.patient, e.dokument);
    },
  });
  const fehler = zuordnen.error instanceof ApiFehler ? zuordnen.error.felder : {};
  const darfZuordnen = !!patient && darfBei("eintraege_erfassen", patient);
  const originaleErlaubt = (a.originale ?? []).length > 0 && (a.originale ?? []).every((o) => ["application/pdf", "image/jpeg", "image/png"].includes(o.mime));
  const nurTest = scan.ist_test || !!ich?.schreibt_nur_testpatienten;

  // funktional: Auch ein Klick ins Bild (Ziel) ändert die aktuelle Fassung, nicht die beim Wählen des Felds
  const zeile = (i: number, neu: Partial<LaborZeile>) => setWerte((alt) => alt.map((w, j) => (j === i ? { ...w, ...neu } : w)));
  const leereZeile = (): LaborZeile => ({ an: true, parameter: null, freitext_name: "", wert: "", wert_text: "", einheit: "",
    referenz_von: "", referenz_bis: "", quelle: null, index: null });
  const laborName_ = (w: LaborZeile) => (w.parameter ? katalogNamen.get(w.parameter)?.name : "") || w.freitext_name || w.quelle?.erkannt_als || "neuer Wert";
  // Feld als Ziel für einen Klick ins Bild wählen; zugleich die Stelle zeigen, an der der Wert gelesen wurde
  const zielFuer = (schluessel: string, name: string, setzen: (text: string, stelle: Stelle) => void, stelle?: Stelle) => {
    onZiel({ schluessel, name, setzen });
    if (stelle) onStelle(stelle);
  };
  const istZiel = (schluessel: string) => ziel?.schluessel === schluessel;
  const laborZiel = (i: number, w: LaborZeile, feld: "wert" | "einheit" | "referenz_von" | "referenz_bis") => {
    const namen = { wert: "Wert", einheit: "Einheit", referenz_von: "Referenz von", referenz_bis: "Referenz bis" };
    const st = w.stelle ?? (w.quelle?.box ? { seite: w.quelle.seite, box: w.quelle.box } : undefined);
    zielFuer(`labor-${i}-${feld}`, `${namen[feld]} „${laborName_(w)}“`, (text, stelle) => {
      if (feld === "einheit") zeile(i, { einheit: text.trim(), an: true });
      else if (feld === "wert") zeile(i, { wert: zahlAus(text), wert_text: "", an: true, stelle });
      else {
        const b = bereichAus(text);
        zeile(i, b ? { referenz_von: b[0], referenz_bis: b[1] } : { [feld]: zahlAus(text) });
      }
    }, st);
  };
  // Ziel aufgeben, wenn der Abschnitt geschlossen wird
  useEffect(() => { if (!laborAn && ziel?.schluessel.startsWith("labor")) onZiel(null); }, [laborAn]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!biaAn && ziel?.schluessel.startsWith("bia")) onZiel(null); }, [biaAn]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col gap-4" data-testid="zuordnen">
      <div className="flex items-center gap-2">
        <h3 className="m-0 text-base font-semibold grow">{quelle ? "Werte in die Akte übernehmen" : "Einem Patienten zuordnen"}</h3>
        <Knopf klein variante="geist" onClick={onAbbrechen}>Abbrechen</Knopf>
      </div>

      {/* 1. Patient */}
      <section className="flex flex-col gap-2">
        <span className="lbl text-[0.8125rem]">Patient</span>
        {patient ? (
          <div className="flex items-center gap-3 text-sm flex-wrap" data-testid="zuordnen-patient">
            <span className="num gedaempft">{nummer(patient.nummer)}</span>
            <span className="font-medium">{patient.nachname}, {patient.vorname}</span>
            <span className="gedaempft">{datum(patient.geburtsdatum)}</span>
            {patient.ist_test ? <Chip art="warn">Test</Chip> : null}
            <Link to={`/patienten/${patient.id}`} target="_blank" className="text-[0.8125rem]">Akte öffnen</Link>
            {quelle ? null : <Knopf klein variante="geist" onClick={() => setPatient(null)}>ändern</Knopf>}
          </div>
        ) : (
          <>
            <PatientVorschlag vorschlaege={vorschlaege} onWahl={(v) => setPatient(alsWahl(v))} />
            <PatientWahl wert={null} test={nurTest ? "nur" : undefined} fehler={!!fehler.patient}
              onWahl={(p: PatientZeile | null) => p && setPatient({ id: p.id, nummer: p.nummer, nachname: p.nachname, vorname: p.vorname,
                geburtsdatum: p.geburtsdatum, ist_test: p.ist_test })} />
          </>
        )}
        {fehler.patient ? <span className="fehlertext">{fehler.patient}</span> : null}
        {pruefung.data?.hinweise.length ? (
          <Meldung art="warn"><div className="flex flex-col gap-1" data-testid="zuordnen-hinweise">
            <strong className="font-semibold">Passt das Dokument zu diesem Patienten?</strong>
            {pruefung.data.hinweise.map((h) => <span key={h}>{h}</span>)}
          </div></Meldung>
        ) : null}
        {patient && !darfZuordnen ? <Meldung art="info">Als Admin nur bei Testpatienten möglich.</Meldung> : null}
      </section>

      {/* 2. Dokument – bei einer Arbeitskopie gibt es das Dokument schon */}
      {quelle ? (
        <Meldung art="info"><span data-testid="zuordnen-quelle">Kein neues Dokument: Die Werte werden mit „{quelle.titel}“ in der Akte
          verknüpft. Die Datei des Dokuments bleibt unverändert.</span></Meldung>
      ) : (
      <section className="formular grid grid-cols-6 gap-x-3 gap-y-2.5">
        <Feld label="Titel" className="col-span-6 sm:col-span-4" fehler={fehler.titel} pflicht>
          {(p) => <Eingabe {...p} value={titel} onChange={(e) => setTitel(e.target.value)} maxLength={200} />}
        </Feld>
        <Feld label="Datum" className="col-span-3 sm:col-span-2" fehler={fehler.datum}
          hinweis={a.datum && a.datum === dokDatum ? "aus dem Dokument" : undefined}>
          {(p) => <Eingabe {...p} type="date" value={dokDatum} onChange={(e) => setDokDatum(e.target.value)} />}
        </Feld>
        <Feld label="Dokumenttyp" className="col-span-3 sm:col-span-2" fehler={fehler.typ}>
          {(p) => <Auswahl {...p} value={typ} onChange={(e) => setTyp(e.target.value)}>
            <option value="">—</option>
            {(typen.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.wert}</option>)}
          </Auswahl>}
        </Feld>
        <Feld label="Notiz" className="col-span-6 sm:col-span-4" fehler={fehler.notiz}>
          {(p) => <Eingabe {...p} value={notiz} onChange={(e) => setNotiz(e.target.value)} />}
        </Feld>
        {originaleErlaubt ? (
          <label className="col-span-6 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={original} onChange={(e) => setOriginal(e.target.checked)} />
            Hochgeladene Datei zusätzlich unverändert ablegen
            <span className="gedaempft text-[0.8125rem]">(sonst nur die aufbereitete, durchsuchbare PDF)</span>
          </label>
        ) : null}
        {fehler.original ? <span className="col-span-6 fehlertext">{fehler.original}</span> : null}
      </section>
      )}

      {/* 3. Werte – mit Hinweis, wie man die Erkennung verbessert (F189) */}
      {!quelle || arten.length ? <VerbessernHinweis /> : null}
      {arten.length ? (
        <span className="text-[0.8125rem] gedaempft">Erkannt: {arten.map((x) => ARTEN[x] ?? x).join(", ")}. Bitte jeden Wert mit dem Original vergleichen –
          ein Klick auf eine Zeile zeigt die Stelle links.</span>
      ) : null}

      {!arten.length ? (
        <span className="text-[0.8125rem] gedaempft">Die Art des Dokuments wurde nicht erkannt. Laborbefund oder <Begriff name="bia">BIA</Begriff>-Messung lassen
          sich trotzdem übernehmen: Abschnitt einschalten, Feld anklicken und den Wert im Bild links anklicken.</span>
      ) : null}

      {(
        <Abschnitt titel="Laborbefund übernehmen" an={laborAn}
          onAn={(an) => { setLaborAn(an); if (an && !werte.length) setWerte([leereZeile()]); if (an && !abnahme) setAbnahme(a.datum ?? dokDatum); }}
          testid="zuordnen-labor"
          zahl={werte.length ? `${gewaehlteWerte.length} von ${werte.length} Werten gewählt` : "nicht erkannt – Werte von Hand übernehmen"}>
          <div className="grid grid-cols-6 gap-x-3 gap-y-2.5 formular">
            <Feld label="Abnahme am" className="col-span-3 sm:col-span-2" fehler={fehler["labor.abgenommen_am"]}>
              {(p) => <Eingabe {...p} type="date" value={abnahme} onChange={(e) => setAbnahme(e.target.value)} />}
            </Feld>
            <Feld label="Labor" className="col-span-3 sm:col-span-4" fehler={fehler["labor.labor"]}>
              {(p) => <Eingabe {...p} value={laborName} onChange={(e) => setLaborName(e.target.value)} maxLength={150} />}
            </Feld>
          </div>
          <div className="overflow-x-auto">
            <table className="tabelle text-sm" data-testid="labor-pruefen">
              <thead><tr>
                <th className="th w-8"><span className="sr-only">übernehmen</span></th><th className="th">Parameter</th>
                <th className="th">Wert</th><th className="th">Einheit</th><th className="th">Referenz</th><th className="th">gelesen</th>
                <th className="th"><span className="sr-only">falsch erkannt</span></th>
              </tr></thead>
              <tbody>
                {werte.map((w, i) => {
                  const q = w.quelle;
                  const p = w.parameter ? katalogNamen.get(w.parameter) : undefined;
                  const unsicher = !!q && (q.sicherheit < UNSICHER || q.hinweise.length > 0);
                  const st = w.stelle ?? (q?.box ? { seite: q.seite, box: q.box } : null);
                  return (
                    <tr key={i} className={cx(!w.an && "opacity-60", unsicher && w.an && "bg-warn-bg/40")}
                      onClick={() => onStelle(st)} data-testid="laborzeile">
                      <td className="td"><input type="checkbox" checked={w.an} aria-label={`${p?.name ?? (w.freitext_name || "Wert")} übernehmen`}
                        onChange={(e) => zeile(i, { an: e.target.checked })} /></td>
                      <td className="td min-w-[11rem]">
                        <Auswahl value={w.parameter ?? ""} aria-label="Parameter" className="min-w-0"
                          onChange={(e) => {
                            const id = e.target.value ? Number(e.target.value) : null;
                            const neu = id ? katalogNamen.get(id) : undefined;
                            zeile(i, { parameter: id, freitext_name: id ? "" : q?.erkannt_als ?? w.freitext_name, einheit: neu?.einheit || w.einheit, an: true });
                          }}>
                          <option value="">{q ? `Freitext: ${w.freitext_name || q.erkannt_als}` : w.freitext_name ? `Freitext: ${w.freitext_name}` : "— Parameter wählen —"}</option>
                          {(katalog.data ?? []).map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
                        </Auswahl>
                        {!q && !w.parameter ? (
                          <Eingabe value={w.freitext_name} aria-label="Name (wenn nicht im Katalog)" placeholder="oder Name, wenn nicht im Katalog"
                            className="mt-1" maxLength={100} onChange={(e) => zeile(i, { freitext_name: e.target.value })} />
                        ) : null}
                        {q && q.parameter === w.parameter ? <GelerntChip zuordnung={q.zuordnung} /> : null}
                        {q?.hinweise.length ? <span className="block text-xs text-warn mt-0.5">{q.hinweise.join(" · ")}</span> : null}
                      </td>
                      <td className="td">
                        {w.wert_text ? (
                          <Eingabe value={w.wert_text} aria-label="Wert (Text)" className={cx("w-24", istZiel(`labor-${i}-wert`) && "scan-feld-ziel")}
                            onFocus={() => laborZiel(i, w, "wert")} onChange={(e) => zeile(i, { wert_text: e.target.value })} />
                        ) : (
                          <Eingabe value={w.wert} aria-label="Wert" className={cx("num w-24", istZiel(`labor-${i}-wert`) && "scan-feld-ziel")} inputMode="decimal"
                            onFocus={() => laborZiel(i, w, "wert")} onChange={(e) => zeile(i, { wert: e.target.value })} />
                        )}
                        {q?.markierung ? <Chip className="ml-1" art={/[Hh+↑]/.test(q.markierung) ? "fehler" : "warn"}>{q.markierung}</Chip> : null}
                      </td>
                      <td className="td"><Eingabe value={w.einheit} aria-label="Einheit" className={cx("w-24", istZiel(`labor-${i}-einheit`) && "scan-feld-ziel")}
                        onFocus={() => laborZiel(i, w, "einheit")} onChange={(e) => zeile(i, { einheit: e.target.value })} /></td>
                      <td className="td whitespace-nowrap">
                        <Eingabe value={w.referenz_von} aria-label="Referenz von" className={cx("num w-16 inline-block", istZiel(`labor-${i}-referenz_von`) && "scan-feld-ziel")} inputMode="decimal"
                          onFocus={() => laborZiel(i, w, "referenz_von")} onChange={(e) => zeile(i, { referenz_von: e.target.value })} />
                        <span className="px-1 gedaempft">–</span>
                        <Eingabe value={w.referenz_bis} aria-label="Referenz bis" className={cx("num w-16 inline-block", istZiel(`labor-${i}-referenz_bis`) && "scan-feld-ziel")} inputMode="decimal"
                          onFocus={() => laborZiel(i, w, "referenz_bis")} onChange={(e) => zeile(i, { referenz_bis: e.target.value })} />
                      </td>
                      <td className="td text-xs gedaempft max-w-[14rem]" title={q?.zeile}>
                        {q ? <><span className="truncate block">{q.zeile}</span><Sicherheit c={q.sicherheit} hinweise={q.hinweise} />
                          {q.bereich ? <Chip className="ml-1" title="aus dem markierten Bereich gelesen">Bereich</Chip> : null}</>
                          : <span>von Hand</span>}
                      </td>
                      <td className="td">
                        {q && w.index !== null ? (
                          <FalschKnopf name={laborName_(w)} onGrund={(grund) => falsch.mutate({ art: "labor", index: w.index!, grund })} />
                        ) : (
                          <Knopf klein variante="geist" icon="x" aria-label="Zeile entfernen" title="Zeile entfernen"
                            onClick={(e) => { e.stopPropagation(); setWerte((alt) => alt.filter((_, j) => j !== i)); }} />
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {onBereich ? <BereichKnopf aktiv={bereichAktiv} laedt={bereichLaedt} onClick={onBereich} /> : null}
            <Knopf klein icon="plus" onClick={() => {
              const i = werte.length;
              setWerte((alt) => [...alt, leereZeile()]);
              onZiel(null);
              // das neue Parameterfeld wählen
              requestAnimationFrame(() => (document.querySelectorAll<HTMLSelectElement>('[data-testid="labor-pruefen"] select[aria-label="Parameter"]')[i])?.focus());
            }} data-testid="labor-wert-neu">Wert</Knopf>
          </div>
          <Feld label="Beurteilung" fehler={fehler["labor.beurteilung"]}>
            {(p) => <Textfeld {...p} rows={2} value={beurteilung} onChange={(e) => setBeurteilung(e.target.value)} />}
          </Feld>
          {Object.keys(fehler).some((k) => k.startsWith("labor")) ? (
            <Meldung art="fehler">{Object.entries(fehler).filter(([k]) => k.startsWith("labor")).map(([k, v]) => `${k.replace("labor.", "")}: ${v}`).join(" · ")}</Meldung>
          ) : null}
        </Abschnitt>
      )}

      {(
        <Abschnitt titel="BIA-Messung übernehmen" an={biaAn} testid="zuordnen-bia"
          onAn={(an) => { setBiaAn(an); if (an && !gemessen) setGemessen(a.datum ?? dokDatum); }}
          zahl={Object.keys(biaQuelle).length ? `${biaGewaehlt.length} Werte` : "nicht erkannt – Werte von Hand übernehmen"}>
          <span className="text-[0.8125rem] gedaempft">Feld anklicken, dann den Wert im Bild links anklicken – oder eintippen.</span>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-3 gap-y-2.5 formular">
            <Feld label="Gemessen am" fehler={fehler["bia.gemessen_am"]}>
              {(p) => <Eingabe {...p} type="date" value={gemessen} onChange={(e) => setGemessen(e.target.value)} />}
            </Feld>
            {BIA_FELDER.map(([k, name, einheit]) => {
              const q: ScanBiaWert | undefined = biaQuelle[k];
              return (
                <Feld key={k} label={`${name} (${einheit})`} fehler={fehler[`bia.${k}`]}
                  hinweis={q ? <span onMouseEnter={() => onStelle(q.box ? { seite: q.seite, box: q.box } : null)}>
                    gelesen: {q.erkannt_als} <Sicherheit c={q.sicherheit} hinweise={q.hinweise} /><GelerntChip zuordnung={q.zuordnung} />
                    {q.hinweise?.length ? ` · ${q.hinweise.join(" · ")}` : ""}
                    <FalschKnopf name={name} onGrund={(grund) => falsch.mutate({ art: "bia", index: k, grund })} />
                  </span> : undefined}>
                  {(p) => <Eingabe {...p} className={cx("num", istZiel(`bia-${k}`) && "scan-feld-ziel")} inputMode="decimal" value={bia[k] ?? ""}
                    onFocus={() => zielFuer(`bia-${k}`, name, (text, stelle) => {
                      setBia((alt) => ({ ...alt, [k]: zahlAus(text) }));
                      setBiaStellen((alt) => ({ ...alt, [k]: stelle }));
                    },
                      q?.box ? { seite: q.seite, box: q.box } : undefined)}
                    onChange={(e) => { const v = e.target.value; setBia((alt) => ({ ...alt, [k]: v })); }} />}
                </Feld>
              );
            })}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={gewichtUebernehmen} onChange={(e) => setGewichtUebernehmen(e.target.checked)} />
            Gewicht auch in den Gewichtsverlauf eintragen
          </label>
          <Feld label="Beurteilung" hinweis="weitere Werte des Protokolls, für die es kein eigenes Feld gibt">
            {(p) => <Textfeld {...p} rows={2} value={biaBeurteilung} onChange={(e) => setBiaBeurteilung(e.target.value)} />}
          </Feld>
          {Object.keys(fehler).some((k) => k.startsWith("bia")) ? (
            <Meldung art="fehler">{Object.entries(fehler).filter(([k]) => k.startsWith("bia")).map(([, v]) => v).join(" · ")}</Meldung>
          ) : null}
        </Abschnitt>
      )}

      {diagnosen.length ? (
        <Abschnitt titel="Diagnosen übernehmen" an={diagnosenGewaehlt.length > 0}
          onAn={(an) => setDiagnosen(diagnosen.map((d) => ({ ...d, an })))} testid="zuordnen-diagnosen"
          zahl={darfAkte ? `${diagnosenGewaehlt.length} von ${diagnosen.length}` : "nur mit Recht „Akten bearbeiten“"}>
          <ul className="m-0 p-0 list-none flex flex-col gap-1.5">
            {diagnosen.map((d, i) => (
              <li key={d.index} className="flex flex-wrap items-start gap-2 text-sm" data-testid="zuordnen-diagnose"
                onClick={() => onStelle(d.box ? { seite: d.seite, box: d.box } : null)}>
                <input type="checkbox" className="mt-1" checked={d.an} disabled={!darfAkte}
                  onChange={(e) => setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, an: e.target.checked } : x)))} />
                <Eingabe value={d.bezeichnung} aria-label="Bezeichnung" className="grow min-w-0 basis-40" list="zuordnen-diagnoseliste"
                  onChange={(e) => bezeichnungSetzen(i, e.target.value)} />
                <Eingabe value={d.icd_code} aria-label="ICD-Code" className="num w-20" placeholder="ICD" maxLength={10}
                  aria-invalid={d.an && !d.icd_code.trim() ? true : undefined}
                  title={d.icd_code.trim() ? undefined : "ICD-Code ist Pflicht – ergänzen oder Haken entfernen"}
                  onChange={(e) => setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, icd_code: e.target.value.toUpperCase() } : x)))} />
                <Auswahl value={d.kennzeichen} aria-label="Zusatzkennzeichen" className="w-20"
                  onChange={(e) => setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, kennzeichen: e.target.value as ScanDiagnose["kennzeichen"] } : x)))}>
                  <option value="G">G</option><option value="V">V</option><option value="Z">Z</option><option value="A">A</option>
                </Auswahl>
                <GelerntChip zuordnung={d.zuordnung} />
                <FalschKnopf name={d.bezeichnung} onGrund={(grund) => falsch.mutate({ art: "diagnose", index: d.index, grund })} />
                {d.gelernt && d.gelernt.bezeichnung !== d.bezeichnung ? (
                  <Knopf klein variante="geist" title="früher so korrigiert"
                    onClick={(e) => { e.stopPropagation(); setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, bezeichnung: d.gelernt!.bezeichnung, icd_code: d.gelernt!.icd_code } : x))); }}>
                    „{d.gelernt.bezeichnung}“?
                  </Knopf>
                ) : null}
                {d.freitext && d.hinweise?.length ? (
                  <span className={cx("basis-full pl-6 text-xs", d.icd_code.trim() ? "gedaempft" : "text-warn")}>{d.hinweise.join(" · ")}</span>
                ) : null}
              </li>
            ))}
          </ul>
          <datalist id="zuordnen-diagnoseliste">
            {(diagnoseliste.data ?? []).map((v) => <option key={v.id} value={v.bezeichnung}>{v.icd_code}</option>)}
          </datalist>
          {diagnosenOhneCode.length ? (
            <Meldung art="warn" data-testid="zuordnen-diagnosen-ohne-code">
              Ohne ICD-Code: {diagnosenOhneCode.map((d) => d.bezeichnung || "ohne Bezeichnung").join(", ")}. Bitte den Code
              ergänzen oder den Haken entfernen – ohne Code wird keine Diagnose übernommen.
            </Meldung>
          ) : null}
          {fehler.diagnosen || Object.keys(fehler).some((k) => k.startsWith("diagnosen")) ? (
            <Meldung art="fehler">{Object.entries(fehler).filter(([k]) => k.startsWith("diagnosen")).map(([, v]) => v).join(" · ")}</Meldung>
          ) : null}
        </Abschnitt>
      ) : null}

      {darfAkte && TEXTFELDER.some(([k]) => texte[k].text.trim()) ? (
        <Abschnitt titel="Texte in der Akte ergänzen" an={texteGewaehlt.length > 0} testid="zuordnen-texte"
          onAn={(an) => setTexte(Object.fromEntries(TEXTFELDER.map(([k]) => [k, { ...texte[k], an: an && !!texte[k].text.trim() }])) as typeof texte)}
          zahl="wird mit Quelle an das Feld angehängt">
          {TEXTFELDER.filter(([k]) => texte[k].text.trim()).map(([k, name]) => (
            <div key={k} className="flex flex-col gap-1">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input type="checkbox" checked={texte[k].an} onChange={(e) => setTexte({ ...texte, [k]: { ...texte[k], an: e.target.checked } })} />
                {name}
              </label>
              {texte[k].an ? <Textfeld rows={3} value={texte[k].text} aria-label={name}
                onChange={(e) => setTexte({ ...texte, [k]: { ...texte[k], text: e.target.value } })} /> : null}
            </div>
          ))}
        </Abschnitt>
      ) : null}

      {zuordnen.error && !Object.keys(fehler).length ? <Meldung art="fehler">{zuordnen.error.message}</Meldung> : null}
      {fehler.fehler ? <Meldung art="fehler">{fehler.fehler}</Meldung> : null}
      <div className="flex justify-end gap-2 flex-wrap sticky bottom-0 bg-flaeche py-2 border-t border-rand">
        <Knopf onClick={onAbbrechen}>Abbrechen</Knopf>
        <Knopf variante="pri" icon="haken" laedt={zuordnen.isPending}
          disabled={!darfZuordnen || (quelle ? !etwasGewaehlt : !titel.trim()) || diagnosenOhneCode.length > 0}
          onClick={() => zuordnen.mutate()} data-testid="zuordnen-speichern">
          {quelle ? "Übernehmen" : "In die Akte legen"}{gewaehlteWerte.length && laborAn ? ` + ${gewaehlteWerte.length} Laborwerte` : ""}
          {biaAn && biaGewaehlt.length ? " + BIA" : ""}{diagnosenGewaehlt.length ? ` + ${diagnosenGewaehlt.length} Diagnosen` : ""}
        </Knopf>
      </div>
    </div>
  );
}
