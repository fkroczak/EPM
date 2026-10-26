/**
 * Verwaltung › Fälle und Abrechnung (Regeneration Clinic, Anforderung vom 26.10.2026): Stammdaten der Fälle.
 *
 * - Leistungskatalog mit Preisen (auch per CSV) – Grundlage der Rechnungspositionen
 * - Kostenträgertypen mit Paketregel: welche Dokumente ein neuer Fall automatisch bekommt
 * - Kooperationspartner
 * - Unterschriftsberechtigte mit Benutzerkonto und Zertifikat für die elektronische Signatur
 *
 * Nichts wird gelöscht, nur ausgeblendet – bestehende Fälle und Rechnungen behalten ihren Bezug.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, alle, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, eingabeZahl, zahl } from "@/lib/format";
import type { Kooperationspartner, Kostentraegertyp, Leistung, PaketOption, Unterzeichner } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Seitenkopf, Textfeld, cx }
  from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Reiter, ReiterInhalt, useReiter } from "@/components/ui/reiter";
import { Icon } from "@/components/ui/icon";
import { Bestaetigen } from "@/components/Bestaetigen";
import { ZertifikatDialog } from "@/components/ZertifikatDialog";

const REITER = ["leistungen", "kostentraeger", "partner", "unterschriften"] as const;
type ReiterWert = (typeof REITER)[number];

function geld(wert: number | string | null | undefined) {
  return wert === null || wert === undefined || wert === "" ? "—" : `${zahl(wert, 2)} €`;
}
function zahlText(wert: number | string | null | undefined) {
  return wert === null || wert === undefined || wert === "" ? "" : String(wert).replace(".", ",");
}

/** Gleicher Schlüssel wie in der Akte (``useStamm``): Änderungen hier aktualisieren auch die Auswahl dort */
function useListe<T>(pfad: string) {
  return useQuery({ queryKey: ["faelle-stamm", pfad], queryFn: () => api<T[]>(pfad) });
}

/** Speichern (neu oder ändern) und Ein-/Ausblenden einer Stammdaten-Liste */
function useStammSpeichern<T extends { id: number }>(pfad: string, onFertig: () => void) {
  const qc = useQueryClient();
  const melden = useHinweis();
  return useMutation({
    mutationFn: ({ id, body }: { id: number | null; body: Record<string, unknown> }) =>
      id ? api<T>(`${pfad}${id}/`, { method: "PATCH", body }) : api<T>(pfad, { body }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["faelle-stamm"] }); melden("Gespeichert."); onFertig(); },
  });
}
function useUmschalten(pfad: string) {
  const qc = useQueryClient();
  const melden = useHinweis();
  return useMutation({
    mutationFn: (e: { id: number; aktiv: boolean }) => api(`${pfad}${e.id}/`, { method: "PATCH", body: { aktiv: !e.aktiv } }),
    onSuccess: (_d, e) => { void qc.invalidateQueries({ queryKey: ["faelle-stamm"] }); melden(e.aktiv ? "Ausgeblendet." : "Wieder eingeblendet."); },
    onError: (e) => melden(e.message, "fehler"),
  });
}

