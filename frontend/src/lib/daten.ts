/** Gemeinsame Abfragen (Stammdaten werden selten geändert und dürfen länger im Zwischenspeicher bleiben). */
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "./api";
import type { Auswahlwert, Einstellungen, Praeparat, Versorger } from "./typen";

export function useAuswahl(liste: string, nurAktiv = true) {
  return useQuery({
    queryKey: ["auswahlwerte", liste, nurAktiv],
    queryFn: () => api<Auswahlwert[]>(`auswahlwerte/${abfrage({ liste, aktiv: nurAktiv ? "true" : undefined })}`),
    staleTime: 5 * 60_000,
  });
}

export function usePraeparate() {
  return useQuery({
    queryKey: ["praeparate"],
    queryFn: () => api<Praeparat[]>("praeparate/"),
    staleTime: 5 * 60_000,
  });
}

export function useVersorgerListe() {
  return useQuery({
    queryKey: ["versorger"],
    queryFn: () => api<Versorger[]>("versorger/"),
    staleTime: 60_000,
  });
}

export function useEinstellungen() {
  return useQuery({
    queryKey: ["einstellungen"],
    queryFn: () => api<Einstellungen>("einstellungen/"),
    staleTime: 5 * 60_000,
  });
}
