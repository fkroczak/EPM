/** Gemeinsame Abfragen (Stammdaten werden selten geändert und dürfen länger im Zwischenspeicher bleiben). */
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "./api";
import type { Arzt, Auswahlwert, Diagnosevorlage, Einstellungen, Laborparameter, Praeparat, Versorger } from "./typen";

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

/** Katalog der Laborwerte (F112) – Grundlage der Erfassungsmaske eines Befunds */
export function useLaborparameter(nurAktiv = true) {
  return useQuery({
    queryKey: ["laborparameter", nurAktiv],
    queryFn: () => api<Laborparameter[]>(`laborparameter/${abfrage({ aktiv: nurAktiv ? "true" : undefined })}`),
    staleTime: 5 * 60_000,
  });
}

/** Die mitwachsende Diagnoseliste mit ICD-Code (F117) */
export function useDiagnoseliste(nurAktiv = true) {
  return useQuery({
    queryKey: ["diagnoseliste", nurAktiv],
    queryFn: () => api<Diagnosevorlage[]>(`diagnoseliste/${abfrage({ aktiv: nurAktiv ? "true" : undefined })}`),
    staleTime: 60_000,
  });
}

export function useVersorgerListe() {
  return useQuery({
    queryKey: ["versorger"],
    queryFn: () => api<Versorger[]>("versorger/"),
    staleTime: 60_000,
  });
}

/** Gemeinsame Ärzteliste */
export function useAerzteListe() {
  return useQuery({
    queryKey: ["aerzte"],
    queryFn: () => api<Arzt[]>("aerzte/"),
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

export type Absender = { name: string; strasse: string; plz: string; ort: string; telefon: string; fax: string; email: string;
  internet: string; fusszeile: string };
export type Briefkopf = {
  aktiv: "stiftung" | "gug";
  absender: Record<"stiftung" | "gug", Absender>;
  arten: { code: string; name: string }[];
  logo: { vorhanden: boolean; mime?: string; sha256?: string; breite?: number; hoehe?: number; hochgeladen_am?: string };
};

export function useBriefkopf() {
  return useQuery({
    queryKey: ["briefkopf"],
    queryFn: () => api<Briefkopf>("briefkopf/"),
    staleTime: 5 * 60_000,
  });
}
