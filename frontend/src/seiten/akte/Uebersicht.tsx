/** Entwurf 4 · Übersicht der Akte: Gewichtsverlauf mit Erfassung, Diagnose/Therapie, Termine, Plan, Kontakte. */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, alle, api } from "@/lib/api";
import type { Feldfehler, Seite as ApiSeite } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { useEinstellungen } from "@/lib/daten";
import { datum, eingabeDatum, eingabeZahl, heuteIso, kg, prozent, terminZeit, uhrzeit, zahl, zeitpunkt } from "@/lib/format";
import { GEWICHTSQUELLEN, TERMINARTEN, VERSICHERUNGSARTEN } from "@/lib/typen";
import type { Gewicht, Kontakt, Plan, Termin } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, KnopfLink, Laden, Leer, Meldung, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { GewichtsDiagramm, imZeitraum } from "@/components/GewichtsDiagramm";
import type { Zeitraum } from "@/components/GewichtsDiagramm";
import { Richtext, klartext } from "@/components/Editor";
import { TerminDialog } from "@/components/TerminDialog";
import { FirmaMarke } from "@/components/FirmenWahl";
import { useAkte } from "./Akte";
import { BefundeKurz } from "./Befunde";
import { DiagnosenKurz } from "./Diagnosen";
import { StummKarte } from "@/components/HinweisChips";
import { AkteAufEinenBlick, FUELLT } from "@/components/AkteAufEinenBlick";
import { AerzteKarte, BezugspersonenKarte } from "./Kontaktpersonen";
import { KeinPlanHinweis, PlanPdfDialog } from "./Plaene";
import { KarteOderAbschnitt } from "./Aktenseite";
import { RASTER_SPALTEN, useStufe } from "@/lib/stufen";
import { Bereich, Bereiche } from "@/components/ui/bereiche";

const ZEITRAEUME: { wert: Zeitraum; text: string }[] = [
  { wert: "y1", text: "12 Monate" }, { wert: "y3", text: "3 Jahre" }, { wert: "y5", text: "5 Jahre" }, { wert: "alle", text: "Alle" },
];
/** in der Karte mit fester Höhe knapp, damit Zeitraum und „Geglättet“ in eine Zeile passen */
const ZEITRAEUME_KURZ: { wert: Zeitraum; text: string }[] = [
  { wert: "y1", text: "12 Mon." }, { wert: "y3", text: "3 J." }, { wert: "y5", text: "5 J." }, { wert: "alle", text: "Alle" },
];

function useAkteNeuLaden() {
  const qc = useQueryClient();
  const { patient } = useAkte();
  return () => {
    void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    void qc.invalidateQueries({ queryKey: ["patienten"] });
    void qc.invalidateQueries({ queryKey: ["startseite"] });
  };
}

