/** Entwurf 4 · Übersicht der Akte: Gewichtsverlauf mit Erfassung, Diagnose/Therapie, Termine, Plan, Kontakte. */
import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, alle, api } from "@/lib/api";
import type { Feldfehler, Seite as ApiSeite } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { useEinstellungen } from "@/lib/daten";
import { datum, eingabeDatum, eingabeZahl, heuteIso, kg, prozent, terminZeit, uhrzeit, zahl, zeitpunkt } from "@/lib/format";
import { GEWICHTSQUELLEN, TERMINARTEN } from "@/lib/typen";
import type { Gewicht, Kontakt, Plan, Termin } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, KnopfLink, Laden, Leer, Meldung, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { GewichtsDiagramm, imZeitraum } from "@/components/GewichtsDiagramm";
import type { Zeitraum } from "@/components/GewichtsDiagramm";
import { Richtext, klartext } from "@/components/Editor";
import { TerminDialog } from "@/components/TerminDialog";
import { useAkte } from "./Akte";
import { AerzteKarte, BezugspersonenKarte } from "./Kontaktpersonen";

const QUELLEN_NEU = ["telefonisch", "ambulanz", "versorger", "arztbrief"];
const ZEITRAEUME: { wert: Zeitraum; text: string }[] = [
  { wert: "y1", text: "12 Monate" }, { wert: "y3", text: "3 Jahre" }, { wert: "y5", text: "5 Jahre" }, { wert: "alle", text: "Alle" },
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
    onSuccess: () => { neuLaden(); melden("Messung korrigiert."); onZu(); },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={!!messung} onOffen={(o) => { if (!o) onZu(); }} titel="Messung korrigieren" breite={520}
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

function GewichtKarte() {
  const { patient, erfassen } = useAkte();
  const location = useLocation();
  const feld = useRef<HTMLInputElement>(null);
  const [zeitraum, setZeitraum] = useState<Zeitraum>("y1");
  const [geglaettet, setGeglaettet] = useState(true);
  const [wert, setWert] = useState("");
  const [am, setAm] = useState(datum(heuteIso()));
  const [quelle, setQuelle] = useState("telefonisch");
  const [liste, setListe] = useState(false);
  const [korrektur, setKorrektur] = useState<Gewicht | null>(null);
  useOhneRechtSchliessen(erfassen, () => setKorrektur(null));
  const einstellungen = useEinstellungen();
  const neuLaden = useAkteNeuLaden();
  const melden = useHinweis();
  const messungen = useQuery({
    queryKey: ["patient", patient.id, "gewichte"],
    queryFn: () => alle<Gewicht>(`gewichte/${abfrage({ patient: patient.id })}`),
  });
  useEffect(() => {
    const st = location.state as { gewicht?: number } | null;
    if (st?.gewicht && feld.current) {
      feld.current.scrollIntoView({ block: "center" });
      feld.current.focus();
    }
  }, [location.state]);
  const speichern = useMutation({
    mutationFn: () => {
      const kgWert = eingabeZahl(wert);
      const iso = eingabeDatum(am);
      if (!kgWert || kgWert === "ungueltig") throw new ApiFehler(400, "", null, { gewicht_kg: "Bitte ein Gewicht eingeben, z. B. 54,6." });
      if (!iso) throw new ApiFehler(400, "", null, { gemessen_am: "Bitte als TT.MM.JJJJ eingeben." });
      return api<Gewicht>("gewichte/", { body: { patient: patient.id, gewicht_kg: kgWert, gemessen_am: iso, quelle } });
    },
    onSuccess: (g) => {
      neuLaden();
      melden(`Gewicht ${kg(g.gewicht_kg)} gespeichert.`);
      setWert("");
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const k = patient.kopf;
  const trend = k?.gewichtstrend;
  const alleWerte = messungen.data ?? [];
  const sichtbar = imZeitraum(alleWerte, zeitraum);
  const e = einstellungen.data;
  const grenzen = e ? `${zahl(e.gewicht_min_kg)}–${zahl(e.gewicht_max_kg)} kg` : "";
  return (
    <Karte className="px-[22px] py-[18px] flex flex-col gap-4" data-testid="gewichtskarte">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-1">
          <h2 className="lbl m-0">Gewichtsverlauf</h2>
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="num text-[1.375rem] font-semibold" data-testid="aktuelles-gewicht">{k?.gewicht ? kg(k.gewicht.kg) : "—"}</span>
            <span className="text-[0.8125rem] gedaempft">
              {k?.gewicht ? `am ${datum(k.gewicht.am)}` : "noch keine Messung"}
              {patient.groesse_cm ? <> · {zahl(patient.groesse_cm)} cm</> : null}
              {k?.bmi != null ? <> · BMI <span className="num">{zahl(k.bmi, 1)}</span></> : null}
              {" · "}<span className="num">{sichtbar.length}</span> Messungen im Zeitraum
            </span>
          </div>
        </div>
      </div>

      {erfassen ? (
        <form className="flex items-end gap-3 flex-wrap" noValidate onSubmit={(ev) => { ev.preventDefault(); speichern.mutate(); }}>
          <Feld label="Neues Gewicht" fehler={f.gewicht_kg}>
            {(p) => (
              <span className="relative block w-[120px]">
                <Eingabe {...p} ref={feld} className="num pr-9" placeholder="0,0" value={wert} onChange={(ev) => setWert(ev.target.value)} inputMode="decimal" />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[0.8125rem] gedaempft pointer-events-none">kg</span>
              </span>
            )}
          </Feld>
          <Feld label="gemessen am" fehler={f.gemessen_am}>{(p) => <Eingabe {...p} className="num w-[120px]" value={am} onChange={(ev) => setAm(ev.target.value)} />}</Feld>
          <Feld label="Quelle" fehler={f.quelle}>
            {(p) => <Auswahl {...p} className="w-[190px]" value={quelle} onChange={(ev) => setQuelle(ev.target.value)}>{QUELLEN_NEU.map((q) => <option key={q} value={q}>{GEWICHTSQUELLEN[q]}</option>)}</Auswahl>}
          </Feld>
          <Knopf type="submit" variante="pri" laedt={speichern.isPending}>Speichern</Knopf>
          <span className="text-xs gedaempft basis-full">Unplausible Werte{grenzen ? ` (außerhalb ${grenzen})` : ""} und Daten in der Zukunft werden abgewiesen.</span>
          {speichern.error && !Object.keys(f).length ? <Meldung art="fehler" className="basis-full">{speichern.error.message}</Meldung> : null}
        </form>
      ) : null}

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Segmente label="Zeitraum" wert={zeitraum} onWahl={setZeitraum} werte={ZEITRAEUME} />
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={geglaettet} onChange={(ev) => setGeglaettet(ev.target.checked)} /> Geglättet
        </label>
      </div>
      {trend ? (
        <div className={cx("meldung flex items-start gap-2.5", trend.warnung ? "warn" : "info")} data-testid="gewichtstrend">
          <Icon name={trend.warnung ? "warnung" : "info"} />
          <span>
            <strong>{prozent(trend.prozent)}</strong> in {e ? zahl(e.gewicht_warnung_monate) : "…"} Monaten ({datum(trend.von)}: {kg(trend.vergleich_kg)}).
            {e ? ` Hinweis ab mehr als ${zahl(e.gewicht_warnung_prozent)} % in ${zahl(e.gewicht_warnung_monate)} Monaten, berechnet aus den echten Messwerten.` : ""}
          </span>
        </div>
      ) : null}
      {messungen.isLoading ? <Laden /> : (
        <GewichtsDiagramm werte={sichtbar} zeitraum={zeitraum} geglaettet={geglaettet}
          vergleich={trend ? { am: trend.von, kg: trend.vergleich_kg } : null}
          beschriftung={`Gewichtsverlauf ${ZEITRAEUME.find((z) => z.wert === zeitraum)!.text}`} />
      )}
      <div className="flex items-center gap-5 text-xs gedaempft flex-wrap">
        <span className="flex items-center gap-1.5"><span className="w-[18px] h-[3px] rounded-sm bg-akzent" />Verlauf</span>
        <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full border-[1.5px] border-gedaempft" />Messwert</span>
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
                <td className="td num">{datum(g.gemessen_am)}{g.datum_ungenau ? <span className="gedaempft"> (ungefähr)</span> : null}</td>
                <td className="td num text-right">{kg(g.gewicht_kg)}</td>
                <td className="td">{GEWICHTSQUELLEN[g.quelle] ?? g.quelle}{g.notiz ? <span className="gedaempft"> · {g.notiz}</span> : null}</td>
                <td className="td text-[0.8125rem] gedaempft">{zeitpunkt(g.erfasst_am)}{g.erfasst_von_name ? ` · ${g.erfasst_von_name}` : ""}</td>
                <td className="td text-right">{erfassen ? <Knopf klein variante="geist" onClick={() => setKorrektur(g)}>Korrigieren</Knopf> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {erfassen ? <KorrekturDialog messung={korrektur} onZu={() => setKorrektur(null)} /> : null}
    </Karte>
  );
}

function TherapieKarte() {
  const { patient, bearbeiten } = useAkte();
  return (
    <Karte className="px-[22px] py-[18px] flex flex-col gap-4">
      <KartenKopf titel="Diagnose und Therapie" rechts={bearbeiten
        ? <KnopfLink to={`/patienten/${patient.id}/therapie`} klein icon="stift">Öffnen und bearbeiten</KnopfLink>
        : <KnopfLink to={`/patienten/${patient.id}/therapie`} klein>Öffnen</KnopfLink>} />
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)] gap-5">
        <div className="flex flex-col gap-1.5 min-w-0"><span className="text-[0.8125rem] font-medium gedaempft">Diagnose</span><Richtext html={patient.diagnose} leer="Noch keine Diagnose eingetragen." /></div>
        <div className="flex flex-col gap-1.5 min-w-0"><span className="text-[0.8125rem] font-medium gedaempft">Therapie</span><Richtext html={patient.therapie} leer="Noch keine Therapie eingetragen." /></div>
      </div>
    </Karte>
  );
}

function TermineKarte() {
  const { patient, erfassen, terminAnlegen } = useAkte();
  const [bearbeiten, setBearbeiten] = useState<Termin | null>(null);
  useOhneRechtSchliessen(erfassen, () => setBearbeiten(null));
  const neuLaden = useAkteNeuLaden();
  const melden = useHinweis();
  const termine = useQuery({
    queryKey: ["patient", patient.id, "termine"],
    queryFn: () => api<ApiSeite<Termin>>(`termine/${abfrage({ patient: patient.id, offen: "true", seitengroesse: 20 })}`),
  });
  const abhaken = useMutation({
    mutationFn: (t: Termin) => api<Termin>(`termine/${t.id}/erledigt/`, { method: "POST" }),
    onSuccess: (t) => { neuLaden(); void termine.refetch(); melden(`„${t.titel}“ erledigt.`); },
  });
  const liste = termine.data?.results ?? [];
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="aktentermine">
      <KartenKopf titel="Termine" rechts={erfassen ? <Knopf klein icon="plus" onClick={terminAnlegen}>Termin</Knopf> : null} />
      {termine.isLoading ? <Laden /> : liste.length ? (
        <ul className="m-0 p-0 list-none flex flex-col">
          {liste.map((t) => (
            <li key={t.id} className="flex items-center gap-2.5 py-1.5 border-b border-rand last:border-b-0 text-sm">
              {erfassen ? (
                <input type="checkbox" aria-label={`Erledigt: ${t.titel}`} disabled={abhaken.isPending} onChange={() => abhaken.mutate(t)} />
              ) : null}
              <span className={cx("num w-[104px] shrink-0 text-[0.84rem]", t.faellig_am < heuteIso() && "text-fehler")}>{terminZeit(t.faellig_am, t.uhrzeit)}</span>
              <Chip>{t.ort_name ?? TERMINARTEN[t.art]}</Chip>
              {erfassen ? (
                <button type="button" className="bg-transparent border-0 p-0 text-left truncate cursor-pointer text-akzent-text"
                  title="Termin ändern" onClick={() => setBearbeiten(t)}>{t.titel}</button>
              ) : <span className="truncate">{t.titel}</span>}
            </li>
          ))}
        </ul>
      ) : <span className="text-sm gedaempft">Keine offenen Termine.</span>}
      <Fehleranzeige fehler={abhaken.error} />
      <TerminDialog offen={!!bearbeiten && erfassen} onOffen={(o) => { if (!o) setBearbeiten(null); }} termin={bearbeiten}
        patientId={patient.id} patientName={`${patient.nachname}, ${patient.vorname}`} />
    </Karte>
  );
}

function PlanKarte() {
  const { patient } = useAkte();
  const { darfBei } = useAuth();
  const aktuell = patient.kopf?.aktueller_plan;
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
            gültig ab {datum(aktuell.gueltig_ab)}
            {plan.data?.freigegeben_am
              ? ` · Freigegeben ${plan.data.abgeschlossen_von_name && plan.data.freigabe_datum ? datum(plan.data.freigabe_datum) : zeitpunkt(plan.data.freigegeben_am)}${plan.data.freigegeben_von_name ? ` · ${plan.data.freigegeben_von_name}` : ""}`
              : ""}
          </span>
        </>
      ) : <span className="text-sm gedaempft">Noch kein freigegebener Plan.</span>}
      <div className="flex gap-2 flex-wrap">
        {!patient.ist_abgeschlossen && darfBei("plaene_anlegen", patient) ? <KnopfLink to={`/patienten/${patient.id}/plaene/neu`} variante="pri" klein>Neuer Plan</KnopfLink> : null}
        <KnopfLink to={`/patienten/${patient.id}/plaene`} klein>Alle Pläne</KnopfLink>
      </div>
    </Karte>
  );
}

