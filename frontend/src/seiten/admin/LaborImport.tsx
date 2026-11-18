/**
 * Vorlagen › Laborparameter: Export, Import und Übernahme aus den RGC-Vorlagen (Dreisprachigkeit, 18.11.2026).
 *
 * Import immer in zwei Schritten: erst die Vorschau (was ergänzt einen vorhandenen Parameter, was wäre neu, was ist
 * unklar), dann übernehmen – nur die angehakten Zeilen. Vorhandene Parameter ergänzt der Import nur um Englisch und
 * Lettisch (mit ID aus dem Export auch die übrigen Spalten); die Werte der Befunde bleiben am Parameter.
 */
import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { LABORGRUPPEN } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Knopf, Laden, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { DateiWahl } from "@/components/DateiWahl";
import { useHinweis } from "@/components/ui/hinweise";

export type ImportZeile = {
  nr: number;
  id?: number | null;
  gruppe: string;
  name: string;
  name_en: string;
  name_lv: string;
  kurzname?: string;
  einheit?: string;
  referenz_von?: string | null;
  referenz_bis?: string | null;
  suchbegriffe?: string;
  aktiv?: string | boolean | null;
  quellen?: string[];
  zeile?: string;
  status: "ergaenzt" | "vorhanden" | "neu" | "unklar";
  parameter: number | null;
  parameter_name: string;
  aenderungen: Record<string, [string, string]>;
};

const STATUS: Record<ImportZeile["status"], { text: string; art: "ok" | "akzent" | "warn" | "neutral" }> = {
  ergaenzt: { text: "ergänzt vorhandenen", art: "ok" },
  vorhanden: { text: "schon vorhanden", art: "neutral" },
  neu: { text: "neuer Parameter", art: "akzent" },
  unklar: { text: "unklar", art: "warn" },
};
const FELDNAMEN: Record<string, string> = {
  name: "Deutsch", name_en: "Englisch", name_lv: "Lettisch", gruppe: "Gruppe", kurzname: "Kurzname",
  einheit: "Einheit", referenz_von: "Referenz von", referenz_bis: "Referenz bis", suchbegriffe: "Suchbegriffe",
  aktiv: "aktiv",
};

