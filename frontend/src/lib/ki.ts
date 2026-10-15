/** KI (Experimentell, 14.10.2026): Datenformen der API ``/api/ki/…`` und Bezeichnungen für die Oberfläche. */
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import { useAuth } from "./auth";

export type KiStatus = "neu" | "in_verarbeitung" | "ocr_fertig" | "analyse_fertig" | "zur_pruefung" | "teilweise"
  | "uebernommen" | "abgelehnt" | "fehler" | "nachverarbeitung";

export const STATUS_TEXT: Record<KiStatus, string> = {
  neu: "Neu", in_verarbeitung: "In Verarbeitung", ocr_fertig: "OCR abgeschlossen", analyse_fertig: "Analyse abgeschlossen",
  zur_pruefung: "Zur Prüfung vorgelegt", teilweise: "Teilweise freigegeben", uebernommen: "Freigegeben und übernommen",
  abgelehnt: "Abgelehnt", fehler: "Fehler", nachverarbeitung: "Zur Nachverarbeitung markiert",
};

export const STATUS_ART: Partial<Record<KiStatus, "warn" | "fehler" | "ok" | "akzent" | "neutral">> = {
  zur_pruefung: "akzent", teilweise: "warn", uebernommen: "ok", abgelehnt: "neutral", fehler: "fehler",
  nachverarbeitung: "warn",
};

export const DOKUMENTTYPEN: Record<string, string> = {
  labor: "Laborbefund", arztbericht: "Arztbericht", entlassbericht: "Entlassbericht", verlauf: "Verlaufsdokumentation",
  infusionsplan: "Infusionsplan", medikationsplan: "Medikationsplan", pflegebericht: "Pflegebericht", sonstiges: "Sonstiges",
};

export type KiVorgangKurz = {
  id: number; status: KiStatus; status_name: string; dokument: number; dokument_titel: string; dokument_datum: string | null;
  patient: number; patient_name: string; patient_nummer: number; firma: number | null; firma_name: string;
  dokumenttyp: string; dokumenttyp_name: string; typ_konfidenz: number | null; ocr_konfidenz: number | null; seiten: number;
  schritt: string; fortschritt: number; fehler: string; prioritaet: number; erstellt_am: string; fertig_am: string | null;
  felder_offen: number; felder_unsicher: number; metadaten: Record<string, unknown>;
};

export type KiFeldGruppe = "meta" | "labor" | "infusion" | "medikation" | "diagnose" | "text";
export type KiEntscheidung = "" | "neu" | "ergaenzen" | "ersetzen" | "verwerfen";

export type KiFeld = {
  id: number; gruppe: KiFeldGruppe; gruppe_name: string; schluessel: string; nr: number;
  wert: Record<string, unknown>; korrigiert: Record<string, unknown> | null; endwert: Record<string, unknown>;
  konfidenz: number | null; unsicher: boolean; quelle: string;
  belege: { seite?: number; zeile?: string; gelesen?: string; im_ocr_text?: boolean; hinweise?: string[] };
  status: "offen" | "freigegeben" | "verworfen" | "uebernommen"; status_name: string; entscheidung: KiEntscheidung;
  ziel: { modell?: string; id?: number }; korrekturen: number; geaendert_am: string; geaendert_von_name: string;
};

export type KiVorschau = {
  feld: number; gruppe: KiFeldGruppe; schluessel: string;
  aktion: "neu" | "ergaenzen" | "ueberschreiben" | "identisch" | "konflikt" | "nur_info";
  bestehend: Record<string, unknown> | null; optionen: KiEntscheidung[]; fehler: string; unsicher: boolean;
  konfidenz: number | null; entscheidung: KiEntscheidung;
};

export type KiVorgang = KiVorgangKurz & {
  felder: KiFeld[];
  seiten_liste: { nr: number; text: string; vision_text: string; konfidenz: number | null; verfahren: string[]; dauer_s: number | null }[];
  dokument_mime: string; zusammenfassung: string; ocr_text: string; verfahren: string[];
  modell: { name: string; sha256: string; id: number } | null; prompt_version: string; dauer_s: number | null;
  geprueft_von_name: string; geprueft_am: string | null; ablehnungsgrund: string; angefordert_von_name: string;
  angefordert_am: string | null; uebernahmen: { zeitpunkt: string; benutzer: string; ziele: unknown[]; felder: number }[];
  vorschau: KiVorschau[]; rechte: { ki_pruefen: boolean; ki_uebernehmen: boolean };
};

export type KiHinweis = {
  id: number; patient: number; art: string; art_name: string; stufe: "gesichert" | "wahrscheinlich"; stufe_name: string;
  parameter: string; text: string; zeitpunkt: string; status: "neu" | "gesehen" | "ausgeblendet"; aktualisiert_am: string;
  belege: { labor?: Beleg[]; plan?: Beleg[]; folge?: Beleg[]; wiederholungen?: Beleg[] };
};
export type Beleg = { quelle: "akte" | "ki"; id: number; wert?: string | null; einheit?: string; zeit: string; menge?: string | null;
  vorher?: string | null; feld?: string; lage?: string; gueltig_ab?: string };

