/**
 * Berichte aus der Akte heraus (Wunsch 06.10.2026, F115).
 *
 * Entwürfe lassen sich beliebig ändern. Mit der Freigabe entsteht die PDF, sie wird als Dokument der Akte
 * abgelegt, und der Bericht ist danach unveränderlich – eine Korrektur ist ein neuer Bericht.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuswahl } from "@/lib/daten";
import { datum, eingabeDatum, heuteIso } from "@/lib/format";
import type { Bericht } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung }
  from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Editor, Richtext } from "@/components/Editor";
import { PdfDialog } from "@/components/PdfDialog";
import { useAkte } from "./Akte";

function BerichtDialog({ bericht, offen, onOffen }: { bericht: Bericht | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const arten = useAuswahl("berichtart");
  const qc = useQueryClient();
  const melden = useHinweis();
  const [titel, setTitel] = useState("");
  const [art, setArt] = useState("");
  const [tag, setTag] = useState(datum(heuteIso()));
  const [empfaenger, setEmpfaenger] = useState("");
  const [inhalt, setInhalt] = useState("");
  const [stand, setStand] = useState(0);
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${bericht?.id ?? "neu"}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setTitel(bericht?.titel ?? "");
    setArt(bericht?.art ? String(bericht.art) : "");
    setTag(datum(bericht?.datum ?? heuteIso()));
    setEmpfaenger(bericht?.empfaenger ?? "");
    setInhalt(bericht?.inhalt ?? "");
    setStand((s) => s + 1);
  }

  const speichern = useMutation({
    mutationFn: () => {
      const iso = eingabeDatum(tag);
      if (!iso) throw new ApiFehler(400, "", null, { datum: "Bitte als TT.MM.JJJJ eingeben." });
      const koerper = { patient: patient.id, titel: titel.trim(), art: art ? Number(art) : null, datum: iso,
        empfaenger: empfaenger.trim(), inhalt };
      return bericht
        ? api<Bericht>(`berichte/${bericht.id}/`, { method: "PATCH", body: koerper })
        : api<Bericht>("berichte/", { body: koerper });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["berichte", patient.id] });
      melden(bericht ? "Bericht geändert." : "Entwurf gespeichert.");
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};

  return (
    <Dialog offen={offen} onOffen={onOffen} breite={780} titel={bericht ? "Bericht bearbeiten" : "Neuer Bericht"}
      beschreibung="Der Bericht bleibt Entwurf, bis er freigegeben wird. Erst dann entsteht die PDF."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!titel.trim()}
          onClick={() => speichern.mutate()}>Entwurf speichern</Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-[1fr_200px_160px]">
        <Feld label="Titel" fehler={f.titel} pflicht>
          {(p) => <Eingabe {...p} value={titel} maxLength={200} onChange={(e) => setTitel(e.target.value)}
            placeholder="z. B. Verlaufsbericht 2026" />}
        </Feld>
        <Feld label="Berichtsart" fehler={f.art}>
          {(p) => (
            <Auswahl {...p} value={art} onChange={(e) => setArt(e.target.value)}>
              <option value="">— ohne Angabe —</option>
              {(arten.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Datum" fehler={f.datum}>
          {(p) => <Eingabe {...p} className="num" value={tag} onChange={(e) => setTag(e.target.value)} />}
        </Feld>
      </div>
      <Feld label="Empfänger" fehler={f.empfaenger}>
        {(p) => <Eingabe {...p} value={empfaenger} maxLength={200} placeholder="z. B. Hausarzt Dr. Hausmann"
          onChange={(e) => setEmpfaenger(e.target.value)} />}
      </Feld>
      <Feld label="Bericht" fehler={f.inhalt}>
        {() => <Editor key={stand} wert={inhalt} onAenderung={setInhalt} label="Bericht" hoehe={300} />}
      </Feld>
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

function FreigabeDialog({ bericht, offen, onOffen }: { bericht: Bericht | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const freigeben = useMutation({
    mutationFn: () => api<Bericht>(`berichte/${bericht!.id}/freigeben/`, { body: {} }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["berichte", patient.id] });
      void qc.invalidateQueries({ queryKey: ["dokumente", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden("Bericht freigegeben; die PDF liegt in den Dokumenten.");
      onOffen(false);
    },
  });
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Bericht freigeben"
      beschreibung={bericht?.titel}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={freigeben.isPending} onClick={() => freigeben.mutate()}>Freigeben</Knopf>
      </>}>
      <Meldung art="warn">
        Mit der Freigabe entsteht die PDF und wird als Dokument der Akte abgelegt. Danach lässt sich der Bericht
        nicht mehr ändern – eine Korrektur ist ein neuer Bericht.
      </Meldung>
      <Fehleranzeige fehler={freigeben.error} />
    </Dialog>
  );
}

export function Berichte() {
  const { patient, erfassen } = useAkte();
  const { darf } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [dialog, setDialog] = useState<{ offen: boolean; bericht: Bericht | null }>({ offen: false, bericht: null });
  const [freigabe, setFreigabe] = useState<{ offen: boolean; bericht: Bericht | null }>({ offen: false, bericht: null });
  const [pdf, setPdf] = useState<Bericht | null>(null);

  const berichte = useQuery({
    queryKey: ["berichte", patient.id],
    queryFn: () => api<Bericht[]>(`berichte/?patient=${patient.id}`),
  });
  const verwerfen = useMutation({
    mutationFn: (b: Bericht) => api(`berichte/${b.id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["berichte", patient.id] });
      melden("Entwurf verworfen.");
    },
    onError: (e) => melden(e.message, "fehler"),
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="lbl m-0">Berichte{berichte.data?.length ? <span className="num ml-1.5 opacity-70">{berichte.data.length}</span> : null}</h2>
        {erfassen ? <Knopf variante="pri" klein onClick={() => setDialog({ offen: true, bericht: null })}>Neuer Bericht</Knopf> : null}
      </div>
      {berichte.isPending ? <Laden /> : <Fehleranzeige fehler={berichte.error} />}
      {berichte.data?.length === 0 ? <Karte className="p-[22px]"><Leer>Noch kein Bericht in dieser Akte.</Leer></Karte> : null}

      {(berichte.data ?? []).map((b) => (
        <Karte key={b.id} className="p-[22px] flex flex-col gap-3" data-testid={`bericht-${b.id}`}>
          <KartenKopf
            titel={<span className="flex items-center gap-2">{b.titel}
              <Chip art={b.status === "freigegeben" ? "ok" : "warn"}>{b.status_name}</Chip></span>}
            unter={[b.art_name, datum(b.datum), b.empfaenger ? `an ${b.empfaenger}` : "", b.erstellt_von_name]
              .filter(Boolean).join(" · ")}
            rechts={<>
              {b.status === "entwurf" && erfassen ? (
                <Knopf klein onClick={() => setDialog({ offen: true, bericht: b })}>Bearbeiten</Knopf>
              ) : null}
              {b.status === "entwurf" && erfassen && darf("berichte_freigeben") ? (
                <Knopf klein variante="pri" onClick={() => setFreigabe({ offen: true, bericht: b })}>Freigeben</Knopf>
              ) : null}
              {b.status === "entwurf" && erfassen ? (
                <Knopf klein variante="dng" laedt={verwerfen.isPending} onClick={() => verwerfen.mutate(b)}>Verwerfen</Knopf>
              ) : null}
              {b.status === "freigegeben" && b.dokument ? (
                <Knopf klein onClick={() => setPdf(b)}>PDF ansehen</Knopf>
              ) : null}
            </>}
          />
          <Richtext html={b.inhalt} leer="Noch kein Text." />
          {b.freigabevermerk ? <p className="m-0 text-[0.8125rem] gedaempft border-t border-rand pt-2">{b.freigabevermerk}</p> : null}
        </Karte>
      ))}

      {erfassen ? <>
        <BerichtDialog bericht={dialog.bericht} offen={dialog.offen} onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} />
        <FreigabeDialog bericht={freigabe.bericht} offen={freigabe.offen} onOffen={(o) => setFreigabe((d) => ({ ...d, offen: o }))} />
      </> : null}
      <PdfDialog offen={!!pdf} onOffen={(o) => !o && setPdf(null)} titel={pdf?.titel ?? "Bericht"}
        pfad={pdf?.dokument ? `dokumente/${pdf.dokument}/datei/?anzeigen=1` : ""}
        dateiname={`Bericht-${patient.nummer}.pdf`} />
    </div>
  );
}
