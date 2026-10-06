/**
 * Diagnoseliste der Akte mit ICD-Code und Zusatzkennzeichen (Wunsch 06.10.2026, F117).
 *
 * Angezeigt wie gewünscht: „Kurzdarmsyndrom [K91.2G]“. Die Liste im Hintergrund (Vorlagen › Diagnosen) wächst
 * beim Eintragen von allein mit und schlägt beim nächsten Mal vor. Nicht mehr zutreffende Diagnosen werden auf
 * „nicht mehr zutreffend“ gesetzt, nicht gelöscht – jede Fassung bleibt im Verlauf.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useDiagnoseliste } from "@/lib/daten";
import { datum, eingabeDatum } from "@/lib/format";
import { DIAGNOSE_KENNZEICHEN } from "@/lib/typen";
import type { Diagnose } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung }
  from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { RASTER_SPALTEN, useStufe } from "@/lib/stufen";
import { Bereich, Bereiche } from "@/components/ui/bereiche";
import { Link } from "react-router";
import { useAkte } from "./Akte";
import { TextKarte } from "./TextKarte";

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

export function DiagnosenKarte() {
  const { patient, bearbeiten } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
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
  const sichtbar = beendete ? alle : alle.filter((d) => d.aktiv);
  const anzahlBeendet = alle.length - alle.filter((d) => d.aktiv).length;

  return (
    <Karte className="px-[22px] py-[18px] flex flex-col gap-3 min-w-0" data-testid="karte-diagnosen">
      <KartenKopf titel="Diagnosen (ICD)" unter="Gesichert (G), Verdacht (V), Zustand nach (Z), Ausschluss (A)"
        rechts={bearbeiten ? <Knopf klein icon="plus" onClick={() => setDialog({ offen: true, diagnose: null })}>
          Diagnose</Knopf> : undefined} />
      {diagnosen.isPending ? <Laden /> : <Fehleranzeige fehler={diagnosen.error} />}
      {sichtbar.length === 0 ? <Leer>Noch keine Diagnose mit ICD-Code eingetragen.</Leer> : (
        <ul className="m-0 p-0 list-none flex flex-col gap-1.5" data-testid="diagnoseliste">
          {sichtbar.map((d) => (
            <li key={d.id} className="flex items-start justify-between gap-3 border-b border-rand pb-1.5 last:border-0">
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="text-sm">
                  {d.bezeichnung} <span className="num gedaempft">[{d.icd_code}{d.kennzeichen}]</span>
                  {!d.aktiv ? <Chip className="ml-2">nicht mehr zutreffend</Chip> : null}
                  {d.kennzeichen !== "G" && d.aktiv ? <Chip art="warn" className="ml-2">{d.kennzeichen_name}</Chip> : null}
                </span>
                {d.seit || d.notiz ? (
                  <span className="text-[0.75rem] gedaempft">
                    {[d.seit ? `seit ${datum(d.seit)}` : "", d.notiz].filter(Boolean).join(" · ")}
                  </span>
                ) : null}
              </div>
              {bearbeiten ? (
                <div className="flex items-center gap-1.5 shrink-0">
                  <Knopf klein onClick={() => setDialog({ offen: true, diagnose: d })}>Ändern</Knopf>
                  <Knopf klein onClick={() => umschalten.mutate(d)}>{d.aktiv ? "Beenden" : "Wieder aktuell"}</Knopf>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {anzahlBeendet ? (
        <button type="button" className="self-start bg-transparent border-0 p-0 text-[0.8125rem] gedaempft cursor-pointer underline"
          onClick={() => setBeendete((b) => !b)}>
          {beendete ? "Beendete ausblenden" : `${anzahlBeendet} beendete anzeigen`}
        </button>
      ) : null}
      {bearbeiten ? <DiagnoseDialog diagnose={dialog.diagnose} offen={dialog.offen}
        onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
    </Karte>
  );
}

/** Reiter „Diagnosen“ (Aufteilung 07.10.2026, F121): die Liste mit ICD-Code und daneben der lange Freitext (U51). */
export function Diagnosen() {
  const { patient } = useAkte();
  const stufe = useStufe();
  return (
    <Bereiche seite="akte_diagnosen" spalten={RASTER_SPALTEN[stufe]} testid="diagnosen-stufe">
      <Bereich id="diagnosen" titel="Diagnosen (ICD)" standard={{ breite: 2 }}><DiagnosenKarte /></Bereich>
      <Bereich id="diagnose" titel="Diagnose (Freitext)"><TextKarte feld="diagnose" /></Bereich>
      <Bereich id="hinweis" titel="Hinweis" menue={false}>
        <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
          <Icon name="info" />
          <span>Die Liste mit ICD-Code und das Freitextfeld bestehen nebeneinander: In der Liste steht, was abgerechnet
            und ausgewertet wird, im Freitext die ausführliche Beschreibung. Jede Fassung bleibt im{" "}
            <Link to={`/patienten/${patient.id}/verlauf`}>Verlauf</Link> erhalten; Therapie und Empfehlung stehen unter{" "}
            <Link to={`/patienten/${patient.id}/therapie`}>Therapie</Link>.</span>
        </div>
      </Bereich>
    </Bereiche>
  );
}
