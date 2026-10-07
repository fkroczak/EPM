/**
 * Ladebalken am oberen Rand (Wunsch 07.10.2026, F124): Sobald eine Anfrage an den Server läuft – Laden, Speichern,
 * Hochladen, PDF, Aufträge –, füllt sich oben ein schmaler Balken und ein Lichtstreifen wandert darüber. Ist alles
 * beantwortet, läuft er voll und blendet aus.
 *
 * Ganz kurze Anfragen (unter 150 ms) zeigen nichts, sonst würde der Balken bei jeder Statusabfrage flackern.
 */
import { useEffect, useState } from "react";
import { useLaufendeAnfragen } from "@/lib/laden";
import { cx } from "./basis";

const VERZOEGERUNG_MS = 150;   // so lange darf eine Anfrage dauern, ohne dass der Balken erscheint
const AUSBLENDEN_MS = 450;     // Zeit für „voll laufen und ausblenden“

export function Ladebalken() {
  const laufend = useLaufendeAnfragen() > 0;
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
  return (
    <div className={cx("ladebalken", stufe === "fertig" && "fertig")} role="progressbar" aria-label="Daten werden übertragen"
      aria-busy={stufe === "laeuft" || undefined} data-testid="ladebalken" data-stufe={stufe}>
      <div className="ladebalken-fuellung" />
    </div>
  );
}
