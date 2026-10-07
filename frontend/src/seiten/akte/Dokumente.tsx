/** Entwurf 9 · Dokumente: Hochladen (Typ am Inhalt geprüft), Vorschau, Metadaten, Altdokumente prüfen, ausblenden. */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, alle, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuswahl } from "@/lib/daten";
import { dateigroesse, datum, eingabeDatum, zeitpunkt } from "@/lib/format";
import type { Dokument, PatientZeile } from "@/lib/typen";
import { useAuth } from "@/lib/auth";
import { PatientWahl } from "@/components/PatientWahl";
import { ZweiFaktorFehlt } from "@/components/ZweiFaktorFehlt";
import { Anzeige, Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Knopf, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Dialog } from "@/components/ui/dialog";
import { PdfLeser, PdfVorschau } from "@/components/PdfAnsicht";
import { name, useAkte } from "./Akte";
import { Aktenseite, Detail, Eintrag, Eintragsliste } from "./Aktenseite";

const DATUMSQUELLE: Record<string, string> = {
  eingabe: "eingegeben", pdf: "aus PDF-Metadaten", exif: "aus EXIF", dateidatum: "Dateidatum (keine Metadaten)",
};

function quelle(d: Dokument) {
  if (d.herkunft === "altsystem") return `Altsystem · Datum ${DATUMSQUELLE[d.datum_quelle] ?? d.datum_quelle}`;
  if (d.herkunft === "system") return `Im System erzeugt am ${zeitpunkt(d.hochgeladen_am)}`;
  return `Hochgeladen am ${zeitpunkt(d.hochgeladen_am)}`;
}

function dateiUrl(d: Dokument, anzeigen: boolean) {
  return `/api/dokumente/${d.id}/datei/${anzeigen ? "?anzeigen=1" : ""}`;
}

function istPdf(dok: Dokument) {
  return dok.mime === "application/pdf";
}

function Vorschau({ dok }: { dok: Dokument }) {
  if (dok.mime.startsWith("image/")) {
    return <img src={dateiUrl(dok, true)} alt={dok.titel} className="w-full max-h-[320px] object-contain rounded-lg border border-rand bg-fein" />;
  }
  if (istPdf(dok)) {
    // eigene Anzeige statt PDF-Programm des Browsers (Adobe Reader blendet dort eine schwarze Leiste ein)
    return <PdfVorschau url={dateiUrl(dok, true)} titel={dok.titel} />;
  }
  if (dok.mime.startsWith("text/")) {
    return <iframe title={`Vorschau ${dok.titel}`} src={dateiUrl(dok, true)} className="w-full h-[320px] rounded-lg border border-rand bg-white" />;
  }
  return <div className="h-[120px] flex items-center justify-center text-sm gedaempft border border-dashed border-rand rounded-lg">Keine Vorschau</div>;
}

/** Falscher Patient: Dokument dem richtigen Patienten zuordnen (Festlegung 02.10.2026). */
function UmhaengenDialog({ dok, offen, onOffen }: { dok: Dokument; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [ziel, setZiel] = useState<PatientZeile | null>(null);
  const [grund, setGrund] = useState("");
  const [geprueft, setGeprueft] = useState(false);
  useEffect(() => { if (offen) { setZiel(null); setGrund(""); setGeprueft(false); } }, [offen]);
  const umhaengen = useMutation({
    mutationFn: () => api<Dokument>(`dokumente/${dok.id}/umhaengen/`, { body: { patient: ziel?.id, grund: grund.trim() } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden(`Dokument ${ziel ? name(ziel) : ""} zugeordnet.`);
      onOffen(false);
    },
  });
  const f: Feldfehler = umhaengen.error instanceof ApiFehler ? umhaengen.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Dokument dem richtigen Patienten zuordnen" breite={620}
      beschreibung={`„${dok.titel}“ ist bei ${name(patient)} abgelegt.`}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={umhaengen.isPending} disabled={!ziel || grund.trim().length < 5 || !geprueft} onClick={() => umhaengen.mutate()}>Zuordnen</Knopf></>}>
      <div className="flex flex-col gap-3" data-testid="umhaengen">
        <Feld label="Richtiger Patient" fehler={f.patient}>
          {(p) => <PatientWahl id={p.id} wert={ziel} onWahl={(z) => { setZiel(z); setGeprueft(false); }} fehler={!!f.patient}
            test={patient.ist_test ? "nur" : "ohne"} ohne={patient.id} />}
        </Feld>
        <Feld label="Grund" fehler={f.grund} hinweis="z. B. „beim falschen Patienten hochgeladen“">
          {(p) => <Textfeld {...p} rows={2} value={grund} onChange={(e) => setGrund(e.target.value)} />}
        </Feld>
        {ziel ? (
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={geprueft} onChange={(e) => setGeprueft(e.target.checked)} className="mt-1" />
            <span>Ich habe geprüft, dass das Dokument zu <strong>{name(ziel)}</strong> (Nr. {ziel.nummer}, geboren {datum(ziel.geburtsdatum)}) gehört.</span>
          </label>
        ) : null}
        <span className="text-[0.8125rem] gedaempft leading-normal">
          Datei und Prüfsumme bleiben unverändert. Hier im Verlauf steht danach nur „einer anderen Akte zugeordnet“ – ohne Titel
          und ohne den anderen Patienten. Beim richtigen Patienten steht „von einer anderen Akte übernommen“ mit Grund. Das
          Audit-Log hält den Vorgang vollständig fest.
        </span>
        {umhaengen.error && !Object.keys(f).length ? <Fehleranzeige fehler={umhaengen.error} /> : null}
      </div>
    </Dialog>
  );
}

