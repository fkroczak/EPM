/** Entwurf 8 · Infusionspläne: Liste, Ansicht wie PDF, Vergleich mit Vorgänger, Freigabe, Verwerfen. */
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { abfrage, alle, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBriefkopf } from "@/lib/daten";
import { datum, kg, zahl, zeitpunkt } from "@/lib/format";
import type { Plan, Vergleich } from "@/lib/typen";
import { Chip, Fehleranzeige, Karte, Knopf, Laden, Leer, Meldung, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Logo } from "@/components/layout/logo";
import { Richtext, klartext } from "@/components/Editor";
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

/** „Ansicht wie PDF“: Aufbau wie der gedruckte Plan (die gespeicherte PDF selbst folgt mit F37/F51) */
function PdfAnsicht({ plan, vergleich }: { plan: Plan; vergleich: Vergleich }) {
  const { patient } = useAkte();
  const briefkopf = useBriefkopf();
  const a = briefkopf.data ? briefkopf.data.absender[briefkopf.data.aktiv] : null;
  const zeilen = vergleich.zeilen.filter((z) => z.schluessel !== "bemerkung");
  const bemerkung = plan.bemerkung;
  const wasserzeichen = plan.status === "entwurf" ? "ENTWURF" : patient.ist_test ? "TESTDATEN" : "";
  return (
    <div className="pdf-blatt relative mx-auto w-full max-w-[720px] px-12 py-10 flex flex-col gap-5 overflow-hidden" data-testid="pdf-ansicht">
      {wasserzeichen ? (
        <div aria-hidden="true" className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <span className="text-[96px] font-bold tracking-[.12em] text-black/[.06] -rotate-[30deg]">{wasserzeichen}</span>
        </div>
      ) : null}
      <div className="flex items-start justify-between gap-6">
        <Logo className="h-[64px] w-[220px]" version={briefkopf.data?.logo.sha256} />
        {a ? (
          <div className="flex flex-col items-end text-[11px] leading-snug text-[#3b3953]">
            <span>{a.strasse} · {a.plz} {a.ort}</span>
            <span>{[a.telefon && `Telefon ${a.telefon}`, a.fax && `Fax ${a.fax}`].filter(Boolean).join(" · ")}</span>
            <span>{[a.email, a.internet].filter(Boolean).join(" · ")}</span>
          </div>
        ) : null}
      </div>
      <div className="flex items-baseline justify-between border-b border-[#1b1932] pb-1.5">
        <span className="text-xl font-semibold">Infusionsplan</span>
        <span className="text-sm">gültig ab {datum(plan.gueltig_ab)}</span>
      </div>
      <div className="grid grid-cols-[90px_minmax(0,1fr)_80px_minmax(0,1fr)] gap-x-2.5 gap-y-0.5 text-[13px]">
        <span className="text-[#5d5b72]">Patient</span><span className="font-medium">{name(patient)}</span>
        <span className="text-[#5d5b72]">Geboren</span><span>{datum(patient.geburtsdatum)}</span>
        <span className="text-[#5d5b72]">Gewicht</span><span>{patient.kopf?.gewicht ? kg(patient.kopf.gewicht.kg) : "—"}</span>
        <span className="text-[#5d5b72]">Versorger</span><span>{patient.kopf?.versorger ?? "—"}</span>
      </div>
      <table className="w-full border-collapse text-[13px]">
        <tbody>
          {zeilen.map((z) => (
            <tr key={z.schluessel} className="border-b border-[#e6e5ee]">
              <td className="py-1 pr-3 w-[38%] text-[#3b3953]">{z.wert}</td>
              <td className="py-1">{z.jetzt ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {bemerkung ? <div className="text-[13px] flex gap-1.5"><span className="font-semibold">Bemerkung:</span><Richtext html={bemerkung} /></div> : null}
      <div className="flex justify-between text-[11px] text-[#5d5b72] border-t border-[#e6e5ee] pt-2">
        <span>{plan.freigegeben_am ? `Freigegeben am ${zeitpunkt(plan.freigegeben_am)} Uhr${plan.freigegeben_von_name ? ` von ${plan.freigegeben_von_name}` : ""}` : "Noch nicht freigegeben"}</span>
        <span>Seite 1/1</span>
      </div>
      {a?.fusszeile ? <div className="text-[10px] text-[#5d5b72] text-center">{a.fusszeile}</div> : null}
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
      </ul>
      <Meldung art="warn">Die PDF wird bei der Freigabe noch nicht erzeugt: die PDF-Erzeugung (F51) ist noch nicht umgesetzt.</Meldung>
      <Fehleranzeige fehler={freigeben.error} />
    </Dialog>
  );
}

export function Plaene() {
  const { patient } = useAkte();
  const { darf } = useAuth();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [modus, setModus] = useState<"ansicht" | "vergleich">("ansicht");
  const [freigabe, setFreigabe] = useState(false);
  const [verwerfen, setVerwerfen] = useState(false);
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
  const anlegen = offen && darf("plaene_anlegen");
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
                  ? "Entwurf: nur für das Team sichtbar, noch nicht beim Versorger. Freigeben darf, wer das Recht „Pläne freigeben“ hat (Mediziner)."
                  : `Freigegeben am ${zeitpunkt(gewaehlt.freigegeben_am)}${gewaehlt.freigegeben_von_name ? ` von ${gewaehlt.freigegeben_von_name}` : ""}. Die gespeicherte PDF mit SHA-256-Prüfung folgt mit der PDF-Erzeugung (F37).`}
              </span>
            </div>
            <div className="flex gap-2 flex-wrap">
              {gewaehlt.status === "entwurf" && anlegen ? <>
                <Knopf icon="stift" onClick={() => navigate(`/patienten/${patient.id}/plaene/${gewaehlt.id}/bearbeiten`)}>Bearbeiten</Knopf>
                <Knopf onClick={() => setVerwerfen(true)}>Verwerfen</Knopf>
                {darf("plaene_freigeben") ? <Knopf variante="pri" icon="haken" onClick={() => setFreigabe(true)}>Freigeben</Knopf> : null}
              </> : null}
              {gewaehlt.status !== "entwurf" ? <>
                <Knopf icon="dokument" disabled title="folgt mit der PDF-Erzeugung (F37)">PDF öffnen</Knopf>
                {anlegen && !entwurfDa ? <Knopf icon="plus" onClick={() => navigate(`/patienten/${patient.id}/plaene/neu?vorlage=${gewaehlt.id}`)}>Als Vorlage für neuen Plan</Knopf> : null}
              </> : null}
            </div>
          </div>
          {vergleich.isLoading ? <Laden /> : vergleich.data ? (
            modus === "ansicht" ? <PdfAnsicht plan={gewaehlt} vergleich={vergleich.data} /> : <VergleichTabelle plan={gewaehlt} vergleich={vergleich.data} />
          ) : <Fehleranzeige fehler={vergleich.error} />}
          <FreigabeDialog plan={gewaehlt} offen={freigabe} onOffen={setFreigabe} />
          <Dialog offen={verwerfen} onOffen={setVerwerfen} titel="Entwurf verwerfen" breite={480}
            beschreibung="Der Entwurf wird gelöscht. Im Verlauf der Akte bleibt sichtbar, dass es ihn gab."
            fuss={<><Knopf onClick={() => setVerwerfen(false)}>Abbrechen</Knopf><Knopf variante="dng" laedt={verwerfenM.isPending} onClick={() => verwerfenM.mutate()}>Verwerfen</Knopf></>}>
            <Fehleranzeige fehler={verwerfenM.error} />
          </Dialog>
        </div>
      ) : null}
    </div>
  );
}
