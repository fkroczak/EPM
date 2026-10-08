/**
 * Reiter „BIA“ (Wunsch aus der Praxis vom 06.10.2026, F114; eigener Reiter seit 07.10.2026, F121).
 *
 * Vorgefertigte Maske für die Körperzusammensetzung: Gewicht, BCM, Fettmasse, ECW, Körperwasser und BMI, dazu ein
 * Feld für die Beurteilung. Das Gewicht kann auf Wunsch gleich in den Gewichtsverlauf übernommen werden.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { datum, eingabeDatum, heuteIso, zahl } from "@/lib/format";
import type { BiaMessung } from "@/lib/typen";
import { Eingabe, Feld, Fehleranzeige, Knopf, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Editor, Richtext } from "@/components/Editor";
import { useAkte } from "./Akte";
import { Abschnitt, Aktenseite, Detail, Eintrag, Eintragsliste, Wertetabelle, useWahl } from "./Aktenseite";
import { AlterHinweis } from "./Befunde";

function BiaDialog({ messung, offen, onOffen }: { messung: BiaMessung | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const leer = { gemessen_am: datum(heuteIso()), gewicht_kg: "", bcm_kg: "", fettmasse_kg: "", ecw_prozent: "",
    koerperwasser_l: "", bmi: "" };
  const [f2, setF2] = useState<Record<string, string>>(leer);
  const [beurteilung, setBeurteilung] = useState("");
  const [uebernehmen, setUebernehmen] = useState(true);
  const [stand, setStand] = useState(0);
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${messung?.id ?? "neu"}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setF2(messung ? {
      gemessen_am: datum(messung.gemessen_am),
      gewicht_kg: messung.gewicht_kg?.toString() ?? "", bcm_kg: messung.bcm_kg?.toString() ?? "",
      fettmasse_kg: messung.fettmasse_kg?.toString() ?? "", ecw_prozent: messung.ecw_prozent?.toString() ?? "",
      koerperwasser_l: messung.koerperwasser_l?.toString() ?? "", bmi: messung.bmi?.toString() ?? "",
    } : leer);
    setBeurteilung(messung?.beurteilung ?? "");
    setUebernehmen(!messung);
    setStand((s) => s + 1);
  }
  const setz = (k: string) => (e: { target: { value: string } }) => setF2((w) => ({ ...w, [k]: e.target.value }));
  const zahlOderNull = (t: string) => (t.trim() ? t.trim().replace(",", ".") : null);
  const bmiVorschlag = useMemo(() => {
    const kg = Number(zahlOderNull(f2.gewicht_kg) ?? NaN);
    if (!patient.groesse_cm || Number.isNaN(kg)) return null;
    const m = patient.groesse_cm / 100;
    return (kg / (m * m)).toFixed(1);
  }, [f2.gewicht_kg, patient.groesse_cm]);

  const speichern = useMutation({
    mutationFn: () => {
      const iso = eingabeDatum(f2.gemessen_am);
      if (!iso) throw new ApiFehler(400, "", null, { gemessen_am: "Bitte als TT.MM.JJJJ eingeben." });
      const koerper = {
        patient: patient.id, gemessen_am: iso, beurteilung, gewicht_uebernehmen: uebernehmen,
        gewicht_kg: zahlOderNull(f2.gewicht_kg), bcm_kg: zahlOderNull(f2.bcm_kg),
        fettmasse_kg: zahlOderNull(f2.fettmasse_kg), ecw_prozent: zahlOderNull(f2.ecw_prozent),
        koerperwasser_l: zahlOderNull(f2.koerperwasser_l), bmi: zahlOderNull(f2.bmi),
      };
      return messung
        ? api<BiaMessung>(`bia-messungen/${messung.id}/`, { method: "PATCH", body: koerper })
        : api<BiaMessung>("bia-messungen/", { body: koerper });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bia", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden(messung ? "BIA-Messung geändert." : "BIA-Messung gespeichert.");
      onOffen(false);
    },
  });
  const fe: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const felder: [string, string, string][] = [
    ["gewicht_kg", "Gewicht", "kg"], ["bcm_kg", "BCM", "kg"], ["fettmasse_kg", "Fettmasse", "kg"],
    ["ecw_prozent", "ECW – extrazelluläres Wasser", "%"], ["koerperwasser_l", "Körperwasser", "l"], ["bmi", "BMI", ""],
  ];

  return (
    <Dialog offen={offen} onOffen={onOffen} breite={620} titel={messung ? "BIA-Messung ändern" : "Neue BIA-Messung"}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <Feld label="Gemessen am" fehler={fe.gemessen_am} className="w-[180px]" pflicht>
        {(p) => <Eingabe {...p} className="num" value={f2.gemessen_am} onChange={setz("gemessen_am")} />}
      </Feld>
      <div className="grid gap-3 sm:grid-cols-2">
        {felder.map(([k, label, einheit]) => (
          <Feld key={k} label={einheit ? `${label} (${einheit})` : label} fehler={fe[k]}
            hinweis={k === "bmi" && bmiVorschlag ? `aus Gewicht und Größe: ${zahl(bmiVorschlag)}` : undefined}>
            {(p) => <Eingabe {...p} className="num" inputMode="decimal" value={f2[k]} onChange={setz(k)} />}
          </Feld>
        ))}
      </div>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" checked={uebernehmen} onChange={(e) => setUebernehmen(e.target.checked)} />
        Gewicht auch in den Gewichtsverlauf eintragen
      </label>
      <Feld label="Zusammenfassung / Beurteilung">
        {() => <Editor key={stand} wert={beurteilung} onAenderung={setBeurteilung} label="Beurteilung" hoehe={96} />}
      </Feld>
      {speichern.error && !Object.keys(fe).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      {fe.fehler ? <span className="fehlertext" role="alert">{fe.fehler}</span> : null}
    </Dialog>
  );
}

/** Die gewählte Messung rechts. */
function BiaDetail({ m, onAendern, aenderbar }: { m: BiaMessung; onAendern: () => void; aenderbar: boolean }) {
  const wert = (x: number | string | null | undefined, einheit: string) =>
    x != null && x !== "" ? `${zahl(x, 1)}${einheit ? ` ${einheit}` : ""}` : "—";
  return (
    <Detail testid="bia-detail"
      titel={<>BIA-Messung vom <span className="num">{datum(m.gemessen_am)}</span></>}
      unter={m.erfasst_von_name ?? undefined}
      aktionen={aenderbar ? <Knopf klein icon="stift" onClick={onAendern}>Bearbeiten</Knopf> : undefined}>
      <Wertetabelle werte={[
        ["Gewicht", wert(m.gewicht_kg, "kg")],
        ["BCM", wert(m.bcm_kg, "kg")],
        ["Fettmasse", wert(m.fettmasse_kg, "kg")],
        ["ECW (extrazelluläres Wasser)", wert(m.ecw_prozent, "%")],
        ["Körperwasser", wert(m.koerperwasser_l, "l")],
        ["BMI", wert(m.bmi, "")],
      ]} />
      {m.beurteilung ? <Abschnitt titel="Beurteilung"><Richtext html={m.beurteilung} className="text-sm" /></Abschnitt> : null}
    </Detail>
  );
}