function Tabelle({ testid, kopf, children }: { testid: string; kopf: ReactNode; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="tabelle w-full text-sm" data-testid={testid}>
        <thead><tr>{kopf}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Aktionen({ aktiv, onBearbeiten, onUmschalten, children }: { aktiv: boolean; onBearbeiten: () => void; onUmschalten: () => void; children?: ReactNode }) {
  return (
    <td className="td text-right whitespace-nowrap">
      {children}
      <Knopf klein onClick={onBearbeiten}>Bearbeiten</Knopf>{" "}
      <Knopf klein onClick={onUmschalten}>{aktiv ? "Ausblenden" : "Einblenden"}</Knopf>
    </td>
  );
}

function Name({ text, aktiv, unter }: { text: ReactNode; aktiv: boolean; unter?: ReactNode }) {
  return (
    <td className="td break-words min-w-[12rem]">
      <span>{text}</span>{!aktiv ? <Chip className="ml-2">ausgeblendet</Chip> : null}
      {unter ? <span className="block text-xs gedaempft">{unter}</span> : null}
    </td>
  );
}

// ================================================================= Leistungskatalog
function LeistungDialog({ eintrag, onZu }: { eintrag: Leistung | "neu" | null; onZu: () => void }) {
  const vorhanden = eintrag && eintrag !== "neu" ? eintrag : null;
  const leer = { code: "", bezeichnung: "", bezeichnung_lv: "", bezeichnung_en: "", gruppe: "", einheit: "Stück", preis: "", ust_satz: "0" };
  const [f, setF] = useState(leer);
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (eintrag && gesetzt !== eintrag) {
    setGesetzt(eintrag);
    setF(vorhanden ? { code: vorhanden.code, bezeichnung: vorhanden.bezeichnung, bezeichnung_lv: vorhanden.bezeichnung_lv,
      bezeichnung_en: vorhanden.bezeichnung_en, gruppe: vorhanden.gruppe, einheit: vorhanden.einheit,
      preis: zahlText(vorhanden.preis), ust_satz: zahlText(vorhanden.ust_satz) } : leer);
  }
  const speichern = useStammSpeichern<Leistung>("leistungen/", onZu);
  const [lokal, setLokal] = useState<Feldfehler>({});
  const senden = () => {
    const preis = eingabeZahl(f.preis), ust = eingabeZahl(f.ust_satz || "0");
    const fehler: Feldfehler = {};
    if (!preis || preis === "ungueltig") fehler.preis = "Bitte einen Preis angeben, z. B. 120,00.";
    if (!ust || ust === "ungueltig") fehler.ust_satz = "Bitte eine Zahl angeben.";
    if (Object.keys(fehler).length) { speichern.reset(); setLokal(fehler); return; }
    setLokal({});
    speichern.mutate({ id: vorhanden?.id ?? null, body: { code: f.code.trim(), bezeichnung: f.bezeichnung.trim(),
      bezeichnung_lv: f.bezeichnung_lv.trim(), bezeichnung_en: f.bezeichnung_en.trim(), gruppe: f.gruppe.trim(),
      einheit: f.einheit.trim(), preis, ust_satz: ust } });
  };
  const { reset } = speichern;
  useEffect(() => { if (eintrag) { reset(); setLokal({}); } }, [eintrag, reset]);
  const e: Feldfehler = { ...(speichern.error instanceof ApiFehler ? speichern.error.felder : {}), ...lokal };
  const setz = (k: keyof typeof f) => (ev: { target: { value: string } }) => setF((a) => ({ ...a, [k]: ev.target.value }));
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} breite={640}
      titel={vorhanden ? `Leistung ${vorhanden.code}` : "Neue Leistung"}
      beschreibung="Eine Preisänderung gilt für neue Rechnungspositionen; bestehende behalten ihren Preis."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!f.code.trim() || !f.bezeichnung.trim()} onClick={senden}
          data-testid="leistung-speichern">Speichern</Knopf></>}>
      <div className="grid gap-3 sm:grid-cols-3" data-testid="leistung-formular">
        <Feld label="Leistungsnummer" fehler={e.code} pflicht>{(p) => <Eingabe {...p} className="num" value={f.code} maxLength={30} onChange={setz("code")} autoFocus />}</Feld>
        <Feld label="Gruppe" fehler={e.gruppe} hinweis="z. B. Operation, Unterbringung" className="sm:col-span-2">
          {(p) => <Eingabe {...p} value={f.gruppe} maxLength={80} onChange={setz("gruppe")} />}
        </Feld>
        <Feld label="Bezeichnung (Deutsch)" fehler={e.bezeichnung} pflicht className="sm:col-span-3">
          {(p) => <Eingabe {...p} value={f.bezeichnung} maxLength={300} onChange={setz("bezeichnung")} />}
        </Feld>
        <Feld label="Bezeichnung (Lettisch)" fehler={e.bezeichnung_lv} className="sm:col-span-3">
          {(p) => <Eingabe {...p} value={f.bezeichnung_lv} maxLength={300} onChange={setz("bezeichnung_lv")} />}
        </Feld>
        <Feld label="Bezeichnung (Englisch)" fehler={e.bezeichnung_en} className="sm:col-span-3">
          {(p) => <Eingabe {...p} value={f.bezeichnung_en} maxLength={300} onChange={setz("bezeichnung_en")} />}
        </Feld>
        <Feld label="Einheit" fehler={e.einheit}>{(p) => <Eingabe {...p} value={f.einheit} maxLength={30} onChange={setz("einheit")} />}</Feld>
        <Feld label="Preis (EUR)" fehler={e.preis} pflicht>{(p) => <Eingabe {...p} className="num" inputMode="decimal" value={f.preis} onChange={setz("preis")} />}</Feld>
        <Feld label="USt. %" fehler={e.ust_satz} hinweis="0 bei Heilbehandlung">
          {(p) => <Eingabe {...p} className="num" inputMode="decimal" value={f.ust_satz} onChange={setz("ust_satz")} />}
        </Feld>
      </div>
      {speichern.error && !Object.keys(e).length ? <Fehleranzeige fehler={speichern.error} /> : null}
    </Dialog>
  );
}

