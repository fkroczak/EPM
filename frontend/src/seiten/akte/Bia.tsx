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
import { Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Editor, Richtext } from "@/components/Editor";
import { useAkte } from "./Akte";
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

function BiaTabelle({ messungen, onAendern, aenderbar }: {
  messungen: BiaMessung[]; onAendern: (m: BiaMessung) => void; aenderbar: boolean;
}) {
  if (!messungen.length) return <Leer>Noch keine BIA-Messung erfasst.</Leer>;
  return (
    <div className="overflow-x-auto">
      <table className="tabelle w-full" data-testid="bia-tabelle">
        <thead>
          <tr>
            <th>Datum</th><th className="num">Gewicht</th><th className="num">BCM</th><th className="num">Fettmasse</th>
            <th className="num">ECW</th><th className="num">Körperwasser</th><th className="num">BMI</th>
            <th>Beurteilung</th>{aenderbar ? <th /> : null}
          </tr>
        </thead>
        <tbody>
          {messungen.map((m) => (
            <tr key={m.id}>
              <td className="num">{datum(m.gemessen_am)}</td>
              <td className="num">{m.gewicht_kg != null ? `${zahl(m.gewicht_kg, 1)} kg` : "—"}</td>
              <td className="num">{m.bcm_kg != null ? `${zahl(m.bcm_kg, 1)} kg` : "—"}</td>
              <td className="num">{m.fettmasse_kg != null ? `${zahl(m.fettmasse_kg, 1)} kg` : "—"}</td>
              <td className="num">{m.ecw_prozent != null ? `${zahl(m.ecw_prozent, 1)} %` : "—"}</td>
              <td className="num">{m.koerperwasser_l != null ? `${zahl(m.koerperwasser_l, 1)} l` : "—"}</td>
              <td className="num">{m.bmi != null ? zahl(m.bmi, 1) : "—"}</td>
              <td className="max-w-[320px]"><Richtext html={m.beurteilung} className="text-sm" /></td>
              {aenderbar ? <td className="text-right"><Knopf klein onClick={() => onAendern(m)}>Ändern</Knopf></td> : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ================================================================= Seite
export function Bia() {
  const { patient, erfassen } = useAkte();
  const [dialog, setDialog] = useState<{ offen: boolean; messung: BiaMessung | null }>({ offen: false, messung: null });
  const bia = useQuery({
    queryKey: ["bia", patient.id],
    queryFn: () => api<BiaMessung[]>(`bia-messungen/?patient=${patient.id}`),
  });
  return (
    <div className="flex flex-col gap-4">
      <Karte className="p-[22px] flex flex-col gap-3">
        <KartenKopf titel="BIA-Messungen" unter="Körperzusammensetzung mit Beurteilung"
          rechts={erfassen ? <Knopf variante="pri" klein onClick={() => setDialog({ offen: true, messung: null })}>
            Neue Messung</Knopf> : undefined} />
        <AlterHinweis art="bia" am={bia.data?.[0]?.gemessen_am} was="BIA-Messung" />
        {bia.isPending ? <Laden /> : <Fehleranzeige fehler={bia.error} />}
        {bia.data ? <BiaTabelle messungen={bia.data} aenderbar={erfassen}
          onAendern={(m) => setDialog({ offen: true, messung: m })} /> : null}
      </Karte>
      {erfassen ? <BiaDialog messung={dialog.messung} offen={dialog.offen}
        onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
    </div>
  );
}
