/**
 * Administration › KI › Nachtaufgaben (14.11.2026): Zeitplan des KI-Dienstes. Eine Aufgabe reiht nur Arbeit ein
 * (Akte auf einen Blick für Termine, Dokumente neu lesen, Dokumente vormerken); abgearbeitet wird nach Modus,
 * Grenzen und Nachtfenster. Darunter „Jetzt neu lesen“ auf Anforderung.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { zeitpunkt } from "@/lib/format";
import { AUFGABE_ARTEN, DOKUMENTTYPEN, WOCHENTAGE_KURZ } from "@/lib/ki";
import type { KiAufgabe, KiAufgabeArt, KiAufgabeParameter, KiNeuLesenFilter } from "@/lib/ki";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";

const NEU_LESEN_STANDARD: KiNeuLesenFilter = { seit_tagen: 30, dokumenttypen: [], nur_anderes_modell: true, hoechstens: 200 };
const PARAMETER_STANDARD: Record<KiAufgabeArt, KiAufgabeParameter> = {
  zusammenfassung_termine: { tage_voraus: 1 },
  neu_lesen: NEU_LESEN_STANDARD,
  dokumente_vormerken: { altbestand: true },
};

function wochentageText(tage: number[]): string {
  const t = [...tage].sort();
  if (t.length === 7) return "täglich";
  if (t.join() === "0,1,2,3,4") return "Mo–Fr";
  return t.map((x) => WOCHENTAGE_KURZ[x] ?? x).join(", ");
}

function parameterText(a: KiAufgabe): string {
  const p = a.parameter ?? {};
  if (a.art === "zusammenfassung_termine") return `Termine in ${p.tage_voraus ?? 1} Tag${(p.tage_voraus ?? 1) === 1 ? "" : "en"}`;
  if (a.art === "neu_lesen") return [`seit ${p.seit_tagen ?? "—"} Tagen`, p.dokumenttypen?.length
    ? p.dokumenttypen.map((d) => DOKUMENTTYPEN[d] ?? d).join(", ") : "alle Typen",
  p.nur_anderes_modell ? "nur von anderem Modell gelesene" : "", `höchstens ${p.hoechstens ?? "—"}`].filter(Boolean).join(" · ");
  return p.altbestand ? "mit Altbestand" : "nur neue";
}

export function KiNachtaufgaben() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const q = useQuery({
    queryKey: ["ki", "aufgaben"],
    queryFn: () => api<KiAufgabe[]>("ki/aufgaben/"),
    refetchInterval: (a) => ((a.state.data ?? []).some((x) => x.jetzt_angefordert) ? 10_000 : false),
  });
  const [bearbeiten, setBearbeiten] = useState<KiAufgabe | "neu" | null>(null);
  const neuLaden = () => qc.invalidateQueries({ queryKey: ["ki", "aufgaben"] });
  const umschalten = useMutation({
    mutationFn: (a: KiAufgabe) => api(`ki/aufgaben/${a.id}/`, { method: "PATCH", body: { aktiv: !a.aktiv } }),
    onSuccess: neuLaden,
  });
  const jetzt = useMutation({
    mutationFn: (a: KiAufgabe) => api(`ki/aufgaben/${a.id}/jetzt/`, { body: {} }),
    onSuccess: () => { void neuLaden(); melden("Angefordert – läuft beim nächsten Durchlauf des KI-Dienstes."); },
  });
  const loeschen = useMutation({
    mutationFn: (a: KiAufgabe) => api(`ki/aufgaben/${a.id}/`, { method: "DELETE" }),
    onSuccess: () => { void neuLaden(); melden("Aufgabe gelöscht."); },
  });
  return (
    <div className="flex flex-col gap-4">
      <Karte className="flex flex-col gap-3 overflow-x-auto">
        <KartenKopf titel="Nachtaufgaben"
          unter="Eine Aufgabe reiht nur Arbeit ein – abgearbeitet wird nach Modus, Grenzen und Nachtfenster. Uhrzeit in der Zeitzone der KI-Einstellungen."
          rechts={<Knopf klein icon="plus" onClick={() => setBearbeiten("neu")}>Neue Aufgabe</Knopf>} />
        {q.isLoading ? <Laden /> : (
          <table className="tabelle text-sm" data-testid="ki-aufgaben">
            <thead><tr><th className="th">Aufgabe</th><th className="th">Wann</th><th className="th">Aktiv</th>
              <th className="th">Nächster Lauf</th><th className="th">Letzter Lauf</th><th className="th"><span className="sr-only">Aktionen</span></th></tr></thead>
            <tbody>{(q.data ?? []).map((a) => (
              <tr key={a.id}>
                <td className="td"><div className="font-medium">{a.name}</div>
                  <div className="text-[0.75rem] gedaempft">{a.art_name || AUFGABE_ARTEN[a.art] || a.art} · {parameterText(a)}</div></td>
                <td className="td whitespace-nowrap">{wochentageText(a.wochentage)}, {(a.uhrzeit ?? "").slice(0, 5)} Uhr</td>
                <td className="td">
                  <label className="flex items-center gap-1.5">
                    <input type="checkbox" checked={a.aktiv} disabled={umschalten.isPending}
                      aria-label={`${a.name} ${a.aktiv ? "deaktivieren" : "aktivieren"}`} onChange={() => umschalten.mutate(a)} />
                    <span className="text-[0.8125rem]">{a.aktiv ? "an" : "aus"}</span>
                  </label>
                </td>
                <td className="td whitespace-nowrap">{a.jetzt_angefordert ? <Chip art="akzent">jetzt angefordert</Chip>
                  : a.aktiv ? zeitpunkt(a.naechster_lauf) : <span className="gedaempft">—</span>}</td>
                <td className="td">{a.letzter_lauf ? <>{zeitpunkt(a.letzter_lauf)}
                  {a.letztes_ergebnis ? <div className="text-[0.75rem] gedaempft">{a.letztes_ergebnis}</div> : null}</> : <span className="gedaempft">noch nie</span>}</td>
                <td className="td whitespace-nowrap">
                  <Knopf klein variante="geist" laedt={jetzt.isPending && jetzt.variables?.id === a.id} disabled={a.jetzt_angefordert}
                    onClick={() => jetzt.mutate(a)}>Jetzt ausführen</Knopf>
                  <Knopf klein variante="geist" icon="stift" aria-label={`${a.name} bearbeiten`} title="Bearbeiten" onClick={() => setBearbeiten(a)} />
                  <Knopf klein variante="geist" icon="x" aria-label={`${a.name} löschen`} title="Löschen"
                    laedt={loeschen.isPending && loeschen.variables?.id === a.id}
                    onClick={() => { if (window.confirm(`Aufgabe „${a.name}“ löschen?`)) loeschen.mutate(a); }} />
                </td>
              </tr>))}</tbody>
          </table>)}
        {q.data && !q.data.length ? <Leer>Keine Aufgaben angelegt.</Leer> : null}
        <Fehleranzeige fehler={q.error ?? umschalten.error ?? jetzt.error ?? loeschen.error} />
      </Karte>
      <NeuLesenJetzt />
      {bearbeiten ? <AufgabeDialog aufgabe={bearbeiten === "neu" ? null : bearbeiten} onZu={() => setBearbeiten(null)} /> : null}
    </div>
  );
}

type Entwurf = { name: string; art: KiAufgabeArt; aktiv: boolean; wochentage: number[]; uhrzeit: string; parameter: KiAufgabeParameter };

function AufgabeDialog({ aufgabe, onZu }: { aufgabe: KiAufgabe | null; onZu: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [w, setW] = useState<Entwurf>(() => aufgabe
    ? { name: aufgabe.name, art: aufgabe.art, aktiv: aufgabe.aktiv, wochentage: aufgabe.wochentage, uhrzeit: (aufgabe.uhrzeit ?? "").slice(0, 5),
      parameter: { ...PARAMETER_STANDARD[aufgabe.art], ...aufgabe.parameter } }
    : { name: "", art: "zusammenfassung_termine", aktiv: true, wochentage: [0, 1, 2, 3, 4, 5, 6], uhrzeit: "03:00",
      parameter: PARAMETER_STANDARD.zusammenfassung_termine });
  const los = useMutation({
    mutationFn: () => aufgabe
      ? api(`ki/aufgaben/${aufgabe.id}/`, { method: "PATCH", body: w })
      : api("ki/aufgaben/", { body: w }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["ki", "aufgaben"] }); melden("Aufgabe gespeichert."); onZu(); },
  });
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  // Fehler der Parameter kommen flach als „parameter.seit_tagen“ oder als „parameter“
  const pf: Feldfehler = Object.fromEntries(Object.entries(f).filter(([k]) => k.startsWith("parameter.")).map(([k, v]) => [k.slice(10), v]));
  const setP = (p: Partial<KiAufgabeParameter>) => setW({ ...w, parameter: { ...w.parameter, ...p } });
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel={aufgabe ? "Aufgabe bearbeiten" : "Neue Aufgabe"} breite={600}
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={los.isPending} disabled={!w.name.trim() || !w.wochentage.length} onClick={() => los.mutate()}>Speichern</Knopf></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Feld label="Name" fehler={f.name} className="sm:col-span-2" pflicht>
          {(p) => <Eingabe {...p} maxLength={100} value={w.name} onChange={(e) => setW({ ...w, name: e.target.value })} />}</Feld>
        <Feld label="Art" fehler={f.art}>
          {(p) => <Auswahl {...p} value={w.art} onChange={(e) => {
            const art = e.target.value as KiAufgabeArt;
            setW({ ...w, art, parameter: PARAMETER_STANDARD[art] });
          }}>{Object.entries(AUFGABE_ARTEN).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</Auswahl>}</Feld>
        <Feld label="Uhrzeit" fehler={f.uhrzeit}>
          {(p) => <Eingabe {...p} type="time" value={w.uhrzeit} onChange={(e) => setW({ ...w, uhrzeit: e.target.value })} />}</Feld>
      </div>
      <fieldset className="m-0 p-0 border-0 flex flex-col gap-1.5">
        <legend className="text-[0.8125rem] font-medium mb-1">Wochentage</legend>
        <div className="flex gap-3 flex-wrap text-sm">
          {WOCHENTAGE_KURZ.map((t, i) => (
            <label key={t} className="flex items-center gap-1.5"><input type="checkbox" checked={w.wochentage.includes(i)}
              onChange={(e) => setW({ ...w, wochentage: e.target.checked ? [...w.wochentage, i].sort() : w.wochentage.filter((x) => x !== i) })} />{t}</label>))}
        </div>
        {f.wochentage ? <span className="fehlertext" role="alert">{f.wochentage}</span> : null}
      </fieldset>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={w.aktiv} onChange={(e) => setW({ ...w, aktiv: e.target.checked })} />aktiv</label>
      <div className="flex flex-col gap-3 border-t border-rand pt-3">
        {w.art === "zusammenfassung_termine" ? (
          <Feld label="Termine in wie vielen Tagen?" hinweis="1 = Termine von morgen (1–14)" fehler={f.parameter ?? pf.tage_voraus}>
            {(p) => <Eingabe {...p} type="number" min={1} max={14} value={String(w.parameter.tage_voraus ?? "")}
              onChange={(e) => setP({ tage_voraus: e.target.value === "" ? undefined : Number(e.target.value) })} />}</Feld>
        ) : w.art === "neu_lesen" ? (
          <NeuLesenFelder werte={{ ...NEU_LESEN_STANDARD, ...w.parameter }} onWerte={(x) => setP(x)} fehler={pf} />
        ) : (
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!w.parameter.altbestand}
            onChange={(e) => setP({ altbestand: e.target.checked })} />auch Altbestand vormerken (sonst nur neue Dokumente)</label>
        )}
        {w.art !== "zusammenfassung_termine" && (f.parameter || pf.altbestand)
          ? <span className="fehlertext" role="alert">{f.parameter ?? pf.altbestand}</span> : null}
      </div>
      <Fehleranzeige fehler={los.error} />
    </Dialog>
  );
}

function NeuLesenFelder({ werte, onWerte, fehler }: { werte: KiNeuLesenFilter; onWerte: (w: KiNeuLesenFilter) => void; fehler: Feldfehler }) {
  const zahlWert = (v: string) => (v === "" ? ("" as unknown as number) : Number(v));
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Feld label="Dokumente der letzten (Tage)" hinweis="hochgeladen in diesem Zeitraum" fehler={fehler.seit_tagen}>
          {(p) => <Eingabe {...p} type="number" min={1} value={String(werte.seit_tagen ?? "")}
            onChange={(e) => onWerte({ ...werte, seit_tagen: zahlWert(e.target.value) })} />}</Feld>
        <Feld label="Höchstens (Dokumente)" fehler={fehler.hoechstens}>
          {(p) => <Eingabe {...p} type="number" min={1} value={String(werte.hoechstens ?? "")}
            onChange={(e) => onWerte({ ...werte, hoechstens: zahlWert(e.target.value) })} />}</Feld>
      </div>
      <fieldset className="m-0 p-0 border-0 flex flex-col gap-1.5">
        <legend className="text-[0.8125rem] font-medium mb-1">Dokumenttypen <span className="gedaempft font-normal">(keiner gewählt = alle)</span></legend>
        <div className="flex gap-3 flex-wrap text-[0.8125rem]">
          {Object.entries(DOKUMENTTYPEN).map(([k, t]) => (
            <label key={k} className="flex items-center gap-1.5"><input type="checkbox" checked={werte.dokumenttypen.includes(k)}
              onChange={(e) => onWerte({ ...werte, dokumenttypen: e.target.checked ? [...werte.dokumenttypen, k] : werte.dokumenttypen.filter((x) => x !== k) })} />{t}</label>))}
        </div>
        {fehler.dokumenttypen ? <span className="fehlertext" role="alert">{fehler.dokumenttypen}</span> : null}
      </fieldset>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={werte.nur_anderes_modell}
        onChange={(e) => onWerte({ ...werte, nur_anderes_modell: e.target.checked })} />nur Dokumente, die mit einem anderen Modell gelesen wurden</label>
      <p className="m-0 text-[0.75rem] gedaempft">Ausgenommen: Dokumente in Arbeit, übernommene und abgelehnte (die nur einzeln über „Erneut verarbeiten“).</p>
    </div>
  );
}

function NeuLesenJetzt() {
  const qc = useQueryClient();
  const [werte, setWerte] = useState<KiNeuLesenFilter>(NEU_LESEN_STANDARD);
  const los = useMutation({
    mutationFn: () => api<{ vorgemerkt: number }>("ki/vorgaenge/neu_lesen/", { body: werte }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ki"] }),
  });
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  return (
    <Karte className="flex flex-col gap-3" data-testid="ki-neu-lesen">
      <KartenKopf titel="Jetzt neu lesen"
        unter="Dokumente mit dem aktiven Modell erneut lesen lassen – mit der Priorität „Neu lesen“, abgearbeitet nach Modus und Nachtfenster" />
      <NeuLesenFelder werte={werte} onWerte={(w) => { setWerte(w); los.reset(); }} fehler={f} />
      <div className="flex gap-2"><Knopf variante="pri" laedt={los.isPending} onClick={() => los.mutate()}>Neu lesen vormerken</Knopf></div>
      {los.data ? <Meldung art="ok">{los.data.vorgemerkt === 1 ? "1 Dokument vorgemerkt." : `${los.data.vorgemerkt} Dokumente vorgemerkt.`}</Meldung> : null}
      <Fehleranzeige fehler={los.error} />
    </Karte>
  );
}
