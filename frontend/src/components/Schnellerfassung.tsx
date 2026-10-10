/**
 * Schnellerfassung von der Startseite (S02, Entwurf „Schnellerfassung“): Kontakt – auf Wunsch mit Gewicht und
 * Wiedervorlage – und Gewicht allein, mit Patientenauswahl und dem Kasten „Aus der Akte“ (letzter Kontakt, Gewicht,
 * aktueller Plan, nächster Termin, Auskunft an).
 *
 * Kontakt und Gewicht werden mit zwei getrennten Anfragen gespeichert (Festlegung 01.10.2026, SU1): erst der Kontakt
 * (mit Wiedervorlage, F26), dann das Gewicht (F25). Scheitert das Gewicht, bleibt der Kontakt gespeichert; der Dialog
 * sagt das deutlich und lässt nur das Gewicht korrigieren und erneut speichern.
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, alle, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useIch } from "@/lib/auth";
import { useAuswahl, useEinstellungen } from "@/lib/daten";
import { datum, eingabeDatum, eingabeUhrzeit, eingabeZahl, heuteIso, inMonaten, inTagen, kg, prozent, terminZeit, uhrzeit, vorZeit,
  zahl } from "@/lib/format";
import { GEWICHTSQUELLEN, TERMINARTEN } from "@/lib/typen";
import type { Gewicht, Kontakt, Patient, PatientZeile } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Knopf, Meldung, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Editor } from "./Editor";
import { PatientWahl } from "./PatientWahl";

export type Vorgabe = { id: number; name: string; ist_test?: boolean };
const QUELLEN = ["telefonisch", "ambulanz", "versorger", "arztbrief"];

function jetztUhr() {
  return new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
}

/** Vergleich wie im Backend (berechne_trend): jüngste Messung, die etwa den eingestellten Zeitraum zurückliegt */
function veraenderung(messungen: Gewicht[], am: string, neu: number, monate: number) {
  const reihe = [...messungen].filter((m) => m.gemessen_am <= am).sort((a, b) => a.gemessen_am.localeCompare(b.gemessen_am));
  if (!reihe.length) return null;
  const letzte = reihe[reihe.length - 1];
  const stichtag = new Date(`${am}T12:00:00`);
  stichtag.setDate(stichtag.getDate() - (30 * monate - 15));
  const grenze = stichtag.toISOString().slice(0, 10);
  const frueher = reihe.filter((m) => m.gemessen_am <= grenze);
  const vergleich = frueher.length ? frueher[frueher.length - 1] : reihe.find((m) => m.gemessen_am < am) ?? null;
  const p = (alt: number) => ((neu - alt) / alt) * 100;
  return {
    letzte: { am: letzte.gemessen_am, prozent: p(Number(letzte.gewicht_kg)) },
    zeitraum: vergleich ? { am: vergleich.gemessen_am, prozent: p(Number(vergleich.gewicht_kg)) } : null,
  };
}

function Wert({ titel, children }: { titel: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-xs gedaempft">{titel}</span>
      <span className="text-sm">{children}</span>
    </div>
  );
}

