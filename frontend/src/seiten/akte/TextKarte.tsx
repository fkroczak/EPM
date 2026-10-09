/**
 * Die Freitextfelder der Akte (Diagnose-Notizen, Therapie, Empfehlung) im Muster der übrigen Reiter (F122).
 *
 * Links die Fassungen mit Datum, rechts der Text: Die aktuelle Fassung ist bearbeitbar, ältere sind nur lesbar.
 * Jede gespeicherte Fassung bleibt mit Person, Datum und Uhrzeit erhalten; gelöscht wird nichts.
 *
 * ``Textkopf`` ist der Einzeleintrag für Reiter, die den Text neben anderen Einträgen führen (Diagnosen ›
 * Notizen); ``TextfassungsListe`` ist die ganze Spalte für Reiter, die nur aus einem Text bestehen.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { datum, uhrzeit, zeitpunkt } from "@/lib/format";
import type { Patient } from "@/lib/typen";
import { Fehleranzeige, Knopf, Laden } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { Editor, Richtext } from "@/components/Editor";
import { useAkte } from "./Akte";
import { Detail, Eintrag } from "./Aktenseite";

export type Textfeld = "diagnose" | "therapie" | "empfehlung" | "bemerkung";
type Fassung = { version: number; zeitpunkt: string; person: string | null; text: string };
type Fassungen = { feld: Textfeld; version: number; fassungen: Fassung[] };

export const TITEL: Record<Textfeld, string> = {
  diagnose: "Notizen", therapie: "Therapie", empfehlung: "Empfehlung", bemerkung: "Bemerkung",
};

export function useFassungen(feld: Textfeld, an = true) {
  const { patient } = useAkte();
  return useQuery({
    queryKey: ["patient", patient.id, "versionen", feld],
    queryFn: () => api<Fassungen>(`patienten/${patient.id}/versionen/?feld=${feld}`),
    enabled: an,
  });
}

/** Ein Eintrag in der Liste links für einen Text, der neben anderen Einträgen steht (Diagnosen › Notizen). */
export function Textkopf({ feld, titel, aktiv, onWahl }: {
  feld: Textfeld; titel?: string; aktiv: boolean; onWahl: () => void;
}) {
  const { patient } = useAkte();
  const v = patient.kopf?.versionen[feld];
  return (
    <Eintrag aktiv={aktiv} onWahl={onWahl}
      datum={v ? datum(v.zeitpunkt) : "—"}
      merkmal={v ? <span className="text-xs gedaempft">Version {v.version}</span> : null}
      zeile={titel ?? TITEL[feld]}
      unten={v ? (v.person ?? "") : "noch nicht bearbeitet"} />
  );
}

/** Die ganze linke Spalte für einen Reiter, der nur aus einem Text besteht (Therapie, Empfehlung). */
export function TextfassungsListe({ feld, gewaehlt, onWahl }: {
  feld: Textfeld; gewaehlt: number | null; onWahl: (version: number) => void;
}) {
  const daten = useFassungen(feld);
  const liste = daten.data?.fassungen ?? [];
  if (daten.isPending) return <Laden />;
  if (!liste.length) {
    return <Eintrag aktiv onWahl={() => undefined} datum="—" zeile={TITEL[feld]} unten="noch nicht bearbeitet" />;
  }
  const aktuell = liste[0].version;
  return (
    <>
      {liste.map((f) => (
        <Eintrag key={f.version} aktiv={(gewaehlt ?? aktuell) === f.version} onWahl={() => onWahl(f.version)}
          datum={datum(f.zeitpunkt)}
          merkmal={f.version === aktuell ? <span className="text-xs gedaempft">aktuell</span> : null}
          zeile={`Version ${f.version}`}
          unten={`${uhrzeit(f.zeitpunkt)} Uhr · ${f.person ?? "—"}`} />
      ))}
    </>
  );
}

