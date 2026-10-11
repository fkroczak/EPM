/**
 * Reiter „Diagnosen“: die Liste mit ICD-Code und die Notizen in einem Reiter (Wünsche 06./07.10.2026, F117, F122).
 *
 * Aufbau wie überall in der Akte: links die Einträge mit Datum – obenan die Notizen, darunter die Diagnosen –,
 * rechts der gewählte Eintrag. Angezeigt wie gewünscht: „Kurzdarmsyndrom [K91.2G]“. Die Liste im Hintergrund
 * (Vorlagen › Labor und Diagnosen) wächst beim Eintragen von allein mit. Nicht mehr zutreffende Diagnosen werden
 * auf „nicht mehr zutreffend“ gesetzt, nicht gelöscht – jede Fassung bleibt im Verlauf.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useDiagnoseliste } from "@/lib/daten";
import { datum, eingabeDatum } from "@/lib/format";
import { DIAGNOSE_KENNZEICHEN } from "@/lib/typen";
import type { Diagnose } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Karte, Knopf, Laden, Meldung, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { FirmaMarke } from "@/components/FirmenWahl";
import { useAkte } from "./Akte";
import { useWahl } from "./Aktenseite";
import { Textfassung } from "./TextKarte";
import { Bestaetigen } from "@/components/Bestaetigen";

const KATALOG_ID = "diagnoseliste";


function DiagnoseDialog({ diagnose, offen, onOffen }: { diagnose: Diagnose | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const katalog = useDiagnoseliste();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [bezeichnung, setBezeichnung] = useState("");
  const [icd, setIcd] = useState("");
  const [kennzeichen, setKennzeichen] = useState("G");
  const [seit, setSeit] = useState("");
  const [notiz, setNotiz] = useState("");
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${diagnose?.id ?? "neu"}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setBezeichnung(diagnose?.bezeichnung ?? "");
    setIcd(diagnose?.icd_code ?? "");
    setKennzeichen(diagnose?.kennzeichen ?? "G");
    setSeit(diagnose?.seit ? datum(diagnose.seit) : "");
    setNotiz(diagnose?.notiz ?? "");
  }

  /** Aus der Liste gewählt: Bezeichnung und Code zusammen übernehmen */
  const ausKatalog = (text: string) => {
    const treffer = (katalog.data ?? []).find((d) => d.bezeichnung === text);
    setBezeichnung(text);
    if (treffer) setIcd(treffer.icd_code);
  };

  const speichern = useMutation({
    mutationFn: () => {
      let iso: string | null = null;
      if (seit.trim()) {
        iso = eingabeDatum(seit);
        if (!iso) throw new ApiFehler(400, "", null, { seit: "Bitte als TT.MM.JJJJ eingeben." });
      }
      const koerper = { patient: patient.id, bezeichnung: bezeichnung.trim(), icd_code: icd.trim().toUpperCase(),
        kennzeichen, seit: iso, notiz: notiz.trim() };
      return diagnose
        ? api<Diagnose>(`diagnosen/${diagnose.id}/`, { method: "PATCH", body: koerper })
        : api<Diagnose>("diagnosen/", { body: koerper });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["diagnosen", patient.id] });
      void qc.invalidateQueries({ queryKey: ["diagnoseliste"] });
      melden(diagnose ? "Diagnose geändert." : "Diagnose eingetragen.");
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};

  return (
    <Dialog offen={offen} onOffen={onOffen} breite={620} titel={diagnose ? "Diagnose ändern" : "Neue Diagnose"}
      beschreibung="Bezeichnung und ICD-Code; das Zusatzkennzeichen sagt, wie sicher die Diagnose ist."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!bezeichnung.trim() || !icd.trim()}
          onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <Feld label="Diagnose" fehler={f.bezeichnung} pflicht
        hinweis="Aus der Liste wählen oder neu eintragen – neue Einträge wandern in die Liste.">
        {(p) => <>
          <Eingabe {...p} list={KATALOG_ID} value={bezeichnung} maxLength={200}
            onChange={(e) => ausKatalog(e.target.value)} placeholder="z. B. Kurzdarmsyndrom" />
          <datalist id={KATALOG_ID}>
            {(katalog.data ?? []).map((d) => <option key={d.id} value={d.bezeichnung}>{d.icd_code}</option>)}
          </datalist>
        </>}
      </Feld>
      <div className="grid gap-3 sm:grid-cols-[8.75rem_1fr_10rem]">
        <Feld label="ICD-Code" fehler={f.icd_code} pflicht>
          {(p) => <Eingabe {...p} className="num" value={icd} maxLength={10} placeholder="K91.2"
            onChange={(e) => setIcd(e.target.value.toUpperCase())} />}
        </Feld>
        <Feld label="Zusatzkennzeichen" fehler={f.kennzeichen} pflicht>
          {(p) => (
            <Auswahl {...p} value={kennzeichen} onChange={(e) => setKennzeichen(e.target.value)}>
              {Object.entries(DIAGNOSE_KENNZEICHEN).map(([k, text]) => <option key={k} value={k}>{text}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="besteht seit" fehler={f.seit}>
          {(p) => <Eingabe {...p} className="num" value={seit} placeholder="TT.MM.JJJJ"
            onChange={(e) => setSeit(e.target.value)} />}
        </Feld>
      </div>
      <Feld label="Notiz" fehler={f.notiz}>
        {(p) => <Eingabe {...p} value={notiz} maxLength={300} onChange={(e) => setNotiz(e.target.value)} />}
      </Feld>
      <Meldung art="info">
        Vorschau: <strong>{bezeichnung.trim() || "Diagnose"} [{(icd.trim() || "ICD").toUpperCase()}{kennzeichen}]</strong>
      </Meldung>
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

/** Code mit Zusatzkennzeichen als Marke: „K91.2 G“; Verdacht, Zustand nach und Ausschluss farbig abgesetzt */
function Code({ d }: { d: Diagnose }) {
  return (
    <span className={cx("diagnose-code", d.kennzeichen !== "G" && "anders", !d.aktiv && "beendet")} title={d.kennzeichen_name}>
      {d.icd_code}<span className="diagnose-kz">{d.kennzeichen}</span>
    </span>
  );
}

/** Eine Zeile der Diagnoseliste: Code, Bezeichnung, darunter seit/Notiz; rechts die Aktionen */
function DiagnoseZeile({ d, markiert, bearbeiten, onBearbeiten, onUmschalten, laedt }: {
  d: Diagnose; markiert: boolean; bearbeiten: boolean; onBearbeiten: () => void; onUmschalten: () => void; laedt: boolean;
}) {
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => { if (markiert) ref.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [markiert]);
  const unter = [d.kennzeichen !== "G" ? d.kennzeichen_name : "", d.seit ? `seit ${datum(d.seit)}` : "",
    d.aktiv ? "" : `beendet ${datum(d.beendet_am)}`].filter(Boolean).join(" · ");
  return (
    <li ref={ref} className={cx("diagnose-zeile", markiert && "markiert", !d.aktiv && "beendet")} data-testid="diagnose-zeile">
      <Code d={d} />
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className={cx("font-medium", !d.aktiv && "line-through decoration-gedaempft")}>{d.bezeichnung}</span>
        {unter || d.firma_kurz ? (
          <span className="flex items-center gap-1.5 text-[0.8125rem] gedaempft">{unter ? <span>{unter}</span> : null}<FirmaMarke kurz={d.firma_kurz} /></span>
        ) : null}
        {d.notiz ? <span className="text-[0.8125rem] text-text2">{d.notiz}</span> : null}
      </div>
      {bearbeiten ? (
        <div className="flex items-center gap-1 justify-end">
          <Knopf klein variante="geist" icon="stift" onClick={onBearbeiten} aria-label={`${d.bezeichnung} bearbeiten`} title="Bearbeiten" />
          {d.aktiv
            ? <Knopf klein variante="geist" onClick={onUmschalten} aria-label={`${d.bezeichnung} beenden`}>Beenden</Knopf>
            : <Knopf klein laedt={laedt} onClick={onUmschalten} aria-label={`${d.bezeichnung} wieder aktuell`}>Wieder aktuell</Knopf>}
        </div>
      ) : <span />}
    </li>
  );
}

/**
 * Reiter „Diagnosen“ (Wunsch 10.10.2026: „sieht ungewöhnlich aus, wenn die Codes einzeln gespeichert werden“): alle
 * Diagnosen zusammen als Liste wie im Arztbrief – Code, Bezeichnung, seit –, daneben die Notizen. Jede Diagnose bleibt
 * ein eigener Eintrag mit Verlauf; „?eintrag=<id>“ (aus Karteikarte und Verlauf) hebt die Zeile hervor.
 */
export function Diagnosen() {
  const { patient, bearbeiten } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [wahl] = useWahl("eintrag");
  const [dialog, setDialog] = useState<{ offen: boolean; diagnose: Diagnose | null }>({ offen: false, diagnose: null });
  const [beendeteAn, setBeendete] = useState(false);
  const [beenden, setBeenden] = useState<Diagnose | null>(null);

  const diagnosen = useQuery({
    queryKey: ["diagnosen", patient.id],
    queryFn: () => api<Diagnose[]>(`diagnosen/?patient=${patient.id}`),
  });
  const umschalten = useMutation({
    mutationFn: (d: Diagnose) => api<Diagnose>(`diagnosen/${d.id}/`, { method: "PATCH", body: { aktiv: !d.aktiv } }),
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: ["diagnosen", patient.id] });
      melden(d.aktiv ? "Wieder als zutreffend eingetragen." : "Als nicht mehr zutreffend eingetragen.");
      setBeenden(null);
    },
    onError: (e) => { if (!beenden) melden(e.message, "fehler"); },
  });

  const alle = diagnosen.data ?? [];
  const offene = alle.filter((d) => d.aktiv);
  const beendete = alle.filter((d) => !d.aktiv);
  // aus der Karteikarte auf eine beendete Diagnose gezeigt: beendete gleich mit anzeigen
  const zeigeBeendete = beendeteAn || beendete.some((d) => String(d.id) === wahl);
  const zeile = (d: Diagnose) => (
    <DiagnoseZeile key={d.id} d={d} markiert={String(d.id) === wahl} bearbeiten={bearbeiten}
      onBearbeiten={() => setDialog({ offen: true, diagnose: d })} laedt={umschalten.isPending}
      onUmschalten={() => { umschalten.reset(); if (d.aktiv) setBeenden(d); else umschalten.mutate(d); }} />
  );

  return (
    <>
    <div className="akte-spalten grid grid-cols-1 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-[var(--abstand)] items-start" data-testid="diagnosen">
      <Karte className="overflow-hidden" data-testid="diagnoseliste">
        <div className="px-5 pt-4 pb-3 flex items-center justify-between gap-3 flex-wrap">
          <h2 className="lbl m-0 text-[0.9375rem] flex items-center gap-2">
            Diagnosen{offene.length ? <Chip>{offene.length}</Chip> : null}
          </h2>
          {bearbeiten ? <Knopf variante="pri" icon="plus" onClick={() => setDialog({ offen: true, diagnose: null })}>Neue Diagnose</Knopf> : null}
        </div>
        {diagnosen.isPending ? <Laden /> : offene.length ? (
          <ul className="m-0 p-0 list-none">{offene.map(zeile)}</ul>
        ) : (
          <p className="m-0 px-5 pb-4 text-sm gedaempft">Noch keine Diagnose mit ICD-Code.</p>
        )}
        {beendete.length ? (
          <div className="border-t border-rand">
            <button type="button" className="w-full text-left px-5 py-2.5 bg-transparent border-0 text-[0.8125rem] gedaempft cursor-pointer hover:bg-fein"
              aria-expanded={zeigeBeendete} onClick={() => setBeendete((b) => !b)}>
              {zeigeBeendete ? "Beendete ausblenden" : `${beendete.length} beendete anzeigen`}
            </button>
            {zeigeBeendete ? <ul className="m-0 p-0 list-none">{beendete.map(zeile)}</ul> : null}
          </div>
        ) : null}
      </Karte>
      <Textfassung feld="diagnose" titel="Notizen"
        hinweis="Ausführliche Beschreibung zu den Diagnosen. Jede Fassung bleibt mit Person und Zeitpunkt erhalten." />
    </div>
    {bearbeiten ? <Bestaetigen offen={!!beenden} onOffen={(o) => { if (!o) setBeenden(null); }} titel="Diagnose beenden" knopf="Beenden"
      text={<>„{beenden?.bezeichnung}“ trifft nicht mehr zu. Sie bleibt unter „beendete anzeigen“ sichtbar und lässt sich wieder als aktuell eintragen.</>}
      laedt={umschalten.isPending} fehler={umschalten.error} onJa={() => beenden && umschalten.mutate(beenden)} /> : null}
    {bearbeiten ? <DiagnoseDialog diagnose={dialog.diagnose} offen={dialog.offen}
      onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
    </>
  );
}

/** Nur für die Übersicht der Akte: die zutreffenden Diagnosen in Kurzform. */
export function DiagnosenKurz({ patientId, alle }: { patientId: number; alle?: boolean }) {
  const diagnosen = useQuery({
    queryKey: ["diagnosen", patientId],
    queryFn: () => api<Diagnose[]>(`diagnosen/?patient=${patientId}`),
  });
  const offene = (diagnosen.data ?? []).filter((d) => d.aktiv);
  if (!offene.length) return <p className="m-0 text-sm gedaempft">Noch keine Diagnose mit ICD-Code.</p>;
  return (
    <ul className="m-0 p-0 list-none flex flex-col gap-1.5" data-testid="diagnosen-kurz">
      {(alle ? offene : offene.slice(0, 6)).map((d) => (
        <li key={d.id} className="text-sm flex items-baseline gap-2 min-w-0">
          <Code d={d} /><span className="min-w-0">{d.bezeichnung}</span>
        </li>
      ))}
      {!alle && offene.length > 6 ? <li className="text-[0.8125rem] gedaempft">und {offene.length - 6} weitere</li> : null}
    </ul>
  );
}
