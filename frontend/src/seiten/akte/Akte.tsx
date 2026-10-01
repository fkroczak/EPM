/** Entwurf 4 · Patientenakte: Kopf mit Kerndaten und Schnellaktionen, Reiter mit Zählern. */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Outlet, useNavigate, useOutletContext, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuswahl, useVersorgerListe } from "@/lib/daten";
import { alter, datum, eingabeDatum, eingabeZahl, heuteIso, kg, nummer, prozent, terminZeit, zahl } from "@/lib/format";
import { ABSCHLUSSANLAESSE, GESCHLECHTER, TERMINARTEN } from "@/lib/typen";
import type { Patient } from "@/lib/typen";
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

function Kennzahl({ titel, children, erste }: { titel: string; children: ReactNode; erste?: boolean }) {
  return (
    <div className={cx("flex flex-col gap-0.5 min-w-0 px-[18px]", !erste && "border-l border-rand")}>
      <span className="lbl text-[0.78rem] gedaempft font-medium">{titel}</span>
      <span className="text-sm truncate">{children}</span>
    </div>
  );
}

/** Stammdaten bearbeiten (Felder wie „Neuer Patient“) */
function StammdatenDialog({ patient, offen, onOffen }: { patient: Patient; offen: boolean; onOffen: (o: boolean) => void }) {
  const start = () => ({
    nachname: patient.nachname, vorname: patient.vorname, geschlecht: patient.geschlecht, geburtsdatum: datum(patient.geburtsdatum),
    groesse: patient.groesse_cm != null ? zahl(patient.groesse_cm) : "", strasse: patient.strasse, plz: patient.plz, ort: patient.ort,
    telefon: patient.telefon, email: patient.email, versorger: patient.versorger ? String(patient.versorger) : "",
    ansprechpartner: patient.ansprechpartner ? String(patient.ansprechpartner) : "", katheter: patient.katheter ? String(patient.katheter) : "",
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
      versorger: f.versorger ? Number(f.versorger) : null, ansprechpartner: f.ansprechpartner ? Number(f.ansprechpartner) : null,
      katheter: f.katheter ? Number(f.katheter) : null, nickelallergie: f.nickelallergie, hausarzt: f.hausarzt.trim(),
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
        <fieldset className="border-0 p-0 m-0">
          <legend className="text-sm font-medium mb-2">Nickelallergie</legend>
          <div className="flex gap-3 h-9 items-center">
            {["ja", "nein", "unbekannt"].map((w) => (
              <label key={w} className="flex items-center gap-1.5 text-sm"><input type="radio" name="nickel" value={w} checked={f.nickelallergie === w} onChange={set("nickelallergie")} />{w}</label>
            ))}
          </div>
        </fieldset>
        <Feld label="Straße und Hausnummer" className="col-span-2" fehler={e.strasse}>{(p) => <Eingabe {...p} value={f.strasse} onChange={set("strasse")} />}</Feld>
        <Feld label="PLZ" fehler={e.plz}>{(p) => <Eingabe {...p} className="num" value={f.plz} onChange={set("plz")} />}</Feld>
        <Feld label="Ort" fehler={e.ort}>{(p) => <Eingabe {...p} value={f.ort} onChange={set("ort")} />}</Feld>
        <Feld label="Telefon" className="col-span-2" fehler={e.telefon}>{(p) => <Eingabe {...p} className="num" value={f.telefon} onChange={set("telefon")} />}</Feld>
        <Feld label="E-Mail" className="col-span-2" fehler={e.email}>{(p) => <Eingabe {...p} type="email" value={f.email} onChange={set("email")} />}</Feld>
        <Feld label="Versorger" className="col-span-2" fehler={e.versorger}>
          {(p) => (
            <Auswahl {...p} value={f.versorger} onChange={(ev) => setF((a) => ({ ...a, versorger: ev.target.value, ansprechpartner: "" }))}>
              <option value="">— noch keiner —</option>
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
              <option value="">— noch keiner —</option>
              {(katheter.data ?? []).filter((k) => k.aktiv || String(k.id) === f.katheter).map((k) => <option key={k.id} value={k.id}>{k.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Hausarzt" className="col-span-2" fehler={e.hausarzt}>{(p) => <Eingabe {...p} value={f.hausarzt} onChange={set("hausarzt")} />}</Feld>
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
  const { darf, darfBei, ich } = useAuth();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"" | "stammdaten" | "abschluss" | "oeffnen" | "termin">("");
  const akte = useQuery({ queryKey: ["patient", pid], queryFn: () => api<Patient>(`patienten/${pid}/`), enabled: !!pid });
  const p = akte.data;
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
              {p.ist_test ? <Chip art="warn">Testpatient</Chip> : null}
              {ich?.schreibt_nur_testpatienten && !p.ist_test
                ? <Chip title="Admins schreiben Patientendaten nur bei Testpatienten">nur lesen</Chip> : null}
              {p.ist_abgeschlossen ? <Chip>abgeschlossen</Chip> : null}
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
              { text: "Akte als PDF", onClick: () => undefined, aus: true, hinweis: "folgt mit der PDF-Erzeugung (F23)" },
              ...(offen && darfBei("akten_abschliessen", p) ? [{ text: "Akte abschließen", onClick: () => setDialog("abschluss"), gefaehrlich: true }] : []),
              ...(!offen && darf("akten_wieder_oeffnen") ? [{ text: "Akte wieder öffnen", onClick: () => setDialog("oeffnen") }] : []),
            ]} />
          </div>
        </div>
        {k ? (
          <div className="flex flex-wrap gap-y-3 -mx-[18px]" data-testid="kennzahlen">
            <Kennzahl titel="Gewicht" erste>
              {k.gewicht ? <>{kg(k.gewicht.kg)} {trend ? (
                <span className={cx("font-semibold", trend.warnung ? "text-warn" : "gedaempft")} title={`seit ${datum(trend.von)}`}>
                  {richtung(Number(trend.prozent))} {prozent(trend.prozent, false)}
                </span>
              ) : null}</> : "—"}
            </Kennzahl>
            <Kennzahl titel="BMI"><span className="num">{k.bmi != null ? zahl(k.bmi, 1) : "—"}</span></Kennzahl>
            <Kennzahl titel="Katheter">{k.katheter ?? "—"}</Kennzahl>
            <Kennzahl titel="Versorger">{k.versorger ?? "—"}</Kennzahl>
            <Kennzahl titel="Ansprechpartner">{k.ansprechpartner ? <>{k.ansprechpartner}{k.ansprechpartner_telefon ? <> · <span className="num">{k.ansprechpartner_telefon}</span></> : null}</> : "—"}</Kennzahl>
            <Kennzahl titel="Aktueller Plan">{k.aktueller_plan ? `${zahl(k.aktueller_plan.kcal)} kcal${k.aktueller_plan.laufzeit_h ? ` · ${zahl(k.aktueller_plan.laufzeit_h)} h` : ""}` : "—"}</Kennzahl>
            <Kennzahl titel="Nächster Termin">
              {k.naechster_termin ? `${terminZeit(k.naechster_termin.faellig_am, k.naechster_termin.uhrzeit)} · ${k.naechster_termin.ort ?? TERMINARTEN[k.naechster_termin.art]}` : "—"}
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
        ) : null}
      </Karte>

      {p.ist_abgeschlossen ? (
        <Meldung art="info">
          Akte abgeschlossen am {datum(p.abgeschlossen_am)} · Anlass: {ABSCHLUSSANLAESSE[p.abschluss_anlass] ?? p.abschluss_anlass}
          {p.abschluss_notiz ? ` · ${p.abschluss_notiz}` : ""}. Die Akte ist nur noch lesbar.
        </Meldung>
      ) : null}

      <nav aria-label="Aktenbereiche" className="segmente self-start">
        <Reiter zu={basis} text="Übersicht" ende />
        <Reiter zu={`${basis}/therapie`} text="Diagnose & Therapie" />
        <Reiter zu={`${basis}/kontakte`} text="Kontakte" zahl={k?.zaehler.kontakte} />
        <Reiter zu={`${basis}/plaene`} text="Infusionspläne" zahl={k?.zaehler.infusionsplaene} />
        <Reiter zu={`${basis}/dokumente`} text="Dokumente" zahl={k?.zaehler.dokumente} />
        <Reiter zu={`${basis}/verlauf`} text="Verlauf" />
      </nav>

      <Outlet context={kontext} />

      {kontext.bearbeiten ? <StammdatenDialog patient={p} offen={dialog === "stammdaten"} onOffen={(o) => setDialog(o ? "stammdaten" : "")} /> : null}
      <AbschlussDialog patient={p} offen={dialog === "abschluss"} onOffen={(o) => setDialog(o ? "abschluss" : "")} />
      <WiederOeffnenDialog patient={p} offen={dialog === "oeffnen"} onOffen={(o) => setDialog(o ? "oeffnen" : "")} />
      <TerminDialog offen={dialog === "termin"} onOffen={(o) => setDialog(o ? "termin" : "")} patientId={p.id} patientName={name(p)} />
    </Seite>
  );
}
