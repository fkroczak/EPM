/** Konten mit Handlungsbedarf (Startseite: Zähler und Kachel „Konten“). Eigene Datei, damit die Startseite den Zähler
 *  abfragen kann, ohne die Kacheln der Administration zu laden (seiten/start/admin.tsx wird erst bei Bedarf geladen). */
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type Konto = { id: number; benutzername: string; anzeigename: string; rolle: string;
  probleme: ("gesperrt" | "einmal_kennwort" | "einmal_kennwort_abgelaufen" | "ohne_2fa" | "notfallcodes")[];
  gesperrt_am: string | null; sperrgrund: string; fehlversuche: number; einmal_kennwort_gueltig_bis: string | null;
  notfallcodes_uebrig: number; notfallcodes_gesamt: number };

export function useKonten(aktiv: boolean) {
  return useQuery({ queryKey: ["benutzer", "konten"], queryFn: () => api<Konto[]>("benutzer/konten/"), enabled: aktiv, refetchInterval: 60_000 });
}