/** Datei aus der API herunterladen (CSV) */
export async function herunterladen(pfad: string, name: string) {
  const blob = await api<Blob>(pfad, { alsBlob: true });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export function LaborImportDialog({ quelle, onZu }: { quelle: "datei" | "vorlagen" | null; onZu: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [datei, setDatei] = useState<File | null>(null);
  const [zeilen, setZeilen] = useState<ImportZeile[] | null>(null);
  const [gewaehlt, setGewaehlt] = useState<Set<number>>(new Set());
  const [filter, setFilter] = useState<"alle" | ImportZeile["status"]>("alle");
  const [geladen, setGeladen] = useState<string | null>(null);

  const setzeVorschau = (z: ImportZeile[]) => {
    setZeilen(z);
    // vorgewählt: nur, was vorhandene Parameter ergänzt – Neues erst nach Anhaken (Festlegung 18.11.2026)
    setGewaehlt(new Set(z.filter((x) => x.status === "ergaenzt").map((x) => x.nr)));
  };
  const vorschau = useMutation({
    mutationFn: async () => {
      if (quelle === "vorlagen") return api<{ zeilen: ImportZeile[] }>("laborparameter/aus-vorlagen/");
      const form = new FormData();
      form.append("datei", datei!);
      return api<{ zeilen: ImportZeile[] }>("laborparameter/import/", { form });
    },
    onSuccess: (d) => setzeVorschau(d.zeilen),
  });
  // RGC-Vorlagen: Vorschau gleich beim Öffnen
  if (quelle && geladen !== quelle) {
    setGeladen(quelle);
    setZeilen(null);
    setDatei(null);
    setFilter("alle");
    if (quelle === "vorlagen") vorschau.mutate();
  }
  if (!quelle && geladen) setGeladen(null);

  const uebernehmen = useMutation({
    mutationFn: () => api<{ ergaenzt: string[]; neu: string[]; unveraendert: number }>("laborparameter/import/", {
      body: { uebernehmen: true, zeilen: (zeilen ?? []).filter((z) => gewaehlt.has(z.nr)) },
    }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["laborparameter"] });
      melden(`Übernommen: ${r.ergaenzt.length} ergänzt, ${r.neu.length} neu angelegt.`);
      onZu();
    },
  });

  const anzahl = useMemo(() => {
    const a: Record<string, number> = { alle: zeilen?.length ?? 0 };
    for (const z of zeilen ?? []) a[z.status] = (a[z.status] ?? 0) + 1;
    return a;
  }, [zeilen]);
  const sichtbar = (zeilen ?? []).filter((z) => filter === "alle" || z.status === filter);
  const aendern = (nr: number, feld: keyof ImportZeile, wert: string) =>
    setZeilen((l) => (l ?? []).map((z) => (z.nr === nr ? { ...z, [feld]: wert } : z)));
  const umschalten = (nr: number, an: boolean) => setGewaehlt((g) => {
    const neu = new Set(g);
    if (an) neu.add(nr); else neu.delete(nr);
    return neu;
  });
  const alleSichtbaren = (an: boolean) => setGewaehlt((g) => {
    const neu = new Set(g);
    for (const z of sichtbar) if (z.status !== "vorhanden") { if (an) neu.add(z.nr); else neu.delete(z.nr); }
    return neu;
  });
  const fehlendDeutsch = (zeilen ?? []).some((z) => gewaehlt.has(z.nr) && !z.parameter && !z.name.trim());

  return (
    <Dialog offen={!!quelle} onOffen={(o) => { if (!o) onZu(); }} breite={1100}
      titel={quelle === "vorlagen" ? "Laborparameter aus den RGC-Vorlagen" : "Laborparameter importieren (CSV)"}
      beschreibung={quelle === "vorlagen"
        ? "Alle Ankreuzzeilen der Laboranforderungen und Laborprofile der Regeneration Clinic, zugeordnet über das Wörterbuch Deutsch · Englisch · Lettisch."
        : "Datei im Format des Exports (Semikolon, Kopfzeile id;gruppe;name_de;name_en;name_lv;…). Zuerst kommt eine Vorschau."}
      fuss={<>
        <Knopf onClick={onZu}>Abbrechen</Knopf>
        {zeilen ? (
          <Knopf variante="pri" laedt={uebernehmen.isPending} disabled={!gewaehlt.size || fehlendDeutsch}
            onClick={() => uebernehmen.mutate()} data-testid="labor-import-uebernehmen">
            {gewaehlt.size} {gewaehlt.size === 1 ? "Zeile" : "Zeilen"} übernehmen
          </Knopf>
        ) : quelle === "datei" ? (
          <Knopf variante="pri" disabled={!datei} laedt={vorschau.isPending} onClick={() => vorschau.mutate()}>Vorschau</Knopf>
        ) : null}
      </>}>
      {quelle === "datei" && !zeilen ? (
        <DateiWahl datei={datei} onDatei={setDatei} accept=".csv,text/csv" label="CSV-Datei" testid="labor-import-datei" />
      ) : null}
      {vorschau.isPending ? <Laden text="Vorschau wird erstellt …" /> : null}
      {vorschau.error ? <Meldung art="fehler">{vorschau.error.message}</Meldung> : null}
      {uebernehmen.error ? <Meldung art="fehler">{uebernehmen.error.message}</Meldung> : null}
      {zeilen ? <>
        <Meldung art="info">
          Werte hängen am Parameter, nicht am Namen: „Fosfors“ und „Phosphat“ sind derselbe Wert. Vorgewählt ist nur, was
          vorhandene Parameter ergänzt; neue Parameter erst nach Anhaken. Bei neuen und unklaren Zeilen lassen sich Namen und
          Gruppe hier korrigieren.
        </Meldung>
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter">
          {(["alle", "ergaenzt", "neu", "unklar", "vorhanden"] as const).map((f) => (
            <Knopf key={f} klein variante={filter === f ? "pri" : "sec"} onClick={() => setFilter(f)}>
              {f === "alle" ? "Alle" : STATUS[f].text} <span className="num opacity-80">({anzahl[f] ?? 0})</span>
            </Knopf>
          ))}
          <span className="grow" />
          <Knopf klein onClick={() => alleSichtbaren(true)}>Angezeigte anhaken</Knopf>
          <Knopf klein onClick={() => alleSichtbaren(false)}>Angezeigte abwählen</Knopf>
        </div>
        <div className="overflow-auto max-h-[55vh]">
          <table className="tabelle w-full" data-testid="labor-import-vorschau">
            <thead><tr><th /><th>Status</th><th>Deutsch</th><th>Englisch</th><th>Lettisch</th><th>Gruppe</th><th>Herkunft</th></tr></thead>
            <tbody>
              {sichtbar.map((z) => {
                const frei = !z.parameter;
                return (
                  <tr key={z.nr} className={z.status === "vorhanden" ? "opacity-60" : ""}>
                    <td><input type="checkbox" aria-label={`${z.name || z.name_lv} übernehmen`} disabled={z.status === "vorhanden"}
                      checked={gewaehlt.has(z.nr)} onChange={(e) => umschalten(z.nr, e.target.checked)} /></td>
                    <td><Chip art={STATUS[z.status].art}>{STATUS[z.status].text}</Chip>
                      {z.parameter_name && z.parameter_name !== z.name
                        ? <div className="text-xs gedaempft mt-0.5">→ {z.parameter_name}</div> : null}</td>
                    <td>{frei ? <Eingabe className="klein" aria-label="Deutsch" value={z.name} onChange={(e) => aendern(z.nr, "name", e.target.value)} />
                      : z.parameter_name}</td>
                    {(["name_en", "name_lv"] as const).map((f) => (
                      <td key={f}>
                        {frei ? <Eingabe className="klein" aria-label={FELDNAMEN[f]} value={z[f] ?? ""} onChange={(e) => aendern(z.nr, f, e.target.value)} />
                          : <>{z[f] || "—"}{z.aenderungen[f] ? <div className="text-xs gedaempft">bisher: {z.aenderungen[f][0] || "leer"}</div> : null}</>}
                      </td>
                    ))}
                    <td>{frei ? (
                      <Auswahl className="klein" aria-label="Gruppe" value={z.gruppe || "sonstiges"} onChange={(e) => aendern(z.nr, "gruppe", e.target.value)}>
                        {Object.entries(LABORGRUPPEN).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
                      </Auswahl>
                    ) : LABORGRUPPEN[z.gruppe] ?? "—"}
                      {Object.keys(z.aenderungen).filter((f) => !["name_en", "name_lv"].includes(f)).map((f) => (
                        <div key={f} className="text-xs gedaempft">{FELDNAMEN[f] ?? f}: {z.aenderungen[f][0] || "leer"} → {z.aenderungen[f][1]}</div>
                      ))}
                    </td>
                    <td className="text-xs gedaempft max-w-[16rem]">
                      {z.zeile && z.zeile !== z.name ? <div>„{z.zeile}“</div> : null}
                      {(z.quellen ?? []).join(", ")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {fehlendDeutsch ? <Meldung art="warn">Für neue Parameter bitte den deutschen Namen eintragen.</Meldung> : null}
      </> : null}
    </Dialog>
  );
}
