/**
 * Reiter „Medikamente“ (Kundenwunsch 11.10.2026: „Medikamentenplan als neuer Punkt beim Patienten“).
 *
 * Aufbau wie der bundeseinheitliche Medikationsplan: Dauermedikation und Bedarfsmedikation mit Wirkstoff, Handelsname,
 * Stärke, Form, Dosierung morgens – mittags – abends – zur Nacht („1 – 0 – 1 – 0“), Einheit, Hinweisen und Grund. Am PC
 * eine Tabelle, am Telefon je Medikament eine Karte. Nicht mehr eingenommene Medikamente werden abgesetzt (mit Datum
 * und Grund), nie gelöscht – sie stehen unter „Abgesetzt“ und lassen sich wieder ansetzen. „?eintrag=<id>“ (aus
 * der Karteikarte) hebt das Medikament hervor.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { datum, eingabeDatum } from "@/lib/format";
import { DARREICHUNGSFORMEN, MEDIKAMENT_EINHEITEN } from "@/lib/typen";
import type { Medikament } from "@/lib/typen";
import { Chip, Eingabe, Feld, Karte, Knopf, Laden, Meldung, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { FirmaMarke } from "@/components/FirmenWahl";
import { PdfDialog } from "@/components/PdfDialog";
import { Bestaetigen } from "@/components/Bestaetigen";
import { useAkte } from "./Akte";
import { useWahl } from "./Aktenseite";

const FORMEN_ID = "medikament-formen";
const EINHEITEN_ID = "medikament-einheiten";
const DOSIS: { feld: "morgens" | "mittags" | "abends" | "nachts"; kurz: string; text: string }[] = [
  { feld: "morgens", kurz: "Mo", text: "morgens" }, { feld: "mittags", kurz: "Mi", text: "mittags" },
  { feld: "abends", kurz: "Ab", text: "abends" }, { feld: "nachts", kurz: "Zn", text: "zur Nacht" },
];

type Werte = Omit<Medikament, "id" | "patient" | "aktiv" | "abgesetzt_am" | "absetzgrund" | "reihenfolge" | "schema"
  | "dosierung" | "angelegt_am" | "angelegt_von_name" | "firma_kurz">;

const LEER: Werte = {
  wirkstoff: "", handelsname: "", staerke: "", darreichungsform: "", morgens: "", mittags: "", abends: "", nachts: "",
  dosierung_frei: "", einheit: "", bedarf: false, hinweise: "", grund: "", seit: null,
};

function useNeuLaden() {
  const qc = useQueryClient();
  const { patient } = useAkte();
  return () => {
    void qc.invalidateQueries({ queryKey: ["medikamente", patient.id] });
    // Zähler im Reiter und Karteikarte
    void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
  };
}

function MedikamentDialog({ medikament, offen, onOffen }: { medikament: Medikament | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [w, setW] = useState<Werte>(LEER);
  const [seit, setSeit] = useState("");
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${medikament?.id ?? "neu"}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setW(medikament ? { ...LEER, ...Object.fromEntries(Object.keys(LEER).map((k) => [k, medikament[k as keyof Werte]])) } as Werte : LEER);
    setSeit(medikament?.seit ? datum(medikament.seit) : "");
  }
  // geschlossen: beim nächsten Öffnen neu vorbelegen (sonst stünde das zuletzt gespeicherte Medikament noch drin)
  if (!offen && gesetzt) setGesetzt("");
  const setze = <K extends keyof Werte>(feld: K, wert: Werte[K]) => setW((alt) => ({ ...alt, [feld]: wert }));

  const speichern = useMutation({
    mutationFn: () => {
      let iso: string | null = null;
      if (seit.trim()) {
        iso = eingabeDatum(seit);
        if (!iso) throw new ApiFehler(400, "", null, { seit: "Bitte als TT.MM.JJJJ eingeben." });
      }
      const koerper = { ...w, patient: patient.id, seit: iso };
      return medikament
        ? api<Medikament>(`medikamente/${medikament.id}/`, { method: "PATCH", body: koerper })
        : api<Medikament>("medikamente/", { body: koerper });
    },
    onSuccess: () => {
      neuLaden();
      melden(medikament ? "Medikament geändert." : "Medikament eingetragen.");
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const schema = DOSIS.some((d) => w[d.feld].trim()) ? DOSIS.map((d) => w[d.feld].trim() || "0").join(" – ") : "";

  return (
    <Dialog offen={offen} onOffen={onOffen} breite={680} titel={medikament ? "Medikament ändern" : "Neues Medikament"}
      beschreibung="Wie im Medikationsplan: Wirkstoff, Stärke und Dosierung morgens – mittags – abends – zur Nacht."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!w.wirkstoff.trim()}
          onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Feld label="Wirkstoff" fehler={f.wirkstoff} pflicht>
          {(p) => <Eingabe {...p} value={w.wirkstoff} maxLength={200} placeholder="z. B. Pantoprazol"
            onChange={(e) => setze("wirkstoff", e.target.value)} />}
        </Feld>
        <Feld label="Handelsname" fehler={f.handelsname}>
          {(p) => <Eingabe {...p} value={w.handelsname} maxLength={200} placeholder="z. B. Pantozol"
            onChange={(e) => setze("handelsname", e.target.value)} />}
        </Feld>
        <Feld label="Stärke" fehler={f.staerke}>
          {(p) => <Eingabe {...p} value={w.staerke} maxLength={60} placeholder="z. B. 40 mg"
            onChange={(e) => setze("staerke", e.target.value)} />}
        </Feld>
        <Feld label="Darreichungsform" fehler={f.darreichungsform}>
          {(p) => <>
            <Eingabe {...p} list={FORMEN_ID} value={w.darreichungsform} maxLength={60} placeholder="z. B. Tablette"
              onChange={(e) => setze("darreichungsform", e.target.value)} />
            <datalist id={FORMEN_ID}>{DARREICHUNGSFORMEN.map((x) => <option key={x} value={x} />)}</datalist>
          </>}
        </Feld>
      </div>
      <fieldset className="m-0 p-0 border-0 flex flex-col gap-1.5" data-testid="medikament-dosierung">
        <legend className="text-[0.8125rem] font-medium mb-1.5">Dosierung</legend>
        <div className="grid grid-cols-4 gap-2 max-w-[22rem]">
          {DOSIS.map((d) => (
            <Feld key={d.feld} label={d.text} fehler={f[d.feld]}>
              {(p) => <Eingabe {...p} className="num text-center" inputMode="decimal" maxLength={10} placeholder="0"
                value={w[d.feld]} onChange={(e) => setze(d.feld, e.target.value)} />}
            </Feld>
          ))}
        </div>
        <span className="text-[0.8125rem] gedaempft">
          {schema ? <>Schema: <strong className="num">{schema}</strong></> : "z. B. 1, ½ oder 0 – leer bleibt leer."}
        </span>
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Feld label="Dosierung (frei)" fehler={f.dosierung_frei}
          hinweis="Wenn das Schema nicht passt, z. B. „1× wöchentlich montags“.">
          {(p) => <Eingabe {...p} value={w.dosierung_frei} maxLength={120}
            onChange={(e) => setze("dosierung_frei", e.target.value)} />}
        </Feld>
        <Feld label="Einheit" fehler={f.einheit}>
          {(p) => <>
            <Eingabe {...p} list={EINHEITEN_ID} value={w.einheit} maxLength={30} placeholder="z. B. Stück"
              onChange={(e) => setze("einheit", e.target.value)} />
            <datalist id={EINHEITEN_ID}>{MEDIKAMENT_EINHEITEN.map((x) => <option key={x} value={x} />)}</datalist>
          </>}
        </Feld>
      </div>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" checked={w.bedarf} onChange={(e) => setze("bedarf", e.target.checked)} />
        Bei Bedarf (steht im Plan unter „Bedarfsmedikation“)
      </label>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem]">
        <Feld label="Grund" fehler={f.grund} hinweis="Behandlungsgrund, z. B. Magenschutz">
          {(p) => <Eingabe {...p} value={w.grund} maxLength={200} onChange={(e) => setze("grund", e.target.value)} />}
        </Feld>
        <Feld label="seit" fehler={f.seit}>
          {(p) => <Eingabe {...p} className="num" value={seit} placeholder="TT.MM.JJJJ" onChange={(e) => setSeit(e.target.value)} />}
        </Feld>
      </div>
      <Feld label="Hinweise" fehler={f.hinweise} hinweis="z. B. „30 min vor dem Frühstück“">
        {(p) => <Eingabe {...p} value={w.hinweise} maxLength={300} onChange={(e) => setze("hinweise", e.target.value)} />}
      </Feld>
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

/** Dosierung kompakt: „1 – 0 – 1 – 0“, darunter die freie Dosierung */
function Dosierung({ m }: { m: Medikament }) {
  if (!m.schema && !m.dosierung_frei) return <span className="gedaempft">{m.bedarf ? "bei Bedarf" : "—"}</span>;
  return (
    <span className="flex flex-col gap-0.5">
      {m.schema ? <span className="num whitespace-nowrap font-medium" title="morgens – mittags – abends – zur Nacht">{m.schema}</span> : null}
      {m.dosierung_frei ? <span className="text-[0.8125rem]">{m.dosierung_frei}</span> : null}
    </span>
  );
}

