/** Termin anlegen oder ändern: Rückruf, Wiedervorlage, Praxistermin (mit Terminort), Sonstiges. */
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuswahl } from "@/lib/daten";
import { heuteIso, zeitpunkt } from "@/lib/format";
import { TERMINARTEN } from "@/lib/typen";
import type { PatientZeile, Termin } from "@/lib/typen";
import { Auswahl, Eingabe, Feld, Knopf, Meldung, Textfeld } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { PatientWahl } from "./PatientWahl";

export function TerminDialog({ offen, onOffen, patientId, patientName, termin, datum, mitAkte }: {
  offen: boolean; onOffen: (o: boolean) => void; patientId?: number; patientName?: string;
  /** Knopf „Akte öffnen“ beim Ändern (Kalender, Startseite) */
  mitAkte?: boolean;
  /** vorhandener, offener Termin zum Ändern */
  termin?: Termin | null;
  /** Vorgabe für das Datum eines neuen Termins (z. B. Klick auf einen Tag im Kalender), „JJJJ-MM-TT“ */
  datum?: string;
}) {
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const [art, setArt] = useState("rueckruf");
  const [ort, setOrt] = useState("");
  const [faellig, setFaellig] = useState(heuteIso());
  const [uhr, setUhr] = useState("");
  const [titel, setTitel] = useState("");
  const [notiz, setNotiz] = useState("");
  const orte = useAuswahl("terminort");
  // Praxistermin ohne Ort: Praxis Dr. Holtmeier vorschlagen, damit der Termin auf dem Infoblatt an die Praxis steht (F177)
  const holtmeier = orte.data?.find((o) => /holtmeier/i.test(o.wert));
  // „kein“: bewusst ohne Ort gewählt – dann nichts vorschlagen
  const ortWert = ort === "kein" ? "" : ort || (art === "praxistermin" && holtmeier ? String(holtmeier.id) : "");
  const qc = useQueryClient();
  const melden = useHinweis();
  useEffect(() => {
    if (offen && termin) {
      setArt(termin.art); setOrt(termin.ort ? String(termin.ort) : ""); setFaellig(termin.faellig_am);
      setUhr(termin.uhrzeit ? termin.uhrzeit.slice(0, 5) : ""); setTitel(termin.titel); setNotiz(termin.notiz);
    }
  }, [offen, termin]);
  useEffect(() => {
    if (offen && !termin && datum) setFaellig(datum);
  }, [offen, termin, datum]);
  const speichern = useMutation({
    mutationFn: () => {
      const daten = {
        art,
        ort: art === "praxistermin" && ortWert ? Number(ortWert) : null,
        faellig_am: faellig,
        uhrzeit: uhr || null,
        titel: titel.trim() || TERMINARTEN[art],
        notiz,
      };
      return termin
        ? api<Termin>(`termine/${termin.id}/`, { method: "PATCH", body: daten })
        : api<Termin>("termine/", { body: { ...daten, patient: patientId ?? patient?.id } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      void qc.invalidateQueries({ queryKey: ["termine"] });
      void qc.invalidateQueries({ queryKey: ["kalender"] });
      void qc.invalidateQueries({ queryKey: ["patient"] });
      melden(termin ? "Termin geändert." : "Termin angelegt.");
      onOffen(false);
      setPatient(null);
      setTitel("");
      setNotiz("");
      setUhr("");
    },
  });
  // Kalender: Klick auf einen offenen Termin öffnet gleich diesen Dialog – dort auch „Erledigt“ und „Akte öffnen“
  // (Vorschlag „Bearbeiten sichtbar“, 08.10.2026)
  const abhaken = useMutation({
    mutationFn: () => api<Termin>(`termine/${termin!.id}/erledigt/`, { method: "POST" }),
    onSuccess: (t) => {
      for (const k of [["startseite"], ["termine"], ["kalender"], ["patient", t.patient]]) void qc.invalidateQueries({ queryKey: k });
      melden(`Erledigt: ${t.patient_name}`);
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={termin ? "Termin bearbeiten" : "Neuer Termin"}
      beschreibung={patientName ? `für ${patientName}` : "Erscheint im Kalender und auf der Startseite unter „Termine und Wiedervorlagen“."}
      fuss={<>
        {termin && mitAkte ? <Link className="btn sec mr-auto" to={`/patienten/${termin.patient}`}>Akte öffnen</Link> : null}
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        {termin && !termin.erledigt_am ? <Knopf icon="haken" laedt={abhaken.isPending} onClick={() => abhaken.mutate()}>Erledigt</Knopf> : null}
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!termin && !patientId && !patient}
          onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <form className="grid grid-cols-2 gap-4" onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        {!patientId && !termin ? (
          <Feld label="Patient" className="col-span-2" fehler={f.patient} pflicht>
            {(p) => <PatientWahl id={p.id} wert={patient} onWahl={setPatient} fehler={!!f.patient} />}
          </Feld>
        ) : null}
        <Feld label="Art" fehler={f.art}>
          {(p) => (
            <Auswahl {...p} value={art} onChange={(e) => setArt(e.target.value)}>
              {Object.entries(TERMINARTEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Ort" fehler={f.ort} hinweis={art !== "praxistermin" ? "nur bei Praxisterminen"
          : !ortWert ? "Ohne Ort steht der Termin nicht auf dem Infoblatt an die Praxis" : undefined}>
          {(p) => (
            <Auswahl {...p} value={ortWert} disabled={art !== "praxistermin"} onChange={(e) => setOrt(e.target.value || "kein")}>
              <option value="">—</option>
              {(orte.data ?? []).map((o) => <option key={o.id} value={o.id}>{o.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Datum" fehler={f.faellig_am} pflicht>
          {(p) => <Eingabe {...p} type="date" value={faellig} onChange={(e) => setFaellig(e.target.value)} />}
        </Feld>
        <Feld label="Uhrzeit" hinweis="leer = ganztägig" fehler={f.uhrzeit}>
          {(p) => <Eingabe {...p} type="time" value={uhr} onChange={(e) => setUhr(e.target.value)} />}
        </Feld>
        <Feld label="Titel" className="col-span-2" fehler={f.titel} hinweis="z. B. „Laborwerte besprechen“">
          {(p) => <Eingabe {...p} value={titel} maxLength={200} onChange={(e) => setTitel(e.target.value)} />}
        </Feld>
        <Feld label="Notiz" className="col-span-2" fehler={f.notiz}>
          {(p) => <Textfeld {...p} rows={2} value={notiz} onChange={(e) => setNotiz(e.target.value)} />}
        </Feld>
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler" className="col-span-2">{speichern.error.message}</Meldung> : null}
        {abhaken.error ? <Meldung art="fehler" className="col-span-2">{abhaken.error.message}</Meldung> : null}
        {termin ? <span className="col-span-2 text-[0.8125rem] gedaempft" data-testid="termin-angelegt">
          Angelegt {zeitpunkt(termin.angelegt_am)}{termin.angelegt_von_name ? ` von ${termin.angelegt_von_name}` : ""}</span> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}
