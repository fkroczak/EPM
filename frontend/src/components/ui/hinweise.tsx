/** Kurze Rückmeldungen („Gespeichert“) unten rechts, für Screenreader angesagt. */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { HINWEIS } from "@/lib/api";
import type { ReactNode } from "react";
import { cx } from "./basis";

type Hinweis = { id: number; text: string; art: "ok" | "fehler" };
type Kontext = { melden: (text: string, art?: "ok" | "fehler") => void };

const HinweisKontext = createContext<Kontext>({ melden: () => undefined });

export function HinweisProvider({ children }: { children: ReactNode }) {
  const [liste, setListe] = useState<Hinweis[]>([]);
  const zaehler = useRef(0);
  const melden = useCallback((text: string, art: "ok" | "fehler" = "ok") => {
    const id = ++zaehler.current;
    setListe((l) => [...l, { id, text, art }]);
    window.setTimeout(() => setListe((l) => l.filter((h) => h.id !== id)), art === "fehler" ? 7000 : 3500);
  }, []);
  useEffect(() => {
    const aufEreignis = (e: Event) => melden(String((e as CustomEvent).detail ?? ""), "fehler");
    window.addEventListener(HINWEIS, aufEreignis);
    return () => window.removeEventListener(HINWEIS, aufEreignis);
  }, [melden]);
  return (
    <HinweisKontext.Provider value={{ melden }}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 nicht-drucken">
        {liste.map((h) => (
          <div key={h.id} role={h.art === "fehler" ? "alert" : "status"}
            className={cx("meldung shadow-md", h.art === "ok" ? "ok" : "fehler")}>
            {h.text}
          </div>
        ))}
      </div>
    </HinweisKontext.Provider>
  );
}

export function useHinweis() {
  return useContext(HinweisKontext).melden;
}
