/** Reiter „Datenschutz“ der Akte: Erklärungen nachhalten (wie die Nickelallergie), Anfragen mit Frist, Kopie der Akte,
 *  Aufbewahrung, Verarbeitung einschränken, Akte endgültig löschen. Rechtsgrundlagen: docs/DATENSCHUTZ.md. */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, eingabeDatum, heuteIso, nummer, zeitpunkt } from "@/lib/format";
import { ANFRAGEARTEN, ANFRAGE_ERGEBNISSE, ERKLAERUNGEN } from "@/lib/typen";
import type { AktenDatenschutz, Datenschutzanfrage, Erklaerung, ErklaerungsArt, Patient } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Leer, Meldung, Textfeld } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { PdfDialog } from "@/components/PdfDialog";
import { ZweiFaktorFehlt } from "@/components/ZweiFaktorFehlt";
import { name, useAkte } from "./Akte";

const ARTEN = Object.keys(ERKLAERUNGEN) as ErklaerungsArt[];

function felder(fehler: unknown): Feldfehler {
  return fehler instanceof ApiFehler ? fehler.felder : {};
}

/** Allgemeine Meldung nur, wenn der Fehler an keinem Feld steht */
function Rest({ fehler }: { fehler: unknown }) {
  return fehler && !Object.keys(felder(fehler)).length ? <Fehleranzeige fehler={fehler} /> : null;
}

function useNeuLaden(patient: Patient) {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    void qc.invalidateQueries({ queryKey: ["patienten"] });
    void qc.invalidateQueries({ queryKey: ["startseite"] });
    void qc.invalidateQueries({ queryKey: ["datenschutz"] });
  };
}

/** Datum als TT.MM.JJJJ → ISO; wirft einen Feldfehler, wenn es nicht stimmt */
function isoOderFehler(text: string, feld: string): string {
  const iso = eingabeDatum(text);
  if (!iso) throw new ApiFehler(400, "", null, { [feld]: "Bitte als TT.MM.JJJJ eingeben." });
  return iso;
}

// ------------------------------------------------------------------------------------------------ Erklärungen
function ErfassenDialog({ art, patient, abgeschlossen, offen, onOffen }: {
  art: ErklaerungsArt; patient: Patient; abgeschlossen: boolean; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const [am, setAm] = useState(datum(heuteIso()));
  const [notiz, setNotiz] = useState("");
  const [datei, setDatei] = useState<File | null>(null);
  const eingabe = useRef<HTMLInputElement>(null);
  const neuLaden = useNeuLaden(patient);
  const melden = useHinweis();
  useEffect(() => { if (offen) { setAm(datum(heuteIso())); setNotiz(""); setDatei(null); } }, [offen]);
  const speichern = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("patient", String(patient.id));
      form.append("art", art);
      form.append("erteilt_am", isoOderFehler(am, "erteilt_am"));
      form.append("notiz", notiz.trim());
      if (datei) form.append("datei", datei);
      return api<Erklaerung>("erklaerungen/", { form });
    },
    onSuccess: () => { neuLaden(); melden(`${ERKLAERUNGEN[art]} erfasst.`); onOffen(false); },
  });
  const f = felder(speichern.error);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={`${ERKLAERUNGEN[art]} erfassen`} breite={560}
      beschreibung={art === "datenschutzinformation" ? "Wann hat die Patientin oder der Patient die Information erhalten?"
        : "Wann wurde die Erklärung unterschrieben?"}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Erfassen</Knopf></>}>
      <div className="flex flex-col gap-3" data-testid="erklaerung-erfassen">
        <Feld label={art === "datenschutzinformation" ? "Ausgehändigt am" : "Unterschrieben am"} pflicht fehler={f.erteilt_am}>
          {(p) => <Eingabe {...p} className="num w-40" value={am} onChange={(e) => setAm(e.target.value)} placeholder="TT.MM.JJJJ" />}
        </Feld>
        {abgeschlossen ? (
          <span className="text-[0.8125rem] gedaempft">Die Akte ist abgeschlossen: Ein neues Dokument kann nicht hochgeladen werden. Die Erklärung wird ohne Scan erfasst.</span>
        ) : (
          <div className="feld">
            <span>Unterschriebenes Blatt (Scan, optional)</span>
            <div className="flex items-center gap-2.5 flex-wrap">
              <Knopf icon="hochladen" onClick={() => eingabe.current?.click()}>Datei auswählen</Knopf>
              <span className="text-sm">{datei ? datei.name : <span className="gedaempft">keine Datei gewählt</span>}</span>
              <input ref={eingabe} type="file" hidden aria-label="Unterschriebenes Blatt" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                onChange={(e) => setDatei(e.target.files?.[0] ?? null)} />
            </div>
            {f.datei ? <span className="fehlertext" role="alert">{f.datei}</span>
              : <span className="hinweis">Liegt danach unter „Dokumente“ und ist hier verknüpft.</span>}
          </div>
        )}
        <Feld label="Notiz" fehler={f.notiz} hinweis="z. B. wo das Original liegt">
          {(p) => <Eingabe {...p} value={notiz} maxLength={300} onChange={(e) => setNotiz(e.target.value)} />}
        </Feld>
        <Rest fehler={speichern.error} />
      </div>
    </Dialog>
  );
}