export type KiBericht = {
  id: number; patient: number; art: "labor" | "infusion" | "verlauf"; art_name: string; von: string | null; bis: string | null;
  dokumenttypen: string[]; status: "wartet" | "laeuft" | "fertig" | "fehler" | "gespeichert" | "verworfen"; status_name: string;
  angefordert_von_name: string; angefordert_am: string; fakten: { nr: number; text: string; quelle: { modell: string; id: number } }[];
  entwurf: string; fehler: string; modell: string | null; fertig_am: string | null; bericht: number | null; kennzeichnung: string;
  pruefung: { ok?: boolean; unbelegte_werte?: string[]; unbekannte_belege?: number[]; saetze_ohne_beleg?: string[];
    empfehlung_oder_bewertung?: string[]; bearbeitet?: boolean };
};

export type KiStand = {
  aktiv: boolean;
  nachtfenster: { beginn: string; ende: string; zeitzone: string; jetzt: boolean };
  dienst: null | {
    laeuft: boolean; alter_s: number | null; bearbeitet: number; laufend: number[]; pp_ocr: boolean;
    entscheidung: { modus: string; parallel: number; nur_angefordert: boolean; sparsam: boolean; grund: string;
      last: { cpu_prozent: number | null; ram_frei_mb: number | null; ram_gesamt_mb: number | null; last1: number | null; kerne: number } };
    modell: { eingerichtet: boolean; bereit: boolean; adresse: string };
  };
  queue?: { je_status: Partial<Record<KiStatus, number>>; noch_nicht_vorgemerkt: number; gesamt: number };
  modell?: { id: number; name: string } | null;
};

/** Anzahl zur Prüfung (Menüpunkt). Ohne Recht keine Abfrage. */
export function useKiZurPruefung(): number {
  const { darf } = useAuth();
  const q = useQuery({
    queryKey: ["ki", "zaehler"],
    queryFn: () => api<{ zur_pruefung: number }>("ki/vorgaenge/zaehler/"),
    enabled: darf("ki_ansehen"),
    staleTime: 60_000,
  });
  return q.data?.zur_pruefung ?? 0;
}

export function prozentText(wert: number | null | undefined): string {
  return wert === null || wert === undefined ? "—" : `${Math.round(wert * 100)} %`;
}

export const MODUS_TEXT: Record<string, string> = {
  nacht: "Nachtverarbeitung", tag: "Tagbetrieb (nur auf Anforderung)", pause: "Pause", aus: "Aus",
};

export const AKTION_TEXT: Record<KiVorschau["aktion"], string> = {
  neu: "neu", ergaenzen: "ergänzt Vorhandenes", ueberschreiben: "würde überschreiben", identisch: "schon vorhanden",
  konflikt: "Konflikt", nur_info: "nur Information",
};

export const ENTSCHEIDUNG_TEXT: Record<Exclude<KiEntscheidung, "">, string> = {
  neu: "Neu anlegen", ergaenzen: "Bestehenden Eintrag ergänzen", ersetzen: "Bestehenden Eintrag ersetzen", verwerfen: "Verwerfen",
};

export const FEHLERARTEN: Record<string, string> = {
  lesefehler: "Zeichen falsch gelesen (OCR)", zuordnung: "falscher Parameter / falsche Zuordnung", einheit: "Einheit falsch",
  datum: "Datum/Uhrzeit falsch", typ: "Dokumenttyp falsch", fehlt: "Wert fehlte", ueberfluessig: "kein Wert (gehört nicht dazu)",
  sonstiges: "sonstiges",
};