/** „Aus der Akte“: was man am Telefon sofort braucht */
function Kontextkasten({ patientId }: { patientId: number }) {
  const akte = useQuery({ queryKey: ["patient", patientId], queryFn: () => api<Patient>(`patienten/${patientId}/`) });
  const k = akte.data?.kopf;
  if (akte.error) return <Meldung art="fehler">{akte.error.message}</Meldung>;
  if (!k) return <div className="rounded-[10px] bg-grund border border-fein px-4 py-3.5 text-sm gedaempft">Akte wird geladen …</div>;
  const t = k.gewichtstrend;
  return (
    <section aria-label="Aus der Akte" className="rounded-[10px] bg-grund border border-fein px-4 py-3.5 flex flex-col gap-2.5"
      data-testid="kontextkasten">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2.5">
        <Wert titel="Letzter Kontakt">{k.letzter_kontakt ? <><span className="num">{datum(k.letzter_kontakt)}</span> · {vorZeit(k.letzter_kontakt)}</>
          : <span className="text-warn">noch kein Kontakt</span>}</Wert>
        <Wert titel="Gewicht">{k.gewicht ? <><span className="num">{kg(k.gewicht.kg)}</span>
          {t ? <> <span className={t.warnung ? "text-fehler" : "gedaempft"} aria-label={`Trend ${Number(t.prozent) < 0 ? "fallend" : "steigend"}`}>
            {Number(t.prozent) <= -1 ? "↓" : Number(t.prozent) >= 1 ? "↑" : "→"}</span> {prozent(t.prozent)}</> : null}
          {" · "}<span className="num">{datum(k.gewicht.am)}</span></> : "—"}</Wert>
        <Wert titel="Aktueller Plan">{k.aktueller_plan ? <><span className="num">{zahl(k.aktueller_plan.kcal)} kcal
          {k.aktueller_plan.laufzeit_h ? ` · ${zahl(k.aktueller_plan.laufzeit_h)} h` : ""}</span>{k.versorger ? ` · ${k.versorger}` : ""}</> : "—"}</Wert>
        <Wert titel="Nächster Termin">{k.naechster_termin ? `${terminZeit(k.naechster_termin.faellig_am, k.naechster_termin.uhrzeit)} · ${
          k.naechster_termin.ort ?? TERMINARTEN[k.naechster_termin.art] ?? k.naechster_termin.titel}` : "—"}</Wert>
      </div>
      <div className="flex items-center gap-2 flex-wrap pt-2.5 border-t border-fein" data-testid="kontext-auskunft">
        <span className="text-xs gedaempft">Auskunft an</span>
        {k.auskunft.length ? k.auskunft.map((a) => (
          <Chip key={a.id} art="ok"><Icon name="haken" groesse={12} />{a.name}{a.beziehung ? ` · ${a.beziehung}` : ""}</Chip>
        )) : <Chip art="warn">niemand eingetragen</Chip>}
        <Link to={`/patienten/${patientId}`} className="ml-auto text-[0.8125rem] font-medium no-underline">Akte öffnen</Link>
      </div>
    </section>
  );
}

/** Gewicht: Wert, Quelle, gemessen am – mit Veränderung gegenüber der letzten Messung und dem Warnzeitraum */
function GewichtFelder({ patientId, wert, quelle, am, onWert, onQuelle, onAm, fehler }: {
  patientId: number; wert: string; quelle: string; am: string; onWert: (s: string) => void; onQuelle: (s: string) => void;
  onAm: (s: string) => void; fehler: Feldfehler;
}) {
  const messungen = useQuery({
    queryKey: ["patient", patientId, "gewichte"],
    queryFn: () => alle<Gewicht>(`gewichte/${abfrage({ patient: patientId })}`),
  });
  const e = useEinstellungen().data;
  const neu = eingabeZahl(wert);
  const iso = eingabeDatum(am);
  const monate = Number(e?.gewicht_warnung_monate ?? 3);
  const schwelle = Number(e?.gewicht_warnung_prozent ?? 5);
  const v = neu && neu !== "ungueltig" && iso && messungen.data ? veraenderung(messungen.data, iso, Number(neu), monate) : null;
  return (
    <>
      <div className="grid grid-cols-[140px_minmax(0,1fr)_minmax(0,1fr)] gap-3">
        <Feld label="Gewicht" fehler={fehler.gewicht_kg}>
          {(p) => (
            <span className="relative block">
              <Eingabe {...p} className="num pr-9" inputMode="decimal" placeholder="0,0" value={wert} onChange={(ev) => onWert(ev.target.value)} />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[0.8125rem] gedaempft pointer-events-none">kg</span>
            </span>
          )}
        </Feld>
        <Feld label="Quelle" fehler={fehler.quelle}>
          {(p) => <Auswahl {...p} value={quelle} onChange={(ev) => onQuelle(ev.target.value)}>
            {QUELLEN.map((q) => <option key={q} value={q}>{GEWICHTSQUELLEN[q]}</option>)}</Auswahl>}
        </Feld>
        <Feld label="Gemessen am" fehler={fehler.gemessen_am}>
          {(p) => <Eingabe {...p} className="num" value={am} onChange={(ev) => onAm(ev.target.value)} />}
        </Feld>
      </div>
      {v ? (
        <span className={cx("text-[0.8125rem] flex items-center gap-1.5", v.zeitraum && v.zeitraum.prozent <= -schwelle ? "text-fehler" : "gedaempft")}
          data-testid="gewicht-veraenderung">
          <Icon name="info" groesse={14} />
          {prozent(v.letzte.prozent)} gegenüber {datum(v.letzte.am)}
          {v.zeitraum ? ` · ${prozent(v.zeitraum.prozent)} seit ${datum(v.zeitraum.am)}` : ""} (Warnung ab {zahl(schwelle)} % in {monate} Monaten)
        </span>
      ) : null}
    </>
  );
}

