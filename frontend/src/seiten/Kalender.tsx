/**
 * Globaler Kalender (Menüpunkt „Kalender“, Wunsch 02.10.2026): Termine und Wiedervorlagen aller Patienten, berechnete
 * Fälligkeiten (Kontakt fällig, Infusionsplan prüfen) und Feiertage (NRW) – als Monat, Woche oder Liste.
 * Termine anlegen, ändern und abhaken wie auf der Startseite (gleicher Dialog, gleiche Rechte).
 */
import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { datum, heuteIso, nummer, uhrzeit, zeitpunkt } from "@/lib/format";
import { ab, useMobil, useStufe } from "@/lib/stufen";
import { TERMINARTEN } from "@/lib/typen";
import type { Termin } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Fehleranzeige, Karte, Knopf, Laden, Leer, Segmente, Seitenkopf, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { TerminDialog } from "@/components/TerminDialog";
import { RuheDialog } from "@/components/HinweisChips";

/** „×“ an jedem Eintrag (Wunsch 08.10.2026, F142): Termin bzw. Fälligkeit ausblenden – wie die Hinweise der Akte */
const Ausblenden = createContext<((e: Eintrag) => void) | null>(null);

/** stufe (nur Kontakt, S04): am Tag „bald fällig“ bzw. „überfällig“ – je Akte ein Eintrag je Stufe */
type Faelligkeit = { art: "kontakt" | "plan"; stufe?: "bald" | "ueberfaellig"; patient: number; name: string; nummer: number;
  ist_test: boolean; faellig_am: string; seit: string; ueberfaellig: boolean; text: string };
type KalenderDaten = {
  von: string; bis: string; heute: string;
  termine: Termin[]; termine_ueberfaellig: Termin[]; faelligkeiten: Faelligkeit[];
  grenzen: { kontakt_monate?: number; kontakt_bald_monate?: number; plan_monate?: number };
  feiertage: { datum: string; name: string }[];
};
type Ansicht = "monat" | "woche" | "liste";
type Filter = "praxistermin" | "rueckruf" | "wiedervorlage" | "sonstiges" | "kontakt" | "plan";
type Eintrag = { schluessel: string; datum: string; termin?: Termin; faellig?: Faelligkeit };

const FILTER: { wert: Filter; text: string }[] = [
  { wert: "praxistermin", text: "Praxistermine" }, { wert: "rueckruf", text: "Rückrufe" },
  { wert: "wiedervorlage", text: "Wiedervorlagen" }, { wert: "sonstiges", text: "Sonstiges" },
  { wert: "kontakt", text: "Kontakt fällig" }, { wert: "plan", text: "Plan prüfen" },
];
const WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November",
  "Dezember"];

// ---------------------------------------------------------------- Datumsrechnung auf „JJJJ-MM-TT“ (ohne Zeitzonen)
function tag(iso: string) {
  const [j, m, t] = iso.split("-").map(Number);
  return new Date(Date.UTC(j, m - 1, t));
}
function iso(d: Date) {
  return d.toISOString().slice(0, 10);
}
function plus(isoDatum: string, tage: number) {
  const d = tag(isoDatum);
  d.setUTCDate(d.getUTCDate() + tage);
  return iso(d);
}
/** Montag der Woche (0 = Montag) */
function montag(isoDatum: string) {
  const wt = (tag(isoDatum).getUTCDay() + 6) % 7;
  return plus(isoDatum, -wt);
}
function monatsErster(isoDatum: string, verschiebung = 0) {
  const d = tag(isoDatum);
  return iso(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + verschiebung, 1)));
}
function kalenderwoche(isoDatum: string) {
  const d = tag(isoDatum);
  const donnerstag = new Date(d);
  donnerstag.setUTCDate(d.getUTCDate() + 3 - ((d.getUTCDay() + 6) % 7));
  const jahresbeginn = new Date(Date.UTC(donnerstag.getUTCFullYear(), 0, 4));
  return 1 + Math.round(((donnerstag.getTime() - jahresbeginn.getTime()) / 86400000 - 3 + ((jahresbeginn.getUTCDay() + 6) % 7)) / 7);
}
function kurz(isoDatum: string) {
  const d = tag(isoDatum);
  return `${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}.`;
}
function langerTag(isoDatum: string) {
  return tag(isoDatum).toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
}

