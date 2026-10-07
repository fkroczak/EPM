/**
 * Zählt die laufenden Anfragen an den Server – für den Ladebalken am oberen Rand (Wunsch 07.10.2026, F124).
 *
 * Jede Anfrage über ``api`` und ``apiDatei`` meldet sich hier an und ab; damit erfasst der Balken alles, was auf
 * den Server wartet: Laden, Speichern, Hochladen, PDFs, die Abfragen der Aufträge. Ohne Abhängigkeit von der
 * Abfrage-Bibliothek, damit auch direkte Aufrufe (etwa das Hochladen von Dateien) sichtbar sind.
 */
import { useEffect, useSyncExternalStore } from "react";

let laufend = 0;
/** Arbeit, die auf dem Server läuft und auf die jemand wartet (Aufträge des Systemagenten) – je Seite ein Schlüssel */
const hintergrund = new Set<string>();
const zuhoerer = new Set<() => void>();

function melden() {
  for (const z of zuhoerer) z();
}

/** Beginn einer Anfrage; die zurückgegebene Funktion meldet ihr Ende (auch bei Fehler oder Abbruch aufrufen). */
export function anfrageBeginnt(): () => void {
  laufend += 1;
  melden();
  let beendet = false;
  return () => {
    if (beendet) return;
    beendet = true;
    laufend = Math.max(0, laufend - 1);
    melden();
  };
}

function abonnieren(z: () => void) {
  zuhoerer.add(z);
  return () => { zuhoerer.delete(z); };
}

/** Wie viele Anfragen gerade laufen – aktualisiert sich von selbst. */
export function useLaufendeAnfragen(): number {
  return useSyncExternalStore(abonnieren, () => laufend, () => 0);
}

/**
 * Hintergrundarbeit anmelden, solange ``aktiv`` gilt – z. B. „ein Auftrag läuft auf dem Server“. Der Balken bleibt
 * dann durchgehend in Bewegung, bis die Arbeit beendet ist, auch wenn die einzelnen Statusabfragen nur Millisekunden
 * dauern (Wunsch 07.10.2026). Beim Verlassen der Seite endet die Anmeldung von selbst.
 */
export function useHintergrundarbeit(schluessel: string, aktiv: boolean) {
  useEffect(() => {
    if (!aktiv) return;
    hintergrund.add(schluessel);
    melden();
    return () => {
      hintergrund.delete(schluessel);
      melden();
    };
  }, [schluessel, aktiv]);
}

/** Läuft gerade Hintergrundarbeit, auf die jemand wartet? */
export function useHintergrundAktiv(): boolean {
  return useSyncExternalStore(abonnieren, () => hintergrund.size > 0, () => false);
}
