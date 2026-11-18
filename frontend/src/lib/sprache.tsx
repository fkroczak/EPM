/**
 * Sprache der Oberfläche (Dreisprachigkeit der RGC, 18.11.2026): Deutsch, Englisch, Lettisch. Gewählt wird mit den
 * Flaggen in der Kopfzeile, gespeichert im Benutzerkonto (``ich.sprache``). Gilt nur in der Firma Regeneration Clinic
 * („rg“); in der DSKM bleibt alles deutsch. Schlüssel der Übersetzung ist der deutsche Text (lib/uebersetzungen.ts) –
 * fehlt ein Eintrag, bleibt er deutsch.
 */
import { useCallback, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { UEBERSETZUNGEN } from "@/lib/uebersetzungen";

export type Sprache = "de" | "en" | "lv";

export const SPRACHEN: { wert: Sprache; name: string }[] = [
  { wert: "de", name: "Deutsch" },
  { wert: "en", name: "English" },
  { wert: "lv", name: "Latviešu" },
];

/** Firma, in der die Sprache umschaltbar ist */
export const MEHRSPRACHIGE_FIRMA = "rg";

/** Deutscher Text → Text in der Sprache (ohne Eintrag: deutsch) */
export function uebersetze(text: string, sprache: Sprache): string {
  if (sprache === "de" || !text) return text;
  return UEBERSETZUNGEN[text]?.[sprache] ?? text;
}

/** Wirksame Sprache: gespeicherte Wahl nur in der RGC, sonst Deutsch */
export function useSprache(): Sprache {
  const { ich } = useAuth();
  const s = ich?.firma === MEHRSPRACHIGE_FIRMA ? ich.sprache : undefined;
  return s === "en" || s === "lv" ? s : "de";
}

/** ``const t = useT(); t("Patienten")`` → „Pacienti“ bei Lettisch */
export function useT(): (text: string) => string {
  const sprache = useSprache();
  return useCallback((text: string) => uebersetze(text, sprache), [sprache]);
}

/** Setzt ``<html lang>`` passend zur Sprache (einmal in der Shell) */
export function useSpracheImDokument(): void {
  const sprache = useSprache();
  useEffect(() => {
    document.documentElement.lang = sprache;
  }, [sprache]);
}
