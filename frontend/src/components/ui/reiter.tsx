/**
 * Reiter für lange Seiten (Wunsch 10.10.2026: Administration › System und › Backup in Bereiche gliedern statt endlos zu
 * scrollen). Aussehen wie die Umschalter („segmente“); am Telefon wischt man die Leiste seitlich (index.css,
 * nav.segmente). Der gewählte Reiter steht in der Adresse (``?reiter=…``), damit Links (z. B. von der Systemverwaltung)
 * direkt dorthin führen und „Zurück“ im Browser funktioniert.
 */
import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router";
import { cx } from "./basis";

export type ReiterEintrag<T extends string> = { wert: T; text: ReactNode; zahl?: number; warn?: boolean; testid?: string };

/** Gewählter Reiter aus ``?reiter=``; unbekannte Werte fallen auf den ersten zurück. */
export function useReiter<T extends string>(werte: readonly T[]): [T, (w: T) => void] {
  const [suche, setSuche] = useSearchParams();
  const roh = suche.get("reiter") as T | null;
  const wert = roh && werte.includes(roh) ? roh : werte[0];
  const setzen = (w: T) => {
    const neu = new URLSearchParams(suche);
    if (w === werte[0]) neu.delete("reiter"); else neu.set("reiter", w);
    setSuche(neu, { replace: false });
  };
  return [wert, setzen];
}

export function Reiter<T extends string>({ label, eintraege, wert, onWahl, testid }: {
  label: string; eintraege: ReiterEintrag<T>[]; wert: T; onWahl: (w: T) => void; testid?: string;
}) {
  const leiste = useRef<HTMLElement>(null);
  const id = useId();
  // am Telefon: Rand ausblenden, wo noch Reiter kommen (wie bei den Reitern der Akte)
  useEffect(() => {
    const el = leiste.current;
    if (!el) return;
    const pruefen = () => {
      el.classList.toggle("am-anfang", el.scrollLeft <= 1);
      el.classList.toggle("am-ende", el.scrollLeft + el.clientWidth >= el.scrollWidth - 1);
    };
    pruefen();
    el.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
    el.addEventListener("scroll", pruefen, { passive: true });
    window.addEventListener("resize", pruefen);
    return () => { el.removeEventListener("scroll", pruefen); window.removeEventListener("resize", pruefen); };
  }, [wert]);
  return (
    <nav ref={leiste} aria-label={label} className="segmente self-start max-w-full" data-testid={testid}>
      <div role="tablist" aria-label={label} className="contents">
        {eintraege.map((e) => (
          <button key={e.wert} type="button" role="tab" id={`${id}-${e.wert}`} aria-selected={e.wert === wert}
            className="segment" data-testid={e.testid} onClick={() => onWahl(e.wert)}
            onKeyDown={(ev) => {
              // Pfeiltasten wechseln wie bei Reitern üblich
              if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
              const i = eintraege.findIndex((x) => x.wert === e.wert);
              const n = eintraege[(i + (ev.key === "ArrowRight" ? 1 : eintraege.length - 1)) % eintraege.length];
              onWahl(n.wert);
              (ev.currentTarget.parentElement?.querySelector(`#${CSS.escape(`${id}-${n.wert}`)}`) as HTMLElement | null)?.focus();
            }}>
            {e.text}
            {e.zahl ? <span className={cx("chip h-5 min-h-5 px-1.5 text-[0.6875rem]", e.warn ? "warn" : undefined)}>{e.zahl}</span> : null}
          </button>
        ))}
      </div>
    </nav>
  );
}

/** Inhalt eines Reiters (für Bildschirmleser mit dem Reiter verbunden) */
export function ReiterInhalt({ children, className, testid }: { children: ReactNode; className?: string; testid?: string }) {
  return <div role="tabpanel" className={cx("flex flex-col gap-4 min-w-0", className)} data-testid={testid}>{children}</div>;
}
