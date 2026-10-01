/** Entwurf 10 · Verlauf: jede Fassung aller Einträge der Akte, unveränderlich, gefiltert nach Bereich und Person. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import { usePraeparate, useVersorgerListe } from "@/lib/daten";
import { datum, uhrzeit } from "@/lib/format";
import { ABSCHLUSSANLAESSE, GESCHLECHTER, GEWICHTSQUELLEN, TERMINARTEN, ppiName, ppiZeiten } from "@/lib/typen";
import type { Auswahlwert, Verlaufseintrag } from "@/lib/typen";
import { Auswahl, Chip, Fehleranzeige, Karte, Knopf, Laden, Leer, Segmente } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { klartext } from "@/components/Editor";
import { useAkte } from "./Akte";

const BEREICHE: { wert: string; text: string }[] = [
  { wert: "", text: "Alle" }, { wert: "stammdaten", text: "Stammdaten" }, { wert: "diagnose", text: "Diagnose" },
  { wert: "therapie", text: "Therapie" }, { wert: "empfehlung", text: "Empfehlung" }, { wert: "kontakte", text: "Kontakte" },
  { wert: "gewichte", text: "Gewicht" }, { wert: "termine", text: "Termine" }, { wert: "infusionsplaene", text: "Infusionspläne" },
  { wert: "dokumente", text: "Dokumente" },
];
const BEREICH_EINZELN: Record<string, string> = {
  stammdaten: "Stammdaten", diagnose: "Diagnose", therapie: "Therapie", empfehlung: "Empfehlung", kontakte: "Kontakt",
  gewichte: "Gewicht", termine: "Termin", infusionsplaene: "Infusionsplan", dokumente: "Dokument",
};

const FELDER: Record<string, string> = {
  nachname: "Nachname", vorname: "Vorname", geburtsdatum: "Geburtsdatum", geschlecht: "Geschlecht", strasse: "Straße", plz: "PLZ",
  ort: "Ort", telefon: "Telefon", telefon2: "Telefon 2", email: "E-Mail", krankenkasse: "Krankenkasse", hausarzt: "Hausarzt",
  ueberweisung_durch: "Überweisung durch", groesse_cm: "Größe (cm)", katheter: "Katheter", versorger: "Versorger",
  ansprechpartner: "Ansprechpartner", nickelallergie: "Nickelallergie", diagnose: "Diagnose", therapie: "Therapie",
  empfehlung: "Empfehlung", bemerkung: "Bemerkung", abgeschlossen_am: "Abgeschlossen am", abschluss_anlass: "Anlass",
  abschluss_notiz: "Notiz zum Abschluss", gewicht_kg: "Gewicht (kg)", gemessen_am: "gemessen am", datum_ungenau: "Datum ungefähr",
  quelle: "Quelle", notiz: "Notiz", text: "Text", zeitpunkt: "Zeitpunkt", storniert_am: "Storniert am", storno_grund: "Grund",
  art: "Art", faellig_am: "fällig am", uhrzeit: "Uhrzeit", titel: "Titel", bei: "bei", erledigt_am: "Erledigt am",
  typ: "Typ", datum: "Datum", ausgeblendet: "Ausgeblendet", typ_geprueft: "Typ geprüft", datum_quelle: "Datumsquelle",
  status: "Status", gueltig_ab: "gültig ab", basis_praeparat: "Basislösung", basis_ml: "Basislösung (ml)",
  glucose_praeparat: "Glucose-Präparat", glucose_g: "Glucose (g)", aminosaeuren_praeparat: "Aminosäuren-Präparat",
  aminosaeuren_g: "Aminosäuren (g)", lipide_praeparat: "Lipid-Präparat", lipide_g: "Lipide (g)", albumin_praeparat: "Albumin-Präparat",
  albumin_g: "Albumin (g)", natrium_mmol: "Natrium", kalium_mmol: "Kalium", phosphat_mmol: "Phosphat", calcium_mmol: "Calcium",
  magnesium_mmol: "Magnesium", spurenelemente: "Spurenelemente", katheterschutz: "Katheterblock", laufzeit_h: "Laufzeit (h)",
  tage_pro_woche: "Tage pro Woche", pantozol_stufe: "Protonenpumpenhemmer", pantozol_tage: "PPI-Zeiten", kcal_manuell: "Energie (manuell)",
  gesamtvolumen_ml: "Gesamtvolumen (ml)", volumen_gewicht_kg: "Gewicht für das Gesamtvolumen (kg)",
};
/** technische Felder, die sich bei jeder Aktion mitändern */
const VERBORGEN = new Set(["geaendert_am", "erfasst_am", "angelegt_am", "hochgeladen_am", "freigegeben_am", "freigegeben_von",
  "erledigt_von", "storniert_von", "angelegt_von", "erfasst_von", "hochgeladen_von", "erstellt_von", "erstellt_am", "id"]);
const TEXTFELDER = new Set(["diagnose", "therapie", "empfehlung", "bemerkung", "text"]);

