/**
 * Berichte aus der Akte heraus (Wunsch 06.10.2026, F115).
 *
 * Entwürfe lassen sich beliebig ändern. Mit der Freigabe entsteht die PDF, sie wird als Dokument der Akte
 * abgelegt, und der Bericht ist danach unveränderlich – eine Korrektur ist ein neuer Bericht.
 */
import { Begriff } from "@/components/ui/Begriff";
import { useEffect, useState } from "react";
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
import { FirmaMarke } from "@/components/FirmenWahl";
import { useAkte } from "./Akte";
import { Aktenseite, Detail, Eintrag, Eintragsliste, useWahl } from "./Aktenseite";
import { DiagnosenKurz } from "./Diagnosen";
import type { Diagnose } from "@/lib/typen";

/** Einheitliche Gliederung der Fallzusammenfassung (F175), zusammengeführt aus den Fallzusammenfassungen von
 *  Prof. Masin (Wunsch von Alice Hessel, 09.10.2026). Die Hinweise in [eckigen Klammern] werden überschrieben. */
const GLIEDERUNG_FALL: [string, string][] = [
  ["1. Anlass und zugrunde liegende Unterlagen", "[Zuweisung bzw. Kontakt (z. B. über die Stiftung, Datum); vorliegende Unterlagen mit Absender und Datum; Anlass der Zusammenfassung]"],
  ["2. Grunderkrankung und Diagnosen", "[Diagnosen mit ICD-10 und Quelle; die Diagnosen der Akte stehen zusätzlich als Tabelle im Bericht]"],
  ["3. Anamnese und Krankheitsverlauf", "[Beginn und Verlauf; Operationen und Eingriffe chronologisch; stationäre Aufenthalte und Reha]"],
  ["4. Aktuelle Symptomatik und Eigenangaben", "[gastrointestinale und vegetative Beschwerden, Kostaufbau, was die Patientin bzw. der Patient selbst berichtet]"],
  ["5. Ernährungsstatus und Anthropometrie", "[Größe; Gewichtsverlauf prämorbid bis aktuell; BMI; Gewichtsverlust in %; Einordnung nach GLIM]"],
  ["6. Bisherige und aktuelle Ernährungstherapie", "[oral, Trinknahrung, enteral, parenteral (Regime, Zugang); ernährungstherapeutische Begleitung]"],
  ["7. Medikation, Supplemente, Allergien und Unverträglichkeiten", "[aktuelle Medikation; Supplementationsversuche und Verträglichkeit; Allergien]"],
  ["8. Laborbefunde", "[Schlüsselbefunde mit Datum und Verlauf; Mikronährstoffstatus; fehlende Parameter]"],
  ["9. Bildgebung und weitere Befunde", "[Befund, Datum, Einrichtung]"],
  ["10. Zusammenfassende Beurteilung", "[ernährungsmedizinische Einordnung des Falles]"],
  ["11. Empfehlungen und weiteres Vorgehen", "[nummerierte Handlungsvorschläge, z. B. Sprechstunde, Substitution, Monitoring]"],
  ["12. Offene Fragen, Unstimmigkeiten und fehlende Unterlagen", "[z. B. abweichende Angaben zu Größe oder Geburtsdatum in den Unterlagen; noch angeforderte Befunde]"],
];
const GLIEDERUNG_HTML = GLIEDERUNG_FALL.map(([h, t]) => `<h3>${h}</h3><p>${t}</p>`).join("");
const DIAGNOSEN_PLATZHALTER = `<p>${GLIEDERUNG_FALL[1][1]}</p>`;

function html(text: string) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Die zutreffenden Diagnosen der Akte als Liste für den Berichtstext: „Kurzdarmsyndrom (ICD-10 K91.2 G, seit …)“ */
function diagnosenHtml(liste: Diagnose[]): string {
  const art: Record<string, string> = { V: "Verdacht", Z: "Zustand nach", A: "Ausschluss" };
  return `<ul>${liste.map((d) => `<li>${html(d.bezeichnung)} (ICD-10 ${html(d.icd_code)} ${d.kennzeichen}${
    art[d.kennzeichen] ? `, ${art[d.kennzeichen]}` : ""}${d.seit ? `, seit ${datum(d.seit)}` : ""})</li>`).join("")}</ul>`;
}

