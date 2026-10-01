/**
 * Ärzte und Bezugspersonen der Akte (Festlegung 01.10.2026).
 * - Ärzte kommen aus der gemeinsamen Ärzteliste und werden mit Rolle zugeordnet (Hausarzt, Facharzt …).
 * - Bezugspersonen (Mutter, Vater, Betreuer/in …) gehören nur zu dieser Akte; „Auskunft erlaubt“ =
 *   Schweigepflichtentbindung liegt vor und steht im Patientenkopf.
 * Nichts wird gelöscht: Nicht mehr Aktuelles wird markiert und bleibt im Verlauf.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { useAerzteListe, useAuswahl } from "@/lib/daten";
import { ARZTROLLEN } from "@/lib/typen";
import type { Bezugsperson, PatientArzt } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { useAkte } from "./Akte";

function useNeuLaden() {
  const { patient } = useAkte();
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    void qc.invalidateQueries({ queryKey: ["aerzte"] });
  };
}

function Kontaktzeile({ telefon, mobil, fax, email }: { telefon?: string; mobil?: string; fax?: string; email?: string }) {
  const teile = [
    telefon ? <span key="t" className="inline-flex items-center gap-1"><Icon name="telefon" groesse={14} /><span className="num">{telefon}</span></span> : null,
    mobil ? <span key="m" className="num">mobil {mobil}</span> : null,
    fax ? <span key="f" className="num">Fax {fax}</span> : null,
    email ? <a key="e" href={`mailto:${email}`} className="truncate">{email}</a> : null,
  ].filter(Boolean);
  return teile.length ? <span className="flex flex-wrap gap-x-3 gap-y-0.5 text-[0.8125rem]">{teile}</span> : null;
}

// ------------------------------------------------------------------ Ärzte
function ArztZuordnungDialog({ zuordnung, offen, onOffen }: { zuordnung: PatientArzt | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const { darf } = useAuth();
  const aerzte = useAerzteListe();
  const [arzt, setArzt] = useState("");
  const [rolle, setRolle] = useState("hausarzt");
  const [notiz, setNotiz] = useState("");
  const neuLaden = useNeuLaden();
  const melden = useHinweis();
  useEffect(() => {
    if (offen) {
      setArzt(zuordnung ? String(zuordnung.arzt) : "");
      setRolle(zuordnung?.rolle ?? "hausarzt");
      setNotiz(zuordnung?.notiz ?? "");
    }
  }, [offen, zuordnung]);
  const fertig = (text: string) => { neuLaden(); melden(text); onOffen(false); };
  const speichern = useMutation({
    mutationFn: () => zuordnung
      ? api<PatientArzt>(`patient-aerzte/${zuordnung.id}/`, { method: "PATCH", body: { rolle, notiz } })
      : api<PatientArzt>("patient-aerzte/", { body: { patient: patient.id, arzt: arzt ? Number(arzt) : null, rolle, notiz } }),
    onSuccess: () => fertig(zuordnung ? "Zuordnung gespeichert." : "Arzt zugeordnet."),
  });
  const aktivSetzen = useMutation({
    mutationFn: (aktiv: boolean) => api<PatientArzt>(`patient-aerzte/${zuordnung!.id}/`, { method: "PATCH", body: { aktiv } }),
    onSuccess: (z) => fertig(z.aktiv ? "Wieder zuständig." : "Als nicht mehr zuständig markiert."),
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} breite={560}
      titel={zuordnung ? zuordnung.arzt_daten.name : "Arzt zuordnen"}
      beschreibung={zuordnung ? "Kontaktdaten ändern Sie in der Ärzteliste – sie gelten dann für alle Patienten."
        : "Aus der gemeinsamen Ärzteliste. Fehlt ein Arzt, legen Sie ihn dort einmal an."}
      fuss={<>
        {zuordnung && zuordnung.aktiv ? <Knopf className="mr-auto" laedt={aktivSetzen.isPending} onClick={() => aktivSetzen.mutate(false)}>Nicht mehr zuständig</Knopf> : null}
        {zuordnung && !zuordnung.aktiv ? <Knopf className="mr-auto" laedt={aktivSetzen.isPending} onClick={() => aktivSetzen.mutate(true)}>Wieder zuständig</Knopf> : null}
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!zuordnung && !arzt} onClick={() => speichern.mutate()}>
          {zuordnung ? "Speichern" : "Zuordnen"}
        </Knopf>
      </>}>
      <form className="grid grid-cols-2 gap-3" onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        {!zuordnung ? (
          <div className="col-span-2 relative">
            {darf("versorger_pflegen") ? <Link to="/aerzte?neu=1" className="absolute right-0 top-0 text-[0.8125rem]">Neuen Arzt anlegen</Link> : null}
            <Feld label="Arzt" pflicht fehler={f.arzt}>
              {(p) => (
                <Auswahl {...p} value={arzt} onChange={(e) => setArzt(e.target.value)}>
                  <option value="">— bitte wählen —</option>
                  {(aerzte.data ?? []).filter((a) => a.aktiv).map((a) => (
                    <option key={a.id} value={a.id}>{a.name}{a.fachrichtung ? ` · ${a.fachrichtung}` : ""}{a.ort ? ` (${a.ort})` : ""}</option>
                  ))}
                </Auswahl>
              )}
            </Feld>
          </div>
        ) : null}
        <Feld label="Rolle" fehler={f.rolle}>
          {(p) => (
            <Auswahl {...p} value={rolle} onChange={(e) => setRolle(e.target.value)}>
              {Object.entries(ARZTROLLEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Notiz" fehler={f.notiz} hinweis="z. B. „Kontrolle halbjährlich“">
          {(p) => <Eingabe {...p} value={notiz} onChange={(e) => setNotiz(e.target.value)} />}
        </Feld>
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler" className="col-span-2">{speichern.error.message}</Meldung> : null}
        {aktivSetzen.error ? <Meldung art="fehler" className="col-span-2">{aktivSetzen.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

export function AerzteKarte() {
  const { patient, bearbeiten } = useAkte();
  const [frueher, setFrueher] = useState(false);
  const [dialog, setDialog] = useState<{ offen: boolean; z: PatientArzt | null }>({ offen: false, z: null });
  useOhneRechtSchliessen(bearbeiten, () => setDialog({ offen: false, z: null }));
  const liste = useQuery({
    queryKey: ["patient", patient.id, "aerzte"],
    queryFn: () => api<PatientArzt[]>(`patient-aerzte/${abfrage({ patient: patient.id })}`),
  });
  const alle = liste.data ?? [];
  const sichtbar = alle.filter((z) => frueher || z.aktiv);
  const anzahlFrueher = alle.filter((z) => !z.aktiv).length;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="aerzte">
      <KartenKopf titel="Ärzte" rechts={bearbeiten ? <Knopf klein icon="plus" onClick={() => setDialog({ offen: true, z: null })}>Arzt</Knopf> : null} />
      {liste.isLoading ? <Laden /> : sichtbar.length ? (
        <ul className="m-0 p-0 list-none flex flex-col gap-3">
          {sichtbar.map((z) => {
            const a = z.arzt_daten;
            const adresse = [a.strasse, [a.plz, a.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
            return (
              <li key={z.id} className={cx("flex flex-col gap-0.5 text-sm", !z.aktiv && "opacity-60")} data-testid="arzt-zuordnung">
                <span className="flex items-center gap-2 flex-wrap">
                  {bearbeiten ? (
                    <button type="button" className="bg-transparent border-0 p-0 text-left font-medium text-akzent-text cursor-pointer"
                      onClick={() => setDialog({ offen: true, z })}>{a.name}</button>
                  ) : <span className="font-medium">{a.name}</span>}
                  <Chip art={z.rolle === "hausarzt" ? "akzent" : "neutral"}>{z.rolle_name}</Chip>
                  {!z.aktiv ? <Chip>nicht mehr zuständig</Chip> : null}
                  {!a.aktiv ? <Chip>Arzt deaktiviert</Chip> : null}
                </span>
                <span className="text-[0.8125rem] gedaempft">{[a.praxis, a.fachrichtung, adresse].filter(Boolean).join(" · ") || "—"}</span>
                <Kontaktzeile telefon={a.telefon} fax={a.fax} email={a.email} />
                {z.notiz ? <span className="text-[0.8125rem]">{z.notiz}</span> : null}
              </li>
            );
          })}
        </ul>
      ) : <Leer>Noch kein Arzt zugeordnet.</Leer>}
      <div className="flex gap-3 text-[0.8125rem] flex-wrap">
        {anzahlFrueher ? (
          <button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer" onClick={() => setFrueher(!frueher)}>
            {frueher ? "Nur aktuelle anzeigen" : `Frühere anzeigen (${anzahlFrueher})`}
          </button>
        ) : null}
        <Link to="/aerzte">Ärzteliste</Link>
      </div>
      {bearbeiten ? <ArztZuordnungDialog zuordnung={dialog.z} offen={dialog.offen} onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
    </Karte>
  );
}

// ------------------------------------------------------------------ Bezugspersonen
const BP_FELDER = ["name", "telefon", "mobil", "email", "strasse", "plz", "ort", "notiz"] as const;
type BpFormular = Record<(typeof BP_FELDER)[number], string> & { beziehung: string; auskunft_erlaubt: boolean };
const LEER_BP: BpFormular = { name: "", telefon: "", mobil: "", email: "", strasse: "", plz: "", ort: "", notiz: "", beziehung: "", auskunft_erlaubt: false };

function BezugspersonDialog({ person, offen, onOffen }: { person: Bezugsperson | null; offen: boolean; onOffen: (o: boolean) => void }) {
  const { patient } = useAkte();
  const beziehungen = useAuswahl("beziehung", false);
  const [f, setF] = useState<BpFormular>({ ...LEER_BP });
  const neuLaden = useNeuLaden();
  const melden = useHinweis();
  useEffect(() => {
    if (offen) {
      setF(person ? {
        ...(Object.fromEntries(BP_FELDER.map((k) => [k, person[k] ?? ""])) as Record<(typeof BP_FELDER)[number], string>),
        beziehung: person.beziehung ? String(person.beziehung) : "", auskunft_erlaubt: person.auskunft_erlaubt,
      } : { ...LEER_BP });
    }
  }, [offen, person]);
  const fertig = (text: string) => { neuLaden(); melden(text); onOffen(false); };
  const speichern = useMutation({
    mutationFn: () => {
      const daten = { ...f, beziehung: f.beziehung ? Number(f.beziehung) : null };
      return person
        ? api<Bezugsperson>(`bezugspersonen/${person.id}/`, { method: "PATCH", body: daten })
        : api<Bezugsperson>("bezugspersonen/", { body: { ...daten, patient: patient.id } });
    },
    onSuccess: () => fertig(person ? "Bezugsperson gespeichert." : "Bezugsperson angelegt."),
  });
  const aktivSetzen = useMutation({
    mutationFn: (aktiv: boolean) => api<Bezugsperson>(`bezugspersonen/${person!.id}/`, { method: "PATCH", body: { aktiv } }),
    onSuccess: (b) => fertig(b.aktiv ? "Wieder als aktuell markiert." : "Als nicht mehr aktuell markiert."),
  });
  const fe: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const feld = (k: (typeof BP_FELDER)[number], label: string, extra?: { num?: boolean; span?: boolean; typ?: string }) => (
    <Feld label={label} className={extra?.span ? "col-span-2" : undefined} fehler={fe[k]} pflicht={k === "name"}>
      {(p) => <Eingabe {...p} className={extra?.num ? "num" : undefined} type={extra?.typ} value={f[k]}
        onChange={(e) => setF((alt) => ({ ...alt, [k]: e.target.value }) as BpFormular)} />}
    </Feld>
  );
  return (
    <Dialog offen={offen} onOffen={onOffen} breite={600} titel={person ? person.name : "Neue Bezugsperson"}
      beschreibung="Jede Änderung steht mit Person und Zeitpunkt im Verlauf der Akte."
      fuss={<>
        {person && person.aktiv ? <Knopf className="mr-auto" laedt={aktivSetzen.isPending} onClick={() => aktivSetzen.mutate(false)}>Nicht mehr aktuell</Knopf> : null}
        {person && !person.aktiv ? <Knopf className="mr-auto" laedt={aktivSetzen.isPending} onClick={() => aktivSetzen.mutate(true)}>Wieder aktuell</Knopf> : null}
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <form className="grid grid-cols-2 gap-3" noValidate onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        <Feld label="Beziehung" fehler={fe.beziehung}>
          {(p) => (
            <Auswahl {...p} value={f.beziehung} onChange={(e) => setF({ ...f, beziehung: e.target.value })}>
              <option value="">— bitte wählen —</option>
              {(beziehungen.data ?? []).filter((b) => b.aktiv || String(b.id) === f.beziehung).map((b) => <option key={b.id} value={b.id}>{b.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
        {feld("name", "Name")}
        {feld("telefon", "Telefon", { num: true })}
        {feld("mobil", "Mobil", { num: true })}
        {feld("email", "E-Mail", { span: true, typ: "email" })}
        {feld("strasse", "Straße", { span: true })}
        <div className="col-span-2 grid grid-cols-[110px_1fr] gap-3">
          {feld("plz", "PLZ", { num: true })}
          {feld("ort", "Ort")}
        </div>
        <Feld label="Notiz" className="col-span-2" fehler={fe.notiz}>
          {(p) => <Textfeld {...p} rows={2} value={f.notiz} onChange={(e) => setF({ ...f, notiz: e.target.value })} />}
        </Feld>
        <label className="col-span-2 flex items-start gap-2 text-sm cursor-pointer">
          <input type="checkbox" className="mt-0.5" checked={f.auskunft_erlaubt} onChange={(e) => setF({ ...f, auskunft_erlaubt: e.target.checked })} />
          <span><span className="font-medium">Auskunft erlaubt</span> – Schweigepflichtentbindung liegt vor. Die Person erscheint dann im Patientenkopf unter „Auskunft an“.</span>
        </label>
        {speichern.error && !Object.keys(fe).length ? <Meldung art="fehler" className="col-span-2">{speichern.error.message}</Meldung> : null}
        {aktivSetzen.error ? <Meldung art="fehler" className="col-span-2">{aktivSetzen.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

export function BezugspersonenKarte() {
  const { patient, bearbeiten } = useAkte();
  const [frueher, setFrueher] = useState(false);
  const [dialog, setDialog] = useState<{ offen: boolean; p: Bezugsperson | null }>({ offen: false, p: null });
  useOhneRechtSchliessen(bearbeiten, () => setDialog({ offen: false, p: null }));
  const liste = useQuery({
    queryKey: ["patient", patient.id, "bezugspersonen"],
    queryFn: () => api<Bezugsperson[]>(`bezugspersonen/${abfrage({ patient: patient.id })}`),
  });
  const alle = liste.data ?? [];
  const sichtbar = alle.filter((b) => frueher || b.aktiv);
  const anzahlFrueher = alle.filter((b) => !b.aktiv).length;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="bezugspersonen">
      <KartenKopf titel="Bezugspersonen" unter="Angehörige, Betreuer/in, Pflegedienst"
        rechts={bearbeiten ? <Knopf klein icon="plus" onClick={() => setDialog({ offen: true, p: null })}>Person</Knopf> : null} />
      {liste.isLoading ? <Laden /> : sichtbar.length ? (
        <ul className="m-0 p-0 list-none flex flex-col gap-3">
          {sichtbar.map((b) => {
            const adresse = [b.strasse, [b.plz, b.ort].filter(Boolean).join(" ")].filter(Boolean).join(", ");
            return (
              <li key={b.id} className={cx("flex flex-col gap-0.5 text-sm", !b.aktiv && "opacity-60")} data-testid="bezugsperson">
                <span className="flex items-center gap-2 flex-wrap">
                  {bearbeiten ? (
                    <button type="button" className="bg-transparent border-0 p-0 text-left font-medium text-akzent-text cursor-pointer"
                      onClick={() => setDialog({ offen: true, p: b })}>{b.name}</button>
                  ) : <span className="font-medium">{b.name}</span>}
                  {b.beziehung_name ? <Chip>{b.beziehung_name}</Chip> : null}
                  {b.auskunft_erlaubt ? <Chip art="ok"><Icon name="haken" />Auskunft erlaubt</Chip> : null}
                  {!b.aktiv ? <Chip>nicht mehr aktuell</Chip> : null}
                </span>
                {adresse ? <span className="text-[0.8125rem] gedaempft">{adresse}</span> : null}
                <Kontaktzeile telefon={b.telefon} mobil={b.mobil} email={b.email} />
                {b.notiz ? <span className="text-[0.8125rem]">{b.notiz}</span> : null}
              </li>
            );
          })}
        </ul>
      ) : <Leer>Keine Bezugspersonen eingetragen.</Leer>}
      {anzahlFrueher ? (
        <button type="button" className="self-start bg-transparent border-0 p-0 text-[0.8125rem] text-akzent-text cursor-pointer" onClick={() => setFrueher(!frueher)}>
          {frueher ? "Nur aktuelle anzeigen" : `Frühere anzeigen (${anzahlFrueher})`}
        </button>
      ) : null}
      {bearbeiten ? <BezugspersonDialog person={dialog.p} offen={dialog.offen} onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} /> : null}
    </Karte>
  );
}
