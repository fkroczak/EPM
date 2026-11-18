/**
 * Laborparameter in drei Sprachen (Dreisprachigkeit der RGC, 18.11.2026). Der Wert hängt am Parameter, nicht am Namen:
 * „Fosfors“ (lettisch) und „Phosphat“ sind derselbe Wert – angezeigt wird nur der Name in der gewählten Sprache.
 */
import { useCallback } from "react";
import { useLaborparameter } from "@/lib/daten";
import { useSprache } from "@/lib/sprache";
import type { Sprache } from "@/lib/sprache";
import { LABORGRUPPEN } from "@/lib/typen";
import type { Laborparameter, Laborwert } from "@/lib/typen";

/** Gruppennamen Englisch / Lettisch (Deutsch: LABORGRUPPEN) */
const GRUPPEN: Record<string, { en: string; lv: string }> = {
  transaminasen: { en: "Liver enzymes", lv: "Aknu fermenti" },
  niere: { en: "Kidney function", lv: "Nieru funkcija" },
  eisen: { en: "Iron metabolism", lv: "Dzelzs vielmaiņa" },
  eiweiss_fett: { en: "Protein and lipid metabolism", lv: "Olbaltumvielu un tauku vielmaiņa" },
  elektrolyte: { en: "Electrolytes", lv: "Elektrolīti" },
  spurenelemente: { en: "Trace elements", lv: "Mikroelementi" },
  haematologie: { en: "Haematology", lv: "Hematoloģija" },
  vitamine: { en: "Vitamins", lv: "Vitamīni" },
  knochen: { en: "Bone metabolism", lv: "Kaulu vielmaiņa" },
  pankreas: { en: "Pancreatic enzymes", lv: "Aizkuņģa dziedzera fermenti" },
  diabetes: { en: "Blood glucose / diabetes", lv: "Glikoze / diabēts" },
  schilddruese: { en: "Thyroid", lv: "Vairogdziedzeris" },
  tumormarker: { en: "Tumour markers", lv: "Audzēju marķieri" },
  genetik: { en: "Genetic parameters", lv: "Ģenētiskie parametri" },
  gerinnung: { en: "Coagulation", lv: "Koagulācija" },
  hormone: { en: "Hormones", lv: "Hormoni" },
  immunologie: { en: "Immunology and autoantibodies", lv: "Imunoloģija un autoantivielas" },
  allergologie: { en: "Allergology and mast cells", lv: "Alergoloģija un tuklās šūnas" },
  urin_stuhl: { en: "Urine and stool", lv: "Urīns un fēces" },
  sonstiges: { en: "Further parameters", lv: "Citi parametri" },
};

export function gruppenName(gruppe: string | null | undefined, sprache: Sprache): string {
  const g = gruppe ?? "sonstiges";
  if (sprache !== "de" && GRUPPEN[g]) return GRUPPEN[g][sprache];
  return LABORGRUPPEN[g] ?? LABORGRUPPEN.sonstiges;
}

export function parameterName(p: Pick<Laborparameter, "name" | "name_en" | "name_lv">, sprache: Sprache): string {
  if (sprache === "en" && p.name_en) return p.name_en;
  if (sprache === "lv" && p.name_lv) return p.name_lv;
  return p.name;
}

/** Namen von Parametern und Laborwerten in der gewählten Sprache; der deutsche Name steht im Tooltip */
export function useLaborNamen() {
  const sprache = useSprache();
  const katalog = useLaborparameter(false);
  const nachId = katalog.data ? new Map(katalog.data.map((p) => [p.id, p])) : null;
  const parameter = useCallback((p: Laborparameter) => parameterName(p, sprache), [sprache]);
  const wert = (w: Laborwert): string => {
    const p = w.parameter != null ? nachId?.get(w.parameter) : undefined;
    return p ? parameterName(p, sprache) : (w.bezeichnung ?? w.freitext_name);
  };
  const gruppe = useCallback((g: string | null | undefined) => gruppenName(g, sprache), [sprache]);
  return { sprache, parameter, wert, gruppe };
}

/** Beschriftungen rund ums Labor (Akte › Labor, Vorlagen › Laborparameter) */
const TEXTE: Record<string, { en: string; lv: string }> = {
  "Laborbefund": { en: "Lab report", lv: "Laboratorijas izmeklējums" },
  "Laborbefunde": { en: "Lab reports", lv: "Laboratorijas izmeklējumi" },
  "Neuer Laborbefund": { en: "New lab report", lv: "Jauns laboratorijas izmeklējums" },
  "Laborbefund ändern": { en: "Edit lab report", lv: "Labot laboratorijas izmeklējumu" },
  "Nur den gemessenen Wert eintragen – die Einheit steht schon da. Leere Zeilen werden nicht gespeichert.": {
    en: "Enter only the measured value – the unit is already filled in. Empty rows are not saved.",
    lv: "Ievadiet tikai izmērīto vērtību – mērvienība jau ir norādīta. Tukšās rindas netiek saglabātas.",
  },
  "Abnahme am": { en: "Sampled on", lv: "Paraugs ņemts" },
  "Labor": { en: "Laboratory", lv: "Laboratorija" },
  "z. B. Labor Dr. Wagner": { en: "e.g. Lab Dr. Wagner", lv: "piem., laboratorija Dr. Wagner" },
  "Parameter werden geladen …": { en: "Loading parameters …", lv: "Ielādē parametrus …" },
  "Weitere Parameter": { en: "Further parameters", lv: "Citi parametri" },
  "Parameter hinzufügen": { en: "Add parameter", lv: "Pievienot parametru" },
  "Zusammenfassung / Beurteilung": { en: "Summary / assessment", lv: "Kopsavilkums / novērtējums" },
  "Beurteilung": { en: "Assessment", lv: "Novērtējums" },
  "Abbrechen": { en: "Cancel", lv: "Atcelt" },
  "Speichern": { en: "Save", lv: "Saglabāt" },
  "Wert": { en: "value", lv: "vērtība" },
  "Werte": { en: "values", lv: "vērtības" },
  "Bearbeiten": { en: "Edit", lv: "Labot" },
  "Laborbefund vom": { en: "Lab report of", lv: "Laboratorijas izmeklējums no" },
  "über": { en: "above", lv: "virs" },
  "unter": { en: "below", lv: "zem" },
  "Referenz": { en: "reference", lv: "references" },
  "Labor nicht angegeben": { en: "Laboratory not specified", lv: "Laboratorija nav norādīta" },
  "Noch kein Laborbefund erfasst.": { en: "No lab report recorded yet.", lv: "Vēl nav reģistrēts neviens izmeklējums." },
  "Links einen Befund wählen.": { en: "Select a report on the left.", lv: "Izvēlieties izmeklējumu kreisajā pusē." },
  "Laborbefund gespeichert.": { en: "Lab report saved.", lv: "Izmeklējums saglabāts." },
  "Laborbefund geändert.": { en: "Lab report changed.", lv: "Izmeklējums labots." },
  "Bitte als TT.MM.JJJJ eingeben.": { en: "Please enter as DD.MM.YYYY.", lv: "Lūdzu, ievadiet formātā DD.MM.GGGG." },
};

/** ``const lt = useLaborText(); lt("Neuer Laborbefund")`` */
export function useLaborText(): (text: string) => string {
  const sprache = useSprache();
  return useCallback((text: string) => (sprache === "de" ? text : TEXTE[text]?.[sprache] ?? text), [sprache]);
}
