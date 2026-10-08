/** Kacheln der Startseite für die Arbeit mit den Akten (S03–S07, S09, S10; Entwurf 2). */
import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth, useOhneRechtSchliessen } from "@/lib/auth";
import { alsDatum, datum, heuteIso, kg, nummer, prozent, relativ, terminZeit, uhrzeit, vorZeit, zahl } from "@/lib/format";
import { TERMINARTEN } from "@/lib/typen";
import type { Termin } from "@/lib/typen";
import { Chip, Knopf, KnopfLink, Leer, Segmente, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { TerminDialog } from "@/components/TerminDialog";
import type { Vorgabe } from "@/components/Schnellerfassung";
import type { MeineAkte, MeineAkten, Startdaten, Wiedereintrag, Zuletzt } from "./daten";

// ---------------------------------------------------------------- Bausteine einer Kachel
export function KachelKopf({ id, titel, rechts, unter }: { id: string; titel: ReactNode; rechts?: ReactNode; unter?: ReactNode }) {
  return (
    <div className="flex justify-between items-start gap-x-3 gap-y-2 flex-wrap px-5 pt-4 pb-2 shrink-0">
      <div className="flex flex-col gap-0.5 min-w-0">
        <h2 id={`k-${id}`} className="lbl m-0">{titel}</h2>
        {unter ? <span className="text-[0.78125rem] gedaempft">{unter}</span> : null}
      </div>
      {rechts ? <div className="flex items-center gap-2 flex-wrap">{rechts}</div> : null}
    </div>
  );
}

/** Inhalt: scrollt in der Kachel, wenn er nicht passt (Festlegung 01.10.2026) */
export function KachelInhalt({ children, className, testid }: { children: ReactNode; className?: string; testid?: string }) {
  return <div className={cx("kachel-inhalt px-5 pb-3", className)} data-testid={testid}>{children}</div>;
}

export function KachelFuss({ zu, children }: { zu: string; children: ReactNode }) {
  return (
    <Link to={zu} className="shrink-0 mx-5 py-2.5 border-t border-rand text-[0.8125rem] font-medium no-underline flex items-center gap-1">
      {children}<Icon name="pfeilRechts" groesse={14} />
    </Link>
  );
}

function Person({ name, zu, unter, extra }: { name: ReactNode; zu: string; unter?: ReactNode; extra?: ReactNode }) {
  return (
    <span className="flex flex-col gap-px min-w-0">
      <span className="flex items-center gap-2 min-w-0"><Link to={zu} className="font-medium no-underline truncate">{name}</Link>{extra}</span>
      {unter ? <span className="text-[0.78125rem] gedaempft truncate">{unter}</span> : null}
    </span>
  );
}

function Zeile({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("flex justify-between items-center gap-3 py-[9px] border-b border-rand last:border-b-0", className)}>{children}</div>;
}

// ---------------------------------------------------------------- Termine und Wiedervorlagen (S03: Wochenstreifen)
const WOCHENTAGE = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

function terminChip(t: Termin) {
  if (t.art === "wiedervorlage") return <Chip art="warn">{TERMINARTEN[t.art]}</Chip>;
  if (t.art === "praxistermin") return <Chip art="akzent">{t.ort_name || t.bei || TERMINARTEN[t.art]}</Chip>;
  return <Chip>{TERMINARTEN[t.art]}</Chip>;
}

function Wochenstreifen({ woche, tag, onTag }: { woche: Startdaten["woche"]; tag: string | null; onTag: (t: string | null) => void }) {
  return (
    <div role="group" aria-label="Tag wählen" className="grid grid-cols-7 gap-1.5 px-5 pb-2 shrink-0" data-testid="wochenstreifen">
      {woche.map((w, i) => {
        const d = alsDatum(w.datum)!;
        const frei = !!w.feiertag || d.getDay() === 0 || d.getDay() === 6;
        const an = tag === w.datum;
        return (
          <button key={w.datum} type="button" aria-pressed={an} onClick={() => onTag(an ? null : w.datum)}
            title={w.feiertag ?? undefined} data-testid={`tag-${w.datum}`}
            className={cx("flex flex-col items-start gap-0.5 px-2.5 py-1.5 rounded-[10px] border text-left cursor-pointer min-w-0",
              an ? "border-akzent bg-akzent-weich" : frei ? "border-dashed border-rand bg-grund" : "border-rand bg-flaeche",
              frei && !an && "text-gedaempft")}>
            <span className={cx("text-xs", an || i === 0 ? "text-akzent-text font-semibold" : "gedaempft")}>{WOCHENTAGE[d.getDay()]}{i === 0 ? " · heute" : ""}</span>
            <span className="text-sm font-medium">{d.toLocaleDateString("de-DE", { day: "numeric", month: "short" })}</span>
            <span className="text-[0.78125rem] truncate max-w-full">{w.feiertag ?? (w.anzahl ? `${w.anzahl} ${w.anzahl === 1 ? "Termin" : "Termine"}` : "—")}</span>
            <span className="flex gap-[3px] h-1.5" aria-label={w.praxistermine ? `${w.praxistermine} Praxistermine` : undefined}>
              {Array.from({ length: Math.min(w.praxistermine, 6) }, (_, j) => <span key={j} className="w-1.5 h-1.5 rounded-full bg-akzent" />)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function TermineKachel({ daten, breit }: { daten: Startdaten; breit: boolean }) {
  const { darf, darfBei } = useAuth();
  const [tab, setTab] = useState<"heute" | "woche" | "ueber">("heute");
  const [tag, setTag] = useState<string | null>(null);
  const [dialog, setDialog] = useState(false);
  const [erledigt, setErledigt] = useState<Record<number, Termin>>({});
  const [laeuft, setLaeuft] = useState<number[]>([]);
  const qc = useQueryClient();
  const melden = useHinweis();
  const abhaken = useMutation({
    mutationFn: (t: Termin) => api<Termin>(`termine/${t.id}/erledigt/`, { method: "POST" }),
    onMutate: (t) => setLaeuft((l) => [...l, t.id]), // Haken sofort zeigen, bei Fehler zurücknehmen
    onSettled: (_d, _e, t) => setLaeuft((l) => l.filter((x) => x !== t.id)),
    onSuccess: (t) => {
      setErledigt((e) => ({ ...e, [t.id]: t }));
      void qc.invalidateQueries({ queryKey: ["patient", t.patient] });
      melden(`Erledigt: ${t.patient_name}`);
    },
    onError: (e) => melden(e.message, "fehler"),
  });
  const offen = (l: Termin[]) => l.filter((t) => !erledigt[t.id]).length;
  const heute = daten.termine.heute, woche = daten.termine.naechste_7_tage, ueber = daten.termine.ueberfaellig;
  const zeilen = tag ? woche.filter((t) => t.faellig_am === tag) : tab === "heute" ? heute : tab === "woche" ? woche : ueber;
  const schreiben = darf("eintraege_erfassen");
  useOhneRechtSchliessen(schreiben, () => setDialog(false));
  return (
    <>
      <KachelKopf id="termine" titel="Termine und Wiedervorlagen" rechts={<>
        <Segmente label="Zeitraum" wert={tag ? "woche" : tab} onWahl={(w) => { setTab(w); setTag(null); }} werte={[
          { wert: "heute", text: <>Heute <span className="num opacity-70">{offen(heute)}</span></> },
          { wert: "woche", text: <>7 Tage <span className="num opacity-70">{offen(woche)}</span></> },
          { wert: "ueber", text: <>Überfällig <span className="num opacity-70">{offen(ueber)}</span></> },
        ]} />
        {schreiben ? <Knopf klein icon="plus" aria-label="Termin anlegen" onClick={() => setDialog(true)}>Termin</Knopf> : null}
      </>} />
      {breit ? <Wochenstreifen woche={daten.woche} tag={tag} onTag={(t) => { setTag(t); if (t) setTab("woche"); }} /> : null}
      <KachelInhalt testid="terminliste">
        {tag ? <span className="block text-[0.78125rem] gedaempft pb-1">{datum(tag)}{daten.woche.find((w) => w.datum === tag)?.feiertag
          ? ` · ${daten.woche.find((w) => w.datum === tag)?.feiertag}` : ""}</span> : null}
        {zeilen.length === 0 ? <Leer>Keine offenen Termine.</Leer> : zeilen.map((t) => {
          const fertig = erledigt[t.id];
          const kaestchen = darfBei("eintraege_erfassen", { ist_test: t.patient_ist_test }) ? (
            <input type="checkbox" title="Erledigt" aria-label={`Erledigt: ${t.patient_name}, ${t.titel}`} className="!w-5 !h-5"
              checked={!!fertig || laeuft.includes(t.id)} disabled={!!fertig || laeuft.includes(t.id)} onChange={() => abhaken.mutate(t)} />
          ) : <span aria-hidden="true" />;
          const wer = (
            <span className="text-[0.78125rem] gedaempft">
              {fertig ? `erledigt ${uhrzeit(fertig.erledigt_am)} von ${fertig.erledigt_von_name ?? "—"}` : `angelegt von ${t.angelegt_von_name ?? "—"}`}
            </span>
          );
          const text = fertig ? <span className="gedaempft line-through">{t.patient_name} · {t.titel}</span> : (
            <span className="min-w-0"><Link to={`/patienten/${t.patient}`} className="font-medium no-underline">{t.patient_name}</Link>{" "}
              <span className="text-text2">· {t.titel}{t.notiz ? ` – ${t.notiz}` : ""}</span></span>
          );
          return breit ? (
            <div key={t.id} className="grid grid-cols-[28px_128px_168px_minmax(0,1fr)] items-center gap-3 py-[9px] border-b border-rand last:border-b-0">
              {kaestchen}
              <span className="num text-[0.84375rem] text-text2">{terminZeit(t.faellig_am, t.uhrzeit)}</span>
              <span className="min-w-0 truncate">{terminChip(t)}</span>
              <span className="flex flex-col gap-px min-w-0">{text}{wer}</span>
            </div>
          ) : (
            <div key={t.id} className="grid grid-cols-[28px_minmax(0,1fr)] items-start gap-2.5 py-[9px] border-b border-rand last:border-b-0">
              {kaestchen}
              <span className="flex flex-col gap-1 min-w-0">
                <span className="flex items-center gap-2 flex-wrap"><span className="num text-[0.8125rem] text-text2">{terminZeit(t.faellig_am, t.uhrzeit)}</span>{terminChip(t)}</span>
                {text}{wer}
              </span>
            </div>
          );
        })}
      </KachelInhalt>
      <KachelFuss zu="/kalender">Alle Termine im Kalender</KachelFuss>
      {schreiben ? <TerminDialog offen={dialog} onOffen={setDialog} datum={tag ?? undefined} /> : null}
    </>
  );
}

// ---------------------------------------------------------------- Wiedereinbestellung fällig (S04)
export function WiederKachel({ daten, onKontakt, onTermin }: { daten: Startdaten; onKontakt: (v: Vorgabe) => void;
  onTermin: (v: Vorgabe) => void }) {
  const { darfBei } = useAuth();
  const w = daten.wiedereinbestellung;
  const liste = (xs: Wiedereintrag[]) => xs.map((x) => (
    <Zeile key={x.patient}>
      <Person name={x.name} zu={`/patienten/${x.patient}`} extra={x.ist_test ? <Chip art="warn">Test</Chip> : null}
        unter={x.letzter_kontakt ? <>zuletzt <span className="num">{datum(x.letzter_kontakt)}</span> · {vorZeit(x.letzter_kontakt)}</> : "noch kein Kontakt erfasst"} />
      {darfBei("eintraege_erfassen", { ist_test: x.ist_test }) ? (
        <span className="flex gap-1 shrink-0">
          <Knopf klein variante="sec" className="icon" aria-label={`Kontakt erfassen: ${x.name}`} title="Kontakt erfassen"
            onClick={() => onKontakt({ id: x.patient, name: x.name, ist_test: x.ist_test })}><Icon name="telefon" groesse={15} /></Knopf>
          <Knopf klein variante="sec" className="icon" aria-label={`Termin anlegen: ${x.name}`} title="Termin anlegen"
            onClick={() => onTermin({ id: x.patient, name: x.name, ist_test: x.ist_test })}><Icon name="kalender" groesse={15} /></Knopf>
        </span>
      ) : null}
    </Zeile>
  ));
  const gesamt = w.anzahl_ueberfaellig + w.anzahl_bald;
  return (
    <>
      <KachelKopf id="wieder" titel="Wiedereinbestellung fällig" unter="Kein Kontakt und kein Termin geplant" />
      <KachelInhalt testid="wiedereinbestellung">
        {gesamt === 0 ? <Leer>Niemand fällig – alle haben einen aktuellen Kontakt oder einen geplanten Termin.</Leer> : null}
        {w.anzahl_ueberfaellig ? (
          <>
            <span className="flex justify-between items-center pt-1 text-[0.78125rem] font-semibold text-fehler">
              <span>Überfällig · über {w.ueberfaellig_monate} Monate</span><Chip art="fehler" className="num" data-testid="wieder-ueberfaellig">{w.anzahl_ueberfaellig}</Chip>
            </span>
            <div className="flex flex-col">{liste(w.ueberfaellig)}</div>
          </>
        ) : null}
        {w.anzahl_bald ? (
          <>
            <span className="flex justify-between items-center pt-3 text-[0.78125rem] font-semibold text-warn">
              <span>Bald fällig · {w.bald_monate} bis {w.ueberfaellig_monate} Monate</span><Chip art="warn" className="num" data-testid="wieder-bald">{w.anzahl_bald}</Chip>
            </span>
            <div className="flex flex-col">{liste(w.bald)}</div>
          </>
        ) : null}
      </KachelInhalt>
      {gesamt ? <KachelFuss zu="/patienten?pruefen=wiedereinbestellung">Alle {gesamt} in der Patientenliste</KachelFuss> : null}
    </>
  );
}

// ---------------------------------------------------------------- Meine Akten (S05)
function Stern({ an }: { an: boolean }) {
  return <Icon name="stern" groesse={16} fill={an ? "currentColor" : "none"} />;
}

function akteUnter(a: MeineAkte) {
  const teile: string[] = [];
  if (a.gewicht) {
    const r = a.trend?.richtung;
    teile.push(`${kg(a.gewicht.kg)}${r ? ` ${r === "down" ? "↓" : r === "up" ? "↑" : "→"}` : ""}`);
  }
  if (a.naechster_termin) {
    teile.push(a.naechster_termin.faellig_am === heuteIso() ? "Termin heute"
      : a.naechster_termin.faellig_am < heuteIso() ? "Termin überfällig" : `Termin ${terminZeit(a.naechster_termin.faellig_am, a.naechster_termin.uhrzeit)}`);
  }
  if (a.plan_entwurf) teile.push("Plan im Entwurf");
  if (a.ist_abgeschlossen) teile.push("abgeschlossen");
  return teile.join(" · ");
}

export function MeineKachel() {
  const [ansicht, setAnsicht] = useState<"merkliste" | "zuletzt">("merkliste");
  const qc = useQueryClient();
  const melden = useHinweis();
  const daten = useQuery({ queryKey: ["meine-akten"], queryFn: () => api<MeineAkten>("meine-akten/") });
  const umschalten = useMutation({
    mutationFn: ({ a, merken }: { a: MeineAkte; merken: boolean }) => merken
      ? api<MeineAkten>("meine-akten/merken/", { body: { patient: a.patient } })
      : api<MeineAkten>(`meine-akten/merken/${a.patient}/`, { method: "DELETE" }),
    onSuccess: (neu, { a, merken }) => {
      qc.setQueryData(["meine-akten"], neu);
      void qc.invalidateQueries({ queryKey: ["patient", a.patient] });
      melden(merken ? `${a.name} auf der Merkliste.` : `${a.name} von der Merkliste genommen.`);
    },
    onError: (e) => melden(e.message, "fehler"),
  });
  const d = daten.data;
  const gemerkt = new Set((d?.merkliste ?? []).map((a) => a.patient));
  const liste = (ansicht === "merkliste" ? d?.merkliste : d?.zuletzt) ?? [];
  return (
    <>
      <KachelKopf id="meine" titel="Meine Akten" rechts={
        <Segmente label="Auswahl" wert={ansicht} onWahl={setAnsicht} werte={[
          { wert: "merkliste", text: <>Merkliste <span className="num opacity-70">{d ? d.merkliste.length : ""}</span></> },
          { wert: "zuletzt", text: "Zuletzt geöffnet" },
        ]} />} />
      <KachelInhalt testid="meine-akten">
        {d && liste.length === 0 ? (
          <Leer>{ansicht === "merkliste" ? "Noch nichts gemerkt. Der Stern im Kopf einer Akte setzt sie auf die Merkliste." : "Noch keine Akte geöffnet."}</Leer>
        ) : null}
        {liste.map((a) => {
          const an = gemerkt.has(a.patient);
          return (
            <Zeile key={a.patient}>
              <span className="flex items-center gap-2 min-w-0">
                <button type="button" className={cx("bg-transparent border-0 p-0 cursor-pointer flex", an ? "text-akzent-text" : "gedaempft")}
                  aria-label={an ? `Von der Merkliste nehmen: ${a.name}` : `Auf die Merkliste: ${a.name}`} aria-pressed={an}
                  onClick={() => umschalten.mutate({ a, merken: !an })}><Stern an={an} /></button>
                <Person name={<>{a.name} <span className="num gedaempft font-normal text-[0.78125rem]">{nummer(a.nummer)}</span></>}
                  zu={`/patienten/${a.patient}`} unter={akteUnter(a) || (ansicht === "zuletzt" ? `geöffnet ${relativ(a.am, true)}` : undefined)} />
              </span>
            </Zeile>
          );
        })}
      </KachelInhalt>
    </>
  );
}

// ---------------------------------------------------------------- Auffällige Gewichte (S06: Mini-Verlauf)
const TAG_MS = 86400000;

/** Mini-Verlauf der letzten 6 Monate in echten Zeitabständen (x = Tage), letzter Wert als Punkt */
export function Funke({ punkte }: { punkte: { am: string; kg: number }[] }) {
  if (punkte.length < 2) return null;
  const start = Date.now() - 180 * TAG_MS;
  const xs = punkte.map((p) => 4 + 72 * Math.min(1, Math.max(0, ((alsDatum(p.am)?.getTime() ?? start) - start) / (180 * TAG_MS))));
  const vs = punkte.map((p) => Number(p.kg));
  const lo = Math.min(...vs), hi = Math.max(...vs);
  const ys = vs.map((v) => 4 + (20 * (hi - v)) / Math.max(hi - lo, 0.1));
  const pfad = xs.map((x, i) => `${i ? "L" : "M"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  return (
    <svg width="80" height="28" viewBox="0 0 80 28" role="img" className="text-fehler shrink-0"
      aria-label={`Verlauf 6 Monate: ${kg(vs[0])} am ${datum(punkte[0].am)} bis ${kg(vs[vs.length - 1])} am ${datum(punkte[punkte.length - 1].am)}`}>
      <path d={pfad} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="2.2" fill="currentColor" />
    </svg>
  );
}

export function GewichtKachel({ daten }: { daten: Startdaten }) {
  const s = daten.gewicht_schwelle;
  const liste = daten.gewichtswarnungen;
  return (
    <>
      <KachelKopf id="gewicht" titel="Auffällige Gewichte"
        unter={`Mehr als ${String(s.prozent).replace(".", ",")} % Verlust in ${s.monate} Monaten · 6 Monate Verlauf`} />
      <KachelInhalt testid="gewichtswarnungen">
        {liste.length === 0 ? <Leer>Keine auffälligen Gewichte.</Leer> : liste.map((w) => (
          <Zeile key={w.patient}>
            <Person name={w.name} zu={`/patienten/${w.patient}`}
              unter={w.gewicht ? <span className="num">{kg(w.gewicht.kg)} · {datum(w.gewicht.am).slice(0, 6)}</span> : undefined} />
            <span className="flex items-center gap-2 shrink-0"><Funke punkte={w.verlauf} /><Chip art="warn" className="num">{prozent(w.prozent)}</Chip></span>
          </Zeile>
        ))}
      </KachelInhalt>
      {liste.length ? <KachelFuss zu="/patienten?schnellfilter=gewichtsverlust">Alle {liste.length} in der Patientenliste</KachelFuss> : null}
    </>
  );
}

// ---------------------------------------------------------------- Infusionspläne (S07)
export function PlaeneKachel({ daten }: { daten: Startdaten }) {
  const p = daten.infusionsplaene;
  return (
    <>
      <KachelKopf id="plaene" titel="Infusionspläne" />
      <KachelInhalt testid="plaene-kachel">
        <span className="block text-[0.78125rem] font-semibold gedaempft">Zur Freigabe · <span className="num">{p.anzahl_entwuerfe}</span></span>
        <div className="flex flex-col">
          {p.entwuerfe.length === 0 ? <span className="text-sm gedaempft py-2">Keine Entwürfe.</span> : p.entwuerfe.map((e) => (
            <Zeile key={e.id}>
              <Person name={e.name} zu={`/patienten/${e.patient}/plaene?plan=${e.id}`}
                unter={`seit ${vorZeit(e.erstellt_am).replace(/^vor /, "")} · ${e.erstellt_von ?? "—"}`} />
              <KnopfLink klein to={`/patienten/${e.patient}/plaene?plan=${e.id}`} aria-label={`Entwurf prüfen: ${e.name}`}>Prüfen</KnopfLink>
            </Zeile>
          ))}
        </div>
        <Link to="/infusionsplaene?gruppe=alt" className="mt-1.5 flex justify-between items-center px-3 py-2.5 rounded-[10px] bg-grund no-underline text-tinte text-sm">
          <span>Älter als {p.grenze_monate} Monate</span><Chip art={p.anzahl_aelter ? "warn" : undefined} className="num" data-testid="plaene-alt">{p.anzahl_aelter}</Chip>
        </Link>
      </KachelInhalt>
      <KachelFuss zu="/infusionsplaene?gruppe=entwuerfe">Zur Übersicht der Pläne</KachelFuss>
    </>
  );
}

// ---------------------------------------------------------------- Nach und nach prüfen (S04, S09)
export function PruefenKachel({ daten }: { daten: Startdaten }) {
  const p = daten.pruefen;
  const { darf } = useAuth();
  const eintraege: [string, number, string][] = [
    ["Altdokumente: Typ und Datum prüfen", p.altdokumente, "altdokumente"],
    ["Nickelallergie nicht erfasst", p.nickelallergie_unbekannt, "nickelallergie"],
    ["Versorger nicht erfasst", p.kein_versorger, "kein_versorger"],
    // Ergänzung zur Fehlerliste 02.10.2026: Akten ohne Plan, bei denen niemand „kein Plan nötig“ bestätigt hat
    ["Kein Infusionsplan", p.ohne_plan ?? 0, "ohne_plan"],
    [`Kontakt überfällig (über ${p.kontakt_ueberfaellig_monate} Monate)`, p.kontakt_ueberfaellig, "kontakt_ueberfaellig"],
    [`Kontakt bald fällig (${p.kontakt_bald_monate}–${p.kontakt_ueberfaellig_monate} Monate)`, p.kontakt_bald, "kontakt_bald"],
    // Datenschutz: Erklärungen nachhalten wie die Nickelallergie; lange ruhende Akten abschließen (erst dann läuft die Frist)
    // Befunde (F120): fehlt ganz oder ist älter als die eingestellte Grenze
    [`Laborbefund fehlt oder ist älter als ${p.labor_monate ?? 12} Monate`, p.labor_faellig ?? 0, "labor_faellig"],
    [`BIA-Messung fehlt oder ist älter als ${p.bia_monate ?? 12} Monate`, p.bia_faellig ?? 0, "bia_faellig"],
    ["Erklärungen zum Datenschutz fehlen", p.erklaerungen_fehlen, "erklaerungen"],
    [`Abschluss prüfen: kein Kontakt seit über ${p.abschluss_monate} Monaten`, p.abschluss_pruefen, "abschluss_pruefen"],
  ];
  const datenschutz = (darf("datenschutz_bearbeiten") || darf("datenschutz_entscheiden")) && p.datenschutz_anfragen > 0;
  const geprueft = p.altdokumente_gesamt - p.altdokumente;
  const anteil = p.altdokumente_gesamt ? Math.round((100 * geprueft) / p.altdokumente_gesamt) : 0;
  return (
    <>
      <KachelKopf id="pruefen" titel="Nach und nach prüfen" />
      <KachelInhalt className="flex flex-col gap-2.5">
        {p.altdokumente_gesamt ? (
          <div className="flex flex-col gap-1.5" data-testid="altdokumente-fortschritt">
            <div className="flex justify-between text-[0.8125rem] text-text2"><span>Altdokumente geprüft</span>
              <span className="num">{zahl(geprueft)} von {zahl(p.altdokumente_gesamt)}</span></div>
            <div role="progressbar" aria-label="Altdokumente geprüft" aria-valuemin={0} aria-valuemax={p.altdokumente_gesamt}
              aria-valuenow={geprueft} className="h-2 rounded bg-fein overflow-hidden">
              <div className="h-2 rounded bg-akzent" style={{ width: `${anteil}%` }} />
            </div>
          </div>
        ) : null}
        <div className="flex flex-col gap-2.5 text-sm">
          {eintraege.map(([text, n, filter]) => (
            <Link key={filter} to={`/patienten?pruefen=${filter}`} className="flex justify-between gap-3 no-underline text-tinte hover:text-akzent-text">
              <span>{text}</span><span className="num text-akzent-text" data-testid={`pruefen-${filter}`}>{n}</span>
            </Link>
          ))}
          {datenschutz ? (
            <Link to="/datenschutz" className="flex justify-between gap-3 no-underline text-tinte hover:text-akzent-text">
              <span>Offene Datenschutz-Anfragen{p.datenschutz_ueberfaellig ? <span className="text-fehler" data-testid="pruefen-datenschutz-ueberfaellig"> · {p.datenschutz_ueberfaellig} überfällig</span> : null}</span>
              <span className="num text-akzent-text" data-testid="pruefen-datenschutz">{p.datenschutz_anfragen}</span>
            </Link>
          ) : null}
        </div>
      </KachelInhalt>
    </>
  );
}

// ---------------------------------------------------------------- Zuletzt eingetragen (S10)
const BEREICHE: Record<string, string> = { kontakt: "Kontakt", gewicht: "Gewicht", dokument: "Dokument", plan: "Plan", termin: "Termin" };

function wann(z: string) {
  const r = relativ(z);
  return r === "heute" ? uhrzeit(z) : r === "gestern" ? "gestern" : datum(z).slice(0, 6);
}

export function AktivKachel({ daten, breit }: { daten: Startdaten; breit: boolean }) {
  const [wer, setWer] = useState<"alle" | "ich">("alle");
  const liste: Zuletzt[] = wer === "alle" ? daten.zuletzt_eingetragen : daten.zuletzt_von_mir;
  return (
    <>
      <KachelKopf id="aktiv" titel="Zuletzt eingetragen" rechts={
        <Segmente label="Wer" wert={wer} onWahl={setWer} werte={[{ wert: "alle", text: "Alle" }, { wert: "ich", text: "Von mir" }]} />} />
      <KachelInhalt className="text-[0.84375rem]" testid="zuletzt-eingetragen">
        {liste.length === 0 ? <Leer>{wer === "alle" ? "Noch nichts eingetragen." : "Von dir ist noch nichts eingetragen."}</Leer> : liste.map((z, i) => breit ? (
          <div key={`${z.bereich}-${z.objekt_id}-${i}`} className="grid grid-cols-[64px_120px_90px_minmax(0,1fr)_minmax(0,160px)] items-center gap-3 py-[7px] border-b border-rand last:border-b-0">
            <span className="num gedaempft">{wann(z.zeitpunkt)}</span>
            <span className="truncate">{z.person ?? "—"}</span>
            <span><Chip>{BEREICHE[z.bereich] ?? z.bereich}</Chip></span>
            <span className="text-text2 truncate">{z.bezeichnung}</span>
            <Link to={`/patienten/${z.patient}`} className="font-medium no-underline truncate">{z.name ?? "Akte"}</Link>
          </div>
        ) : (
          <div key={`${z.bereich}-${z.objekt_id}-${i}`} className="py-[7px] border-b border-rand last:border-b-0">
            <span className="num gedaempft">{wann(z.zeitpunkt)}</span> {z.person ?? "—"} · {z.bezeichnung}{" "}
            <Link to={`/patienten/${z.patient}`}>{z.name?.split(",")[0] ?? "Akte"}</Link>
          </div>
        ))}
      </KachelInhalt>
    </>
  );
}
