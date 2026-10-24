/** Stand der Diktate für Navigation und Aufnahme (eigene Datei: die Seitenleiste lädt nicht die ganze Aufnahme). */
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useAuth } from "./auth";
import type { DiktatStand } from "./typen";

export function useDiktatStand(aktiv = true) {
  const { darf } = useAuth();
  return useQuery({
    queryKey: ["diktate", "stand"],
    queryFn: () => api<DiktatStand>("diktate/stand/", { hintergrund: true }),
    enabled: aktiv && (darf("diktieren") || darf("eintraege_erfassen")),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
