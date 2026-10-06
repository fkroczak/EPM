/**
 * Reiter „Labor“ (Wünsche aus der Praxis vom 06.10.2026, F112/F113; eigener Reiter seit 07.10.2026, F121).
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
import type { Laborbefund, Laborparameter, Laborwert } from "@/lib/typen";
import { Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, cx }
  from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Editor, Richtext } from "@/components/Editor";
import { useAkte } from "./Akte";
import { AlterHinweis } from "./Befunde";

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

// ================================================================= Seite
export function Labor() {
  const { patient, erfassen } = useAkte();
  const [dialog, setDialog] = useState<{ offen: boolean; befund: Laborbefund | null }>({ offen: false, befund: null });
  const befunde = useQuery({
    queryKey: ["laborbefunde", patient.id],
    queryFn: () => api<Laborbefund[]>(`laborbefunde/?patient=${patient.id}`),
  });
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-0.5">
          <h2 className="lbl m-0">Laborbefunde{befunde.data?.length ? <span className="num ml-1.5 opacity-70">{befunde.data.length}</span> : null}</h2>
          <AlterHinweis art="labor" am={befunde.data?.[0]?.abgenommen_am} was="Laborbefund" />
        </div>
        {erfassen ? <Knopf variante="pri" klein onClick={() => setDialog({ offen: true, befund: null })}>
          Neuer Laborbefund</Knopf> : null}
      </div>
      {befunde.isPending ? <Laden /> : <Fehleranzeige fehler={befunde.error} />}
      {befunde.data?.length === 0 ? (
        <Karte className="p-[22px]"><Leer>Noch kein Laborbefund erfasst.</Leer></Karte>
      ) : null}
      {(befunde.data ?? []).map((b) => (
        <BefundKarte key={b.id} befund={b} aenderbar={erfassen} onAendern={() => setDialog({ offen: true, befund: b })} />
      ))}
      {erfassen ? <BefundDialog befund={dialog.befund} offen={dialog.offen}
        onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
    </div>
  );
}
