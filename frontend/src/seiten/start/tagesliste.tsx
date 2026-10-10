/**
 * „Heute zu tun“ ganz oben auf der Startseite (F184, Automatisierungen für die Pflege 10.10.2026).
 *
 * Eine kurze, priorisierte Liste: heutige Termine, fällige Rückrufe und Wiedervorlagen, Infoblatt an die Praxis,
 * fehlende Terminbestätigungen, überfällige Kontakte, Pläne zur Freigabe, Scans zum Zuordnen und fehlende Angaben in
 * den Akten (F186). Jede Zeile führt mit einem Klick zum Ziel; was erledigt ist, verschwindet. Nichts wird von allein
 * verschickt oder eingetragen – Knöpfe öffnen nur den passenden Dialog.
 *
 * Ersetzt die einzelnen Hinweise „Praxis informieren“ (F177) und „Scans warten auf Zuordnung“ (F165) oben auf der Seite.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, terminZeit } from "@/lib/format";
import { TERMINARTEN } from "@/lib/typen";
import type { ScansStand, Termin } from "@/lib/typen";
import { Chip, Knopf, KnopfLink, cx } from "@/components/ui/basis";
import { Begriff } from "@/components/ui/Begriff";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { AnkuendigungDialog } from "@/components/AnkuendigungDialog";
import { TerminDialog } from "@/components/TerminDialog";
import { BestaetigungDialog } from "@/components/TerminBestaetigung";
import type { LueckenArt, Startdaten } from "./daten";

/** Wie viele Einträge eine Gruppe aufgeklappt zeigt, bevor „… weitere“ zum Ziel führt */
const HOECHSTENS = 3;

const LUECKEN: { art: LueckenArt; filter: string; text: (n: number, monate: number) => string }[] = [
  { art: "telefon", filter: "ohne_telefon", text: (n) => `${n === 1 ? "1 Akte" : `${n} Akten`} ohne Telefonnummer` },
  { art: "hausarzt", filter: "ohne_hausarzt", text: (n) => `${n === 1 ? "1 Akte" : `${n} Akten`} ohne Hausarzt` },
  { art: "diagnose", filter: "ohne_diagnose", text: (n) => `${n === 1 ? "1 Akte" : `${n} Akten`} ohne Diagnose` },
  { art: "gewicht_fehlt", filter: "ohne_gewicht",
    text: (n, m) => `${n === 1 ? "1 Akte" : `${n} Akten`} ohne Gewicht seit ${m} ${m === 1 ? "Monat" : "Monaten"}` },
];

function mehrzahl(n: number, eins: string, viele: string) {
  return `${n} ${n === 1 ? eins : viele}`;
}

/** Eine Zeile der Liste: Symbol, Text, Anzahl, Ziel (Link oder Knopf); darunter ggf. die einzelnen Einträge */
function Punkt({ icon, art, text, unter, anzahl, zu, aktion, children, testid }: {
  icon: string; art?: "warn" | "fehler"; text: ReactNode; unter?: ReactNode; anzahl?: number; zu?: string; aktion?: ReactNode;
  children?: ReactNode; testid: string;
}) {
  const kopf = (
    <>
      <span className={cx("shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
        art === "fehler" ? "bg-fehler-bg text-fehler" : art === "warn" ? "bg-warn-bg text-warn" : "bg-akzent-weich text-akzent-text")}>
        <Icon name={icon} groesse={16} /></span>
      <span className="grow min-w-0 flex flex-col gap-px">
        <span className="font-medium">{text}</span>
        {unter ? <span className="text-[0.78125rem] gedaempft">{unter}</span> : null}
      </span>
      {anzahl !== undefined ? <Chip art={art} className="num shrink-0">{anzahl}</Chip> : null}
    </>
  );
  return (
    <li className="border-b border-rand last:border-b-0" data-testid={testid}>
      {zu ? (
        <Link to={zu} className="flex items-center gap-3 min-h-12 py-2 no-underline text-tinte hover:text-akzent-text">
          {kopf}<Icon name="pfeilRechts" groesse={16} className="shrink-0 gedaempft" />
        </Link>
      ) : (
        <div className="flex items-center gap-x-3 gap-y-2 min-h-12 py-2 flex-wrap">
          <span className="grow min-w-[min(100%,16rem)] flex items-center gap-3">{kopf}</span>{aktion}
        </div>
      )}
      {children ? <ul className="m-0 p-0 list-none pl-11 pb-2 flex flex-col">{children}</ul> : null}
    </li>
  );
}

