/**
 * Texterkennung lernt mit (F182): Bereich „Gelernte Zuordnungen“ unter Scans und die Kennzahl
 * „Wie oft musste korrigiert werden“.
 *
 * Beim Übernehmen merkt sich EPM, welche Bezeichnung auf einem Befund zu welchem Laborparameter, BIA-Feld oder welcher
 * Diagnose gehört – je Labor und allgemein, ohne Patientendaten. Hier lassen sich einzelne Zuordnungen ansehen, löschen
 * oder sperren („nie wieder so zuordnen“). Sichtbar mit „Scans“ oder „Vorlagen pflegen“ (Server prüft).
 *
 * F189: Steuerung des Lernens (pausieren, Schwelle 1–3) für „Vorlagen pflegen“, Erklärung „Falsches korrigieren“,
 * neue Arten „nicht auswerten“ (aus „Falsch erkannt – gehört nicht dazu“) und „Bereich der Werte“.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { datum, zahl } from "@/lib/format";
import { Auswahl, Chip, Fehleranzeige, Karte, Knopf, Laden, Leer, Meldung, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { Bestaetigen } from "@/components/Bestaetigen";
import { Icon } from "@/components/ui/icon";
import { useHinweis } from "@/components/ui/hinweise";

type Eintrag = {
  id: number; art: "labor" | "bia" | "diagnose" | "spalte" | "ignorieren" | "bereich"; art_name: string; quelle: string; quelle_name: string;
  erkannt: string; ziel: string; bestaetigt: number; sicher: boolean; gesperrt: boolean; lesefehler: boolean;
  zuletzt_am: string; zuletzt_von: string | null;
};
type Steuerung = { pausiert: boolean; schwelle: number; geaendert_am: string | null; geaendert_von: string | null; darf_steuern: boolean };
type Liste = { eintraege: Eintrag[]; quellen: { quelle: string; name: string }[]; schwelle: number; darf_aendern: boolean;
  steuerung: Steuerung };

type Monat = { monat: string; uebernommen: number; korrigiert: number; verworfen?: number; anteil: number | null;
  arten: Record<"labor" | "bia" | "diagnose", { uebernommen: number; korrigiert: number; anteil: number | null }> };
export type Kennzahl = { monate: Monat[]; aktuell: Monat; vormonat: Monat | null; trend: number | null; gelernt: number; schwelle: number };

const ARTEN_NAMEN: Record<string, string> = { labor: "Labor", bia: "BIA", diagnose: "Diagnosen", spalte: "Spaltenlage",
  ignorieren: "Nicht auswerten", bereich: "Bereich der Werte" };

function monatName(iso: string, lang = false): string {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("de-DE", lang ? { month: "long", year: "numeric" } : { month: "short" });
}

function anteil(a: number | null | undefined): string {
  return a == null ? "–" : `${String(a).replace(".", ",")} %`;
}

// ---------------------------------------------------------------- Kennzahl
/** Klein in der Scans-Übersicht: Anteil der korrigierten Werte in diesem Monat mit Trend; Klick öffnet die große Ansicht */
export function KorrekturKennzahl() {
  const [offen, setOffen] = useState(false);
  const k = useQuery({ queryKey: ["scans", "kennzahl"], queryFn: () => api<Kennzahl>("scans/kennzahl/"), staleTime: 60_000 });
  const d = k.data;
  if (!d) return null;
  const t = d.trend;
  return (
    <>
      <button type="button" onClick={() => setOffen(true)} data-testid="kennzahl-korrekturen"
        className="bg-transparent border-0 p-0 cursor-pointer text-xs gedaempft hover:underline text-left"
        title="Anteil der übernommenen Werte, die beim Zuordnen geändert oder von Hand ergänzt werden mussten">
        · korrigiert im {monatName(d.aktuell.monat)}: <span className="num font-medium text-tinte">{anteil(d.aktuell.anteil)}</span>
        {t != null && t !== 0 ? <span className={cx("ml-1", t < 0 ? "text-ok" : "text-warn")}>{t < 0 ? "▼" : "▲"} {String(Math.abs(t)).replace(".", ",")}</span> : null}
      </button>
      <Dialog offen={offen} onOffen={setOffen} titel="Wie oft musste korrigiert werden?" breite={640}
        beschreibung="Anteil der übernommenen Werte (Labor, BIA, Diagnosen), die die Pflegekraft beim Zuordnen ändern oder von Hand ergänzen musste. Je kleiner, desto besser liest die Texterkennung."
        fuss={<Knopf onClick={() => setOffen(false)}>Schließen</Knopf>}>
        <KennzahlGross k={d} />
      </Dialog>
    </>
  );
}