function LeistungenBereich() {
  const qc = useQueryClient();
  const [suche, setSuche] = useState("");
  const [nurAktive, setNurAktive] = useState(true);
  const [dialog, setDialog] = useState<Leistung | "neu" | null>(null);
  const liste = useListe<Leistung>("leistungen/");
  const umschalten = useUmschalten("leistungen/");
  const datei = useRef<HTMLInputElement>(null);
  const importieren = useMutation({
    mutationFn: (d: File) => {
      const form = new FormData();
      form.append("datei", d);
      return api<{ neu: number; geaendert: number }>("leistungen/import/", { form });
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["faelle-stamm"] }),
  });
  const importFehler = importieren.error instanceof ApiFehler
    ? ((importieren.error.daten as { datei?: string | string[] } | null)?.datei ?? importieren.error.message) : null;
  const begriff = suche.trim().toLowerCase();
  const gefiltert = (liste.data ?? []).filter((l) => (!nurAktive || l.aktiv)
    && (!begriff || `${l.code} ${l.bezeichnung} ${l.bezeichnung_lv} ${l.bezeichnung_en} ${l.gruppe}`.toLowerCase().includes(begriff)));

  return (
    <Karte className="p-[1.375rem] flex flex-col gap-3">
      <KartenKopf titel="Leistungskatalog" unter="Leistungen mit Preis für die Rechnungen. Text und Preis werden beim Hinzufügen in die Position übernommen."
        rechts={<>
          <Eingabe type="search" aria-label="Leistungen durchsuchen" className="w-[13.75rem]" placeholder="Suchen …" value={suche}
            onChange={(e) => setSuche(e.target.value)} data-testid="leistungen-suche" />
          <label className="flex items-center gap-1.5 text-[0.8125rem]">
            <input type="checkbox" checked={nurAktive} onChange={(e) => setNurAktive(e.target.checked)} />nur aktive
          </label>
          <Knopf klein icon="hochladen" laedt={importieren.isPending} onClick={() => { importieren.reset(); datei.current?.click(); }}
            data-testid="leistungen-import">CSV importieren</Knopf>
          <Knopf klein variante="pri" icon="plus" onClick={() => setDialog("neu")} data-testid="leistung-neu">Leistung hinzufügen</Knopf>
        </>} />
      <input ref={datei} type="file" hidden accept=".csv,text/csv" aria-label="CSV-Datei wählen"
        onChange={(e) => { const d = e.target.files?.[0]; if (d) importieren.mutate(d); e.target.value = ""; }} />
      {importieren.data ? (
        <Meldung art="ok">CSV übernommen: {importieren.data.neu} neu, {importieren.data.geaendert} geändert.</Meldung>
      ) : null}
      {importFehler ? (
        <Meldung art="fehler">
          <span className="block font-medium">Die CSV wurde nicht übernommen – nichts wurde geändert.</span>
          {Array.isArray(importFehler)
            ? <ul className="m-0 mt-1 pl-4">{importFehler.map((t, i) => <li key={i}>{t}</li>)}</ul>
            : <span className="block">{importFehler}</span>}
        </Meldung>
      ) : null}
      <details className="text-[0.8125rem] gedaempft">
        <summary className="cursor-pointer">Aufbau der CSV-Datei</summary>
        <p className="m-0 mt-1">UTF-8, Semikolon als Trenner, erste Zeile:
          <code className="block mt-1 break-all">code;bezeichnung;bezeichnung_lv;bezeichnung_en;gruppe;einheit;preis;ust_satz</code>
          Bekannte Codes werden aktualisiert, neue angelegt. Enthält eine Zeile einen Fehler, wird nichts übernommen.</p>
      </details>
      {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
      {liste.isSuccess && !gefiltert.length ? <Leer>{liste.data.length ? "Keine passende Leistung." : "Noch keine Leistungen im Katalog."}</Leer> : null}
      {gefiltert.length ? (
        <Tabelle testid="leistungen" kopf={<><th className="th">Code</th><th className="th">Bezeichnung</th><th className="th">Gruppe</th><th className="th">Einheit</th><th className="th num text-right">Preis</th><th className="th num text-right">USt.</th><th className="th" /></>}>
          {gefiltert.map((l) => (
            <tr key={l.id} className={l.aktiv ? "" : "opacity-60"}>
              <td className="td num whitespace-nowrap">{l.code}</td>
              <Name text={l.bezeichnung} aktiv={l.aktiv} unter={[l.bezeichnung_lv, l.bezeichnung_en].filter(Boolean).join(" · ") || undefined} />
              <td className="td">{l.gruppe || "—"}</td>
              <td className="td">{l.einheit || "—"}</td>
              <td className="td num text-right whitespace-nowrap">{geld(l.preis)}</td>
              <td className="td num text-right">{zahl(l.ust_satz)} %</td>
              <Aktionen aktiv={l.aktiv} onBearbeiten={() => setDialog(l)} onUmschalten={() => umschalten.mutate(l)} />
            </tr>
          ))}
        </Tabelle>
      ) : null}
      <LeistungDialog eintrag={dialog} onZu={() => setDialog(null)} />
    </Karte>
  );
}

