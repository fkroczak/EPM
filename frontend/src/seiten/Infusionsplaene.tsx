/**
 * Menüpunkt „Infusionspläne“ (Wunsch 02.10.2026): alle Pläne aller Patienten – Entwürfe zur Freigabe, aktuelle Pläne,
 * Pläne älter als der Grenzwert, abgelöste. Öffnen führt in die Akte (Pläne), dort wird bearbeitet und freigegeben.
 */
import { Begriff } from "@/components/ui/Begriff";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { abfrage, api, apiDatei } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { datum, nummer, zahl } from "@/lib/format";
import { ab, useMobil, useStufe } from "@/lib/stufen";
import type { PatientZeile, Plan } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Eingabe, Fehleranzeige, Karte, Knopf, KnopfLink, Laden, Leer, Meldung, Segmente, Seitenkopf } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { PatientWahl } from "@/components/PatientWahl";
import { PdfLeser } from "@/components/PdfAnsicht";
import { PdfDialog } from "@/components/PdfDialog";
import { PlanPdfDialog } from "./akte/Plaene";

type Gruppe = "entwuerfe" | "aktuell" | "alt" | "abgeloest" | "alle";
type Zeile = {
  id: number; patient: number; name: string; nummer: number; ist_test: boolean; patient_abgeschlossen: boolean;
  status: "entwurf" | "aktuell" | "abgeloest"; gueltig_ab: string; kcal: number | null; laufzeit_h: number | null;
  rate_ml_h: number | null; tage_pro_woche: number | null; erstellt_am: string; erstellt_von: string | null;
  freigegeben_am: string | null; freigegeben_von: string | null; pdf: boolean; pdf_sha256: string | null; herkunft: "epm" | "altsystem";
  aelter_als_grenze: boolean; alt_ab: string | null;
};
type Antwort = { zaehler: Record<Gruppe, number>; grenze_monate: number; ergebnisse: Zeile[] };