function KontakteKarte() {
  const { patient, erfassen } = useAkte();
  const kontakte = useQuery({
    queryKey: ["patient", patient.id, "kontakte", "letzte"],
    queryFn: () => api<ApiSeite<Kontakt>>(`kontakte/${abfrage({ patient: patient.id, seitengroesse: 3 })}`),
  });
  const liste = kontakte.data?.results ?? [];
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="letzte-kontakte">
      <KartenKopf titel="Letzte Kontakte" rechts={erfassen ? <KnopfLink to={`/patienten/${patient.id}/kontakte`} state={{ neu: Date.now() }} klein icon="plus">Kontakt</KnopfLink> : null} />
      {kontakte.isLoading ? <Laden /> : liste.length ? (
        <ul className="m-0 p-0 list-none flex flex-col gap-3">
          {liste.map((k) => (
            <li key={k.id} className={cx("flex flex-col gap-1 text-sm", k.storniert_am && "opacity-60")}>
              <span className="flex gap-2 text-[0.8125rem] gedaempft"><span className="num">{datum(k.zeitpunkt)}, {uhrzeit(k.zeitpunkt)}</span><span>{k.erfasst_von_name}</span>{k.storniert_am ? <Chip>storniert</Chip> : null}</span>
              <span className={cx("line-clamp-2", k.storniert_am && "line-through")}>{klartext(k.text)}</span>
            </li>
          ))}
        </ul>
      ) : <Leer>Noch keine Kontakte.</Leer>}
      <Link to={`/patienten/${patient.id}/kontakte`} className="text-[0.8125rem]">Alle Kontakte</Link>
    </Karte>
  );
}

