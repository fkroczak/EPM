/**
 * Reihenfolge per Ziehen (Maus) oder per Pfeiltasten auf dem Griff (Tastatur) – ohne Zusatzbibliothek.
 */
import { useState } from "react";
import type { DragEvent, KeyboardEvent } from "react";

export function verschiebe<T>(liste: T[], von: number, nach: number): T[] {
  const neu = [...liste];
  const [x] = neu.splice(von, 1);
  neu.splice(nach, 0, x);
  return neu;
}

/** Liefert Props für Zeilen (draggable) und Griffe (Tastatur). */
export function useSortierbar<T>(liste: T[], onAendern: (neu: T[]) => void) {
  const [zieht, setZieht] = useState<number | null>(null);
  const [ueber, setUeber] = useState<number | null>(null);
  return {
    zieht,
    ueber,
    zeile: (i: number) => ({
      draggable: true,
      onDragStart: (e: DragEvent) => {
        setZieht(i);
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(i));
      },
      onDragOver: (e: DragEvent) => {
        e.preventDefault();
        setUeber(i);
      },
      onDragLeave: () => setUeber((u) => (u === i ? null : u)),
      onDrop: (e: DragEvent) => {
        e.preventDefault();
        const von = zieht ?? Number(e.dataTransfer.getData("text/plain"));
        setZieht(null);
        setUeber(null);
        if (!Number.isNaN(von) && von !== i) onAendern(verschiebe(liste, von, i));
      },
      onDragEnd: () => {
        setZieht(null);
        setUeber(null);
      },
    }),
    griff: (i: number, name: string, gruppe = "sortierung") => ({
      "aria-label": `${name} verschieben (Pfeiltasten)`,
      "data-griff-gruppe": gruppe,
      onKeyDown: (e: KeyboardEvent) => {
        const zurueck = e.key === "ArrowUp" || e.key === "ArrowLeft";
        const vor = e.key === "ArrowDown" || e.key === "ArrowRight";
        if (!zurueck && !vor) return;
        e.preventDefault();
        const ziel = zurueck ? i - 1 : i + 1;
        if (ziel < 0 || ziel >= liste.length) return;
        onAendern(verschiebe(liste, i, ziel));
        window.requestAnimationFrame(() => {
          const griffe = document.querySelectorAll<HTMLElement>(`[data-griff-gruppe="${gruppe}"]`);
          griffe[ziel]?.focus();
        });
      },
    }),
  };
}