function WiderrufDialog({ erklaerung, patient, offen, onOffen }: {
  erklaerung: Erklaerung; patient: Patient; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const [am, setAm] = useState(datum(heuteIso()));
  const [notiz, setNotiz] = useState("");
  const neuLaden = useNeuLaden(patient);
  const melden = useHinweis();
  useEffect(() => { if (offen) { setAm(datum(heuteIso())); setNotiz(""); } }, [offen]);
  const widerrufen = useMutation({
    mutationFn: () => api<Erklaerung>(`erklaerungen/${erklaerung.id}/widerrufen/`, {
      body: { widerrufen_am: isoOderFehler(am, "widerrufen_am"), notiz: notiz.trim() } }),
    onSuccess: (e) => { neuLaden(); melden(e.hinweis ? `Widerruf eingetragen. ${e.hinweis}` : "Widerruf eingetragen."); onOffen(false); },
  });
  const f = felder(widerrufen.error);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Widerruf eintragen" breite={520}
      beschreibung={`${erklaerung.art_name} vom ${datum(erklaerung.erteilt_am)} · ${name(patient)}`}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={widerrufen.isPending} onClick={() => widerrufen.mutate()}>Widerruf eintragen</Knopf></>}>
      <div className="flex flex-col gap-3" data-testid="erklaerung-widerruf">
        <span className="text-sm">Der Widerruf wirkt für die Zukunft. Die Erklärung bleibt mit Widerruf im Verlauf sichtbar.</span>
        <Feld label="Widerrufen am" pflicht fehler={f.widerrufen_am}>
          {(p) => <Eingabe {...p} className="num w-40" value={am} onChange={(e) => setAm(e.target.value)} />}
        </Feld>
        <Feld label="Notiz" hinweis="z. B. „telefonisch“, „Schreiben vom …“">
          {(p) => <Eingabe {...p} value={notiz} maxLength={300} onChange={(e) => setNotiz(e.target.value)} />}
        </Feld>
        <Rest fehler={widerrufen.error} />
      </div>
    </Dialog>
  );
}

