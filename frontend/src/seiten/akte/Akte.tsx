/** Entwurf 4 · Patientenakte: Kopf mit Kerndaten und Schnellaktionen, Reiter mit Zählern. */
import { useEffect, useRef, useState } from "react";
import { PdfDialog } from "@/components/PdfDialog";
import type { ReactNode } from "react";
import { NavLink, Outlet, useNavigate, useOutletContext, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { useAuswahl, useVersorgerListe } from "@/lib/daten";
import { alter, datum, eingabeDatum, eingabeZahl, heuteIso, kg, nummer, prozent, terminZeit, zahl } from "@/lib/format";
import { ABSCHLUSSANLAESSE, ERKLAERUNGEN_KURZ, GESCHLECHTER, TERMINARTEN, VERSICHERUNGSARTEN } from "@/lib/typen";
import type { Patient, Recht } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog, Menue } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { TerminDialog } from "@/components/TerminDialog";

export type AktenKontext = {
  patient: Patient;
  /** Akte ist offen und die Person darf Einträge erfassen */
  erfassen: boolean;
  /** Akte ist offen und die Person darf Stammdaten, Diagnose, Therapie ändern */
  bearbeiten: boolean;
  terminAnlegen: () => void;
};

export function useAkte() {
  return useOutletContext<AktenKontext>();
}

export function name(p: { nachname: string; vorname: string }) {
  return `${p.nachname}, ${p.vorname}`;
}

function richtung(p: number) {
  return p <= -1 ? "↓" : p >= 1 ? "↑" : "→"; // U11: unter ±1 % gleichbleibend
}

/** Eine Kennzahl im Aktenkopf: feste Spalte, eine Zeile (zu Langes wird gekürzt, ganz im Tooltip) – der Kopf springt nicht */
function Kennzahl({ titel, children, hinweis }: { titel: string; children: ReactNode; hinweis?: string }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0 px-[18px] border-l border-rand" title={hinweis}>
      <span className="lbl text-[0.78rem] gedaempft font-medium">{titel}</span>
      <span className="text-sm truncate">{children}</span>
    </div>
  );
}

/** Wert der Auswahl „kein“ (bewusst keiner) bei Versorger und Katheter */
const KEIN = "kein";

