/**
 * Einheitliche Rückfrage (Vorschlag „Eine Sprache“, 08.10.2026) vor allem, was Daten löscht oder aus der Auswahl
 * nimmt: kurzer Satz, was passiert; der rote Knopf steht links (siehe .dialog-fuss .btn.dng), „Abbrechen“ rechts.
 */
import type { ReactNode } from "react";
import { Fehleranzeige, Knopf } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";

export function Bestaetigen({ offen, onOffen, titel, text, knopf, laedt, fehler, onJa, children }: {
  offen: boolean; onOffen: (o: boolean) => void; titel: string; text: ReactNode; knopf: string; laedt?: boolean;
  fehler?: unknown; onJa: () => void; children?: ReactNode;
}) {
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={titel} breite={480} beschreibung={text}
      fuss={<>
        <Knopf variante="dng" laedt={laedt} onClick={onJa} data-testid="bestaetigen">{knopf}</Knopf>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
      </>}>
      {children}
      <Fehleranzeige fehler={fehler} />
    </Dialog>
  );
}
