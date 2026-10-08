/**
 * Reiter „Diagnosen“: die Liste mit ICD-Code und die Notizen in einem Reiter (Wünsche 06./07.10.2026, F117, F122).
 *
 * Aufbau wie überall in der Akte: links die Einträge mit Datum – obenan die Notizen, darunter die Diagnosen –,
 * rechts der gewählte Eintrag. Angezeigt wie gewünscht: „Kurzdarmsyndrom [K91.2G]“. Die Liste im Hintergrund
 * (Vorlagen › Labor und Diagnosen) wächst beim Eintragen von allein mit. Nicht mehr zutreffende Diagnosen werden
 * auf „nicht mehr zutreffend“ gesetzt, nicht gelöscht – jede Fassung bleibt im Verlauf.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useDiagnoseliste } from "@/lib/daten";
import { datum, eingabeDatum, zeitpunkt } from "@/lib/format";
import { DIAGNOSE_KENNZEICHEN } from "@/lib/typen";
import type { Diagnose } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Knopf, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { useAkte } from "./Akte";
import { Abschnitt, Aktenseite, Detail, Eintrag, Eintragsliste, useWahl } from "./Aktenseite";
import { Textfassung, Textkopf } from "./TextKarte";

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
      <div className="grid gap-3 sm:grid-cols-[140px_1fr_160px]">
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

/** Der Eintrag einer Diagnose in der Liste links. */
function DiagnoseEintrag({ d, aktiv, onWahl }: { d: Diagnose; aktiv: boolean; onWahl: () => void }) {
  return (
    <Eintrag aktiv={aktiv} onWahl={onWahl} warnung={!d.aktiv}
      datum={d.seit ? datum(d.seit) : datum(d.angelegt_am)}
      merkmal={d.aktiv
        ? (d.kennzeichen !== "G" ? <Chip art="warn">{d.kennzeichen}</Chip> : <Chip>{d.kennzeichen}</Chip>)
        : <Chip art="warn">beendet</Chip>}
      zeile={d.bezeichnung}
      unten={<span className="num">{d.icd_code}{d.kennzeichen}</span>} />
  );
}

