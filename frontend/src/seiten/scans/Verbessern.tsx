/**
 * Erkennung verbessern (F189): „Falsch erkannt“ mit Grund und der einblendbare Hinweis „So helfen Sie EPM, besser zu
 * lesen“ in der Prüfansicht beim Zuordnen.
 *
 * „Falsch erkannt“ wirkt sofort (die Zeile verschwindet) und fließt ins Lernen ein – nur die Bezeichnung, für dieses
 * Labor; der Server prüft, dass nichts zur Person gespeichert wird.
 */
import { useState } from "react";
import { Menu as BaseMenu } from "@base-ui/react/menu";
import { Knopf, Meldung, cx } from "@/components/ui/basis";
import { Begriff } from "@/components/ui/Begriff";
import { Icon } from "@/components/ui/icon";

export type Grund = "falsche_zeile" | "falscher_wert" | "gehoert_nicht_dazu";

const GRUENDE: { wert: Grund; text: string; hinweis: string }[] = [
  { wert: "falsche_zeile", text: "Falsche Zeile", hinweis: "Die Bezeichnung gehört zu einem anderen Wert" },
  { wert: "falscher_wert", text: "Falscher Wert", hinweis: "Die Zahl ist falsch gelesen" },
  { wert: "gehoert_nicht_dazu", text: "Gehört nicht dazu", hinweis: "Kopfzeile, Referenzbereich, Datum … – künftig weglassen" },
];

export const GRUND_TEXT: Record<Grund, string> = {
  falsche_zeile: "falsche Zeile", falscher_wert: "falscher Wert", gehoert_nicht_dazu: "gehört nicht dazu",
};

/** Deutlicher Knopf „Falsch erkannt“ mit kurzer Auswahl des Grunds */
export function FalschKnopf({ onGrund, name, klein = true }: { onGrund: (g: Grund) => void; name: string; klein?: boolean }) {
  return (
    <BaseMenu.Root>
      <BaseMenu.Trigger className={cx("btn geist", klein && "klein", "text-fehler whitespace-nowrap")}
        aria-label={`„${name}“ falsch erkannt`} title="Falsch erkannt – Grund wählen" data-testid="falsch-erkannt"
        onClick={(e) => e.stopPropagation()}>
        <Icon name="x" groesse={14} />Falsch erkannt
      </BaseMenu.Trigger>
      <BaseMenu.Portal>
        <BaseMenu.Positioner side="bottom" align="end" sideOffset={6} className="z-50">
          <BaseMenu.Popup className="card min-w-[15rem] p-1 flex flex-col outline-none" data-testid="falsch-gruende">
            {GRUENDE.map((g) => (
              <BaseMenu.Item key={g.wert} onClick={() => onGrund(g.wert)}
                className="flex flex-col items-start gap-0.5 rounded-md px-3 py-2 text-sm cursor-pointer outline-none data-[highlighted]:bg-fein">
                <span>{g.text}</span>
                <span className="text-xs gedaempft">{g.hinweis}</span>
              </BaseMenu.Item>
            ))}
          </BaseMenu.Popup>
        </BaseMenu.Positioner>
      </BaseMenu.Portal>
    </BaseMenu.Root>
  );
}

const SCHLUESSEL = "epm-scans-hinweis-verbessern";

function gelesen(): boolean {
  try {
    return localStorage.getItem(SCHLUESSEL) === "weg";
  } catch {
    return false;
  }
}

/** „So helfen Sie EPM, besser zu lesen“: einmal eingeblendet, wegklickbar, über „?“ wieder aufrufbar */
export function VerbessernHinweis() {
  const [offen, setOffen] = useState(() => !gelesen());
  const schliessen = () => {
    setOffen(false);
    try {
      localStorage.setItem(SCHLUESSEL, "weg");
    } catch { /* ohne Speicher erscheint der Hinweis eben wieder */ }
  };
  if (!offen) {
    return (
      <button type="button" className="btn geist klein self-start" onClick={() => setOffen(true)} data-testid="verbessern-hilfe"
        title="So helfen Sie EPM, besser zu lesen"><Icon name="hilfe" groesse={14} />Besser lesen helfen</button>
    );
  }
  return (
    <Meldung art="info">
      <div className="flex flex-col gap-1.5 text-sm" data-testid="verbessern-hinweis">
        <div className="flex items-start gap-2">
          <strong className="font-semibold grow">So helfen Sie EPM, besser zu lesen</strong>
          <button type="button" className="btn geist klein -mt-1" onClick={schliessen} aria-label="Hinweis schließen"
            data-testid="verbessern-hinweis-zu"><Icon name="x" /></button>
        </div>
        <ol className="m-0 pl-5 flex flex-col gap-1">
          <li>Vergleichen Sie jede Zeile mit dem Bild links. Ein Klick auf die Zeile zeigt die Stelle.</li>
          <li>Ist eine Zeile falsch, tippen Sie auf <strong>Falsch erkannt</strong> und wählen den Grund – zum Beispiel
            „Gehört nicht dazu“ bei einer Kopfzeile oder dem Referenzbereich.</li>
          <li>Fehlt ein Wert, tippen Sie auf <strong>Bereich markieren</strong> und ziehen mit Maus oder Finger einen Rahmen
            um die richtigen Zeilen im Bild. EPM liest nur diesen Teil noch einmal.</li>
          <li>Wählen Sie bei Bedarf den richtigen Laborwert aus der Liste und legen Sie alles in die Akte.</li>
        </ol>
        <span className="gedaempft">EPM merkt sich das für dieses Labor (<Begriff name="gelernt">gelernt</Begriff>) und
          liest den nächsten Befund besser. Gespeichert werden nur Bezeichnungen, keine Werte und keine Namen.</span>
      </div>
    </Meldung>
  );
}

/** Knopf „Bereich markieren“ (Rahmen im Bild aufziehen, nur diesen Teil neu lesen) */
export function BereichKnopf({ aktiv, laedt, onClick }: { aktiv: boolean; laedt?: boolean; onClick: () => void }) {
  return (
    <Knopf klein icon="rahmen" variante={aktiv ? "pri" : "sec"} aria-pressed={aktiv} laedt={laedt} onClick={onClick}
      data-testid="bereich-markieren" title="Rahmen um die richtigen Zeilen im Bild ziehen – EPM liest nur diesen Teil neu">
      {aktiv ? "Rahmen im Bild ziehen …" : "Bereich markieren"}
    </Knopf>
  );
}
