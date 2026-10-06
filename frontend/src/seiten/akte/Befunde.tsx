/**
 * Gemeinsames zu Labor und BIA: die Kurzfassung für die Übersicht der Akte und der Hinweis „zu alt“.
 *
 * Die Masken selbst stehen in eigenen Reitern (Aufteilung 07.10.2026, F121): Labor.tsx und Bia.tsx. Ab welchem Alter
 * ein Befund als zu alt gilt, steht unter Vorlagen › Grenzwerte (F120, Standard zwölf Monate).
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useEinstellungen } from "@/lib/daten";
import { datum, zahl } from "@/lib/format";
import type { BiaMessung, Laborbefund } from "@/lib/typen";
import { Anzeige, Meldung } from "@/components/ui/basis";

/** Monate zwischen ``iso`` und heute (angefangene Monate zählen nicht). */
function monateSeit(iso: string): number {
  const a = new Date(iso);
  const b = new Date();
  let m = (b.getFullYear() - a.getFullYear()) * 12 + (b.getMonth() - a.getMonth());
  if (b.getDate() < a.getDate()) m -= 1;
  return m;
}

/** „Der letzte Laborbefund ist älter als zwölf Monate“ – Grenze aus den Einstellungen (F120). */
export function AlterHinweis({ art, am, was }: { art: "labor" | "bia"; am?: string | null; was: string }) {
  const e = useEinstellungen();
  const grenze = Number(e.data?.[art === "labor" ? "labor_alter_warnung_monate" : "bia_alter_warnung_monate"] ?? 12) || 12;
  if (!am) return null;
  const alt = monateSeit(am) >= grenze;
  return (
    <span data-testid={`alter-${art}`} className={alt ? "contents" : "text-[0.8125rem] gedaempft"}>
      {alt
        ? <Meldung art="warn">Der letzte {was} ist vom {datum(am)} und damit älter als {grenze} Monate.</Meldung>
        : <>Letzte Erfassung {datum(am)}</>}
    </span>
  );
}

/** Kurzfassung für die Übersicht der Akte: letzter Laborbefund und letzte BIA-Messung. */
export function BefundeKurz({ patientId }: { patientId: number }) {
  const befunde = useQuery({ queryKey: ["laborbefunde", patientId], queryFn: () => api<Laborbefund[]>(`laborbefunde/?patient=${patientId}`) });
  const bia = useQuery({ queryKey: ["bia", patientId], queryFn: () => api<BiaMessung[]>(`bia-messungen/?patient=${patientId}`) });
  const letzterBefund = befunde.data?.[0];
  const letzteBia = bia.data?.[0];
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Anzeige label="Letzter Laborbefund">
        {letzterBefund ? `${datum(letzterBefund.abgenommen_am)} · ${letzterBefund.anzahl_werte} Werte` : ""}
      </Anzeige>
      <Anzeige label="Letzte BIA-Messung">
        {letzteBia ? `${datum(letzteBia.gemessen_am)}${letzteBia.bcm_kg != null ? ` · BCM ${zahl(letzteBia.bcm_kg, 1)} kg` : ""}` : ""}
      </Anzeige>
    </div>
  );
}
