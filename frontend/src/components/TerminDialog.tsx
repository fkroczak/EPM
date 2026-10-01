/** Termin anlegen: Rückruf, Wiedervorlage, Praxistermin (mit Terminort), Sonstiges. */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuswahl } from "@/lib/daten";
import { heuteIso } from "@/lib/format";
import { TERMINARTEN } from "@/lib/typen";
import type { PatientZeile, Termin } from "@/lib/typen";
import { Auswahl, Eingabe, Feld, Knopf, Meldung, Textfeld } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { PatientWahl } from "./PatientWahl";

export function TerminDialog({ offen, onOffen, patientId, patientName }: {
  offen: boolean; onOffen: (o: boolean) => void; patientId?: number; patientName?: string;
}) {
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const [art, setArt] = useState("rueckruf");
  const [ort, setOrt] = useState("");
  const [faellig, setFaellig] = useState(heuteIso());
  const [uhr, setUhr] = useState("");
  const [titel, setTitel] = useState("");
  const [notiz, setNotiz] = useState("");
  const orte = useAuswahl("terminort");
  const qc = useQueryClient();
  const melden = useHinweis();
  const speichern = useMutation({
    mutationFn: () => api<Termin>("termine/", {
      body: {
        patient: patientId ?? patient?.id,
        art,
        ort: art === "praxistermin" && ort ? Number(ort) : null,
        faellig_am: faellig,
        uhrzeit: uhr || null,
        titel: titel.trim() || TERMINARTEN[art],
        notiz,
      },
    }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      void qc.invalidateQueries({ queryKey: ["termine"] });
      void qc.invalidateQueries({ queryKey: ["patient"] });
      melden("Termin angelegt.");
      onOffen(false);
      setPatient(null);
      setTitel("");
      setNotiz("");
      setUhr("");
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Termin anlegen"
      beschreibung={patientName ? `für ${patientName}` : "Erscheint auf der Startseite unter „Termine und Wiedervorlagen“."}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!patientId && !patient}
          onClick={() => speichern.mutate()}>Termin speichern</Knopf>
      </>}>
      <form className="grid grid-cols-2 gap-4" onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        {!patientId ? (
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
        <Feld label="Ort" fehler={f.ort} hinweis={art !== "praxistermin" ? "nur bei Praxisterminen" : undefined}>
          {(p) => (
            <Auswahl {...p} value={ort} disabled={art !== "praxistermin"} onChange={(e) => setOrt(e.target.value)}>
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
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}