// ================================================================= Kostenträgertypen mit Paket
function PaketEditor({ paket, onPaket, optionen, fehler }: {
  paket: string[]; onPaket: (p: string[]) => void; optionen: PaketOption[]; fehler?: string;
}) {
  const [neu, setNeu] = useState("");
  const name = (w: string) => optionen.find((o) => o.wert === w)?.name ?? `${w} (nicht mehr verfügbar)`;
  const frei = optionen.filter((o) => !paket.includes(o.wert));
  const gruppen = [...new Set(frei.map((o) => o.gruppe))];
  const schieben = (i: number, um: number) => {
    const p = [...paket];
    [p[i], p[i + um]] = [p[i + um], p[i]];
    onPaket(p);
  };
  return (
    <div className="flex flex-col gap-2 min-w-0" data-testid="paket-editor">
      <span className="text-[0.8125rem] font-medium">Dokumentenpaket ({paket.length})</span>
      <span className="text-[0.8125rem] gedaempft">Diese Dokumente bekommt ein neuer Fall automatisch – in dieser Reihenfolge. Ist die
        Aufklärung zur Operation dabei, kommt der Zusatzbogen des Fachbereichs dazu.</span>
      {paket.length ? (
        <ol className="m-0 p-0 list-none flex flex-col gap-1">
          {paket.map((w, i) => (
            <li key={w} className="card border px-2.5 py-1.5 flex items-center gap-2 text-sm">
              <span className="num gedaempft w-6 text-right">{i + 1}.</span>
              <span className={cx("grow min-w-0 break-words", !optionen.some((o) => o.wert === w) && "text-fehler")}>{name(w)}</span>
              <Knopf klein variante="geist" icon="hoch" aria-label={`${name(w)} nach oben`} title="Nach oben" disabled={i === 0} onClick={() => schieben(i, -1)} />
              <Knopf klein variante="geist" icon="runter" aria-label={`${name(w)} nach unten`} title="Nach unten" disabled={i === paket.length - 1} onClick={() => schieben(i, 1)} />
              <Knopf klein variante="geist" icon="x" aria-label={`${name(w)} entfernen`} title="Entfernen" onClick={() => onPaket(paket.filter((x) => x !== w))} />
            </li>
          ))}
        </ol>
      ) : <Leer>Kein Dokument im Paket.</Leer>}
      <div className="flex items-end gap-2 flex-wrap">
        <Feld label="Dokument hinzufügen" className="grow min-w-[14rem]">
          {(p) => (
            <Auswahl {...p} value={neu} onChange={(e) => setNeu(e.target.value)} data-testid="paket-option">
              <option value="">— bitte wählen —</option>
              {gruppen.map((g) => (
                <optgroup key={g} label={g}>
                  {frei.filter((o) => o.gruppe === g).map((o) => <option key={o.wert} value={o.wert}>{o.name}</option>)}
                </optgroup>
              ))}
            </Auswahl>
          )}
        </Feld>
        <Knopf icon="plus" disabled={!neu} onClick={() => { onPaket([...paket, neu]); setNeu(""); }} data-testid="paket-hinzufuegen">Hinzufügen</Knopf>
      </div>
      {fehler ? <span className="fehlertext" role="alert">{fehler}</span> : null}
    </div>
  );
}

