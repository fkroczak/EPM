/**
 * Vorlagen › Laborparameter und Diagnosen (Wünsche aus der Praxis vom 06.10.2026, F112 und F117).
 *
 * Beide Listen werden hier gepflegt und nur ausgeblendet, nie gelöscht – sonst verlören bereits erfasste
 * Befunde und Diagnosen ihren Bezug. Die Diagnoseliste wächst beim Eintragen in einer Akte von allein mit;
 * hier wird sie korrigiert.
 */
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { zahl } from "@/lib/format";
import { LABORGRUPPEN } from "@/lib/typen";
import type { Laborparameter } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Segmente }
  from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { useIch } from "@/lib/auth";
import { LaborImportDialog, herunterladen } from "./LaborImport";

// ================================================================= Laborparameter

/** Pseudo-Gruppe „ohne Referenzbereich“ (Entscheidung der Praxis 10.10.2026, F190) */
const OHNE_REFERENZ = "ohne_referenz";
/** Parameter, die für die Hinweise im Infusionsplan zählen (F187) – beim Nachtragen zuerst */
const FUER_PLAENE = ["Natrium", "Kalium", "Calcium", "Magnesium", "Phosphat", "Albumin", "Glucose", "Triglyceride",
  "Kupfer", "Zink", "Selen", "Mangan"];
const rangPlan = (p: Laborparameter) => {
  const i = FUER_PLAENE.indexOf(p.name);
  return i >= 0 ? i : p.gruppe === "vitamine" ? FUER_PLAENE.length : FUER_PLAENE.length + 1;
};

