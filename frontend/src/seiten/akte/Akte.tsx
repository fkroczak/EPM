/** Entwurf 4 · Patientenakte: Kopf mit Kerndaten und Schnellaktionen, Reiter mit Zählern – in drei Ansichten je Person
 *  (Kopfzeile, Seitenleiste, Karteikarte; Wunsch 08.10.2026, siehe ./ansicht.tsx). */
import { Fragment, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { PdfDialog } from "@/components/PdfDialog";
import type { CSSProperties, ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { useAuswahl, useVersorgerListe } from "@/lib/daten";
import { alter, datum, eingabeDatum, eingabeZahl, heuteIso, kg, nummer, prozent, terminZeit, zahl } from "@/lib/format";
import { ABSCHLUSSANLAESSE, ERKLAERUNGEN_KURZ, GESCHLECHTER, TERMINARTEN, VERSICHERUNGSARTEN } from "@/lib/typen";
import type { Patient, Recht, Termin } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog, Menue } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Begriff } from "@/components/ui/Begriff";
import { Icon } from "@/components/ui/icon";
import { TerminDialog } from "@/components/TerminDialog";
import { HinweisChips, HinweisChipsKompakt } from "@/components/HinweisChips";
import type { AktenAktion } from "@/lib/sprungziele";
import { GewichtDialog, KontaktDialog } from "@/components/Schnellerfassung";
import { useAktenAblage } from "@/components/AktenAblage";
import type { Aktenansicht } from "@/lib/darstellung";
import { ab, useMobil, useStufe } from "@/lib/stufen";
import { Kopfgriff, Leistengriff, useDarstellung } from "./ansicht";
import { SchreibenAusAkte } from "./Schreiben";

export type AktenKontext = {
  patient: Patient;
  /** Akte ist offen und die Person darf Einträge erfassen */
  erfassen: boolean;
  /** Akte ist offen und die Person darf Stammdaten, Diagnose, Therapie ändern */
  bearbeiten: boolean;
  /** Akte ist offen und die Person darf Infusionspläne anlegen */
  planen: boolean;
  terminAnlegen: () => void;
  /** offenen Termin ändern (Karteikarte, 08.10.2026) */
  terminAendern: (t: Termin) => void;
  /** Termin per Nummer öffnen (Wunsch 11.10.2026): Dialog „Termin bearbeiten“, ohne Recht bzw. erledigt im Kalender */
  terminOeffnen: (id: number) => void;
  /** Dialoge „Kontakt erfassen“ / „Gewicht erfassen“ wie im Aktenkopf (F149) */
  kontaktErfassen: (text?: string) => void;
  gewichtErfassen: (wert?: string) => void;
  /** Dialog „Stammdaten bearbeiten“ (Stift auf der Karte „Anschrift und Kontakt“, 08.10.2026) */
  stammdatenBearbeiten: () => void;
  /** Dialog „Schreiben und E-Mail“ (z. B. „Blutuntersuchung anfordern“ aus dem Plan-Editor, F187); null ohne Recht */
  schreibenOeffnen: (() => void) | null;
  /** Inhalt neben einer Seitenleiste oder Spalte (Ansichten „Seitenleiste“ und „Karteikarte“): Raster nach der
   *  tatsächlichen Breite statt nach der Fensterbreite */
  schmal: boolean;
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
    <div className="flex flex-col gap-0.5 min-w-0 px-3 sm:px-[1.125rem] border-l border-rand" title={hinweis}>
      <span className="lbl text-[0.78rem] gedaempft font-medium">{titel}</span>
      <span className="text-sm truncate">{children}</span>
    </div>
  );
}