/** Status; beim Überfahren mit der Maus (und für Bildschirmleser) steht die Frist dabei (Fehlerliste 02.10.2026, 1.2). */
function StatusChip({ z, grenze }: { z: Zeile; grenze: number }) {
  if (z.status === "entwurf") return <Chip art="warn"><Begriff name="entwurf">Entwurf</Begriff></Chip>;
  if (z.status === "abgeloest") return <Chip title="Durch einen neueren Plan abgelöst" className="cursor-help">abgelöst</Chip>;
  const frist = z.alt_ab ? datum(z.alt_ab) : "—";
  return z.aelter_als_grenze
    ? <Chip art="fehler" className="cursor-help" data-testid="plan-frist"
      title={`Frist abgelaufen am ${frist}: gültig seit ${datum(z.gueltig_ab)}, älter als ${grenze} Monate – bitte prüfen und neu freigeben.`}>aktuell, alt</Chip>
    : <Chip art="ok" className="cursor-help" data-testid="plan-frist"
      title={`Frist: ${frist} – ab dann gilt der Plan als alt (älter als ${grenze} Monate).`}>aktuell</Chip>;
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

/**
 * PDF eines Plans neben der Liste (ab 1920 px; Wunsch 10.10.2026: „PDFs einfach einsehbar“): freigegeben = gespeicherte
 * PDF mit Prüfsumme, Entwurf = Ansicht mit der aktiven Dokumentvorlage (Wasserzeichen „ENTWURF“).
 */
function PdfSeitlich({ z, onZu }: { z: Zeile; onZu: () => void }) {
  const original = z.pdf;
  const datei = useQuery({
    queryKey: ["plan", z.id, original ? "pdf" : "ansicht", z.status],
    queryFn: () => apiDatei(original ? `infusionsplaene/${z.id}/pdf/` : `infusionsplaene/${z.id}/ansicht/`),
    staleTime: 0,
    gcTime: 0,
  });
  const pruefung = datei.data?.kopf.get("X-EPM-Pruefung");
  return (
    <Karte className="px-4 py-3.5 flex flex-col gap-2 min-w-0 sticky top-4 h-[calc(100vh-7.5rem)] min-h-[30rem]" data-testid="plan-pdf-seitlich">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col min-w-0">
          <span className="font-semibold truncate">{z.name}</span>
          <span className="text-[0.8125rem] gedaempft">gültig ab {datum(z.gueltig_ab)} · {original
            ? pruefung === "ok" ? "gespeicherte PDF, Prüfsumme stimmt" : pruefung ? "Prüfsumme weicht ab – bitte die Administration informieren" : "gespeicherte PDF"
            : "Ansicht mit der aktiven Dokumentvorlage"}</span>
        </div>
        <span className="flex gap-1.5 shrink-0">
          <KnopfLink klein to={`/patienten/${z.patient}/plaene?plan=${z.id}`}>Öffnen</KnopfLink>
          <Knopf klein variante="geist" icon="x" aria-label="PDF schließen" onClick={onZu} />
        </span>
      </div>
      <Fehleranzeige fehler={datei.error} />
      {datei.isLoading ? <Laden text="PDF wird geladen …" /> : datei.data ? (
        <PdfLeser url={`seitlich-${z.id}-${datei.dataUpdatedAt}`} einpassen laden={() => Promise.resolve(datei.data!.daten)} className="flex-1" />
      ) : null}
    </Karte>
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
  const mobil = useMobil();
  const seitlich = ab(useStufe(), "fhd");
  const infusion = (p: Zeile) => [p.laufzeit_h ? `${zahl(p.laufzeit_h)} h` : null, p.rate_ml_h ? `${zahl(p.rate_ml_h)} ml/h` : null,
    p.tage_pro_woche ? `${p.tage_pro_woche}×/Woche` : null].filter(Boolean).join(" · ");
  return (
    <Seite pfad={[{ text: "Infusionspläne" }]}>
      <Seitenkopf titel="Infusionspläne" unter="Bearbeitet und freigegeben wird in der Akte."
        rechts={anlegen ? <Knopf variante="pri" icon="plus" onClick={() => setNeu(true)}>Neuer Plan</Knopf> : null} />
      <div className="flex items-center gap-3 flex-wrap">
        <Segmente label="Pläne" wert={gruppe} onWahl={(g) => setParams(new URLSearchParams({ gruppe: g }), { replace: true })} werte={[
          { wert: "entwuerfe", text: <>Zur Freigabe {anzahl("entwuerfe")}</> },
          { wert: "aktuell", text: <>Aktuell {anzahl("aktuell")}</> },
          { wert: "alt", text: <>Älter als {grenze} Mon. {anzahl("alt")}</> },
          { wert: "abgeloest", text: <>Abgelöst {anzahl("abgeloest")}</> },
          { wert: "alle", text: <>Alle {anzahl("alle")}</> },
        ]} />
        <Eingabe type="search" aria-label="Patient suchen" placeholder="Patient: Name oder Nr." className="w-full sm:w-[16.25rem]"
          value={suche} onChange={(e) => setSuche(e.target.value)} />
        <label className="flex items-center gap-1.5 text-sm">
          <input type="checkbox" checked={abgeschlossene} onChange={(e) => setAbgeschlossene(e.target.checked)} />
          auch abgeschlossene Akten
        </label>
        {daten.isFetching ? <span className="text-xs gedaempft">wird geladen …</span> : null}
      </div>
      <Fehleranzeige fehler={daten.error} />
      {mobil ? (
        // Telefon (Festlegung 08.10.2026): je Plan eine Karte; „Öffnen“ führt in die Akte, dort wird freigegeben
        daten.isLoading ? <Laden /> : zeilen.length === 0 ? <Karte><Leer>Keine Pläne in dieser Auswahl.</Leer></Karte> : (
          <div role="list" aria-label="Infusionspläne" className="flex flex-col gap-2" data-testid="plan-uebersicht">
            {zeilen.map((p) => (
              <div key={p.id} role="listitem" className="card flex flex-col">
                <Link to={`/patienten/${p.patient}/plaene?plan=${p.id}`} className="px-3.5 pt-3 pb-2 flex flex-col gap-1 no-underline text-tinte rounded-[0.75rem]"
                  aria-label={`Plan von ${p.name} öffnen`}>
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-medium truncate">{p.name}</span>
                    <StatusChip z={p} grenze={grenze} />
                  </span>
                  <span className="text-[0.8125rem] gedaempft">
                    Nr. <span className="num">{nummer(p.nummer)}</span> · gültig ab <span className="num">{datum(p.gueltig_ab)}</span>
                    {p.kcal != null ? <> · <span className="num">{zahl(p.kcal)} kcal</span></> : null}
                  </span>
                  {infusion(p) ? <span className="num text-[0.8125rem]">{infusion(p)}</span> : null}
                  <span className="text-xs gedaempft">
                    {p.freigegeben_am ? <>freigegeben <span className="num">{datum(p.freigegeben_am)}</span>{p.freigegeben_von ? ` · ${p.freigegeben_von}` : ""}</>
                      : <>erstellt <span className="num">{datum(p.erstellt_am)}</span>{p.erstellt_von ? ` · ${p.erstellt_von}` : ""}</>}
                    {p.ist_test ? " · Testpatient" : ""}{p.patient_abgeschlossen ? " · Akte abgeschlossen" : ""}
                  </span>
                </Link>
                <div className="px-3.5 pb-3"><Knopf klein icon="dokument" onClick={() => setPdf(p)} aria-label={`PDF des Plans von ${p.name}`}>PDF</Knopf></div>
              </div>
            ))}
          </div>
        )
      ) : <div className={seitlich && pdf ? "grid grid-cols-[minmax(0,1fr)_minmax(24rem,0.55fr)] gap-[var(--abstand)] items-start" : "contents"}>
      <Karte className="overflow-x-auto">
        {daten.isLoading ? <Laden /> : zeilen.length === 0 ? <Leer>Keine Pläne in dieser Auswahl.</Leer> : (
          <table className="tabelle" data-testid="plan-uebersicht">
            <thead>
              <tr>
                <th className="th">Nr.</th><th className="th">Patient</th><th className="th">Status</th><th className="th">gültig ab</th>
                <th className="th text-right">Energie</th><th className="th">Infusion</th>
                <th className="th">Erstellt</th><th className="th">Freigegeben</th><th className="th"><span className="sr-only">Aktionen</span></th>
              </tr>
            </thead>
            <tbody>
              {zeilen.map((p) => (
                <tr key={p.id}>
                  <td className="td num gedaempft whitespace-nowrap">{nummer(p.nummer)}</td>
                  <td className="td">
                    <Link to={`/patienten/${p.patient}`} className="font-medium no-underline">{p.name}</Link>
                    {p.ist_test ? <Chip art="warn" className="ml-2">Test</Chip> : null}
                    {p.patient_abgeschlossen ? <Chip className="ml-2">abgeschlossen</Chip> : null}
                  </td>
                  <td className="td whitespace-nowrap"><StatusChip z={p} grenze={grenze} /></td>
                  <td className="td num whitespace-nowrap">{datum(p.gueltig_ab)}</td>
                  <td className="td num text-right whitespace-nowrap">{p.kcal != null ? `${zahl(p.kcal)} kcal` : "—"}</td>
                  <td className="td num whitespace-nowrap">{[p.laufzeit_h ? `${zahl(p.laufzeit_h)} h` : null, p.rate_ml_h ? `${zahl(p.rate_ml_h)} ml/h` : null,
                    p.tage_pro_woche ? `${p.tage_pro_woche}×/Woche` : null].filter(Boolean).join(" · ") || "—"}</td>
                  <td className="td text-[0.8125rem] whitespace-nowrap"><span className="num">{datum(p.erstellt_am)}</span>
                    {p.erstellt_von ? <span className="gedaempft"> · {p.erstellt_von}</span> : null}</td>
                  <td className="td text-[0.8125rem] whitespace-nowrap">{p.freigegeben_am
                    ? <><span className="num">{datum(p.freigegeben_am)}</span>{p.freigegeben_von ? <span className="gedaempft"> · {p.freigegeben_von}</span> : null}</>
                    : p.herkunft === "altsystem" ? <span className="gedaempft">aus dem Altsystem</span> : "—"}</td>
                  <td className="td">
                    <div className="flex gap-1.5 justify-end">
                      <Knopf klein icon="dokument" variante={pdf?.id === p.id && seitlich ? "pri" : undefined} onClick={() => setPdf(p)}
                        aria-label={`PDF des Plans von ${p.name}`} title={p.pdf ? "Gespeicherte PDF ansehen" : "Ansicht mit der aktiven Dokumentvorlage"}>PDF</Knopf>
                      <KnopfLink klein to={`/patienten/${p.patient}/plaene?plan=${p.id}`} aria-label={`Plan von ${p.name} öffnen`}>Öffnen</KnopfLink>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Karte>
      {seitlich && pdf ? <PdfSeitlich key={pdf.id} z={pdf} onZu={() => setPdf(null)} /> : null}
      </div>}
      {zeilen.length >= 1000 ? <span className="text-xs gedaempft">Die ersten 1.000 Pläne – bitte die Suche eingrenzen.</span> : null}
      {anlegen ? <NeuerPlanDialog offen={neu} onOffen={setNeu} /> : null}
      {pdf && !seitlich && pdf.pdf ? <PlanPdfDialog plan={{ id: pdf.id, gueltig_ab: pdf.gueltig_ab, pdf_sha256: pdf.pdf_sha256 ?? "" }} offen
        onOffen={(o) => { if (!o) setPdf(null); }} /> : null}
      {pdf && !seitlich && !pdf.pdf ? <PdfDialog offen onOffen={(o) => { if (!o) setPdf(null); }} titel={`Infusionsplan ${pdf.name} · gültig ab ${datum(pdf.gueltig_ab)}`}
        pfad={`infusionsplaene/${pdf.id}/ansicht/`} dateiname={`Infusionsplan-${pdf.nummer}-Ansicht.pdf`} /> : null}
    </Seite>
  );
}
