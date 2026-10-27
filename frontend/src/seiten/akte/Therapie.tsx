/**
 * Reiter „Therapie“, „Empfehlung“ und „Befunde“ (Aufteilung 07.10.2026, F121/F122; neu gestaltet 10.10.2026;
 * Befunde seit 27.10.2026).
 *
 * Statt einer Spalte „Fassungen“ steht der Text als lesbares Dokument vorn; frühere Fassungen öffnet ein Knopf.
 * Bei der Therapie steht darunter der Verlauf als eigene Einträge mit Datum (Beginn HPE, Umstellung Lipide …),
 * rechts das, was man beim Schreiben braucht: aktueller Plan, Empfehlung bzw. Therapie, Diagnosen.
 */
import { useState } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { datum, eingabeDatum, heuteIso, uhrzeit, zahl } from "@/lib/format";
import type { Therapieschritt } from "@/lib/typen";
import { Chip, Eingabe, Feld, Karte, Knopf, Laden, Meldung, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { FirmaMarke } from "@/components/FirmenWahl";
import { Richtext } from "@/components/Editor";
import { Bestaetigen } from "@/components/Bestaetigen";
import { useAkte } from "./Akte";
import { useWahl } from "./Aktenseite";
import { DiagnosenKurz } from "./Diagnosen";
import { TITEL, Textfassung, useFassungen } from "./TextKarte";
import type { Textfeld } from "./TextKarte";

/** Frühere Fassungen in einem Dialog: Klick zeigt die Fassung (nur lesbar) im Dokument */
function FassungenDialog({ feld, offen, onOffen, gewaehlt, onWahl }: {
  feld: Textfeld; offen: boolean; onOffen: (o: boolean) => void; gewaehlt: number | null; onWahl: (v: number | null) => void;
}) {
  const daten = useFassungen(feld, offen);
  const liste = daten.data?.fassungen ?? [];
  const aktuell = liste[0]?.version;
  return (
    <Dialog offen={offen} onOffen={onOffen} breite={520} titel={`Frühere Fassungen: ${TITEL[feld]}`}
      beschreibung="Jede gespeicherte Fassung bleibt mit Person und Zeitpunkt erhalten. Ältere Fassungen sind nur lesbar.">
      {daten.isPending ? <Laden /> : (
        <ul className="m-0 p-0 list-none flex flex-col gap-1" data-testid="fassungen">
          {liste.map((f) => {
            const an = (gewaehlt ?? aktuell) === f.version;
            return (
              <li key={f.version}>
                <button type="button" onClick={() => { onWahl(f.version === aktuell ? null : f.version); onOffen(false); }}
                  className={cx("w-full text-left rounded-lg border px-3 py-2 flex items-center justify-between gap-3 cursor-pointer",
                    an ? "border-akzent bg-akzent-weich" : "border-rand bg-flaeche hover:bg-fein")}>
                  <span className="flex flex-col">
                    <span className="font-medium">Fassung {f.version}</span>
                    <span className="text-[0.8125rem] gedaempft">{datum(f.zeitpunkt)}, {uhrzeit(f.zeitpunkt)} Uhr · {f.person ?? "—"}</span>
                  </span>
                  {f.version === aktuell ? <Chip art="ok">aktuell</Chip> : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Dialog>
  );
}

/** Der Text als Dokument: aktuelle Fassung bearbeitbar, eine gewählte ältere nur lesbar */
function Dokument({ feld }: { feld: Textfeld }) {
  const { patient } = useAkte();
  const [wahl, setWahl] = useWahl("fassung");
  const [liste, setListe] = useState(false);
  const kopf = patient.kopf?.versionen[feld];
  const gewaehlt = wahl ? Number(wahl) : null;
  const alt = gewaehlt != null && gewaehlt !== kopf?.version;
  return (
    <>
      {alt ? (
        <Meldung art="info">
          <span className="flex items-center justify-between gap-3 flex-wrap">
            Sie sehen Fassung {gewaehlt} – nur lesbar.
            <Knopf klein onClick={() => setWahl("")}>Zur aktuellen Fassung</Knopf>
          </span>
        </Meldung>
      ) : null}
      {/* Erst lesen, dann „Bearbeiten“ (08.10.2026) – nur ein leerer Text öffnet gleich den Editor */}
      <Textfassung feld={feld} version={gewaehlt} immerOffen={!alt && !patient[feld]}
        vorAktionen={kopf && kopf.version > 1
          ? <Knopf klein icon="uhr" onClick={() => setListe(true)}>Frühere Fassungen ({kopf.version - 1})</Knopf> : null} />
      <FassungenDialog feld={feld} offen={liste} onOffen={setListe} gewaehlt={gewaehlt} onWahl={(v) => setWahl(v ? String(v) : "")} />
    </>
  );
}

/** Verlauf der Therapie: Schritte mit Datum, neueste oben; „+ Schritt“ ohne den ganzen Text zu bearbeiten */
function Verlauf() {
  const { patient, bearbeiten } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [neu, setNeu] = useState(false);
  const [tag, setTag] = useState("");
  const [text, setText] = useState("");
  const [entfernen, setEntfernen] = useState<Therapieschritt | null>(null);
  const schluessel = ["therapieschritte", patient.id];
  const schritte = useQuery({
    queryKey: schluessel,
    queryFn: () => api<Therapieschritt[]>(`therapieschritte/?patient=${patient.id}&aktiv=true`),
  });
  const anlegen = useMutation({
    mutationFn: () => {
      const iso = eingabeDatum(tag);
      if (!iso) throw new ApiFehler(400, "", null, { datum: "Bitte als TT.MM.JJJJ eingeben." });
      return api<Therapieschritt>("therapieschritte/", { body: { patient: patient.id, datum: iso, text: text.trim() } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: schluessel });
      melden("Schritt im Verlauf eingetragen.");
      setNeu(false);
    },
  });
  const weg = useMutation({
    mutationFn: (s: Therapieschritt) => api<Therapieschritt>(`therapieschritte/${s.id}/`, { method: "PATCH", body: { aktiv: false } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: schluessel });
      melden("Schritt entfernt.");
      setEntfernen(null);
    },
  });
  const f: Feldfehler = anlegen.error instanceof ApiFehler ? anlegen.error.felder : {};
  const liste = schritte.data ?? [];
  const oeffnen = () => { setTag(datum(heuteIso())); setText(""); anlegen.reset(); setNeu(true); };

  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="therapie-verlauf">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="lbl m-0 text-[0.9375rem]">Verlauf</h2>
        {bearbeiten && !neu ? <Knopf klein icon="plus" onClick={oeffnen}>Schritt im Verlauf</Knopf> : null}
      </div>
      {neu ? (
        <form className="grid grid-cols-1 sm:grid-cols-[9rem_minmax(0,1fr)_auto] gap-3 items-end rounded-lg bg-grund p-3"
          onSubmit={(e) => { e.preventDefault(); anlegen.mutate(); }} data-testid="therapieschritt-neu">
          <Feld label="Datum" fehler={f.datum}>{(p) => <Eingabe {...p} className="num" value={tag} onChange={(e) => setTag(e.target.value)} />}</Feld>
          <Feld label="Was hat sich geändert?" fehler={f.text}>
            {(p) => <Eingabe {...p} value={text} maxLength={300} autoFocus placeholder="z. B. Umstellung Lipide" onChange={(e) => setText(e.target.value)} />}
          </Feld>
          <div className="flex gap-2">
            <Knopf onClick={() => setNeu(false)}>Abbrechen</Knopf>
            <Knopf type="submit" variante="pri" laedt={anlegen.isPending} disabled={!text.trim()}>Eintragen</Knopf>
          </div>
          {anlegen.error && !Object.keys(f).length ? <Meldung art="fehler" className="sm:col-span-3">{anlegen.error.message}</Meldung> : null}
        </form>
      ) : null}
      {schritte.isPending ? <Laden /> : liste.length ? (
        <ol className="m-0 p-0 list-none flex flex-col" data-testid="therapieschritte">
          {liste.map((s, i) => (
            <li key={s.id} className="therapie-schritt">
              <span className="num text-[0.8125rem] gedaempft pt-0.5">{datum(s.datum)}</span>
              <span className="therapie-punkt" aria-hidden="true"><span className={cx(i === 0 && "erster")} />{i < liste.length - 1 ? <i /> : null}</span>
              <span className="flex flex-col gap-0.5 min-w-0 pb-4">
                <span>{s.text}</span>
                <span className="flex items-center gap-1.5 text-[0.75rem] gedaempft"><span>{s.angelegt_von_name ?? ""}</span><FirmaMarke kurz={s.firma_kurz} /></span>
              </span>
              {bearbeiten ? (
                <button type="button" className="btn geist icon klein !h-7 !w-7 self-start" aria-label={`„${s.text}“ entfernen`}
                  title="Entfernen" onClick={() => { weg.reset(); setEntfernen(s); }}><Icon name="x" groesse={14} /></button>
              ) : <span />}
            </li>
          ))}
        </ol>
      ) : !neu ? (
        <p className="m-0 text-sm gedaempft">Noch keine Schritte eingetragen – z. B. „Beginn HPE“ oder „Umstellung Lipide“ mit Datum.</p>
      ) : null}
      {bearbeiten ? <Bestaetigen offen={!!entfernen} onOffen={(o) => { if (!o) setEntfernen(null); }} titel="Schritt entfernen" knopf="Entfernen"
        text={<>„{entfernen?.text}“ wird aus dem Verlauf entfernt. Im Verlauf der Akte bleibt nachvollziehbar, dass es ihn gab.</>}
        laedt={weg.isPending} fehler={weg.error} onJa={() => entfernen && weg.mutate(entfernen)} /> : null}
    </Karte>
  );
}

/** Rechte Spalte: aktueller Plan, der jeweils andere Text, Diagnosen */
function Seitenspalte({ feld }: { feld: Textfeld }) {
  const { patient } = useAkte();
  const basis = `/patienten/${patient.id}`;
  const plan = patient.kopf?.aktueller_plan;
  const anderes: Textfeld = feld === "therapie" ? "empfehlung" : "therapie";
  return (
    <aside className="flex flex-col gap-[var(--abstand)] min-w-0" aria-label="Zum Nachschlagen">
      <Karte className="px-5 py-4 flex flex-col gap-2.5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="lbl m-0">Aktueller Infusionsplan</h2>
          {plan ? <Chip art="ok"><Icon name="haken" groesse={12} />gültig</Chip> : null}
        </div>
        {plan ? (
          <div className="grid grid-cols-2 gap-2">
            <span className="flex flex-col"><span className="num text-lg font-semibold">{zahl(plan.kcal)}</span><span className="text-xs gedaempft">kcal</span></span>
            {plan.laufzeit_h ? <span className="flex flex-col"><span className="num text-lg font-semibold">{zahl(plan.laufzeit_h)} h</span><span className="text-xs gedaempft">Laufzeit</span></span> : null}
          </div>
        ) : <span className="text-sm gedaempft">{patient.kopf?.kein_plan ? "Kein Plan nötig." : "Noch kein freigegebener Plan."}</span>}
        <Link to={`${basis}/plaene`} className="text-sm font-medium self-start">Zu den Plänen</Link>
      </Karte>
      <Karte className="px-5 py-4 flex flex-col gap-2" data-testid={`seite-${anderes}`}>
        <div className="flex items-center justify-between gap-2">
          <h2 className="lbl m-0">{TITEL[anderes]}</h2>
          <Link to={`${basis}/${anderes}`} className="text-sm font-medium">Öffnen</Link>
        </div>
        <div className="max-h-48 overflow-auto" tabIndex={0} role="region" aria-label={TITEL[anderes]}><Richtext html={patient[anderes]} className="text-sm" leer={`Noch keine ${TITEL[anderes]} eingetragen.`} /></div>
      </Karte>
      <Karte className="px-5 py-4 flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="lbl m-0">Diagnosen</h2>
          <Link to={`${basis}/diagnosen`} className="text-sm font-medium">Alle</Link>
        </div>
        <DiagnosenKurz patientId={patient.id} />
      </Karte>
    </aside>
  );
}

function Textseite({ feld, testid }: { feld: Textfeld; testid: string }) {
  return (
    <div className="akte-spalten grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(17.5rem,22rem)] gap-[var(--abstand)] items-start" data-testid={testid}>
      <div className="flex flex-col gap-[var(--abstand)] min-w-0 xl:max-w-[60rem]">
        <Dokument feld={feld} />
        {feld === "therapie" ? <Verlauf /> : null}
      </div>
      <Seitenspalte feld={feld} />
    </div>
  );
}

// Erklärtexte stehen seit 08.10.2026 in der Hilfe („Stammdaten, Diagnose und Therapie ändern“)
export function Therapie() {
  return <Textseite feld="therapie" testid="therapie" />;
}

export function Empfehlung() {
  return <Textseite feld="empfehlung" testid="empfehlung" />;
}

// Reiter „Befunde“ (27.10.2026): aufgebaut wie die Empfehlung, rechts daneben die Therapie
export function Befunde() {
  return <Textseite feld="befunde" testid="befunde" />;
}