function useWertAnzeige() {
  const versorger = useVersorgerListe();
  const praeparate = usePraeparate();
  const auswahl = useQuery({ queryKey: ["auswahlwerte", "alle"], queryFn: () => api<Auswahlwert[]>("auswahlwerte/"), staleTime: 5 * 60_000 });
  return (feld: string, wert: string) => {
    if (wert === "" || wert === "None") return "—";
    if (TEXTFELDER.has(feld)) return klartext(wert) || "—";
    if (feld === "versorger") return versorger.data?.find((v) => String(v.id) === wert)?.name ?? wert;
    if (feld === "ansprechpartner") return versorger.data?.flatMap((v) => v.ansprechpartner).find((a) => String(a.id) === wert)?.name ?? wert;
    if (["katheter", "ort", "typ"].includes(feld) || (feld === "art" && /^\d+$/.test(wert))) return auswahl.data?.find((a) => String(a.id) === wert)?.wert ?? wert;
    if (feld.endsWith("_praeparat") || feld === "spurenelemente" || feld === "katheterschutz") return praeparate.data?.find((p) => String(p.id) === wert)?.anzeige ?? wert;
    if (feld === "geschlecht") return GESCHLECHTER[wert] ?? wert;
    if (feld === "quelle") return GEWICHTSQUELLEN[wert] ?? wert;
    if (feld === "abschluss_anlass") return ABSCHLUSSANLAESSE[wert] ?? wert;
    if (feld === "art") return TERMINARTEN[wert] ?? wert;
    if (feld === "pantozol_stufe") return ppiName(wert);
    if (feld === "pantozol_tage") return ppiZeiten(wert) || wert;
    if (wert === "True") return "ja";
    if (wert === "False") return "nein";
    if (/^\d{4}-\d{2}-\d{2}$/.test(wert)) return datum(wert);
    if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}/.test(wert)) return `${datum(wert)}, ${uhrzeit(wert)}`;
    if (/^-?\d+\.\d+$/.test(wert)) return wert.replace(/\.?0+$/, "").replace(".", ",");
    return wert;
  };
}

export function Verlauf() {
  const { patient } = useAkte();
  const [bereich, setBereich] = useState("");
  const [person, setPerson] = useState("");
  const anzeige = useWertAnzeige();
  const eintraege = useQuery({
    queryKey: ["patient", patient.id, "verlauf", bereich, person],
    queryFn: () => api<(Verlaufseintrag & { beschreibung?: string })[]>(`patienten/${patient.id}/verlauf/${abfrage({ bereich, person })}`),
    placeholderData: (vorher: (Verlaufseintrag & { beschreibung?: string })[] | undefined) => vorher,
  });
  const alle = useQuery({
    queryKey: ["patient", patient.id, "verlauf", "", ""],
    queryFn: () => api<Verlaufseintrag[]>(`patienten/${patient.id}/verlauf/`),
  });
  const personen = new Map<number, string>();
  for (const e of alle.data ?? []) if (e.person_id && e.person) personen.set(e.person_id, e.person);
  const liste = eintraege.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Segmente label="Bereich" wert={bereich} onWahl={setBereich} werte={BEREICHE} />
        <div className="flex items-center gap-2.5">
          <Auswahl aria-label="Person" className="w-[220px]" value={person} onChange={(e) => setPerson(e.target.value)}>
            <option value="">Alle Personen</option>
            {[...personen.entries()].map(([id, n]) => <option key={id} value={id}>{n}</option>)}
          </Auswahl>
          <Knopf icon="dokument" disabled title="folgt mit der PDF-Erzeugung (F24)">Verlauf als PDF</Knopf>
        </div>
      </div>
      <Karte className="overflow-hidden">
        {eintraege.isLoading ? <Laden /> : (
          <table className="tabelle" data-testid="verlauf" aria-busy={eintraege.isFetching || undefined}>
            <thead><tr><th className="th w-[110px]">Zeitpunkt</th><th className="th">Person</th><th className="th">Bereich</th><th className="th">Aktion</th><th className="th">Details</th></tr></thead>
            <tbody>
              {liste.map((e, i) => {
                const aenderungen = e.aenderungen.filter((a) => !VERBORGEN.has(a.feld) && !(e.bereich !== "stammdaten" && TEXTFELDER.has(a.feld) && e.bereich === a.feld));
                const textAenderung = e.aenderungen.find((a) => TEXTFELDER.has(a.feld) && a.feld === e.bereich);
                return (
                  <tr key={`${e.bereich}-${e.objekt_id}-${i}`}>
                    <td className="td num align-top">{datum(e.zeitpunkt)}<br /><span className="text-[0.8125rem] gedaempft">{uhrzeit(e.zeitpunkt)}</span></td>
                    <td className="td align-top">{e.person ?? <span className="gedaempft">System</span>}</td>
                    <td className="td align-top">{BEREICH_EINZELN[e.bereich] ?? e.bereich}</td>
                    <td className="td align-top"><Chip art={e.aktion === "storniert" || e.aktion === "gelöscht" ? "fehler" : e.aktion === "freigegeben" ? "ok" : undefined}>{e.aktion}</Chip></td>
                    <td className="td align-top text-sm">
                      <div className="flex flex-col gap-1">
                        {e.beschreibung ? <span>{e.beschreibung}</span> : null}
                        {textAenderung ? (
                          <span className="flex flex-col gap-0.5">
                            <span className="gedaempft line-through line-clamp-2">{anzeige(textAenderung.feld, textAenderung.alt)}</span>
                            <span className="line-clamp-3">{anzeige(textAenderung.feld, textAenderung.neu)}</span>
                          </span>
                        ) : null}
                        {aenderungen.map((a) => (
                          <span key={a.feld}>
                            {FELDER[a.feld] ?? a.feld}: <span className="gedaempft line-through">{anzeige(a.feld, a.alt)}</span> <span aria-label="geändert in">→</span> <span>{anzeige(a.feld, a.neu)}</span>
                          </span>
                        ))}
                        {e.grund ? <span className="gedaempft">Grund: {e.grund}</span> : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {eintraege.data && !liste.length ? <Leer>Keine Einträge für diese Auswahl.</Leer> : null}
        <Fehleranzeige fehler={eintraege.error} />
      </Karte>
      <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
        <Icon name="schloss" />
        <span>Der Verlauf wird automatisch geschrieben und kann von niemandem geändert oder gelöscht werden, auch nicht von der
          Administration. Stornierte Einträge bleiben hier sichtbar.</span>
      </div>
    </div>
  );
}
