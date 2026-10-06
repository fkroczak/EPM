/** Entwurf 5 · Diagnose und Therapie: formatierte Texte mit Versionen (jede Fassung bleibt im Verlauf). */
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { zeitpunkt } from "@/lib/format";
import type { Patient } from "@/lib/typen";
import { Fehleranzeige, Karte, Knopf, Laden, Meldung, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Editor, Richtext } from "@/components/Editor";
import { RASTER_SPALTEN, useStufe } from "@/lib/stufen";
import { Bereich, Bereiche } from "@/components/ui/bereiche";
import { useAkte } from "./Akte";
import { DiagnosenKarte } from "./Diagnosen";

type Feld = "diagnose" | "therapie" | "empfehlung" | "bemerkung";
type Fassungen = { feld: Feld; version: number; fassungen: { version: number; zeitpunkt: string; person: string | null; text: string }[] };

const TITEL: Record<Feld, string> = { diagnose: "Diagnose", therapie: "Therapie", empfehlung: "Empfehlung", bemerkung: "Bemerkung" };

function VersionenDialog({ feld, offen, onOffen }: { feld: Feld; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const daten = useQuery({
    queryKey: ["patient", patient.id, "versionen", feld],
    queryFn: () => api<Fassungen>(`patienten/${patient.id}/versionen/?feld=${feld}`),
    enabled: offen,
  });
  const liste = daten.data?.fassungen ?? [];
  const aktiv = liste.find((f) => f.version === gewaehlt) ?? liste[0];
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={`${TITEL[feld]} · Versionen`} breite={880}
      beschreibung="Jede gespeicherte Fassung mit Person, Datum und Uhrzeit. Ältere Fassungen sind nur lesbar.">
      {daten.isLoading ? <Laden /> : liste.length ? (
        <div className="grid grid-cols-[220px_minmax(0,1fr)] gap-4 min-h-[300px]">
          <ul className="m-0 p-0 list-none flex flex-col gap-1 border-r border-rand pr-3" aria-label="Fassungen">
            {liste.map((f) => (
              <li key={f.version}>
                <button type="button" aria-current={aktiv?.version === f.version ? "true" : undefined}
                  className={cx("w-full text-left bg-transparent border-0 rounded-md px-2.5 py-2 cursor-pointer flex flex-col gap-0.5",
                    aktiv?.version === f.version ? "bg-akzent-weich" : "hover:bg-fein")}
                  onClick={() => setGewaehlt(f.version)}>
                  <span className="text-sm font-medium">Version {f.version}{f.version === liste[0].version ? " · aktuell" : ""}</span>
                  <span className="num text-xs gedaempft">{zeitpunkt(f.zeitpunkt)}</span>
                  <span className="text-xs gedaempft">{f.person ?? "—"}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="min-w-0 overflow-auto" data-testid="fassung">
            {aktiv ? <Richtext html={aktiv.text} leer="(leer)" /> : null}
          </div>
        </div>
      ) : <Meldung>Noch keine Fassung gespeichert.</Meldung>}
      <Fehleranzeige fehler={daten.error} />
    </Dialog>
  );
}

function Versionszeile({ feld, onVersionen }: { feld: Feld; onVersionen: () => void }) {
  const { patient } = useAkte();
  const v = patient.kopf?.versionen[feld];
  if (!v) return <span className="text-[0.8125rem] gedaempft">Noch nicht bearbeitet</span>;
  return (
    <span className="text-[0.8125rem] gedaempft" data-testid={`version-${feld}`}>
      Version {v.version} · geändert {zeitpunkt(v.zeitpunkt)}{v.person ? ` von ${v.person}` : ""} ·{" "}
      <button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer underline text-[0.8125rem]" onClick={onVersionen}>Versionen</button>
    </span>
  );
}

function TextKarte({ feld, immerOffen, className }: { feld: Feld; immerOffen?: boolean; className?: string }) {
  const { patient, bearbeiten } = useAkte();
  const gespeichert = patient[feld];
  const [entwurf, setEntwurf] = useState(gespeichert);
  const [offen, setOffen] = useState(false);
  const [versionen, setVersionen] = useState(false);
  const qc = useQueryClient();
  const melden = useHinweis();
  const editor = bearbeiten && (immerOffen || offen);
  // Neue Fassung vom Server übernehmen, aber keine laufende Eingabe überschreiben
  const vorher = useRef(gespeichert);
  useEffect(() => {
    if (gespeichert !== vorher.current) {
      const alt = vorher.current;
      setEntwurf((e) => (e === alt ? gespeichert : e));
      vorher.current = gespeichert;
    }
  }, [gespeichert]);
  const speichern = useMutation({
    mutationFn: () => api<Patient>(`patienten/${patient.id}/`, { method: "PATCH", body: { [feld]: entwurf } }),
    onSuccess: (p) => {
      qc.setQueryData(["patient", patient.id], p);
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      setEntwurf(p[feld]);
      setOffen(false);
      melden(`${TITEL[feld]} gespeichert.`);
    },
  });
  const geaendert = entwurf !== gespeichert;
  return (
    <Karte className={cx("px-[22px] py-[18px] flex flex-col gap-3 min-w-0", className)} data-testid={`karte-${feld}`}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <h2 className="lbl m-0">{TITEL[feld]}</h2>
          <Versionszeile feld={feld} onVersionen={() => setVersionen(true)} />
        </div>
        {bearbeiten && !immerOffen && !offen ? <Knopf klein icon="stift" onClick={() => { setEntwurf(gespeichert); setOffen(true); }}>Bearbeiten</Knopf> : null}
      </div>
      {editor ? (
        <>
          <Editor wert={entwurf} onAenderung={setEntwurf} label={TITEL[feld]} hoehe={immerOffen ? 420 : 160} autofokus={!immerOffen} />
          <Fehleranzeige fehler={speichern.error} />
          <div className="flex justify-end gap-2">
            <Knopf disabled={!geaendert && immerOffen} onClick={() => { setEntwurf(gespeichert); setOffen(false); speichern.reset(); }}>Verwerfen</Knopf>
            <Knopf variante="pri" laedt={speichern.isPending} disabled={!geaendert} onClick={() => speichern.mutate()}>Speichern</Knopf>
          </div>
        </>
      ) : <Richtext html={gespeichert} leer={`Noch keine ${TITEL[feld]} eingetragen.`} />}
      <VersionenDialog feld={feld} offen={versionen} onOffen={setVersionen} />
    </Karte>
  );
}

/** Im Raster mit einstellbarer Größe je Karte (Fehlerliste 02.10.2026, Punkt 2); Diagnose und Therapie brauchen
 *  Platz für lange Texte – Standard: Therapie doppelt so breit. */
export function Therapie() {
  const { patient } = useAkte();
  const stufe = useStufe();
  return (
    <Bereiche seite="akte_therapie" spalten={RASTER_SPALTEN[stufe]} testid="therapie-stufe">
      {/* Diagnoseliste mit ICD-Code (F117); das lange Freitextfeld bleibt daneben bestehen (U51) */}
      <Bereich id="diagnosen" titel="Diagnosen (ICD)"><DiagnosenKarte /></Bereich>
      <Bereich id="diagnose" titel="Diagnose (Freitext)"><TextKarte feld="diagnose" /></Bereich>
      <Bereich id="therapie" titel="Therapie" standard={{ breite: 2 }}><TextKarte feld="therapie" immerOffen /></Bereich>
      <Bereich id="empfehlung" titel="Empfehlung"><TextKarte feld="empfehlung" /></Bereich>
      {/* seit 03.10.2026 sichtbar (Klärung U5) – u. a. Bemerkungen aus dem Altsystem */}
      <Bereich id="bemerkung" titel="Bemerkung"><TextKarte feld="bemerkung" /></Bereich>
      <Bereich id="hinweis" titel="Hinweis" menue={false}>
        <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
          <Icon name="info" />
          <span>Diagnose, Therapie, Empfehlung und Bemerkung sind änderbar. Jede Fassung bleibt mit Person, Datum und Uhrzeit im{" "}
            <Link to={`/patienten/${patient.id}/verlauf`}>Verlauf</Link> erhalten. Die Kommunikation mit dem Patienten steht unter{" "}
            <Link to={`/patienten/${patient.id}/kontakte`}>Kontakte</Link>.</span>
        </div>
      </Bereich>
    </Bereiche>
  );
}