function ParameterDialog({ eintrag, gruppe, onZu }: {
  eintrag: Laborparameter | "neu" | null; gruppe: string; onZu: () => void;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const vorhanden = eintrag && eintrag !== "neu" ? eintrag : null;
  const [f, setF] = useState({ name: "", name_en: "", name_lv: "", kurzname: "", einheit: "", referenz_von: "", referenz_bis: "", gruppe, suchbegriffe: "" });
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (eintrag && gesetzt !== eintrag) {
    setGesetzt(eintrag);
    setF(vorhanden
      ? { name: vorhanden.name, name_en: vorhanden.name_en ?? "", name_lv: vorhanden.name_lv ?? "", kurzname: vorhanden.kurzname, einheit: vorhanden.einheit,
          referenz_von: vorhanden.referenz_von != null ? zahl(vorhanden.referenz_von) : "",
          referenz_bis: vorhanden.referenz_bis != null ? zahl(vorhanden.referenz_bis) : "", gruppe: vorhanden.gruppe,
          suchbegriffe: vorhanden.suchbegriffe ?? "" }
      : { name: "", name_en: "", name_lv: "", kurzname: "", einheit: "", referenz_von: "", referenz_bis: "", gruppe, suchbegriffe: "" });
  }
  const zahlOderNull = (t: string) => (t.trim() ? t.trim().replace(",", ".") : null);
  const speichern = useMutation({
    mutationFn: () => {
      const daten = { gruppe: f.gruppe, name: f.name.trim(), name_en: f.name_en.trim(), name_lv: f.name_lv.trim(), kurzname: f.kurzname.trim(), einheit: f.einheit.trim(),
        referenz_von: zahlOderNull(f.referenz_von), referenz_bis: zahlOderNull(f.referenz_bis), suchbegriffe: f.suchbegriffe };
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
        <Feld label="Name (Deutsch)" fehler={e.name} pflicht>{(p) => <Eingabe {...p} value={f.name} maxLength={150} onChange={setz("name")} autoFocus />}</Feld>
        <Feld label="Name (Englisch)" fehler={e.name_en}>{(p) => <Eingabe {...p} value={f.name_en} maxLength={150} onChange={setz("name_en")} />}</Feld>
        <Feld label="Name (Lettisch)" fehler={e.name_lv} hinweis="z. B. „Fosfors“ – derselbe Wert wie „Phosphat“">
          {(p) => <Eingabe {...p} value={f.name_lv} maxLength={150} onChange={setz("name_lv")} />}
        </Feld>
        <Feld label="Kurzname" hinweis="für enge Spalten, z. B. GPT" fehler={e.kurzname}>
          {(p) => <Eingabe {...p} value={f.kurzname} maxLength={60} onChange={setz("kurzname")} />}
        </Feld>
        <Feld label="Einheit" fehler={e.einheit}>{(p) => <Eingabe {...p} value={f.einheit} maxLength={30} onChange={setz("einheit")} />}</Feld>
        <div />
        <Feld label="Referenz von" fehler={e.referenz_von}>{(p) => <Eingabe {...p} className="num" inputMode="decimal" value={f.referenz_von} onChange={setz("referenz_von")} />}</Feld>
        <Feld label="Referenz bis" fehler={e.referenz_bis}>{(p) => <Eingabe {...p} className="num" inputMode="decimal" value={f.referenz_bis} onChange={setz("referenz_bis")} />}</Feld>
        <Feld label="Suchbegriffe für Scans" fehler={e.suchbegriffe} className="sm:col-span-2"
          hinweis="Weitere Schreibweisen auf Laborbefunden, durch Komma getrennt (z. B. „ALAT, SGPT“) – damit „Scans“ den Wert erkennt. Übliche Schreibweisen sind schon bekannt.">
          {(p) => <Eingabe {...p} value={f.suchbegriffe} maxLength={300} onChange={setz("suchbegriffe")} />}
        </Feld>
      </div>
      <Meldung art="info">
        Referenzbereiche sind freiwillig. Sind sie gesetzt, markiert EPM abweichende Werte im Befund.
      </Meldung>
      {speichern.error && !Object.keys(e).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

function LaborparameterBereich() {
  // ?labor=ohne_referenz (Link aus dem Plan-Editor) öffnet gleich die Liste zum Nachtragen
  const [params] = useSearchParams();
  const [gruppe, setGruppe] = useState(params.get("labor") === OHNE_REFERENZ ? OHNE_REFERENZ : "transaminasen");
  const [dialog, setDialog] = useState<Laborparameter | "neu" | null>(null);
  const [importQuelle, setImportQuelle] = useState<"datei" | "vorlagen" | null>(null);
  const ich = useIch();
  const qc = useQueryClient();
  const melden = useHinweis();
  const liste = useQuery({ queryKey: ["laborparameter", false], queryFn: () => api<Laborparameter[]>("laborparameter/") });
  const umschalten = useMutation({
    mutationFn: (p: Laborparameter) => api(`laborparameter/${p.id}/`, { method: "PATCH", body: { aktiv: !p.aktiv } }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["laborparameter"] }); melden("Gespeichert."); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const ohneReferenz = useMemo(() => (liste.data ?? []).filter((p) => p.aktiv && p.referenz_von == null && p.referenz_bis == null)
    .sort((a, b) => rangPlan(a) - rangPlan(b) || a.name.localeCompare(b.name, "de")), [liste.data]);
  const gefiltert = useMemo(() => (gruppe === OHNE_REFERENZ ? ohneReferenz : (liste.data ?? []).filter((p) => p.gruppe === gruppe)),
    [liste.data, gruppe, ohneReferenz]);
  const dialogGruppe = gruppe === OHNE_REFERENZ ? "transaminasen" : gruppe;

  return (
    <div className="grid gap-4 lg:grid-cols-[16.25rem_minmax(0,1fr)]">
      <Karte className="p-4 flex flex-col gap-1 h-fit">
        <h3 className="lbl m-0 mb-1">Gruppen</h3>
        {ohneReferenz.length ? (
          <button type="button" aria-current={gruppe === OHNE_REFERENZ ? "true" : undefined} data-testid="ohne-referenz"
            className={`w-full text-left bg-transparent border-0 rounded-md px-2.5 py-1.5 mb-1 cursor-pointer text-sm flex justify-between gap-2 text-warn font-medium ${gruppe === OHNE_REFERENZ ? "bg-akzent-weich" : "hover:bg-fein"}`}
            onClick={() => setGruppe(OHNE_REFERENZ)}>
            <span>Ohne Referenzbereich</span><span className="num">{ohneReferenz.length}</span>
          </button>
        ) : null}
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
        {/* Dreisprachigkeit (18.11.2026): Katalog als CSV, Import mit Vorschau, Parameter aus den RGC-Vorlagen */}
        <h3 className="lbl m-0 mt-3 mb-1">Deutsch · Englisch · Lettisch</h3>
        <Knopf klein icon="herunterladen" className="justify-start"
          onClick={() => herunterladen("laborparameter/export/", "laborparameter.csv").catch((er: Error) => melden(er.message, "fehler"))}>
          Exportieren (CSV)</Knopf>
        <Knopf klein icon="hochladen" className="justify-start" onClick={() => setImportQuelle("datei")}>Importieren (CSV)</Knopf>
        {ich.firma === "rg" ? <>
          <Knopf klein icon="vorlagen" className="justify-start" onClick={() => setImportQuelle("vorlagen")}
            data-testid="labor-aus-vorlagen">Aus RGC-Vorlagen übernehmen</Knopf>
          <Knopf klein icon="herunterladen" className="justify-start"
            onClick={() => herunterladen("laborparameter/aus-vorlagen/?als=csv", "laborparameter-aus-rgc-vorlagen.csv").catch((er: Error) => melden(er.message, "fehler"))}>
            RGC-Vorlagen exportieren (CSV)</Knopf>
        </> : null}
      </Karte>
      <Karte className="p-[1.375rem] flex flex-col gap-3">
        <KartenKopf titel={gruppe === OHNE_REFERENZ ? `${ohneReferenz.length} Laborwerte ohne Referenzbereich` : LABORGRUPPEN[gruppe]}
          unter={gruppe === OHNE_REFERENZ ? "Zuerst die Werte, die für die Hinweise im Infusionsplan zählen." : "Ausgeblendete Parameter erscheinen nicht in neuen Befunden."}
          rechts={gruppe === OHNE_REFERENZ ? null : <Knopf klein variante="pri" onClick={() => setDialog("neu")}>Parameter hinzufügen</Knopf>} />
        {gruppe === OHNE_REFERENZ ? (
          <Meldung art="info">Bitte den Referenzbereich vom eigenen Labor übernehmen (steht auf jedem Befund). Er gilt nur, wenn ein
            Befund keinen eigenen Bereich mitbringt, und ist die Grundlage für die Hinweise „außerhalb des Referenzbereichs“ im
            Infusionsplan. „Bearbeiten“ öffnet den Parameter.</Meldung>
        ) : null}
        {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
        {gefiltert.length === 0 && !liste.isPending ? <Leer>In dieser Gruppe gibt es noch keine Parameter.</Leer> : null}
        {gefiltert.length ? (
          <div className="overflow-x-auto">
            <table className="tabelle w-full" data-testid="laborparameter">
              <thead><tr><th>Name</th><th>Englisch</th><th>Lettisch</th><th>Kurz</th><th>Einheit</th><th>Referenz</th><th className="num">in Befunden</th><th /></tr></thead>
              <tbody>
                {gefiltert.map((p) => (
                  <tr key={p.id} className={p.aktiv ? "" : "opacity-60"}>
                    <td>{p.name}{!p.aktiv ? <Chip className="ml-2">ausgeblendet</Chip> : null}
                      {gruppe === OHNE_REFERENZ && rangPlan(p) <= FUER_PLAENE.length ? <Chip art="akzent" className="ml-2">Infusionsplan</Chip> : null}</td>
                    <td>{p.name_en || "—"}</td>
                    <td>{p.name_lv || "—"}</td>
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
      <ParameterDialog eintrag={dialog} gruppe={dialogGruppe} onZu={() => setDialog(null)} />
      <LaborImportDialog quelle={importQuelle} onZu={() => setImportQuelle(null)} />
    </div>
  );
}

// ================================================================= Diagnoseliste und OPS-Liste
/** Eine Liste „Bezeichnung + Code“ im Hintergrund: Diagnosen mit ICD-Code (F117) und Prozeduren mit OPS-Code (RGC,
 * 21.11.2026). Beide wachsen beim Eintragen in einer Akte von allein mit; hier werden sie korrigiert und ausgeblendet. */
type CodeEintrag = { id: number; bezeichnung: string; aktiv: boolean } & ({ icd_code: string } | { ops_code: string });
type CodeListe = {
  pfad: "diagnoseliste" | "opsliste"; feld: "icd_code" | "ops_code"; code: string; beispiel: string; name: string;
  titel: string; hinzufuegen: string; dialogHinweis?: string; testid: string;
  /** ICD groß, OPS klein (so schreibt es der OPS) */
  schreibweise: (text: string) => string;
};
const LISTEN: Record<"diagnosen" | "ops", CodeListe> = {
  diagnosen: { pfad: "diagnoseliste", feld: "icd_code", code: "ICD-Code", beispiel: "K91.2", name: "Diagnose",
    titel: "Diagnosen mit ICD-Code", hinzufuegen: "Diagnose hinzufügen", testid: "diagnoseliste-verwaltung",
    dialogHinweis: "Das Zusatzkennzeichen (G/V/Z/A) gehört zur einzelnen Diagnose in der Akte, nicht in die Liste.",
    schreibweise: (t) => t.toUpperCase() },
  ops: { pfad: "opsliste", feld: "ops_code", code: "OPS-Code", beispiel: "5-455.01", name: "Prozedur",
    titel: "Prozeduren mit OPS-Code", hinzufuegen: "Prozedur hinzufügen", testid: "opsliste-verwaltung",
    dialogHinweis: "Wächst beim Eintragen eines Eingriffs (Reiter „Eingriffe“ der Regeneration Clinic) mit.",
    schreibweise: (t) => t.toLowerCase() },
};
const codeVon = (l: CodeListe, d: CodeEintrag) => (d as Record<string, unknown>)[l.feld] as string;

function CodeEintragDialog({ l, eintrag, onZu }: { l: CodeListe; eintrag: CodeEintrag | "neu" | null; onZu: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const vorhanden = eintrag && eintrag !== "neu" ? eintrag : null;
  const [bezeichnung, setBezeichnung] = useState("");
  const [code, setCode] = useState("");
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (eintrag && gesetzt !== eintrag) {
    setGesetzt(eintrag);
    setBezeichnung(vorhanden?.bezeichnung ?? "");
    setCode(vorhanden ? codeVon(l, vorhanden) : "");
  }
  const speichern = useMutation({
    mutationFn: () => {
      const daten = { bezeichnung: bezeichnung.trim(), [l.feld]: l.schreibweise(code.trim()) };
      return vorhanden
        ? api(`${l.pfad}/${vorhanden.id}/`, { method: "PATCH", body: daten })
        : api(`${l.pfad}/`, { body: daten });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [l.pfad] });
      melden("Gespeichert.");
      onZu();
    },
  });
  const e: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} breite={520}
      titel={vorhanden ? `${l.name} bearbeiten` : `Neue ${l.name} in der Liste`}
      beschreibung={l.dialogHinweis}
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!bezeichnung.trim() || !code.trim()}
          onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <Feld label="Bezeichnung" fehler={e.bezeichnung} pflicht>
        {(p) => <Eingabe {...p} value={bezeichnung} maxLength={200} onChange={(ev) => setBezeichnung(ev.target.value)} autoFocus />}
      </Feld>
      <Feld label={l.code} fehler={e[l.feld]} hinweis={`z. B. ${l.beispiel}`} pflicht>
        {(p) => <Eingabe {...p} className="num w-[10rem]" value={code} maxLength={12}
          onChange={(ev) => setCode(l.schreibweise(ev.target.value))} />}
      </Feld>
      {speichern.error && !Object.keys(e).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

function CodeListeBereich({ l }: { l: CodeListe }) {
  const [suche, setSuche] = useState("");
  const [dialog, setDialog] = useState<CodeEintrag | "neu" | null>(null);
  const qc = useQueryClient();
  const melden = useHinweis();
  const liste = useQuery({ queryKey: [l.pfad, false], queryFn: () => api<CodeEintrag[]>(`${l.pfad}/`) });
  const umschalten = useMutation({
    mutationFn: (d: CodeEintrag) => api(`${l.pfad}/${d.id}/`, { method: "PATCH", body: { aktiv: !d.aktiv } }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: [l.pfad] }); melden("Gespeichert."); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const gefiltert = (liste.data ?? []).filter((d) =>
    !suche.trim() || `${d.bezeichnung} ${codeVon(l, d)}`.toLowerCase().includes(suche.trim().toLowerCase()));

  return (
    <Karte className="p-[1.375rem] flex flex-col gap-3">
      <KartenKopf titel={l.titel}
        unter="Wächst beim Eintragen in einer Akte von allein mit; hier wird sie korrigiert und ausgeblendet."
        rechts={<>
          <Eingabe aria-label="Suchen" className="w-[13.75rem]" placeholder="Suchen …" value={suche}
            onChange={(e) => setSuche(e.target.value)} />
          <Knopf klein variante="pri" onClick={() => setDialog("neu")}>{l.hinzufuegen}</Knopf>
        </>} />
      {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
      {gefiltert.length === 0 && !liste.isPending ? <Leer>Keine Einträge.</Leer> : null}
      {gefiltert.length ? (
        <div className="overflow-x-auto">
          <table className="tabelle w-full" data-testid={l.testid}>
            <thead><tr><th>{l.name}</th><th>{l.code.replace("-Code", "")}</th><th /></tr></thead>
            <tbody>
              {gefiltert.map((d) => (
                <tr key={d.id} className={d.aktiv ? "" : "opacity-60"}>
                  <td>{d.bezeichnung}{!d.aktiv ? <Chip className="ml-2">ausgeblendet</Chip> : null}</td>
                  <td className="num">{codeVon(l, d)}</td>
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
      <CodeEintragDialog l={l} eintrag={dialog} onZu={() => setDialog(null)} />
    </Karte>
  );
}

export function KatalogeBereich() {
  const [teil, setTeil] = useState<"labor" | "diagnosen" | "ops">("labor");
  // Hinweis „N Laborwerte ohne Referenzbereich“ (F190) steht in LaborparameterBereich
  return (
    <div className="flex flex-col gap-4">
      <Segmente label="Katalog" wert={teil} onWahl={setTeil} className="self-start"
        werte={[{ wert: "labor", text: "Laborparameter" }, { wert: "diagnosen", text: "Diagnosen" },
          { wert: "ops", text: "OPS (Eingriffe)" }]} />
      {teil === "labor" ? <LaborparameterBereich /> : <CodeListeBereich key={teil} l={LISTEN[teil]} />}
    </div>
  );
}