function KostentraegerDialog({ eintrag, onZu }: { eintrag: Kostentraegertyp | "neu" | null; onZu: () => void }) {
  const vorhanden = eintrag && eintrag !== "neu" ? eintrag : null;
  const optionen = useQuery({ queryKey: ["faelle-stamm", "kostentraegertypen/optionen/"],
    queryFn: () => api<PaketOption[]>("kostentraegertypen/optionen/"), enabled: !!eintrag });
  const leer = { kuerzel: "", name: "", land: "", beschreibung: "", reihenfolge: "0" };
  const [f, setF] = useState(leer);
  const [paket, setPaket] = useState<string[]>([]);
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (eintrag && gesetzt !== eintrag) {
    setGesetzt(eintrag);
    setF(vorhanden ? { kuerzel: vorhanden.kuerzel, name: vorhanden.name, land: vorhanden.land, beschreibung: vorhanden.beschreibung,
      reihenfolge: String(vorhanden.reihenfolge) } : leer);
    setPaket(vorhanden ? [...vorhanden.paket] : []);
  }
  const speichern = useStammSpeichern<Kostentraegertyp>("kostentraegertypen/", onZu);
  const { reset } = speichern;
  useEffect(() => { if (eintrag) reset(); }, [eintrag, reset]);
  const e: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const paketFehler = Object.entries(e).filter(([k]) => k === "paket" || k.startsWith("paket.")).map(([, v]) => v).join(" ");
  const setz = (k: keyof typeof f) => (ev: { target: { value: string } }) => setF((a) => ({ ...a, [k]: ev.target.value }));
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} breite={720}
      titel={vorhanden ? `Kostenträgertyp: ${vorhanden.name}` : "Neuer Kostenträgertyp"}
      beschreibung="Das Paket gilt für neue Fälle. Bestehende Fälle bekommen fehlende Dokumente über „Paket ergänzen“."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!f.kuerzel.trim() || !f.name.trim()} data-testid="kostentraeger-speichern"
          onClick={() => speichern.mutate({ id: vorhanden?.id ?? null, body: { kuerzel: f.kuerzel.trim(), name: f.name.trim(),
            land: f.land.trim(), beschreibung: f.beschreibung.trim(), reihenfolge: Number(f.reihenfolge) || 0, paket } })}>Speichern</Knopf></>}>
      <div className="grid gap-3 sm:grid-cols-3" data-testid="kostentraeger-formular">
        <Feld label="Name" fehler={e.name} pflicht className="sm:col-span-2">{(p) => <Eingabe {...p} value={f.name} maxLength={120} onChange={setz("name")} autoFocus />}</Feld>
        <Feld label="Kürzel" fehler={e.kuerzel} pflicht hinweis="Kleinbuchstaben, Ziffern, Bindestrich">
          {(p) => <Eingabe {...p} className="num" value={f.kuerzel} maxLength={20}
            onChange={(ev) => setF((a) => ({ ...a, kuerzel: ev.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") }))} />}
        </Feld>
        <Feld label="Land / Region" fehler={e.land} className="sm:col-span-2">{(p) => <Eingabe {...p} value={f.land} maxLength={60} onChange={setz("land")} />}</Feld>
        <Feld label="Reihenfolge" fehler={e.reihenfolge}>
          {(p) => <Eingabe {...p} className="num" inputMode="numeric" value={f.reihenfolge} maxLength={4}
            onChange={(ev) => setF((a) => ({ ...a, reihenfolge: ev.target.value.replace(/\D/g, "") }))} />}
        </Feld>
        <Feld label="Beschreibung" fehler={e.beschreibung} className="sm:col-span-3">
          {(p) => <Eingabe {...p} value={f.beschreibung} maxLength={300} onChange={setz("beschreibung")} />}
        </Feld>
      </div>
      {optionen.isPending ? <Laden /> : <Fehleranzeige fehler={optionen.error} />}
      {optionen.data ? <PaketEditor paket={paket} onPaket={setPaket} optionen={optionen.data} fehler={paketFehler || undefined} /> : null}
      {speichern.error && !Object.keys(e).length ? <Fehleranzeige fehler={speichern.error} /> : null}
    </Dialog>
  );
}

function KostentraegerBereich() {
  const [dialog, setDialog] = useState<Kostentraegertyp | "neu" | null>(null);
  const liste = useListe<Kostentraegertyp>("kostentraegertypen/");
  const umschalten = useUmschalten("kostentraegertypen/");
  const daten = liste.data ?? [];
  return (
    <Karte className="p-[1.375rem] flex flex-col gap-3">
      <KartenKopf titel="Kostenträgertypen" unter="Je Typ das Dokumentenpaket, das ein neuer Fall automatisch bekommt."
        rechts={<Knopf klein variante="pri" icon="plus" onClick={() => setDialog("neu")} data-testid="kostentraeger-neu">Typ hinzufügen</Knopf>} />
      {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
      {liste.isSuccess && !daten.length ? <Leer>Noch keine Kostenträgertypen.</Leer> : null}
      {daten.length ? (
        <Tabelle testid="kostentraegertypen" kopf={<><th className="th">Name</th><th className="th">Kürzel</th><th className="th">Land</th><th className="th num">Dokumente</th><th className="th" /></>}>
          {daten.map((t) => (
            <tr key={t.id} className={t.aktiv ? "" : "opacity-60"}>
              <Name text={t.name} aktiv={t.aktiv} unter={t.beschreibung || undefined} />
              <td className="td num">{t.kuerzel}</td>
              <td className="td">{t.land || "—"}</td>
              <td className="td num">{t.paket.length}</td>
              <Aktionen aktiv={t.aktiv} onBearbeiten={() => setDialog(t)} onUmschalten={() => umschalten.mutate(t)} />
            </tr>
          ))}
        </Tabelle>
      ) : null}
      <KostentraegerDialog eintrag={dialog} onZu={() => setDialog(null)} />
    </Karte>
  );
}

// ================================================================= Kooperationspartner
function PartnerDialog({ eintrag, onZu }: { eintrag: Kooperationspartner | "neu" | null; onZu: () => void }) {
  const vorhanden = eintrag && eintrag !== "neu" ? eintrag : null;
  const leer = { name: "", kurzname: "", anschrift: "", kontakt: "" };
  const [f, setF] = useState(leer);
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (eintrag && gesetzt !== eintrag) {
    setGesetzt(eintrag);
    setF(vorhanden ? { name: vorhanden.name, kurzname: vorhanden.kurzname, anschrift: vorhanden.anschrift, kontakt: vorhanden.kontakt } : leer);
  }
  const speichern = useStammSpeichern<Kooperationspartner>("kooperationspartner/", onZu);
  const { reset } = speichern;
  useEffect(() => { if (eintrag) reset(); }, [eintrag, reset]);
  const e: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const setz = (k: keyof typeof f) => (ev: { target: { value: string } }) => setF((a) => ({ ...a, [k]: ev.target.value }));
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} breite={560}
      titel={vorhanden ? `Kooperationspartner: ${vorhanden.name}` : "Neuer Kooperationspartner"}
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!f.name.trim()} data-testid="partner-speichern"
          onClick={() => speichern.mutate({ id: vorhanden?.id ?? null, body: { name: f.name.trim(), kurzname: f.kurzname.trim(),
            anschrift: f.anschrift, kontakt: f.kontakt.trim() } })}>Speichern</Knopf></>}>
      <div className="grid gap-3 sm:grid-cols-3" data-testid="partner-formular">
        <Feld label="Name" fehler={e.name} pflicht className="sm:col-span-2">{(p) => <Eingabe {...p} value={f.name} maxLength={150} onChange={setz("name")} autoFocus />}</Feld>
        <Feld label="Kurzname" fehler={e.kurzname}>{(p) => <Eingabe {...p} value={f.kurzname} maxLength={40} onChange={setz("kurzname")} />}</Feld>
        <Feld label="Anschrift" fehler={e.anschrift} className="sm:col-span-3">
          {(p) => <Textfeld {...p} rows={3} value={f.anschrift} onChange={setz("anschrift")} className="font-[inherit] leading-snug" />}
        </Feld>
        <Feld label="Kontakt" fehler={e.kontakt} hinweis="Ansprechpartner, Telefon, E-Mail" className="sm:col-span-3">
          {(p) => <Eingabe {...p} value={f.kontakt} maxLength={200} onChange={setz("kontakt")} />}
        </Feld>
      </div>
      {speichern.error && !Object.keys(e).length ? <Fehleranzeige fehler={speichern.error} /> : null}
    </Dialog>
  );
}