function useNeuLaden() {
  const qc = useQueryClient();
  return (patientId?: number) => {
    for (const k of [["startseite"], ["patienten"], ["kalender"], ["termine"], ["meine-akten"]]) void qc.invalidateQueries({ queryKey: k });
    if (patientId) void qc.invalidateQueries({ queryKey: ["patient", patientId] });
  };
}

const ARTEN: { wert: string; text: string }[] = [
  { wert: "rueckruf", text: TERMINARTEN.rueckruf }, { wert: "wiedervorlage", text: TERMINARTEN.wiedervorlage },
  { wert: "praxistermin", text: TERMINARTEN.praxistermin }, { wert: "sonstiges", text: TERMINARTEN.sonstiges },
];

/** Wiedervorlage beim Kontakt: Standard 14 Tage, unter Vorlagen › Grenzwerte einstellbar (Wunsch 08.10.2026) */
export function useWiedervorlageTage(): number {
  const t = Number(useEinstellungen().data?.wiedervorlage_tage ?? 14);
  return Number.isFinite(t) && t > 0 ? t : 14;
}

function absatz(text: string): string {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc ? `<p>${esc}</p>` : "";
}

export function KontaktDialog({ offen, onOffen, vorgabe, text: textVorgabe }: {
  offen: boolean; onOffen: (o: boolean) => void; vorgabe?: Vorgabe | null; text?: string;
}) {
  const ich = useIch();
  const wvTage = useWiedervorlageTage();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const orte = useAuswahl("terminort");
  const kontaktarten = useAuswahl("kontaktart");
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const [tag, setTag] = useState(datum(heuteIso()));
  const [uhr, setUhr] = useState(jetztUhr());
  const [text, setText] = useState("");
  const [kontaktart, setKontaktart] = useState("");
  const [mitGewicht, setMitGewicht] = useState(false);
  const [wert, setWert] = useState("");
  const [quelle, setQuelle] = useState("telefonisch");
  const [gemessen, setGemessen] = useState(datum(heuteIso()));
  const [mitTermin, setMitTermin] = useState(false);
  const [art, setArt] = useState("wiedervorlage");
  const [ort, setOrt] = useState("");
  const [faellig, setFaellig] = useState(inTagen(wvTage));
  const [terminUhr, setTerminUhr] = useState("");
  const [titel, setTitel] = useState("");
  const [lokal, setLokal] = useState<Feldfehler>({});
  // Kontakt schon gespeichert, Gewicht nicht: nur noch das Gewicht ist offen
  const [gespeichert, setGespeichert] = useState<Kontakt | null>(null);
  const [editorSchluessel, setEditorSchluessel] = useState(0);

  useEffect(() => {
    if (!offen) return;
    setPatient(null); setTag(datum(heuteIso())); setUhr(jetztUhr()); setText(absatz(textVorgabe ?? "")); setKontaktart(""); setMitGewicht(false); setWert("");
    setQuelle("telefonisch"); setGemessen(datum(heuteIso())); setMitTermin(false); setArt("wiedervorlage"); setOrt("");
    setFaellig(inTagen(wvTage)); setTerminUhr(""); setTitel(""); setLokal({}); setGespeichert(null); setEditorSchluessel((n) => n + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offen]);

  const pid = vorgabe?.id ?? patient?.id ?? null;
  const name = vorgabe?.name ?? (patient ? `${patient.nachname}, ${patient.vorname}` : "");

  const gewichtSpeichern = (patientId: number) => {
    const kgWert = eingabeZahl(wert);
    const iso = eingabeDatum(gemessen);
    if (!kgWert || kgWert === "ungueltig") throw new ApiFehler(400, "", null, { gewicht_kg: "Bitte ein Gewicht eingeben, z. B. 54,6." });
    if (!iso) throw new ApiFehler(400, "", null, { gemessen_am: "Bitte als TT.MM.JJJJ eingeben." });
    return api<Gewicht>("gewichte/", { body: { patient: patientId, gewicht_kg: kgWert, gemessen_am: iso, quelle } });
  };

  const speichern = useMutation({
    mutationFn: async () => {
      if (!pid) throw new ApiFehler(400, "", null, { patient: "Bitte einen Patienten wählen." });
      let kontakt = gespeichert;
      if (!kontakt) {
        const fehler: Feldfehler = {};
        const isoTag = eingabeDatum(tag);
        if (!isoTag) fehler.zeitpunkt = "Datum bitte so eingeben: 14.03.2026 (oder „heute“).";
        const uhrText = eingabeUhrzeit(uhr);
        if (!uhrText) fehler.uhrzeit = "Uhrzeit bitte so eingeben: 10:30 (oder 1030).";
        let wiedervorlage: Record<string, unknown> | null = null;
        if (mitTermin) {
          const isoFaellig = eingabeDatum(faellig);
          if (!isoFaellig) fehler["wiedervorlage.faellig_am"] = "Bitte als TT.MM.JJJJ eingeben.";
          wiedervorlage = { art, ort: art === "praxistermin" && ort ? Number(ort) : null, faellig_am: isoFaellig,
            uhrzeit: terminUhr || null, titel: titel.trim() || undefined };
        }
        if (mitGewicht) {
          const kgWert = eingabeZahl(wert);
          if (!kgWert || kgWert === "ungueltig") fehler.gewicht_kg = "Bitte ein Gewicht eingeben, z. B. 54,6.";
          if (!eingabeDatum(gemessen)) fehler.gemessen_am = "Bitte als TT.MM.JJJJ eingeben.";
        }
        setLokal(fehler);
        if (Object.keys(fehler).length) throw new ApiFehler(400, "", null, fehler);
        const zeitpunkt = new Date(`${isoTag}T${uhrText}:00`).toISOString();
        kontakt = await api<Kontakt>("kontakte/", { body: { patient: pid, text, zeitpunkt, art: kontaktart ? Number(kontaktart) : null,
          wiedervorlage } });
        setGespeichert(kontakt);
      }
      if (mitGewicht) {
        try {
          await gewichtSpeichern(pid);
        } catch (fehler) {
          neuLaden(pid);
          throw fehler;
        }
      }
      return kontakt;
    },
    onSuccess: () => {
      neuLaden(pid ?? undefined);
      melden(mitGewicht ? `Kontakt und Gewicht für ${name} gespeichert.` : mitTermin
        ? `Kontakt und Wiedervorlage für ${name} gespeichert.` : `Kontakt für ${name} gespeichert.`);
      onOffen(false);
    },
  });
  const server: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const f: Feldfehler = { ...server, ...lokal };
  const nurGewichtOffen = !!gespeichert && mitGewicht;
  const gewichtFehler = nurGewichtOffen && speichern.error;
  const sonstigerFehler = speichern.error && !gewichtFehler && !Object.keys(f).length ? speichern.error.message : null;

  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Kontakt erfassen" breite={720}
      beschreibung="Telefonat, E-Mail oder Gespräch festhalten. Nach dem Speichern nicht mehr änderbar, nur stornierbar."
      fuss={<>
        {/* Warum „Speichern“ noch nicht geht, steht gleich daneben (Bedienung für Pflegekräfte, 10.10.2026) */}
        <span className="mr-auto self-center text-[0.8125rem] gedaempft" data-testid="kontakt-fuss">
          {!pid ? "Zuerst den Patienten wählen." : !gespeichert && !text ? "Zum Speichern bitte eine Notiz schreiben."
            : `Erfasst von ${ich.anzeigename} · steht danach im Verlauf der Akte`}</span>
        <Knopf onClick={() => onOffen(false)}>{gespeichert ? "Schließen" : "Abbrechen"}</Knopf>
        <Knopf variante="pri" icon="haken" laedt={speichern.isPending} disabled={!pid || (!gespeichert && !text)}
          onClick={() => speichern.mutate()}>{nurGewichtOffen ? "Gewicht speichern" : "Speichern"}</Knopf>
      </>}>
      <div className="flex flex-col gap-4" data-testid="schnellerfassung">
        {vorgabe ? (
          <div className="flex items-center gap-2.5 text-sm"><span className="gedaempft">Patient</span><strong>{vorgabe.name}</strong>
            {vorgabe.ist_test ? <Chip art="warn">Testpatient</Chip> : null}</div>
        ) : (
          <Feld label="Patient" fehler={f.patient} pflicht>
            {(p) => <PatientWahl id={p.id} wert={patient} onWahl={(x) => { if (!gespeichert) setPatient(x); }} fehler={!!f.patient} />}
          </Feld>
        )}
        {pid ? <Kontextkasten patientId={pid} /> : null}

        {gespeichert ? (
          <Meldung art={gewichtFehler ? "warn" : "ok"}>
            <span data-testid="kontakt-gespeichert"><strong>Kontakt gespeichert</strong> ({datum(gespeichert.zeitpunkt)}, {uhrzeit(gespeichert.zeitpunkt)}).
              {gewichtFehler ? " Das Gewicht wurde nicht gespeichert – bitte korrigieren und „Gewicht speichern“ wählen, oder schließen." : ""}</span>
          </Meldung>
        ) : (
          <>
            <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,2fr)] gap-3 items-end">
              <Feld label="Datum" fehler={f.zeitpunkt}>{(p) => <Eingabe {...p} className="num" value={tag} onChange={(e) => setTag(e.target.value)} />}</Feld>
              <Feld label="Uhrzeit" hinweis="vorbelegt mit jetzt" fehler={f.uhrzeit}>{(p) => <Eingabe {...p} className="num" value={uhr} onChange={(e) => setUhr(e.target.value)} />}</Feld>
              {/* Kontaktart seit 03.10.2026 sichtbar (Klärung U6) */}
              <Feld label="Kontaktart" fehler={f.art}>
                {(p) => (
                  <Auswahl {...p} value={kontaktart} onChange={(e) => setKontaktart(e.target.value)}>
                    <option value="">— ohne Angabe —</option>
                    {(kontaktarten.data ?? []).map((o) => <option key={o.id} value={o.id}>{o.wert}</option>)}
                  </Auswahl>
                )}
              </Feld>
            </div>
            <div className="feld">
              <span>Notiz</span>
              <Editor key={editorSchluessel} wert={text} onAenderung={setText} label="Notiz" hoehe={92}
                platzhalter="Telefonat, Ambulanz, Absprache mit Versorger …" />
              {f.text ? <span className="fehlertext" role="alert">{f.text}</span> : null}
            </div>
          </>
        )}

        <fieldset className="m-0 border border-rand rounded-[10px] px-4 py-3.5 flex flex-col gap-3" disabled={nurGewichtOffen ? false : !!gespeichert}>
          <label className="flex items-center gap-2.5 text-sm font-medium cursor-pointer">
            <input type="checkbox" className="!w-[18px] !h-[18px]" checked={mitGewicht} disabled={!!gespeichert}
              onChange={(e) => setMitGewicht(e.target.checked)} />Gewicht mit erfassen
          </label>
          {mitGewicht && pid ? (
            <GewichtFelder patientId={pid} wert={wert} quelle={quelle} am={gemessen} onWert={setWert} onQuelle={setQuelle} onAm={setGemessen}
              fehler={f} />
          ) : null}
          {gewichtFehler && !f.gewicht_kg && !f.gemessen_am ? <Meldung art="fehler">{speichern.error?.message}</Meldung> : null}
        </fieldset>

        {!gespeichert ? (
          <fieldset className="m-0 border border-rand rounded-[10px] px-4 py-3.5 flex flex-col gap-3">
            <label className="flex items-center gap-2.5 text-sm font-medium cursor-pointer">
              <input type="checkbox" className="!w-[18px] !h-[18px]" checked={mitTermin} onChange={(e) => setMitTermin(e.target.checked)} />
              Wiedervorlage anlegen
            </label>
            {mitTermin ? (
              <>
                <Segmente label="Art" wert={art} onWahl={setArt} werte={ARTEN} className="self-start" />
                <div className="grid grid-cols-[140px_110px_minmax(0,1fr)] gap-3">
                  <Feld label="Fällig am" fehler={f["wiedervorlage.faellig_am"]}>
                    {(p) => <Eingabe {...p} className="num" value={faellig} onChange={(e) => setFaellig(e.target.value)} />}</Feld>
                  <Feld label="Uhrzeit" fehler={f["wiedervorlage.uhrzeit"]}>
                    {(p) => <Eingabe {...p} type="time" className="num" value={terminUhr} onChange={(e) => setTerminUhr(e.target.value)} />}</Feld>
                  {art === "praxistermin" ? (
                    <Feld label="Ort" fehler={f["wiedervorlage.ort"]}>
                      {(p) => <Auswahl {...p} value={ort} onChange={(e) => setOrt(e.target.value)}>
                        <option value="">—</option>{(orte.data ?? []).map((o) => <option key={o.id} value={o.id}>{o.wert}</option>)}</Auswahl>}
                    </Feld>
                  ) : (
                    <Feld label="Titel" fehler={f["wiedervorlage.titel"]} hinweis="leer = Art">
                      {(p) => <Eingabe {...p} maxLength={200} value={titel} onChange={(e) => setTitel(e.target.value)} />}</Feld>
                  )}
                </div>
                <div className="flex gap-1.5 flex-wrap">
                  {([[wvTage === 14 ? "in 2 Wochen" : `in ${wvTage} Tagen`, inTagen(wvTage)], ["in 1 Monat", inMonaten(1)], ["in 3 Monaten (Quartal)", inMonaten(3)]] as const).map(([t, d]) => (
                    <button key={t} type="button" className={cx("chip h-[26px] cursor-pointer border", faellig === d ? "akzent border-akzent" : "border-rand bg-flaeche text-text2")}
                      onClick={() => setFaellig(d)}>{t}</button>
                  ))}
                </div>
              </>
            ) : null}
          </fieldset>
        ) : null}
        {sonstigerFehler ? <Meldung art="fehler">{sonstigerFehler}</Meldung> : null}
      </div>
    </Dialog>
  );
}