/** Bezeichnung und Wert eines Felds in einer Zeile (für Liste und Übernahme-Zusammenfassung). */
export function feldText(f: { gruppe: KiFeldGruppe; schluessel: string; endwert: Record<string, unknown> }): { titel: string; wert: string } {
  const w = f.endwert as Record<string, string | null | undefined | boolean>;
  const s = (x: unknown) => (x === null || x === undefined || x === "" ? "" : String(x));
  switch (f.gruppe) {
    case "labor":
      return { titel: s(w.parameter_name) || s(w.erkannt_als) || "Laborwert",
        wert: [s(w.wert)?.replace(".", ",") || s(w.wert_text), s(w.einheit), w.markierung ? `${w.markierung}` : "",
          w.referenz_von || w.referenz_bis ? `(Ref. ${s(w.referenz_von).replace(".", ",")}–${s(w.referenz_bis).replace(".", ",")})` : "",
          w.datum ? `· ${s(w.datum).split("-").reverse().join(".")}${w.uhrzeit ? ` ${w.uhrzeit}` : ""}` : ""].filter(Boolean).join(" ") };
    case "infusion":
      return { titel: s(w.substanz) || "Infusion",
        wert: [s(w.menge).replace(".", ","), s(w.einheit), s(w.applikation), s(w.haeufigkeit),
          w.von ? `ab ${s(w.von).split("-").reverse().join(".")}${w.uhrzeit ? ` ${w.uhrzeit}` : ""}` : "",
          w.planfeld ? `→ Planfeld ${w.planfeld}` : "→ Position (Bemerkung)"].filter(Boolean).join(" ") };
    case "medikation":
      return { titel: s(w.wirkstoff) || "Medikament", wert: [s(w.staerke), s(w.dosierung), s(w.grund)].filter(Boolean).join(" · ") };
    case "diagnose":
      return { titel: s(w.bezeichnung) || "Diagnose", wert: s(w.icd_code) };
    case "text":
      return { titel: { zusammenfassung: "Zusammenfassung", verlauf: "Verlauf", offene_punkte: "Offene Punkte" }[f.schluessel] ?? "Text",
        wert: s(w.text) };
    default: {
      const titel = { dokumenttyp: "Dokumenttyp", dokumentdatum: "Dokumentdatum", erstellungsdatum: "Erstellungsdatum", absender: "Absender",
        fall: "Fall / Aufenthalt", sprache: "Sprache", vertraulich: "Vertraulich", patient: "Patient im Dokument",
        ocr_konfidenz: "OCR-Sicherheit" }[f.schluessel] ?? f.schluessel;
      if (f.schluessel === "dokumenttyp") return { titel, wert: DOKUMENTTYPEN[s(w.wert)] ?? s(w.wert) };
      if (f.schluessel === "patient") return { titel, wert: `${s(w.name)}${w.geburtsdatum ? `, geb. ${s(w.geburtsdatum).split("-").reverse().join(".")}` : ""} – ${w.passt ? "passt zur Akte" : "passt NICHT zur Akte"}` };
      if (f.schluessel === "ocr_konfidenz") return { titel, wert: `${prozentText(w.wert as unknown as number)} (niedrigste Seite)` };
      if (f.schluessel.endsWith("datum")) return { titel, wert: s(w.wert).split("-").reverse().join(".") };
      return { titel, wert: typeof w.wert === "boolean" ? (w.wert ? "ja" : "nein") : s(w.wert) };
    }
  }
}

/** Welche Angaben ein Feld je Gruppe hat (Bearbeiten-Dialog) */
export const FELD_ANGABEN: Record<KiFeldGruppe, { name: string; text: string; breit?: boolean; auswahl?: Record<string, string> }[]> = {
  labor: [{ name: "parameter_name", text: "Parameter" }, { name: "wert", text: "Wert (Zahl)" }, { name: "wert_text", text: "Wert als Text" },
    { name: "einheit", text: "Einheit" }, { name: "referenz_von", text: "Referenz von" }, { name: "referenz_bis", text: "Referenz bis" },
    { name: "datum", text: "Datum (JJJJ-MM-TT)" }, { name: "uhrzeit", text: "Uhrzeit (HH:MM)" }],
  infusion: [{ name: "substanz", text: "Substanz" }, { name: "menge", text: "Menge" }, { name: "einheit", text: "Einheit" },
    { name: "von", text: "gültig ab (JJJJ-MM-TT)" }, { name: "bis", text: "bis" }, { name: "uhrzeit", text: "Uhrzeit" },
    { name: "applikation", text: "Applikation" }, { name: "haeufigkeit", text: "Häufigkeit" },
    { name: "planfeld", text: "Feld im Infusionsplan", auswahl: { "": "– als Position (Bemerkung) –", kalium_mmol: "Kalium (mmol)",
      natrium_mmol: "Natrium (mmol)", phosphat_mmol: "Phosphat (mmol)", calcium_mmol: "Calcium (mmol)", magnesium_mmol: "Magnesium (mmol)",
      glucose_g: "Glucose (g)", aminosaeuren_g: "Aminosäuren (g)", lipide_g: "Lipide (g)", albumin_ml: "Humanalbumin (ml)" } },
    { name: "kontext", text: "Zusammenhang", breit: true }],
  medikation: [{ name: "wirkstoff", text: "Wirkstoff" }, { name: "handelsname", text: "Handelsname" }, { name: "staerke", text: "Stärke" },
    { name: "dosierung", text: "Dosierung" }, { name: "seit", text: "seit (JJJJ-MM-TT)" }, { name: "grund", text: "Grund" }],
  diagnose: [{ name: "bezeichnung", text: "Bezeichnung", breit: true }, { name: "icd_code", text: "ICD-10" }],
  text: [{ name: "aktenabschnitt", text: "Abschnitt der Akte", auswahl: { "": "– bitte wählen –", diagnose: "Diagnose", therapie: "Therapie",
    empfehlung: "Empfehlung" } }, { name: "text", text: "Text", breit: true }],
  meta: [{ name: "wert", text: "Wert", breit: true }],
};
