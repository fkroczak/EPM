/**
 * Vorladen (Performance-Prüfung 14.11.2026) – nur Lesen, ändert nichts am Verhalten:
 *
 * 1. Seiten-Dateien im Leerlauf: Nach dem Start lädt der Browser die Dateien der häufigsten Seiten (Patienten, Akte,
 *    Kalender …), sobald er nichts anderes zu tun hat. Ein Klick wartet dann nicht mehr auf das Netz.
 * 2. Akte beim Überfahren: Bleibt die Maus kurz auf einem Link zu einer Akte, holt EPM deren Kopfdaten schon vorab
 *    (gleiche Abfrage wie die Akte selbst). Ohne Ladebalken und als Hintergrundabfrage: verlängert die Sitzung nicht.
 */
import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Patient } from "./typen";

const SEITEN: (() => Promise<unknown>)[] = [
  () => import("@/seiten/Patienten"),
  () => import("@/seiten/akte/Akte"),
  () => import("@/seiten/akte/Uebersicht"),
  () => import("@/seiten/akte/Kontakte"),
  () => import("@/seiten/akte/Plaene"),
  () => import("@/seiten/akte/Dokumente"),
  () => import("@/seiten/Kalender"),
  () => import("@/seiten/Infusionsplaene"),
];

export function useVorladen() {
  const qc = useQueryClient();
  useEffect(() => {
    const w = window as Window & { requestIdleCallback?: (f: () => void, o?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void };
    const laden = () => { for (const s of SEITEN) void s().catch(() => { /* beim Klick erneut versucht */ }); };
    const leerlauf = w.requestIdleCallback ? w.requestIdleCallback(laden, { timeout: 5000 }) : window.setTimeout(laden, 2000);

    let warten = 0;
    const ueber = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      const link = (e.target as Element | null)?.closest?.("a[href]");
      const treffer = link?.getAttribute("href")?.match(/^\/patienten\/(\d+)(?:[/?#]|$)/);
      window.clearTimeout(warten);
      if (!treffer) return;
      const pid = Number(treffer[1]);
      warten = window.setTimeout(() => {
        // gleicher Schlüssel wie in seiten/akte/Akte.tsx; frische Daten nicht erneut holen (staleTime wie in main.tsx)
        void qc.prefetchQuery({ queryKey: ["patient", pid], staleTime: 20_000,
          queryFn: () => api<Patient>(`patienten/${pid}/`, { hintergrund: true, still: true }) });
      }, 100);
    };
    document.addEventListener("pointerover", ueber, { passive: true });
    return () => {
      document.removeEventListener("pointerover", ueber);
      window.clearTimeout(warten);
      if (w.cancelIdleCallback) w.cancelIdleCallback(leerlauf); else window.clearTimeout(leerlauf);
    };
  }, [qc]);
}