/** Endgültig löschen: Mediziner und Admin (auch bei echten Akten), mit Kennwort, Code aus der Authenticator-App und abgetipptem Bestätigungscode. */
function LoeschenDialog({ dok, offen, onOffen }: { dok: Dokument; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [grund, setGrund] = useState("");
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  const zweiterFaktor = !!useAuth().ich?.zweiter_faktor;
  const [bestaetigung, setBestaetigung] = useState("");
  const vorbereiten = useMutation({
    mutationFn: () => api<{ code: string; gueltig_bis: string }>(`dokumente/${dok.id}/loeschen-vorbereiten/`, { method: "POST" }),
  });
  const { mutate: vorbereitenStarten, reset: vorbereitenZuruecksetzen } = vorbereiten;
  useEffect(() => {
    if (!offen) return;
    setGrund(""); setKennwort(""); setCode(""); setBestaetigung("");
    vorbereitenZuruecksetzen();
    vorbereitenStarten();
  }, [offen, vorbereitenStarten, vorbereitenZuruecksetzen]);
  const loeschen = useMutation({
    mutationFn: () => api(`dokumente/${dok.id}/loeschen/`, { body: { grund: grund.trim(), kennwort, code: code.trim(), bestaetigung } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden("Dokument endgültig gelöscht.");
      onOffen(false);
    },
    onError: () => { setKennwort(""); setCode(""); },
  });
  const f: Feldfehler = loeschen.error instanceof ApiFehler ? loeschen.error.felder : {};
  const abgelaufen = /abgelaufen|neuen anfordern/.test(f.bestaetigung ?? "");
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Dokument endgültig löschen" breite={600}
      beschreibung={`„${dok.titel}“ bei ${name(patient)}`}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={loeschen.isPending} onClick={() => loeschen.mutate()}
          disabled={!vorbereiten.data || grund.trim().length < 10 || !zweiterFaktor || !kennwort || code.trim().length < 6 || bestaetigung.trim().length < 6}>Endgültig löschen</Knopf></>}>
      <div className="flex flex-col gap-3" data-testid="loeschen">
        <Meldung art="fehler">Datei, Inhalt, Titel, Dateiname, Notiz und Datum werden unwiederbringlich gelöscht – auch aus Historie und Audit-Log (Art. 17 DSGVO). Es bleibt nur der Nachweis ohne Inhalt: im Verlauf „endgültig gelöscht“ mit Grund, im Audit-Log Dokumentnummer, Typ, Prüfsumme, Person und Zeitpunkt. Ältere Sicherungen enthalten das Dokument noch bis zu ihrem Ablauf; nach einer Wiederherstellung wird es automatisch erneut gelöscht. Gehört das Dokument einem anderen Patienten der Stiftung, bitte stattdessen „Anderem Patienten zuordnen“.</Meldung>
        <Feld label="Grund" fehler={f.grund} hinweis="mindestens 10 Zeichen · ohne Namen oder Gesundheitsangaben der fremden Person – der Grund bleibt im Protokoll">
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
            {/* abtippen statt kopieren: nicht markierbar */}
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
        {loeschen.error && !Object.keys(f).length ? <Fehleranzeige fehler={loeschen.error} /> : null}
      </div>
    </Dialog>
  );
}

