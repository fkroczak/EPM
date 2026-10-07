/**
 * Reiter „Therapie“ und „Empfehlung“ (Aufteilung 07.10.2026, F121/F122).
 *
 * Beide bestehen aus einem Text mit Fassungen: links die Fassungen mit Datum, rechts der Text. Die aktuelle
 * Fassung ist bearbeitbar, ältere sind nur lesbar – gelöscht wird nichts.
 */
import { Link } from "react-router";
import { useAkte } from "./Akte";
import { Aktenseite, Eintragsliste, useWahl } from "./Aktenseite";
import { TITEL, Textfassung, TextfassungsListe } from "./TextKarte";
import type { Textfeld } from "./TextKarte";

function Textseite({ feld, fuss, testid }: { feld: Textfeld; fuss: React.ReactNode; testid: string }) {
  const { patient } = useAkte();
  const [wahl, setWahl] = useWahl("fassung");
  const kopf = patient.kopf?.versionen[feld];
  const gewaehlt = wahl ? Number(wahl) : null;
  return (
    <Aktenseite
      testid={testid}
      titel="Fassungen"
      anzahl={kopf?.version}
      fuss={fuss}
      liste={
        <Eintragsliste name={`Fassungen der ${TITEL[feld]}`}>
          <TextfassungsListe feld={feld} gewaehlt={gewaehlt} onWahl={(v) => setWahl(String(v))} />
        </Eintragsliste>
      }
      detail={<Textfassung feld={feld} version={gewaehlt} immerOffen={!gewaehlt || gewaehlt === kopf?.version} />}
    />
  );
}

export function Therapie() {
  const { patient } = useAkte();
  return (
    <Textseite feld="therapie" testid="therapie"
      fuss={<>Jede gespeicherte Fassung bleibt mit Person, Datum und Uhrzeit im{" "}
        <Link to={`/patienten/${patient.id}/verlauf`}>Verlauf</Link> erhalten. Die Diagnosen stehen unter{" "}
        <Link to={`/patienten/${patient.id}/diagnosen`}>Diagnosen</Link>, die Empfehlung unter{" "}
        <Link to={`/patienten/${patient.id}/empfehlung`}>Empfehlung</Link>.</>} />
  );
}

export function Empfehlung() {
  const { patient } = useAkte();
  return (
    <Textseite feld="empfehlung" testid="empfehlung"
      fuss={<>Die Empfehlung aus der letzten Sprechstunde; sie steht auch auf den{" "}
        <Link to={`/patienten/${patient.id}`}>Unterlagen für die Sprechstunde</Link>. Jede Fassung bleibt im{" "}
        <Link to={`/patienten/${patient.id}/verlauf`}>Verlauf</Link> erhalten.</>} />
  );
}