/**
 * Alle Diagnosen der Akte im Bericht (Wunsch 10.10.2026: „in Berichten als komplette Übersicht mit allen Diagnosen“):
 * im PDF stehen sie ohnehin als Tabelle; hier sieht man sie beim Schreiben und kann sie in den Text übernehmen.
 */
function DiagnosenImBericht({ patientId, onUebernehmen }: { patientId: number; onUebernehmen?: (html: string) => void }) {
  const diagnosen = useQuery({ queryKey: ["diagnosen", patientId], queryFn: () => api<Diagnose[]>(`diagnosen/?patient=${patientId}`) });
  const offene = (diagnosen.data ?? []).filter((d) => d.aktiv);
  return (
    <div className="rounded-lg border border-rand bg-grund px-3.5 py-3 flex flex-col gap-2" data-testid="bericht-diagnosen">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className="text-sm font-medium">Diagnosen der Akte{offene.length ? ` (${offene.length})` : ""}</span>
        {onUebernehmen && offene.length ? (
          <Knopf klein icon="plus" onClick={() => onUebernehmen(diagnosenHtml(offene))}>In den Text übernehmen</Knopf>
        ) : null}
      </div>
      <DiagnosenKurz patientId={patientId} alle />
      <span className="text-[0.75rem] gedaempft">Im PDF des Berichts stehen alle zutreffenden Diagnosen zusätzlich als Tabelle.</span>
    </div>
  );
}

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
  // geschlossen: beim nächsten Öffnen neu vorbelegen (sonst stünde der zuletzt bearbeitete Bericht noch drin)
  if (!offen && gesetzt) setGesetzt("");

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
  const { reset } = speichern;
  useEffect(() => { if (offen) reset(); }, [offen, reset]);
  const istFall = arten.data?.find((a) => String(a.id) === art)?.wert === "Fallzusammenfassung";
  const gliederung = () => {
    const leer = !inhalt.replace(/<[^>]+>/g, "").trim();
    if (!leer && !window.confirm("Die Gliederung vor den bisherigen Text setzen?")) return;
    setInhalt(GLIEDERUNG_HTML + (leer ? "" : inhalt));
    if (!titel.trim()) setTitel("Fallzusammenfassung");
    setStand((s) => s + 1);
  };

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
      {istFall ? (
        <div className="flex items-center gap-3 flex-wrap text-[0.8125rem]">
          <Knopf klein icon="plus" onClick={gliederung}>Gliederung einfügen</Knopf>
          <span className="gedaempft">Einheitlicher Aufbau in 12 Abschnitten; Hinweise in [eckigen Klammern] überschreiben.</span>
        </div>
      ) : null}
      <DiagnosenImBericht patientId={patient.id} onUebernehmen={(liste) => {
        // in der Fallzusammenfassung an Abschnitt 2, sonst als eigener Abschnitt ans Ende
        setInhalt((alt) => alt.includes(DIAGNOSEN_PLATZHALTER) ? alt.replace(DIAGNOSEN_PLATZHALTER, liste) : `${alt}<h3>Diagnosen</h3>${liste}`);
        setStand((x) => x + 1);
      }} />
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
                datum={<>{datum(b.datum)}<FirmaMarke kurz={b.firma_kurz} className="ml-1.5" /></>}
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
              <Chip art={gewaehlt.status === "freigegeben" ? "ok" : "warn"} data-testid="bericht-status">{gewaehlt.status === "entwurf"
                ? <Begriff name="entwurf">{gewaehlt.status_name}</Begriff> : gewaehlt.status_name}</Chip></span>}
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
            {entwurf ? <DiagnosenImBericht patientId={patient.id} /> : null}
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