/** Einzelner Termin unter einer Gruppe: Uhrzeit, Patient (zur Akte), Ort bzw. Titel, rechts eine Aktion */
function TerminZeile({ t, aktion, zeit = "uhr" }: { t: Termin; aktion?: ReactNode; zeit?: "uhr" | "datum" }) {
  const wann = zeit === "uhr" ? (t.uhrzeit ? t.uhrzeit.slice(0, 5) : "ganztägig") : terminZeit(t.faellig_am, t.uhrzeit);
  const wo = t.art === "praxistermin" ? (t.ort_name || t.bei || "Ort fehlt") : TERMINARTEN[t.art];
  return (
    <li className="flex items-center gap-x-3 gap-y-1 py-1.5 flex-wrap text-[0.875rem]" data-testid="heute-zu-tun-termin">
      <span className={cx("num text-text2 shrink-0 whitespace-nowrap", zeit === "uhr" ? "w-[4.5rem]" : "w-[8.5rem]")}>{wann}</span>
      <span className="min-w-0 grow flex flex-col gap-px">
        <Link to={`/patienten/${t.patient}`} className="font-medium no-underline truncate">{t.patient_name}</Link>
        <span className="text-[0.78125rem] gedaempft truncate">{wo}{t.titel && t.titel !== TERMINARTEN[t.art] ? ` · ${t.titel}` : ""}</span>
      </span>
      {aktion ? <span className="ml-auto">{aktion}</span> : null}
    </li>
  );
}

function Weitere({ n, zu, text }: { n: number; zu: string; text: string }) {
  if (n <= 0) return null;
  return <li className="py-1 text-[0.8125rem]"><Link to={zu} className="font-medium">… und {n} weitere {text}</Link></li>;
}

