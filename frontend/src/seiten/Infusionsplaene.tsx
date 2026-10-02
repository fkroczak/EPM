/**
 * Menüpunkt „Infusionspläne“ (Wunsch 02.10.2026): alle Pläne aller Patienten – Entwürfe zur Freigabe, aktuelle Pläne,
 * Pläne älter als der Grenzwert, abgelöste. Öffnen führt in die Akte (Pläne), dort wird bearbeitet und freigegeben.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { datum, nummer, relativ, zahl } from "@/lib/format";
import type { PatientZeile, Plan } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Eingabe, Fehleranzeige, Karte, Knopf, KnopfLink, Laden, Leer, Meldung, Segmente, Seitenkopf } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { PatientWahl } from "@/components/PatientWahl";
import { PlanPdfDialog } from "./akte/Plaene";

type Gruppe = "entwuerfe" | "aktuell" | "alt" | "abgeloest" | "alle";
type Zeile = {
  id: number; patient: number; name: string; nummer: number; ist_test: boolean; patient_abgeschlossen: boolean;
  status: "entwurf" | "aktuell" | "abgeloest"; gueltig_ab: string; kcal: number | null; laufzeit_h: number | null;
  rate_ml_h: number | null; tage_pro_woche: number | null; erstellt_am: string; erstellt_von: string | null;
  freigegeben_am: string | null; freigegeben_von: string | null; pdf: boolean; pdf_sha256: string | null; herkunft: "epm" | "altsystem";
  aelter_als_grenze: boolean;
};
type Antwort = { zaehler: Record<Gruppe, number>; grenze_monate: number; ergebnisse: Zeile[] };

function StatusChip({ z }: { z: Zeile }) {
  if (z.status === "entwurf") return <Chip art="warn">Entwurf</Chip>;
  if (z.status === "abgeloest") return <Chip>abgelöst</Chip>;
  return z.aelter_als_grenze ? <Chip art="fehler">aktuell, alt</Chip> : <Chip art="ok">aktuell</Chip>;
}

/** Neuer Plan: Patient wählen; gibt es schon einen Entwurf, diesen öffnen statt einen zweiten anzulegen. */
function NeuerPlanDialog({ offen, onOffen }: { offen: boolean; onOffen: (o: boolean) => void }) {
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const navigate = useNavigate();
  const entwurf = useQuery({
    queryKey: ["infusionsplaene", "entwurf-von", patient?.id],
    queryFn: () => api<ApiSeite<Plan>>(`infusionsplaene/${abfrage({ patient: patient!.id, status: "entwurf" })}`),
    enabled: !!patient,
  });
  useEffect(() => { if (!offen) setPatient(null); }, [offen]);
  const vorhanden = entwurf.data?.results[0];
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Neuer Infusionsplan" beschreibung="Für welchen Patienten? Der Plan wird mit dem aktuellen Plan vorbelegt."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        {vorhanden ? (
          <Knopf variante="pri" onClick={() => navigate(`/patienten/${patient!.id}/plaene/${vorhanden.id}/bearbeiten`)}>Entwurf öffnen</Knopf>
        ) : (
          <Knopf variante="pri" disabled={!patient || entwurf.isLoading} onClick={() => navigate(`/patienten/${patient!.id}/plaene/neu`)}>
            Weiter zum Plan</Knopf>
        )}
      </>}>
      <div className="feld">
        <label htmlFor="neuer-plan-patient">Patient</label>
        <PatientWahl id="neuer-plan-patient" wert={patient} onWahl={setPatient} />
      </div>
      {vorhanden ? <Meldung art="warn">Für diesen Patienten gibt es schon einen Entwurf (gültig ab {datum(vorhanden.gueltig_ab)}). Bitte diesen
        bearbeiten oder verwerfen.</Meldung> : null}
      <Fehleranzeige fehler={entwurf.error} />
    </Dialog>
  );
}

