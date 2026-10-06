/**
 * Vorlagen › Laborparameter und Diagnosen (Wünsche aus der Praxis vom 06.10.2026, F112 und F117).
 *
 * Beide Listen werden hier gepflegt und nur ausgeblendet, nie gelöscht – sonst verlören bereits erfasste
 * Befunde und Diagnosen ihren Bezug. Die Diagnoseliste wächst beim Eintragen in einer Akte von allein mit;
 * hier wird sie korrigiert.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { zahl } from "@/lib/format";
import { LABORGRUPPEN } from "@/lib/typen";
import type { Diagnosevorlage, Laborparameter } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Segmente }
  from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";

// ================================================================= Laborparameter
function ParameterDialog({ eintrag, gruppe, onZu }: {
  eintrag: Laborparameter | "neu" | null; gruppe: string; onZu: () => void;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const vorhanden = eintrag && eintrag !== "neu" ? eintrag : null;
  const [f, setF] = useState({ name: "", kurzname: "", einheit: "", referenz_von: "", referenz_bis: "", gruppe });
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (eintrag && gesetzt !== eintrag) {
    setGesetzt(eintrag);
    setF(vorhanden
      ? { name: vorhanden.name, kurzname: vorhanden.kurzname, einheit: vorhanden.einheit,
          referenz_von: vorhanden.referenz_von != null ? zahl(vorhanden.referenz_von) : "",
          referenz_bis: vorhanden.referenz_bis != null ? zahl(vorhanden.referenz_bis) : "", gruppe: vorhanden.gruppe }
      : { name: "", kurzname: "", einheit: "", referenz_von: "", referenz_bis: "", gruppe });
  }
  const zahlOderNull = (t: string) => (t.trim() ? t.trim().replace(",", ".") : null);
  const speichern = useMutation({
    mutationFn: () => {
      const daten = { gruppe: f.gruppe, name: f.name.trim(), kurzname: f.kurzname.trim(), einheit: f.einheit.trim(),
        referenz_von: zahlOderNull(f.referenz_von), referenz_bis: zahlOderNull(f.referenz_bis) };
      return vorhanden
        ? api(`laborparameter/${vorhanden.id}/`, { method: "PATCH", body: daten })
        : api("laborparameter/", { body: daten });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["laborparameter"] });
      melden("Gespeichert.");
      onZu();
    },
  });
  const e: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const setz = (k: keyof typeof f) => (ev: { target: { value: string } }) => setF((a) => ({ ...a, [k]: ev.target.value }));
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} breite={560}
      titel={vorhanden ? `Laborparameter: ${vorhanden.name}` : "Neuer Laborparameter"}
      beschreibung="Die Einheit wird in neuen Befunden vorbelegt und bleibt je Wert überschreibbar."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!f.name.trim()} onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Feld label="Gruppe" fehler={e.gruppe} className="sm:col-span-2">
          {(p) => (
            <Auswahl {...p} value={f.gruppe} onChange={setz("gruppe")}>
              {Object.entries(LABORGRUPPEN).map(([k, text]) => <option key={k} value={k}>{text}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Name" fehler={e.name} pflicht>{(p) => <Eingabe {...p} value={f.name} maxLength={150} onChange={setz("name")} autoFocus />}</Feld>
        <Feld label="Kurzname" hinweis="für enge Spalten, z. B. GPT" fehler={e.kurzname}>
          {(p) => <Eingabe {...p} value={f.kurzname} maxLength={60} onChange={setz("kurzname")} />}
        </Feld>
        <Feld label="Einheit" fehler={e.einheit}>{(p) => <Eingabe {...p} value={f.einheit} maxLength={30} onChange={setz("einheit")} />}</Feld>
        <div />
        <Feld label="Referenz von" fehler={e.referenz_von}>{(p) => <Eingabe {...p} className="num" inputMode="decimal" value={f.referenz_von} onChange={setz("referenz_von")} />}</Feld>
        <Feld label="Referenz bis" fehler={e.referenz_bis}>{(p) => <Eingabe {...p} className="num" inputMode="decimal" value={f.referenz_bis} onChange={setz("referenz_bis")} />}</Feld>
      </div>
      <Meldung art="info">
        Referenzbereiche sind freiwillig. Sind sie gesetzt, markiert EPM abweichende Werte im Befund.
      </Meldung>
      {speichern.error && !Object.keys(e).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

function LaborparameterBereich() {
  const [gruppe, setGruppe] = useState("transaminasen");
  const [dialog, setDialog] = useState<Laborparameter | "neu" | null>(null);
  const qc = useQueryClient();
  const melden = useHinweis();
  const liste = useQuery({ queryKey: ["laborparameter", false], queryFn: () => api<Laborparameter[]>("laborparameter/") });
  const umschalten = useMutation({
    mutationFn: (p: Laborparameter) => api(`laborparameter/${p.id}/`, { method: "PATCH", body: { aktiv: !p.aktiv } }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["laborparameter"] }); melden("Gespeichert."); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const gefiltert = useMemo(() => (liste.data ?? []).filter((p) => p.gruppe === gruppe), [liste.data, gruppe]);

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
      <Karte className="p-4 flex flex-col gap-1 h-fit">
        <h3 className="lbl m-0 mb-1">Gruppen</h3>
        {Object.entries(LABORGRUPPEN).map(([k, text]) => {
          const anzahl = (liste.data ?? []).filter((p) => p.gruppe === k).length;
          return (
            <button key={k} type="button" aria-current={k === gruppe ? "true" : undefined}
              className={`w-full text-left bg-transparent border-0 rounded-md px-2.5 py-1.5 cursor-pointer text-sm flex justify-between gap-2 ${k === gruppe ? "bg-akzent-weich" : "hover:bg-fein"}`}
              onClick={() => setGruppe(k)}>
              <span>{text}</span><span className="num gedaempft">{anzahl}</span>
            </button>
          );
        })}
      </Karte>
      <Karte className="p-[22px] flex flex-col gap-3">
        <KartenKopf titel={LABORGRUPPEN[gruppe]} unter="Ausgeblendete Parameter erscheinen nicht in neuen Befunden."
          rechts={<Knopf klein variante="pri" onClick={() => setDialog("neu")}>Parameter hinzufügen</Knopf>} />
        {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
        {gefiltert.length === 0 && !liste.isPending ? <Leer>In dieser Gruppe gibt es noch keine Parameter.</Leer> : null}
        {gefiltert.length ? (
          <div className="overflow-x-auto">
            <table className="tabelle w-full" data-testid="laborparameter">
              <thead><tr><th>Name</th><th>Kurz</th><th>Einheit</th><th>Referenz</th><th className="num">in Befunden</th><th /></tr></thead>
              <tbody>
                {gefiltert.map((p) => (
                  <tr key={p.id} className={p.aktiv ? "" : "opacity-60"}>
                    <td>{p.name}{!p.aktiv ? <Chip className="ml-2">ausgeblendet</Chip> : null}</td>
                    <td>{p.kurzname || "—"}</td>
                    <td>{p.einheit || "—"}</td>
                    <td className="num">
                      {p.referenz_von == null && p.referenz_bis == null ? "—"
                        : `${p.referenz_von != null ? zahl(p.referenz_von) : ""} – ${p.referenz_bis != null ? zahl(p.referenz_bis) : ""}`}
                    </td>
                    <td className="num">{p.in_befunden}</td>
                    <td className="text-right whitespace-nowrap">
                      <Knopf klein onClick={() => setDialog(p)}>Bearbeiten</Knopf>{" "}
                      <Knopf klein onClick={() => umschalten.mutate(p)}>{p.aktiv ? "Ausblenden" : "Einblenden"}</Knopf>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Karte>
      <ParameterDialog eintrag={dialog} gruppe={gruppe} onZu={() => setDialog(null)} />
    </div>
  );
}

// ================================================================= Diagnoseliste
function DiagnoseEintragDialog({ eintrag, onZu }: { eintrag: Diagnosevorlage | "neu" | null; onZu: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const vorhanden = eintrag && eintrag !== "neu" ? eintrag : null;
  const [bezeichnung, setBezeichnung] = useState("");
  const [icd, setIcd] = useState("");
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (eintrag && gesetzt !== eintrag) {
    setGesetzt(eintrag);
    setBezeichnung(vorhanden?.bezeichnung ?? "");
    setIcd(vorhanden?.icd_code ?? "");
  }
  const speichern = useMutation({
    mutationFn: () => {
      const daten = { bezeichnung: bezeichnung.trim(), icd_code: icd.trim().toUpperCase() };
      return vorhanden
        ? api(`diagnoseliste/${vorhanden.id}/`, { method: "PATCH", body: daten })
        : api("diagnoseliste/", { body: daten });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["diagnoseliste"] });
      melden("Gespeichert.");
      onZu();
    },
  });
  const e: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} breite={520}
      titel={vorhanden ? "Diagnose bearbeiten" : "Neue Diagnose in der Liste"}
      beschreibung="Das Zusatzkennzeichen (G/V/Z/A) gehört zur einzelnen Diagnose in der Akte, nicht in die Liste."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!bezeichnung.trim() || !icd.trim()}
          onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <Feld label="Bezeichnung" fehler={e.bezeichnung} pflicht>
        {(p) => <Eingabe {...p} value={bezeichnung} maxLength={200} onChange={(ev) => setBezeichnung(ev.target.value)} autoFocus />}
      </Feld>
      <Feld label="ICD-Code" fehler={e.icd_code} hinweis="z. B. K91.2" pflicht>
        {(p) => <Eingabe {...p} className="num w-[160px]" value={icd} maxLength={10}
          onChange={(ev) => setIcd(ev.target.value.toUpperCase())} />}
      </Feld>
      {speichern.error && !Object.keys(e).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

function DiagnosenBereich() {
  const [suche, setSuche] = useState("");
  const [dialog, setDialog] = useState<Diagnosevorlage | "neu" | null>(null);
  const qc = useQueryClient();
  const melden = useHinweis();
  const liste = useQuery({ queryKey: ["diagnoseliste", false], queryFn: () => api<Diagnosevorlage[]>("diagnoseliste/") });
  const umschalten = useMutation({
    mutationFn: (d: Diagnosevorlage) => api(`diagnoseliste/${d.id}/`, { method: "PATCH", body: { aktiv: !d.aktiv } }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["diagnoseliste"] }); melden("Gespeichert."); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const gefiltert = (liste.data ?? []).filter((d) =>
    !suche.trim() || `${d.bezeichnung} ${d.icd_code}`.toLowerCase().includes(suche.trim().toLowerCase()));

  return (
    <Karte className="p-[22px] flex flex-col gap-3">
      <KartenKopf titel="Diagnosen mit ICD-Code"
        unter="Wächst beim Eintragen in einer Akte von allein mit; hier wird sie korrigiert und ausgeblendet."
        rechts={<>
          <Eingabe aria-label="Suchen" className="w-[220px]" placeholder="Suchen …" value={suche}
            onChange={(e) => setSuche(e.target.value)} />
          <Knopf klein variante="pri" onClick={() => setDialog("neu")}>Diagnose hinzufügen</Knopf>
        </>} />
      {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
      {gefiltert.length === 0 && !liste.isPending ? <Leer>Keine Einträge.</Leer> : null}
      {gefiltert.length ? (
        <div className="overflow-x-auto">
          <table className="tabelle w-full" data-testid="diagnoseliste-verwaltung">
            <thead><tr><th>Diagnose</th><th>ICD</th><th /></tr></thead>
            <tbody>
              {gefiltert.map((d) => (
                <tr key={d.id} className={d.aktiv ? "" : "opacity-60"}>
                  <td>{d.bezeichnung}{!d.aktiv ? <Chip className="ml-2">ausgeblendet</Chip> : null}</td>
                  <td className="num">{d.icd_code}</td>
                  <td className="text-right whitespace-nowrap">
                    <Knopf klein onClick={() => setDialog(d)}>Bearbeiten</Knopf>{" "}
                    <Knopf klein onClick={() => umschalten.mutate(d)}>{d.aktiv ? "Ausblenden" : "Einblenden"}</Knopf>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <DiagnoseEintragDialog eintrag={dialog} onZu={() => setDialog(null)} />
    </Karte>
  );
}

export function KatalogeBereich() {
  const [teil, setTeil] = useState<"labor" | "diagnosen">("labor");
  return (
    <div className="flex flex-col gap-4">
      <Segmente label="Katalog" wert={teil} onWahl={setTeil} className="self-start"
        werte={[{ wert: "labor", text: "Laborparameter" }, { wert: "diagnosen", text: "Diagnosen" }]} />
      {teil === "labor" ? <LaborparameterBereich /> : <DiagnosenBereich />}
    </div>
  );
}