/** Wirkstoff fett, Handelsname darunter; Firma, in der das Medikament erfasst wurde */
function Name({ m }: { m: Medikament }) {
  return (
    <span className="flex flex-col gap-0.5 min-w-0">
      <span className={cx("font-medium flex items-center gap-1.5 flex-wrap", !m.aktiv && "line-through decoration-gedaempft")}>
        {m.wirkstoff}<FirmaMarke kurz={m.firma_kurz} />
      </span>
      {m.handelsname ? <span className="text-[0.8125rem] gedaempft">{m.handelsname}</span> : null}
    </span>
  );
}

type Aktionen = { bearbeiten: boolean; onBearbeiten: (m: Medikament) => void; onAbsetzen: (m: Medikament) => void;
  onAnsetzen: (m: Medikament) => void; laedt: boolean };

function Knoepfe({ m, a }: { m: Medikament; a: Aktionen }) {
  if (!a.bearbeiten) return null;
  return (
    <span className="flex items-center gap-1 justify-end flex-wrap md:flex-nowrap">
      {m.aktiv ? <>
        <Knopf klein variante="geist" icon="stift" onClick={() => a.onBearbeiten(m)} aria-label={`${m.wirkstoff} bearbeiten`} title="Bearbeiten" />
        <Knopf klein variante="geist" onClick={() => a.onAbsetzen(m)} aria-label={`${m.wirkstoff} absetzen`}>Absetzen</Knopf>
      </> : (
        <Knopf klein laedt={a.laedt} onClick={() => a.onAnsetzen(m)} aria-label={`${m.wirkstoff} wieder ansetzen`}>Wieder ansetzen</Knopf>
      )}
    </span>
  );
}