function StammKarte() {
  const { patient: p } = useAkte();
  const adresse = [p.strasse, [p.plz, p.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  return (
    <Karte className="px-[22px] py-[18px] grid grid-cols-[100px_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm" data-testid="stammdaten">
      <span className="gedaempft">Adresse</span><span>{adresse || "—"}</span>
      <span className="gedaempft">Telefon</span><span className="num">{p.telefon || "—"}</span>
      <span className="gedaempft">E-Mail</span><span className="truncate">{p.email || "—"}</span>
      {p.hausarzt ? <><span className="gedaempft">Hausarzt</span><span title="bisheriger Freitext; Ärzte mit Kontaktdaten unter „Ärzte“">{p.hausarzt}</span></> : null}
      <span className="gedaempft">Überweisung</span><span>{p.ueberweisung_durch || "—"}</span>
      <span className="gedaempft">Größe</span><span className="num">{p.groesse_cm != null ? `${zahl(p.groesse_cm)} cm` : "—"}</span>
    </Karte>
  );
}

export function Uebersicht() {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-5 items-start">
      <div className="flex flex-col gap-5 min-w-0">
        <GewichtKarte />
        <TherapieKarte />
      </div>
      <div className="flex flex-col gap-5 min-w-0">
        <TermineKarte />
        <PlanKarte />
        <KontakteKarte />
        <StammKarte />
        <AerzteKarte />
        <BezugspersonenKarte />
      </div>
    </div>
  );
}