/** Unter 1280 px (Telefon, Tablet, kleine Fenster): Versorgung und Hinweise im Kopf erst auf Antippen */
const SCHMALER_KOPF = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(max-width: 79.99em)") : null;
function useSchmalerKopf(): boolean {
  return useSyncExternalStore(
    (melden) => { SCHMALER_KOPF?.addEventListener("change", melden); return () => SCHMALER_KOPF?.removeEventListener("change", melden); },
    () => !!SCHMALER_KOPF?.matches,
    () => false,
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
      <Karte className="px-[1.375rem] py-[1.125rem] flex flex-col gap-3 max-w-[45rem]" data-testid="akte-eingeschraenkt">
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

/** ``stufe``: haupt = Bereiche der Behandlung (groß), neben = Befunde und Unterlagen, ende = Verlauf und Datenschutz (klein
 *  am Ende der Leiste, Wunsch 10.10.2026 „Menüpunkte verkleinern“) */
type ReiterEintrag = { zu: string; text: string; zahl?: number; ende?: boolean; gruppe?: string; kuerzel?: string; stufe?: "haupt" | "neben" | "ende" };

function Reiter({ zu, text, zahl: anzahl, ende, senkrecht, kuerzel, stufe }: ReiterEintrag & { senkrecht?: boolean }) {
  if (senkrecht) {
    return (
      <NavLink to={zu} end={ende} title={kuerzel} className={({ isActive }) => cx("vreiter no-underline", isActive && "aktiv")}>
        <span className="truncate">{text}</span>
        {anzahl ? <span className="num opacity-70 vreiter-zahl">{zahl(anzahl)}</span> : null}
      </NavLink>
    );
  }
  return (
    <NavLink to={zu} end={ende} title={kuerzel} className={({ isActive }) => cx("segment no-underline", stufe && stufe !== "haupt" && "neben", isActive && "aktiv")}>
      {/* Zähler nur, wo etwas da ist – „0“ an jedem leeren Reiter war Lärm (Wunsch 10.10.2026) */}
      {text}{anzahl ? <span className="num ml-1.5 opacity-70">{zahl(anzahl)}</span> : null}
    </NavLink>
  );
}

/** Eine Angabe des Aktenkopfs (Kennzahl) – in den Gruppen als Zeile „Titel | Wert“, in einer Zeile als Spalte */
type Angabe = { titel: string; inhalt: ReactNode; hinweis?: string };
type Gruppe = { titel: string; angaben: Angabe[]; bearbeiten?: () => void };

const VERSICHERUNG_KURZ: Record<string, string> = { gkv: "GKV", pkv: "PKV", selbstzahler: "Selbstzahler", sonstige: "Sonstige" };

/** Zeile in einer Gruppe: eine Zeile hoch, Langes gekürzt und ganz im Tooltip – mehr Personen ändern die Höhe nicht */
function Angabezeile({ a }: { a: Angabe }) {
  return (
    <div className="grid grid-cols-[7.75rem_minmax(0,1fr)] gap-x-3 items-baseline min-w-0" title={a.hinweis}>
      <span className="text-[0.8125rem] gedaempft md:truncate">{a.titel}</span>
      <span className="text-sm min-w-0 md:truncate max-md:[overflow-wrap:anywhere]">{a.inhalt}</span>
    </div>
  );
}

/** „heute“, „gestern“, „vor 12 Tagen“ – wie lange der letzte Kontakt her ist */
function vorTagen(tag: string): string {
  const tage = Math.round((new Date(heuteIso()).getTime() - new Date(tag.slice(0, 10)).getTime()) / 86400000);
  return tage <= 0 ? "heute" : tage === 1 ? "gestern" : `vor ${zahl(tage)} Tagen`;
}

/** Kennzahl im Kopf (Stufe „voll“): Bezeichnung klein darüber, Wert kräftig, Zusatz grau dahinter – zwei Zeilen hoch */
function Kopfzahl({ titel, wert, unter, hinweis }: { titel: string; wert: ReactNode; unter?: ReactNode; hinweis?: string }) {
  return (
    <div className="flex flex-col min-w-0" title={hinweis}>
      <span className="text-[0.75rem] gedaempft leading-tight">{titel}</span>
      <span className="flex flex-wrap md:flex-nowrap items-baseline gap-x-2 min-w-0 leading-snug">
        <span className="text-base font-semibold md:shrink-0 max-w-full md:truncate">{wert}</span>
        {unter ? <span className="text-[0.75rem] gedaempft min-w-0 md:truncate max-md:[overflow-wrap:anywhere]">{unter}</span> : null}
      </span>
    </div>
  );
}

/** Kleine Angabe in der zweiten Zeile des Kopfs: „Titel Wert“, gekürzt, ganz im Tooltip */
function Kopfangabe({ a }: { a: Angabe }) {
  return (
    <div className="inline-flex items-baseline gap-1.5 min-w-0 max-w-full md:max-w-[20rem]" title={a.hinweis}>
      <span className="gedaempft shrink-0">{a.titel}</span>
      <span className="min-w-0 md:truncate max-md:[overflow-wrap:anywhere]">{a.inhalt}</span>
    </div>
  );
}

/**
 * Kopf der Akte, Stufe „voll“ (Wunsch 10.10.2026: „überfüllte Übersicht, zu viele Infos“, dann „Akte deutlich
 * entschlanken, möglichst ohne Scrollen“): vier Kennzahlen – Gewicht, Infusionsplan, nächster Termin, letzter
 * Kontakt – in einer Zeile, Versorgung und Hinweise in einer schmalen Zeile darunter. Telefon und Versicherung stehen
 * in „Personen und Anschrift“ der Übersicht. Rund 70 px statt vorher 170 px.
 */
function KopfVoll({ angabe, unter, bearbeiten, mobil, hinweise, anzahlHinweise = 0 }: { angabe: Record<string, Angabe>;
  unter: Record<string, ReactNode>; bearbeiten?: () => void; mobil?: boolean;
  /** Telefon: Hinweis-Chips im aufklappbaren Teil */
  hinweise?: ReactNode; anzahlHinweise?: number }) {
  // Telefon und Tablet: Versorgung und Hinweise auf Antippen – sonst schöbe der Kopf die Akte weit nach unten bzw. ließe
  // der Übersicht im Fenster zu wenig Platz (Nickelallergie und Gewichtsverlust stehen als CAVE ohnehin beim Namen)
  const [mehr, setMehr] = useState(false);
  return (
    <div className="border-t border-rand pt-2 pb-1.5 flex flex-col gap-1.5" data-testid="kennzahlen">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-x-6 gap-y-2">
        <div role="group" aria-label="Ernährung" className="grid grid-cols-2 gap-x-5 min-w-0">
          <Kopfzahl titel="Gewicht" wert={angabe.gewicht.inhalt} unter={unter.gewicht} hinweis={angabe.gewicht.hinweis} />
          <Kopfzahl titel="Infusionsplan" wert={angabe.plan.inhalt} unter={unter.plan} hinweis={angabe.plan.hinweis} />
        </div>
        <div role="group" aria-label="Termine und Kontakt" className="grid grid-cols-2 gap-x-5 min-w-0 md:border-l md:border-rand md:pl-6">
          <Kopfzahl titel="Nächster Termin" wert={unter.terminWann ?? "—"} unter={unter.terminWo} hinweis={angabe.termin.hinweis} />
          <Kopfzahl titel="Letzter Kontakt" wert={angabe.kontakt.inhalt} unter={unter.kontakt} />
        </div>
      </div>
      {mobil ? (
        <button type="button" className="self-start bg-transparent border-0 p-0 text-[0.8125rem] text-akzent-text cursor-pointer inline-flex items-center gap-1"
          aria-expanded={mehr} onClick={() => setMehr(!mehr)} data-testid="kopf-mehr">
          {mehr ? "Weniger anzeigen" : `Versorgung und Hinweise${anzahlHinweise ? ` (${anzahlHinweise})` : ""}`}<Icon name={mehr ? "hoch" : "runter"} groesse={14} /></button>
      ) : null}
      {hinweise && (!mobil || mehr) ? <div className="flex flex-wrap gap-1.5" data-testid="kopf-hinweise">{hinweise}</div> : null}
      <div className={cx("flex-wrap items-center gap-x-6 gap-y-1 border-t border-fein pt-1.5 text-[0.8125rem] min-w-0", mobil && !mehr ? "hidden" : "flex")}>
        <div role="group" aria-label="Versorgung" className="flex flex-wrap items-center gap-x-4 gap-y-1 min-w-0">
          <span className="sr-only">Versorgung:</span>
          {[angabe.versorger, angabe.ansprechpartner, angabe.hausarzt, angabe.katheter].map((a) => <Kopfangabe key={a.titel} a={a} />)}
          {bearbeiten ? <button type="button" className="btn geist icon !h-6 !w-6 shrink-0 nicht-drucken" aria-label="Versorgung bearbeiten"
            title="Stammdaten bearbeiten" onClick={bearbeiten}><Icon name="stift" groesse={13} /></button> : null}
        </div>
        <div role="group" aria-label="Hinweise und Auskunft" className="flex flex-wrap items-center gap-x-4 gap-y-1 min-w-0">
          <span className="sr-only">Hinweise und Auskunft:</span>
          {[angabe.nickel, angabe.auskunft].map((a) => <Kopfangabe key={a.titel} a={a} />)}
        </div>
      </div>
    </div>
  );
}

/**
 * Angaben in Gruppen (Ernährung, Versorgung, Termine und Kontakt, Hinweise und Auskunft): im Kopf nebeneinander mit
 * Trennlinien, in der Seitenleiste und der rechten Spalte der Karteikarte untereinander.
 */
function Gruppen({ gruppen, art }: { gruppen: Gruppe[]; art: "kopf" | "leiste" }) {
  return (
    <div className={art === "kopf" ? "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-x-6 gap-y-4" : "flex flex-col"}>
      {gruppen.map((g, i) => (
        <div key={g.titel} role="group" aria-label={g.titel}
          className={cx("flex flex-col gap-1.5 min-w-0",
            art === "kopf" ? i > 0 && "xl:border-l xl:border-rand xl:pl-6" : i > 0 && "border-t border-rand pt-3 mt-3")}>
          <span className="flex items-center justify-between gap-2">
            <span className="text-[0.6875rem] font-semibold tracking-[.06em] uppercase gedaempft">{g.titel}</span>
            {/* Stift an der Gruppe (Vorschlag „Bearbeiten sichtbar“, 08.10.2026): öffnet „Stammdaten bearbeiten“ */}
            {g.bearbeiten ? <button type="button" className="btn geist icon !h-6 !w-6 nicht-drucken" aria-label={`${g.titel} bearbeiten`}
              title="Stammdaten bearbeiten" onClick={g.bearbeiten}><Icon name="stift" groesse={13} /></button> : null}
          </span>
          {g.angaben.map((a) => <Angabezeile key={a.titel} a={a} />)}
        </div>
      ))}
    </div>
  );
}

export function Akte() {
  const { id } = useParams();
  const pid = Number(id);
  const { darf, darfBei } = useAuth();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"" | "stammdaten" | "abschluss" | "oeffnen" | "termin" | "kontakt" | "gewicht" | "pdf" | "sprechstunde" | "schreiben">("");
  // Vorbelegung aus der Kürzelzeile (Karteikarte: „K Text“, „G 54,6“)
  const [vorbelegt, setVorbelegt] = useState("");
  const [aenderTermin, setAenderTermin] = useState<Termin | null>(null);
  const akte = useQuery({ queryKey: ["patient", pid], queryFn: () => api<Patient>(`patienten/${pid}/`), enabled: !!pid });
  const p = akte.data;
  const qc = useQueryClient();
  const melden = useHinweis();
  // Aufbau der Akte je Person (Design › Patientenakte); am Telefon immer mit Kopf oben
  const [darstellung, darstellungAendern] = useDarstellung();
  const mobil = useMobil();
  const fhd = ab(useStufe(), "fhd");
  const schmalerKopf = useSchmalerKopf();
  const ansicht: Aktenansicht = mobil ? "kopfzeile" : darstellung.aktenansicht;
  const [leisteZug, setLeisteZug] = useState<number | null>(null);
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
  // Reiter am Telefon: Die Leiste wischt seitlich; der aktive Reiter wird in die Mitte geholt
  const reiterLeiste = useRef<HTMLElement>(null);
  const location = useLocation();
  const { pathname } = location;
  useEffect(() => {
    const leiste = reiterLeiste.current;
    const aktiv = leiste?.querySelector<HTMLElement>(".segment.aktiv");
    if (!leiste) return;
    if (aktiv && leiste.scrollWidth > leiste.clientWidth) leiste.scrollLeft = aktiv.offsetLeft - (leiste.clientWidth - aktiv.offsetWidth) / 2;
    // am Telefon blendet der Rand aus, wo noch Reiter kommen (index.css, nav.segmente)
    const raender = () => {
      leiste.classList.toggle("am-anfang", leiste.scrollLeft <= 1);
      leiste.classList.toggle("am-ende", leiste.scrollLeft + leiste.clientWidth >= leiste.scrollWidth - 1);
    };
    raender();
    leiste.addEventListener("scroll", raender, { passive: true });
    window.addEventListener("resize", raender);
    return () => { leiste.removeEventListener("scroll", raender); window.removeEventListener("resize", raender); };
  }, [pathname, akte.data?.id]);
  // Karteikarte: Eine frisch geöffnete Akte beginnt mit der Karteikarte; „Übersicht“ bleibt als Reiter erreichbar
  const umgeleitet = useRef<number | null>(null);
  useEffect(() => {
    if (!p || ansicht !== "karteikarte" || umgeleitet.current === p.id) return;
    umgeleitet.current = p.id;
    const start = `/patienten/${p.id}`;
    if ((pathname === start || pathname === `${start}/`) && !location.state) navigate(`${start}/kartei`, { replace: true });
  }, [p, ansicht, pathname, location.state, navigate]);
  const gemeldet = useRef<number | null>(null);
  useEffect(() => {
    if (!p || gemeldet.current === p.id) return;
    gemeldet.current = p.id;
    api("meine-akten/geoeffnet/", { body: { patient: p.id } })
      .then(() => qc.invalidateQueries({ queryKey: ["meine-akten"] }))
      .catch(() => undefined); // nur ein Lesezeichen: scheitert es, bleibt die Akte trotzdem offen
  }, [p, qc]);
  // Sprung von einem offenen Punkt oder Termin (lib/sprungziele.ts, Wunsch 11.10.2026): passenden Dialog öffnen bzw. an die
  // Karte der Übersicht scrollen – einmal je Klick (``zeit``)
  const sprung = location.state as { oeffnen?: AktenAktion; termin?: number; zeit?: number } | null;
  const erledigterSprung = useRef<number | undefined>(undefined);
  const terminOeffnen = (id: number) => {
    void api<Termin>(`termine/${id}/`).then((t) => {
      if (p && !p.ist_abgeschlossen && !t.erledigt_am && darfBei("eintraege_erfassen", p)) setAenderTermin(t);
      else navigate(`/kalender?ansicht=woche&datum=${t.faellig_am}`);
    }).catch(() => melden("Der Termin ließ sich nicht öffnen.", "fehler"));
  };
  useEffect(() => {
    if (!p || !sprung?.zeit || erledigterSprung.current === sprung.zeit) return;
    erledigterSprung.current = sprung.zeit;
    const schreiben = !p.ist_abgeschlossen;
    const zeigen = (testid: string) => {
      let versuche = 0;
      const suchen = () => {
        const el = document.querySelector<HTMLElement>(`[data-testid="${testid}"]`);
        if (el) { el.scrollIntoView({ block: "center", behavior: "smooth" }); return; }
        if (++versuche < 40) window.setTimeout(suchen, 50);
      };
      suchen();
    };
    if (sprung.oeffnen === "stammdaten" && schreiben && darfBei("akten_bearbeiten", p)) setDialog("stammdaten");
    else if (sprung.oeffnen === "gewicht" && schreiben && darfBei("eintraege_erfassen", p)) { setVorbelegt(""); setDialog("gewicht"); }
    else if (sprung.oeffnen === "gewichtsverlauf") zeigen("gewichtskarte");
    else if (sprung.oeffnen === "termine") zeigen("aktentermine");
    if (sprung.termin) terminOeffnen(sprung.termin);
  }, [p, sprung, darfBei]);
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
    kontakt: offenBei("eintraege_erfassen"),
    // Schreiben mit E-Mail (F172): Patientenaufnahme, Terminbestätigung, Reisebescheinigung
    schreiben: offenBei("eintraege_erfassen"),
    gewicht: offenBei("eintraege_erfassen"),
  };
  useOhneRechtSchliessen(erlaubt[dialog], () => setDialog(""));
  // Tastenkürzel: der Handler wird unten gesetzt (braucht Akte und Reiter), hier einmal angemeldet
  const tasten = useRef<((e: KeyboardEvent) => void) | null>(null);
  const [kuerzelHilfe, setKuerzelHilfe] = useState(false);
  useEffect(() => {
    const h = (e: KeyboardEvent) => tasten.current?.(e);
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);
  tasten.current = null; // erst mit geladener Akte (unten) wieder gesetzt
  useOhneRechtSchliessen(offenBei("eintraege_erfassen"), () => setAenderTermin(null));
  // Dokumente: „Dokument hochladen“ im Kopf und Dateien auf die ganze Akte ziehen (08.10.2026)
  const { waehlen: dateiWaehlen, ablage } = useAktenAblage(offenBei("eintraege_erfassen") && p ? p.id : null);
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
  // Telefon mit Kopf „Alle Angaben“: Hinweise im aufklappbaren Teil des Kopfs statt neben dem Namen
  const hinweiseImKopf = mobil && ansicht === "kopfzeile" && darstellung.aktenkopf === "voll" && !!p.kopf?.hinweise?.length;
  const kontext: AktenKontext = {
    patient: p,
    erfassen: offen && darfBei("eintraege_erfassen", p),
    bearbeiten: offen && darfBei("akten_bearbeiten", p),
    planen: offen && darfBei("plaene_anlegen", p),
    terminAnlegen: () => setDialog("termin"),
    terminAendern: (t: Termin) => setAenderTermin(t),
    terminOeffnen,
    kontaktErfassen: (text?: string) => { setVorbelegt(text ?? ""); setDialog("kontakt"); },
    gewichtErfassen: (wert?: string) => { setVorbelegt(wert ?? ""); setDialog("gewicht"); },
    stammdatenBearbeiten: () => setDialog("stammdaten"),
    schreibenOeffnen: erlaubt.schreiben ? () => setDialog("schreiben") : null,
    schmal: ansicht !== "kopfzeile",
  };
  const k = p.kopf;
  const trend = k?.gewichtstrend;
  const basis = `/patienten/${p.id}`;

  // ---------------------------------------------------------------- Bausteine, die alle drei Ansichten nutzen
  const titel = (klein: boolean) => (
    <div className="flex items-center gap-2 flex-wrap min-w-0">
      <h1 className={cx("m-0 font-semibold", klein ? "text-[1.25rem]" : "text-[1.375rem] sm:text-[1.625rem]")}>{name(p)}</h1>
      <button type="button" className={cx("btn icon klein geist", k?.gemerkt ? "!text-akzent-text" : "")} data-testid="merken"
        aria-pressed={!!k?.gemerkt} aria-label={k?.gemerkt ? "Von der Merkliste nehmen" : "Auf die Merkliste"}
        title={k?.gemerkt ? "Von der Merkliste nehmen" : "Auf die Merkliste (erscheint auf der Startseite unter „Meine Akten“)"}
        disabled={merken.isPending} onClick={() => merken.mutate(!k?.gemerkt)}>
        <Icon name="stern" groesse={18} fill={k?.gemerkt ? "currentColor" : "none"} /></button>
    </div>
  );
  const status = (
    <>
      {p.ist_test ? <Chip art="warn"><Begriff name="testpatient">Testpatient</Begriff></Chip> : null}
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
      {/* Hinweise wie in der Patientenliste, dazu fehlende Angaben (F186); mit „×“ für 3/6/12 Monate ausblendbar (F119) */}
      {/* ruhig: ab zwei Hinweisen ein Chip „N Hinweise ▾“ (Nacharbeit F181); am Telefon stehen sie unter „Versorgung und Hinweise“ */}
      {hinweiseImKopf ? null : <HinweisChipsKompakt hinweise={k?.hinweise ?? []} patientId={p.id} ausblendbar={kontext.bearbeiten} />}
    </>
  );
  // CAVE: Nickelallergie und Gewichtsverlust stehen in jeder Ansicht direkt beim Namen; ebenso eine noch nicht erfasste
  // Nickelallergie (wichtig wegen des Katheters, Wunsch 11.10.2026) – mit Recht zum Bearbeiten öffnet sie die Stammdaten
  const nickelFehlt = p.nickelallergie === "unbekannt";
  const cave = p.nickelallergie === "ja" || nickelFehlt || trend?.warnung ? (
    <span className="inline-flex items-center gap-1.5 flex-wrap" data-testid="cave">
      {p.nickelallergie === "ja" ? <Chip art="fehler">Nickelallergie</Chip> : null}
      {nickelFehlt ? (kontext.bearbeiten
        ? <button type="button" className="chip warn cursor-pointer" onClick={() => setDialog("stammdaten")}
            title="Wichtig wegen des Katheters – jetzt in den Stammdaten erfassen" data-testid="nickel-fehlt">Nickelallergie nicht erfasst</button>
        : <Chip art="warn" title="Wichtig wegen des Katheters" data-testid="nickel-fehlt">Nickelallergie nicht erfasst</Chip>) : null}
      {trend?.warnung ? <Chip art="warn" title={`seit ${datum(trend.von)}`}>Gewicht {richtung(Number(trend.prozent))} {prozent(trend.prozent, false)}</Chip> : null}
    </span>
  ) : null;
  // neben dem Namen knapp: Geschlecht als Buchstabe (ausgeschrieben im Tooltip und in den Stammdaten)
  const meta = (
    <span className="num text-sm gedaempft" title={p.geschlecht ? GESCHLECHTER[p.geschlecht] : undefined}>
      Nr. {nummer(p.nummer)}{p.geschlecht ? ` · ${p.geschlecht}` : ""} · {datum(p.geburtsdatum)} ({alter(p.geburtsdatum)} J.)
    </span>
  );
  const aktionen = (klein: boolean) => (
    <div className={cx("flex items-center flex-wrap", klein ? "gap-1.5" : "gap-2")} data-testid="aktenaktionen">
      {kontext.erfassen ? <>
        {/* Kontakt und Gewicht als Dialog wie „Termin“ (Wunsch 08.10.2026) – die Seite bleibt, wo sie ist */}
        <Knopf klein={klein} icon="sprechblase" title="Kontakt erfassen (K)" onClick={() => kontext.kontaktErfassen()}>Kontakt</Knopf>
        <Knopf klein={klein} icon="waage" title="Gewicht erfassen (G)" onClick={() => kontext.gewichtErfassen()}>Gewicht</Knopf>
        <Knopf klein={klein} icon="kalender" title="Neuer Termin (T)" onClick={() => setDialog("termin")}>Termin</Knopf>
        {/* eigener Knopf statt unter „⋯“ (Bedienbarkeits-Review 10.10.2026); Ziehen auf die Akte geht weiterhin */}
        <Knopf klein={klein} icon="hochladen" title="Dokument in die Akte legen (Datei auswählen oder auf die Akte ziehen)" onClick={dateiWaehlen}>Dokument</Knopf>
      </> : null}
      {/* Offener Entwurf: fortsetzen statt eines zweiten Plans (Vorschlag „Erfassen“, 08.10.2026) */}
      {kontext.planen ? (p.kopf?.plan_entwurf
        ? <Knopf klein={klein} icon="stift" title={`Entwurf vom ${datum(p.kopf.plan_entwurf.erstellt_am)} fortsetzen (P)`}
            onClick={() => navigate(`${basis}/plaene/${p.kopf!.plan_entwurf!.id}/bearbeiten`)}>Entwurf fortsetzen</Knopf>
        : <Knopf klein={klein} icon="tropfen" title="Neuer Plan (P)" onClick={() => navigate(`${basis}/plaene/neu`)}>Neuer Plan</Knopf>) : null}
      <Menue label="Weitere Aktionen" eintraege={[
        ...(kontext.bearbeiten ? [{ text: "Stammdaten bearbeiten", onClick: () => setDialog("stammdaten") }] : []),
        { text: "Akte als PDF", onClick: () => setDialog("pdf") },
        // Unterlagen für die Sprechstunde (F116): der aktuellste Stand aller Bereiche auf einem Blatt
        { text: "Unterlagen für die Sprechstunde", onClick: () => setDialog("sprechstunde") },
        ...(erlaubt.schreiben ? [{ text: "Schreiben und E-Mail …", onClick: () => setDialog("schreiben") }] : []),
        ...(erlaubt.abschluss ? [{ text: "Akte abschließen", onClick: () => setDialog("abschluss"), gefaehrlich: true }] : []),
        ...(erlaubt.oeffnen ? [{ text: "Akte wieder öffnen", onClick: () => setDialog("oeffnen") }] : []),
      ]} />
    </div>
  );

  // Angaben des Kopfs – einmal festgelegt, je Ansicht in Gruppen oder in einer Zeile
  const terminText = k?.naechster_termin ? `${terminZeit(k.naechster_termin.faellig_am, k.naechster_termin.uhrzeit)} · ${k.naechster_termin.ort ?? TERMINARTEN[k.naechster_termin.art]}` : undefined;
  const angabe: Record<string, Angabe> | null = k ? {
    gewicht: {
      titel: "Gewicht", hinweis: k.gewicht ? `gemessen am ${datum(k.gewicht.am)}` : undefined,
      inhalt: k.gewicht ? <>{kg(k.gewicht.kg)} {trend ? (
        <span className={cx("font-semibold", trend.warnung ? "text-warn" : "gedaempft")} title={`seit ${datum(trend.von)}`}>
          {richtung(Number(trend.prozent))} {prozent(trend.prozent, false)}
        </span>
      ) : null}</> : "—",
    },
    bmi: {
      titel: "BMI", hinweis: p.groesse_cm != null ? `Größe ${zahl(p.groesse_cm)} cm` : undefined,
      inhalt: <span className="num">{k.bmi != null ? zahl(k.bmi, 1) : "—"}{p.groesse_cm != null ? <span className="gedaempft"> · {zahl(p.groesse_cm)} cm</span> : null}</span>,
    },
    plan: {
      titel: "Aktueller Plan",
      hinweis: k.aktueller_plan ? `gültig ab ${datum(k.aktueller_plan.gueltig_ab)}` : undefined,
      inhalt: k.aktueller_plan ? `${zahl(k.aktueller_plan.kcal)} kcal${k.aktueller_plan.laufzeit_h ? ` · ${zahl(k.aktueller_plan.laufzeit_h)} h` : ""}`
        : k.kein_plan ? <span className="gedaempft">nicht nötig</span> : "—",
    },
    katheter: { titel: "Katheter", hinweis: k.katheter ?? undefined, inhalt: k.katheter ?? <span className="gedaempft">nicht erfasst</span> },
    versorger: { titel: "Versorger", hinweis: k.versorger ?? undefined, inhalt: k.versorger ?? <span className="gedaempft">nicht erfasst</span> },
    ansprechpartner: {
      titel: "Ansprechpartner",
      hinweis: k.ansprechpartner ? [k.ansprechpartner, k.ansprechpartner_telefon].filter(Boolean).join(" · ") : undefined,
      inhalt: k.ansprechpartner ? <>{k.ansprechpartner}{k.ansprechpartner_telefon ? <> · <span className="num">{k.ansprechpartner_telefon}</span></> : null}</> : "—",
    },
    hausarzt: {
      titel: "Hausarzt", hinweis: k.hausarzt ? [k.hausarzt.name, k.hausarzt.telefon].filter(Boolean).join(" · ") : undefined,
      inhalt: k.hausarzt ? <>{k.hausarzt.name}{k.hausarzt.telefon ? <> · <span className="num">{k.hausarzt.telefon}</span></> : null}</> : "—",
    },
    // Klick öffnet den Termin (ohne Recht: Kalender), Wunsch 11.10.2026
    termin: { titel: "Nächster Termin", hinweis: terminText, inhalt: terminText && k.naechster_termin ? (
      <button type="button" className="termin-sprung text-akzent-text" title="Termin öffnen" data-testid="kopf-termin"
        onClick={() => terminOeffnen(k.naechster_termin!.id)}>{terminText}</button>) : "—" },
    kontakt: { titel: "Letzter Kontakt", inhalt: k.letzter_kontakt ? <span className="num">{datum(k.letzter_kontakt)}</span> : "—" },
    telefon: {
      titel: "Telefon", hinweis: [p.telefon, p.telefon2].filter(Boolean).join(" · ") || undefined,
      inhalt: p.telefon || p.telefon2 ? <span className="num">{[p.telefon, p.telefon2].filter(Boolean).join(" · ")}</span> : "—",
    },
    auskunft: {
      titel: k.auskunft.length > 1 ? `Auskunft an (${k.auskunft.length})` : "Auskunft an",
      hinweis: k.auskunft.map((a) => `${a.name}${a.beziehung ? ` (${a.beziehung})` : ""}${a.telefon ? ` ${a.telefon}` : ""}`).join("\n") || undefined,
      // Bezugspersonen mit Schweigepflichtentbindung – am Telefon sofort sichtbar; ein Klick führt zu den Kontaktdaten
      inhalt: <span data-testid="auskunft">{k.auskunft.length ? k.auskunft.map((a, i) => (
        <span key={a.id}>{i ? " · " : ""}
          <button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer hover:underline"
            onClick={() => navigate(basis, { state: { bezugsperson: a.id, zeit: Date.now() } })}>
            {a.name}{a.beziehung ? ` (${a.beziehung})` : ""}</button>
          {a.telefon ? <> <span className="num">{a.telefon}</span></> : null}</span>
      )) : <span className="gedaempft">niemand eingetragen</span>}</span>,
    },
    nickel: {
      titel: "Nickelallergie",
      inhalt: p.nickelallergie === "ja" ? <Chip art="fehler">ja</Chip>
        : p.nickelallergie === "nein" ? "nein"
        : kontext.bearbeiten ? (
          <button type="button" className="bg-transparent border-0 p-0 text-warn cursor-pointer inline-flex items-center gap-1 font-medium"
            onClick={() => setDialog("stammdaten")}><Icon name="warnung" /> nicht erfasst</button>
        ) : <span className="text-warn">nicht erfasst</span>,
    },
    versicherung: {
      titel: "Versicherung",
      inhalt: [VERSICHERUNG_KURZ[p.versicherungsart], p.krankenkasse].filter(Boolean).join(" · ") || "—",
    },
  } : null;
  const gruppen: Gruppe[] = angabe ? [
    { titel: "Ernährung", angaben: [angabe.gewicht, angabe.bmi, angabe.plan, angabe.katheter] },
    { titel: "Versorgung", angaben: [angabe.versorger, angabe.ansprechpartner, angabe.hausarzt],
      bearbeiten: kontext.bearbeiten ? () => setDialog("stammdaten") : undefined },
    { titel: "Termine und Kontakt", angaben: [angabe.termin, angabe.kontakt, angabe.telefon] },
    { titel: "Hinweise und Auskunft", angaben: [angabe.nickel, angabe.auskunft, angabe.versicherung] },
  ] : [];

  // Reihenfolge (Wunsch 10.10.2026): Diagnosen, Therapie, Empfehlung und Infusionspläne direkt nach der Übersicht –
  // ein Klick, ohne Suchen; Befunde und Unterlagen danach; Verlauf und Datenschutz (selten) klein am Ende. Jeder
  // Bereich bleibt ein eigener Reiter (F121).
  const reiter: ReiterEintrag[] = ([
    ...(ansicht === "karteikarte" ? [{ zu: `${basis}/kartei`, text: "Karteikarte", stufe: "haupt" }] : []),
    { zu: basis, text: "Übersicht", ende: true, gruppe: "Akte", stufe: "haupt" },
    { zu: `${basis}/diagnosen`, text: "Diagnosen", zahl: k?.zaehler.diagnosen, gruppe: "Behandlung", stufe: "haupt" },
    { zu: `${basis}/therapie`, text: "Therapie", stufe: "haupt" },
    { zu: `${basis}/empfehlung`, text: "Empfehlung", stufe: "haupt" },
    { zu: `${basis}/plaene`, text: "Infusionspläne", zahl: k?.zaehler.infusionsplaene, stufe: "haupt" },
    { zu: `${basis}/kontakte`, text: "Kontakte", zahl: k?.zaehler.kontakte, stufe: "haupt" },
    // Wünsche aus der Praxis vom 06.10.2026 (F112–F115)
    { zu: `${basis}/labor`, text: "Labor", zahl: k?.zaehler.laborbefunde, gruppe: "Befunde und Unterlagen", stufe: "neben" },
    { zu: `${basis}/bia`, text: "BIA", zahl: k?.zaehler.bia_messungen, stufe: "neben" },
    { zu: `${basis}/berichte`, text: "Berichte", zahl: k?.zaehler.berichte, stufe: "neben" },
    { zu: `${basis}/dokumente`, text: "Dokumente", zahl: k?.zaehler.dokumente, stufe: "neben" },
    { zu: `${basis}/verlauf`, text: "Verlauf", gruppe: "Weiteres", stufe: "ende" },
    { zu: `${basis}/datenschutz`, text: "Datenschutz", zahl: k?.datenschutz_anfragen || undefined, stufe: "ende" },
  ] as ReiterEintrag[]).map((r, i) => (i < 10 ? { ...r, kuerzel: `${r.text} (Alt+${(i + 1) % 10})` } : r));
  // Tastenkürzel in der Akte (Vorschlag „Schneller mit der Tastatur“, 08.10.2026); nicht in Eingabefeldern und nicht,
  // solange ein Dialog offen ist
  tasten.current = (e: KeyboardEvent) => {
    if (e.defaultPrevented || e.ctrlKey || e.metaKey) return;
    const ziel = e.target as HTMLElement | null;
    if (ziel && (ziel.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(ziel.tagName))) return;
    if (document.querySelector('[role="dialog"], [role="alertdialog"], [role="menu"]')) return;
    if (e.altKey) {
      const m = /^Digit(\d)$/.exec(e.code);
      if (!m) return;
      const r = reiter[(Number(m[1]) + 9) % 10];
      if (!r) return;
      e.preventDefault();
      navigate(r.zu);
      return;
    }
    const taste = e.key.toLowerCase();
    const aktion = taste === "k" && kontext.erfassen ? () => kontext.kontaktErfassen()
      : taste === "g" && kontext.erfassen ? () => kontext.gewichtErfassen()
      : taste === "t" && kontext.erfassen ? () => setDialog("termin")
      : taste === "p" && kontext.planen ? () => navigate(p.kopf?.plan_entwurf ? `${basis}/plaene/${p.kopf.plan_entwurf.id}/bearbeiten` : `${basis}/plaene/neu`)
      : e.key === "?" ? () => setKuerzelHilfe(true)
      : null;
    if (!aktion) return;
    e.preventDefault();
    aktion();
  };
  // Jeder Bereich ein eigener Reiter (Wunsch 07.10.2026, F121); bei schmalem Fenster umbrechen die Reiter, am
  // Telefon lassen sie sich seitlich wischen (der aktive bleibt im Blick)
  const reiterWaagerecht = (
    <nav aria-label="Aktenbereiche" className="segmente akte-reiter self-start flex-wrap h-auto relative shrink-0" ref={reiterLeiste}>
      {reiter.map((r, i) => (
        <Fragment key={r.zu}>
          {i > 0 && r.stufe === "neben" && reiter[i - 1].stufe === "haupt" ? <span className="reiter-trenner" aria-hidden="true" /> : null}
          {r.stufe === "ende" && reiter[i - 1]?.stufe !== "ende" ? <span className="reiter-ende" aria-hidden="true" /> : null}
          <Reiter {...r} />
        </Fragment>
      ))}
    </nav>
  );

  const meldungen = (
    <>
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
    </>
  );

  const dialoge = (
    <>
      {kontext.bearbeiten ? <StammdatenDialog patient={p} offen={dialog === "stammdaten"} onOffen={(o) => setDialog(o ? "stammdaten" : "")} /> : null}
      {/* Dialoge nur mit Recht: entzieht die Administration ein Recht, verschwindet auch ein offener Dialog */}
      {erlaubt.abschluss ? <AbschlussDialog patient={p} offen={dialog === "abschluss"} onOffen={(o) => setDialog(o ? "abschluss" : "")} /> : null}
      {erlaubt.oeffnen ? <WiederOeffnenDialog patient={p} offen={dialog === "oeffnen"} onOffen={(o) => setDialog(o ? "oeffnen" : "")} /> : null}
      <PdfDialog offen={dialog === "pdf"} onOffen={(o) => setDialog(o ? "pdf" : "")} titel={`Akte ${name(p)} als PDF`}
        pfad={`patienten/${p.id}/pdf/`} dateiname={`Patientendatenblatt-${p.nummer}.pdf`} />
      <PdfDialog offen={dialog === "sprechstunde"} onOffen={(o) => setDialog(o ? "sprechstunde" : "")}
        titel={`Unterlagen für die Sprechstunde · ${name(p)}`}
        pfad={`patienten/${p.id}/sprechstunde/`} dateiname={`Sprechstunde-${p.nummer}.pdf`} />
      {erlaubt.schreiben ? <SchreibenAusAkte patient={p} offen={dialog === "schreiben"} onOffen={(o) => setDialog(o ? "schreiben" : "")} /> : null}
      {kontext.erfassen ? <TerminDialog offen={dialog === "termin"} onOffen={(o) => setDialog(o ? "termin" : "")} patientId={p.id} patientName={name(p)} /> : null}
      {kontext.erfassen ? <KontaktDialog offen={dialog === "kontakt"} onOffen={(o) => setDialog(o ? "kontakt" : "")}
        vorgabe={{ id: p.id, name: name(p), ist_test: p.ist_test }} text={vorbelegt} /> : null}
      {kontext.erfassen ? <GewichtDialog offen={dialog === "gewicht"} onOffen={(o) => setDialog(o ? "gewicht" : "")}
        vorgabe={{ id: p.id, name: name(p), ist_test: p.ist_test }} wert={vorbelegt} /> : null}
      {kontext.erfassen ? <TerminDialog offen={!!aenderTermin} onOffen={(o) => { if (!o) setAenderTermin(null); }} termin={aenderTermin}
        patientName={name(p)} /> : null}
      {ablage}
      <Dialog offen={kuerzelHilfe} onOffen={setKuerzelHilfe} titel="Tastenkürzel in der Akte" breite={460}
        beschreibung="Nicht während in einem Eingabefeld geschrieben wird.">
        <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm" data-testid="tastenkuerzel">
          {([["K", "Kontakt erfassen"], ["G", "Gewicht erfassen"], ["T", "Neuer Termin"], ["P", "Neuer Plan bzw. Entwurf fortsetzen"],
            ["Alt+1 … Alt+9", "Reiter der Akte wechseln"], ["Strg Enter", "im Dialog speichern"], ["Esc", "Dialog schließen"],
            ["Strg K", "Patientensuche"], ["?", "diese Übersicht"]] as const).map(([t, w]) => (
            <Fragment key={t}><dt><kbd className="num font-medium border border-rand rounded-[0.3125rem] px-1.5 py-0.5 text-[0.8125rem]">{t}</kbd></dt><dd className="m-0">{w}</dd></Fragment>
          ))}
        </dl>
      </Dialog>
    </>
  );
  const pfad = [{ text: "Patienten", zu: "/patienten" }, { text: name(p) }];

  // ---------------------------------------------------------------- Ansicht 2: Seitenleiste mit senkrechten Reitern
  if (ansicht === "seitenleiste") {
    // wie im Entwurf: Leiste und senkrechte Reiter bündig über die volle Höhe, nur der Inhalt rechts mit Rand und
    // runden Karten (Wunsch 08.10.2026)
    return (
      <Seite pfad={pfad} className="akte-voll">
        <div className="akte-leiste" data-testid="akte-ansicht" data-ansicht="seitenleiste"
          style={{ "--leiste": `${leisteZug ?? darstellung.aktenleiste_breite}px` } as CSSProperties}>
          <aside className="akte-leiste-kopf flex flex-col gap-3" data-testid="aktenkopf" aria-label="Angaben zur Akte">
            {aktionen(true)}
            <div className="flex flex-col gap-1.5 border-t border-rand pt-3">
              {titel(false)}
              {meta}
              <div className="flex items-center gap-1.5 flex-wrap empty:hidden">{status}{cave}</div>
            </div>
            {k ? <div className="border-t border-rand pt-3" data-testid="kennzahlen"><Gruppen gruppen={gruppen} art="leiste" /></div> : null}
          </aside>
          <Leistengriff breite={darstellung.aktenleiste_breite} onBreite={(px) => darstellungAendern({ aktenleiste_breite: px })}
            onZiehen={setLeisteZug} />
          <div className="akte-leiste-inhalt">
            <nav aria-label="Aktenbereiche" className="akte-vreiter" data-testid="senkrechte-reiter">
              <div className="akte-vreiter-innen">
                {reiter.map((r) => (
                  <Fragment key={r.zu}>
                    {r.gruppe ? <span className="vreiter-gruppe" aria-hidden="true">{r.gruppe}</span> : null}
                    <Reiter {...r} senkrecht />
                  </Fragment>
                ))}
              </div>
            </nav>
            <div className="akte-leiste-flaeche stapel min-w-0 flex flex-col gap-4 md:gap-5">
              {meldungen}
              <Outlet context={kontext} />
            </div>
          </div>
        </div>
        {dialoge}
      </Seite>
    );
  }

  // ---------------------------------------------------------------- Ansicht 3: Karteikarte wie in einer Arztsoftware
  if (ansicht === "karteikarte" && angabe) {
    const kurz = [angabe.gewicht, angabe.bmi, angabe.plan, angabe.termin];
    return (
      <Seite pfad={pfad}>
        <Karte className="px-4 sm:px-[1.125rem] py-3 flex items-center gap-x-5 gap-y-2 flex-wrap" data-testid="aktenkopf">
          <div className="flex items-center gap-x-3 gap-y-1 flex-wrap min-w-0">
            {titel(true)}
            {meta}
            {status}
          </div>
          {cave ? <span className="inline-flex items-center gap-1.5"><span className="text-[0.6875rem] font-bold tracking-[.08em] text-fehler">CAVE</span>{cave}</span> : null}
          <div className="flex items-center gap-x-5 gap-y-1 flex-wrap ml-auto text-sm" data-testid="kurzwerte">
            {kurz.map((a) => (
              <span key={a.titel} className="inline-flex items-baseline gap-1.5 whitespace-nowrap" title={a.hinweis}>
                <span className="text-[0.75rem] gedaempft">{a.titel}</span><span className="font-medium">{a.inhalt}</span>
              </span>
            ))}
          </div>
          {aktionen(true)}
        </Karte>
        {meldungen}
        {reiterWaagerecht}
        <div className="akte-kartei" data-testid="akte-ansicht" data-ansicht="karteikarte">
          <div className="stapel min-w-0 flex flex-col gap-4 md:gap-5"><Outlet context={kontext} /></div>
          <aside className="akte-kartei-spalte" aria-label="Angaben zur Akte">
            <Karte className="px-4 py-4" data-testid="kennzahlen"><Gruppen gruppen={gruppen} art="leiste" /></Karte>
          </aside>
        </div>
        {dialoge}
      </Seite>
    );
  }

  // ---------------------------------------------------------------- Ansicht 1: Kopfzeile mit Gruppen (Standard)
  const stufe = darstellung.aktenkopf;
  return (
    <Seite pfad={pfad} fuellen>
      <Karte className={cx("px-4 sm:px-[1.125rem] pt-3 flex flex-col gap-2 shrink-0", mobil ? "pb-3" : "pb-0")}
        data-testid="aktenkopf" data-stufe={stufe}>
        <div className="flex items-center justify-between gap-x-4 gap-y-2 flex-wrap">
          {/* Name, Hinweise und Nummer/Geburtsdatum in einer Zeile (vorher zwei) */}
          <div className="flex items-center gap-x-2.5 gap-y-1 flex-wrap min-w-0">{titel(true)}{status}{cave}{meta}</div>
          {aktionen(!fhd)}
        </div>
        {k && stufe === "voll" && angabe ? (
          <KopfVoll angabe={angabe} mobil={schmalerKopf}
            hinweise={hinweiseImKopf ? <HinweisChips hinweise={[...(k.hinweise ?? [])].sort((x, y) => Number(y.stufe === "ueberfaellig") - Number(x.stufe === "ueberfaellig"))} patientId={p.id} ausblendbar={kontext.bearbeiten} /> : undefined}
            anzahlHinweise={hinweiseImKopf ? k.hinweise?.length : 0} bearbeiten={kontext.bearbeiten ? () => setDialog("stammdaten") : undefined} unter={{
            gewicht: k.bmi != null || k.gewicht ? <>{k.bmi != null ? <><Begriff name="bmi">BMI</Begriff> {zahl(k.bmi, 1)}</> : null}
              {k.bmi != null && k.gewicht ? " · " : null}{k.gewicht ? `gemessen ${datum(k.gewicht.am)}` : null}</> : undefined,
            plan: k.aktueller_plan ? `gültig ab ${datum(k.aktueller_plan.gueltig_ab)}` : undefined,
            terminWann: k.naechster_termin ? (
              <button type="button" className="termin-sprung text-akzent-text" title="Termin öffnen" data-testid="kopf-termin"
                onClick={() => terminOeffnen(k.naechster_termin!.id)}>{terminZeit(k.naechster_termin.faellig_am, k.naechster_termin.uhrzeit)}</button>
            ) : undefined,
            terminWo: k.naechster_termin ? k.naechster_termin.ort ?? TERMINARTEN[k.naechster_termin.art] : undefined,
            kontakt: k.letzter_kontakt ? vorTagen(k.letzter_kontakt) : undefined,
          }} />
        ) : null}
        {k && stufe === "kompakt" && angabe ? (
          <div className="overflow-hidden -mx-3 sm:-mx-[1.125rem]">
            {/* eine Zeile mit den wichtigsten Angaben */}
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-y-3 -ml-px" data-testid="kennzahlen">
              {[angabe.gewicht, angabe.plan, angabe.termin, angabe.versorger, angabe.nickel].map((a) => (
                <Kennzahl key={a.titel} titel={a.titel} hinweis={a.hinweis}>{a.inhalt}</Kennzahl>
              ))}
            </div>
          </div>
        ) : null}
        {mobil ? null : <Kopfgriff stufe={stufe} onStufe={(s) => darstellungAendern({ aktenkopf: s })} />}
      </Karte>
      {meldungen}
      {reiterWaagerecht}
      <div className="akte-flaeche" data-testid="akte-flaeche"><Outlet context={kontext} /></div>
      {dialoge}
    </Seite>
  );
}
