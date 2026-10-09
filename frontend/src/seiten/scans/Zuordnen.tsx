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
 */
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuswahl, useLaborparameter } from "@/lib/daten";
import { datum, eingabeZahl, nummer } from "@/lib/format";
import type { PatientZeile, Scan, ScanBiaWert, ScanDiagnose, ScanLaborwert } from "@/lib/typen";
import { PatientWahl } from "@/components/PatientWahl";
import { Auswahl, Chip, Eingabe, Feld, Knopf, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { useHinweis } from "@/components/ui/hinweise";
import { ARTEN, UNSICHER } from "./hilfen";

export type Stelle = { seite: number; box: number[] } | null;
/** Gewähltes Feld: Ein Klick auf ein Wort im Bild schreibt dessen Text hinein */
export type Ziel = { schluessel: string; name: string; setzen: (text: string, stelle: Stelle) => void } | null;

type Wahl = { id: number; nummer: number; nachname: string; vorname: string; geburtsdatum: string | null; ist_test: boolean };

type LaborZeile = { an: boolean; parameter: number | null; freitext_name: string; wert: string; wert_text: string;
  einheit: string; referenz_von: string; referenz_bis: string; quelle: ScanLaborwert | null; stelle?: Stelle };

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

export function Zuordnen({ scan, onStelle, onFertig, onAbbrechen, ziel = null, onZiel = () => {} }: {
  scan: Scan; onStelle: (s: Stelle) => void; onFertig: (patientId: number, dokumentId: number) => void; onAbbrechen: () => void;
  ziel?: Ziel; onZiel?: (z: Ziel) => void;
}) {
  const a = scan.auswertung ?? {};
  const arten = a.arten ?? [];
  const { darf, darfBei, ich } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const katalog = useLaborparameter();
  const typen = useAuswahl("dokumenttyp");

  const [patient, setPatient] = useState<Wahl | null>(null);
  const [titel, setTitel] = useState(scan.titel);
  const [typ, setTyp] = useState("");
  const [dokDatum, setDokDatum] = useState(scan.dokumentdatum ?? "");
  const [notiz, setNotiz] = useState("");
  const [original, setOriginal] = useState(false);

  const [laborAn, setLaborAn] = useState(arten.includes("labor"));
  const [abnahme, setAbnahme] = useState(a.datum_quelle === "abnahme" || a.datum_quelle === "befund" ? a.datum ?? "" : a.datum ?? "");
  const [laborName, setLaborName] = useState(a.labor?.name ?? "");
  const [beurteilung, setBeurteilung] = useState(arten.includes("labor") ? a.abschnitte?.verlauf ?? "" : "");
  const [werte, setWerte] = useState<LaborZeile[]>(() => (a.labor?.werte ?? []).map((w) => ({
    an: w.vorschlag, parameter: w.parameter, freitext_name: w.freitext_name, wert: komma(w.wert), wert_text: w.wert_text,
    einheit: w.einheit, referenz_von: komma(w.referenz_von), referenz_bis: komma(w.referenz_bis), quelle: w,
  })));

  const biaQuelle = a.bia?.werte ?? {};
  const [biaAn, setBiaAn] = useState(arten.includes("bia"));
  const [gemessen, setGemessen] = useState(arten.includes("bia") ? a.datum ?? "" : "");
  const [bia, setBia] = useState<Record<string, string>>(() => Object.fromEntries(
    BIA_FELDER.map(([k]) => [k, (biaQuelle[k]?.vorschlag ?? false) ? komma(biaQuelle[k]?.wert) : ""])));
  const [gewichtUebernehmen, setGewichtUebernehmen] = useState(true);
  const [biaBeurteilung, setBiaBeurteilung] = useState(() => (a.bia?.weitere ?? [])
    .map((w) => `${w.name}: ${komma(w.wert)}${w.einheit ? ` ${w.einheit}` : ""}`).join("\n"));

  const darfAkte = darf("akten_bearbeiten");
  const [diagnosen, setDiagnosen] = useState<(ScanDiagnose & { an: boolean })[]>(() =>
    (a.diagnosen ?? []).map((d) => ({ ...d, an: d.vorschlag && darfAkte })));
  const [texte, setTexte] = useState<Record<Textfeldname, { an: boolean; text: string }>>(() => ({
    diagnose: { an: false, text: a.abschnitte?.diagnosen ?? "" },
    therapie: { an: false, text: a.abschnitte?.therapie ?? "" },
    empfehlung: { an: false, text: a.abschnitte?.procedere ?? "" },
  }));

  // Vorschlag übernehmen, sobald er da ist (nur der erste, eindeutige)
  const vorschlaege = scan.vorschlaege ?? [];
  useEffect(() => {
    if (!patient && vorschlaege.length >= 1 && (vorschlaege.length === 1 || vorschlaege[0].punkte > vorschlaege[1].punkte)) {
      const v = vorschlaege[0];
      if (!v.abgeschlossen) {
        const [nach, ...vor] = v.name.split(", ");
        setPatient({ id: v.id, nummer: v.nummer, nachname: nach, vorname: vor.join(", "), geburtsdatum: v.geburtsdatum, ist_test: v.ist_test });
      }
    }
  }, [scan.id]); // eslint-disable-line react-hooks/exhaustive-deps

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
  const texteGewaehlt = TEXTFELDER.filter(([k]) => texte[k].an && texte[k].text.trim());

  const zuordnen = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { patient: patient!.id, titel, typ: typ || null, datum: dokDatum || null, notiz, original };
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
      return api<{ dokument: number; patient: number; laborbefund?: number; bia?: number; diagnosen?: number[] }>(
        `scans/${scan.id}/zuordnen/`, { body });
    },
    onSuccess: (e) => {
      const teile = [e.laborbefund ? `${gewaehlteWerte.length} Laborwerte` : "", e.bia ? "BIA-Messung" : "",
        e.diagnosen?.length ? `${e.diagnosen.length} Diagnosen` : ""].filter(Boolean);
      melden(`Als Dokument in die Akte gelegt${teile.length ? ` – übernommen: ${teile.join(", ")}` : ""}.`);
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
    referenz_von: "", referenz_bis: "", quelle: null });
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
        <h3 className="m-0 text-base font-semibold grow">Einem Patienten zuordnen</h3>
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
            <Knopf klein variante="geist" onClick={() => setPatient(null)}>ändern</Knopf>
          </div>
        ) : (
          <>
            {vorschlaege.length ? (
              <div className="flex flex-wrap gap-2" data-testid="patient-vorschlaege">
                {vorschlaege.map((v) => (
                  <button key={v.id} type="button" disabled={v.abgeschlossen}
                    className="btn sec klein" title={v.abgeschlossen ? "Akte ist abgeschlossen" : `erkannt an: ${v.grund}`}
                    onClick={() => {
                      const [nach, ...vor] = v.name.split(", ");
                      setPatient({ id: v.id, nummer: v.nummer, nachname: nach, vorname: vor.join(", "), geburtsdatum: v.geburtsdatum, ist_test: v.ist_test });
                    }}>
                    <Icon name="patienten" groesse={14} />{v.name} <span className="gedaempft">({v.grund})</span>
                  </button>
                ))}
              </div>
            ) : null}
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

      {/* 2. Dokument */}
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

      {/* 3. Werte */}
      {arten.length ? (
        <span className="text-[0.8125rem] gedaempft">Erkannt: {arten.map((x) => ARTEN[x] ?? x).join(", ")}. Bitte jeden Wert mit dem Original vergleichen –
          ein Klick auf eine Zeile zeigt die Stelle links.</span>
      ) : null}

      {!arten.length ? (
        <span className="text-[0.8125rem] gedaempft">Die Art des Dokuments wurde nicht erkannt. Laborbefund oder BIA-Messung lassen
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
                        {q ? <><span className="truncate block">{q.zeile}</span><Sicherheit c={q.sicherheit} hinweise={q.hinweise} /></>
                          : <span>von Hand</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div>
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
                    gelesen: {q.erkannt_als} <Sicherheit c={q.sicherheit} hinweise={q.hinweise} />{q.hinweise?.length ? ` · ${q.hinweise.join(" · ")}` : ""}
                  </span> : undefined}>
                  {(p) => <Eingabe {...p} className={cx("num", istZiel(`bia-${k}`) && "scan-feld-ziel")} inputMode="decimal" value={bia[k] ?? ""}
                    onFocus={() => zielFuer(`bia-${k}`, name, (text) => setBia((alt) => ({ ...alt, [k]: zahlAus(text) })),
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
        <Abschnitt titel="Diagnosen mit ICD-Code übernehmen" an={diagnosenGewaehlt.length > 0}
          onAn={(an) => setDiagnosen(diagnosen.map((d) => ({ ...d, an })))} testid="zuordnen-diagnosen"
          zahl={darfAkte ? `${diagnosenGewaehlt.length} von ${diagnosen.length}` : "nur mit Recht „Akten bearbeiten“"}>
          <ul className="m-0 p-0 list-none flex flex-col gap-1.5">
            {diagnosen.map((d, i) => (
              <li key={d.icd_code} className="flex items-start gap-2 text-sm" onClick={() => onStelle(d.box ? { seite: d.seite, box: d.box } : null)}>
                <input type="checkbox" className="mt-1" checked={d.an} disabled={!darfAkte}
                  onChange={(e) => setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, an: e.target.checked } : x)))} />
                <Eingabe value={d.bezeichnung} aria-label="Bezeichnung" className="grow min-w-0"
                  onChange={(e) => setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, bezeichnung: e.target.value } : x)))} />
                <Eingabe value={d.icd_code} aria-label="ICD-Code" className="num w-20"
                  onChange={(e) => setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, icd_code: e.target.value } : x)))} />
                <Auswahl value={d.kennzeichen} aria-label="Zusatzkennzeichen" className="w-20"
                  onChange={(e) => setDiagnosen(diagnosen.map((x, j) => (j === i ? { ...x, kennzeichen: e.target.value as ScanDiagnose["kennzeichen"] } : x)))}>
                  <option value="G">G</option><option value="V">V</option><option value="Z">Z</option><option value="A">A</option>
                </Auswahl>
              </li>
            ))}
          </ul>
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
      <div className="flex justify-end gap-2 flex-wrap sticky bottom-0 bg-flaeche py-2 border-t border-rand">
        <Knopf onClick={onAbbrechen}>Abbrechen</Knopf>
        <Knopf variante="pri" icon="haken" laedt={zuordnen.isPending} disabled={!darfZuordnen || !titel.trim()}
          onClick={() => zuordnen.mutate()} data-testid="zuordnen-speichern">
          In die Akte legen{gewaehlteWerte.length && laborAn ? ` + ${gewaehlteWerte.length} Laborwerte` : ""}
          {biaAn && biaGewaehlt.length ? " + BIA" : ""}{diagnosenGewaehlt.length ? ` + ${diagnosenGewaehlt.length} Diagnosen` : ""}
        </Knopf>
      </div>
    </div>
  );
}
