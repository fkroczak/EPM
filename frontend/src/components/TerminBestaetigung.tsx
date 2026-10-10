/**
 * Terminbestätigung automatisch vorbereiten (F185, Automatisierungen für die Pflege 10.10.2026).
 *
 * Nach dem Speichern eines neuen oder verschobenen Praxistermins fragt EPM: „Terminbestätigung an Frau X schicken?“
 * Ein Klick öffnet „Schreiben und E-Mail“ (F172) mit genau diesem Termin – dort entsteht die E-Mail (Outlook-Entwurf)
 * oder die PDF. Versendet wird nichts von allein; „Nicht jetzt“ geht immer. Sobald eine PDF oder E-Mail erstellt ist,
 * merkt sich der Termin das („Bestätigung erstellt am …“); verschiebt man ihn, fehlt sie wieder.
 * Das Angebot lässt sich unter Vorlagen › Grenzwerte abschalten.
 */
import { useQueryClient } from "@tanstack/react-query";
import { datum, terminZeit, uhrzeit } from "@/lib/format";
import type { Termin } from "@/lib/typen";
import { Chip, Knopf, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { SchreibenDialog } from "@/components/SchreibenDialog";

/** Braucht dieser Termin noch eine Bestätigung? (Praxistermin, Angebot an, noch keine erstellt) */
export function bestaetigungFehlt(t: Termin | null | undefined): boolean {
  return !!t?.bestaetigung?.angebot && !t.bestaetigung_am;
}

function wo(t: Termin) {
  return t.ort_name || t.bei || "Praxistermin";
}

/** „Bestätigung erstellt am 10.10.“ bzw. „Bestätigung fehlt“ – nur bei Praxisterminen, sonst nichts */
export function BestaetigungChip({ termin }: { termin: Termin }) {
  if (termin.bestaetigung_am) {
    return (
      <Chip art="ok" title={`Terminbestätigung erstellt am ${datum(termin.bestaetigung_am)} um ${uhrzeit(termin.bestaetigung_am)}`
        + (termin.bestaetigung_von_name ? ` von ${termin.bestaetigung_von_name}` : "")} data-testid="bestaetigung-erstellt">
        Bestätigung erstellt am {datum(termin.bestaetigung_am).slice(0, 6)}
      </Chip>
    );
  }
  return bestaetigungFehlt(termin) ? <Chip art="warn" data-testid="bestaetigung-fehlt">Bestätigung fehlt</Chip> : null;
}

/** Die Frage direkt nach dem Speichern: „Terminbestätigung an Frau X schicken?“ */
export function BestaetigungAngebot({ termin, onJa, onNein }: { termin: Termin | null; onJa: () => void; onNein: () => void }) {
  const t = termin;
  return (
    <Dialog offen={!!t} onOffen={(o) => { if (!o) onNein(); }} breite={520}
      titel={t ? `Terminbestätigung an ${t.bestaetigung?.anrede ?? t.patient_name} schicken?` : ""}
      beschreibung={t ? `${terminZeit(t.faellig_am, t.uhrzeit)} · ${wo(t)}` : undefined}
      fuss={<>
        <Knopf onClick={onNein}>Nicht jetzt</Knopf>
        <Knopf variante="pri" icon="mail" onClick={onJa}>Ja, Bestätigung vorbereiten</Knopf>
      </>}>
      <div data-testid="bestaetigung-angebot">
        <Meldung art="info">
          EPM bereitet die Terminbestätigung vor – {t?.bestaetigung?.email ? "als E-Mail-Entwurf mit PDF im Anhang oder als PDF zum Drucken"
            : "als PDF zum Drucken (in der Akte ist keine E-Mail-Adresse hinterlegt)"}. Verschickt wird erst, wenn du es selbst tust.
        </Meldung>
      </div>
    </Dialog>
  );
}

/** „Schreiben und E-Mail“ mit der Terminbestätigung für genau diesen Termin */
export function BestaetigungDialog({ termin, offen, onOffen }: { termin: Termin | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const qc = useQueryClient();
  if (!termin) return null;
  const neuLaden = () => {
    for (const k of [["startseite"], ["termine"], ["kalender"], ["patient", termin.patient]]) void qc.invalidateQueries({ queryKey: k });
  };
  return (
    <SchreibenDialog offen={offen} onOffen={onOffen} titel={`Terminbestätigung an ${termin.bestaetigung?.anrede ?? termin.patient_name}`}
      pfad={`patienten/${termin.patient}/schreiben/`} koerper={{ art: "terminbestaetigung", termin: termin.id }} ablegen
      onErzeugt={neuLaden}
      onAbgelegt={() => void qc.invalidateQueries({ queryKey: ["dokumente", termin.patient] })}
      optionen={
        <div className="flex items-center gap-2 flex-wrap text-[0.875rem]" data-testid="bestaetigung-termin">
          <span className="gedaempft">Termin:</span>
          <strong className="num">{terminZeit(termin.faellig_am, termin.uhrzeit)}</strong>
          <span>· {wo(termin)} · {termin.patient_name}</span>
          <BestaetigungChip termin={termin} />
        </div>
      } />
  );
}