/**
 * Der Text rechts. Ohne ``version`` (oder mit der aktuellen) ist er bearbeitbar, sonst nur lesbar.
 * ``immerOffen`` öffnet den Editor sofort – für Reiter, auf denen hauptsächlich geschrieben wird.
 */
export function Textfassung({ feld, titel, hinweis, version, immerOffen, vorAktionen }: {
  feld: Textfeld; titel?: string; hinweis?: string; version?: number | null; immerOffen?: boolean;
  /** weitere Knöpfe vor „Bearbeiten“ (z. B. „Frühere Fassungen“) */
  vorAktionen?: ReactNode;
}) {
  const { patient, bearbeiten } = useAkte();
  const name = titel ?? TITEL[feld];
  const gespeichert = patient[feld];
  const kopf = patient.kopf?.versionen[feld];
  const aktuell = version == null || version === kopf?.version;
  const fassungen = useFassungen(feld, !aktuell);
  const alt = aktuell ? null : fassungen.data?.fassungen.find((f) => f.version === version) ?? null;

  const [entwurf, setEntwurf] = useState(gespeichert);
  const [offen, setOffen] = useState(false);
  const qc = useQueryClient();
  const melden = useHinweis();
  const editor = aktuell && bearbeiten && (immerOffen || offen);
  // Neue Fassung vom Server übernehmen, aber keine laufende Eingabe überschreiben
  const vorher = useRef(gespeichert);
  useEffect(() => {
    if (gespeichert !== vorher.current) {
      const vorige = vorher.current;
      setEntwurf((e) => (e === vorige ? gespeichert : e));
      vorher.current = gespeichert;
    }
  }, [gespeichert]);

  const speichern = useMutation({
    mutationFn: () => api<Patient>(`patienten/${patient.id}/`, { method: "PATCH", body: { [feld]: entwurf } }),
    onSuccess: (p) => {
      qc.setQueryData(["patient", patient.id], p);
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      setEntwurf(p[feld]);
      setOffen(false);
      melden(`${name} gespeichert.`);
    },
  });
  const geaendert = entwurf !== gespeichert;

  return (
    <Detail testid={`karte-${feld}`}
      titel={aktuell ? name : `${name} · Version ${version}`}
      unter={aktuell
        ? (kopf
          ? `Version ${kopf.version} · geändert ${zeitpunkt(kopf.zeitpunkt)}${kopf.person ? ` von ${kopf.person}` : ""}`
          : (hinweis ?? "Noch nicht bearbeitet"))
        : alt ? `gespeichert ${zeitpunkt(alt.zeitpunkt)}${alt.person ? ` von ${alt.person}` : ""} · nur lesbar` : "nur lesbar"}
      aktionen={<>
        {vorAktionen}
        {aktuell && bearbeiten && !immerOffen && !offen
          ? <Knopf klein variante="pri" icon="stift" onClick={() => { setEntwurf(gespeichert); setOffen(true); }}>Bearbeiten</Knopf>
          : null}
      </>}>
      {!aktuell ? (
        fassungen.isPending ? <Laden /> : <div data-testid="fassung"><Richtext html={alt?.text ?? ""} leer="(leer)" /></div>
      ) : editor ? (
        <>
          <Editor wert={entwurf} onAenderung={setEntwurf} label={name} hoehe={immerOffen ? 420 : 220} autofokus={!immerOffen} />
          <Fehleranzeige fehler={speichern.error} />
          <div className="flex justify-end gap-2">
            <Knopf disabled={!geaendert && immerOffen} onClick={() => { setEntwurf(gespeichert); setOffen(false); speichern.reset(); }}>Abbrechen</Knopf>
            <Knopf variante="pri" laedt={speichern.isPending} disabled={!geaendert} onClick={() => speichern.mutate()}>Speichern</Knopf>
          </div>
        </>
      ) : <Richtext html={gespeichert} leer={`Noch keine ${name} eingetragen.`} />}
    </Detail>
  );
}