export function Tagesliste({ d }: { d: Startdaten }) {
  const { darf, darfBei } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [weg, setWeg] = useState<number[]>([]);
  const [infoblatt, setInfoblatt] = useState(false);
  const [bestaetigen, setBestaetigen] = useState<Termin | null>(null);
  const [ortTermin, setOrtTermin] = useState<Termin | null>(null);
  const erfassen = darf("eintraege_erfassen");
  const scans = useQuery({
    queryKey: ["scans", "stand"],
    queryFn: () => api<ScansStand>("scans/stand/"),
    enabled: darf("scans_bearbeiten"),
    staleTime: 30_000,
  });
  const abhaken = useMutation({
    mutationFn: (t: Termin) => api<Termin>(`termine/${t.id}/erledigt/`, { method: "POST" }),
    onMutate: (t) => setWeg((w) => [...w, t.id]), // verschwindet sofort, bei Fehler wieder da
    onSuccess: (t) => {
      melden(`Erledigt: ${t.patient_name}`);
      for (const k of [["startseite"], ["termine"], ["kalender"], ["patient", t.patient]]) void qc.invalidateQueries({ queryKey: k });
    },
    onError: (e, t) => { setWeg((w) => w.filter((x) => x !== t.id)); melden(e.message, "fehler"); },
  });
  const tl = d.tagesliste;
  if (!tl) return null;

  const heute = tl.termine_heute.filter((t) => !weg.includes(t.id));
  const rueckrufe = tl.rueckrufe.filter((t) => !weg.includes(t.id));
  const rueckrufAnzahl = Math.max(0, tl.rueckrufe_anzahl - (tl.rueckrufe.length - rueckrufe.length));
  const ib = erfassen ? d.infoblatt : null;
  const offeneScans = scans.data?.offen ?? 0;
  const luecken = LUECKEN.filter((l) => tl.fehlende_angaben[l.art] > 0);
  const kaestchen = (t: Termin) => darfBei("eintraege_erfassen", { ist_test: t.patient_ist_test }) ? (
    <label className="flex items-center gap-1.5 text-[0.8125rem] cursor-pointer shrink-0 min-h-11">
      <input type="checkbox" className="!w-5 !h-5" aria-label={`Erledigt: ${t.patient_name}, ${t.titel}`}
        checked={weg.includes(t.id)} disabled={weg.includes(t.id)} onChange={() => abhaken.mutate(t)} />erledigt
    </label>
  ) : null;

  const punkte: ReactNode[] = [];
  if (heute.length) {
    const praxis = heute.filter((t) => t.art === "praxistermin").length;
    punkte.push(
      <Punkt key="heute" icon="kalender" testid="tl-termine" anzahl={heute.length}
        text={mehrzahl(heute.length, "Termin heute", "Termine heute")}
        unter={praxis ? `davon ${mehrzahl(praxis, "Praxistermin", "Praxistermine")}` : undefined}>
        {heute.slice(0, HOECHSTENS).map((t) => <TerminZeile key={t.id} t={t} aktion={kaestchen(t)} />)}
        <Weitere n={heute.length - HOECHSTENS} zu="/kalender?ansicht=woche" text="im Kalender" />
      </Punkt>,
    );
  }
  if (rueckrufAnzahl) {
    punkte.push(
      <Punkt key="rueckrufe" icon="telefon" art={tl.rueckrufe_ueberfaellig ? "fehler" : "warn"} testid="tl-rueckrufe" anzahl={rueckrufAnzahl}
        text={<>{rueckrufAnzahl} {rueckrufAnzahl === 1 ? <>Rückruf oder <Begriff name="wiedervorlage">Wiedervorlage</Begriff></>
          : <>Rückrufe und <Begriff name="wiedervorlage">Wiedervorlagen</Begriff></>} fällig</>}
        unter={tl.rueckrufe_ueberfaellig ? `davon ${tl.rueckrufe_ueberfaellig} überfällig` : "heute fällig"}>
        {rueckrufe.slice(0, HOECHSTENS).map((t) => <TerminZeile key={t.id} t={t} zeit="datum" aktion={kaestchen(t)} />)}
        <Weitere n={rueckrufAnzahl - Math.min(rueckrufe.length, HOECHSTENS)} zu="/kalender?ansicht=liste" text="im Kalender" />
      </Punkt>,
    );
  }
  if (ib) {
    const praxis = ib.ort?.wert.replace(/\bDr\.\s*/, "") ?? "Praxis";
    punkte.push(
      <Punkt key="infoblatt" icon="mail" art="warn" testid="infoblatt-hinweis"
        text={`${praxis} informieren: ${mehrzahl(ib.anzahl, "Termin", "Termine")} vom ${datum(ib.von).slice(0, 6)} bis ${datum(ib.bis)}`}
        unter={`${ib.rhythmus === "monat" ? "Das Infoblatt für den nächsten Monat" : "Das Infoblatt für die nächste Woche"} ist noch nicht erstellt.${
          ib.ohne_ort ? ` Bei ${mehrzahl(ib.ohne_ort, "Termin", "Terminen")} fehlt noch der Ort.` : ""}`}
        aktion={<Knopf variante="pri" icon="mail" className="min-h-11 px-5" onClick={() => setInfoblatt(true)}>Infoblatt erstellen</Knopf>} />,
    );
  }
  if (erfassen && tl.bestaetigung_fehlt.length) {
    const n = tl.bestaetigung_fehlt.length;
    punkte.push(
      <Punkt key="bestaetigung" icon="mail" testid="tl-bestaetigung" anzahl={n}
        text={`Terminbestätigung fehlt bei ${mehrzahl(n, "Praxistermin", "Praxisterminen")}`} unter="in den nächsten zwei Wochen">
        {tl.bestaetigung_fehlt.slice(0, HOECHSTENS).map((t) => (
          <TerminZeile key={t.id} t={t} zeit="datum" aktion={
            <Knopf klein icon="mail" onClick={() => setBestaetigen(t)} aria-label={`Bestätigung vorbereiten: ${t.patient_name}`}>
              Bestätigung vorbereiten</Knopf>} />
        ))}
        <Weitere n={n - HOECHSTENS} zu="/kalender?ansicht=liste" text="im Kalender" />
      </Punkt>,
    );
  }
  if (tl.kontakt_ueberfaellig) {
    punkte.push(
      <Punkt key="kontakt" icon="sprechblase" art="fehler" testid="tl-kontakt" anzahl={tl.kontakt_ueberfaellig}
        text={`${mehrzahl(tl.kontakt_ueberfaellig, "Patient", "Patienten")} ohne Kontakt seit über ${tl.kontakt_monate} Monaten`}
        unter={<><Begriff name="wiedereinbestellung">Wiedereinbestellung</Begriff> fällig: kein Termin geplant – anrufen oder Termin anlegen</>}
        aktion={<KnopfLink klein to="/patienten?pruefen=wiedereinbestellung" aria-label="Wiedereinbestellung: zur Patientenliste">
          Zur Liste</KnopfLink>} />,
    );
  }
  if (tl.plaene_pruefen) {
    punkte.push(
      <Punkt key="plaene" icon="tropfen" testid="tl-plaene" anzahl={tl.plaene_pruefen} zu="/infusionsplaene?gruppe=entwuerfe"
        text={`${mehrzahl(tl.plaene_pruefen, "Infusionsplan", "Infusionspläne")} zur Prüfung`} unter="Entwürfe, die auf die Freigabe warten" />,
    );
  }
  if (offeneScans) {
    punkte.push(
      <Punkt key="scans" icon="scan" testid="tl-scans" anzahl={offeneScans} zu="/scans"
        text={`${mehrzahl(offeneScans, "Scan wartet", "Scans warten")} auf Zuordnung`} unter="einer Akte zuordnen oder löschen" />,
    );
  }
  if (erfassen && tl.ohne_ort.length) {
    const n = tl.ohne_ort.length;
    punkte.push(
      <Punkt key="ort" icon="warnung" art="warn" testid="tl-ohne-ort" anzahl={n}
        text={`${mehrzahl(n, "Praxistermin", "Praxistermine")} ohne Ort`} unter="fehlen sonst auf dem Infoblatt an die Praxis">
        {tl.ohne_ort.slice(0, HOECHSTENS).map((t) => (
          <TerminZeile key={t.id} t={t} zeit="datum" aktion={
            <Knopf klein icon="stift" onClick={() => setOrtTermin(t)} aria-label={`Ort eintragen: ${t.patient_name}`}>Ort eintragen</Knopf>} />
        ))}
        <Weitere n={n - HOECHSTENS} zu="/kalender?ansicht=liste" text="im Kalender" />
      </Punkt>,
    );
  }
  for (const l of luecken) {
    const n = tl.fehlende_angaben[l.art];
    punkte.push(
      <Punkt key={l.art} icon="info" testid={`tl-luecke-${l.art}`} anzahl={n} zu={`/patienten?pruefen=${l.filter}`}
        text={l.text(n, tl.gewicht_fehlt_monate)} unter="fehlende Angabe in der Akte nachtragen" />,
    );
  }

  return (
    <section className="card px-5 pt-4 pb-2 flex flex-col" aria-labelledby="heute-zu-tun" data-testid="heute-zu-tun">
      <div className="flex items-center justify-between gap-3 flex-wrap pb-1">
        <h2 id="heute-zu-tun" className="m-0 text-[1.0625rem] font-semibold flex items-center gap-2">
          Heute zu tun {punkte.length ? <Chip art="akzent" className="num" data-testid="heute-zu-tun-anzahl">{punkte.length}</Chip> : null}
        </h2>
        {punkte.length ? <span className="text-[0.8125rem] gedaempft">Wichtigstes zuerst · ein Klick führt hin</span> : null}
      </div>
      {punkte.length ? <ul className="m-0 p-0 list-none">{punkte}</ul> : (
        <p className="m-0 py-3 flex items-center gap-2.5 text-[0.9375rem]" data-testid="heute-zu-tun-leer">
          <span className="w-8 h-8 rounded-full flex items-center justify-center bg-ok-bg text-ok"><Icon name="haken" groesse={16} /></span>
          Für heute ist alles erledigt.
        </p>
      )}
      {ib ? <AnkuendigungDialog offen={infoblatt} onOffen={setInfoblatt} von={ib.von} bis={ib.bis} rhythmus={ib.rhythmus} /> : null}
      <BestaetigungDialog termin={bestaetigen} offen={!!bestaetigen} onOffen={(o) => { if (!o) setBestaetigen(null); }} />
      {erfassen ? <TerminDialog offen={!!ortTermin} onOffen={(o) => { if (!o) setOrtTermin(null); }} termin={ortTermin} mitAkte /> : null}
    </section>
  );
}