export function Diagnosen() {
  const { patient, bearbeiten } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [wahl, setWahl] = useWahl("eintrag");
  const [dialog, setDialog] = useState<{ offen: boolean; diagnose: Diagnose | null }>({ offen: false, diagnose: null });
  const [beendete, setBeendete] = useState(false);

  const diagnosen = useQuery({
    queryKey: ["diagnosen", patient.id],
    queryFn: () => api<Diagnose[]>(`diagnosen/?patient=${patient.id}`),
  });
  const umschalten = useMutation({
    mutationFn: (d: Diagnose) => api<Diagnose>(`diagnosen/${d.id}/`, { method: "PATCH", body: { aktiv: !d.aktiv } }),
    onSuccess: (d) => {
      void qc.invalidateQueries({ queryKey: ["diagnosen", patient.id] });
      melden(d.aktiv ? "Wieder als zutreffend eingetragen." : "Als nicht mehr zutreffend eingetragen.");
    },
    onError: (e) => melden(e.message, "fehler"),
  });

  const alle = diagnosen.data ?? [];
  const offene = alle.filter((d) => d.aktiv);
  // aus der Karteikarte auf eine beendete Diagnose gezeigt: beendete gleich mit anzeigen
  const sichtbar = beendete || alle.some((d) => !d.aktiv && String(d.id) === wahl) ? alle : offene;
  const anzahlBeendet = alle.length - offene.length;
  // „notizen“ steht obenan; sonst die gewählte Diagnose, ersatzweise die erste
  const gewaehlt = wahl === "notizen" ? null : sichtbar.find((d) => String(d.id) === wahl) ?? (wahl ? null : sichtbar[0]);
  const notizen = wahl === "notizen" || (!gewaehlt && !sichtbar.length);

  return (
    <>
    <Aktenseite
      testid="diagnosen"
      titel={offene.length === 1 ? "Diagnose" : "Diagnosen"}
      anzahl={offene.length}
      laedt={diagnosen.isPending}
      aktion={bearbeiten
        ? <Knopf variante="pri" icon="plus" onClick={() => setDialog({ offen: true, diagnose: null })}>Neue Diagnose</Knopf>
        : undefined}
      fuss={<>Gesichert (G), Verdacht (V), Zustand nach (Z), Ausschluss (A). Beendete Diagnosen bleiben erhalten;
        jede Fassung steht im Verlauf der Akte.</>}
      liste={
        <Eintragsliste name="Diagnosen" leer={sichtbar.length ? undefined : "Noch keine Diagnose mit ICD-Code."}>
          <Textkopf feld="diagnose" titel="Notizen" aktiv={notizen} onWahl={() => setWahl("notizen")} />
          {sichtbar.map((d) => (
            <DiagnoseEintrag key={d.id} d={d} aktiv={gewaehlt?.id === d.id} onWahl={() => setWahl(String(d.id))} />
          ))}
          {anzahlBeendet ? (
            <button type="button" className="self-start bg-transparent border-0 p-0 text-[0.8125rem] gedaempft cursor-pointer underline"
              onClick={() => setBeendete((b) => !b)}>
              {beendete ? "Beendete ausblenden" : `${anzahlBeendet} beendete anzeigen`}
            </button>
          ) : null}
        </Eintragsliste>
      }
      detail={notizen || !gewaehlt ? (
        <Textfassung feld="diagnose" titel="Notizen"
          hinweis="Ausführliche Beschreibung zu den Diagnosen. Jede Fassung bleibt mit Person und Zeitpunkt erhalten." />
      ) : (
        <Detail testid="diagnose-detail"
          titel={<>{gewaehlt.bezeichnung} <span className="num gedaempft">[{gewaehlt.icd_code}{gewaehlt.kennzeichen}]</span></>}
          unter={[gewaehlt.kennzeichen_name, gewaehlt.seit ? `besteht seit ${datum(gewaehlt.seit)}` : "",
            gewaehlt.aktiv ? "" : `beendet ${datum(gewaehlt.beendet_am)}`].filter(Boolean).join(" · ")}
          aktionen={bearbeiten ? <>
            <Knopf klein icon="stift" onClick={() => setDialog({ offen: true, diagnose: gewaehlt })}>Ändern</Knopf>
            <Knopf klein laedt={umschalten.isPending} onClick={() => umschalten.mutate(gewaehlt)}>
              {gewaehlt.aktiv ? "Beenden" : "Wieder aktuell"}</Knopf>
          </> : undefined}>
          {gewaehlt.notiz ? <Abschnitt titel="Notiz zur Diagnose"><p className="m-0 text-sm">{gewaehlt.notiz}</p></Abschnitt> : null}
          <Abschnitt titel="Eingetragen">
            <p className="m-0 text-sm gedaempft">
              {zeitpunkt(gewaehlt.angelegt_am)}{gewaehlt.angelegt_von_name ? ` · ${gewaehlt.angelegt_von_name}` : ""}
            </p>
          </Abschnitt>
        </Detail>
      )}
    />
    {bearbeiten ? <DiagnoseDialog diagnose={dialog.diagnose} offen={dialog.offen}
      onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
    </>
  );
}

/** Nur für die Übersicht der Akte: die zutreffenden Diagnosen in Kurzform. */
export function DiagnosenKurz({ patientId }: { patientId: number }) {
  const diagnosen = useQuery({
    queryKey: ["diagnosen", patientId],
    queryFn: () => api<Diagnose[]>(`diagnosen/?patient=${patientId}`),
  });
  const offene = (diagnosen.data ?? []).filter((d) => d.aktiv);
  if (!offene.length) return <p className="m-0 text-sm gedaempft">Noch keine Diagnose mit ICD-Code.</p>;
  return (
    <ul className="m-0 p-0 list-none flex flex-col gap-0.5" data-testid="diagnosen-kurz">
      {offene.slice(0, 6).map((d) => (
        <li key={d.id} className="text-sm">
          {d.bezeichnung} <span className="num gedaempft">[{d.icd_code}{d.kennzeichen}]</span>
        </li>
      ))}
      {offene.length > 6 ? <li className="text-[0.8125rem] gedaempft">und {offene.length - 6} weitere</li> : null}
    </ul>
  );
}
