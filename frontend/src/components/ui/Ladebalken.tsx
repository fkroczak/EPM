/**
 * Ladebalken am oberen Rand (Wunsch 07.10.2026, F124): Sobald eine Anfrage an den Server läuft – Laden, Speichern,
 * Hochladen, PDF, Aufträge –, füllt sich oben ein schmaler Balken und ein Lichtstreifen wandert darüber. Ist alles
 * beantwortet, läuft er voll und blendet aus.
 *
 * Ganz kurze Anfragen (unter 150 ms) zeigen nichts, sonst würde der Balken bei jeder Statusabfrage flackern.
 * Läuft ein Auftrag auf dem Server (Administration › System, Backup), meldet die Seite das als Hintergrundarbeit:
 * Dann bleibt der Balken durchgehend in Bewegung, bis der Auftrag beendet ist (Wunsch 07.10.2026).
 */
import { useEffect, useState } from "react";
import { useHintergrundAktiv, useLaufendeAnfragen } from "@/lib/laden";
import { cx } from "./basis";

const VERZOEGERUNG_MS = 150;   // so lange darf eine Anfrage dauern, ohne dass der Balken erscheint
const AUSBLENDEN_MS = 450;     // Zeit für „voll laufen und ausblenden“

export function Ladebalken() {
  const anfragen = useLaufendeAnfragen() > 0;
  // Hintergrundarbeit (Auftrag auf dem Server): der Balken bleibt in Bewegung, bis sie beendet ist
  const hintergrund = useHintergrundAktiv();
  const laufend = anfragen || hintergrund;
  const [stufe, setStufe] = useState<"aus" | "laeuft" | "fertig">("aus");

  useEffect(() => {
    if (laufend) {
      if (stufe === "laeuft") return;
      const t = window.setTimeout(() => setStufe("laeuft"), stufe === "fertig" ? 0 : VERZOEGERUNG_MS);
      return () => window.clearTimeout(t);
    }
    if (stufe === "laeuft") {
      setStufe("fertig");
      return;
    }
    if (stufe === "fertig") {
      const t = window.setTimeout(() => setStufe("aus"), AUSBLENDEN_MS);
      return () => window.clearTimeout(t);
    }
  }, [laufend, stufe]);

  if (stufe === "aus") return null;
  // Hintergrundarbeit: ein wandernder Abschnitt statt der Füllung, die stehen bliebe. Die kurzen Statusabfragen
  // alle drei Sekunden ändern daran nichts – sonst spränge die Darstellung bei jeder hin und her.
  const dauer = stufe === "laeuft" && hintergrund;
  return (
    <div className={cx("ladebalken", stufe === "fertig" && "fertig", dauer && "dauer")} role="progressbar"
      aria-label={dauer ? "Ein Auftrag läuft auf dem Server" : "Daten werden übertragen"}
      aria-busy={stufe === "laeuft" || undefined} data-testid="ladebalken" data-stufe={dauer ? "dauer" : stufe}>
      <div className="ladebalken-fuellung" />
    </div>
  );
}