export function GewichtDialog({ offen, onOffen, vorgabe, wert: wertVorgabe }: {
  offen: boolean; onOffen: (o: boolean) => void; vorgabe?: Vorgabe | null; wert?: string;
}) {
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const [wert, setWert] = useState("");
  const [quelle, setQuelle] = useState("telefonisch");
  const [am, setAm] = useState(datum(heuteIso()));
  useEffect(() => {
    if (offen) { setPatient(null); setWert(wertVorgabe ?? ""); setQuelle("telefonisch"); setAm(datum(heuteIso())); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offen]);
  const pid = vorgabe?.id ?? patient?.id ?? null;
  const name = vorgabe?.name ?? (patient ? `${patient.nachname}, ${patient.vorname}` : "");
  const speichern = useMutation({
    mutationFn: () => {
      if (!pid) throw new ApiFehler(400, "", null, { patient: "Bitte einen Patienten wählen." });
      const kgWert = eingabeZahl(wert);
      const iso = eingabeDatum(am);
      if (!kgWert || kgWert === "ungueltig") throw new ApiFehler(400, "", null, { gewicht_kg: "Bitte ein Gewicht eingeben, z. B. 54,6." });
      if (!iso) throw new ApiFehler(400, "", null, { gemessen_am: "Bitte als TT.MM.JJJJ eingeben." });
      return api<Gewicht>("gewichte/", { body: { patient: pid, gewicht_kg: kgWert, gemessen_am: iso, quelle } });
    },
    onSuccess: (g) => { neuLaden(pid ?? undefined); melden(`Gewicht ${kg(g.gewicht_kg)} für ${name} gespeichert.`); onOffen(false); },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Gewicht erfassen" breite={640}
      beschreibung="Unplausible Werte und Daten in der Zukunft werden abgewiesen. Eine falsche Messung lässt sich in der Akte korrigieren."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" icon="haken" laedt={speichern.isPending} disabled={!pid} onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <form className="flex flex-col gap-4" noValidate onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        {vorgabe ? <div className="text-sm"><span className="gedaempft">Patient</span> <strong>{vorgabe.name}</strong></div> : (
          <Feld label="Patient" fehler={f.patient} pflicht>
            {(p) => <PatientWahl id={p.id} wert={patient} onWahl={setPatient} fehler={!!f.patient} />}
          </Feld>
        )}
        {pid ? <Kontextkasten patientId={pid} /> : null}
        {pid ? <GewichtFelder patientId={pid} wert={wert} quelle={quelle} am={am} onWert={setWert} onQuelle={setQuelle} onAm={setAm} fehler={f} /> : null}
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

