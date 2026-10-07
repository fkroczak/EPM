/**
 * Zählt die laufenden Anfragen an den Server – für den Ladebalken am oberen Rand (Wunsch 07.10.2026, F124).
 *
 * Jede Anfrage über ``api`` und ``apiDatei`` meldet sich hier an und ab; damit erfasst der Balken alles, was auf
 * den Server wartet: Laden, Speichern, Hochladen, PDFs, die Abfragen der Aufträge. Ohne Abhängigkeit von der
 * Abfrage-Bibliothek, damit auch direkte Aufrufe (etwa das Hochladen von Dateien) sichtbar sind.
 */
import { useSyncExternalStore } from "react";

let laufend = 0;
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
