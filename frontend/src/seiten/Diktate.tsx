/**
 * Diktate (Wunsch 23.10.2026): ans Sekretariat abgegebene Diktate, deren Text noch nicht im Bericht steht – älteste
 * zuerst. Öffnen führt zum Bericht in der Akte; dort nachhören, übernehmen und fertig machen.
 *
 * Neues Diktat auch hier, nicht nur in der Akte (Wunsch 26.10.2026): Patient wählen, Berichtsart, aufnehmen – beim
 * Senden entsteht ein Bericht-Entwurf, an dem das Diktat hängt.
 */
import { useRef, useState } from "react";
import { Link } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuswahl } from "@/lib/daten";
import { datum, heuteIso, uhrzeit } from "@/lib/format";
import type { Bericht, Diktat, PatientZeile } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Laden, Leer, Meldung, Seitenkopf } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { DiktatAufnahme, dauerText } from "@/components/Diktat";
import { PatientWahl } from "@/components/PatientWahl";

/** Neues Diktat ohne Umweg über die Akte: der Bericht-Entwurf wird beim Senden der Aufnahme angelegt */
function NeuesDiktat() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const arten = useAuswahl("berichtart");
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const [art, setArt] = useState("");
  const [titel, setTitel] = useState("");
  const [aktiv, setAktiv] = useState(false);
  const [gesendet, setGesendet] = useState<Diktat | null>(null);
  // neue Aufnahme (anderer Patient, neuer Bericht): Aufnahme-Baustein neu aufsetzen
  const [runde, setRunde] = useState(0);

  // angelegter Entwurf: scheitert das Hochladen, nimmt der zweite Versuch denselben Bericht
  const angelegt = useRef<{ patient: number; bericht: number } | null>(null);
  const entwurf = async () => {
    if (angelegt.current?.patient === patient!.id) return angelegt.current.bericht;
    const name = titel.trim() || arten.data?.find((a) => String(a.id) === art)?.wert || `Diktat vom ${datum(heuteIso())}`;
    const neu = await api<Bericht>("berichte/", { body: { patient: patient!.id, titel: name, art: art ? Number(art) : null,
      datum: heuteIso(), empfaenger: "", inhalt: "" } });
    angelegt.current = { patient: patient!.id, bericht: neu.id };
    void qc.invalidateQueries({ queryKey: ["berichte", patient!.id] });
    return neu.id;
  };

  return (
    <Karte className="flex flex-col gap-3" data-testid="diktat-neu">
      <KartenKopf titel="Neues Diktat" unter="Für einen neuen Bericht. Beim Senden wird der Entwurf in der Akte angelegt." />
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12.5rem_minmax(0,1fr)]">
        <Feld label="Patient" pflicht>
          {(p) => <PatientWahl id={p.id} wert={patient} onWahl={(x) => {
            if (aktiv && !window.confirm("Die Aufnahme ist noch nicht gesendet. Verwerfen?")) return;
            setPatient(x); setGesendet(null); setRunde((r) => r + 1);
          }} />}
        </Feld>
        <Feld label="Berichtsart">
          {(p) => (
            <Auswahl {...p} value={art} disabled={aktiv} onChange={(e) => setArt(e.target.value)}>
              <option value="">— ohne Angabe —</option>
              {(arten.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Titel" hinweis="Leer: nach der Berichtsart">
          {(p) => <Eingabe {...p} value={titel} maxLength={200} disabled={aktiv} onChange={(e) => setTitel(e.target.value)}
            placeholder="z. B. Verlaufsbericht" />}
        </Feld>
      </div>
      {patient ? (
        <DiktatAufnahme key={`${patient.id}-${runde}`} patientId={patient.id} vorHochladen={entwurf} onAktiv={setAktiv}
          onHochgeladen={(d) => {
            angelegt.current = null; setGesendet(d); setTitel(""); setRunde((r) => r + 1);
            void qc.invalidateQueries({ queryKey: ["diktate", "offen"] });
            melden(d.wann === "nachts" ? "Diktat gesendet – es wird heute Nacht abgeschrieben."
              : "Diktat gesendet – die Abschrift erscheint im Bericht, meist nach wenigen Minuten.");
          }} />
      ) : <span className="text-[0.8125rem] gedaempft">Erst den Patienten wählen, dann aufnehmen.</span>}
      {gesendet?.bericht ? (
        <Meldung art="ok">
          Gesendet: <Link to={`/patienten/${gesendet.patient}/berichte?bericht=${gesendet.bericht}`}>{gesendet.bericht_titel ?? "Bericht"}</Link>
          {" "}bei {gesendet.patient_name}. Ein weiteres Diktat wird ein neuer Bericht.
        </Meldung>
      ) : null}
    </Karte>
  );
}

export function Diktate() {
  const { darf } = useAuth();
  const offen = useQuery({
    queryKey: ["diktate", "offen"],
    queryFn: () => api<Diktat[]>("diktate/offen/"),
    refetchInterval: 30_000,
  });
  const liste = offen.data ?? [];
  return (
    <Seite pfad={[{ text: "Diktate" }]}>
      <Seitenkopf titel="Diktate"
        unter="Neues Diktat aufnehmen; darunter ans Sekretariat gegebene Diktate, deren Text noch nicht im Bericht steht. Im Bericht: nachhören, „In den Text übernehmen“, korrigieren, speichern." />
      {darf("diktieren") ? <NeuesDiktat /> : null}
      <Fehleranzeige fehler={offen.error} />
      <Karte className="overflow-x-auto">
        <KartenKopf titel="Fürs Sekretariat" />
        {offen.isPending ? <Laden /> : liste.length === 0 ? <Leer>Keine offenen Diktate.</Leer> : (
          <table className="tabelle" data-testid="diktate-offen">
            <thead>
              <tr>
                <th className="th">Patient</th><th className="th">Bericht</th><th className="th">Diktiert</th>
                <th className="th text-right">Länge</th><th className="th">Stand</th>
              </tr>
            </thead>
            <tbody>
              {liste.map((d) => (
                <tr key={d.id}>
                  <td className="td">
                    <Link to={`/patienten/${d.patient}`} className="font-medium no-underline">{d.patient_name}</Link>
                  </td>
                  <td className="td">
                    <Link to={`/patienten/${d.patient}/berichte?bericht=${d.bericht}`}>{d.bericht_titel ?? "Bericht"}</Link>
                  </td>
                  <td className="td text-[0.8125rem] whitespace-nowrap">
                    <span className="num">{datum(d.erstellt_am)} {uhrzeit(d.erstellt_am)}</span>
                    {d.erstellt_von_name ? <span className="gedaempft"> · {d.erstellt_von_name}</span> : null}
                  </td>
                  <td className="td num text-right">{dauerText(d.dauer_s)}</td>
                  <td className="td whitespace-nowrap">
                    <Chip art={d.status === "fertig" ? "warn" : d.status === "fehler" ? "fehler" : "neutral"}>
                      {d.status === "fertig" ? "zum Übernehmen" : d.status === "wartet" && d.wann === "nachts" ? "wartet auf die Nacht" : d.status_name}
                    </Chip>
                    {d.status === "fertig" && d.unsicher ? <Chip art="warn" className="ml-1.5">{d.unsicher} unsicher</Chip> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Karte>
    </Seite>
  );
}