function PartnerBereich() {
  const [dialog, setDialog] = useState<Kooperationspartner | "neu" | null>(null);
  const liste = useListe<Kooperationspartner>("kooperationspartner/");
  const umschalten = useUmschalten("kooperationspartner/");
  const daten = liste.data ?? [];
  return (
    <Karte className="p-[1.375rem] flex flex-col gap-3">
      <KartenKopf titel="Kooperationspartner" unter="Zur Auswahl im Fall, z. B. Vermittler oder Partnerkliniken."
        rechts={<Knopf klein variante="pri" icon="plus" onClick={() => setDialog("neu")} data-testid="partner-neu">Partner hinzufügen</Knopf>} />
      {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
      {liste.isSuccess && !daten.length ? <Leer>Noch keine Kooperationspartner.</Leer> : null}
      {daten.length ? (
        <Tabelle testid="kooperationspartner" kopf={<><th className="th">Name</th><th className="th">Kurzname</th><th className="th">Kontakt</th><th className="th" /></>}>
          {daten.map((k) => (
            <tr key={k.id} className={k.aktiv ? "" : "opacity-60"}>
              <Name text={k.name} aktiv={k.aktiv} unter={k.anschrift ? k.anschrift.split("\n").join(", ") : undefined} />
              <td className="td">{k.kurzname || "—"}</td>
              <td className="td break-words">{k.kontakt || "—"}</td>
              <Aktionen aktiv={k.aktiv} onBearbeiten={() => setDialog(k)} onUmschalten={() => umschalten.mutate(k)} />
            </tr>
          ))}
        </Tabelle>
      ) : null}
      <PartnerDialog eintrag={dialog} onZu={() => setDialog(null)} />
    </Karte>
  );
}

// ================================================================= Unterschriftsberechtigte
function UnterzeichnerDialog({ eintrag, onZu }: { eintrag: Unterzeichner | "neu" | null; onZu: () => void }) {
  const { ich, darf } = useAuth();
  const vorhanden = eintrag && eintrag !== "neu" ? eintrag : null;
  const benutzer = useQuery({
    queryKey: ["benutzer", "unterzeichner"],
    queryFn: () => api<{ id: number; name: string }[]>("unterzeichner/konten/"),
    enabled: !!eintrag,
  });
  const leer = { name: "", funktion: "", benutzer: "", reihenfolge: "0" };
  const [f, setF] = useState(leer);
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (eintrag && gesetzt !== eintrag) {
    setGesetzt(eintrag);
    setF(vorhanden ? { name: vorhanden.name, funktion: vorhanden.funktion, benutzer: vorhanden.benutzer ? String(vorhanden.benutzer) : "",
      reihenfolge: String(vorhanden.reihenfolge) } : leer);
  }
  const speichern = useStammSpeichern<Unterzeichner>("unterzeichner/", onZu);
  const { reset } = speichern;
  useEffect(() => { if (eintrag) reset(); }, [eintrag, reset]);
  const e: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const setz = (k: keyof typeof f) => (ev: { target: { value: string } }) => setF((a) => ({ ...a, [k]: ev.target.value }));
  // Konten aus ``unterzeichner/konten/``; bis sie geladen sind, das eigene und das bisher verknüpfte
  const konten: { id: number; name: string }[] = benutzer.data
    ? [...benutzer.data, ...(vorhanden?.benutzer && !benutzer.data.some((b) => b.id === vorhanden.benutzer)
        ? [{ id: vorhanden.benutzer, name: vorhanden.benutzer_name ?? `Konto ${vorhanden.benutzer}` }] : [])]
    : [...(ich ? [{ id: ich.id, name: `${ich.anzeigename} (eigenes Konto)` }] : []),
      ...(vorhanden?.benutzer && vorhanden.benutzer !== ich?.id ? [{ id: vorhanden.benutzer, name: vorhanden.benutzer_name ?? `Konto ${vorhanden.benutzer}` }] : [])];
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} breite={560}
      titel={vorhanden ? `Unterschrift: ${vorhanden.name}` : "Neue unterschriftsberechtigte Person"}
      beschreibung="Elektronisch signieren kann nur das verknüpfte Benutzerkonto – mit dem eigenen Zertifikat."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!f.name.trim()} data-testid="unterzeichner-speichern"
          onClick={() => speichern.mutate({ id: vorhanden?.id ?? null, body: { name: f.name.trim(), funktion: f.funktion.trim(),
            benutzer: f.benutzer ? Number(f.benutzer) : null, reihenfolge: Number(f.reihenfolge) || 0 } })}>Speichern</Knopf></>}>
      <div className="grid gap-3 sm:grid-cols-3" data-testid="unterzeichner-formular">
        <Feld label="Name mit Titel" fehler={e.name} pflicht hinweis="z. B. Dr. med. Markus Gottwald" className="sm:col-span-3">
          {(p) => <Eingabe {...p} value={f.name} maxLength={150} onChange={setz("name")} autoFocus />}
        </Feld>
        <Feld label="Funktion" fehler={e.funktion} hinweis="z. B. Chefarzt" className="sm:col-span-2">
          {(p) => <Eingabe {...p} value={f.funktion} maxLength={150} onChange={setz("funktion")} />}
        </Feld>
        <Feld label="Reihenfolge" fehler={e.reihenfolge}>
          {(p) => <Eingabe {...p} className="num" inputMode="numeric" value={f.reihenfolge} maxLength={4}
            onChange={(ev) => setF((a) => ({ ...a, reihenfolge: ev.target.value.replace(/\D/g, "") }))} />}
        </Feld>
        <Feld label="Benutzerkonto" fehler={e.benutzer} className="sm:col-span-3"
          hinweis="Mit diesem Konto meldet sich die Person an und signiert.">
          {(p) => (
            <Auswahl {...p} value={f.benutzer} onChange={setz("benutzer")} data-testid="unterzeichner-benutzer">
              <option value="">— kein Konto —</option>
              {konten.map((k) => <option key={k.id} value={k.id}>{k.name}</option>)}
            </Auswahl>
          )}
        </Feld>
      </div>
      {speichern.error && !Object.keys(e).length ? <Fehleranzeige fehler={speichern.error} /> : null}
    </Dialog>
  );
}

