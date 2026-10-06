/**
 * Labor und BIA (Wünsche aus der Praxis vom 06.10.2026, F112–F114).
 *
 * Statt jeden Befund abzuschreiben, steht die Maske schon da: die Parameter nach Gruppen, Einheit vorbelegt –
 * eingetragen wird nur der gemessene Wert. Zeilen ohne Wert werden nicht gespeichert. Für alles, was nicht im
 * Katalog steht (Tumormarker, genetische Parameter), gibt es freie Zeilen.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useLaborparameter } from "@/lib/daten";
import { datum, eingabeDatum, heuteIso, zahl } from "@/lib/format";
import { LABORGRUPPEN } from "@/lib/typen";
import type { BiaMessung, Laborbefund, Laborparameter, Laborwert } from "@/lib/typen";
import { Anzeige, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, cx }
  from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Editor, Richtext } from "@/components/Editor";
import { useAkte } from "./Akte";

type Zeile = { parameter: number | null; freitext_name: string; wert: string; einheit: string; bemerkung: string };

function leereZeile(): Zeile {
  return { parameter: null, freitext_name: "", wert: "", einheit: "", bemerkung: "" };
}

/** „18“ → Zahl, „< 0,1“ oder „negativ“ → Text (U47). Komma gilt als Dezimaltrennzeichen. */
function wertFelder(text: string): { wert: string | null; wert_text: string } {
  const sauber = text.trim().replace(",", ".");
  if (!sauber) return { wert: null, wert_text: "" };
  return /^-?\d+(\.\d+)?$/.test(sauber) ? { wert: sauber, wert_text: "" } : { wert: null, wert_text: text.trim() };
}

function anzeigeWert(w: Laborwert): string {
  return w.anzeige_wert ?? (w.wert != null ? zahl(w.wert) : w.wert_text);
}

function referenzText(w: { referenz_von: number | null; referenz_bis: number | null }): string {
  if (w.referenz_von == null && w.referenz_bis == null) return "";
  return `${w.referenz_von != null ? zahl(w.referenz_von) : ""} – ${w.referenz_bis != null ? zahl(w.referenz_bis) : ""}`
    .replace(/^ – /, "< ").replace(/ – $/, " >").trim();
}

