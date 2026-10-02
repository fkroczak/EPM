/** Entwurf 8 · Infusionspläne: Liste, Ansicht wie PDF, Vergleich mit Vorgänger, Freigabe, Verwerfen. */
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, alle, api, apiDatei } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { datum, eingabeDatum, heuteIso, zahl, zeitpunkt } from "@/lib/format";
import { FREIGABEWEGE } from "@/lib/typen";
import type { Plan, Vergleich } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Leer, Meldung, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { klartext } from "@/components/Editor";
import { PdfLeser } from "@/components/PdfAnsicht";
import { name, useAkte } from "./Akte";

export const STATUS_TEXT: Record<Plan["status"], string> = { entwurf: "Entwurf", aktuell: "aktuell gültig", abgeloest: "abgelöst" };

export function StatusChip({ status }: { status: Plan["status"] }) {
  if (status === "entwurf") return <Chip art="warn"><Icon name="stift" />Entwurf</Chip>;
  if (status === "aktuell") return <Chip art="ok"><Icon name="haken" />aktuell gültig</Chip>;
  return <Chip>abgelöst</Chip>;
}

function kopfText(plan: Plan) {
  const s = plan.status === "entwurf" ? "Entwurf" : plan.status === "aktuell" ? "Aktuell gültig" : "Abgelöst";
  return `${s} · ${datum(plan.gueltig_ab)}`;
}

/** „Ansicht wie PDF“: die echte PDF. Freigegebene Pläne zeigen das gespeicherte Original (Prüfsumme geprüft),
 *  Entwürfe und Pläne ohne gespeicherte PDF werden mit der aktiven Dokumentvorlage gezeichnet – so sieht die Akte
 *  immer genauso aus wie die PDF. */
function PlanAnsicht({ plan }: { plan: Plan }) {
  const original = !!plan.pdf_sha256;
  const pfad = original ? `infusionsplaene/${plan.id}/pdf/` : `infusionsplaene/${plan.id}/ansicht/`;
  const datei = useQuery({
    queryKey: ["plan", plan.id, original ? "pdf" : "ansicht", plan.status],
    queryFn: () => apiDatei(pfad),
    staleTime: 0,
    gcTime: 0,
  });
  const pruefung = datei.data?.kopf.get("X-EPM-Pruefung");
  return (
    <div className="flex flex-col gap-2" data-testid="plan-ansicht">
      <span className="text-[0.8125rem] gedaempft" data-testid="ansicht-herkunft">
        {original ? <>Gespeicherte PDF der Freigabe{pruefung === "ok" ? " · Prüfsumme stimmt" : ""}.</>
          : plan.status === "entwurf" ? "Vorschau mit der aktiven Dokumentvorlage. Die PDF entsteht bei der Freigabe."
          : "Für diesen Plan ist keine PDF gespeichert (vor Einführung der PDF-Erzeugung freigegeben). Ansicht mit der aktiven Dokumentvorlage."}
      </span>
      {pruefung === "abweichend" ? <Meldung art="fehler">Die gespeicherte PDF weicht von der Prüfsumme ab und wurde nach der Freigabe verändert. Bitte die Administration informieren.</Meldung> : null}
      <Fehleranzeige fehler={datei.error} />
      {datei.isLoading ? <Laden text="PDF wird geladen …" /> : datei.data ? (
        <PdfLeser url={`plan-ansicht-${plan.id}-${datei.dataUpdatedAt}`} laden={() => Promise.resolve(datei.data.daten)} className="h-[78vh]" />
      ) : null}
    </div>
  );
}