function UnterschriftenBereich() {
  const { ich } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [dialog, setDialog] = useState<Unterzeichner | "neu" | null>(null);
  const [zertifikat, setZertifikat] = useState<Unterzeichner | null>(null);
  const [entfernen, setEntfernen] = useState<Unterzeichner | null>(null);
  const liste = useListe<Unterzeichner>("unterzeichner/");
  const umschalten = useUmschalten("unterzeichner/");
  const zertifikatWeg = useMutation({
    mutationFn: (u: Unterzeichner) => api(`unterzeichner/${u.id}/zertifikat/`, { method: "DELETE" }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["faelle-stamm"] }); melden("Zertifikat entfernt."); setEntfernen(null); },
  });
  const daten = liste.data ?? [];
  const abgelaufen = (u: Unterzeichner) => !!u.zertifikat_bis && new Date(u.zertifikat_bis) < new Date();
  return (
    <Karte className="p-[1.375rem] flex flex-col gap-3">
      <KartenKopf titel="Unterschriftsberechtigte" unter="Wer Dokumente der Fälle unterschreibt. Für die elektronische Signatur braucht die Person ein verknüpftes Benutzerkonto; ihr Zertifikat hinterlegt sie selbst (angemeldet mit diesem Konto)."
        rechts={<Knopf klein variante="pri" icon="plus" onClick={() => setDialog("neu")} data-testid="unterzeichner-neu">Person hinzufügen</Knopf>} />
      {liste.isPending ? <Laden /> : <Fehleranzeige fehler={liste.error} />}
      {liste.isSuccess && !daten.length ? <Leer>Noch keine unterschriftsberechtigten Personen.</Leer> : null}
      {daten.length ? (
        <Tabelle testid="unterzeichner" kopf={<><th className="th">Name</th><th className="th">Benutzerkonto</th><th className="th">Zertifikat</th><th className="th" /></>}>
          {daten.map((u) => (
            <tr key={u.id} className={u.aktiv ? "" : "opacity-60"}>
              <Name text={u.name} aktiv={u.aktiv} unter={u.funktion || undefined} />
              <td className="td">{u.benutzer_name || <span className="gedaempft">—</span>}</td>
              <td className="td min-w-[12rem]">
                {u.hat_zertifikat ? (
                  <span className="flex flex-col gap-0.5">
                    <span className="flex items-center gap-1.5 flex-wrap">
                      {abgelaufen(u) ? <Chip art="fehler">abgelaufen</Chip> : <Chip art="ok"><Icon name="schloss" groesse={12} />hinterlegt</Chip>}
                      {u.zertifikat_bis ? <span className="text-xs gedaempft num">bis {datum(u.zertifikat_bis)}</span> : null}
                    </span>
                    <span className="text-xs gedaempft break-all">{u.zertifikat_info}</span>
                  </span>
                ) : <span className="gedaempft">keins</span>}
              </td>
              <Aktionen aktiv={u.aktiv} onBearbeiten={() => setDialog(u)} onUmschalten={() => umschalten.mutate(u)}>
                {/* hinterlegen nur die Person selbst (mit dem verknüpften Konto) */}
                {u.benutzer && u.benutzer === ich?.id ? <><Knopf klein icon="hochladen" onClick={() => setZertifikat(u)} data-testid="zertifikat-hochladen">
                  {u.hat_zertifikat ? "Zertifikat ersetzen" : "Zertifikat"}</Knopf>{" "}</> : null}
                {u.hat_zertifikat ? <><Knopf klein variante="dng" onClick={() => { zertifikatWeg.reset(); setEntfernen(u); }}>Zertifikat entfernen</Knopf>{" "}</> : null}
              </Aktionen>
            </tr>
          ))}
        </Tabelle>
      ) : null}
      <UnterzeichnerDialog eintrag={dialog} onZu={() => setDialog(null)} />
      <ZertifikatDialog person={zertifikat} offen={!!zertifikat} onOffen={(o) => { if (!o) setZertifikat(null); }} />
      <Bestaetigen offen={!!entfernen} onOffen={(o) => { if (!o) setEntfernen(null); }} titel="Zertifikat entfernen" knopf="Entfernen"
        text={<>Das Zertifikat von {entfernen?.name} wird entfernt. Bis ein neues hinterlegt ist, kann die Person nicht elektronisch signieren.</>}
        laedt={zertifikatWeg.isPending} fehler={zertifikatWeg.error} onJa={() => entfernen && zertifikatWeg.mutate(entfernen)} />
    </Karte>
  );
}

