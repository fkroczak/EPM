/**
 * Terminbestätigung automatisch vorbereiten (F185, Automatisierungen für die Pflege 10.10.2026).
 *
 * Nach dem Speichern eines neuen oder verschobenen Praxistermins fragt EPM: „Terminbestätigung an Frau X schicken?“
 * Ein Klick öffnet „Schreiben und E-Mail“ (F172) mit genau diesem Termin – dort entsteht die E-Mail (Outlook-Entwurf)
 * oder die PDF. Versendet wird nichts von allein; „Nicht jetzt“ geht immer. Sobald eine PDF oder E-Mail erstellt ist,
 * merkt sich der Termin das („Bestätigung erstellt am …“); verschiebt man ihn, fehlt sie wieder.
 * Das Angebot lässt sich unter Vorlagen › Grenzwerte abschalten.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { datum, terminZeit, uhrzeit } from "@/lib/format";
import type { Termin } from "@/lib/typen";
import { Chip, Knopf, Meldung } from "@/components/ui/basis";
import { Dialog, Menue } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { SchreibenDialog } from "@/components/SchreibenDialog";

/** Braucht dieser Termin noch eine Bestätigung? (Praxistermin, Angebot an, noch keine erstellt) */
export function bestaetigungFehlt(t: Termin | null | undefined): boolean {
  return !!t?.bestaetigung?.angebot && !t.bestaetigung_am;
}

function wo(t: Termin) {
  return t.ort_name || t.bei || "Praxistermin";
}

const WEGE = { telefonisch: "telefonisch", persoenlich: "persönlich", anderweitig: "anderweitig" } as const;

/** „Bestätigung erstellt am 10.10.“ bzw. „Bestätigt telefonisch am 10.10.“ bzw. „Bestätigung fehlt“ – nur bei
 *  Praxisterminen, sonst nichts */
export function BestaetigungChip({ termin }: { termin: Termin }) {
  if (termin.bestaetigung_am) {
    const weg = termin.bestaetigung_weg ? WEGE[termin.bestaetigung_weg] : "";
    return (
      <Chip art="ok" title={`Terminbestätigung ${weg || "erstellt"} am ${datum(termin.bestaetigung_am)} um ${uhrzeit(termin.bestaetigung_am)}`
        + (termin.bestaetigung_von_name ? ` von ${termin.bestaetigung_von_name}` : "")} data-testid="bestaetigung-erstellt">
        {weg ? `Bestätigt ${weg} am` : "Bestätigung erstellt am"} {datum(termin.bestaetigung_am).slice(0, 6)}
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

/** „Schon bestätigt …“ (Wunsch 11.10.2026): „Bestätigung fehlt“ wegklicken, wenn der Termin schon telefonisch,
 *  persönlich oder anderweitig bestätigt ist – vermerkt am Termin (Person, Zeitpunkt, Weg), steht im Verlauf. */
export function SchonBestaetigt({ termin, onFertig }: { termin: Termin; onFertig?: (t: Termin) => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const vermerken = useMutation({
    mutationFn: (weg: keyof typeof WEGE) => api<Termin>(`termine/${termin.id}/bestaetigt/`, { body: { weg } }),
    onSuccess: (t) => {
      for (const k of [["startseite"], ["termine"], ["kalender"], ["patient", t.patient]]) void qc.invalidateQueries({ queryKey: k });
      melden(`Terminbestätigung vermerkt (${WEGE[t.bestaetigung_weg as keyof typeof WEGE] ?? "anderweitig"}).`);
      onFertig?.(t);
    },
    onError: (e) => melden(e.message, "fehler"),
  });
  return (
    <Menue label={`Schon bestätigt: ${termin.patient_name}`} ausloeser={<>Schon bestätigt …</>}
      eintraege={(Object.keys(WEGE) as (keyof typeof WEGE)[]).map((w) => ({
        text: `${WEGE[w].charAt(0).toUpperCase()}${WEGE[w].slice(1)} bestätigt`, onClick: () => vermerken.mutate(w),
      }))} />
  );
}
