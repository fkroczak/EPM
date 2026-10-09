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
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Knopf, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Editor, Richtext } from "@/components/Editor";
import { PdfDialog } from "@/components/PdfDialog";
import { Bestaetigen } from "@/components/Bestaetigen";
import { useAkte } from "./Akte";
import { Aktenseite, Detail, Eintrag, Eintragsliste, useWahl } from "./Aktenseite";

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
      <div className="grid gap-3 sm:grid-cols-[1fr_12.5rem_10rem]">
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
  const [wahl, setWahl] = useWahl("bericht");
  const [dialog, setDialog] = useState<{ offen: boolean; bericht: Bericht | null }>({ offen: false, bericht: null });
  const [freigabe, setFreigabe] = useState<{ offen: boolean; bericht: Bericht | null }>({ offen: false, bericht: null });
  const [pdf, setPdf] = useState<Bericht | null>(null);
  const [weg, setWeg] = useState<Bericht | null>(null);

  const berichte = useQuery({
    queryKey: ["berichte", patient.id],
    queryFn: () => api<Bericht[]>(`berichte/?patient=${patient.id}`),
  });
  const verwerfen = useMutation({
    mutationFn: (b: Bericht) => api(`berichte/${b.id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["berichte", patient.id] });
      melden("Entwurf verworfen.");
      setWeg(null);
    },
  });

  const liste = berichte.data ?? [];
  const gewaehlt = liste.find((b) => String(b.id) === wahl) ?? liste[0];
  const entwurf = gewaehlt?.status === "entwurf";

  return (
    <>
      <Aktenseite
        testid="berichte"
        titel={liste.length === 1 ? "Bericht" : "Berichte"}
        anzahl={liste.length}
        laedt={berichte.isPending}
        aktion={erfassen
          ? <Knopf variante="pri" icon="plus" onClick={() => setDialog({ offen: true, bericht: null })}>Neuer Bericht</Knopf>
          : undefined}
        kopfrechts={<Fehleranzeige fehler={berichte.error} />}
        liste={
          <Eintragsliste name="Berichte" leer={liste.length ? undefined : "Noch kein Bericht in dieser Akte."}>
            {liste.map((b) => (
              <Eintrag key={b.id} aktiv={gewaehlt?.id === b.id} onWahl={() => setWahl(String(b.id))}
                warnung={b.status === "entwurf"}
                datum={datum(b.datum)}
                merkmal={<Chip art={b.status === "freigegeben" ? "ok" : "warn"} data-testid="bericht-status">{b.status_name}</Chip>}
                zeile={b.titel}
                unten={[b.art_name, b.empfaenger ? `an ${b.empfaenger}` : ""].filter(Boolean).join(" · ")} />
            ))}
          </Eintragsliste>
        }
        fuss={<>Freigegebene Berichte sind unveränderlich.</>}
        detail={gewaehlt ? (
          <Detail testid="bericht-detail"
            titel={<span className="flex items-center gap-2">{gewaehlt.titel}
              <Chip art={gewaehlt.status === "freigegeben" ? "ok" : "warn"} data-testid="bericht-status">{gewaehlt.status_name}</Chip></span>}
            unter={[gewaehlt.art_name, datum(gewaehlt.datum), gewaehlt.empfaenger ? `an ${gewaehlt.empfaenger}` : "",
              gewaehlt.erstellt_von_name].filter(Boolean).join(" · ")}
            aktionen={<>
              {entwurf && erfassen ? <Knopf klein icon="stift" onClick={() => setDialog({ offen: true, bericht: gewaehlt })}>Bearbeiten</Knopf> : null}
              {entwurf && erfassen && darf("berichte_freigeben")
                ? <Knopf klein variante="pri" icon="haken" onClick={() => setFreigabe({ offen: true, bericht: gewaehlt })}>Freigeben</Knopf> : null}
              {entwurf && erfassen
                ? <Knopf klein variante="dng" onClick={() => { verwerfen.reset(); setWeg(gewaehlt); }}>Verwerfen</Knopf> : null}
              {gewaehlt.status === "freigegeben" && gewaehlt.dokument
                ? <Knopf klein icon="dokument" onClick={() => setPdf(gewaehlt)}>PDF ansehen</Knopf> : null}
            </>}>
            <Richtext html={gewaehlt.inhalt} leer="Noch kein Text." />
            {gewaehlt.freigabevermerk
              ? <p className="m-0 text-[0.8125rem] gedaempft border-t border-rand pt-2">{gewaehlt.freigabevermerk}</p> : null}
          </Detail>
        ) : null}
        leer="Links einen Bericht wählen."
      />
      {erfassen ? <>
        <BerichtDialog bericht={dialog.bericht} offen={dialog.offen} onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} />
        <FreigabeDialog bericht={freigabe.bericht} offen={freigabe.offen} onOffen={(o) => setFreigabe((d) => ({ ...d, offen: o }))} />
        {/* Rückfrage vor dem Verwerfen (Vorschlag „Eine Sprache“, 08.10.2026) – vorher wirkte der Knopf sofort */}
        <Bestaetigen offen={!!weg} onOffen={(o) => { if (!o) setWeg(null); }} titel="Entwurf verwerfen" knopf="Verwerfen"
          text={<>Der Entwurf „{weg?.titel}“ wird gelöscht.</>} laedt={verwerfen.isPending} fehler={verwerfen.error}
          onJa={() => weg && verwerfen.mutate(weg)} />
      </> : null}
      <PdfDialog offen={!!pdf} onOffen={(o) => !o && setPdf(null)} titel={pdf?.titel ?? "Bericht"}
        pfad={pdf?.dokument ? `dokumente/${pdf.dokument}/datei/?anzeigen=1` : ""}
        dateiname={`Bericht-${patient.nummer}.pdf`} />
    </>
  );
}