// ================================================================= Laborbefund erfassen
function BefundDialog({ befund, offen, onOffen }: { befund: Laborbefund | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const katalog = useLaborparameter();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [abgenommen, setAbgenommen] = useState(datum(heuteIso()));
  const [labor, setLabor] = useState("");
  const [beurteilung, setBeurteilung] = useState("");
  const [werte, setWerte] = useState<Record<number, string>>({});
  const [frei, setFrei] = useState<Zeile[]>([]);
  const [stand, setStand] = useState(0);

  // Dialog öffnen: Felder aus dem Befund füllen (oder leeren)
  const schluessel = `${befund?.id ?? "neu"}-${offen}`;
  const [gesetzt, setGesetzt] = useState("");
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setAbgenommen(datum(befund?.abgenommen_am ?? heuteIso()));
    setLabor(befund?.labor ?? "");
    setBeurteilung(befund?.beurteilung ?? "");
    const ausKatalog: Record<number, string> = {};
    const freie: Zeile[] = [];
    for (const w of befund?.werte ?? []) {
      if (w.parameter) ausKatalog[w.parameter] = anzeigeWert(w);
      else freie.push({ parameter: null, freitext_name: w.freitext_name, wert: anzeigeWert(w), einheit: w.einheit, bemerkung: w.bemerkung });
    }
    setWerte(ausKatalog);
    setFrei(freie);
    setStand((s) => s + 1);
  }

  const gruppen = useMemo(() => {
    const nach: Record<string, Laborparameter[]> = {};
    for (const p of katalog.data ?? []) (nach[p.gruppe] ??= []).push(p);
    return Object.entries(nach);
  }, [katalog.data]);

  const anzahl = Object.values(werte).filter((v) => v.trim()).length + frei.filter((z) => z.freitext_name.trim() && z.wert.trim()).length;

  const speichern = useMutation({
    mutationFn: () => {
      const iso = eingabeDatum(abgenommen);
      if (!iso) throw new ApiFehler(400, "", null, { abgenommen_am: "Bitte als TT.MM.JJJJ eingeben." });
      const zeilen: Record<string, unknown>[] = [];
      for (const p of katalog.data ?? []) {
        const text = (werte[p.id] ?? "").trim();
        if (!text) continue;
        zeilen.push({ parameter: p.id, ...wertFelder(text), einheit: p.einheit });
      }
      for (const z of frei) {
        if (!z.freitext_name.trim() || !z.wert.trim()) continue;
        zeilen.push({ freitext_name: z.freitext_name.trim(), ...wertFelder(z.wert), einheit: z.einheit.trim(), bemerkung: z.bemerkung.trim() });
      }
      const koerper = { patient: patient.id, abgenommen_am: iso, labor: labor.trim(), beurteilung, werte: zeilen };
      return befund
        ? api<Laborbefund>(`laborbefunde/${befund.id}/`, { method: "PATCH", body: koerper })
        : api<Laborbefund>("laborbefunde/", { body: koerper });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["laborbefunde", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden(befund ? "Laborbefund geändert." : "Laborbefund gespeichert.");
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};

  return (
    <Dialog offen={offen} onOffen={onOffen} breite={900}
      titel={befund ? "Laborbefund ändern" : "Neuer Laborbefund"}
      beschreibung="Nur den gemessenen Wert eintragen – die Einheit steht schon da. Leere Zeilen werden nicht gespeichert."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!anzahl} onClick={() => speichern.mutate()}>
          {anzahl ? `${anzahl} ${anzahl === 1 ? "Wert" : "Werte"} speichern` : "Speichern"}
        </Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-[160px_1fr]">
        <Feld label="Abnahme am" fehler={f.abgenommen_am} pflicht>
          {(p) => <Eingabe {...p} className="num" value={abgenommen} onChange={(e) => setAbgenommen(e.target.value)} />}
        </Feld>
        <Feld label="Labor" fehler={f.labor}>
          {(p) => <Eingabe {...p} value={labor} maxLength={150} placeholder="z. B. Labor Dr. Wagner"
            onChange={(e) => setLabor(e.target.value)} />}
        </Feld>
      </div>

      {katalog.isPending ? <Laden text="Parameter werden geladen …" /> : null}
      <div className="flex flex-col gap-4" data-testid="labor-maske">
        {gruppen.map(([gruppe, liste]) => (
          <section key={gruppe} className="flex flex-col gap-1.5">
            <h3 className="lbl m-0 text-[0.8125rem]">{LABORGRUPPEN[gruppe] ?? gruppe}</h3>
            <div className="grid gap-x-4 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
              {liste.map((p) => (
                <label key={p.id} className="grid grid-cols-[1fr_84px_auto] items-center gap-2 text-sm">
                  <span className="truncate" title={p.name}>{p.name}</span>
                  <Eingabe className="num klein" inputMode="decimal" aria-label={p.name}
                    value={werte[p.id] ?? ""} onChange={(e) => setWerte((w) => ({ ...w, [p.id]: e.target.value }))} />
                  <span className="gedaempft text-[0.75rem] w-[72px]">{p.einheit}</span>
                </label>
              ))}
            </div>
          </section>
        ))}
      </div>

      {/* Weitere Parameter: Tumormarker, genetische Parameter … (nicht im Katalog) */}
      <section className="flex flex-col gap-2" data-testid="weitere-parameter">
        <h3 className="lbl m-0 text-[0.8125rem]">Weitere Parameter</h3>
        {frei.map((z, i) => (
          <div key={i} className="grid grid-cols-[1fr_96px_96px_1fr_auto] items-center gap-2">
            <Eingabe aria-label={`Parameter ${i + 1}`} placeholder="z. B. CA 19-9" value={z.freitext_name}
              onChange={(e) => setFrei((l) => l.map((x, j) => (j === i ? { ...x, freitext_name: e.target.value } : x)))} />
            <Eingabe aria-label={`Wert ${i + 1}`} className="num" value={z.wert}
              onChange={(e) => setFrei((l) => l.map((x, j) => (j === i ? { ...x, wert: e.target.value } : x)))} />
            <Eingabe aria-label={`Einheit ${i + 1}`} placeholder="U/ml" value={z.einheit}
              onChange={(e) => setFrei((l) => l.map((x, j) => (j === i ? { ...x, einheit: e.target.value } : x)))} />
            <Eingabe aria-label={`Bemerkung ${i + 1}`} value={z.bemerkung}
              onChange={(e) => setFrei((l) => l.map((x, j) => (j === i ? { ...x, bemerkung: e.target.value } : x)))} />
            <Knopf klein icon="x" aria-label={`Zeile ${i + 1} entfernen`}
              onClick={() => setFrei((l) => l.filter((_, j) => j !== i))} />
          </div>
        ))}
        <Knopf klein className="self-start" onClick={() => setFrei((l) => [...l, leereZeile()])}>Parameter hinzufügen</Knopf>
      </section>

      <Feld label="Zusammenfassung / Beurteilung">
        {() => <Editor key={stand} wert={beurteilung} onAenderung={setBeurteilung} label="Beurteilung" hoehe={96} />}
      </Feld>
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      {Object.entries(f).filter(([k]) => k !== "abgenommen_am" && k !== "labor").map(([k, v]) =>
        <span key={k} className="fehlertext" role="alert">{v}</span>)}
    </Dialog>
  );
}

function BefundKarte({ befund, onAendern, aenderbar }: { befund: Laborbefund; onAendern: () => void; aenderbar: boolean }) {
  const [offen, setOffen] = useState(false);
  const nachGruppe = useMemo(() => {
    const nach: Record<string, Laborwert[]> = {};
    for (const w of befund.werte) (nach[w.gruppe ?? "sonstiges"] ??= []).push(w);
    return Object.entries(nach);
  }, [befund.werte]);
  return (
    <Karte className="p-[22px] flex flex-col gap-3">
      <KartenKopf
        titel={<>Laborbefund vom <span className="num">{datum(befund.abgenommen_am)}</span></>}
        unter={[befund.labor, `${befund.anzahl_werte} Werte`, befund.erfasst_von_name].filter(Boolean).join(" · ")}
        rechts={<>
          <Knopf klein onClick={() => setOffen((o) => !o)}>{offen ? "Zuklappen" : "Werte zeigen"}</Knopf>
          {aenderbar ? <Knopf klein onClick={onAendern}>Ändern</Knopf> : null}
        </>}
      />
      {offen ? (
        <div className="flex flex-col gap-3">
          {nachGruppe.map(([gruppe, liste]) => (
            <section key={gruppe} className="flex flex-col gap-1">
              <h3 className="lbl m-0 text-[0.8125rem]">{LABORGRUPPEN[gruppe] ?? "Weitere Parameter"}</h3>
              <div className="grid gap-x-4 sm:grid-cols-2 lg:grid-cols-3">
                {liste.map((w, i) => (
                  <div key={w.id ?? i} className="grid grid-cols-[1fr_auto_auto] items-baseline gap-2 text-sm py-0.5">
                    <span className="truncate">{w.bezeichnung}</span>
                    <span className={cx("num", w.ausserhalb && "font-semibold")}>{anzeigeWert(w)}</span>
                    <span className="gedaempft text-[0.75rem] w-[64px]">{w.einheit}</span>
                    {w.ausserhalb ? <span className="col-span-3 text-[0.75rem] gedaempft">
                      {w.ausserhalb === "hoch" ? "über" : "unter"} Referenz {referenzText(w)}</span> : null}
                  </div>
                ))}
              </div>
            </section>
          ))}
          {befund.beurteilung ? (
            <div>
              <h3 className="lbl m-0 text-[0.8125rem]">Beurteilung</h3>
              <Richtext html={befund.beurteilung} />
            </div>
          ) : null}
        </div>
      ) : null}
    </Karte>
  );
}

// ================================================================= BIA
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
export function Befunde() {
  const { patient, erfassen } = useAkte();
  const [befundDialog, setBefundDialog] = useState<{ offen: boolean; befund: Laborbefund | null }>({ offen: false, befund: null });
  const [biaDialog, setBiaDialog] = useState<{ offen: boolean; messung: BiaMessung | null }>({ offen: false, messung: null });

  const befunde = useQuery({
    queryKey: ["laborbefunde", patient.id],
    queryFn: () => api<Laborbefund[]>(`laborbefunde/?patient=${patient.id}`),
  });
  const bia = useQuery({
    queryKey: ["bia", patient.id],
    queryFn: () => api<BiaMessung[]>(`bia-messungen/?patient=${patient.id}`),
  });

  return (
    <div className="flex flex-col gap-4">
      <Karte className="p-[22px] flex flex-col gap-3">
        <KartenKopf titel="BIA-Messungen" unter="Körperzusammensetzung mit Beurteilung"
          rechts={erfassen ? <Knopf variante="pri" klein onClick={() => setBiaDialog({ offen: true, messung: null })}>
            Neue Messung</Knopf> : undefined} />
        {bia.isPending ? <Laden /> : <Fehleranzeige fehler={bia.error} />}
        {bia.data ? <BiaTabelle messungen={bia.data} aenderbar={erfassen}
          onAendern={(m) => setBiaDialog({ offen: true, messung: m })} /> : null}
      </Karte>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="lbl m-0">Laborbefunde{befunde.data?.length ? <span className="num ml-1.5 opacity-70">{befunde.data.length}</span> : null}</h2>
        {erfassen ? <Knopf variante="pri" klein onClick={() => setBefundDialog({ offen: true, befund: null })}>
          Neuer Laborbefund</Knopf> : null}
      </div>
      {befunde.isPending ? <Laden /> : <Fehleranzeige fehler={befunde.error} />}
      {befunde.data?.length === 0 ? (
        <Karte className="p-[22px]"><Leer>Noch kein Laborbefund erfasst.</Leer></Karte>
      ) : null}
      {(befunde.data ?? []).map((b) => (
        <BefundKarte key={b.id} befund={b} aenderbar={erfassen} onAendern={() => setBefundDialog({ offen: true, befund: b })} />
      ))}

      {erfassen ? <>
        <BefundDialog befund={befundDialog.befund} offen={befundDialog.offen}
          onOffen={(o) => setBefundDialog((d) => ({ ...d, offen: o }))} />
        <BiaDialog messung={biaDialog.messung} offen={biaDialog.offen}
          onOffen={(o) => setBiaDialog((d) => ({ ...d, offen: o }))} />
      </> : null}
    </div>
  );
}

/** Kurzfassung für die Übersicht der Akte: letzter Laborbefund und letzte BIA-Messung. */
export function BefundeKurz({ patientId }: { patientId: number }) {
  const befunde = useQuery({ queryKey: ["laborbefunde", patientId], queryFn: () => api<Laborbefund[]>(`laborbefunde/?patient=${patientId}`) });
  const bia = useQuery({ queryKey: ["bia", patientId], queryFn: () => api<BiaMessung[]>(`bia-messungen/?patient=${patientId}`) });
  const letzterBefund = befunde.data?.[0];
  const letzteBia = bia.data?.[0];
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Anzeige label="Letzter Laborbefund">
        {letzterBefund ? `${datum(letzterBefund.abgenommen_am)} · ${letzterBefund.anzahl_werte} Werte` : ""}
      </Anzeige>
      <Anzeige label="Letzte BIA-Messung">
        {letzteBia ? `${datum(letzteBia.gemessen_am)}${letzteBia.bcm_kg != null ? ` · BCM ${zahl(letzteBia.bcm_kg, 1)} kg` : ""}` : ""}
      </Anzeige>
    </div>
  );
}