/** Stammdaten bearbeiten (Felder wie „Neuer Patient“) */
function StammdatenDialog({ patient, offen, onOffen }: { patient: Patient; offen: boolean; onOffen: (o: boolean) => void }) {
  const start = () => ({
    nachname: patient.nachname, vorname: patient.vorname, geschlecht: patient.geschlecht, geburtsdatum: datum(patient.geburtsdatum),
    groesse: patient.groesse_cm != null ? zahl(patient.groesse_cm) : "", strasse: patient.strasse, plz: patient.plz, ort: patient.ort,
    telefon: patient.telefon, telefon2: patient.telefon2, email: patient.email,
    versicherungsart: patient.versicherungsart, krankenkasse: patient.krankenkasse,
    versichertennummer: patient.versichertennummer,
    versorger: patient.versorger ? String(patient.versorger) : patient.kein_versorger ? KEIN : "",
    ansprechpartner: patient.ansprechpartner ? String(patient.ansprechpartner) : "",
    katheter: patient.katheter ? String(patient.katheter) : patient.kein_katheter ? KEIN : "",
    nickelallergie: patient.nickelallergie, hausarzt: patient.hausarzt, ueberweisung_durch: patient.ueberweisung_durch,
  });
  const [f, setF] = useState(start);
  const [lokal, setLokal] = useState<Feldfehler>({});
  useEffect(() => {
    if (offen) { setF(start()); setLokal({}); }
  }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const versorger = useVersorgerListe();
  const katheter = useAuswahl("katheter", false);
  const qc = useQueryClient();
  const melden = useHinweis();
  const gewaehlt = (versorger.data ?? []).find((v) => String(v.id) === f.versorger);
  const speichern = useMutation({
    mutationFn: (daten: Record<string, unknown>) => api<Patient>(`patienten/${patient.id}/`, { method: "PATCH", body: daten }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      melden("Stammdaten gespeichert.");
      onOffen(false);
    },
  });
  const absenden = () => {
    const fehler: Feldfehler = {};
    const geb = eingabeDatum(f.geburtsdatum);
    if (!f.nachname.trim()) fehler.nachname = "Bitte Nachnamen eingeben.";
    if (!f.vorname.trim()) fehler.vorname = "Bitte Vornamen eingeben.";
    if (!geb) fehler.geburtsdatum = "Bitte als TT.MM.JJJJ eingeben.";
    const groesse = eingabeZahl(f.groesse);
    if (groesse === "ungueltig") fehler.groesse_cm = "Bitte eine Zahl eingeben.";
    setLokal(fehler);
    if (Object.keys(fehler).length) return;
    speichern.mutate({
      nachname: f.nachname.trim(), vorname: f.vorname.trim(), geschlecht: f.geschlecht, geburtsdatum: geb, groesse_cm: groesse,
      strasse: f.strasse.trim(), plz: f.plz.trim(), ort: f.ort.trim(), telefon: f.telefon.trim(), email: f.email.trim(),
      telefon2: f.telefon2.trim(),
      // Versichertendaten (F118): Art, Versicherung und Versichertennummer
      versicherungsart: f.versicherungsart, krankenkasse: f.krankenkasse.trim(),
      versichertennummer: f.versichertennummer.trim(),
      // „kein“ = bewusst keiner, leer = noch nicht erfasst (Festlegung 01.10.2026)
      versorger: f.versorger && f.versorger !== KEIN ? Number(f.versorger) : null, kein_versorger: f.versorger === KEIN,
      ansprechpartner: f.ansprechpartner && f.versorger !== KEIN ? Number(f.ansprechpartner) : null,
      katheter: f.katheter && f.katheter !== KEIN ? Number(f.katheter) : null, kein_katheter: f.katheter === KEIN,
      nickelallergie: f.nickelallergie, hausarzt: f.hausarzt.trim(),
      ueberweisung_durch: f.ueberweisung_durch.trim(),
    });
  };
  const e: Feldfehler = { ...(speichern.error instanceof ApiFehler ? speichern.error.felder : {}), ...lokal };
  const set = (k: keyof ReturnType<typeof start>) => (ev: { target: { value: string } }) => setF((a) => ({ ...a, [k]: ev.target.value }));
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Stammdaten bearbeiten" breite={760}
      beschreibung="Jede Änderung steht mit Person und Zeitpunkt im Verlauf der Akte."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={absenden}>Speichern</Knopf>
      </>}>
      <form className="grid grid-cols-4 gap-x-4 gap-y-3" noValidate onSubmit={(ev) => { ev.preventDefault(); absenden(); }}>
        <Feld label="Nachname" pflicht className="col-span-2" fehler={e.nachname}>{(p) => <Eingabe {...p} value={f.nachname} onChange={set("nachname")} />}</Feld>
        <Feld label="Vorname" pflicht className="col-span-2" fehler={e.vorname}>{(p) => <Eingabe {...p} value={f.vorname} onChange={set("vorname")} />}</Feld>
        <Feld label="Geschlecht" fehler={e.geschlecht}>
          {(p) => <Auswahl {...p} value={f.geschlecht} onChange={set("geschlecht")}>{["w", "m", "d", ""].map((k) => <option key={k} value={k}>{GESCHLECHTER[k]}</option>)}</Auswahl>}
        </Feld>
        <Feld label="Geburtsdatum" pflicht fehler={e.geburtsdatum}>{(p) => <Eingabe {...p} className="num" value={f.geburtsdatum} onChange={set("geburtsdatum")} />}</Feld>
        <Feld label="Größe (cm)" fehler={e.groesse_cm}>{(p) => <Eingabe {...p} className="num" value={f.groesse} onChange={set("groesse")} inputMode="decimal" />}</Feld>
        <Feld label="Nickelallergie" fehler={e.nickelallergie}>
          {(p) => (
            <Auswahl {...p} value={f.nickelallergie} onChange={set("nickelallergie")}>
              <option value="unbekannt">nicht erfasst</option>
              <option value="ja">ja</option>
              <option value="nein">nein</option>
            </Auswahl>
          )}
        </Feld>
        <Feld label="Straße und Hausnummer" className="col-span-2" fehler={e.strasse}>{(p) => <Eingabe {...p} value={f.strasse} onChange={set("strasse")} />}</Feld>
        <Feld label="PLZ" fehler={e.plz}>{(p) => <Eingabe {...p} className="num" value={f.plz} onChange={set("plz")} />}</Feld>
        <Feld label="Ort" fehler={e.ort}>{(p) => <Eingabe {...p} value={f.ort} onChange={set("ort")} />}</Feld>
        <Feld label="Telefon" className="col-span-2" fehler={e.telefon}>{(p) => <Eingabe {...p} className="num" value={f.telefon} onChange={set("telefon")} />}</Feld>
        <Feld label="Telefon 2" className="col-span-2" fehler={e.telefon2}>{(p) => <Eingabe {...p} className="num" value={f.telefon2} onChange={set("telefon2")} />}</Feld>
        <Feld label="E-Mail" className="col-span-2" fehler={e.email}>{(p) => <Eingabe {...p} type="email" value={f.email} onChange={set("email")} />}</Feld>
        <Feld label="Versicherungsart" className="col-span-2" fehler={e.versicherungsart}>
          {(p) => (
            <Auswahl {...p} value={f.versicherungsart} onChange={set("versicherungsart")}>
              {Object.entries(VERSICHERUNGSARTEN).map(([k, text]) => <option key={k} value={k}>{text}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Versicherung" className="col-span-2" fehler={e.krankenkasse}>{(p) => <Eingabe {...p} maxLength={100} value={f.krankenkasse} onChange={set("krankenkasse")} />}</Feld>
        <Feld label="Versichertennummer" className="col-span-2" fehler={e.versichertennummer}>{(p) => <Eingabe {...p} className="num" maxLength={50} value={f.versichertennummer} onChange={set("versichertennummer")} />}</Feld>
        <Feld label="Versorger" className="col-span-2" fehler={e.versorger}>
          {(p) => (
            <Auswahl {...p} value={f.versorger} onChange={(ev) => setF((a) => ({ ...a, versorger: ev.target.value, ansprechpartner: "" }))}>
              <option value="">— nicht erfasst —</option>
              <option value={KEIN}>kein Versorger</option>
              {(versorger.data ?? []).filter((v) => v.aktiv || String(v.id) === f.versorger).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Ansprechpartner beim Versorger" className="col-span-2" fehler={e.ansprechpartner}>
          {(p) => (
            <Auswahl {...p} value={f.ansprechpartner} onChange={set("ansprechpartner")} disabled={!gewaehlt}>
              <option value="">— noch offen —</option>
              {(gewaehlt?.ansprechpartner ?? []).filter((a) => a.aktiv || String(a.id) === f.ansprechpartner).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Katheter" className="col-span-2" fehler={e.katheter}>
          {(p) => (
            <Auswahl {...p} value={f.katheter} onChange={set("katheter")}>
              <option value="">— nicht erfasst —</option>
              <option value={KEIN}>kein Katheter</option>
              {(katheter.data ?? []).filter((k) => k.aktiv || String(k.id) === f.katheter).map((k) => <option key={k.id} value={k.id}>{k.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
        {patient.hausarzt ? (
          // Freitext aus dem Altsystem bzw. von vor der Ärzteliste: bleibt erhalten, neue Ärzte über „Ärzte“ zuordnen
          <Feld label="Hausarzt (bisheriger Freitext)" className="col-span-2" fehler={e.hausarzt}
            hinweis="Ärzte mit Kontaktdaten in der Übersicht unter „Ärzte“ zuordnen">
            {(p) => <Eingabe {...p} value={f.hausarzt} onChange={set("hausarzt")} />}
          </Feld>
        ) : null}
        <Feld label="Überweisung / Kontaktaufnahme durch" className="col-span-4" fehler={e.ueberweisung_durch}>{(p) => <Eingabe {...p} value={f.ueberweisung_durch} onChange={set("ueberweisung_durch")} />}</Feld>
        {speichern.error && !(speichern.error instanceof ApiFehler && Object.keys(speichern.error.felder).length) ? <Meldung art="fehler" className="col-span-4">{speichern.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

function AbschlussDialog({ patient, offen, onOffen }: { patient: Patient; offen: boolean; onOffen: (o: boolean) => void }) {
  const [anlass, setAnlass] = useState("");
  const [am, setAm] = useState(datum(heuteIso()));
  const [notiz, setNotiz] = useState("");
  const qc = useQueryClient();
  const melden = useHinweis();
  const abschliessen = useMutation({
    mutationFn: () => {
      const iso = eingabeDatum(am);
      if (!iso) throw new ApiFehler(400, "Bitte das Datum als TT.MM.JJJJ eingeben.", null, { datum: "Bitte als TT.MM.JJJJ eingeben." });
      return api<Patient>(`patienten/${patient.id}/abschliessen/`, { body: { anlass, datum: iso, notiz } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden("Akte abgeschlossen.");
      onOffen(false);
    },
  });
  const f: Feldfehler = abschliessen.error instanceof ApiFehler ? abschliessen.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Akte abschließen" breite={520}
      beschreibung="Die Akte bleibt vollständig lesbar, wird aber nicht mehr verändert. Wieder öffnen kann nur die Administration."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={abschliessen.isPending} disabled={!anlass} onClick={() => abschliessen.mutate()}>Akte abschließen</Knopf>
      </>}>
      <fieldset className="border-0 p-0 m-0 flex flex-col gap-2">
        <legend className="text-sm font-medium mb-2">Anlass</legend>
        {Object.entries(ABSCHLUSSANLAESSE).map(([k, v]) => (
          <label key={k} className="flex items-center gap-2 text-sm"><input type="radio" name="anlass" value={k} checked={anlass === k} onChange={() => setAnlass(k)} />{v}</label>
        ))}
        {f.anlass ? <span className="fehlertext" role="alert">{f.anlass}</span> : null}
      </fieldset>
      <Feld label="Abgeschlossen am" fehler={f.datum}>{(p) => <Eingabe {...p} className="num w-40" value={am} onChange={(e) => setAm(e.target.value)} />}</Feld>
      <Feld label="Notiz" fehler={f.notiz}>{(p) => <Textfeld {...p} rows={2} value={notiz} onChange={(e) => setNotiz(e.target.value)} />}</Feld>
      {abschliessen.error && !Object.keys(f).length ? <Meldung art="fehler">{abschliessen.error.message}</Meldung> : null}
    </Dialog>
  );
}

function WiederOeffnenDialog({ patient, offen, onOffen }: { patient: Patient; offen: boolean; onOffen: (o: boolean) => void }) {
  const [grund, setGrund] = useState("");
  const qc = useQueryClient();
  const melden = useHinweis();
  const oeffnen = useMutation({
    mutationFn: () => api<Patient>(`patienten/${patient.id}/wieder-oeffnen/`, { body: { grund } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      melden("Akte wieder geöffnet.");
      onOffen(false);
    },
  });
  const f: Feldfehler = oeffnen.error instanceof ApiFehler ? oeffnen.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Akte wieder öffnen" breite={520}
      beschreibung="Zum Beispiel nach einem Versehen. Der Grund steht im Verlauf der Akte und im Audit-Log."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={oeffnen.isPending} onClick={() => oeffnen.mutate()}>Wieder öffnen</Knopf>
      </>}>
      <Feld label="Grund" pflicht fehler={f.grund}>{(p) => <Textfeld {...p} rows={2} value={grund} onChange={(e) => setGrund(e.target.value)} />}</Feld>
      {oeffnen.error && !Object.keys(f).length ? <Meldung art="fehler">{oeffnen.error.message}</Meldung> : null}
    </Dialog>
  );
}

/** Akte, deren Verarbeitung eingeschränkt ist (Art. 18 DSGVO): Sie ist nur mit begründeter Einsicht lesbar. */
type Eingeschraenkt = { eingeschraenkt: true; id: number; nummer: number; eingeschraenkt_am: string; darf_einsicht: boolean; fehler: string };

function EinsichtAnsicht({ info }: { info: Eingeschraenkt }) {
  const [grund, setGrund] = useState("");
  const qc = useQueryClient();
  const einsicht = useMutation({
    mutationFn: () => api<{ bis: string }>(`patienten/${info.id}/einsicht/`, { body: { grund: grund.trim() } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", info.id] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
    },
  });
  const f: Feldfehler = einsicht.error instanceof ApiFehler ? einsicht.error.felder : {};
  return (
    <Seite pfad={[{ text: "Patienten", zu: "/patienten" }, { text: `Akte Nr. ${nummer(info.nummer)}` }]}>
      <Karte className="px-[22px] py-[18px] flex flex-col gap-3 max-w-[720px]" data-testid="akte-eingeschraenkt">
        <div className="flex items-center gap-2.5 flex-wrap">
          <h1 className="m-0 text-[1.625rem] font-semibold">Akte Nr. {nummer(info.nummer)}</h1>
          <Chip art="warn"><Icon name="schloss" />Verarbeitung eingeschränkt</Chip>
        </div>
        <span className="text-sm">Die Verarbeitung dieser Akte ist seit {datum(info.eingeschraenkt_am)} eingeschränkt (Art. 18 DSGVO).
          Sie bleibt gespeichert, erscheint aber in keiner Liste und ist nur mit einer begründeten Einsicht lesbar.</span>
        {info.darf_einsicht ? (
          <form className="flex flex-col gap-3" noValidate onSubmit={(e) => { e.preventDefault(); einsicht.mutate(); }}>
            <span className="text-[0.8125rem] gedaempft" data-testid="einsicht-zulaessig">Eingeschränkte Daten dürfen – von der Speicherung abgesehen – nur mit
              Einwilligung der betroffenen Person verarbeitet werden, zur Geltendmachung, Ausübung oder Verteidigung von
              Rechtsansprüchen, zum Schutz der Rechte einer anderen Person oder aus Gründen eines wichtigen öffentlichen
              Interesses (Art. 18 Abs. 2 DSGVO). Bitte den Grund entsprechend angeben.</span>
            <Feld label="Grund der Einsicht" pflicht fehler={f.grund} hinweis="mindestens 10 Zeichen · die Einsicht gilt 60 Minuten und steht mit Grund im Audit-Log">
              {(p) => <Textfeld {...p} rows={2} value={grund} onChange={(e) => setGrund(e.target.value)} />}
            </Feld>
            {einsicht.error && !Object.keys(f).length ? <Meldung art="fehler">{einsicht.error.message}</Meldung> : null}
            <Knopf variante="pri" type="submit" className="self-start" laedt={einsicht.isPending} disabled={grund.trim().length < 10}>Einsicht nehmen</Knopf>
          </form>
        ) : <Meldung art="info">Einsicht nehmen kann, wer über Datenschutz-Anfragen entscheidet.</Meldung>}
      </Karte>
    </Seite>
  );
}

function Reiter({ zu, text, zahl: anzahl, ende }: { zu: string; text: string; zahl?: number; ende?: boolean }) {
  return (
    <NavLink to={zu} end={ende} className={({ isActive }) => cx("segment no-underline", isActive && "aktiv")}>
      {text}{anzahl !== undefined ? <span className="num ml-1.5 opacity-70">{zahl(anzahl)}</span> : null}
    </NavLink>
  );
}

export function Akte() {
  const { id } = useParams();
  const pid = Number(id);
  const { darf, darfBei } = useAuth();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"" | "stammdaten" | "abschluss" | "oeffnen" | "termin" | "pdf" | "sprechstunde">("");
  const akte = useQuery({ queryKey: ["patient", pid], queryFn: () => api<Patient>(`patienten/${pid}/`), enabled: !!pid });
  const p = akte.data;
  const qc = useQueryClient();
  const melden = useHinweis();
  // „Meine Akten“ (S05): Stern im Aktenkopf, und die Akte meldet sich einmal je Aufruf als „zuletzt geöffnet“
  const merken = useMutation({
    mutationFn: (an: boolean) => an ? api("meine-akten/merken/", { body: { patient: pid } })
      : api(`meine-akten/merken/${pid}/`, { method: "DELETE" }),
    onSuccess: (_d, an) => {
      void qc.invalidateQueries({ queryKey: ["patient", pid] });
      void qc.invalidateQueries({ queryKey: ["meine-akten"] });
      melden(an ? "Auf die Merkliste gesetzt." : "Von der Merkliste genommen.");
    },
    onError: (e) => melden(e.message, "fehler"),
  });
  const gemeldet = useRef<number | null>(null);
  useEffect(() => {
    if (!p || gemeldet.current === p.id) return;
    gemeldet.current = p.id;
    api("meine-akten/geoeffnet/", { body: { patient: p.id } })
      .then(() => qc.invalidateQueries({ queryKey: ["meine-akten"] }))
      .catch(() => undefined); // nur ein Lesezeichen: scheitert es, bleibt die Akte trotzdem offen
  }, [p, qc]);
  // Fenster, deren Recht wegfällt, verschwinden und bleiben zu – auch wenn das Recht später zurückkommt
  const offenBei = (recht: Recht) => !!p && !p.ist_abgeschlossen && darfBei(recht, p);
  const erlaubt: Record<typeof dialog, boolean> = {
    "": true,
    pdf: true,
    sprechstunde: true,
    stammdaten: offenBei("akten_bearbeiten"),
    abschluss: offenBei("akten_abschliessen"),
    oeffnen: !!p && p.ist_abgeschlossen && darf("akten_wieder_oeffnen"),
    termin: offenBei("eintraege_erfassen"),
  };
  useOhneRechtSchliessen(erlaubt[dialog], () => setDialog(""));
  // Verarbeitung eingeschränkt (auch wenn es während der Arbeit geschieht oder die Einsicht abläuft): Was vorher
  // geladen war, wird nicht weiter gezeigt
  const gesperrt = akte.error instanceof ApiFehler && akte.error.status === 403 ? akte.error.daten as Eingeschraenkt | null : null;
  if (gesperrt?.eingeschraenkt) return <EinsichtAnsicht info={gesperrt} />;
  if (akte.isLoading) return <Seite pfad={[{ text: "Patienten", zu: "/patienten" }, { text: "…" }]}><Laden /></Seite>;
  if (!p) {
    return (
      <Seite pfad={[{ text: "Patienten", zu: "/patienten" }, { text: "Akte" }]}>
        <Fehleranzeige fehler={akte.error ?? "Akte nicht gefunden."} />
      </Seite>
    );
  }
  const offen = !p.ist_abgeschlossen;
  const kontext: AktenKontext = {
    patient: p,
    erfassen: offen && darfBei("eintraege_erfassen", p),
    bearbeiten: offen && darfBei("akten_bearbeiten", p),
    terminAnlegen: () => setDialog("termin"),
  };
  const k = p.kopf;
  const trend = k?.gewichtstrend;
  const basis = `/patienten/${p.id}`;
  return (
    <Seite pfad={[{ text: "Patienten", zu: "/patienten" }, { text: name(p) }]}>
      <Karte className="px-[22px] py-[18px] flex flex-col gap-4" data-testid="aktenkopf">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="m-0 text-[1.625rem] font-semibold">{name(p)}</h1>
              <button type="button" className={cx("btn icon klein geist", k?.gemerkt ? "!text-akzent-text" : "")} data-testid="merken"
                aria-pressed={!!k?.gemerkt} aria-label={k?.gemerkt ? "Von der Merkliste nehmen" : "Auf die Merkliste"}
                title={k?.gemerkt ? "Von der Merkliste nehmen" : "Auf die Merkliste (erscheint auf der Startseite unter „Meine Akten“)"}
                disabled={merken.isPending} onClick={() => merken.mutate(!k?.gemerkt)}>
                <Icon name="stern" groesse={18} fill={k?.gemerkt ? "currentColor" : "none"} /></button>
              {p.ist_test ? <Chip art="warn">Testpatient</Chip> : null}
              {p.ist_abgeschlossen ? <Chip>abgeschlossen</Chip> : null}
              {p.ist_eingeschraenkt ? <Chip art="warn"><Icon name="schloss" />Verarbeitung eingeschränkt</Chip> : null}
              {/* Erklärungen zum Datenschutz: nachgehalten wie die Nickelallergie – fehlt eine, steht es hier */}
              {offen && k?.erklaerungen.fehlt.length ? (
                <button type="button" className="chip warn border-0 cursor-pointer" data-testid="erklaerungen-fehlen"
                  title={k.erklaerungen.fehlt.map((a) => `${ERKLAERUNGEN_KURZ[a]}: ${k.erklaerungen.stand[a].status === "widerrufen" ? "widerrufen" : "nicht erfasst"}`).join("\n")}
                  onClick={() => navigate(`${basis}/datenschutz`)}>
                  <Icon name="warnung" />
                  {k.erklaerungen.fehlt.length === 1 ? `${ERKLAERUNGEN_KURZ[k.erklaerungen.fehlt[0]]} fehlt` : `${k.erklaerungen.fehlt.length} Erklärungen fehlen`}
                </button>
              ) : null}
            </div>
            <span className="num text-sm gedaempft">
              Nr. {nummer(p.nummer)}{p.geschlecht ? ` · ${GESCHLECHTER[p.geschlecht]}` : ""} · {datum(p.geburtsdatum)} ({alter(p.geburtsdatum)} J.)
            </span>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {kontext.erfassen ? <>
              <Knopf icon="sprechblase" onClick={() => navigate(`${basis}/kontakte`, { state: { neu: Date.now() } })}>Kontakt</Knopf>
              <Knopf icon="waage" onClick={() => navigate(basis, { state: { gewicht: Date.now() } })}>Gewicht</Knopf>
              <Knopf icon="kalender" onClick={() => setDialog("termin")}>Termin</Knopf>
            </> : null}
            {offen && darfBei("plaene_anlegen", p) ? <Knopf icon="tropfen" onClick={() => navigate(`${basis}/plaene/neu`)}>Neuer Plan</Knopf> : null}
            <Menue label="Weitere Aktionen" eintraege={[
              ...(kontext.bearbeiten ? [{ text: "Stammdaten bearbeiten", onClick: () => setDialog("stammdaten") }] : []),
              { text: "Akte als PDF", onClick: () => setDialog("pdf") },
              // Unterlagen für die Sprechstunde (F116): der aktuellste Stand aller Bereiche auf einem Blatt
              { text: "Unterlagen für die Sprechstunde", onClick: () => setDialog("sprechstunde") },
              ...(erlaubt.abschluss ? [{ text: "Akte abschließen", onClick: () => setDialog("abschluss"), gefaehrlich: true }] : []),
              ...(erlaubt.oeffnen ? [{ text: "Akte wieder öffnen", onClick: () => setDialog("oeffnen") }] : []),
            ]} />
          </div>
        </div>
        {k ? (
          <div className="overflow-hidden -mx-[18px]">
          {/* festes Raster (2 Zeilen à 5 auf breiten Bildschirmen): mehr Ärzte oder Personen verändern die Höhe nicht */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-y-3 -ml-px" data-testid="kennzahlen">
            <Kennzahl titel="Gewicht">
              {k.gewicht ? <>{kg(k.gewicht.kg)} {trend ? (
                <span className={cx("font-semibold", trend.warnung ? "text-warn" : "gedaempft")} title={`seit ${datum(trend.von)}`}>
                  {richtung(Number(trend.prozent))} {prozent(trend.prozent, false)}
                </span>
              ) : null}</> : "—"}
            </Kennzahl>
            <Kennzahl titel="BMI"><span className="num">{k.bmi != null ? zahl(k.bmi, 1) : "—"}</span></Kennzahl>
            <Kennzahl titel="Katheter" hinweis={k.katheter ?? undefined}>{k.katheter ?? <span className="gedaempft">nicht erfasst</span>}</Kennzahl>
            <Kennzahl titel="Versorger" hinweis={k.versorger ?? undefined}>{k.versorger ?? <span className="gedaempft">nicht erfasst</span>}</Kennzahl>
            <Kennzahl titel="Ansprechpartner" hinweis={k.ansprechpartner ? [k.ansprechpartner, k.ansprechpartner_telefon].filter(Boolean).join(" · ") : undefined}>
              {k.ansprechpartner ? <>{k.ansprechpartner}{k.ansprechpartner_telefon ? <> · <span className="num">{k.ansprechpartner_telefon}</span></> : null}</> : "—"}</Kennzahl>
            <Kennzahl titel="Aktueller Plan">{k.aktueller_plan ? `${zahl(k.aktueller_plan.kcal)} kcal${k.aktueller_plan.laufzeit_h ? ` · ${zahl(k.aktueller_plan.laufzeit_h)} h` : ""}`
              : k.kein_plan ? <span className="gedaempft">nicht nötig</span> : "—"}</Kennzahl>
            <Kennzahl titel="Nächster Termin" hinweis={k.naechster_termin ? `${terminZeit(k.naechster_termin.faellig_am, k.naechster_termin.uhrzeit)} · ${k.naechster_termin.ort ?? TERMINARTEN[k.naechster_termin.art]}` : undefined}>
              {k.naechster_termin ? `${terminZeit(k.naechster_termin.faellig_am, k.naechster_termin.uhrzeit)} · ${k.naechster_termin.ort ?? TERMINARTEN[k.naechster_termin.art]}` : "—"}
            </Kennzahl>
            <Kennzahl titel="Hausarzt" hinweis={k.hausarzt ? [k.hausarzt.name, k.hausarzt.telefon].filter(Boolean).join(" · ") : undefined}>
              {k.hausarzt ? <>{k.hausarzt.name}{k.hausarzt.telefon ? <> · <span className="num">{k.hausarzt.telefon}</span></> : null}</> : "—"}
            </Kennzahl>
            <Kennzahl titel={k.auskunft.length > 1 ? `Auskunft an (${k.auskunft.length})` : "Auskunft an"}
              hinweis={k.auskunft.map((a) => `${a.name}${a.beziehung ? ` (${a.beziehung})` : ""}${a.telefon ? ` ${a.telefon}` : ""}`).join("\n") || undefined}>
              {/* Bezugspersonen mit Schweigepflichtentbindung – am Telefon sofort sichtbar; ein Klick führt zu den Kontaktdaten */}
              <span data-testid="auskunft">{k.auskunft.length ? k.auskunft.map((a, i) => (
                <span key={a.id}>{i ? " · " : ""}
                  <button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer hover:underline"
                    onClick={() => navigate(basis, { state: { bezugsperson: a.id, zeit: Date.now() } })}>
                    {a.name}{a.beziehung ? ` (${a.beziehung})` : ""}</button>
                  {a.telefon ? <> <span className="num">{a.telefon}</span></> : null}</span>
              )) : <span className="gedaempft">niemand eingetragen</span>}</span>
            </Kennzahl>
            <Kennzahl titel="Nickelallergie">
              {p.nickelallergie === "ja" ? <Chip art="fehler">ja</Chip>
                : p.nickelallergie === "nein" ? "nein"
                : kontext.bearbeiten ? (
                  <button type="button" className="bg-transparent border-0 p-0 text-warn cursor-pointer inline-flex items-center gap-1 font-medium"
                    onClick={() => setDialog("stammdaten")}><Icon name="warnung" /> nicht erfasst</button>
                ) : <span className="text-warn">nicht erfasst</span>}
            </Kennzahl>
          </div>
          </div>
        ) : null}
      </Karte>

      {p.ist_eingeschraenkt ? (
        <Meldung art="warn">
          Die Verarbeitung dieser Akte ist eingeschränkt (Art. 18 DSGVO). Sie sehen sie mit begründeter Einsicht; die Einsicht
          gilt 60 Minuten und steht im Audit-Log.
        </Meldung>
      ) : null}
      {p.ist_abgeschlossen ? (
        <Meldung art="info">
          Akte abgeschlossen am {datum(p.abgeschlossen_am)} · Anlass: {ABSCHLUSSANLAESSE[p.abschluss_anlass] ?? p.abschluss_anlass}
          {p.abschluss_notiz ? ` · ${p.abschluss_notiz}` : ""}. Die Akte ist nur noch lesbar.
          {p.aufbewahrung?.bis ? ` Aufbewahrung bis ${datum(p.aufbewahrung.bis)}${p.aufbewahrung.abgelaufen ? " (Frist abgelaufen)" : ""}.` : ""}
        </Meldung>
      ) : null}

      {/* Jeder Bereich ein eigener Reiter (Wunsch 07.10.2026, F121); bei schmalem Fenster umbrechen die Reiter */}
      <nav aria-label="Aktenbereiche" className="segmente self-start flex-wrap h-auto">
        <Reiter zu={basis} text="Übersicht" ende />
        <Reiter zu={`${basis}/diagnosen`} text="Diagnosen" zahl={k?.zaehler.diagnosen} />
        <Reiter zu={`${basis}/therapie`} text="Therapie" />
        <Reiter zu={`${basis}/empfehlung`} text="Empfehlung" />
        <Reiter zu={`${basis}/kontakte`} text="Kontakte" zahl={k?.zaehler.kontakte} />
        <Reiter zu={`${basis}/plaene`} text="Infusionspläne" zahl={k?.zaehler.infusionsplaene} />
        {/* Wünsche aus der Praxis vom 06.10.2026 (F112–F115) */}
        <Reiter zu={`${basis}/labor`} text="Labor" zahl={k?.zaehler.laborbefunde} />
        <Reiter zu={`${basis}/bia`} text="BIA" zahl={k?.zaehler.bia_messungen} />
        <Reiter zu={`${basis}/berichte`} text="Berichte" zahl={k?.zaehler.berichte} />
        <Reiter zu={`${basis}/dokumente`} text="Dokumente" zahl={k?.zaehler.dokumente} />
        <Reiter zu={`${basis}/datenschutz`} text="Datenschutz" zahl={k?.datenschutz_anfragen || undefined} />
        <Reiter zu={`${basis}/verlauf`} text="Verlauf" />
      </nav>

      <Outlet context={kontext} />

      {kontext.bearbeiten ? <StammdatenDialog patient={p} offen={dialog === "stammdaten"} onOffen={(o) => setDialog(o ? "stammdaten" : "")} /> : null}
      {/* Dialoge nur mit Recht: entzieht die Administration ein Recht, verschwindet auch ein offener Dialog */}
      {erlaubt.abschluss ? <AbschlussDialog patient={p} offen={dialog === "abschluss"} onOffen={(o) => setDialog(o ? "abschluss" : "")} /> : null}
      {erlaubt.oeffnen ? <WiederOeffnenDialog patient={p} offen={dialog === "oeffnen"} onOffen={(o) => setDialog(o ? "oeffnen" : "")} /> : null}
      <PdfDialog offen={dialog === "pdf"} onOffen={(o) => setDialog(o ? "pdf" : "")} titel={`Akte ${name(p)} als PDF`}
        pfad={`patienten/${p.id}/pdf/`} dateiname={`Patientendatenblatt-${p.nummer}.pdf`} />
      <PdfDialog offen={dialog === "sprechstunde"} onOffen={(o) => setDialog(o ? "sprechstunde" : "")}
        titel={`Unterlagen für die Sprechstunde · ${name(p)}`}
        pfad={`patienten/${p.id}/sprechstunde/`} dateiname={`Sprechstunde-${p.nummer}.pdf`} />
      {kontext.erfassen ? <TerminDialog offen={dialog === "termin"} onOffen={(o) => setDialog(o ? "termin" : "")} patientId={p.id} patientName={name(p)} /> : null}
    </Seite>
  );
}