function KorrekturDialog({ messung, onZu }: { messung: Gewicht | null; onZu: () => void }) {
  const [wert, setWert] = useState("");
  const [am, setAm] = useState("");
  const [quelle, setQuelle] = useState("telefonisch");
  const [notiz, setNotiz] = useState("");
  const neuLaden = useAkteNeuLaden();
  const melden = useHinweis();
  useEffect(() => {
    if (messung) {
      setWert(zahl(messung.gewicht_kg, 1));
      setAm(datum(messung.gemessen_am));
      setQuelle(messung.quelle);
      setNotiz(messung.notiz);
    }
  }, [messung]);
  const speichern = useMutation({
    mutationFn: () => {
      const kgWert = eingabeZahl(wert);
      const iso = eingabeDatum(am);
      if (!kgWert || kgWert === "ungueltig") throw new ApiFehler(400, "", null, { gewicht_kg: "Bitte eine Zahl eingeben, z. B. 54,6." });
      if (!iso) throw new ApiFehler(400, "", null, { gemessen_am: "Bitte als TT.MM.JJJJ eingeben." });
      return api<Gewicht>(`gewichte/${messung!.id}/`, { method: "PATCH", body: { gewicht_kg: kgWert, gemessen_am: iso, quelle, notiz } });
    },
    onSuccess: () => { neuLaden(); melden("Messung gespeichert."); onZu(); },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={!!messung} onOffen={(o) => { if (!o) onZu(); }} titel="Messung bearbeiten" breite={520}
      beschreibung="Die bisherige Fassung bleibt im Verlauf der Akte sichtbar."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf><Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <div className="grid grid-cols-2 gap-3">
        <Feld label="Gewicht (kg)" fehler={f.gewicht_kg}>{(p) => <Eingabe {...p} className="num" value={wert} onChange={(e) => setWert(e.target.value)} />}</Feld>
        <Feld label="gemessen am" fehler={f.gemessen_am}>{(p) => <Eingabe {...p} className="num" value={am} onChange={(e) => setAm(e.target.value)} />}</Feld>
        <Feld label="Quelle" fehler={f.quelle}>
          {(p) => <Auswahl {...p} value={quelle} onChange={(e) => setQuelle(e.target.value)}>{Object.entries(GEWICHTSQUELLEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Auswahl>}
        </Feld>
        <Feld label="Notiz" fehler={f.notiz}>{(p) => <Eingabe {...p} value={notiz} onChange={(e) => setNotiz(e.target.value)} />}</Feld>
      </div>
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

function GewichtKarte({ startZeitraum = "y1", fuellen }: { startZeitraum?: Zeitraum;
  /** Karte mit fester Höhe (Übersicht im Fenster): das Diagramm füllt den Platz */
  fuellen?: boolean }) {
  // Erfassen nur noch über den Dialog „Gewicht erfassen“ wie im Aktenkopf (ein Dialog je Sache, 08.10.2026);
  // die letzte Messung lässt sich direkt bearbeiten (Klick auf den Wert oder „Bearbeiten“)
  const { patient, erfassen, gewichtErfassen } = useAkte();
  const [zeitraum, setZeitraum] = useState<Zeitraum>(startZeitraum);
  const [geglaettet, setGeglaettet] = useState(true);
  const [liste, setListe] = useState(false);
  const [korrektur, setKorrektur] = useState<Gewicht | null>(null);
  useOhneRechtSchliessen(erfassen, () => setKorrektur(null));
  const einstellungen = useEinstellungen();
  // Größe der Zeichenfläche (nur in der Karte mit fester Höhe gebraucht)
  const diagrammRef = useRef<HTMLDivElement>(null);
  const [diagrammMasse, setDiagrammMasse] = useState({ breite: 0, hoehe: 0 });
  useLayoutEffect(() => {
    const el = diagrammRef.current;
    if (!fuellen || !el) return;
    const messen = () => setDiagrammMasse((alt) => {
      const neu = { breite: Math.floor(el.clientWidth), hoehe: Math.floor(el.clientHeight) };
      return alt.breite === neu.breite && alt.hoehe === neu.hoehe ? alt : neu;
    });
    messen();
    const beobachter = new ResizeObserver(messen);
    beobachter.observe(el);
    return () => beobachter.disconnect();
  });
  const messungen = useQuery({
    queryKey: ["patient", patient.id, "gewichte"],
    queryFn: () => alle<Gewicht>(`gewichte/${abfrage({ patient: patient.id })}`),
  });
  const k = patient.kopf;
  const trend = k?.gewichtstrend;
  const alleWerte = messungen.data ?? [];
  const sichtbar = imZeitraum<Gewicht>(alleWerte, zeitraum);
  const e = einstellungen.data;
  // letzte Messung = jüngstes Messdatum, bei gleichem Datum die zuletzt erfasste
  const letzte = [...alleWerte].sort((x, y) => (y.gemessen_am.localeCompare(x.gemessen_am) || y.erfasst_am.localeCompare(x.erfasst_am)))[0];
  const wert = erfassen && letzte ? (
    <button type="button" className={cx("num font-semibold bg-transparent border-0 p-0 cursor-pointer text-inherit hover:underline whitespace-nowrap shrink-0", fuellen ? "text-lg" : "text-[1.375rem]")}
      data-testid="aktuelles-gewicht" title="Letzte Messung bearbeiten" onClick={() => setKorrektur(letzte)}>
      {k?.gewicht ? kg(k.gewicht.kg) : kg(letzte.gewicht_kg)}</button>
  ) : <span className={cx("num font-semibold whitespace-nowrap shrink-0", fuellen ? "text-lg" : "text-[1.375rem]")} data-testid="aktuelles-gewicht">{k?.gewicht ? kg(k.gewicht.kg) : "—"}</span>;
  const zusatz = (
    <span className={cx("text-[0.8125rem] gedaempft", fuellen && "truncate min-w-0")}
      title={fuellen && k?.gewicht ? `am ${datum(k.gewicht.am)} · ${sichtbar.length} Messungen im Zeitraum` : undefined}>
      {k?.gewicht ? `am ${datum(k.gewicht.am)}` : "noch keine Messung"}
      {patient.groesse_cm ? <> · {zahl(patient.groesse_cm)} cm</> : null}
      {k?.bmi != null ? <> · BMI <span className="num">{zahl(k.bmi, 1)}</span></> : null}
      {" · "}<span className="num">{sichtbar.length}</span> Messungen im Zeitraum
    </span>
  );
  return (
    <Karte className={cx("flex flex-col @container", fuellen ? "px-4 py-3 gap-2" : "px-4 sm:px-[1.375rem] py-4 sm:py-[1.125rem] gap-4")} data-testid="gewichtskarte">
      {fuellen ? (
        // Karte mit fester Höhe: Kopf in einer Zeile, damit das Diagramm Platz hat
        <div className="flex items-center justify-between gap-3 min-w-0">
          <div className="flex items-baseline gap-2.5 min-w-0">
            {/* schmale Karte (Tablet): Überschrift und Knopftext weichen dem Wert */}
            <h2 className="lbl m-0 shrink-0 @max-[22rem]:sr-only">Gewicht</h2>{wert}{zusatz}
          </div>
          {erfassen ? <Knopf klein icon="plus" className="shrink-0" onClick={() => gewichtErfassen()}
            title="Gewicht erfassen"><span className="@max-[22rem]:sr-only">Gewicht</span></Knopf> : null}
        </div>
      ) : (
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex flex-col gap-1">
            <h2 className="lbl m-0">Gewichtsverlauf</h2>
            <div className="flex items-baseline gap-3 flex-wrap">{wert}{zusatz}</div>
          </div>
          {erfassen ? (
            <div className="flex items-center gap-2">
              {letzte ? <Knopf klein icon="stift" onClick={() => setKorrektur(letzte)} title={`Messung vom ${datum(letzte.gemessen_am)} bearbeiten`}>Bearbeiten</Knopf> : null}
              <Knopf klein icon="plus" onClick={() => gewichtErfassen()}>Gewicht</Knopf>
            </div>
          ) : null}
        </div>
      )}

      <div className={cx("flex items-center justify-between gap-3", fuellen ? "flex-nowrap" : "flex-wrap")}>
        <Segmente label="Zeitraum" wert={zeitraum} onWahl={setZeitraum} werte={fuellen ? ZEITRAEUME_KURZ : ZEITRAEUME} />
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={geglaettet} onChange={(ev) => setGeglaettet(ev.target.checked)} /> <span className={fuellen ? "@max-[22rem]:sr-only" : undefined}>Geglättet</span>
        </label>
      </div>
      {/* nur als Warnung – die Veränderung steht ohnehin im Kopf der Akte (Wunsch 10.10.2026: weniger Infos) */}
      {trend?.warnung ? (
        <div className="meldung flex items-start gap-2.5 warn" data-testid="gewichtstrend">
          <Icon name="warnung" />
          <span>
            <strong>{prozent(trend.prozent)}</strong> in {e ? zahl(e.gewicht_warnung_monate) : "…"} Monaten ({datum(trend.von)}: {kg(trend.vergleich_kg)}).
            {e ? ` Hinweis ab mehr als ${zahl(e.gewicht_warnung_prozent)} % in ${zahl(e.gewicht_warnung_monate)} Monaten, berechnet aus den echten Messwerten.` : ""}
          </span>
        </div>
      ) : null}
      {messungen.isLoading ? <Laden /> : (
        <div className={fuellen ? "gewicht-fuellen" : undefined} ref={diagrammRef}><GewichtsDiagramm<Gewicht> masse={fuellen ? diagrammMasse : undefined} werte={sichtbar} zeitraum={zeitraum} geglaettet={geglaettet} onPunkt={erfassen ? (w) => setKorrektur(w) : undefined}
          vergleich={trend ? { am: trend.von, kg: trend.vergleich_kg } : null}
          beschriftung={`Gewichtsverlauf ${ZEITRAEUME.find((z) => z.wert === zeitraum)!.text}`} /></div>
      )}
      <div className="flex items-center gap-5 text-xs gedaempft flex-wrap">
        {fuellen ? null : <>
          <span className="flex items-center gap-1.5"><span className="w-[1.125rem] h-[0.1875rem] rounded-sm bg-akzent" />Verlauf</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full border-[1.5px] border-gedaempft" />Messwert</span>
        </>}
        {trend ? <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full border-2 border-warn" />Vergleichswert vor {e ? zahl(e.gewicht_warnung_monate) : "…"} Monaten</span> : null}
        <button type="button" className="ml-auto bg-transparent border-0 p-0 text-akzent-text cursor-pointer text-xs" aria-expanded={liste}
          onClick={() => setListe(!liste)}>{liste ? "Messwerte ausblenden" : `Messwerte anzeigen (${alleWerte.length})`}</button>
      </div>
      {liste ? (
        <table className="tabelle" data-testid="messwerte">
          <thead><tr><th className="th">gemessen am</th><th className="th text-right">Gewicht</th><th className="th">Quelle</th><th className="th">erfasst</th><th className="th" /></tr></thead>
          <tbody>
            {alleWerte.map((g) => (
              <tr key={g.id}>
                <td className="td num">{datum(g.gemessen_am)}{g.datum_ungenau ? <span className="gedaempft"> (ungefähr)</span> : null}<FirmaMarke kurz={g.firma_kurz} className="ml-1.5" /></td>
                <td className="td num text-right">{kg(g.gewicht_kg)}</td>
                <td className="td">{GEWICHTSQUELLEN[g.quelle] ?? g.quelle}{g.notiz ? <span className="gedaempft"> · {g.notiz}</span> : null}</td>
                <td className="td text-[0.8125rem] gedaempft">{zeitpunkt(g.erfasst_am)}{g.erfasst_von_name ? ` · ${g.erfasst_von_name}` : ""}</td>
                <td className="td text-right">{erfassen ? <Knopf klein variante="geist" onClick={() => setKorrektur(g)}>Bearbeiten</Knopf> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {erfassen ? <KorrekturDialog messung={korrektur} onZu={() => setKorrektur(null)} /> : null}
    </Karte>
  );
}

function medikamenteText(anzahl: number) {
  return anzahl ? `Medikamentenplan: ${anzahl === 1 ? "1 Medikament" : `${anzahl} Medikamente`}` : "Medikamentenplan: noch kein Medikament";
}

/** Diagnosen, Therapie und Empfehlung auf einen Blick – je ein Klick in den Reiter (Wunsch 10.10.2026: „einfacher
 *  erreichbar“). Ganz zu lesen und zu bearbeiten in den Reitern. */
function BehandlungKarte() {
  const { patient, bearbeiten } = useAkte();
  const icon = bearbeiten ? "stift" : undefined;
  return (
    <Karte className="px-4 py-3.5 flex flex-col gap-3" data-testid="behandlung">
      <KartenKopf titel="Diagnosen, Therapie, Empfehlung" />
      <section className="karten-abschnitt flex flex-col gap-1.5 min-w-0">
        <div className="flex items-center justify-between gap-2"><h3 className="lbl m-0 text-[0.8125rem]">Diagnosen</h3>
          <KnopfLink to={`/patienten/${patient.id}/diagnosen`} klein variante="geist" icon={icon}>Diagnosen</KnopfLink></div>
        <DiagnosenKurz patientId={patient.id} />
        {/* Medikamentenplan (Wunsch 11.10.2026): nur die Zahl, der Plan selbst steht im Reiter */}
        <Link to={`/patienten/${patient.id}/medikamente`} className="text-[0.8125rem] font-medium self-start" data-testid="medikamente-kurz">
          {medikamenteText(patient.kopf?.zaehler.medikamente ?? 0)}
        </Link>
      </section>
      <section className="karten-abschnitt flex flex-col gap-1.5 min-w-0">
        <div className="flex items-center justify-between gap-2"><h3 className="lbl m-0 text-[0.8125rem]">Therapie</h3>
          <KnopfLink to={`/patienten/${patient.id}/therapie`} klein variante="geist" icon={icon}>Therapie</KnopfLink></div>
        <Richtext html={patient.therapie} leer="Noch keine Therapie eingetragen." className="text-sm" />
      </section>
      <section className="karten-abschnitt flex flex-col gap-1.5 min-w-0" data-testid="empfehlung-kurz">
        <div className="flex items-center justify-between gap-2"><h3 className="lbl m-0 text-[0.8125rem]">Empfehlung</h3>
          <KnopfLink to={`/patienten/${patient.id}/empfehlung`} klein variante="geist" icon={icon}>Empfehlung</KnopfLink></div>
        <Richtext html={patient.empfehlung} leer="Noch keine Empfehlung eingetragen." className="text-sm" />
      </section>
    </Karte>
  );
}

export function TermineKarte({ rahmenlos }: { rahmenlos?: boolean } = {}) {
  const { patient, erfassen, terminAnlegen, terminOeffnen } = useAkte();
  const [bearbeiten, setBearbeiten] = useState<Termin | null>(null);
  useOhneRechtSchliessen(erfassen, () => setBearbeiten(null));
  const neuLaden = useAkteNeuLaden();
  const melden = useHinweis();
  const termine = useQuery({
    queryKey: ["patient", patient.id, "termine"],
    queryFn: () => api<ApiSeite<Termin>>(`termine/${abfrage({ patient: patient.id, offen: "true", ausgeblendet: "false", seitengroesse: 20 })}`),
  });
  const abhaken = useMutation({
    mutationFn: (t: Termin) => api<Termin>(`termine/${t.id}/erledigt/`, { method: "POST" }),
    onSuccess: (t) => { neuLaden(); void termine.refetch(); melden(`„${t.titel}“ erledigt.`); },
  });
  const liste = termine.data?.results ?? [];
  return (
    <KarteOderAbschnitt rahmenlos={rahmenlos} className="px-5 py-4 flex flex-col gap-3" testid="aktentermine">
      <KartenKopf titel="Termine" rechts={erfassen ? <Knopf klein icon="plus" onClick={terminAnlegen}>Termin</Knopf> : null} />
      {termine.isLoading ? <Laden /> : liste.length ? (
        <ul className="m-0 p-0 list-none flex flex-col">
          {liste.map((t) => (
            <li key={t.id} className="flex items-center gap-2.5 py-1.5 border-b border-rand last:border-b-0 text-sm">
              {erfassen ? (
                <input type="checkbox" title="Erledigt" aria-label={`Erledigt: ${t.titel}`} disabled={abhaken.isPending} onChange={() => abhaken.mutate(t)} />
              ) : null}
              <span className={cx("num w-[6.5rem] shrink-0 text-[0.84rem]", t.faellig_am < heuteIso() && "text-fehler")}>{terminZeit(t.faellig_am, t.uhrzeit)}</span>
              <Chip>{t.ort_name ?? TERMINARTEN[t.art]}</Chip>
              <FirmaMarke kurz={t.firma_kurz} />
              {erfassen ? (
                <button type="button" className="bg-transparent border-0 p-0 text-left truncate cursor-pointer text-akzent-text"
                  title="Termin bearbeiten" onClick={() => setBearbeiten(t)}>{t.titel}</button>
              ) : <button type="button" className="bg-transparent border-0 p-0 text-left truncate cursor-pointer text-akzent-text"
                title="Im Kalender zeigen" onClick={() => terminOeffnen(t.id)}>{t.titel}</button>}
            </li>
          ))}
        </ul>
      ) : <span className="text-sm gedaempft">Keine offenen Termine.</span>}
      <Fehleranzeige fehler={abhaken.error} />
      <TerminDialog offen={!!bearbeiten && erfassen} onOffen={(o) => { if (!o) setBearbeiten(null); }} termin={bearbeiten}
        patientId={patient.id} patientName={`${patient.nachname}, ${patient.vorname}`} />
    </KarteOderAbschnitt>
  );
}

function PlanKarte() {
  const { patient } = useAkte();
  const { darfBei } = useAuth();
  const [pdf, setPdf] = useState(false);
  const aktuell = patient.kopf?.aktueller_plan;
  const entwurf = patient.kopf?.plan_entwurf;
  const plan = useQuery({
    queryKey: ["patient", patient.id, "plan", aktuell?.id],
    queryFn: () => api<Plan>(`infusionsplaene/${aktuell!.id}/`),
    enabled: !!aktuell,
  });
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="aktueller-plan">
      <KartenKopf titel="Aktueller Infusionsplan" rechts={aktuell ? <Chip art="ok"><Icon name="haken" />gültig</Chip> : null} />
      {aktuell ? (
        <>
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col"><span className="num text-lg font-semibold">{zahl(aktuell.kcal)}</span><span className="text-xs gedaempft">kcal</span></div>
            <div className="flex flex-col"><span className="num text-lg font-semibold">{aktuell.laufzeit_h != null ? `${zahl(aktuell.laufzeit_h)} h` : "—"}</span><span className="text-xs gedaempft">Laufzeit</span></div>
            <div className="flex flex-col"><span className="num text-lg font-semibold">{plan.data?.tage_pro_woche != null ? `${plan.data.tage_pro_woche}×` : "—"}</span><span className="text-xs gedaempft">pro Woche</span></div>
          </div>
          <span className="text-[0.8125rem]" data-testid="plan-volumen">
            Gesamtvolumen <span className="num">{plan.data?.volumen_summe_ml != null ? `${zahl(plan.data.volumen_summe_ml)} ml` : "—"}</span>
            {" · "}Rate <span className="num">{plan.data?.rate_ml_h != null ? `${zahl(plan.data.rate_ml_h)} ml/h` : "—"}</span>
          </span>
          <span className="text-[0.8125rem] gedaempft">
            gültig ab {datum(aktuell.gueltig_ab)}<FirmaMarke kurz={plan.data?.firma_kurz} className="ml-1.5" />
            {plan.data?.freigegeben_am
              ? ` · Freigegeben ${plan.data.abgeschlossen_von_name && plan.data.freigabe_datum ? datum(plan.data.freigabe_datum) : zeitpunkt(plan.data.freigegeben_am)}${plan.data.freigegeben_von_name ? ` · ${plan.data.freigegeben_von_name}` : ""}`
              : ""}
          </span>
        </>
      ) : null}
      <KeinPlanHinweis />
      {/* Ein offener Entwurf ist das, was als Nächstes zu tun ist: freigeben oder weiter bearbeiten */}
      {entwurf ? (
        <div className="meldung warn flex items-center justify-between gap-2 text-[0.8125rem]" data-testid="plan-entwurf-hinweis">
          <span>Entwurf vom {datum(entwurf.erstellt_am)} wartet auf Freigabe.</span>
          <KnopfLink to={`/patienten/${patient.id}/plaene?plan=${entwurf.id}`} klein>Ansehen</KnopfLink>
        </div>
      ) : null}
      <div className="flex gap-2 flex-wrap">
        {/* PDF mit einem Klick (Wunsch 10.10.2026: „PDFs einfach einsehbar“) */}
        {plan.data?.pdf_sha256 ? <Knopf klein icon="dokument" onClick={() => setPdf(true)}>PDF ansehen</Knopf> : null}
        {!patient.ist_abgeschlossen && darfBei("plaene_anlegen", patient) && !entwurf ? <KnopfLink to={`/patienten/${patient.id}/plaene/neu`} variante="pri" klein>Neuer Plan</KnopfLink> : null}
        <KnopfLink to={`/patienten/${patient.id}/plaene`} klein>Alle Pläne</KnopfLink>
      </div>
      {plan.data?.pdf_sha256 ? <PlanPdfDialog plan={plan.data} offen={pdf} onOffen={setPdf} /> : null}
    </Karte>
  );
}

function KontakteKarte({ rahmenlos }: { rahmenlos?: boolean } = {}) {
  const { patient, erfassen, kontaktErfassen } = useAkte();
  const kontakte = useQuery({
    queryKey: ["patient", patient.id, "kontakte", "letzte"],
    queryFn: () => api<ApiSeite<Kontakt>>(`kontakte/${abfrage({ patient: patient.id, seitengroesse: 3 })}`),
  });
  const liste = kontakte.data?.results ?? [];
  return (
    <KarteOderAbschnitt rahmenlos={rahmenlos} className="px-5 py-4 flex flex-col gap-3" testid="letzte-kontakte">
      <KartenKopf titel="Letzte Kontakte" rechts={erfassen ? <Knopf klein icon="plus" onClick={() => kontaktErfassen()}>Kontakt</Knopf> : null} />
      {kontakte.isLoading ? <Laden /> : liste.length ? (
        <ul className="m-0 p-0 list-none flex flex-col gap-3">
          {liste.map((k) => (
            <li key={k.id} className={cx("flex flex-col gap-1 text-sm", k.storniert_am && "opacity-60")}>
              <span className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[0.8125rem] gedaempft"><span className="num whitespace-nowrap">{datum(k.zeitpunkt)}, {uhrzeit(k.zeitpunkt)}</span><span className="whitespace-nowrap">{k.erfasst_von_name}</span><FirmaMarke kurz={k.firma_kurz} />{k.art_name ? <span className="whitespace-nowrap">· {k.art_name}</span> : null}{k.storniert_am ? <Chip>storniert</Chip> : null}</span>
              <span className={cx("line-clamp-2", k.storniert_am && "line-through")}>{klartext(k.text)}</span>
            </li>
          ))}
        </ul>
      ) : <Leer>Noch keine Kontakte.</Leer>}
      <Link to={`/patienten/${patient.id}/kontakte`} className="text-[0.8125rem]">Alle Kontakte</Link>
    </KarteOderAbschnitt>
  );
}

function StammKarte({ rahmenlos }: { rahmenlos?: boolean } = {}) {
  const { patient: p, bearbeiten, stammdatenBearbeiten } = useAkte();
  const adresse = [p.strasse, [p.plz, p.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  return (
    <KarteOderAbschnitt rahmenlos={rahmenlos} testid="stammdaten"
      className="px-4 sm:px-[1.375rem] py-4 sm:py-[1.125rem] grid grid-cols-[minmax(6.25rem,max-content)_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm"
      abschnittKlasse="grid grid-cols-[minmax(6.25rem,max-content)_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-sm">
      <div className="col-span-2 pb-1 flex items-center justify-between gap-2">
        <h2 className="lbl m-0">Anschrift und Kontakt</h2>
        {bearbeiten ? <Knopf klein variante="geist" icon="stift" onClick={stammdatenBearbeiten}>Bearbeiten</Knopf> : null}
      </div>
      <span className="gedaempft">Adresse</span><span>{adresse || "—"}</span>
      <span className="gedaempft">Telefon</span><span className="num">{p.telefon || "—"}</span>
      {/* Telefon 2 und Krankenkasse seit 03.10.2026 sichtbar (Klärung U5) */}
      <span className="gedaempft">Telefon 2</span><span className="num" data-testid="telefon2">{p.telefon2 || "—"}</span>
      <span className="gedaempft">E-Mail</span><span className="truncate">{p.email || "—"}</span>
      <span className="gedaempft">Versicherung</span><span data-testid="krankenkasse">
        {[VERSICHERUNGSARTEN[p.versicherungsart] !== "nicht erfasst" ? VERSICHERUNGSARTEN[p.versicherungsart] : "",
          p.krankenkasse].filter(Boolean).join(" · ") || "—"}</span>
      <span className="gedaempft">Versichertennummer</span><span className="num" data-testid="versichertennummer">{p.versichertennummer || "—"}</span>
      {p.hausarzt ? <><span className="gedaempft">Hausarzt</span><span title="bisheriger Freitext; Ärzte mit Kontaktdaten unter „Ärzte“">{p.hausarzt}</span></> : null}
      <span className="gedaempft">Überweisung</span><span>{p.ueberweisung_durch || "—"}</span>
      <span className="gedaempft">Größe</span><span className="num">{p.groesse_cm != null ? `${zahl(p.groesse_cm)} cm` : "—"}</span>
    </KarteOderAbschnitt>
  );
}

/**
 * Was beim Altdaten-Import nicht ins vorgesehene Feld passte, hat der Import im früheren Feld „Bemerkung“
 * abgelegt – im Originalwortlaut, damit nichts verloren geht. Die Bemerkung als Arbeitsfeld gibt es seit dem
 * 07.10.2026 nicht mehr (nie benutzt); diese Hinweise erscheinen nur hier, nur lesbar und nur, wenn es welche gibt.
 */
function ImportHinweise() {
  const { patient } = useAkte();
  if (!klartext(patient.bemerkung).trim()) return null;
  return (
    <Karte className="p-4 flex flex-col gap-2" data-testid="import-hinweise">
      <KartenKopf titel="Hinweise aus der Altdaten-Übernahme"
        unter="Werte, die beim Import nicht ins vorgesehene Feld passten – im Wortlaut des Altsystems." />
      <Richtext html={patient.bemerkung} className="text-sm" />
    </Karte>
  );
}

/** Letzter Laborbefund und letzte BIA-Messung mit Weg in die Reiter (Wünsche 06./07.10.2026, F112–F114, F121). */
function BefundeKarte() {
  const { patient } = useAkte();
  return (
    <Karte className="px-4 sm:px-[1.375rem] py-4 sm:py-[1.125rem] flex flex-col gap-4" data-testid="karte-befunde">
      <KartenKopf titel="Labor und BIA" rechts={<>
        <KnopfLink to={`/patienten/${patient.id}/labor`} klein>Labor</KnopfLink>
        <KnopfLink to={`/patienten/${patient.id}/bia`} klein>BIA</KnopfLink>
      </>} />
      <BefundeKurz patientId={patient.id} />
    </Karte>
  );
}

/** Spalten des Rasters nach der tatsächlichen Breite der Fläche: etwa die Breiten, die der Inhalt bei 1366/1920/2560 px
 *  hat (1366 px: drei Spalten, 1920 px: vier). */
function spaltenFuerBreite(px: number): number {
  // Tablet (1024 px, Fläche ~940 px): zwei breite Spalten (Entscheidung der Praxis 10.10.2026, F190)
  return px < 560 ? 1 : px < 1100 ? 2 : px < 1560 ? 3 : px < 2200 ? 4 : 5;
}

/** Kleinste sinnvolle Höhe einer Kartenzeile; darunter scrollt die Fläche statt die Karten zu quetschen */
const MIN_ZEILE = 170;

/**
 * Breite der Übersicht und – wenn die Akte das Fenster füllt – die Höhe, die für das Raster bleibt (Fläche unter den
 * Reitern abzüglich Hinweiskarten darüber).
 */
function useFlaeche() {
  const ref = useRef<HTMLDivElement>(null);
  const raster = useRef<HTMLDivElement>(null);
  const [mass, setMass] = useState({ breite: 0, hoehe: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    const flaeche = el?.closest<HTMLElement>(".akte-flaeche");
    if (!el) return;
    const messen = () => {
      const fuellt = !!flaeche && window.matchMedia(FUELLT).matches;
      let hoehe = 0;
      if (fuellt && raster.current) {
        const stil = getComputedStyle(flaeche!);
        const innen = flaeche!.clientHeight - parseFloat(stil.paddingTop) - parseFloat(stil.paddingBottom);
        hoehe = Math.floor(innen - (raster.current.getBoundingClientRect().top - el.getBoundingClientRect().top));
      }
      setMass({ breite: Math.round(el.clientWidth), hoehe });
    };
    messen();
    const beobachter = new ResizeObserver(messen);
    beobachter.observe(el);
    if (flaeche) beobachter.observe(flaeche);
    window.addEventListener("resize", messen);
    return () => { beobachter.disconnect(); window.removeEventListener("resize", messen); };
  }, []);
  return [ref, raster, mass] as const;
}

/**
 * Übersicht der Akte (Wunsch 10.10.2026: „deutlich entschlanken, im besten Fall ohne Scrollen“): sechs Karten statt
 * neun – Gewicht, Infusionsplan, Diagnosen/Therapie/Empfehlung, Kontakte und Termine, Labor und BIA, Personen und
 * Anschrift. Ab 1280 × 600 px und mindestens drei Spalten füllen sie in zwei Reihen genau das Fenster; was nicht
 * hineinpasst, scrollt in der Karte (wie die Kacheln der Startseite). Jede Karte behält das Menü für Breite und Höhe
 * (je Person gespeichert); wer selbst eine Größe wählt, bekommt sie – dann darf die Fläche auch scrollen.
 */
export function Uebersicht() {
  const stufe = useStufe();
  const { patient, bearbeiten } = useAkte();
  const [flaeche, rasterRef, mass] = useFlaeche();
  const spalten = mass.breite > 0 ? Math.min(RASTER_SPALTEN.qhd, spaltenFuerBreite(mass.breite)) : RASTER_SPALTEN[stufe];
  const abstand = 12; // --abstand (0,75 rem bei 16 px); genau genug für die Aufteilung
  // Das Raster zählt in 8-px-Zeilen (components/ui/bereiche.tsx): die Höhe so wählen, dass zwei Reihen samt Abstand
  // genau aufgehen, sonst ragt die zweite Reihe um ein paar Pixel über das Fenster
  const zeile = spalten >= 3 && mass.hoehe > 0 ? Math.floor(mass.hoehe / 2 / 8) * 8 - abstand : 0;
  const fuellen = zeile >= MIN_ZEILE;
  const h = fuellen ? 1 : 0;
  return (
    <div className="stapel flex flex-col gap-4 min-w-0" ref={flaeche} data-testid="akte-uebersicht" data-fuellt={fuellen ? "1" : undefined}>
      {/* KI-Entwurf „Auf einen Blick“: was seit dem letzten Termin dazukam (14.11.2026); nur mit ki_ansehen, einklappbar */}
      <AkteAufEinenBlick patient={patient.id} />
      {/* Weggeklickte Hinweise stehen hier und lassen sich zurückholen (Wunsch 07.10.2026, F119) */}
      <StummKarte patientId={patient.id} aenderbar={bearbeiten} />
      <ImportHinweise />
      <div ref={rasterRef} className="min-w-0">
        <Bereiche seite="akte_uebersicht" spalten={spalten} testid="uebersicht-stufe"
          style={fuellen ? ({ "--raster-zeile": `${zeile}px` } as CSSProperties) : undefined}>
          {/* Reihenfolge nach Bedeutung: Verlauf und Behandlung vorn, Kontaktdaten zuletzt */}
          <Bereich id="gewicht" titel="Gewichtsverlauf" standard={{ breite: fuellen && spalten < 4 ? 1 : 2, hoehe: h }}>
            <GewichtKarte startZeitraum={stufe === "qhd" ? "y3" : "y1"} fuellen={fuellen} /></Bereich>
          <Bereich id="plan" titel="Aktueller Infusionsplan" standard={{ hoehe: h }}><PlanKarte /></Bereich>
          <Bereich id="therapie" titel="Diagnosen, Therapie, Empfehlung" standard={{ breite: fuellen ? 1 : 2, hoehe: h }}><BehandlungKarte /></Bereich>
          <Bereich id="kontakte" titel="Kontakte und Termine" standard={{ breite: spalten === 4 ? 2 : 1, hoehe: h }}>
            <Karte className="px-4 py-3.5 flex flex-col gap-3" data-testid="kontakte-termine">
              <KontakteKarte rahmenlos />
              <TermineKarte rahmenlos />
            </Karte>
          </Bereich>
          <Bereich id="befunde" titel="Labor und BIA" standard={{ hoehe: h }}><BefundeKarte /></Bereich>
          <Bereich id="personen" titel="Personen und Anschrift" standard={{ hoehe: h }}>
            <Karte className="px-4 py-3.5 flex flex-col gap-3" data-testid="personen">
              <BezugspersonenKarte rahmenlos />
              <AerzteKarte rahmenlos />
              <StammKarte rahmenlos />
            </Karte>
          </Bereich>
        </Bereiche>
      </div>
    </div>
  );
}
