/**
 * Reiter „Therapie“ und „Empfehlung“ (Aufteilung 07.10.2026, F121/F122).
 *
 * Beide bestehen aus einem Text mit Fassungen: links die Fassungen mit Datum, rechts der Text. Die aktuelle
 * Fassung ist bearbeitbar, ältere sind nur lesbar – gelöscht wird nichts.
 */
import { useAkte } from "./Akte";
import { Aktenseite, Eintragsliste, useWahl } from "./Aktenseite";
import { TITEL, Textfassung, TextfassungsListe } from "./TextKarte";
import type { Textfeld } from "./TextKarte";

function Textseite({ feld, testid }: { feld: Textfeld; testid: string }) {
  const { patient } = useAkte();
  const [wahl, setWahl] = useWahl("fassung");
  const kopf = patient.kopf?.versionen[feld];
  const gewaehlt = wahl ? Number(wahl) : null;
  return (
    <Aktenseite
      testid={testid}
      titel="Fassungen"
      anzahl={kopf?.version}
      liste={
        <Eintragsliste name={`Fassungen der ${TITEL[feld]}`}>
          <TextfassungsListe feld={feld} gewaehlt={gewaehlt} onWahl={(v) => setWahl(String(v))} />
        </Eintragsliste>
      }
      // Erst lesen, dann „Bearbeiten“ (Vorschlag „Bearbeiten sichtbar“, 08.10.2026) – nur ein leerer Text öffnet
      // gleich den Editor, damit niemand erst auf „Bearbeiten“ klicken muss, um etwas einzutragen
      detail={<Textfassung feld={feld} version={gewaehlt} immerOffen={(!gewaehlt || gewaehlt === kopf?.version) && !patient[feld]} />}
    />
  );
}

// Erklärtexte stehen seit 08.10.2026 in der Hilfe („Stammdaten, Diagnose und Therapie ändern“)
export function Therapie() {
  return <Textseite feld="therapie" testid="therapie" />;
}

export function Empfehlung() {
  return <Textseite feld="empfehlung" testid="empfehlung" />;
}
