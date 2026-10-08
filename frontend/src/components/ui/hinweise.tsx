/**
 * Rückmeldungen als Overlay (Wunsch 08.10.2026, wie im alten EPM): Nach dem Speichern erscheint oben in der Mitte ein
 * grünes Overlay und blendet sich nach wenigen Sekunden aus – es quittiert die Aktion. Fehler erscheinen rot und
 * bleiben deutlich länger stehen; sie lassen sich mit „×“ schließen. Das Overlay fängt keine Klicks ab (nur das „×“),
 * damit darunter weitergearbeitet werden kann. Für Screenreader angesagt (Bestätigung höflich, Fehler sofort).
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { HINWEIS } from "@/lib/api";
import type { ReactNode } from "react";
import { cx } from "./basis";
import { Icon } from "./icon";

type Art = "ok" | "fehler";
type Hinweis = { id: number; text: string; art: Art; geht: boolean };
type Kontext = { melden: (text: string, art?: Art) => void };

/** Standzeiten: grüne Bestätigung kurz, rote Fehler länger */
export const STANDZEIT_MS: Record<Art, number> = { ok: 2800, fehler: 9000 };
const AUSBLENDEN_MS = 350;

const HinweisKontext = createContext<Kontext>({ melden: () => undefined });

export function HinweisProvider({ children }: { children: ReactNode }) {
  const [liste, setListe] = useState<Hinweis[]>([]);
  const zaehler = useRef(0);
  const uhren = useRef(new Map<number, number>());

  const entfernen = useCallback((id: number) => {
    window.clearTimeout(uhren.current.get(id));
    setListe((l) => l.map((h) => (h.id === id ? { ...h, geht: true } : h)));
    uhren.current.set(id, window.setTimeout(() => {
      uhren.current.delete(id);
      setListe((l) => l.filter((h) => h.id !== id));
    }, AUSBLENDEN_MS));
  }, []);
  const starten = useCallback((id: number, art: Art) => {
    window.clearTimeout(uhren.current.get(id));
    uhren.current.set(id, window.setTimeout(() => entfernen(id), STANDZEIT_MS[art]));
  }, [entfernen]);

  const melden = useCallback((text: string, art: Art = "ok") => {
    const id = ++zaehler.current;
    // gleiche Meldung kurz hintereinander nur einmal (z. B. zwei Anfragen mit demselben Fehler)
    setListe((l) => [...l.filter((h) => !(h.text === text && h.art === art)), { id, text, art, geht: false }].slice(-4));
    starten(id, art);
  }, [starten]);

  useEffect(() => {
    const aufEreignis = (e: Event) => melden(String((e as CustomEvent).detail ?? ""), "fehler");
    window.addEventListener(HINWEIS, aufEreignis);
    const alle = uhren.current;
    return () => {
      window.removeEventListener(HINWEIS, aufEreignis);
      for (const t of alle.values()) window.clearTimeout(t);
    };
  }, [melden]);

  return (
    <HinweisKontext.Provider value={{ melden }}>
      {children}
      <div className="rueckmeldungen nicht-drucken" data-testid="rueckmeldungen">
        {liste.map((h) => (
          <div key={h.id} role={h.art === "fehler" ? "alert" : "status"} aria-live={h.art === "fehler" ? "assertive" : "polite"}
            data-art={h.art} data-testid="rueckmeldung"
            className={cx("rueckmeldung", h.art, h.geht && "geht")}>
            <Icon name={h.art === "ok" ? "haken" : "warnung"} groesse={20} />
            <span className="rueckmeldung-text">{h.text}</span>
            <button type="button" className="rueckmeldung-zu" aria-label="Meldung schließen" onClick={() => entfernen(h.id)}>
              <Icon name="x" groesse={16} />
            </button>
          </div>
        ))}
      </div>
    </HinweisKontext.Provider>
  );
}

export function useHinweis() {
  return useContext(HinweisKontext).melden;
}
