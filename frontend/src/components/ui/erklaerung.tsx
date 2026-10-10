/**
 * Kleines „?“ neben einer Überschrift: Ein Klick (oder Enter) zeigt eine kurze Erklärung in Alltagssprache, ein zweiter
 * Klick, Escape oder ein Klick daneben schließt sie (Vorlagen-Portal, F180). Kein Tooltip, damit es auch am Tablet geht.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { cx } from "./basis";

export function Erklaerung({ titel, children, className }: { titel: string; children: ReactNode; className?: string }) {
  const [offen, setOffen] = useState(false);
  const id = useId();
  const rahmen = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!offen) return;
    const zu = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !rahmen.current?.contains(e.target as Node)) setOffen(false);
    };
    document.addEventListener("mousedown", zu);
    document.addEventListener("keydown", zu);
    return () => { document.removeEventListener("mousedown", zu); document.removeEventListener("keydown", zu); };
  }, [offen]);
  return (
    <span ref={rahmen} className={cx("relative inline-flex align-middle normal-case tracking-normal font-normal", className)}>
      <button type="button" aria-label={`Erklärung: ${titel}`} aria-expanded={offen} aria-controls={offen ? id : undefined}
        onClick={() => setOffen(!offen)}
        className="w-[1.125rem] h-[1.125rem] rounded-full border border-rand bg-flaeche text-[0.6875rem] leading-none font-semibold gedaempft cursor-pointer p-0 hover:text-akzent-text hover:border-akzent">
        ?
      </button>
      {offen ? (
        <span id={id} role="note"
          className="absolute z-30 top-[calc(100%+0.375rem)] left-1/2 -translate-x-1/2 w-[17.5rem] max-w-[80vw] p-3 rounded-lg border border-rand bg-flaeche shadow-lg text-[0.8125rem] leading-normal text-tinte text-left">
          <strong className="block mb-1">{titel}</strong>{children}
        </span>
      ) : null}
    </span>
  );
}