function VergleichTabelle({ plan, vergleich }: { plan: Plan; vergleich: Vergleich }) {
  if (!vergleich.vorgaenger) return <Meldung>Erster Plan dieses Patienten – es gibt keinen Vorgänger zum Vergleich.</Meldung>;
  return (
    <div className="flex flex-col gap-3" data-testid="planvergleich">
      <div className="text-sm">
        <strong>{vergleich.anzahl_geaendert}</strong> {vergleich.anzahl_geaendert === 1 ? "Wert" : "Werte"} geändert gegenüber dem Plan vom {datum(vergleich.vorgaenger.gueltig_ab)}.
      </div>
      <Karte className="overflow-hidden">
        <table className="tabelle">
          <thead>
            <tr><th className="th">Wert</th><th className="th">Vorher · {datum(vergleich.vorgaenger.gueltig_ab)}</th><th className="th">{kopfText(plan)}</th><th className="th" /></tr>
          </thead>
          <tbody>
            {vergleich.zeilen.map((z) => {
              const text = (v: string | null) => (z.schluessel === "bemerkung" && v ? klartext(v) : v) ?? "—";
              return (
                <tr key={z.schluessel} className={cx(z.geaendert && "bg-warn-bg")}>
                  <td className="td">{z.wert}</td>
                  <td className="td">{text(z.vorher)}</td>
                  <td className={cx("td", z.geaendert && "font-medium")}>{text(z.jetzt)}</td>
                  <td className="td">{z.geaendert ? <Chip art="warn">geändert</Chip> : null}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Karte>
    </div>
  );
}

function FreigabeDialog({ plan, offen, onOffen }: { plan: Plan; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const freigeben = useMutation({
    mutationFn: () => api<Plan>(`infusionsplaene/${plan.id}/freigeben/`, { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden("Plan freigegeben.");
      onOffen(false);
    },
  });
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Plan freigeben" breite={560}
      beschreibung={`Plan gültig ab ${datum(plan.gueltig_ab)} für ${name(patient)}`}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf><Knopf variante="pri" icon="haken" laedt={freigeben.isPending} onClick={() => freigeben.mutate()}>Freigeben</Knopf></>}>
      <ul className="m-0 pl-5 text-sm flex flex-col gap-1.5">
        <li>Der Plan wird zum aktuell gültigen Plan und ist danach unveränderlich.</li>
        <li>Der bisherige Plan wird „abgelöst“ und bleibt im Verlauf erhalten.</li>
        <li>Die PDF wird mit der aktiven Dokumentvorlage erzeugt, mit Prüfsumme gespeichert und erscheint unter „Dokumente“. Sie wird nie neu erzeugt.</li>
      </ul>
      <Fehleranzeige fehler={freigeben.error} />
    </Dialog>
  );
}

/** Freigabe auf Anordnung: Der Mediziner hat den Entwurf außerhalb von EPM freigegeben (z. B. per E-Mail); wer den Plan
 *  hier abschließt, hält fest, wer freigegeben hat, wann, auf welchem Weg – und hängt den Nachweis an. */
function AbschliessenDialog({ plan, offen, onOffen }: { plan: Plan; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [von, setVon] = useState("");
  const [am, setAm] = useState(datum(heuteIso()));
  const [weg, setWeg] = useState("email");
  const [datei, setDatei] = useState<File | null>(null);
  const eingabe = useRef<HTMLInputElement>(null);
  const mediziner = useQuery({
    queryKey: ["freigebende", patient.id],
    queryFn: () => api<{ id: number; name: string }[]>(`infusionsplaene/freigebende/${abfrage({ patient: patient.id })}`),
    enabled: offen,
  });
  useEffect(() => { if (offen) { setAm(datum(heuteIso())); setWeg("email"); setDatei(null); } }, [offen]);
  useEffect(() => {
    if (!von && mediziner.data?.length === 1) setVon(String(mediziner.data[0].id));
  }, [mediziner.data, von]);
  const pflicht = weg === "email" || weg === "schriftlich";
  const abschliessen = useMutation({
    mutationFn: () => {
      const iso = eingabeDatum(am);
      if (!iso) throw new ApiFehler(400, "", null, { freigegeben_am: "Bitte als TT.MM.JJJJ eingeben." });
      const form = new FormData();
      form.append("freigegeben_von", von);
      form.append("freigegeben_am", iso);
      form.append("weg", weg);
      if (datei) form.append("nachweis", datei);
      return api<Plan>(`infusionsplaene/${plan.id}/abschliessen/`, { form });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden("Plan abgeschlossen.");
      onOffen(false);
    },
  });
  const f: Feldfehler = abschliessen.error instanceof ApiFehler ? abschliessen.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Plan nach Freigabe abschließen" breite={600}
      beschreibung={`Plan gültig ab ${datum(plan.gueltig_ab)} für ${name(patient)}`}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" icon="haken" laedt={abschliessen.isPending} disabled={!von || (pflicht && !datei)} onClick={() => abschliessen.mutate()}>Abschließen</Knopf></>}>
      <div className="flex flex-col gap-3" data-testid="plan-abschliessen">
        <span className="text-sm">Der Mediziner hat diesen Entwurf geprüft und außerhalb von EPM freigegeben. Der Plan wird damit zum
          aktuell gültigen Plan und ist danach unveränderlich. Der Freigabevermerk auf der PDF nennt, wer freigegeben und wer
          abgeschlossen hat.</span>
        <div className="grid grid-cols-2 gap-3">
          <Feld label="Freigegeben von" pflicht fehler={f.freigegeben_von} className="col-span-2">
            {(p) => (
              <Auswahl {...p} value={von} onChange={(e) => setVon(e.target.value)}>
                <option value="">— bitte wählen —</option>
                {(mediziner.data ?? []).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </Auswahl>
            )}
          </Feld>
          <Feld label="Freigegeben am" pflicht fehler={f.freigegeben_am}>
            {(p) => <Eingabe {...p} className="num" value={am} onChange={(e) => setAm(e.target.value)} placeholder="TT.MM.JJJJ" />}
          </Feld>
          <Feld label="Weg der Freigabe" pflicht fehler={f.weg}>
            {(p) => (
              <Auswahl {...p} value={weg} onChange={(e) => setWeg(e.target.value)}>
                {["email", "telefon", "persoenlich", "schriftlich"].map((k) => <option key={k} value={k}>{FREIGABEWEGE[k]}</option>)}
              </Auswahl>
            )}
          </Feld>
        </div>
        <div className="feld">
          <span>Nachweis der Freigabe{pflicht ? " *" : " (optional)"}</span>
          <div className="flex items-center gap-2.5 flex-wrap">
            <Knopf icon="hochladen" onClick={() => eingabe.current?.click()}>Datei auswählen</Knopf>
            <span className="text-sm">{datei ? datei.name : <span className="gedaempft">keine Datei gewählt</span>}</span>
            <input ref={eingabe} type="file" hidden aria-label="Nachweis der Freigabe" accept=".pdf,.jpg,.jpeg,.png,.txt,application/pdf,image/jpeg,image/png,text/plain"
              onChange={(e) => setDatei(e.target.files?.[0] ?? null)} />
          </div>
          {f.nachweis ? <span className="fehlertext" role="alert">{f.nachweis}</span>
            : <span className="hinweis">{pflicht ? "z. B. die E-Mail als PDF oder Bildschirmfoto." : "Bei telefonischer oder persönlicher Freigabe ohne Nachweis möglich."}{" "}
              Liegt danach unter „Dokumente“ (Typ „Freigabe“) und bleibt bei diesem Plan.</span>}
        </div>
        <Fehleranzeige fehler={mediziner.error} />
        {abschliessen.error && !Object.keys(f).length ? <Fehleranzeige fehler={abschliessen.error} /> : null}
      </div>
    </Dialog>
  );
}

/** Gespeicherte PDF (F37): vor der Anzeige prüft der Server die Prüfsumme. */
export function PlanPdfDialog({ plan, offen, onOffen }: { plan: Pick<Plan, "id" | "gueltig_ab" | "pdf_sha256">; offen: boolean;
  onOffen: (o: boolean) => void }) {
  const datei = useQuery({
    queryKey: ["plan", plan.id, "pdf"],
    queryFn: () => apiDatei(`infusionsplaene/${plan.id}/pdf/`),
    enabled: offen,
    staleTime: 0,
    gcTime: 0,
  });
  const pruefung = datei.data?.kopf.get("X-EPM-Pruefung");
  const version = datei.data?.kopf.get("X-EPM-Vorlage-Version");
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={`Infusionsplan gültig ab ${datum(plan.gueltig_ab)}`} breite={1100}
      beschreibung={<>Gespeicherte PDF · <a href={`/api/infusionsplaene/${plan.id}/pdf/`} download>Herunterladen</a></>}>
      <div data-testid="plan-pdf" className="flex flex-col gap-3">
        {datei.isLoading ? <Laden /> : null}
        <Fehleranzeige fehler={datei.error} />
        {pruefung === "ok" ? (
          <div className="meldung ok flex items-center gap-2 text-sm" data-testid="pdf-pruefung">
            <Icon name="haken" />Prüfsumme stimmt: unverändert seit der Freigabe{version ? ` · Dokumentvorlage Version ${version}` : ""}.
          </div>
        ) : pruefung ? (
          <Meldung art="fehler"><span data-testid="pdf-pruefung">Die gespeicherte PDF weicht von der Prüfsumme ab und wurde nach der Freigabe verändert. Bitte die Administration informieren.</span></Meldung>
        ) : null}
        {datei.data ? <PdfLeser url={`plan-${plan.id}-${plan.pdf_sha256}`} laden={() => Promise.resolve(datei.data.daten)} className="h-[64vh]" /> : null}
      </div>
    </Dialog>
  );
}

export function Plaene() {
  const { patient } = useAkte();
  const { darfBei } = useAuth();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [modus, setModus] = useState<"ansicht" | "vergleich">("ansicht");
  const [freigabe, setFreigabe] = useState(false);
  const [abschluss, setAbschluss] = useState(false);
  const [verwerfen, setVerwerfen] = useState(false);
  const [pdf, setPdf] = useState(false);
  const qc = useQueryClient();
  const melden = useHinweis();
  const plaene = useQuery({
    queryKey: ["patient", patient.id, "plaene"],
    queryFn: () => alle<Plan>(`infusionsplaene/${abfrage({ patient: patient.id })}`),
  });
  const liste = plaene.data ?? [];
  const gewaehlt = liste.find((p) => String(p.id) === params.get("plan")) ?? liste.find((p) => p.status === "entwurf") ?? liste.find((p) => p.status === "aktuell") ?? liste[0];
  const vergleich = useQuery({
    queryKey: ["patient", patient.id, "plaene", gewaehlt?.id, "vergleich"],
    queryFn: () => api<Vergleich>(`infusionsplaene/${gewaehlt!.id}/vergleich/`),
    enabled: !!gewaehlt,
  });
  const verwerfenM = useMutation({
    mutationFn: () => api(`infusionsplaene/${gewaehlt!.id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      setParams(new URLSearchParams(), { replace: true });
      setVerwerfen(false);
      melden("Entwurf verworfen.");
    },
  });
  const offen = !patient.ist_abgeschlossen;
  const anlegen = offen && darfBei("plaene_anlegen", patient);
  const freigeben = darfBei("plaene_freigeben", patient);
  // Abschließen nach Freigabe außerhalb von EPM: für alle, die nicht selbst freigeben (z. B. Mitarbeiter)
  const abschliessen = offen && !freigeben && darfBei("plaene_abschliessen", patient);
  useOhneRechtSchliessen(anlegen, () => setVerwerfen(false));
  useOhneRechtSchliessen(freigeben, () => setFreigabe(false));
  useOhneRechtSchliessen(abschliessen, () => setAbschluss(false));
  const entwurfDa = liste.some((p) => p.status === "entwurf");

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[300px_minmax(0,1fr)] gap-6 items-start">
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="lbl m-0">{liste.length} {liste.length === 1 ? "Plan" : "Pläne"} · neueste oben</h2>
        </div>
        {anlegen && !entwurfDa ? <Knopf variante="pri" icon="plus" onClick={() => navigate(`/patienten/${patient.id}/plaene/neu`)}>Neuer Plan</Knopf> : null}
        {plaene.isLoading ? <Laden /> : (
          <div className="flex flex-col gap-2" role="list" aria-label="Infusionspläne" data-testid="planliste">
            {liste.map((p) => (
              <button key={p.id} type="button" role="listitem" aria-current={p.id === gewaehlt?.id ? "true" : undefined}
                className={cx("card text-left px-3.5 py-3 flex flex-col gap-1 cursor-pointer border", p.id === gewaehlt?.id ? "border-akzent bg-akzent-weich" : "hover:bg-fein")}
                onClick={() => setParams(new URLSearchParams({ plan: String(p.id) }), { replace: true })}>
                <span className="flex items-center justify-between gap-2"><span className="num font-medium">{datum(p.gueltig_ab)}</span><StatusChip status={p.status} /></span>
                <span className="num text-[0.8125rem]">{zahl(p.kcal)} kcal{p.laufzeit_h != null ? ` · ${zahl(p.laufzeit_h)} h` : ""}{p.tage_pro_woche ? ` · ${p.tage_pro_woche}×/Woche` : ""}</span>
                <span className="text-xs gedaempft">
                  {p.status === "entwurf" ? `angelegt ${zeitpunkt(p.erstellt_am)}${p.erstellt_von_name ? ` · ${p.erstellt_von_name}` : ""}`
                    : `freigegeben ${zeitpunkt(p.freigegeben_am)}${p.freigegeben_von_name ? ` · ${p.freigegeben_von_name}` : ""}`}
                </span>
              </button>
            ))}
          </div>
        )}
        {plaene.data && !liste.length ? <Leer>Noch kein Infusionsplan.</Leer> : null}
        <span className="text-[0.8125rem] gedaempft leading-normal">Freigegebene Pläne sind unveränderlich. Eine Anpassung ist immer ein neuer Plan, der vorherige wird „abgelöst“.</span>
      </div>

      {gewaehlt ? (
        <div className="flex flex-col gap-4 min-w-0" data-testid="plan-detail">
          <Segmente label="Darstellung" wert={modus} onWahl={setModus}
            werte={[{ wert: "ansicht", text: "Ansicht wie PDF" }, { wert: "vergleich", text: "Vergleich mit Vorgänger" }]} className="self-start" />
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex flex-col gap-1">
              <span className="text-lg font-semibold">{kopfText(gewaehlt)}</span>
              <span className="text-[0.8125rem] gedaempft max-w-[70ch]">
                {gewaehlt.status === "entwurf"
                  ? "Entwurf: nur für das Team sichtbar, noch nicht beim Versorger."
                  : gewaehlt.abgeschlossen_von_name
                    ? `Freigegeben am ${datum(gewaehlt.freigabe_datum)} von ${gewaehlt.freigegeben_von_name ?? "—"} (${gewaehlt.freigabe_weg_name}); im System abgeschlossen am ${zeitpunkt(gewaehlt.freigegeben_am)} von ${gewaehlt.abgeschlossen_von_name}.${gewaehlt.pdf_sha256 ? " Die PDF ist mit Prüfsumme gespeichert und wird nie neu erzeugt." : ""}`
                  : `Freigegeben am ${zeitpunkt(gewaehlt.freigegeben_am)}${gewaehlt.freigegeben_von_name ? ` von ${gewaehlt.freigegeben_von_name}` : ""}. ${gewaehlt.pdf_sha256 ? " Die PDF ist mit Prüfsumme gespeichert und wird nie neu erzeugt." : " Für diesen Plan ist keine PDF gespeichert."}`}
              </span>
            </div>
            <div className="flex gap-2 flex-wrap">
              {gewaehlt.status === "entwurf" && anlegen ? <>
                <Knopf icon="stift" onClick={() => navigate(`/patienten/${patient.id}/plaene/${gewaehlt.id}/bearbeiten`)}>Bearbeiten</Knopf>
                <Knopf onClick={() => setVerwerfen(true)}>Verwerfen</Knopf>
                {darfBei("plaene_freigeben", patient) ? <Knopf variante="pri" icon="haken" onClick={() => setFreigabe(true)}>Freigeben</Knopf> : null}
              </> : null}
              {gewaehlt.status === "entwurf" && abschliessen ? <Knopf variante="pri" icon="haken" onClick={() => setAbschluss(true)}>Nach Freigabe abschließen</Knopf> : null}
              {gewaehlt.status !== "entwurf" ? <>
                <Knopf icon="dokument" disabled={!gewaehlt.pdf_sha256} onClick={() => setPdf(true)}
                  title={gewaehlt.pdf_sha256 ? undefined : "Für diesen Plan ist keine PDF gespeichert (vor Einführung der PDF-Erzeugung freigegeben)."}>PDF öffnen</Knopf>
                {anlegen && !entwurfDa ? <Knopf icon="plus" onClick={() => navigate(`/patienten/${patient.id}/plaene/neu?vorlage=${gewaehlt.id}`)}>Als Vorlage für neuen Plan</Knopf> : null}
              </> : null}
            </div>
          </div>
          {modus === "ansicht" ? <PlanAnsicht key={gewaehlt.id} plan={gewaehlt} />
            : vergleich.isLoading ? <Laden /> : vergleich.data ? <VergleichTabelle plan={gewaehlt} vergleich={vergleich.data} />
            : <Fehleranzeige fehler={vergleich.error} />}
          {freigeben ? <FreigabeDialog plan={gewaehlt} offen={freigabe} onOffen={setFreigabe} /> : null}
          {abschliessen ? <AbschliessenDialog plan={gewaehlt} offen={abschluss} onOffen={setAbschluss} /> : null}
          {gewaehlt.pdf_sha256 ? <PlanPdfDialog plan={gewaehlt} offen={pdf} onOffen={setPdf} /> : null}
          <Dialog offen={verwerfen && anlegen} onOffen={setVerwerfen} titel="Entwurf verwerfen" breite={480}
            beschreibung="Der Entwurf wird gelöscht. Im Verlauf der Akte bleibt sichtbar, dass es ihn gab."
            fuss={<><Knopf onClick={() => setVerwerfen(false)}>Abbrechen</Knopf><Knopf variante="dng" laedt={verwerfenM.isPending} onClick={() => verwerfenM.mutate()}>Verwerfen</Knopf></>}>
            <Fehleranzeige fehler={verwerfenM.error} />
          </Dialog>
        </div>
      ) : null}
    </div>
  );
}