/** Ein Abschnitt (Dauer-, Bedarfsmedikation, Abgesetzt): Tabelle ab 768 px, darunter Karten */
function Liste({ liste, wahl, a, abgesetzt, testid }: { liste: Medikament[]; wahl: string; a: Aktionen; abgesetzt?: boolean; testid: string }) {
  const markiert = useRef<HTMLElement | null>(null);
  useEffect(() => { markiert.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [wahl]);
  const merke = (m: Medikament) => (el: HTMLElement | null) => { if (String(m.id) === wahl && el && el.offsetParent) markiert.current = el; };
  return (
    <div data-testid={testid}>
      <div className="max-md:hidden overflow-x-auto">
        <table className="tabelle tabelle-fest">
          <thead>
            <tr>
              <th className="th pl-5">Wirkstoff / Handelsname</th>
              <th className="th">Stärke</th>
              <th className="th">Form</th>
              <th className="th whitespace-nowrap" title="morgens – mittags – abends – zur Nacht">Mo – Mi – Ab – Zn</th>
              <th className="th">Einheit</th>
              <th className="th">Hinweise</th>
              <th className="th">{abgesetzt ? "Abgesetzt" : "Grund"}</th>
              <th className="th pr-5"><span className="sr-only">Aktionen</span></th>
            </tr>
          </thead>
          <tbody>
            {liste.map((m) => (
              <tr key={m.id} ref={merke(m)} data-testid="medikament-zeile" className={cx(String(m.id) === wahl && "gewaehlt", !m.aktiv && "gedaempft")}>
                <td className="td pl-5 align-top"><Name m={m} /></td>
                <td className="td align-top whitespace-nowrap">{m.staerke || "—"}</td>
                <td className="td align-top">{m.darreichungsform || "—"}</td>
                <td className="td align-top"><Dosierung m={m} /></td>
                <td className="td align-top">{m.einheit || "—"}</td>
                <td className="td align-top text-[0.8125rem]">{m.hinweise || "—"}</td>
                <td className="td align-top text-[0.8125rem]">
                  {abgesetzt ? <>{datum(m.abgesetzt_am)}{m.absetzgrund ? <span className="block">{m.absetzgrund}</span> : null}</> : (m.grund || "—")}
                </td>
                <td className="td pr-5 align-top"><Knoepfe m={m} a={a} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="md:hidden m-0 p-0 list-none">
        {liste.map((m) => (
          <li key={m.id} ref={merke(m)} data-testid="medikament-karte"
            className={cx("px-3 py-3 border-t border-fein flex flex-col gap-1.5 min-w-0", String(m.id) === wahl && "bg-akzent-weich")}>
            <div className="flex items-start justify-between gap-2 min-w-0">
              <Name m={m} />
              <Dosierung m={m} />
            </div>
            <span className="text-[0.8125rem] text-text2 break-words">
              {[m.staerke, m.darreichungsform, m.einheit && `Einheit: ${m.einheit}`].filter(Boolean).join(" · ") || "—"}
            </span>
            {m.hinweise ? <span className="text-[0.8125rem] break-words">{m.hinweise}</span> : null}
            {abgesetzt ? (
              <span className="text-[0.8125rem] gedaempft break-words">abgesetzt am {datum(m.abgesetzt_am)}{m.absetzgrund ? ` · ${m.absetzgrund}` : ""}</span>
            ) : m.grund ? <span className="text-[0.8125rem] gedaempft break-words">Grund: {m.grund}</span> : null}
            <Knoepfe m={m} a={a} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Medikamente() {
  const { patient, bearbeiten } = useAkte();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [wahl] = useWahl("eintrag");
  const [dialog, setDialog] = useState<{ offen: boolean; medikament: Medikament | null }>({ offen: false, medikament: null });
  const [absetzen, setAbsetzen] = useState<Medikament | null>(null);
  const [absetzgrund, setAbsetzgrund] = useState("");
  const [abgesetztAn, setAbgesetzt] = useState(false);
  const [pdf, setPdf] = useState(false);

  const medikamente = useQuery({
    queryKey: ["medikamente", patient.id],
    queryFn: () => api<Medikament[]>(`medikamente/?patient=${patient.id}`),
  });
  const absetzenAusfuehren = useMutation({
    mutationFn: (m: Medikament) => api<Medikament>(`medikamente/${m.id}/absetzen/`, { body: { absetzgrund: absetzgrund.trim() } }),
    onSuccess: (m) => { neuLaden(); melden(`„${m.wirkstoff}“ abgesetzt.`); setAbsetzen(null); },
  });
  const ansetzen = useMutation({
    mutationFn: (m: Medikament) => api<Medikament>(`medikamente/${m.id}/ansetzen/`, { method: "POST" }),
    onSuccess: (m) => { neuLaden(); melden(`„${m.wirkstoff}“ wieder im Plan.`); },
    onError: (e) => melden(e.message, "fehler"),
  });

  const alle = medikamente.data ?? [];
  const dauer = alle.filter((m) => m.aktiv && !m.bedarf);
  const bedarf = alle.filter((m) => m.aktiv && m.bedarf);
  const abgesetzt = alle.filter((m) => !m.aktiv);
  // aus der Karteikarte auf ein abgesetztes Medikament gezeigt: „Abgesetzt“ gleich aufklappen
  const zeigeAbgesetzt = abgesetztAn || abgesetzt.some((m) => String(m.id) === wahl);
  const a: Aktionen = {
    bearbeiten, laedt: ansetzen.isPending,
    onBearbeiten: (m) => setDialog({ offen: true, medikament: m }),
    onAbsetzen: (m) => { absetzenAusfuehren.reset(); setAbsetzgrund(""); setAbsetzen(m); },
    onAnsetzen: (m) => ansetzen.mutate(m),
  };
  const kopf = (titel: string, anzahl: number) => (
    <h3 className="lbl m-0 px-5 max-md:px-3 pt-3 pb-2 text-[0.8125rem] flex items-center gap-2">{titel}{anzahl ? <Chip>{anzahl}</Chip> : null}</h3>
  );

  return (
    <>
      <Karte className="overflow-hidden min-w-0" data-testid="medikamente">
        <div className="px-5 max-md:px-3 pt-4 pb-2 flex items-center justify-between gap-3 flex-wrap">
          <h2 className="lbl m-0 text-[0.9375rem] flex items-center gap-2">
            Medikamentenplan{dauer.length + bedarf.length ? <Chip>{dauer.length + bedarf.length}</Chip> : null}
          </h2>
          <div className="flex items-center gap-2 flex-wrap">
            <Knopf icon="dokument" onClick={() => setPdf(true)} disabled={!alle.length}>Medikationsplan als PDF</Knopf>
            {bearbeiten ? <Knopf variante="pri" icon="plus" onClick={() => setDialog({ offen: true, medikament: null })}>Medikament</Knopf> : null}
          </div>
        </div>
        {medikamente.isPending ? <Laden /> : <>
          <section className="border-t border-rand">
            {kopf("Dauermedikation", dauer.length)}
            {dauer.length ? <Liste liste={dauer} wahl={wahl} a={a} testid="dauermedikation" />
              : <p className="m-0 px-5 max-md:px-3 pb-4 text-sm gedaempft">Keine Dauermedikation eingetragen.</p>}
          </section>
          <section className="border-t border-rand">
            {kopf("Bedarfsmedikation", bedarf.length)}
            {bedarf.length ? <Liste liste={bedarf} wahl={wahl} a={a} testid="bedarfsmedikation" />
              : <p className="m-0 px-5 max-md:px-3 pb-4 text-sm gedaempft">Keine Bedarfsmedikation eingetragen.</p>}
          </section>
          {abgesetzt.length ? (
            <section className="border-t border-rand">
              <button type="button" className="w-full text-left px-5 max-md:px-3 py-2.5 bg-transparent border-0 text-[0.8125rem] gedaempft cursor-pointer hover:bg-fein"
                aria-expanded={zeigeAbgesetzt} onClick={() => setAbgesetzt((b) => !b)} data-testid="abgesetzt-umschalten">
                {zeigeAbgesetzt ? "Abgesetzte ausblenden" : `Abgesetzt (${abgesetzt.length}) anzeigen`}
              </button>
              {zeigeAbgesetzt ? <Liste liste={abgesetzt} wahl={wahl} a={a} abgesetzt testid="abgesetzt" /> : null}
            </section>
          ) : null}
        </>}
      </Karte>
      {bearbeiten ? <Bestaetigen offen={!!absetzen} onOffen={(o) => { if (!o) setAbsetzen(null); }} titel="Medikament absetzen" knopf="Absetzen"
        text={<>„{absetzen?.wirkstoff}{absetzen?.staerke ? ` ${absetzen.staerke}` : ""}“ wird heute abgesetzt. Es bleibt unter „Abgesetzt“ sichtbar und lässt sich wieder ansetzen.</>}
        laedt={absetzenAusfuehren.isPending} fehler={absetzenAusfuehren.error} onJa={() => absetzen && absetzenAusfuehren.mutate(absetzen)}>
        <Feld label="Grund (freiwillig)">
          {(p) => <Eingabe {...p} value={absetzgrund} maxLength={200} placeholder="z. B. keine Beschwerden mehr"
            onChange={(e) => setAbsetzgrund(e.target.value)} />}
        </Feld>
      </Bestaetigen> : null}
      {bearbeiten ? <MedikamentDialog medikament={dialog.medikament} offen={dialog.offen}
        onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
      <PdfDialog offen={pdf} onOffen={setPdf} titel="Medikationsplan als PDF"
        pfad={`patienten/${patient.id}/medikationsplan-pdf/`} dateiname={`Medikationsplan-${patient.nummer}.pdf`} />
    </>
  );
}