function KennzahlGross({ k }: { k: Kennzahl }) {
  const max = 100;
  return (
    <div className="flex flex-col gap-4" data-testid="kennzahl-gross">
      <div className="flex items-end gap-1.5 h-40 border-b border-rand pb-1" role="img"
        aria-label={`Anteil korrigierter Werte je Monat: ${k.monate.map((m) => `${monatName(m.monat, true)} ${anteil(m.anteil)}`).join(", ")}`}>
        {k.monate.map((m) => (
          <div key={m.monat} className="flex-1 flex flex-col items-center justify-end gap-1 h-full min-w-0"
            title={`${monatName(m.monat, true)}: ${anteil(m.anteil)} (${m.korrigiert} von ${m.uebernommen})`}>
            <span className="text-[0.6875rem] num gedaempft">{m.anteil == null ? "" : Math.round(m.anteil)}</span>
            <div className="w-full rounded-t bg-akzent/70" style={{ height: `${m.anteil == null ? 0 : Math.max(2, (m.anteil / max) * 100)}%` }} />
          </div>
        ))}
      </div>
      <div className="flex gap-1.5 -mt-3">
        {k.monate.map((m) => <span key={m.monat} className="flex-1 text-center text-[0.6875rem] gedaempft truncate">{monatName(m.monat)}</span>)}
      </div>
      <div className="overflow-x-auto">
        <table className="tabelle text-sm">
          <thead><tr><th className="th">Monat</th><th className="th">übernommen</th><th className="th">korrigiert</th>
            <th className="th">Labor</th><th className="th">BIA</th><th className="th">Diagnosen</th>
            <th className="th" title="„Falsch erkannt“ angemerkt">verworfen</th></tr></thead>
          <tbody>
            {[...k.monate].reverse().filter((m) => m.uebernommen).map((m) => (
              <tr key={m.monat}>
                <td className="td">{monatName(m.monat, true)}</td>
                <td className="td num">{zahl(m.uebernommen)}</td>
                <td className="td num">{zahl(m.korrigiert)} ({anteil(m.anteil)})</td>
                <td className="td num">{anteil(m.arten.labor.anteil)}</td>
                <td className="td num">{anteil(m.arten.bia.anteil)}</td>
                <td className="td num">{anteil(m.arten.diagnose.anteil)}</td>
                <td className="td num">{zahl(m.verworfen ?? 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!k.monate.some((m) => m.uebernommen) ? <Leer>Noch keine Werte übernommen.</Leer> : null}
      </div>
      <span className="text-[0.8125rem] gedaempft">Gelernte Zuordnungen bisher: {zahl(k.gelernt)}. Gezählt werden nur Übernahmen
        aus Scans; Testzugänge zählen nicht mit.</span>
    </div>
  );
}

// ---------------------------------------------------------------- Liste
export function GelernteZuordnungen({ onZurueck }: { onZurueck: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [suche, setSuche] = useState("");
  const [art, setArt] = useState("");
  const [quelle, setQuelle] = useState("");
  const [weg, setWeg] = useState<Eintrag | null>(null);
  const [erklaerung, setErklaerung] = useState(false);
  const params = new URLSearchParams();
  if (suche.trim()) params.set("suche", suche.trim());
  if (art) params.set("art", art);
  if (quelle) params.set("quelle", quelle);
  const liste = useQuery({
    queryKey: ["scans", "gelernt", params.toString()],
    queryFn: () => api<Liste>(`scans/gelernt/?${params.toString()}`),
    placeholderData: (alt) => alt,
  });
  const aendern = useMutation({
    mutationFn: ({ e, gesperrt }: { e: Eintrag; gesperrt: boolean }) =>
      api<Eintrag>(`scans/gelernt/${e.id}/`, { method: "PATCH", body: { gesperrt } }),
    onSuccess: (e) => {
      melden(e.gesperrt ? `„${e.erkannt}“ wird nicht mehr so zugeordnet.` : `„${e.erkannt}“ ist wieder freigegeben.`);
      void qc.invalidateQueries({ queryKey: ["scans", "gelernt"] });
    },
  });
  const loeschen = useMutation({
    mutationFn: (e: Eintrag) => api(`scans/gelernt/${e.id}/`, { method: "DELETE" }),
    onSuccess: () => {
      melden("Gelernte Zuordnung gelöscht.");
      setWeg(null);
      void qc.invalidateQueries({ queryKey: ["scans", "gelernt"] });
      void qc.invalidateQueries({ queryKey: ["scans", "kennzahl"] });
    },
  });
  const d = liste.data;
  const darf = d?.darf_aendern ?? false;
  const steuern = useMutation({
    mutationFn: (x: Partial<Pick<Steuerung, "pausiert" | "schwelle">>) => api<Steuerung>("scans/gelernt/steuerung/", { method: "PATCH", body: x }),
    onSuccess: (st) => {
      melden(st.pausiert ? "Lernen pausiert – Gelerntes wird weiter genutzt." : `Lernen aktiv, sicher ab ${st.schwelle} Bestätigung${st.schwelle === 1 ? "" : "en"}.`);
      void qc.invalidateQueries({ queryKey: ["scans", "gelernt"] });
      void qc.invalidateQueries({ queryKey: ["scans", "kennzahl"] });
    },
    onError: (e) => melden(e instanceof Error ? e.message : String(e), "fehler"),
  });
  const st = d?.steuerung;

  return (
    <Karte className="min-w-0 flex flex-col" data-testid="gelernt">
      <div className="flex items-center gap-2 flex-wrap px-4 sm:px-5 py-3 border-b border-rand">
        <Knopf klein variante="geist" icon="zurueck" onClick={onZurueck} data-testid="gelernt-zurueck">Scans</Knopf>
        <h2 className="m-0 text-base font-semibold grow">Gelernte Zuordnungen</h2>
        <Knopf klein variante="geist" icon="hilfe" onClick={() => setErklaerung((x) => !x)} aria-expanded={erklaerung}>Was ist das?</Knopf>
      </div>
      {erklaerung || (d && !d.eintraege.length && !suche && !art && !quelle) ? (
        <div className="px-4 sm:px-5 py-3 border-b border-rand text-sm flex flex-col gap-1.5" data-testid="gelernt-erklaerung">
          <p className="m-0">Die Texterkennung lernt aus Ihren Korrekturen. Wenn Sie beim Zuordnen eine Zeile einem anderen
            Laborwert zuordnen, einen falsch gelesenen Namen verbessern oder einen Wert von Hand ergänzen, merkt sich EPM die
            Bezeichnung auf dem Befund – für dieses Labor und allgemein.</p>
          <p className="m-0">Beim nächsten Befund schlägt EPM dann selbst so vor. Ab {d?.schwelle ?? 2} Bestätigungen gilt eine
            Zuordnung als sicher und ist vorgewählt, vorher steht sie nur als Vorschlag mit „gelernt?“ da. In die Akte kommt
            weiterhin nichts, ohne dass Sie es prüfen und übernehmen.</p>
          <p className="m-0">Gespeichert werden nur Bezeichnungen (z. B. „Harnstoff-N → Harnstoff“), keine Werte und keine
            Angaben zu Patienten. Stimmt eine Zuordnung nicht, löschen Sie sie oder wählen „Sperren“: Dann ordnet EPM diese
            Bezeichnung nie wieder so zu. Alles bleibt auf dem Server; nichts geht ins Internet.</p>
        </div>
      ) : null}
      <div className="px-4 sm:px-5 py-3 border-b border-rand text-sm flex flex-col gap-1" data-testid="gelernt-korrigieren">
        <strong className="font-semibold">Falsches korrigieren</strong>
        <span>Beim Zuordnen: bei einer falschen Zeile auf <strong>Falsch erkannt</strong> tippen und den Grund wählen; fehlt ein
          Wert, mit <strong>Bereich markieren</strong> einen Rahmen um die richtigen Zeilen im Bild ziehen. Hier: eine falsche
          Zuordnung <strong>sperren</strong> (nie wieder so) oder <strong>löschen</strong> (darf neu gelernt werden).
          „Nicht auswerten“ heißt: Diese Zeile lässt EPM bei diesem Labor weg – löschen, wenn sie doch ein Wert ist.</span>
      </div>
      {st ? (
        <div className="flex items-center gap-x-4 gap-y-2 flex-wrap px-4 sm:px-5 py-2.5 border-b border-rand text-sm" data-testid="gelernt-steuerung">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={st.pausiert} disabled={!st.darf_steuern || steuern.isPending}
              onChange={(e) => steuern.mutate({ pausiert: e.target.checked })} data-testid="lernen-pausieren" />
            Lernen pausieren
          </label>
          <label className="flex items-center gap-2">
            Sicher ab
            <Auswahl value={String(st.schwelle)} disabled={!st.darf_steuern || steuern.isPending} aria-label="Sicher ab Bestätigungen"
              className="w-auto" onChange={(e) => steuern.mutate({ schwelle: Number(e.target.value) })} data-testid="lernen-schwelle">
              <option value="1">1 Bestätigung</option><option value="2">2 Bestätigungen</option><option value="3">3 Bestätigungen</option>
            </Auswahl>
          </label>
          <span className="text-xs gedaempft grow">
            {st.pausiert ? "Pausiert: Neues wird nicht gelernt, Gelerntes weiter genutzt. " : ""}
            {st.darf_steuern ? "Gilt für alle." : "Ändern darf, wer Vorlagen pflegt."}
            {st.geaendert_von ? ` Zuletzt geändert von ${st.geaendert_von} am ${datum(st.geaendert_am)}.` : ""}
          </span>
        </div>
      ) : null}
      <div className="flex items-center gap-2 flex-wrap px-4 sm:px-5 py-2.5 border-b border-rand">
        <label className="relative block grow min-w-[12rem]">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
          <input className="inp pl-[2.125rem]" type="search" aria-label="Gelernte Zuordnungen durchsuchen" placeholder="Bezeichnung, Ziel, Labor"
            value={suche} onChange={(e) => setSuche(e.target.value)} />
        </label>
        <Auswahl value={art} onChange={(e) => setArt(e.target.value)} aria-label="Art" className="w-auto">
          <option value="">alle Arten</option>
          {Object.entries(ARTEN_NAMEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Auswahl>
        <Auswahl value={quelle} onChange={(e) => setQuelle(e.target.value)} aria-label="Labor" className="w-auto max-w-[16rem]">
          <option value="">alle Labore</option>
          <option value="allgemein">allgemein (alle Labore)</option>
          {(d?.quellen ?? []).map((q) => <option key={q.quelle} value={q.quelle}>{q.name}</option>)}
        </Auswahl>
      </div>
      <Fehleranzeige fehler={liste.error ?? aendern.error} />
      {liste.isLoading ? <Laden /> : (
        <div className="overflow-x-auto">
          <table className="tabelle text-sm" data-testid="gelernt-liste">
            <thead><tr>
              <th className="th">Auf dem Befund</th><th className="th">wird zu</th><th className="th">Labor</th>
              <th className="th">bestätigt</th><th className="th">zuletzt</th><th className="th"><span className="sr-only">Aktionen</span></th>
            </tr></thead>
            <tbody>
              {(d?.eintraege ?? []).map((e) => (
                <tr key={e.id} className={cx(e.gesperrt && "opacity-60")} data-testid="gelernt-zeile">
                  <td className="td">
                    <span className="font-medium">{e.erkannt}</span>
                    <span className="block text-xs gedaempft">{e.art_name}{e.lesefehler ? " · Lesefehler korrigiert" : ""}</span>
                  </td>
                  <td className="td">{e.ziel}</td>
                  <td className="td">{e.quelle_name}</td>
                  <td className="td whitespace-nowrap">
                    <span className="num">{zahl(e.bestaetigt)}×</span>{" "}
                    {e.gesperrt ? <Chip art="fehler">gesperrt</Chip> : e.sicher ? <Chip art="ok">sicher</Chip> : <Chip art="warn">Vorschlag</Chip>}
                  </td>
                  <td className="td text-xs gedaempft whitespace-nowrap">{datum(e.zuletzt_am)}{e.zuletzt_von ? ` · ${e.zuletzt_von}` : ""}</td>
                  <td className="td whitespace-nowrap text-right">
                    {darf ? (
                      <>
                        <Knopf klein variante="geist" onClick={() => aendern.mutate({ e, gesperrt: !e.gesperrt })}
                          title={e.gesperrt ? "wieder zulassen" : "nie wieder so zuordnen"} data-testid="gelernt-sperren">
                          {e.gesperrt ? "Entsperren" : "Sperren"}</Knopf>
                        <Knopf klein variante="geist" icon="x" aria-label={`„${e.erkannt}“ löschen`} onClick={() => setWeg(e)}
                          data-testid="gelernt-loeschen" />
                      </>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {d && !d.eintraege.length ? <div className="p-4"><Leer>{suche || art || quelle ? "Kein Treffer." : "Noch nichts gelernt."}</Leer></div> : null}
          {d && !darf ? <div className="px-4 pb-3"><Meldung art="info">Mit einem Testzugang nur ansehen – das Gelernte gilt für alle.</Meldung></div> : null}
        </div>
      )}
      <Bestaetigen offen={!!weg} onOffen={(o) => { if (!o) setWeg(null); }} titel="Gelernte Zuordnung löschen?"
        text={weg ? `„${weg.erkannt}“ → ${weg.ziel} (${weg.quelle_name}). Kommt die Bezeichnung wieder vor, wird sie wieder wie früher erkannt und kann erneut gelernt werden. Soll sie nie wieder so zugeordnet werden, stattdessen „Sperren“ wählen.` : ""}
        knopf="Löschen" laedt={loeschen.isPending} onJa={() => weg && loeschen.mutate(weg)} />
    </Karte>
  );
}
