/**
 * Korrespondenz der Akte (Wunsch der Praxis, 14.10.2026): jedes Schreiben an oder über den Patienten liegt hier –
 * Arztbrief, Anforderung, Bescheinigung, Erklärung … – mit Status Entwurf → freigegeben → versendet.
 *
 * Entwürfe lassen sich ändern und löschen. Die Freigabe erzeugt die endgültige PDF aus der aktiven Vorlage und den Daten
 * der Akte (Dokument der Akte mit Prüfsumme); danach ist das Schreiben unveränderlich. Eine Korrektur ist ein neuer
 * Entwurf („Als neuen Entwurf kopieren“). Den Versand vermerkt man mit Weg und Datum.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import { ApiFehler, abfrage, api } from "@/lib/api";
import type { Feldfehler, Seite as ApiSeite } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, eingabeDatum, heuteIso, terminZeit, zeitpunkt } from "@/lib/format";
import { TERMINARTEN, VERSANDWEGE } from "@/lib/typen";
import type { Korrespondenzschreiben, Termin } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Knopf, Laden, Leer, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { PdfDialog } from "@/components/PdfDialog";
import { Bestaetigen } from "@/components/Bestaetigen";
import { FirmaMarke } from "@/components/FirmenWahl";
import { useAkte } from "./Akte";
import { Abschnitt, Aktenseite, Detail, Eintrag, Eintragsliste } from "./Aktenseite";
import { SchreibenOptionen } from "./Schreiben";
import type { Schreiben as Vorlage } from "./Schreiben";

type Status = Korrespondenzschreiben["status"];
const STATUS: { wert: "" | Status; text: string }[] = [
  { wert: "", text: "Alle" }, { wert: "entwurf", text: "Entwurf" }, { wert: "freigegeben", text: "freigegeben" },
  { wert: "versendet", text: "versendet" },
];

export function StatusChip({ s }: { s: Pick<Korrespondenzschreiben, "status" | "status_name"> }) {
  return <Chip art={s.status === "entwurf" ? "warn" : s.status === "freigegeben" ? "akzent" : "ok"}
    data-testid="schreiben-status">{s.status_name}</Chip>;
}

function useVorlagen(aktiv: boolean) {
  return useQuery({ queryKey: ["schreiben"], queryFn: () => api<Vorlage[]>("schreiben/"), enabled: aktiv });
}

// ------------------------------------------------------------------ Neues Schreiben / Entwurf bearbeiten
function SchreibenFormular({ schreiben, offen, onOffen, onGespeichert }: {
  schreiben: Korrespondenzschreiben | null; offen: boolean; onOffen: (o: boolean) => void;
  onGespeichert: (s: Korrespondenzschreiben) => void;
}) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const vorlagen = useVorlagen(offen);
  const [vorlage, setVorlage] = useState("");
  const [titel, setTitel] = useState("");
  const [titelVonHand, setTitelVonHand] = useState(false);
  const [empfaenger, setEmpfaenger] = useState("");
  const [text, setText] = useState("");
  const [termin, setTermin] = useState("");
  const [attest, setAttest] = useState(true);
  const [tage, setTage] = useState("");
  const [vorschau, setVorschau] = useState(false);
  // Neu-Dialoge beginnen leer, „Bearbeiten“ mit dem gewählten Entwurf – nie mit Werten vom letzten Öffnen
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${schreiben?.id ?? "neu"}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setVorlage(schreiben?.vorlage ?? "");
    setTitel(schreiben?.titel ?? "");
    setTitelVonHand(!!schreiben);
    setEmpfaenger(schreiben?.empfaenger ?? "");
    setText(schreiben?.text ?? "");
    setTermin(schreiben?.termin ? String(schreiben.termin) : "");
    setAttest(schreiben?.optionen.attest !== false);
    setTage(schreiben?.optionen.tage ? String(schreiben.optionen.tage) : "");
    setVorschau(false);
  }
  if (!offen && gesetzt) setGesetzt("");

  const gewaehlt = vorlagen.data?.find((v) => v.art === vorlage);
  const mitTermin = !!gewaehlt?.termin;
  const termine = useQuery({
    queryKey: ["patient", patient.id, "termine", "schreiben"],
    queryFn: () => api<ApiSeite<Termin>>(`termine/${abfrage({ patient: patient.id, offen: "true", ausgeblendet: "false", seitengroesse: 50 })}`),
    enabled: offen && mitTermin,
  });
  const terminListe = termine.data?.results ?? [];
  const tageZahl = /^\d{1,3}$/.test(tage) && Number(tage) > 0 ? Number(tage) : null;
  const koerper = {
    patient: patient.id, vorlage, titel: titel.trim(), empfaenger: empfaenger.trim(), text,
    termin: mitTermin && termin ? Number(termin) : null,
    optionen: vorlage === "reisebescheinigung" ? { attest, ...(attest && tageZahl ? { tage: tageZahl } : {}) } : {},
  };
  const bereit = !!gewaehlt && !!titel.trim() && (!mitTermin || !!termin);

  const speichern = useMutation({
    mutationFn: () => schreiben
      ? api<Korrespondenzschreiben>(`korrespondenz/${schreiben.id}/`, { method: "PATCH", body: koerper })
      : api<Korrespondenzschreiben>("korrespondenz/", { body: koerper }),
    onSuccess: (s) => {
      void qc.invalidateQueries({ queryKey: ["korrespondenz", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden(schreiben ? "Entwurf geändert." : "Entwurf gespeichert.");
      onGespeichert(s);
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const { reset } = speichern;
  useEffect(() => { if (offen) reset(); }, [offen, reset]);

  const vorlageWaehlen = (art: string) => {
    setVorlage(art);
    // Betreff aus dem Namen der Vorlage, solange er nicht von Hand geändert wurde
    const v = vorlagen.data?.find((x) => x.art === art);
    if (v && !titelVonHand) setTitel(v.name.split(" (")[0]);
  };
  // Vorschlag für den Termin: der nächste Praxistermin (wie im Dialog „Schreiben und E-Mail“)
  const vorschlag = terminListe.find((t) => t.art === "praxistermin") ?? terminListe[0];
  useEffect(() => {
    if (offen && mitTermin && !termin && vorschlag) setTermin(String(vorschlag.id));
  }, [offen, mitTermin, termin, vorschlag]);

  return (
    <>
      <Dialog offen={offen} onOffen={onOffen} breite={780} titel={schreiben ? "Entwurf bearbeiten" : "Neues Schreiben"}
        beschreibung="Das Schreiben bleibt Entwurf, bis es freigegeben wird. Erst dann entsteht die endgültige PDF."
        fuss={<>
          <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
          <Knopf icon="dokument" disabled={!bereit} onClick={() => setVorschau(true)}>Vorschau</Knopf>
          <Knopf variante="pri" laedt={speichern.isPending} disabled={!bereit} onClick={() => speichern.mutate()}>
            Entwurf speichern</Knopf>
        </>}>
        <div className="flex flex-col gap-3.5 min-w-0" data-testid="schreiben-formular">
          <div className="grid gap-3 sm:grid-cols-2">
            <Feld label="Vorlage" fehler={f.vorlage} pflicht hinweis={gewaehlt?.beschreibung || undefined}>
              {(p) => (
                <Auswahl {...p} value={vorlage} onChange={(e) => vorlageWaehlen(e.target.value)}>
                  <option value="">— bitte wählen —</option>
                  <SchreibenOptionen liste={vorlagen.data ?? []} />
                </Auswahl>
              )}
            </Feld>
            <Feld label="Betreff" fehler={f.titel} pflicht>
              {(p) => <Eingabe {...p} value={titel} maxLength={200} placeholder="z. B. Anforderung Laborwerte"
                onChange={(e) => { setTitel(e.target.value); setTitelVonHand(true); }} />}
            </Feld>
          </div>
          {mitTermin ? (
            <Feld label="Termin" fehler={f.termin} pflicht
              hinweis={termine.isSuccess && !terminListe.length ? "Keine offenen Termine – bitte zuerst einen Termin anlegen." : undefined}>
              {(p) => (
                <Auswahl {...p} value={termin} onChange={(e) => setTermin(e.target.value)} disabled={!terminListe.length}>
                  <option value="">— bitte wählen —</option>
                  {terminListe.map((t) => (
                    <option key={t.id} value={t.id}>{terminZeit(t.faellig_am, t.uhrzeit)} · {t.ort_name ?? TERMINARTEN[t.art]} · {t.titel}</option>
                  ))}
                </Auswahl>
              )}
            </Feld>
          ) : null}
          {vorlage === "reisebescheinigung" ? (
            <div className="flex items-end gap-4 flex-wrap">
              <label className="flex items-center gap-2 text-[0.8438rem] pb-2">
                <input type="checkbox" checked={attest} onChange={(e) => setAttest(e.target.checked)} />
                Ärztliches Attest des ADAC anhängen
              </label>
              {attest ? (
                <Feld label="Reisedauer in Tagen" className="w-[12.5rem]" fehler={f.optionen}>
                  {(p) => <Eingabe {...p} className="num" inputMode="numeric" value={tage} maxLength={3}
                    onChange={(e) => setTage(e.target.value.replace(/\D/g, ""))} />}
                </Feld>
              ) : null}
            </div>
          ) : null}
          <Feld label="Empfänger" fehler={f.empfaenger} hinweis="z. B. Hausarzt Dr. Hausmann, Musterstr. 1, 48143 Münster">
            {(p) => <Eingabe {...p} value={empfaenger} maxLength={300} onChange={(e) => setEmpfaenger(e.target.value)} />}
          </Feld>
          <Feld label="Freitext" fehler={f.text}
            hinweis="Steht an der Stelle {{Schreiben.Text}}, sonst vor dem Gruß. Diagnosen, Gewicht und Plan kommen aus der Akte.">
            {(p) => <Textfeld {...p} rows={8} value={text} maxLength={20000} onChange={(e) => setText(e.target.value)}
              className="font-[inherit] leading-snug" />}
          </Feld>
          {speichern.error && !Object.keys(f).length ? <Fehleranzeige fehler={speichern.error} /> : null}
        </div>
      </Dialog>
      <PdfDialog offen={vorschau} onOffen={setVorschau} titel={`Vorschau · ${titel || "Schreiben"}`}
        pfad="korrespondenz/vorschau/" body={koerper} dateiname="Schreiben-Entwurf.pdf" />
    </>
  );
}

// ------------------------------------------------------------------ Freigeben, versendet, Verlauf
function FreigabeDialog({ schreiben, offen, onOffen }: { schreiben: Korrespondenzschreiben | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const freigeben = useMutation({
    mutationFn: () => api<Korrespondenzschreiben>(`korrespondenz/${schreiben!.id}/freigeben/`, { body: {} }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["korrespondenz", patient.id] });
      void qc.invalidateQueries({ queryKey: ["dokumente", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden("Schreiben freigegeben. Die PDF liegt in den Dokumenten.");
      onOffen(false);
    },
  });
  const { reset } = freigeben;
  useEffect(() => { if (offen) reset(); }, [offen, reset]);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Schreiben freigeben" beschreibung={schreiben?.titel}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={freigeben.isPending} onClick={() => freigeben.mutate()} data-testid="freigabe-bestaetigen">Freigeben</Knopf>
      </>}>
      <Meldung art="warn">
        Die Freigabe erzeugt die endgültige PDF mit den heutigen Daten der Akte. Danach lässt sich das Schreiben nicht mehr
        ändern. Eine Korrektur ist ein neuer Entwurf.
      </Meldung>
      <Fehleranzeige fehler={freigeben.error} />
    </Dialog>
  );
}

function VersandDialog({ schreiben, offen, onOffen }: { schreiben: Korrespondenzschreiben | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [weg, setWeg] = useState("");
  const [tag, setTag] = useState("");
  const [notiz, setNotiz] = useState("");
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${schreiben?.id ?? ""}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setWeg("");
    setTag(datum(heuteIso()));
    setNotiz("");
  }
  if (!offen && gesetzt) setGesetzt("");
  const senden = useMutation({
    mutationFn: () => {
      const iso = eingabeDatum(tag);
      if (!iso) throw new ApiFehler(400, "", null, { versendet_am: "Bitte als TT.MM.JJJJ eingeben." });
      return api<Korrespondenzschreiben>(`korrespondenz/${schreiben!.id}/versendet/`,
        { body: { versandweg: weg, versendet_am: iso, versand_notiz: notiz.trim() } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["korrespondenz", patient.id] });
      melden("Als versendet vermerkt.");
      onOffen(false);
    },
  });
  const f: Feldfehler = senden.error instanceof ApiFehler ? senden.error.felder : {};
  const { reset } = senden;
  useEffect(() => { if (offen) reset(); }, [offen, reset]);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Als versendet markieren" beschreibung={schreiben?.titel}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={senden.isPending} disabled={!weg} onClick={() => senden.mutate()}>Speichern</Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-2" data-testid="versand-dialog">
        <Feld label="Weg" fehler={f.versandweg} pflicht>
          {(p) => (
            <Auswahl {...p} value={weg} onChange={(e) => setWeg(e.target.value)}>
              <option value="">— bitte wählen —</option>
              {Object.entries(VERSANDWEGE).map(([w, t]) => <option key={w} value={w}>{t}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Datum" fehler={f.versendet_am} pflicht>
          {(p) => <Eingabe {...p} className="num" value={tag} onChange={(e) => setTag(e.target.value)} />}
        </Feld>
      </div>
      <Feld label="Notiz" fehler={f.versand_notiz} hinweis="z. B. Faxnummer oder Sendungsnummer">
        {(p) => <Eingabe {...p} value={notiz} maxLength={300} onChange={(e) => setNotiz(e.target.value)} />}
      </Feld>
      {senden.error && !Object.keys(f).length ? <Fehleranzeige fehler={senden.error} /> : null}
      <Meldung art="info">Der Vermerk ist danach nicht mehr änderbar.</Meldung>
    </Dialog>
  );
}

type Fassung = { zeitpunkt: string; person: string | null; aktion: string; status: Status;
  aenderungen: { feld: string; name: string; alt: string; neu: string }[] };

function VerlaufDialog({ schreiben, offen, onOffen }: { schreiben: Korrespondenzschreiben | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const verlauf = useQuery({
    queryKey: ["korrespondenz", "verlauf", schreiben?.id],
    queryFn: () => api<Fassung[]>(`korrespondenz/${schreiben!.id}/verlauf/`),
    enabled: offen && !!schreiben,
    staleTime: 0,
  });
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Verlauf des Schreibens" beschreibung={schreiben?.titel} breite={640}
      fuss={<Knopf onClick={() => onOffen(false)}>Schließen</Knopf>}>
      {verlauf.isLoading ? <Laden /> : <Fehleranzeige fehler={verlauf.error} />}
      <ol className="m-0 p-0 list-none flex flex-col gap-2.5" data-testid="schreiben-verlauf">
        {(verlauf.data ?? []).map((e, i) => (
          <li key={i} className="border-b border-rand pb-2 last:border-0 min-w-0">
            <div className="flex items-baseline justify-between gap-2 flex-wrap text-sm">
              <span className="font-medium">{e.aktion}</span>
              <span className="gedaempft text-[0.8125rem] num">{zeitpunkt(e.zeitpunkt)}{e.person ? ` · ${e.person}` : ""}</span>
            </div>
            {e.aenderungen.length ? (
              <ul className="m-0 mt-1 pl-4 text-[0.8125rem] gedaempft break-words">
                {e.aenderungen.map((a) => <li key={a.feld}>{a.name}: {a.alt || "—"} → {a.neu || "—"}</li>)}
              </ul>
            ) : null}
          </li>
        ))}
      </ol>
    </Dialog>
  );
}

// ------------------------------------------------------------------ Reiter
export function Korrespondenz() {
  const { patient, erfassen } = useAkte();
  const { darfBei } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  // Auswahl und Filter in der Adresse (wie ``useWahl``); beide in einem Schritt setzen, sonst überschreibt der zweite
  // Aufruf den ersten
  const [params, setParams] = useSearchParams();
  const wahl = params.get("schreiben") ?? "";
  const filter = (params.get("status") ?? "") as "" | Status;
  const setze = (werte: { schreiben?: string; status?: string }) => setParams((alt) => {
    const neu = new URLSearchParams(alt);
    for (const [k, v] of Object.entries(werte)) if (v) neu.set(k, v); else neu.delete(k);
    return neu;
  }, { replace: true });
  const setWahl = (schreiben: string) => setze({ schreiben });
  const [formular, setFormular] = useState<{ offen: boolean; schreiben: Korrespondenzschreiben | null }>({ offen: false, schreiben: null });
  const [dialog, setDialog] = useState<"" | "freigabe" | "versand" | "verlauf" | "pdf" | "loeschen">("");
  const freigeben = !patient.ist_abgeschlossen && darfBei("schreiben_freigeben", patient);

  const liste = useQuery({
    queryKey: ["korrespondenz", patient.id],
    queryFn: () => api<Korrespondenzschreiben[]>(`korrespondenz/?patient=${patient.id}`),
  });
  const alle = liste.data ?? [];
  const sichtbar = filter ? alle.filter((s) => s.status === filter) : alle;
  const gewaehlt = sichtbar.find((s) => String(s.id) === wahl) ?? sichtbar[0];
  const entwurf = gewaehlt?.status === "entwurf";

  const loeschen = useMutation({
    mutationFn: (s: Korrespondenzschreiben) => api(`korrespondenz/${s.id}/`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["korrespondenz", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden("Entwurf gelöscht.");
      setWahl("");
      setDialog("");
    },
  });
  const kopieren = useMutation({
    mutationFn: (s: Korrespondenzschreiben) => api<Korrespondenzschreiben>(`korrespondenz/${s.id}/kopieren/`, { body: {} }),
    onSuccess: (neu) => {
      void qc.invalidateQueries({ queryKey: ["korrespondenz", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden("Neuer Entwurf angelegt.");
      setze({ status: "", schreiben: String(neu.id) });
    },
    onError: (e) => melden(e.message, "fehler"),
  });
  const anzahl = (s: Status) => alle.filter((x) => x.status === s).length;

  return (
    <>
      <Aktenseite
        testid="korrespondenz"
        titel="Korrespondenz"
        anzahl={alle.length}
        laedt={liste.isPending}
        aktion={erfassen
          ? <Knopf variante="pri" icon="plus" onClick={() => setFormular({ offen: true, schreiben: null })}>Neues Schreiben</Knopf>
          : undefined}
        kopfrechts={<>
          {alle.length ? (
            <div role="group" aria-label="Nach Status filtern" className="segmente !flex !flex-nowrap w-full" data-testid="status-filter">
              {STATUS.map((s) => (
                <button key={s.wert} type="button" className="segment flex-auto justify-center !px-1.5 !gap-1 text-[0.75rem]" aria-pressed={filter === s.wert}
                  onClick={() => setze({ status: s.wert, schreiben: "" })}>
                  {s.text}{s.wert && anzahl(s.wert) ? <span className="num opacity-70">{anzahl(s.wert)}</span> : null}
                </button>
              ))}
            </div>
          ) : null}
          <Fehleranzeige fehler={liste.error} />
        </>}
        liste={
          <Eintragsliste name="Schreiben" leer={sichtbar.length ? undefined
            : alle.length ? "Kein Schreiben mit diesem Status." : "Noch kein Schreiben in dieser Akte."}>
            {sichtbar.map((s) => (
              <Eintrag key={s.id} aktiv={gewaehlt?.id === s.id} onWahl={() => setWahl(String(s.id))} warnung={s.status === "entwurf"}
                datum={<>{datum(s.versendet_am ?? s.freigegeben_am ?? s.erstellt_am)}<FirmaMarke kurz={s.firma_kurz} className="ml-1.5" /></>}
                merkmal={<StatusChip s={s} />}
                zeile={<span className="break-words">{s.titel}</span>}
                unten={[s.empfaenger ? `an ${s.empfaenger}` : "", s.vorlage_name, s.erstellt_von_name].filter(Boolean).join(" · ")} />
            ))}
          </Eintragsliste>
        }
        fuss={<>Freigegebene Schreiben sind unveränderlich; die PDF liegt in den Dokumenten.</>}
        detail={gewaehlt ? (
          <Detail testid="schreiben-detail"
            titel={<span className="flex items-center gap-2 flex-wrap min-w-0"><span className="break-words min-w-0">{gewaehlt.titel}</span>
              <StatusChip s={gewaehlt} /><FirmaMarke kurz={gewaehlt.firma_kurz} /></span>}
            unter={[gewaehlt.vorlage_name + (gewaehlt.vorlage_version ? ` (v${gewaehlt.vorlage_version})` : ""),
              `angelegt am ${datum(gewaehlt.erstellt_am)}${gewaehlt.erstellt_von_name ? ` von ${gewaehlt.erstellt_von_name}` : ""}`,
              gewaehlt.kopie_von ? `Kopie von Nr. ${gewaehlt.kopie_von}` : ""].filter(Boolean).join(" · ")}
            aktionen={<>
              {entwurf && erfassen ? <Knopf klein icon="stift" onClick={() => setFormular({ offen: true, schreiben: gewaehlt })}>Bearbeiten</Knopf> : null}
              {entwurf && freigeben ? <Knopf klein variante="pri" icon="haken" onClick={() => setDialog("freigabe")}>Freigeben</Knopf> : null}
              {gewaehlt.status === "freigegeben" && erfassen
                ? <Knopf klein variante="pri" icon="mail" onClick={() => setDialog("versand")}>Als versendet markieren</Knopf> : null}
              <Knopf klein icon="dokument" onClick={() => setDialog("pdf")}>{entwurf ? "Vorschau" : "PDF öffnen"}</Knopf>
              {!entwurf && erfassen
                ? <Knopf klein icon="kopieren" laedt={kopieren.isPending} onClick={() => kopieren.mutate(gewaehlt)}>Als neuen Entwurf kopieren</Knopf> : null}
              <Knopf klein icon="uhr" onClick={() => setDialog("verlauf")}>Verlauf</Knopf>
              {entwurf && erfassen
                ? <Knopf klein variante="dng" onClick={() => { loeschen.reset(); setDialog("loeschen"); }}>Löschen</Knopf> : null}
            </>}>
            <dl className="m-0 grid grid-cols-[minmax(0,7.5rem)_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm" data-testid="schreiben-angaben">
              <dt className="gedaempft">Empfänger</dt><dd className="m-0 break-words">{gewaehlt.empfaenger || "—"}</dd>
              {gewaehlt.termin_text ? <><dt className="gedaempft">Termin</dt><dd className="m-0">{gewaehlt.termin_text}</dd></> : null}
              {gewaehlt.freigabevermerk ? <><dt className="gedaempft">Freigabe</dt><dd className="m-0">{gewaehlt.freigabevermerk}</dd></> : null}
              {gewaehlt.status === "versendet" ? <>
                <dt className="gedaempft">Versand</dt>
                <dd className="m-0 break-words" data-testid="versand-angabe">{datum(gewaehlt.versendet_am)} · {gewaehlt.versandweg_name}
                  {gewaehlt.versand_notiz ? ` · ${gewaehlt.versand_notiz}` : ""}
                  {gewaehlt.versendet_von_name ? <span className="gedaempft"> (vermerkt von {gewaehlt.versendet_von_name})</span> : null}</dd>
              </> : null}
              {gewaehlt.pdf_sha256 ? <><dt className="gedaempft">Prüfsumme</dt>
                <dd className="m-0 num text-[0.8125rem] gedaempft truncate" title={gewaehlt.pdf_sha256}>SHA-256 {gewaehlt.pdf_sha256.slice(0, 12)}…</dd></> : null}
            </dl>
            <Abschnitt titel="Freitext">
              {gewaehlt.text ? <p className={cx("m-0 text-sm whitespace-pre-wrap break-words leading-relaxed")}>{gewaehlt.text}</p>
                : <Leer>Kein Freitext – der Inhalt kommt aus der Vorlage.</Leer>}
            </Abschnitt>
          </Detail>
        ) : null}
        leer="Links ein Schreiben wählen."
      />
      {erfassen ? <>
        <SchreibenFormular schreiben={formular.schreiben} offen={formular.offen}
          onOffen={(o) => setFormular((d) => ({ ...d, offen: o }))}
          onGespeichert={(s) => setze({ status: "", schreiben: String(s.id) })} />
        <VersandDialog schreiben={gewaehlt ?? null} offen={dialog === "versand"} onOffen={(o) => setDialog(o ? "versand" : "")} />
        <Bestaetigen offen={dialog === "loeschen"} onOffen={(o) => setDialog(o ? "loeschen" : "")} titel="Entwurf löschen" knopf="Löschen"
          text={<>Der Entwurf „{gewaehlt?.titel}“ wird gelöscht.</>} laedt={loeschen.isPending} fehler={loeschen.error}
          onJa={() => gewaehlt && loeschen.mutate(gewaehlt)} />
      </> : null}
      {freigeben ? <FreigabeDialog schreiben={gewaehlt ?? null} offen={dialog === "freigabe"} onOffen={(o) => setDialog(o ? "freigabe" : "")} /> : null}
      <VerlaufDialog schreiben={gewaehlt ?? null} offen={dialog === "verlauf"} onOffen={(o) => setDialog(o ? "verlauf" : "")} />
      <PdfDialog offen={dialog === "pdf" && !!gewaehlt} onOffen={(o) => setDialog(o ? "pdf" : "")}
        titel={gewaehlt ? `${gewaehlt.titel}${gewaehlt.status === "entwurf" ? " (Vorschau)" : ""}` : "Schreiben"}
        pfad={gewaehlt ? `korrespondenz/${gewaehlt.id}/pdf/` : ""}
        dateiname={`Schreiben-${patient.nummer}-${gewaehlt?.id ?? ""}.pdf`} />
    </>
  );
}
