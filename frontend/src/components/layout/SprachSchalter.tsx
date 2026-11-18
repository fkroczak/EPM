/**
 * Sprachschalter mit Flaggen (Dreisprachigkeit der RGC, 18.11.2026): Deutsch, Englisch, Lettisch. Nur in der Firma
 * Regeneration Clinic sichtbar; die Wahl wird im Benutzerkonto gespeichert und gilt auf allen Geräten.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { MEHRSPRACHIGE_FIRMA, SPRACHEN, useSprache, useT } from "@/lib/sprache";
import type { Sprache } from "@/lib/sprache";
import type { Ich } from "@/lib/typen";
import { cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";

/** Flaggen als SVG im Verhältnis 3:2 (Lettland offiziell 2:1, hier gleiche Höhe wie die anderen) */
const FLAGGEN: Record<Sprache, ReactNode> = {
  de: (
    <>
      <rect width="30" height="20" fill="#000" />
      <rect y="6.667" width="30" height="6.667" fill="#DD0000" />
      <rect y="13.333" width="30" height="6.667" fill="#FFCE00" />
    </>
  ),
  en: (
    <>
      <clipPath id="flagge-uk"><rect width="30" height="20" /></clipPath>
      <g clipPath="url(#flagge-uk)">
        <rect width="30" height="20" fill="#012169" />
        <path d="M0,0 30,20 M30,0 0,20" stroke="#fff" strokeWidth="4" />
        <path d="M0,0 30,20 M30,0 0,20" stroke="#C8102E" strokeWidth="1.6" />
        <path d="M15,0 V20 M0,10 H30" stroke="#fff" strokeWidth="6" />
        <path d="M15,0 V20 M0,10 H30" stroke="#C8102E" strokeWidth="3.6" />
      </g>
    </>
  ),
  lv: (
    <>
      {/* karminrot – weiß – karminrot im Verhältnis 2 : 1 : 2 */}
      <rect width="30" height="20" fill="#9E3039" />
      <rect y="8" width="30" height="4" fill="#fff" />
    </>
  ),
};

export function Flagge({ sprache, className }: { sprache: Sprache; className?: string }) {
  return (
    <svg viewBox="0 0 30 20" width="24" height="16" aria-hidden="true" className={cx("block rounded-[2px]", className)}>
      {FLAGGEN[sprache]}
    </svg>
  );
}

export function SprachSchalter({ className }: { className?: string }) {
  const { ich, setIch } = useAuth();
  const sprache = useSprache();
  const t = useT();
  const melden = useHinweis();
  const [laeuft, setLaeuft] = useState(false);
  if (ich?.firma !== MEHRSPRACHIGE_FIRMA) return null;
  const waehlen = async (neu: Sprache) => {
    if (neu === sprache || laeuft) return;
    setLaeuft(true);
    try {
      setIch(await api<Ich>("auth/ich/", { method: "PATCH", body: { sprache: neu } }));
    } catch (e) {
      melden(e instanceof Error ? e.message : "Sprache konnte nicht gespeichert werden.", "fehler");
    } finally {
      setLaeuft(false);
    }
  };
  return (
    <div role="group" aria-label={t("Sprache")} data-testid="sprachschalter" className={cx("flex items-center gap-0.5", className)}>
      {SPRACHEN.map((s) => {
        const aktiv = s.wert === sprache;
        return (
          <button key={s.wert} type="button" title={s.name} aria-label={s.name} aria-pressed={aktiv} disabled={laeuft}
            data-sprache={s.wert} onClick={() => void waehlen(s.wert)}
            className={cx("inline-flex items-center justify-center p-1 rounded-md border-2 bg-transparent cursor-pointer",
              aktiv ? "border-akzent" : "border-transparent opacity-55 hover:opacity-100")}>
            <Flagge sprache={s.wert} />
          </button>
        );
      })}
    </div>
  );
}