export function Infusionsplaene() {
  const { darf } = useAuth();
  const [params, setParams] = useSearchParams();
  const gruppe = (["entwuerfe", "aktuell", "alt", "abgeloest", "alle"].includes(params.get("gruppe") ?? "") ? params.get("gruppe")
    : "aktuell") as Gruppe;
  const [suche, setSuche] = useState("");
  const [abgeschlossene, setAbgeschlossene] = useState(false);
  const [neu, setNeu] = useState(false);
  const [pdf, setPdf] = useState<Zeile | null>(null);
  const anlegen = darf("plaene_anlegen");
  useOhneRechtSchliessen(anlegen, () => setNeu(false));
  const werte = { gruppe, suche: suche.trim() || undefined, abgeschlossene: abgeschlossene ? 1 : undefined };
  const daten = useQuery({
    queryKey: ["infusionsplaene", "uebersicht", werte],
    queryFn: () => api<Antwort>(`infusionsplaene/uebersicht/${abfrage(werte)}`),
    placeholderData: (vorher: Antwort | undefined) => vorher,
  });
  const z = daten.data?.zaehler;
  const grenze = daten.data?.grenze_monate ?? 12;
  const zeilen = daten.data?.ergebnisse ?? [];
  const anzahl = (g: Gruppe) => <span className="num opacity-70">{z ? z[g] : "…"}</span>;
  return (
    <Seite pfad={[{ text: "Infusionspläne" }]}>
      <Seitenkopf titel="Infusionspläne" unter="Alle Pläne aller Patienten. Bearbeitet und freigegeben wird in der Akte."
        rechts={anlegen ? <Knopf variante="pri" icon="plus" onClick={() => setNeu(true)}>Neuer Plan</Knopf> : null} />
      <div className="flex items-center gap-3 flex-wrap">
        <Segmente label="Pläne" wert={gruppe} onWahl={(g) => setParams(new URLSearchParams({ gruppe: g }), { replace: true })} werte={[
          { wert: "entwuerfe", text: <>Zur Freigabe {anzahl("entwuerfe")}</> },
          { wert: "aktuell", text: <>Aktuell {anzahl("aktuell")}</> },
          { wert: "alt", text: <>Älter als {grenze} Mon. {anzahl("alt")}</> },
          { wert: "abgeloest", text: <>Abgelöst {anzahl("abgeloest")}</> },
          { wert: "alle", text: <>Alle {anzahl("alle")}</> },
        ]} />
        <Eingabe type="search" aria-label="Patient suchen" placeholder="Patient: Name oder Nr." className="w-[260px]"
          value={suche} onChange={(e) => setSuche(e.target.value)} />
        <label className="flex items-center gap-1.5 text-sm">
          <input type="checkbox" checked={abgeschlossene} onChange={(e) => setAbgeschlossene(e.target.checked)} />
          auch abgeschlossene Akten
        </label>
        {daten.isFetching ? <span className="text-xs gedaempft">wird geladen …</span> : null}
      </div>
      <Fehleranzeige fehler={daten.error} />
      <Karte className="overflow-x-auto">
        {daten.isLoading ? <Laden /> : zeilen.length === 0 ? <Leer>Keine Pläne in dieser Auswahl.</Leer> : (
          <table className="tabelle" data-testid="plan-uebersicht">
            <thead>
              <tr>
                <th className="th">Nr.</th><th className="th">Patient</th><th className="th">Status</th><th className="th">gültig ab</th>
                <th className="th text-right">Energie</th><th className="th text-right">Laufzeit · Rate</th><th className="th">Tage/Woche</th>
                <th className="th">Erstellt</th><th className="th">Freigegeben</th><th className="th" />
              </tr>
            </thead>
            <tbody>
              {zeilen.map((p) => (
                <tr key={p.id}>
                  <td className="td num gedaempft">{nummer(p.nummer)}</td>
                  <td className="td">
                    <Link to={`/patienten/${p.patient}`} className="font-medium no-underline">{p.name}</Link>
                    {p.ist_test ? <Chip art="warn" className="ml-2">Test</Chip> : null}
                    {p.patient_abgeschlossen ? <Chip className="ml-2">abgeschlossen</Chip> : null}
                  </td>
                  <td className="td"><StatusChip z={p} /></td>
                  <td className="td num">{datum(p.gueltig_ab)}</td>
                  <td className="td num text-right">{p.kcal != null ? `${zahl(p.kcal)} kcal` : "—"}</td>
                  <td className="td num text-right">{p.laufzeit_h ? `${zahl(p.laufzeit_h)} h` : "—"}{p.rate_ml_h ? ` · ${zahl(p.rate_ml_h)} ml/h` : ""}</td>
                  <td className="td num">{p.tage_pro_woche ? `${p.tage_pro_woche}×` : "—"}</td>
                  <td className="td text-[0.8125rem]">{relativ(p.erstellt_am)}<br /><span className="gedaempft">{p.erstellt_von ?? "—"}</span></td>
                  <td className="td text-[0.8125rem]">{p.freigegeben_am ? <>{relativ(p.freigegeben_am)}<br /><span className="gedaempft">{p.freigegeben_von ?? "—"}</span></>
                    : p.herkunft === "altsystem" ? <span className="gedaempft">aus dem Altsystem</span> : "—"}</td>
                  <td className="td">
                    <div className="flex gap-1.5 justify-end">
                      {p.pdf ? <Knopf klein icon="dokument" onClick={() => setPdf(p)} aria-label={`PDF des Plans von ${p.name}`}>PDF</Knopf> : null}
                      <KnopfLink klein to={`/patienten/${p.patient}/plaene?plan=${p.id}`} aria-label={`Plan von ${p.name} öffnen`}>Öffnen</KnopfLink>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Karte>
      {zeilen.length >= 1000 ? <span className="text-xs gedaempft">Die ersten 1.000 Pläne – bitte die Suche eingrenzen.</span> : null}
      {anlegen ? <NeuerPlanDialog offen={neu} onOffen={setNeu} /> : null}
      {pdf ? <PlanPdfDialog plan={{ id: pdf.id, gueltig_ab: pdf.gueltig_ab, pdf_sha256: pdf.pdf_sha256 ?? "" }} offen
        onOffen={(o) => { if (!o) setPdf(null); }} /> : null}
    </Seite>
  );
}