function zeitraum(ansicht: Ansicht, bezug: string): { von: string; bis: string; titel: string } {
  if (ansicht === "woche") {
    const von = montag(bezug);
    const bis = plus(von, 6);
    return { von, bis, titel: `KW ${kalenderwoche(von)} · ${kurz(von)}–${datum(bis)}` };
  }
  const erster = monatsErster(bezug);
  const d = tag(erster);
  const titel = `${MONATE[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  if (ansicht === "liste") return { von: erster, bis: plus(monatsErster(bezug, 1), -1), titel };
  const von = montag(erster);
  return { von, bis: plus(von, 41), titel };
}

function weiter(ansicht: Ansicht, bezug: string, richtung: 1 | -1) {
  return ansicht === "woche" ? plus(bezug, 7 * richtung) : monatsErster(bezug, richtung);
}

// ---------------------------------------------------------------- Darstellung eines Eintrags
function farbe(e: Eintrag, heute: string) {
  if (e.termin) {
    const t = e.termin;
    if (t.erledigt_am) return "bg-fein text-gedaempft line-through";
    if (t.faellig_am < heute) return "bg-fehler-bg text-fehler";
    if (t.art === "praxistermin") return "bg-akzent-weich text-akzent-text";
    if (t.art === "wiedervorlage") return "bg-warn-bg text-warn";
    return "bg-fein text-tinte";
  }
  const f = e.faellig!;
  if (f.art === "kontakt") {
    return f.stufe === "bald" && !f.ueberfaellig ? "border border-dashed border-warn text-warn bg-flaeche"
      : "border border-dashed border-fehler text-fehler bg-flaeche";
  }
  if (f.ueberfaellig) return "border border-dashed border-fehler text-fehler bg-flaeche";
  return "border border-dashed border-akzent text-akzent-text bg-flaeche";
}

function faelligName(f: Faelligkeit) {
  return f.art === "plan" ? "Plan prüfen" : f.stufe === "ueberfaellig" ? "Kontakt überfällig" : "Kontakt bald fällig";
}

function beschriftung(e: Eintrag) {
  if (e.termin) {
    const t = e.termin;
    const zeit = t.uhrzeit ? `${uhrzeit(t.uhrzeit)} ` : "";
    return `${zeit}${TERMINARTEN[t.art]}: ${t.patient_name} – ${t.titel}${t.erledigt_am ? " (erledigt)" : ""}`;
  }
  const f = e.faellig!;
  return `${faelligName(f)}: ${f.name}${f.ueberfaellig && f.art === "plan" ? " (überfällig)" : ""}`;
}

function EintragKnopf({ e, heute, onWahl, voll }: { e: Eintrag; heute: string; onWahl: (e: Eintrag) => void; voll?: boolean }) {
  const t = e.termin;
  const f = e.faellig;
  const ausblenden = useContext(Ausblenden);
  const { darfBei } = useAuth();
  // Termine: wer abhaken darf; Fälligkeiten: wer Hinweise der Akte wegklicken darf (F119)
  const kann = !!ausblenden && (t ? !t.erledigt_am && darfBei("eintraege_erfassen", { ist_test: t.patient_ist_test })
    : f ? darfBei("akten_bearbeiten", { ist_test: f.ist_test }) : false);
  return (
    <div className={cx("w-full rounded-md min-w-0 flex items-stretch", farbe(e, heute))}>
    <button type="button" onClick={(ev) => { ev.stopPropagation(); onWahl(e); }} title={beschriftung(e)} aria-label={beschriftung(e)}
      data-testid="kalender-eintrag"
      className={cx("grow text-left rounded-md px-1.5 py-0.5 text-[0.75rem] leading-snug cursor-pointer border-0 min-w-0 flex gap-1 items-baseline bg-transparent text-inherit",
        voll && "py-1.5 px-2 text-[0.8125rem] flex-col items-start gap-0.5")}>
      {t ? (
        <>
          <span className={cx("num shrink-0", !voll && "opacity-80")}>{t.uhrzeit ? uhrzeit(t.uhrzeit) : voll ? "ganztägig" : ""}</span>
          <span className="truncate min-w-0"><span className="font-medium">{t.patient_name}</span>{voll ? <> · {t.titel}</> : null}</span>
          {voll ? <span className="text-[0.75rem] opacity-80">{TERMINARTEN[t.art]}{t.ort_name ? ` · ${t.ort_name}` : ""}{t.patient_ist_test ? " · Test" : ""}</span> : null}
        </>
      ) : f ? (
        <>
          <Icon name={f.art === "plan" ? "tropfen" : "telefon"} groesse={12} className="shrink-0 self-center" />
          <span className="truncate min-w-0"><span className="font-medium">{f.name}</span>{voll ? <> · {f.art === "plan" ? "Plan prüfen" : "Kontakt fällig"}</> : null}</span>
        </>
      ) : null}
    </button>
    {kann ? (
      <button type="button" data-testid="eintrag-ausblenden" aria-label="Ausblenden" title={`Ausblenden … (${beschriftung(e)})`}
        className="shrink-0 px-1.5 bg-transparent border-0 cursor-pointer text-inherit opacity-60 hover:opacity-100 leading-none text-[0.9375rem]"
        onClick={(ev) => { ev.stopPropagation(); ausblenden!(e); }}>×</button>
    ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- Dialog zu einem Eintrag
function EintragDialog({ e, heute, onZu, onTermin, onAendern }: {
  e: Eintrag | null; heute: string; onZu: () => void; onTermin: (patient: number, name: string, datum: string) => void;
  onAendern: (t: Termin) => void;
}) {
  const { darfBei } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const abhaken = useMutation({
    mutationFn: (t: Termin) => api<Termin>(`termine/${t.id}/erledigt/`, { method: "POST" }),
    onSuccess: (t) => {
      void qc.invalidateQueries({ queryKey: ["kalender"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      void qc.invalidateQueries({ queryKey: ["patient", t.patient] });
      melden(`Erledigt: ${t.patient_name}`);
      onZu();
    },
  });
  if (!e) return null;
  const t = e.termin;
  const f = e.faellig;
  const darf = t ? darfBei("eintraege_erfassen", { ist_test: t.patient_ist_test }) && !t.erledigt_am
    : f ? darfBei("eintraege_erfassen", { ist_test: f.ist_test }) : false;
  const patient = t ? t.patient : f!.patient;
  const name = t ? t.patient_name : f!.name;
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel={t ? t.titel : f!.art === "plan" ? "Infusionsplan prüfen" : faelligName(f!)}
      beschreibung={<Link to={`/patienten/${patient}`} className="font-medium">{name}</Link>}
      fuss={<>
        {f?.art === "plan" ? <Link className="btn sec" to={`/patienten/${patient}/plaene`}>Pläne öffnen</Link>
          : <Link className="btn sec" to={`/patienten/${patient}`}>Akte öffnen</Link>}
        {t && darf ? <Knopf icon="stift" onClick={() => onAendern(t)}>Ändern</Knopf> : null}
        {t && darf ? <Knopf variante="pri" icon="haken" laedt={abhaken.isPending} onClick={() => abhaken.mutate(t)}>Erledigt</Knopf> : null}
        {f && darf ? <Knopf variante="pri" icon="plus" onClick={() => onTermin(f.patient, f.name, f.faellig_am < heute ? heute : f.faellig_am)}>
          Termin anlegen</Knopf> : null}
      </>}>
      <dl className="m-0 grid grid-cols-[130px_1fr] gap-y-1.5 text-sm" data-testid="eintrag-details">
        {t ? (
          <>
            <dt className="gedaempft">Art</dt><dd className="m-0">{TERMINARTEN[t.art]}</dd>
            <dt className="gedaempft">Wann</dt><dd className="m-0">{datum(t.faellig_am)}, {t.uhrzeit ? `${uhrzeit(t.uhrzeit)} Uhr` : "ganztägig"}
              {!t.erledigt_am && t.faellig_am < heute ? <Chip art="fehler" className="ml-2">überfällig</Chip> : null}</dd>
            {t.ort_name || t.bei ? <><dt className="gedaempft">Ort</dt><dd className="m-0">{[t.ort_name, t.bei].filter(Boolean).join(" · ")}</dd></> : null}
            {t.notiz ? <><dt className="gedaempft">Notiz</dt><dd className="m-0 whitespace-pre-line">{t.notiz}</dd></> : null}
            <dt className="gedaempft">Angelegt</dt><dd className="m-0">{zeitpunkt(t.angelegt_am)} von {t.angelegt_von_name ?? "—"}</dd>
            {t.erledigt_am ? <><dt className="gedaempft">Erledigt</dt><dd className="m-0">{zeitpunkt(t.erledigt_am)} von {t.erledigt_von_name ?? "—"}</dd></> : null}
          </>
        ) : f ? (
          <>
            <dt className="gedaempft">Fällig am</dt><dd className="m-0">{datum(f.faellig_am)}
              {f.ueberfaellig ? <Chip art="fehler" className="ml-2">überfällig</Chip> : null}</dd>
            <dt className="gedaempft">Grund</dt><dd className="m-0">{f.text}</dd>
            <dt className="gedaempft">Patient</dt><dd className="m-0"><span className="num">{nummer(f.nummer)}</span>{f.ist_test ? " · Testpatient" : ""}</dd>
          </>
        ) : null}
      </dl>
      {f ? <p className="m-0 text-[0.8125rem] gedaempft">Berechnet aus den Grenzwerten (Vorlagen › Grenzwerte). Die Fälligkeit verschwindet,
        sobald ein {f.art === "plan" ? "neuer Plan freigegeben" : "Kontakt erfasst"} ist.</p> : null}
      <Fehleranzeige fehler={abhaken.error} />
    </Dialog>
  );
}

// ---------------------------------------------------------------- Ansichten
function Monat({ von, bezug, heute, tage, feiertage, gewaehlt, onTag, onWahl, onNeu }: {
  von: string; bezug: string; heute: string; tage: Map<string, Eintrag[]>; feiertage: Map<string, string>;
  gewaehlt: string; onTag: (d: string) => void; onWahl: (e: Eintrag) => void; onNeu?: (d: string) => void;
}) {
  const monat = tag(monatsErster(bezug)).getUTCMonth();
  const wochen = Array.from({ length: 6 }, (_, w) => Array.from({ length: 7 }, (_, t) => plus(von, w * 7 + t)));
  return (
    <table className="w-full border-collapse table-fixed" data-testid="kalender-monat">
      <thead>
        <tr>{WOCHENTAGE.map((w) => <th key={w} scope="col" className="th text-left">{w}</th>)}</tr>
      </thead>
      <tbody>
        {wochen.map((woche) => (
          <tr key={woche[0]}>
            {woche.map((d) => {
              const eintraege = tage.get(d) ?? [];
              const fremd = tag(d).getUTCMonth() !== monat;
              const feiertag = feiertage.get(d);
              const wochenende = tag(d).getUTCDay() % 6 === 0;
              return (
                <td key={d} data-testid={`tag-${d}`} onClick={() => onTag(d)}
                  className={cx("kalender-zelle align-top border border-rand p-1 cursor-pointer group overflow-hidden",
                    fremd && "bg-grund/60", (wochenende || feiertag) && !fremd && "bg-fein/40", d === gewaehlt && "outline-2 outline-akzent -outline-offset-2")}>
                  <div className="flex items-center gap-1 mb-0.5 min-w-0">
                    <span className={cx("num text-[0.8125rem] w-6 h-6 inline-flex items-center justify-center rounded-full shrink-0",
                      d === heute ? "bg-akzent text-auf-akzent font-semibold" : fremd ? "gedaempft" : "")}
                      aria-label={langerTag(d)}>{tag(d).getUTCDate()}</span>
                    {feiertag ? <span className="text-[0.6875rem] text-fehler truncate" title={feiertag}>{feiertag}</span> : null}
                    {onNeu ? (
                      <button type="button" aria-label={`Termin am ${datum(d)} anlegen`} title="Termin anlegen"
                        className="ml-auto btn geist icon !h-6 !w-6 opacity-0 group-hover:opacity-100 focus:opacity-100"
                        onClick={(ev) => { ev.stopPropagation(); onNeu(d); }}>
                        <Icon name="plus" groesse={14} />
                      </button>
                    ) : null}
                  </div>
                  <div className="flex flex-col gap-0.5 min-w-0">
                    {eintraege.slice(0, 3).map((e) => <EintragKnopf key={e.schluessel} e={e} heute={heute} onWahl={onWahl} />)}
                    {eintraege.length > 3 ? (
                      <button type="button" className="text-left text-[0.75rem] gedaempft bg-transparent border-0 cursor-pointer px-1.5"
                        onClick={(ev) => { ev.stopPropagation(); onTag(d); }}>+{eintraege.length - 3} weitere</button>
                    ) : null}
                  </div>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Woche({ von, heute, tage, feiertage, onWahl, onNeu }: {
  von: string; heute: string; tage: Map<string, Eintrag[]>; feiertage: Map<string, string>; onWahl: (e: Eintrag) => void;
  onNeu?: (d: string) => void;
}) {
  return (
    <div className="grid grid-cols-7 gap-2" data-testid="kalender-woche">
      {Array.from({ length: 7 }, (_, i) => plus(von, i)).map((d) => {
        const eintraege = tage.get(d) ?? [];
        return (
          <section key={d} data-testid={`tag-${d}`} aria-label={langerTag(d)}
            className={cx("flex flex-col gap-1 min-w-0 rounded-lg border border-rand p-1.5 min-h-[240px]", d === heute ? "bg-akzent-weich/40" : "bg-flaeche")}>
            <div className="flex items-center gap-1.5">
              <span className={cx("font-semibold text-sm", d === heute && "text-akzent-text")}>{WOCHENTAGE[(tag(d).getUTCDay() + 6) % 7]} {kurz(d)}</span>
              {onNeu ? <button type="button" aria-label={`Termin am ${datum(d)} anlegen`} title="Termin anlegen" className="ml-auto btn geist icon !h-6 !w-6"
                onClick={() => onNeu(d)}><Icon name="plus" groesse={14} /></button> : null}
            </div>
            {feiertage.get(d) ? <span className="text-xs text-fehler">{feiertage.get(d)}</span> : null}
            {eintraege.length === 0 ? <span className="text-xs gedaempft">—</span> : null}
            {eintraege.map((e) => <EintragKnopf key={e.schluessel} e={e} heute={heute} onWahl={onWahl} voll />)}
          </section>
        );
      })}
    </div>
  );
}

function Liste({ tage, feiertage, heute, onWahl }: {
  tage: [string, Eintrag[]][]; feiertage: Map<string, string>; heute: string; onWahl: (e: Eintrag) => void;
}) {
  if (tage.length === 0) return <Leer>In diesem Zeitraum gibt es keine Einträge.</Leer>;
  return (
    <div className="flex flex-col" data-testid="kalender-liste">
      {tage.map(([d, eintraege]) => (
        <section key={d} data-testid={`tag-${d}`} className="grid grid-cols-[200px_minmax(0,1fr)] gap-3 py-2 border-b border-rand last:border-b-0">
          <div className="flex flex-col">
            <span className={cx("font-semibold text-sm", d === heute && "text-akzent-text")}>{langerTag(d)}</span>
            {feiertage.get(d) ? <span className="text-xs text-fehler">{feiertage.get(d)}</span> : null}
          </div>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-1.5">
            {eintraege.map((e) => <EintragKnopf key={e.schluessel} e={e} heute={heute} onWahl={onWahl} voll />)}
          </div>
        </section>
      ))}
    </div>
  );
}

function Seitenliste({ titel, anzahl, children, testid }: { titel: string; anzahl: number; children: ReactNode; testid: string }) {
  return (
    <div className="flex flex-col gap-1.5" data-testid={testid}>
      <h3 className="m-0 text-[0.8125rem] font-semibold flex items-center gap-2">{titel}<span className="num gedaempft font-normal">{anzahl}</span></h3>
      {children}
    </div>
  );
}

function Gekuerzt({ eintraege, heute, onWahl }: { eintraege: Eintrag[]; heute: string; onWahl: (e: Eintrag) => void }) {
  const [alle, setAlle] = useState(false);
  if (eintraege.length === 0) return <span className="text-xs gedaempft">keine</span>;
  const zeigen = alle ? eintraege : eintraege.slice(0, 8);
  return (
    <div className="flex flex-col gap-1">
      {zeigen.map((e) => (
        <div key={e.schluessel} className="flex items-center gap-2 min-w-0">
          <span className="num text-[0.75rem] gedaempft w-12 shrink-0">{kurz(e.datum)}</span>
          <div className="grow min-w-0"><EintragKnopf e={e} heute={heute} onWahl={onWahl} /></div>
        </div>
      ))}
      {eintraege.length > 8 ? (
        <button type="button" className="text-left text-xs gedaempft bg-transparent border-0 cursor-pointer p-0" onClick={() => setAlle(!alle)}>
          {alle ? "weniger anzeigen" : `alle ${eintraege.length} anzeigen`}
        </button>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- Seite
export function Kalender() {
  const { darf } = useAuth();
  const [params, setParams] = useSearchParams();
  // am Telefon (Festlegung 08.10.2026) ist die Liste Standard – das Monatsraster ist dort zu eng zum Lesen
  const mobil = useMobil();
  const ansicht = (["monat", "woche", "liste"].includes(params.get("ansicht") ?? "") ? params.get("ansicht")
    : mobil ? "liste" : "monat") as Ansicht;
  const bezug = /^\d{4}-\d{2}-\d{2}$/.test(params.get("datum") ?? "") ? params.get("datum")! : heuteIso();
  const setze = (werte: Record<string, string>) => setParams((p) => {
    const n = new URLSearchParams(p);
    for (const [k, v] of Object.entries(werte)) n.set(k, v);
    return n;
  }, { replace: true });
  const [filter, setFilter] = useState<Filter[]>(FILTER.map((f) => f.wert));
  const [erledigte, setErledigte] = useState(true);
  const [gewaehlt, setGewaehlt] = useState(heuteIso());
  const [eintrag, setEintrag] = useState<Eintrag | null>(null);
  const [neu, setNeu] = useState<{ datum: string; patient?: number; name?: string } | null>(null);
  const [aendern, setAendern] = useState<Termin | null>(null);
  const [weg, setWeg] = useState<Eintrag | null>(null);
  const schreiben = darf("eintraege_erfassen");
  const stufe = useStufe();
  useOhneRechtSchliessen(schreiben, () => { setNeu(null); setAendern(null); });

  const z = zeitraum(ansicht, bezug);
  const daten = useQuery({
    queryKey: ["kalender", z.von, z.bis, erledigte],
    queryFn: () => api<KalenderDaten>(`kalender/${abfrage({ von: z.von, bis: z.bis, erledigte: erledigte ? 1 : 0 })}`),
    placeholderData: (vorher: KalenderDaten | undefined) => vorher,
  });
  const heute = daten.data?.heute ?? heuteIso();

  const { tage, ueberfaellig, feiertage } = useMemo(() => {
    const karte = new Map<string, Eintrag[]>();
    const ueber: { termine: Eintrag[]; kontakt: Eintrag[]; bald: Eintrag[]; plan: Eintrag[] } = { termine: [], kontakt: [], bald: [], plan: [] };
    const fei = new Map<string, string>();
    const d = daten.data;
    if (!d) return { tage: karte, ueberfaellig: ueber, feiertage: fei };
    const neuEintrag = (e: Eintrag) => {
      if (e.datum < d.von || e.datum > d.bis) return;
      const liste = karte.get(e.datum) ?? [];
      liste.push(e);
      karte.set(e.datum, liste);
    };
    for (const t of d.termine) if (filter.includes(t.art)) neuEintrag({ schluessel: `t${t.id}`, datum: t.faellig_am, termin: t });
    for (const f of d.faelligkeiten) {
      if (filter.includes(f.art)) neuEintrag({ schluessel: `${f.art}${f.stufe ?? ""}${f.patient}`, datum: f.faellig_am, faellig: f });
    }
    for (const liste of karte.values()) {
      liste.sort((a, b) => {
        const rang = (e: Eintrag) => (e.termin ? (e.termin.uhrzeit ? 1 : 0) : 2);
        return rang(a) - rang(b) || (a.termin?.uhrzeit ?? "").localeCompare(b.termin?.uhrzeit ?? "")
          || beschriftung(a).localeCompare(beschriftung(b), "de");
      });
    }
    for (const t of d.termine_ueberfaellig) if (filter.includes(t.art)) ueber.termine.push({ schluessel: `t${t.id}`, datum: t.faellig_am, termin: t });
    // Kontakt: je Akte nur die höchste erreichte Stufe (überfällig vor bald fällig)
    const ueberfaelligeAkten = new Set(d.faelligkeiten.filter((f) => f.art === "kontakt" && f.stufe === "ueberfaellig" && f.ueberfaellig)
      .map((f) => f.patient));
    for (const f of d.faelligkeiten) {
      if (!f.ueberfaellig || !filter.includes(f.art)) continue;
      const e = { schluessel: `${f.art}${f.stufe ?? ""}${f.patient}`, datum: f.faellig_am, faellig: f };
      if (f.art === "plan") ueber.plan.push(e);
      else if (f.stufe === "ueberfaellig") ueber.kontakt.push(e);
      else if (!ueberfaelligeAkten.has(f.patient)) ueber.bald.push(e);
    }
    for (const f of d.feiertage) fei.set(f.datum, f.name);
    return { tage: karte, ueberfaellig: ueber, feiertage: fei };
  }, [daten.data, filter]);

  const listenTage = [...tage.entries()].sort(([a], [b]) => a.localeCompare(b));
  const tagEintraege = tage.get(gewaehlt) ?? [];
  const neuAm = schreiben ? (d: string) => setNeu({ datum: d }) : undefined;

  return (
    <Ausblenden.Provider value={setWeg}>
    <Seite pfad={[{ text: "Kalender" }]}>
      <Seitenkopf titel="Kalender" unter="Termine und Wiedervorlagen aller Patienten, fällige Kontakte und Pläne, Feiertage (NRW)."
        rechts={<>
          <Segmente label="Ansicht" wert={ansicht} onWahl={(a) => setze({ ansicht: a })} werte={[
            { wert: "monat", text: "Monat" }, { wert: "woche", text: "Woche" }, { wert: "liste", text: "Liste" }]} />
          {schreiben ? <Knopf variante="pri" icon="plus" onClick={() => setNeu({ datum: gewaehlt })}>Termin</Knopf> : null}
        </>} />
      <div className="flex items-center gap-2.5 flex-wrap">
        <Knopf klein className="icon" aria-label="Zurück" onClick={() => setze({ datum: weiter(ansicht, bezug, -1) })}>
          <Icon name="pfeilLinks" /></Knopf>
        <Knopf klein onClick={() => { setze({ datum: heuteIso() }); setGewaehlt(heuteIso()); }}>Heute</Knopf>
        <Knopf klein className="icon" aria-label="Weiter" onClick={() => setze({ datum: weiter(ansicht, bezug, 1) })}>
          <Icon name="pfeilRechts" /></Knopf>
        <h2 className="m-0 text-lg font-semibold min-w-[220px]" data-testid="kalender-titel" aria-live="polite">{z.titel}</h2>
        {daten.isFetching ? <span className="text-xs gedaempft">wird geladen …</span> : null}
        <div className="ml-auto flex items-center gap-1.5 flex-wrap" role="group" aria-label="Was anzeigen">
          {FILTER.map((f) => (
            <button key={f.wert} type="button" aria-pressed={filter.includes(f.wert)}
              className={cx("chip h-[30px] cursor-pointer border", filter.includes(f.wert) ? "akzent border-akzent" : "border-rand bg-flaeche text-text2")}
              onClick={() => setFilter(filter.includes(f.wert) ? filter.filter((x) => x !== f.wert) : [...filter, f.wert])}>{f.text}</button>
          ))}
          <label className="flex items-center gap-1.5 text-[0.8125rem] ml-1.5">
            <input type="checkbox" checked={erledigte} onChange={(e) => setErledigte(e.target.checked)} /> Erledigte zeigen
          </label>
        </div>
      </div>
      <Fehleranzeige fehler={daten.error} />
      {/* Stufen (S16, Entwurf 2): bis 1919 px Kalender mit Seitenspalte wie bisher, ab 1920 px Monat ¾ | Tagesliste ¼ */}
      <div className="stapel grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] hd:grid-cols-[minmax(0,1fr)_360px] fhd:grid-cols-[minmax(0,3fr)_minmax(0,1fr)] gap-5 items-start"
        data-testid="kalender-stufe">
        <Karte className="p-2 min-w-0">
          {!daten.data ? <Laden /> : ansicht === "monat" ? (
            <Monat von={z.von} bezug={bezug} heute={heute} tage={tage} feiertage={feiertage} gewaehlt={gewaehlt}
              onTag={setGewaehlt} onWahl={setEintrag} onNeu={neuAm} />
          ) : ansicht === "woche" ? (
            <Woche von={z.von} heute={heute} tage={tage} feiertage={feiertage} onWahl={setEintrag} onNeu={neuAm} />
          ) : (
            <Liste tage={listenTage} feiertage={feiertage} heute={heute} onWahl={setEintrag} />
          )}
        </Karte>
        <div className="flex flex-col gap-4">
          {ansicht === "monat" || ab(stufe, "fhd") ? (
            <Karte className="px-4 py-3.5 flex flex-col gap-2" data-testid="tagesliste">
              <div className="flex items-center justify-between gap-2">
                <h2 className="lbl m-0">{langerTag(gewaehlt)}</h2>
                {schreiben ? <Knopf klein icon="plus" onClick={() => setNeu({ datum: gewaehlt })}>Termin</Knopf> : null}
              </div>
              {feiertage.get(gewaehlt) ? <span className="text-xs text-fehler">{feiertage.get(gewaehlt)}</span> : null}
              {tagEintraege.length === 0 ? <span className="text-sm gedaempft">Keine Einträge.</span>
                : tagEintraege.map((e) => <EintragKnopf key={e.schluessel} e={e} heute={heute} onWahl={setEintrag} voll />)}
            </Karte>
          ) : null}
          <Karte className="px-4 py-3.5 flex flex-col gap-3" data-testid="ueberfaellig">
            <h2 className="lbl m-0 flex items-center gap-2"><Icon name="warnung" groesse={16} />Überfällig</h2>
            <Seitenliste titel="Offene Termine" anzahl={ueberfaellig.termine.length} testid="ueberfaellig-termine">
              <Gekuerzt eintraege={ueberfaellig.termine} heute={heute} onWahl={setEintrag} />
            </Seitenliste>
            <Seitenliste titel={`Kontakt überfällig (über ${daten.data?.grenzen.kontakt_monate ?? "…"} Mon.)`} anzahl={ueberfaellig.kontakt.length}
              testid="ueberfaellig-kontakt">
              <Gekuerzt eintraege={ueberfaellig.kontakt} heute={heute} onWahl={setEintrag} />
            </Seitenliste>
            <Seitenliste titel={`Kontakt bald fällig (über ${daten.data?.grenzen.kontakt_bald_monate ?? "…"} Mon.)`} anzahl={ueberfaellig.bald.length}
              testid="bald-kontakt">
              <Gekuerzt eintraege={ueberfaellig.bald} heute={heute} onWahl={setEintrag} />
            </Seitenliste>
            <Seitenliste titel={`Plan prüfen (älter als ${daten.data?.grenzen.plan_monate ?? "…"} Mon.)`} anzahl={ueberfaellig.plan.length}
              testid="ueberfaellig-plan">
              <Gekuerzt eintraege={ueberfaellig.plan} heute={heute} onWahl={setEintrag} />
            </Seitenliste>
          </Karte>
          <div className="flex flex-col gap-1.5 text-xs gedaempft px-1">
            <span className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm bg-akzent-weich" />Praxistermin
              <span className="w-3 h-3 rounded-sm bg-warn-bg ml-2" />Wiedervorlage<span className="w-3 h-3 rounded-sm bg-fehler-bg ml-2" />überfällig</span>
            <span className="flex items-center gap-2 flex-wrap"><span className="w-3 h-3 rounded-sm border border-dashed border-warn" />berechnet: Kontakt bald fällig
              <span className="w-3 h-3 rounded-sm border border-dashed border-fehler ml-2" />Kontakt überfällig
              <span className="w-3 h-3 rounded-sm border border-dashed border-akzent ml-2" />Plan prüfen</span>
          </div>
        </div>
      </div>
      <EintragDialog e={eintrag} heute={heute} onZu={() => setEintrag(null)}
        onTermin={(patient, name, d) => { setEintrag(null); setNeu({ datum: d, patient, name }); }}
        onAendern={(t) => { setEintrag(null); setAendern(t); }} />
      {schreiben ? (
        <TerminDialog offen={!!neu} onOffen={(o) => { if (!o) setNeu(null); }} datum={neu?.datum}
          patientId={neu?.patient} patientName={neu?.name} />
      ) : null}
      {schreiben ? <TerminDialog offen={!!aendern} onOffen={(o) => { if (!o) setAendern(null); }} termin={aendern}
        patientName={aendern?.patient_name} /> : null}
      {/* „×“: Termin oder Fälligkeit ausblenden – 3/6/12 Monate oder „nicht mehr nötig“, mit Grund (F142) */}
      <RuheDialog offen={!!weg} onOffen={(o) => { if (!o) setWeg(null); }}
        patientId={weg?.termin?.patient ?? weg?.faellig?.patient ?? 0} termin={weg?.termin ?? null}
        hinweis={weg?.faellig ? { art: weg.faellig.art, text: `${faelligName(weg.faellig)}: ${weg.faellig.name} – ${weg.faellig.text}` } : null} />
    </Seite>
    </Ausblenden.Provider>
  );
}