function ErklaerungenKarte({ daten, patient, darf }: { daten: AktenDatenschutz; patient: Patient; darf: boolean }) {
  const [pdf, setPdf] = useState<ErklaerungsArt | null>(null);
  const [erfassen, setErfassen] = useState<ErklaerungsArt | null>(null);
  const [widerruf, setWiderruf] = useState<Erklaerung | null>(null);
  return (
    <Karte className="px-5 py-[18px] flex flex-col gap-3 min-w-0" data-testid="erklaerungen">
      <div className="flex flex-col gap-1">
        <h2 className="lbl m-0 text-[0.9375rem]">Erklärungen</h2>
        <span className="text-[0.8125rem] gedaempft">Vordruck als PDF ausdrucken, unterschreiben lassen und hier erfassen – auf Wunsch mit Scan.</span>
      </div>
      <div className="flex flex-col">
        {ARTEN.map((art) => {
          const s = daten.stand[art];
          const aktuell = daten.erklaerungen.find((e) => e.id === s.id);
          const pflicht = daten.pflicht.includes(art);
          return (
            <div key={art} className="flex items-center justify-between gap-3 flex-wrap py-2.5 border-b border-rand last:border-b-0" data-testid={`erklaerung-${art}`}>
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="font-medium text-sm">{ERKLAERUNGEN[art]}</span>
                <span className="text-[0.8125rem]">
                  {s.status === "liegt_vor" ? <Chip art="ok"><Icon name="haken" />liegt vor seit {datum(s.am)}</Chip>
                    : s.status === "widerrufen" ? <Chip art="fehler">widerrufen am {datum(s.am)}</Chip>
                    : pflicht ? <Chip art="warn"><Icon name="warnung" />nicht erfasst</Chip> : <Chip>nicht erfasst</Chip>}
                  {aktuell?.dokument_titel ? <span className="gedaempft"> · Scan unter „Dokumente“</span> : null}
                  {aktuell?.notiz ? <span className="gedaempft"> · {aktuell.notiz}</span> : null}
                </span>
              </div>
              <div className="flex gap-2 flex-wrap">
                <Knopf klein icon="dokument" onClick={() => setPdf(art)}>Vordruck als PDF</Knopf>
                {darf ? <Knopf klein icon="plus" onClick={() => setErfassen(art)}>Erfassen</Knopf> : null}
                {darf && aktuell && s.status === "liegt_vor" ? <Knopf klein onClick={() => setWiderruf(aktuell)}>Widerruf eintragen</Knopf> : null}
              </div>
            </div>
          );
        })}
      </div>
      {daten.erklaerungen.length ? (
        <details className="text-sm">
          <summary className="cursor-pointer gedaempft">Alle erfassten Erklärungen ({daten.erklaerungen.length})</summary>
          <table className="tabelle mt-2" data-testid="erklaerungen-liste">
            <thead><tr><th className="th">Erklärung</th><th className="th">erteilt am</th><th className="th">Stand</th><th className="th">erfasst</th></tr></thead>
            <tbody>
              {daten.erklaerungen.map((e) => (
                <tr key={e.id}>
                  <td className="td">{e.art_name}</td>
                  <td className="td num">{datum(e.erteilt_am)}</td>
                  <td className="td">{e.widerrufen_am ? `widerrufen am ${datum(e.widerrufen_am)}${e.widerruf_notiz ? ` (${e.widerruf_notiz})` : ""}` : "liegt vor"}</td>
                  <td className="td text-[0.8125rem] gedaempft">{zeitpunkt(e.erfasst_am)}{e.erfasst_von_name ? ` · ${e.erfasst_von_name}` : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ) : null}
      {pdf ? (
        <PdfDialog offen onOffen={(o) => { if (!o) setPdf(null); }} titel={`${ERKLAERUNGEN[pdf]} · ${name(patient)}`}
          pfad={`patienten/${patient.id}/erklaerung-pdf/?art=${pdf}`} dateiname={`${ERKLAERUNGEN[pdf]}-${patient.nummer}.pdf`} />
      ) : null}
      {ARTEN.some((a) => daten.vorlagen[a].entwurf) ? (
        <div className="meldung warn flex gap-2 items-start text-[0.8125rem]" data-testid="vorlage-entwurf">
          <Icon name="warnung" />
          <span>Die Vordrucke {ARTEN.filter((a) => daten.vorlagen[a].entwurf).map((a) => `„${ERKLAERUNGEN[a]}“`).join(", ")} sind noch
            die mitgelieferten Entwürfe mit Lücken und tragen das Wasserzeichen „ENTWURF“. Unter Vorlagen › Dokumentvorlagen
            ausfüllen, prüfen lassen und veröffentlichen.</span>
        </div>
      ) : null}
      {erfassen ? <ErfassenDialog art={erfassen} patient={patient} abgeschlossen={patient.ist_abgeschlossen} offen onOffen={(o) => { if (!o) setErfassen(null); }} /> : null}
      {widerruf ? <WiderrufDialog erklaerung={widerruf} patient={patient} offen onOffen={(o) => { if (!o) setWiderruf(null); }} /> : null}
    </Karte>
  );
}

// ------------------------------------------------------------------------------------------------ Anfragen
function AnfrageDialog({ patient, offen, onOffen }: { patient: Patient; offen: boolean; onOffen: (o: boolean) => void }) {
  const [art, setArt] = useState("auskunft");
  const [am, setAm] = useState(datum(heuteIso()));
  const [von, setVon] = useState("");
  const [inhalt, setInhalt] = useState("");
  const neuLaden = useNeuLaden(patient);
  const melden = useHinweis();
  useEffect(() => { if (offen) { setArt("auskunft"); setAm(datum(heuteIso())); setVon(""); setInhalt(""); } }, [offen]);
  const speichern = useMutation({
    mutationFn: () => api<Datenschutzanfrage>("datenschutzanfragen/", { body: {
      patient: patient.id, art, eingegangen_am: isoOderFehler(am, "eingegangen_am"), gestellt_von: von.trim(), inhalt: inhalt.trim() } }),
    onSuccess: (a) => { neuLaden(); melden(`Anfrage erfasst. Frist: ${datum(a.frist_bis)}.`); onOffen(false); },
  });
  const f = felder(speichern.error);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Datenschutz-Anfrage erfassen" breite={600}
      beschreibung="Zu beantworten unverzüglich, spätestens einen Monat nach Eingang (Art. 12 Abs. 3 DSGVO)."
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Erfassen</Knopf></>}>
      <div className="grid grid-cols-2 gap-3" data-testid="anfrage-erfassen">
        <Feld label="Worum geht es?" fehler={f.art}>
          {(p) => <Auswahl {...p} value={art} onChange={(e) => setArt(e.target.value)}>
            {Object.entries(ANFRAGEARTEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Auswahl>}
        </Feld>
        <Feld label="Eingegangen am" pflicht fehler={f.eingegangen_am}>
          {(p) => <Eingabe {...p} className="num" value={am} onChange={(e) => setAm(e.target.value)} />}
        </Feld>
        <Feld label="Gestellt von" className="col-span-2" fehler={f.gestellt_von} hinweis="z. B. Patientin selbst, Betreuer, Erbin">
          {(p) => <Eingabe {...p} value={von} maxLength={150} onChange={(e) => setVon(e.target.value)} />}
        </Feld>
        <Feld label="Inhalt der Anfrage" className="col-span-2" fehler={f.inhalt}>
          {(p) => <Textfeld {...p} rows={3} value={inhalt} onChange={(e) => setInhalt(e.target.value)} />}
        </Feld>
        <div className="col-span-2"><Rest fehler={speichern.error} /></div>
      </div>
    </Dialog>
  );
}

function VerlaengernDialog({ anfrage, patient, offen, onOffen }: { anfrage: Datenschutzanfrage; patient: Patient; offen: boolean;
  onOffen: (o: boolean) => void }) {
  const [grund, setGrund] = useState("");
  const neuLaden = useNeuLaden(patient);
  const melden = useHinweis();
  const speichern = useMutation({
    mutationFn: () => api<Datenschutzanfrage>(`datenschutzanfragen/${anfrage.id}/`, { method: "PATCH",
      body: { frist_verlaengert: true, verlaengerung_grund: grund.trim() } }),
    onSuccess: (a) => { neuLaden(); melden(`Frist verlängert bis ${datum(a.frist_bis)}.`); onOffen(false); },
  });
  const f = felder(speichern.error);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Frist verlängern" breite={520}
      beschreibung="Um zwei weitere Monate, wenn es wegen Komplexität oder Anzahl der Anfragen nötig ist. Die Person ist innerhalb eines Monats nach Eingang mit Gründen zu unterrichten (Art. 12 Abs. 3 DSGVO)."
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Frist verlängern</Knopf></>}>
      <Feld label="Grund der Verlängerung" pflicht fehler={f.verlaengerung_grund}>
        {(p) => <Textfeld {...p} rows={2} value={grund} maxLength={300} onChange={(e) => setGrund(e.target.value)} />}
      </Feld>
      <Rest fehler={speichern.error} />
    </Dialog>
  );
}

function ErledigenDialog({ anfrage, patient, offen, onOffen }: { anfrage: Datenschutzanfrage; patient: Patient; offen: boolean;
  onOffen: (o: boolean) => void }) {
  const loeschung = anfrage.art === "loeschung";
  const [ergebnis, setErgebnis] = useState(loeschung ? "eingeschraenkt" : "erfuellt");
  const [begruendung, setBegruendung] = useState("");
  const [mitgeteilt, setMitgeteilt] = useState("");
  const neuLaden = useNeuLaden(patient);
  const melden = useHinweis();
  const erledigen = useMutation({
    mutationFn: () => api<Datenschutzanfrage>(`datenschutzanfragen/${anfrage.id}/erledigen/`, { body: {
      ergebnis, begruendung: begruendung.trim(), mitgeteilt_am: mitgeteilt.trim() ? isoOderFehler(mitgeteilt, "mitgeteilt_am") : null } }),
    onSuccess: () => { neuLaden(); melden("Anfrage erledigt."); onOffen(false); },
  });
  const f = felder(erledigen.error);
  const ergebnisse = Object.entries(ANFRAGE_ERGEBNISSE).filter(([k]) => (k === "eingeschraenkt" ? loeschung || anfrage.art === "einschraenkung" : !(loeschung && k === "erfuellt")));
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Anfrage erledigen" breite={600}
      beschreibung={`${anfrage.art_name}, eingegangen am ${datum(anfrage.eingegangen_am)} · Frist ${datum(anfrage.frist_bis)}`}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={erledigen.isPending} onClick={() => erledigen.mutate()}>Erledigen</Knopf></>}>
      <div className="flex flex-col gap-3" data-testid="anfrage-erledigen">
        {loeschung ? (
          <Meldung art="info">Eine Löschung wird mit „Akte endgültig löschen“ erfüllt (unten auf dieser Seite, Mediziner oder Admin). Steht
            eine Aufbewahrungspflicht entgegen, wird stattdessen die Verarbeitung eingeschränkt (Art. 17 Abs. 3 DSGVO, § 35 Abs. 3 BDSG).</Meldung>
        ) : null}
        <Feld label="Ergebnis" fehler={f.ergebnis}>
          {(p) => <Auswahl {...p} value={ergebnis} onChange={(e) => setErgebnis(e.target.value)}>
            {ergebnisse.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Auswahl>}
        </Feld>
        {ergebnis === "eingeschraenkt" ? (
          <span className="text-[0.8125rem] gedaempft">Die Akte erscheint danach nirgends mehr und ist nur mit begründeter Einsicht lesbar. Nur bei abgeschlossenen Akten möglich.</span>
        ) : null}
        <Feld label={ergebnis === "abgelehnt" || ergebnis === "eingeschraenkt" ? "Begründung (wird der Person mitgeteilt)" : "Vermerk"} fehler={f.begruendung}>
          {(p) => <Textfeld {...p} rows={3} value={begruendung} onChange={(e) => setBegruendung(e.target.value)} />}
        </Feld>
        <Feld label="Der Person mitgeteilt am" fehler={f.mitgeteilt_am} hinweis="TT.MM.JJJJ – leer, wenn noch nicht mitgeteilt">
          {(p) => <Eingabe {...p} className="num w-40" value={mitgeteilt} onChange={(e) => setMitgeteilt(e.target.value)} />}
        </Feld>
        <Rest fehler={erledigen.error} />
      </div>
    </Dialog>
  );
}

function AnfragenKarte({ daten, patient, darf, entscheiden }: { daten: AktenDatenschutz; patient: Patient; darf: boolean; entscheiden: boolean }) {
  const [neu, setNeu] = useState(false);
  const [verlaengern, setVerlaengern] = useState<Datenschutzanfrage | null>(null);
  const [erledigen, setErledigen] = useState<Datenschutzanfrage | null>(null);
  return (
    <Karte className="px-5 py-[18px] flex flex-col gap-3 min-w-0" data-testid="anfragen">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className="lbl m-0 text-[0.9375rem]">Anfragen der betroffenen Person</h2>
          <span className="text-[0.8125rem] gedaempft">Auskunft, Berichtigung, Löschung, Einschränkung, Widerruf – jede Anfrage als Vorgang mit Frist.</span>
        </div>
        {darf ? <Knopf klein icon="plus" onClick={() => setNeu(true)}>Anfrage erfassen</Knopf> : null}
      </div>
      {daten.anfragen.length ? (
        <table className="tabelle" data-testid="anfragen-liste">
          <thead><tr><th className="th">Anfrage</th><th className="th">eingegangen</th><th className="th">Frist / Ergebnis</th><th className="th" /></tr></thead>
          <tbody>
            {daten.anfragen.map((a) => (
              <tr key={a.id}>
                <td className="td align-top">
                  <span className="font-medium">{a.art_name}</span>
                  {a.gestellt_von ? <span className="gedaempft"> · {a.gestellt_von}</span> : null}
                  {a.inhalt ? <div className="text-[0.8125rem] gedaempft whitespace-pre-line">{a.inhalt}</div> : null}
                </td>
                <td className="td num align-top">{datum(a.eingegangen_am)}</td>
                <td className="td align-top">
                  {a.ist_offen ? (
                    <Chip art={a.ueberfaellig ? "fehler" : "warn"}>{a.ueberfaellig ? "überfällig seit" : "offen bis"} {datum(a.frist_bis)}{a.frist_verlaengert ? " (verlängert)" : ""}</Chip>
                  ) : (
                    <span className="text-sm">{a.ergebnis_name}{a.mitgeteilt_am ? ` · mitgeteilt am ${datum(a.mitgeteilt_am)}` : ""}
                      {a.begruendung ? <span className="block text-[0.8125rem] gedaempft whitespace-pre-line">{a.begruendung}</span> : null}
                      <span className="block text-[0.8125rem] gedaempft">erledigt {zeitpunkt(a.erledigt_am)}{a.erledigt_von_name ? ` · ${a.erledigt_von_name}` : ""}</span>
                    </span>
                  )}
                </td>
                <td className="td align-top">
                  {a.ist_offen ? (
                    <div className="flex gap-2 flex-wrap justify-end">
                      {darf && !a.frist_verlaengert ? <Knopf klein onClick={() => setVerlaengern(a)}>Frist verlängern</Knopf> : null}
                      {entscheiden ? <Knopf klein variante="pri" onClick={() => setErledigen(a)}>Erledigen</Knopf> : null}
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <Leer>Keine Anfragen.</Leer>}
      {darf ? <AnfrageDialog patient={patient} offen={neu} onOffen={setNeu} /> : null}
      {verlaengern ? <VerlaengernDialog anfrage={verlaengern} patient={patient} offen onOffen={(o) => { if (!o) setVerlaengern(null); }} /> : null}
      {erledigen ? <ErledigenDialog anfrage={erledigen} patient={patient} offen onOffen={(o) => { if (!o) setErledigen(null); }} /> : null}
    </Karte>
  );
}

// ------------------------------------------------------------------------------------------------ Aufbewahrung, Kopie, Einschränkung, Löschen
function GrundDialog({ titel, beschreibung, knopf, gefaehrlich, offen, onOffen, onAbsenden, laedt, fehler, children, testid }: {
  titel: string; beschreibung: ReactNode; knopf: string; gefaehrlich?: boolean; offen: boolean; onOffen: (o: boolean) => void;
  onAbsenden: (grund: string) => void; laedt: boolean; fehler: unknown; children?: ReactNode; testid: string;
}) {
  const [grund, setGrund] = useState("");
  useEffect(() => { if (offen) setGrund(""); }, [offen]);
  const f = felder(fehler);
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={titel} breite={560} beschreibung={beschreibung}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante={gefaehrlich ? "dng" : "pri"} laedt={laedt} disabled={grund.trim().length < 10} onClick={() => onAbsenden(grund.trim())}>{knopf}</Knopf></>}>
      <div className="flex flex-col gap-3" data-testid={testid}>
        {children}
        <Feld label="Grund" pflicht fehler={f.grund} hinweis="mindestens 10 Zeichen · steht im Audit-Log">
          {(p) => <Textfeld {...p} rows={2} value={grund} maxLength={300} onChange={(e) => setGrund(e.target.value)} />}
        </Feld>
        <Rest fehler={fehler} />
      </div>
    </Dialog>
  );
}

function AkteLoeschenDialog({ patient, offen, onOffen }: { patient: Patient; offen: boolean; onOffen: (o: boolean) => void }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [grund, setGrund] = useState("");
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  const zweiterFaktor = !!useAuth().ich?.zweiter_faktor;
  const [bestaetigung, setBestaetigung] = useState("");
  type Vorbereitung = { code: string; gueltig_bis: string; loeschen: AktenDatenschutz["loeschen"]; umfang: Record<string, number> };
  const vorbereiten = useMutation({
    mutationFn: () => api<Vorbereitung>(`patienten/${patient.id}/loeschen-vorbereiten/`, { method: "POST" }),
  });
  const { mutate: vorbereitenStarten, reset: vorbereitenZuruecksetzen } = vorbereiten;
  useEffect(() => {
    if (!offen) return;
    setGrund(""); setKennwort(""); setCode(""); setBestaetigung("");
    vorbereitenZuruecksetzen();
    vorbereitenStarten();
  }, [offen, vorbereitenStarten, vorbereitenZuruecksetzen]);
  const loeschen = useMutation({
    mutationFn: () => api(`patienten/${patient.id}/loeschen/`, { body: { grund: grund.trim(), kennwort, code: code.trim(), bestaetigung } }),
    onSuccess: () => {
      melden(`Akte Nr. ${nummer(patient.nummer)} endgültig gelöscht.`);
      onOffen(false);
      navigate("/patienten?status=abgeschlossen", { replace: true });
      qc.removeQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      void qc.invalidateQueries({ queryKey: ["datenschutz"] });
    },
    onError: () => { setKennwort(""); setCode(""); },
  });
  const f = felder(loeschen.error);
  const abgelaufen = /abgelaufen|neuen anfordern/.test(f.bestaetigung ?? "");
  const u = vorbereiten.data?.umfang;
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Akte endgültig löschen" breite={640}
      beschreibung={`${name(patient)} · Nr. ${nummer(patient.nummer)}`}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={loeschen.isPending} onClick={() => loeschen.mutate()}
          disabled={!vorbereiten.data || grund.trim().length < 10 || !zweiterFaktor || !kennwort || code.trim().length < 6 || bestaetigung.trim().length < 6}>Akte endgültig löschen</Knopf></>}>
      <div className="flex flex-col gap-3" data-testid="akte-loeschen">
        <Meldung art="fehler">Die Akte wird mit allen Einträgen, Infusionsplänen, Dokumenten und ihrem gesamten Verlauf
          unwiederbringlich gelöscht. Es bleiben das Löschprotokoll (Patientennummer, Daten zu Abschluss und Frist, Rechtsgrund,
          Ihr Grund, Umfang in Zahlen – kein Name) und die Einträge im Audit-Log ohne Namen und Inhalte. Ältere Sicherungen enthalten die Akte noch bis zu ihrem Ablauf; nach
          einer Wiederherstellung wird sie automatisch erneut gelöscht.</Meldung>
        {vorbereiten.data ? <Meldung art={vorbereiten.data.loeschen.rechtsgrund === "frist" ? "info" : "warn"}>{vorbereiten.data.loeschen.hinweis}</Meldung> : null}
        {u ? (
          <span className="text-[0.8125rem] gedaempft" data-testid="loesch-umfang">
            Gelöscht werden: {u.kontakte} Kontakte, {u.gewichte} Gewichte, {u.termine} Termine, {u.infusionsplaene} Infusionspläne,{" "}
            {u.dokumente} Dokumente, {u.erklaerungen} Erklärungen, {u.anfragen} Anfragen.
          </span>
        ) : null}
        <Feld label="Grund" fehler={f.grund} hinweis="mindestens 10 Zeichen · ohne Namen – der Grund bleibt im Löschprotokoll">
          {(p) => <Textfeld {...p} rows={2} value={grund} onChange={(e) => setGrund(e.target.value)} />}
        </Feld>
        <ZweiFaktorFehlt />
        <div className="grid grid-cols-2 gap-3">
          <Feld label="Kennwort" fehler={f.kennwort}>{(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}</Feld>
          <Feld label="Code aus der Authenticator-App" fehler={f.code}>{(p) => <Eingabe {...p} inputMode="numeric" autoComplete="one-time-code" className="num" value={code} onChange={(e) => setCode(e.target.value)} />}</Feld>
        </div>
        <div className="flex items-end gap-3 flex-wrap">
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium">Bestätigungscode</span>
            <span data-testid="bestaetigungscode" aria-label={vorbereiten.data ? `Bestätigungscode ${vorbereiten.data.code.split("").join(" ")}` : undefined}
              className="select-none font-mono text-[1.375rem] font-semibold tracking-[0.3em] px-3 py-1 rounded-md bg-fein border border-rand">
              {vorbereiten.data?.code ?? "······"}</span>
          </div>
          <Feld label="Code abtippen" fehler={f.bestaetigung} className="flex-1 min-w-[160px]">
            {(p) => <Eingabe {...p} autoComplete="off" className="font-mono uppercase tracking-[0.2em]" value={bestaetigung} onChange={(e) => setBestaetigung(e.target.value)} />}
          </Feld>
        </div>
        {abgelaufen ? <Knopf klein className="self-start" onClick={() => { loeschen.reset(); setBestaetigung(""); vorbereitenStarten(); }}>Neuen Bestätigungscode anfordern</Knopf> : null}
        <Fehleranzeige fehler={vorbereiten.error} />
        <Rest fehler={loeschen.error} />
      </div>
    </Dialog>
  );
}

function AufbewahrungKarte({ daten, patient, darf, entscheiden, loeschenErlaubt }: {
  daten: AktenDatenschutz; patient: Patient; darf: boolean; entscheiden: boolean; loeschenErlaubt: boolean;
}) {
  const neuLaden = useNeuLaden(patient);
  const melden = useHinweis();
  const [dialog, setDialog] = useState<"" | "verlaengern" | "einschraenken" | "aufheben" | "loeschen">("");
  const [bis, setBis] = useState("");
  const [unterrichtet, setUnterrichtet] = useState("");
  const [entfaellt, setEntfaellt] = useState("");
  useEffect(() => { if (dialog) { setBis(""); setUnterrichtet(""); setEntfaellt(""); } }, [dialog]);
  const zu = () => setDialog("");
  const a = daten.aufbewahrung;
  const verlaengern = useMutation({
    mutationFn: (grund: string | null) => api(`patienten/${patient.id}/aufbewahrung/`, { body: grund === null ? { bis: null }
      : { bis: isoOderFehler(bis, "bis"), grund } }),
    onSuccess: (_d, grund) => { neuLaden(); melden(grund === null ? "Verlängerung zurückgenommen." : "Aufbewahrung verlängert."); zu(); },
  });
  const einschraenken = useMutation({
    mutationFn: (grund: string) => api(`patienten/${patient.id}/einschraenken/`, { body: { grund } }),
    onSuccess: () => { neuLaden(); melden("Verarbeitung eingeschränkt."); zu(); },
  });
  const aufheben = useMutation({
    mutationFn: (grund: string) => api(`patienten/${patient.id}/einschraenkung-aufheben/`, { body: {
      grund, unterrichtet_am: unterrichtet.trim() ? isoOderFehler(unterrichtet, "unterrichtet_am") : null, unterrichtung_entfaellt: entfaellt.trim() } }),
    onSuccess: () => { neuLaden(); melden("Einschränkung aufgehoben."); zu(); },
  });
  const fv = felder(verlaengern.error);
  const fa = felder(aufheben.error);
  return (
    <Karte className="px-5 py-[18px] flex flex-col gap-4 min-w-0" data-testid="aufbewahrung">
      <div className="flex flex-col gap-2">
        <h2 className="lbl m-0 text-[0.9375rem]">Aufbewahrung</h2>
        {patient.ist_abgeschlossen && a.bis ? (
          <span className="text-sm" data-testid="aufbewahrung-stand">
            Abgeschlossen am {datum(patient.abgeschlossen_am)} · Aufbewahrung {a.jahre} Jahre, bis <strong className="num">{datum(a.bis)}</strong>
            {a.abgelaufen ? <> <Chip art="warn">Frist abgelaufen</Chip></> : null}
            {a.beginn && a.beginn !== patient.abgeschlossen_am ? <span className="gedaempft"> · gerechnet ab dem letzten Kontakt am {datum(a.beginn)} (er liegt nach dem Abschlussdatum)</span> : null}
            {a.verlaengert_bis && a.bis === a.verlaengert_bis ? <span className="gedaempft"> · im Einzelfall verlängert (regulär bis {datum(a.regulaer_bis)}): {a.grund}</span> : null}
          </span>
        ) : (
          <span className="text-sm gedaempft">Die Frist ({a.jahre} Jahre) beginnt mit dem Abschluss der Akte. Danach kann die Akte gelöscht werden.</span>
        )}
        {entscheiden && patient.ist_abgeschlossen ? (
          <div className="flex gap-2 flex-wrap">
            <Knopf klein onClick={() => setDialog("verlaengern")}>Im Einzelfall länger aufbewahren</Knopf>
            {a.verlaengert_bis ? <Knopf klein variante="geist" laedt={verlaengern.isPending && verlaengern.variables === null} onClick={() => verlaengern.mutate(null)}>Verlängerung zurücknehmen</Knopf> : null}
          </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-2 border-t border-rand pt-3">
        <h2 className="lbl m-0 text-[0.9375rem]">Kopie der Akte</h2>
        <span className="text-[0.8125rem] gedaempft">Vollständige Kopie zur Aushändigung (Art. 15 Abs. 3 DSGVO): Akte und Verlauf als PDF, alle Dokumente im Original, als ZIP-Datei.</span>
        {darf ? <a className="btn sec klein self-start" href={`/api/patienten/${patient.id}/kopie/`} download data-testid="kopie"
          onClick={() => window.setTimeout(neuLaden, 4000)}><Icon name="herunterladen" />Kopie herunterladen</a> : null}
        {daten.kopien.length ? (
          <span className="text-[0.8125rem]" data-testid="kopien">Bisher erstellt: {daten.kopien.map((k) => `${zeitpunkt(k.zeitpunkt)}${k.person ? ` (${k.person})` : ""}`).join(" · ")}</span>
        ) : <span className="text-[0.8125rem] gedaempft">Noch keine Kopie erstellt.</span>}
      </div>

      <div className="flex flex-col gap-2 border-t border-rand pt-3">
        <h2 className="lbl m-0 text-[0.9375rem]">Verarbeitung einschränken</h2>
        {daten.einschraenkung ? (
          <Meldung art="warn">Eingeschränkt seit {zeitpunkt(daten.einschraenkung.am)}{daten.einschraenkung.von ? ` durch ${daten.einschraenkung.von}` : ""}. Grund: {daten.einschraenkung.grund}</Meldung>
        ) : (
          <span className="text-[0.8125rem] gedaempft">Wenn gelöscht werden soll, die Akte aber noch aufbewahrt werden muss (Art. 18 DSGVO, § 35 Abs. 3 BDSG):
            Die Akte bleibt gespeichert, erscheint aber nirgends mehr und ist nur mit begründeter Einsicht lesbar. Nur bei abgeschlossenen Akten.</span>
        )}
        {entscheiden ? (
          daten.einschraenkung
            ? <Knopf klein className="self-start" onClick={() => setDialog("aufheben")}>Einschränkung aufheben</Knopf>
            : patient.ist_abgeschlossen ? <Knopf klein className="self-start" onClick={() => setDialog("einschraenken")}>Verarbeitung einschränken</Knopf> : null
        ) : null}
      </div>

      {loeschenErlaubt ? (
        <div className="flex flex-col gap-2 border-t border-rand pt-3" data-testid="loeschen-bereich">
          <h2 className="lbl m-0 text-[0.9375rem]">Akte endgültig löschen</h2>
          <span className="text-[0.8125rem] gedaempft">{daten.loeschen.hinweis}</span>
          {daten.loeschen.moeglich ? <Knopf klein variante="dng" className="self-start" onClick={() => setDialog("loeschen")}>Akte endgültig löschen …</Knopf> : null}
        </div>
      ) : null}

      <GrundDialog titel="Im Einzelfall länger aufbewahren" knopf="Verlängern" testid="aufbewahrung-verlaengern"
        beschreibung="Zum Beispiel bei einem laufenden Verfahren. Die reguläre Frist bleibt; es gilt das spätere Datum."
        offen={dialog === "verlaengern"} onOffen={(o) => setDialog(o ? "verlaengern" : "")} laedt={verlaengern.isPending}
        fehler={verlaengern.error} onAbsenden={(g) => verlaengern.mutate(g)}>
        <Feld label="Aufbewahren bis" pflicht fehler={fv.bis}>
          {(p) => <Eingabe {...p} className="num w-40" value={bis} onChange={(e) => setBis(e.target.value)} placeholder="TT.MM.JJJJ" />}
        </Feld>
      </GrundDialog>
      <GrundDialog titel="Verarbeitung einschränken" knopf="Einschränken" gefaehrlich testid="einschraenken"
        beschreibung={`${name(patient)} · Die Akte erscheint danach in keiner Liste und keiner Suche mehr – auch nicht für Sie. Lesbar ist sie nur mit begründeter Einsicht (60 Minuten, im Audit-Log). In der Übersicht „Datenschutz“ bleibt sie mit Nummer aufgeführt; den Namen sieht dort nur, wer Einsicht nehmen darf.`}
        offen={dialog === "einschraenken"} onOffen={(o) => setDialog(o ? "einschraenken" : "")} laedt={einschraenken.isPending}
        fehler={einschraenken.error} onAbsenden={(g) => einschraenken.mutate(g)} />
      <GrundDialog titel="Einschränkung aufheben" knopf="Aufheben" testid="einschraenkung-aufheben"
        beschreibung="Vor dem Aufheben wird die betroffene Person unterrichtet (Art. 18 Abs. 3 DSGVO)."
        offen={dialog === "aufheben"} onOffen={(o) => setDialog(o ? "aufheben" : "")} laedt={aufheben.isPending}
        fehler={aufheben.error} onAbsenden={(g) => aufheben.mutate(g)}>
        <Feld label="Person unterrichtet am" fehler={fa.unterrichtet_am}>
          {(p) => <Eingabe {...p} className="num w-40" value={unterrichtet} onChange={(e) => setUnterrichtet(e.target.value)} placeholder="TT.MM.JJJJ" />}
        </Feld>
        <Feld label="… oder: Warum entfällt die Unterrichtung?" hinweis="z. B. verstorben, keine Anschrift bekannt (mindestens 10 Zeichen)">
          {(p) => <Eingabe {...p} value={entfaellt} onChange={(e) => setEntfaellt(e.target.value)} />}
        </Feld>
      </GrundDialog>
      {loeschenErlaubt ? <AkteLoeschenDialog patient={patient} offen={dialog === "loeschen"} onOffen={(o) => setDialog(o ? "loeschen" : "")} /> : null}
    </Karte>
  );
}

export function AkteDatenschutz() {
  const { patient } = useAkte();
  const { darfBei } = useAuth();
  const daten = useQuery({
    queryKey: ["patient", patient.id, "datenschutz"],
    queryFn: () => api<AktenDatenschutz>(`patienten/${patient.id}/datenschutz/`),
  });
  if (daten.isLoading) return <Laden />;
  if (!daten.data) return <Fehleranzeige fehler={daten.error ?? "Nicht geladen."} />;
  const darf = darfBei("datenschutz_bearbeiten", patient);
  const entscheiden = darfBei("datenschutz_entscheiden", patient);
  // Recht „Akten endgültig löschen“: Mediziner und Admin, Admins auch bei echten Akten (Festlegung 02.10.2026)
  const loeschenErlaubt = darfBei("akten_loeschen", patient);
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start" data-testid="akte-datenschutz">
      <div className="flex flex-col gap-5 min-w-0">
        <ErklaerungenKarte daten={daten.data} patient={patient} darf={darf} />
        <AnfragenKarte daten={daten.data} patient={patient} darf={darf} entscheiden={entscheiden} />
      </div>
      <AufbewahrungKarte daten={daten.data} patient={patient} darf={darf} entscheiden={entscheiden} loeschenErlaubt={loeschenErlaubt} />
    </div>
  );
}
