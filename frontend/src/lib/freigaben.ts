/** Menü „Freigaben“ (16.11.2026): Datenpflege-Vorschläge, Plan-Entwürfe, KI-Prüfungen – mit 60 s Rückgängig. */
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type ArztWerte = { name: string; praxis: string; fachrichtung: string; strasse: string; plz: string; ort: string;
  telefon: string; fax: string; email: string };
export type PersonWerte = { beziehung: string; name: string; telefon: string; mobil: string; email: string };
export type ArztTreffer = { id: number; name: string; praxis: string; ort: string; plz: string; strasse: string;
  telefon: string; email: string };

type SchrittBasis = { id: string; an: boolean; quelle: string; auszug: string; sicher: boolean; hinweis: string;
  abhaengig_von: string[] };
export type Schritt =
  | (SchrittBasis & { art: "arzt"; rolle: string; werte: ArztWerte; arzt_wahl: number | "neu" | "auto"; treffer: ArztTreffer[] })
  | (SchrittBasis & { art: "bezugsperson"; werte: PersonWerte })
  | (SchrittBasis & { art: "feld"; feld: string; label: string; alt: string; neu: string })
  | (SchrittBasis & { art: "hinweis"; titel: string; text: string });

export type PatientKurz = { id: number; nummer: number; name: string; geburtsdatum: string; geschlecht: string };

export type Datenpflege = {
  id: number; art: "datenpflege"; patient: PatientKurz; erstellt_am: string; verfahren: string; status: string;
  schritte: Schritt[];
  bestand: {
    felder: Record<"telefon" | "telefon2" | "email" | "hausarzt" | "ueberweisung_durch", string>;
    bezugspersonen: { id: number; name: string; beziehung: string; telefon: string; mobil: string }[];
    aerzte: { id: number; rolle: string; rolle_name: string; name: string; ort: string; telefon: string }[];
    hinweise: { titel: string; inhalt: string }[];
  };
};

export type PlanEntwurf = {
  id: number; art: "infusionsplan"; patient: PatientKurz; gueltig_ab: string; erstellt_am: string;
  erstellt_von: string | null; vorgaenger: { id: number; gueltig_ab: string } | null; anzahl_geaendert: number;
  zeilen: { schluessel: string; wert: string; vorher: string | null; jetzt: string | null; geaendert: boolean }[];
};

export type LaufendeFreigabe = {
  id: number; art: "datenpflege" | "infusionsplan"; objekt_id: number; status: "wartet" | "umgesetzt" | "zurueck" | "fehler";
  status_name: string; titel: string; patient_id: number; freigegeben_am: string; umsetzen_ab: string; sekunden: number;
  fehler: string; von: string;
};

export type FreigabenDaten = {
  rueckgaengig_s: number;
  datenpflege: Datenpflege[]; datenpflege_gesamt?: number; plaene: PlanEntwurf[]; ki_zur_pruefung: number;
  laufend: LaufendeFreigabe[];
  darf: { datenpflege: boolean; plaene: boolean; ki: boolean; aerzte_anlegen: boolean };
};

/** Zahl offener Freigaben für das Menü (einmal je Minute; setzt nebenbei fällige Freigaben um) */
export function useFreigabenOffen(): number {
  const { darf } = useAuth();
  const q = useQuery({
    queryKey: ["freigaben", "zaehler"],
    queryFn: () => api<{ offen: number }>("freigaben/zaehler/", { hintergrund: true }),
    enabled: darf("akten_bearbeiten") || darf("plaene_freigeben"),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
  return q.data?.offen ?? 0;
}