// ================================================================= Seite
export function Abrechnung() {
  const [reiter, setReiter] = useReiter<ReiterWert>(REITER);
  return (
    <Seite pfad={[{ text: "Administration" }, { text: "Fälle und Abrechnung" }]}>
      <Seitenkopf titel="Fälle und Abrechnung"
        unter="Leistungskatalog, Dokumentenpakete je Kostenträger, Partner und Unterschriften. Nichts wird gelöscht, nur ausgeblendet." />
      <Reiter label="Bereich" wert={reiter} onWahl={setReiter} testid="abrechnung-reiter" eintraege={[
        { wert: "leistungen", text: "Leistungskatalog", testid: "reiter-leistungen" },
        { wert: "kostentraeger", text: "Kostenträgertypen", testid: "reiter-kostentraeger" },
        { wert: "partner", text: "Kooperationspartner", testid: "reiter-partner" },
        { wert: "unterschriften", text: "Unterschriftsberechtigte", testid: "reiter-unterschriften" },
      ]} />
      <ReiterInhalt testid={`abrechnung-${reiter}`}>
        {reiter === "leistungen" ? <LeistungenBereich />
          : reiter === "kostentraeger" ? <KostentraegerBereich />
          : reiter === "partner" ? <PartnerBereich />
          : <UnterschriftenBereich />}
      </ReiterInhalt>
    </Seite>
  );
}