function Details({ dok }: { dok: Dokument }) {
  const { patient, erfassen } = useAkte();
  const { darfBei } = useAuth();
  const [falsch, setFalsch] = useState<"umhaengen" | "loeschen" | null>(null);
  const umhaengenErlaubt = dok.herkunft !== "system" && !patient.ist_abgeschlossen && darfBei("dokumente_umhaengen", patient);
  const loeschenErlaubt = dok.herkunft !== "system" && !patient.ist_abgeschlossen && darfBei("dokumente_loeschen", patient);
  const typen = useAuswahl("dokumenttyp", false);
  const [titel, setTitel] = useState(dok.titel);
  const [typ, setTyp] = useState(dok.typ ? String(dok.typ) : "");
  const [am, setAm] = useState(dok.datum ? datum(dok.datum) : "");
  const [notiz, setNotiz] = useState(dok.notiz);
  const [lesen, setLesen] = useState(false);
  const qc = useQueryClient();
  const melden = useHinweis();
  useEffect(() => {
    setTitel(dok.titel); setTyp(dok.typ ? String(dok.typ) : ""); setAm(dok.datum ? datum(dok.datum) : ""); setNotiz(dok.notiz);
  }, [dok]);
  const neuLaden = () => {
    void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    void qc.invalidateQueries({ queryKey: ["startseite"] });
  };
  const speichern = useMutation({
    mutationFn: (art: "speichern" | "pruefen" | "ausblenden" | "einblenden") => {
      if (art === "ausblenden" || art === "einblenden") {
        return api<Dokument>(`dokumente/${dok.id}/`, { method: "PATCH", body: { ausgeblendet: art === "ausblenden" } });
      }
      const iso = am.trim() ? eingabeDatum(am) : null;
      if (am.trim() && !iso) throw new ApiFehler(400, "", null, { datum: "Bitte als TT.MM.JJJJ eingeben." });
      const daten = { titel: titel.trim(), typ: typ ? Number(typ) : null, datum: iso };
      if (art === "pruefen") return api<Dokument>(`dokumente/${dok.id}/geprueft/`, { body: daten });
      return api<Dokument>(`dokumente/${dok.id}/`, { method: "PATCH", body: { ...daten, notiz } });
    },
    onSuccess: (_d, art) => {
      neuLaden();
      melden({ speichern: "Dokument gespeichert.", pruefen: "Typ und Datum bestätigt.", ausblenden: "Dokument ausgeblendet.", einblenden: "Dokument wieder eingeblendet." }[art]);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Detail testid="dokument-details" titel={dok.titel}
      unter={`${quelle(dok)}${dok.hochgeladen_von_name ? ` · ${dok.hochgeladen_von_name}` : ""}`}
      aktionen={<>
        {istPdf(dok)
          ? <Knopf klein variante="pri" icon="auge" onClick={() => setLesen(true)}>Öffnen</Knopf>
          : <a className="btn pri klein" href={dateiUrl(dok, true)} target="_blank" rel="noopener"><Icon name="auge" />Öffnen</a>}
        <a className="btn sec klein" href={dateiUrl(dok, false)} download><Icon name="herunterladen" />Herunterladen</a>
      </>}>
      <Vorschau dok={dok} />
      {!dok.typ_geprueft && erfassen ? (
        <div className="meldung warn flex gap-2 items-start text-[0.8125rem]"><Icon name="warnung" /><span>Aus dem Altsystem übernommen. Bitte Typ und Datum prüfen.</span></div>
      ) : null}
      {dok.ausgeblendet ? <Chip>ausgeblendet</Chip> : null}
      {erfassen ? <>
      <Feld label="Titel" fehler={f.titel}>{(p) => <Eingabe {...p} value={titel} onChange={(e) => setTitel(e.target.value)} />}</Feld>
      <div className="grid grid-cols-2 gap-3">
        <Feld label="Typ" fehler={f.typ}>
          {(p) => (
            <Auswahl {...p} value={typ} onChange={(e) => setTyp(e.target.value)}>
              <option value="">—</option>
              {(typen.data ?? []).filter((t) => t.aktiv || String(t.id) === typ).map((t) => <option key={t.id} value={t.id}>{t.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Datum" fehler={f.datum}>{(p) => <Eingabe {...p} className="num" value={am} onChange={(e) => setAm(e.target.value)} placeholder="TT.MM.JJJJ" />}</Feld>
      </div>
      <Feld label="Notiz" fehler={f.notiz}>{(p) => <Textfeld {...p} rows={2} value={notiz} onChange={(e) => setNotiz(e.target.value)} />}</Feld>
      </> : <>
        {/* nur lesen: Werte als Text statt ausgegrauter Felder */}
        <div className="grid grid-cols-2 gap-3">
          <Anzeige label="Typ">{dok.typ_name}</Anzeige>
          <Anzeige label="Datum">{dok.datum ? datum(dok.datum) : null}</Anzeige>
        </div>
        <Anzeige label="Notiz" mehrzeilig>{dok.notiz}</Anzeige>
      </>}
      <dl className="grid grid-cols-[90px_minmax(0,1fr)] gap-x-2.5 gap-y-1 text-[0.8125rem] m-0">
        <dt className="gedaempft">Datei</dt><dd className="m-0 break-all">{dok.originalname}</dd>
        <dt className="gedaempft">Größe</dt><dd className="m-0 num">{dateigroesse(dok.groesse)}</dd>
        <dt className="gedaempft">Prüfsumme</dt><dd className="m-0 num" title={dok.sha256}>SHA-256 · {dok.sha256.slice(0, 4)}…{dok.sha256.slice(-4)}</dd>
      </dl>
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      {istPdf(dok) ? (
        <Dialog offen={lesen} onOffen={setLesen} titel={dok.titel} breite={1100}
          beschreibung={<>{dok.originalname} · <a href={dateiUrl(dok, false)} download>Herunterladen</a></>}>
          {lesen ? <PdfLeser url={dateiUrl(dok, true)} className="h-[68vh]" /> : null}
        </Dialog>
      ) : null}
      {erfassen ? (
        <div className="flex gap-2 flex-wrap">
          {!dok.typ_geprueft ? <Knopf variante="pri" laedt={speichern.isPending && speichern.variables === "pruefen"} onClick={() => speichern.mutate("pruefen")}>Typ und Datum bestätigen</Knopf> : null}
          <Knopf laedt={speichern.isPending && speichern.variables === "speichern"} onClick={() => speichern.mutate("speichern")}>Speichern</Knopf>
          <Knopf variante="geist" onClick={() => speichern.mutate(dok.ausgeblendet ? "einblenden" : "ausblenden")}>{dok.ausgeblendet ? "Wieder einblenden" : "Ausblenden"}</Knopf>
        </div>
      ) : null}
      {umhaengenErlaubt || loeschenErlaubt ? (
        <div className="flex flex-col gap-2 border-t border-rand pt-3" data-testid="falsch-zugeordnet">
          <span className="text-[0.8125rem] gedaempft">Falscher Patient oder fremdes Dokument?</span>
          <div className="flex gap-2 flex-wrap">
            {umhaengenErlaubt ? <Knopf klein icon="pfeilRechts" onClick={() => setFalsch("umhaengen")}>Anderem Patienten zuordnen</Knopf> : null}
            {loeschenErlaubt ? <Knopf klein variante="dng" onClick={() => setFalsch("loeschen")}>Endgültig löschen</Knopf> : null}
          </div>
          {umhaengenErlaubt ? <UmhaengenDialog dok={dok} offen={falsch === "umhaengen"} onOffen={(o) => setFalsch(o ? "umhaengen" : null)} /> : null}
          {loeschenErlaubt ? <LoeschenDialog dok={dok} offen={falsch === "loeschen"} onOffen={(o) => setFalsch(o ? "loeschen" : null)} /> : null}
        </div>
      ) : null}
    </Detail>
  );
}

type Hochladen = { name: string; status: "laeuft" | "ok" | "fehler"; meldung?: string };

export function Dokumente() {
  const { patient, erfassen } = useAkte();
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const [ausgeblendete, setAusgeblendete] = useState(false);
  const [ziehen, setZiehen] = useState(false);
  const [uploads, setUploads] = useState<Hochladen[]>([]);
  const eingabe = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const dokumente = useQuery({
    queryKey: ["patient", patient.id, "dokumente", ausgeblendete],
    queryFn: () => alle<Dokument>(`dokumente/${abfrage({ patient: patient.id, ausgeblendet: ausgeblendete ? undefined : "false" })}`),
  });
  const liste = dokumente.data ?? [];
  const aktiv = liste.find((d) => d.id === gewaehlt) ?? liste[0];

  const hochladen = async (dateien: FileList | File[]) => {
    for (const datei of Array.from(dateien)) {
      setUploads((u) => [...u.filter((x) => x.name !== datei.name), { name: datei.name, status: "laeuft" }]);
      const form = new FormData();
      form.append("patient", String(patient.id));
      form.append("datei", datei);
      form.append("titel", datei.name.replace(/\.[^.]+$/, ""));
      try {
        const neu = await api<Dokument>("dokumente/", { form });
        setUploads((u) => u.map((x) => (x.name === datei.name ? { ...x, status: "ok" } : x)));
        setGewaehlt(neu.id);
      } catch (e) {
        const text = e instanceof ApiFehler ? (e.felder.datei || e.message) : String(e);
        setUploads((u) => u.map((x) => (x.name === datei.name ? { ...x, status: "fehler", meldung: text } : x)));
      }
    }
    void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
  };

  return (
    <Aktenseite
      testid="dokumente"
      titel={liste.length === 1 ? "Dokument" : "Dokumente"}
      anzahl={liste.length}
      laedt={dokumente.isLoading}
      aktion={erfassen ? (
        <div
          className={cx("rounded-[12px] border-2 border-dashed px-3 py-3 flex flex-col items-center justify-center gap-1.5 text-[0.8125rem] text-center",
            ziehen ? "border-akzent bg-akzent-weich" : "border-rand bg-flaeche")}
          onDragOver={(e) => { e.preventDefault(); setZiehen(true); }}
          onDragLeave={() => setZiehen(false)}
          onDrop={(e) => { e.preventDefault(); setZiehen(false); if (e.dataTransfer.files.length) void hochladen(e.dataTransfer.files); }}
          data-testid="ablage">
          <Knopf variante="pri" icon="hochladen" onClick={() => eingabe.current?.click()}>Dateien auswählen</Knopf>
          <span className="gedaempft">oder hierher ziehen · PDF, JPG, PNG, TXT · max. 50 MB</span>
          <input ref={eingabe} type="file" multiple hidden aria-label="Dateien hochladen" accept=".pdf,.jpg,.jpeg,.png,.txt,application/pdf,image/jpeg,image/png,text/plain"
            onChange={(e) => { if (e.target.files?.length) void hochladen(e.target.files); e.target.value = ""; }} />
        </div>
      ) : undefined}
      kopfrechts={<>
        {uploads.length ? (
          <ul className="m-0 p-0 list-none flex flex-col gap-1.5" aria-live="polite" data-testid="uploads">
            {uploads.map((u) => (
              <li key={u.name} className={cx("meldung text-[0.8125rem] flex items-center gap-2", u.status === "fehler" ? "fehler" : u.status === "ok" ? "ok" : "info")}>
                <Icon name={u.status === "fehler" ? "warnung" : u.status === "ok" ? "haken" : "sanduhr"} />
                <span className="font-medium">{u.name}</span>
                <span>{u.status === "laeuft" ? "wird hochgeladen …" : u.status === "ok" ? "hochgeladen" : u.meldung}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <label className="flex items-center gap-2 text-[0.8125rem] cursor-pointer">
          <input type="checkbox" checked={ausgeblendete} onChange={(e) => setAusgeblendete(e.target.checked)} /> Ausgeblendete anzeigen
        </label>
        <Fehleranzeige fehler={dokumente.error} />
      </>}
      liste={
        <Eintragsliste name="Dokumente" testid="dokumentliste" leer={liste.length ? undefined : "Noch keine Dokumente."}>
          {liste.map((d) => (
            <Eintrag key={d.id} aktiv={d.id === aktiv?.id} onWahl={() => setGewaehlt(d.id)} warnung={!d.typ_geprueft}
              datum={datum(d.datum)}
              merkmal={!d.typ_geprueft ? <Chip art="warn">Typ prüfen</Chip>
                : d.ausgeblendet ? <Chip>ausgeblendet</Chip> : null}
              zeile={<span className="inline-flex items-center gap-1.5">
                <Icon name={d.mime.startsWith("image/") ? "bild" : "dokument"} groesse={13} />{d.titel}</span>}
              unten={[d.typ_name ?? "ohne Typ", dateigroesse(d.groesse),
                d.herkunft === "altsystem" ? "Import" : d.herkunft === "system" ? "EPM" : d.hochgeladen_von_name ?? ""]
                .filter(Boolean).join(" · ")} />
          ))}
        </Eintragsliste>
      }
      fuss={<>Dokumente aus dem Altsystem haben noch keinen geprüften Typ – beim Durchsehen rechts Typ und Datum
        setzen. Gelöscht wird nichts, Fehlablagen werden ausgeblendet.</>}
      detail={aktiv ? <Details dok={aktiv} /> : null}
      leer="Links ein Dokument wählen."
    />
  );
}