// ================================================================= Seite
export function Bia() {
  const { patient, erfassen } = useAkte();
  const [wahl, setWahl] = useWahl("messung");
  const [dialog, setDialog] = useState<{ offen: boolean; messung: BiaMessung | null }>({ offen: false, messung: null });
  const bia = useQuery({
    queryKey: ["bia", patient.id],
    queryFn: () => api<BiaMessung[]>(`bia-messungen/?patient=${patient.id}`),
  });
  const liste = bia.data ?? [];
  const gewaehlt = liste.find((m) => String(m.id) === wahl) ?? liste[0];
  return (
    <>
      <Aktenseite
        testid="bia"
        titel={liste.length === 1 ? "BIA-Messung" : "BIA-Messungen"}
        anzahl={liste.length}
        laedt={bia.isPending}
        aktion={erfassen
          ? <Knopf variante="pri" icon="plus" onClick={() => setDialog({ offen: true, messung: null })}>Neue Messung</Knopf>
          : undefined}
        kopfrechts={<><Fehleranzeige fehler={bia.error} />
          <AlterHinweis art="bia" am={liste[0]?.gemessen_am} was="BIA-Messung" /></>}
        liste={
          <Eintragsliste name="BIA-Messungen" leer={liste.length ? undefined : "Noch keine BIA-Messung erfasst."}>
            {liste.map((m) => (
              <Eintrag key={m.id} aktiv={gewaehlt?.id === m.id} onWahl={() => setWahl(String(m.id))}
                datum={datum(m.gemessen_am)}
                zeile={m.bcm_kg != null ? `BCM ${zahl(m.bcm_kg, 1)} kg` : "ohne BCM"}
                unten={m.gewicht_kg != null ? `${zahl(m.gewicht_kg, 1)} kg` : ""} />
            ))}
          </Eintragsliste>
        }
        fuss={<>Körperzusammensetzung mit Beurteilung. Das Gewicht wandert auf Wunsch in den Gewichtsverlauf der Akte.</>}
        detail={gewaehlt
          ? <BiaDetail m={gewaehlt} aenderbar={erfassen} onAendern={() => setDialog({ offen: true, messung: gewaehlt })} />
          : null}
        leer="Links eine Messung wählen."
      />
      {erfassen ? <BiaDialog messung={dialog.messung} offen={dialog.offen}
        onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
    </>
  );
}
