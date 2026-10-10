/**
 * „Scan erkennt den Patienten“ (F183): Vorschlag oben in der Scan-Ansicht und beim Zuordnen.
 *
 * Der Server liest Name und Geburtsdatum aus dem Text und vergleicht sie mit den Akten, die die Person sehen darf
 * (Name auch bei Lesefehlern, Geburtsdatum exakt). Zugeordnet wird nie automatisch: Ein Klick auf „Übernehmen“ wählt
 * die Akte, in die Akte gelegt wird erst mit „In die Akte legen“. Unsichere Treffer erscheinen nur als Hinweis.
 */
import type { ScanVorschlag } from "@/lib/typen";
import { datum } from "@/lib/format";
import { Knopf, Meldung } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";

export function vorschlagName(v: ScanVorschlag): string {
  if (v.vorname !== undefined && v.nachname !== undefined) return `${v.vorname} ${v.nachname}`.trim();
  const [nach, ...vor] = v.name.split(", ");
  return `${vor.join(", ")} ${nach}`.trim();
}

function geb(v: ScanVorschlag): string {
  return v.geburtsdatum ? `, geb. ${datum(v.geburtsdatum)}` : "";
}

export function PatientVorschlag({ vorschlaege, onWahl, knopf = "Übernehmen" }: {
  vorschlaege: ScanVorschlag[]; onWahl: (v: ScanVorschlag) => void; knopf?: string;
}) {
  const offen = vorschlaege.filter((v) => !v.abgeschlossen);
  const starke = offen.filter((v) => (v.stufe ?? "wahrscheinlich") !== "unsicher");
  const unsichere = offen.filter((v) => v.stufe === "unsicher");
  const sichere = starke.filter((v) => v.stufe === "sicher");
  const einer = sichere.length === 1 ? sichere[0] : starke.length === 1 ? starke[0] : null;
  const weitere = einer ? starke.filter((v) => v.id !== einer.id) : starke;
  if (!starke.length && !unsichere.length) return null;
  return (
    <div className="flex flex-col gap-2" data-testid="patient-vorschlag">
      {einer ? (
        <Meldung art="ok">
          <span className="flex items-center gap-x-3 gap-y-1.5 flex-wrap">
            <Icon name="patienten" />
            <span className="grow min-w-0">
              Wahrscheinlich: <strong className="font-semibold">{vorschlagName(einer)}</strong>{geb(einer)}
              {einer.ist_test ? " (Test)" : ""} – übernehmen?
              <span className="block text-[0.8125rem] gedaempft">{einer.grund}</span>
            </span>
            <Knopf klein variante="pri" icon="haken" onClick={() => onWahl(einer)} data-testid="patient-vorschlag-uebernehmen">{knopf}</Knopf>
          </span>
        </Meldung>
      ) : null}
      {weitere.length ? (
        <div className="flex flex-col gap-1.5" data-testid="patient-vorschlaege">
          <span className="text-[0.8125rem] gedaempft">{einer ? "Weitere passende Akten:" : "Mehrere Akten passen – bitte wählen:"}</span>
          <div className="flex flex-wrap gap-2">
            {weitere.map((v) => (
              <button key={v.id} type="button" className="btn sec klein" title={`erkannt an: ${v.grund}`} onClick={() => onWahl(v)}>
                <Icon name="patienten" groesse={14} />{vorschlagName(v)}{geb(v)} <span className="gedaempft">({v.grund})</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {unsichere.length && !starke.length ? (
        <span className="text-[0.8125rem] gedaempft" data-testid="patient-hinweis">
          Hinweis: Vielleicht {unsichere.map((v) => `${vorschlagName(v)}${geb(v)} (${v.grund})`).join(" oder ")} – bitte den
          Patienten selbst suchen und prüfen.
        </span>
      ) : null}
    </div>
  );
}
