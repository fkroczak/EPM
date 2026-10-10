/**
 * Entwurf 2 · Startseite (S01–S14, S17): Kennzahlen, Kacheln im festen Raster (1×1, 2×1, 1×2, 2×2; 1/2/3/4/5 Spalten
 * je Fensterbreite), „Startseite anpassen“ mit Ziehen und Einrasten, Schnellerfassung, Kacheln der Administration.
 * Größe, Reihenfolge und Sichtbarkeit je Person (PATCH /api/auth/ich/ {startseite}).
 */
import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import { datum, langesDatum, relativ, zahl } from "@/lib/format";
import { RASTER_SPALTEN, useStufe } from "@/lib/stufen";
import type { Ich, Karte, KartenId, Recht, ScansStand } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Fehleranzeige, Karte as KarteBox, Knopf, KnopfLink, Laden, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { verschiebe } from "@/components/ui/sortierbar";
import { Icon } from "@/components/ui/icon";
import { TerminDialog } from "@/components/TerminDialog";
import { AnkuendigungDialog } from "@/components/AnkuendigungDialog";
import { GewichtDialog, KontaktDialog } from "@/components/Schnellerfassung";
import type { Vorgabe } from "@/components/Schnellerfassung";
import type { Startdaten } from "./start/daten";
import { AktivKachel, GewichtKachel, MeineKachel, PlaeneKachel, PruefenKachel, TermineKachel, WiederKachel } from "./start/kacheln";
import { AngemeldetKachel, HinweisKachel, KontenKachel, ServerKachel, SicherungKachel, TestKachel, UpdatesKachel, ZugriffeKachel,
  useKonten } from "./start/admin";

/** Titel und nötiges Recht je Kachel (ohne Recht erscheint sie weder auf der Seite noch unter „Ausgeblendet“) */
const KACHELN: Record<KartenId, { titel: string; recht: Recht }> = {
  termine: { titel: "Termine und Wiedervorlagen", recht: "akten_lesen" },
  wieder: { titel: "Wiedereinbestellung fällig", recht: "akten_lesen" },
  meine: { titel: "Meine Akten", recht: "akten_lesen" },
  gewicht: { titel: "Auffällige Gewichte", recht: "akten_lesen" },
  plaene: { titel: "Infusionspläne", recht: "akten_lesen" },
  pruefen: { titel: "Nach und nach prüfen", recht: "akten_lesen" },
  aktiv: { titel: "Zuletzt eingetragen", recht: "akten_lesen" },
  sicherung: { titel: "Datensicherung", recht: "backup_verwalten" },
  server: { titel: "Server", recht: "system_verwalten" },
  updates: { titel: "Ubuntu-Updates", recht: "system_verwalten" },
  konten: { titel: "Konten", recht: "benutzer_verwalten" },
  angemeldet: { titel: "Angemeldet", recht: "system_verwalten" },
  hinweis: { titel: "Hinweis an alle", recht: "system_verwalten" },
  zugriffe: { titel: "Zugriffe · 7 Tage", recht: "audit_lesen" },
  testumgebung: { titel: "Testumgebung", recht: "testdaten_zuruecksetzen" },
};
const GROESSEN: [1 | 2, 1 | 2][] = [[1, 1], [2, 1], [1, 2], [2, 2]];

/** Kopfzeile wie im Entwurf: „Backup heute 02:00 erfolgreich“; sonst der wichtigste Hinweis. Mit dem Recht
 *  „Sicherungen verwalten“ führt der Chip zur Seite Backup. */
function BackupStatus({ s, verweis }: { s: Startdaten["sicherung"]; verweis: boolean }) {
  const ok = s.zustand === "ok";
  const text = ok ? `Backup ${relativ(s.letzte_am, true).replace(", ", " ")} erfolgreich` : s.titel || "Backup-Status fehlt";
  const art = ok ? "ok" : s.zustand === "warnung" ? "warn" : s.zustand === "unbekannt" ? undefined : "fehler";
  const inhalt = <><Icon name={ok ? "haken" : "warnung"} groesse={14} />{text}</>;
  const titel = ok ? undefined : s.hinweise.join(" ");
  return verweis ? (
    <Link to="/admin/backup" className={cx("chip h-7 no-underline", art)} title={titel} data-testid="backup-status">{inhalt}</Link>
  ) : (
    <Chip art={art} className="h-7" title={titel} data-testid="backup-status">{inhalt}</Chip>
  );
}

// ---------------------------------------------------------------- Scans (F165): warten auf Zuordnung, laufen ab, Speicher
/** „Praxis Holtmeier informieren: 5 Termine vom … bis …“ mit großem Knopf, der das Infoblatt für genau diesen Zeitraum öffnet */
function InfoblattHinweis({ h }: { h: NonNullable<Startdaten["infoblatt"]> }) {
  const [offen, setOffen] = useState(false);
  const praxis = h.ort?.wert.replace(/\bDr\.\s*/, "") ?? "Praxis";
  const kurz = (iso: string) => datum(iso).slice(0, 6);
  return (
    <div role="status" className="meldung info flex items-center gap-x-4 gap-y-2.5 flex-wrap" data-testid="infoblatt-hinweis">
      <Icon name="mail" groesse={22} />
      <span className="grow min-w-[14rem] flex flex-col gap-0.5">
        <strong className="text-base">{praxis} informieren: {h.anzahl} {h.anzahl === 1 ? "Termin" : "Termine"} vom {kurz(h.von)} bis {datum(h.bis)}</strong>
        <span className="text-[0.8125rem]">
          {h.rhythmus === "monat" ? "Das Infoblatt für den nächsten Monat ist noch nicht erstellt." : "Das Infoblatt für die nächste Woche ist noch nicht erstellt."}
          {h.ohne_ort ? ` Bei ${h.ohne_ort} ${h.ohne_ort === 1 ? "Termin" : "Terminen"} fehlt noch der Ort.` : ""}
        </span>
      </span>
      <Knopf variante="pri" icon="mail" className="min-h-11 px-5" onClick={() => setOffen(true)}>Infoblatt erstellen</Knopf>
      <AnkuendigungDialog offen={offen} onOffen={setOffen} von={h.von} bis={h.bis} rhythmus={h.rhythmus} />
    </div>
  );
}

function ScansHinweis() {
  const { darf } = useAuth();
  const stand = useQuery({
    queryKey: ["scans", "stand"],
    queryFn: () => api<ScansStand>("scans/stand/"),
    enabled: darf("scans_bearbeiten"),
    staleTime: 30_000,
  });
  const s = stand.data;
  if (!s || (!s.offen && !s.laeuft_bald_ab && s.prozent < 80)) return null;
  const teile = [
    s.offen ? `${s.offen === 1 ? "1 Scan wartet" : `${s.offen} Scans warten`} auf Zuordnung` : "",
    s.laeuft_bald_ab ? `${s.laeuft_bald_ab === 1 ? "1 Scan wird" : `${s.laeuft_bald_ab} Scans werden`} in 24 Stunden automatisch gelöscht` : "",
    s.prozent >= 80 ? `Speicher für Scans zu ${String(s.prozent).replace(".", ",")} % belegt` : "",
  ].filter(Boolean);
  return (
    <div role="status" className={cx("meldung flex items-center gap-2.5", s.laeuft_bald_ab || s.prozent >= 80 ? "warn" : "info")}
      data-testid="scans-hinweis">
      <Icon name="scan" groesse={18} />
      <span className="grow">{teile.join(" · ")}.</span>
      <Link to="/scans" className="font-medium whitespace-nowrap">Zu den Scans</Link>
    </div>
  );
}

// ---------------------------------------------------------------- Kennzahlenleiste (S01, SU8)
function Kennzahl({ titel, wert, unter, zu, testid }: { titel: string; wert: ReactNode; unter: ReactNode; zu: string; testid: string }) {
  return (
    <Link to={zu} className="flex flex-col gap-1 px-5 py-1 no-underline text-tinte min-w-0 border-rand schmal:border-l schmal:first:border-l-0"
      data-testid={testid}>
      <span className="text-[0.8125rem] gedaempft">{titel}</span>
      <span className="num text-2xl font-semibold leading-tight">{wert}</span>
      <span className="text-[0.78125rem] gedaempft">{unter}</span>
    </Link>
  );
}

function Kennzahlen({ d }: { d?: Startdaten }) {
  if (!d) {
    return (
      <section aria-label="Kennzahlen" aria-busy="true" className="card grid grid-cols-2 schmal:grid-cols-5 gap-y-3 py-4" data-testid="kennzahlen-laden">
        {["In Betreuung", "Mit offenem Termin", "Termine in 7 Tagen", "Kontakt fällig", "Termine überfällig"].map((t) => (
          <div key={t} className="flex flex-col gap-1 px-5 py-1 min-w-0 border-rand schmal:border-l schmal:first:border-l-0">
            <span className="text-[0.8125rem] gedaempft">{t}</span>
            <span className="num text-2xl font-semibold leading-tight gedaempft">–</span>
            <span className="text-[0.78125rem] gedaempft">{t === "Kontakt fällig" ? <span className="chip invisible">…</span> : "\u00a0"}</span>
          </div>
        ))}
      </section>
    );
  }
  const z = d.zahlen;
  const anteil = z.in_betreuung ? Math.round((100 * z.mit_offenem_termin) / z.in_betreuung) : 0;
  return (
    <section aria-label="Kennzahlen" className="card grid grid-cols-2 schmal:grid-cols-5 gap-y-3 py-4" data-testid="kennzahlenleiste">
      <Kennzahl titel="In Betreuung" wert={zahl(z.in_betreuung)} unter="ohne Testpatienten" zu="/patienten" testid="kz-in-betreuung" />
      <Kennzahl titel="Mit offenem Termin" wert={zahl(z.mit_offenem_termin)} unter={`${anteil} % der Betreuten`} zu="/kalender?ansicht=liste"
        testid="kz-offener-termin" />
      <Kennzahl titel="Termine in 7 Tagen" wert={zahl(z.termine_7_tage)} unter={`davon ${z.praxistermine_7_tage} Praxistermine`}
        zu="/kalender?ansicht=woche" testid="kz-termine-7" />
      <Kennzahl titel="Kontakt fällig" testid="kz-kontakt" zu="/patienten?pruefen=wiedereinbestellung"
        wert={<>{z.kontakt_ueberfaellig} <span className="text-[0.9375rem] font-medium gedaempft">+ {z.kontakt_bald} bald</span></>}
        unter={<span className="flex gap-1 flex-wrap"><Chip art="fehler">über {d.wiedereinbestellung.ueberfaellig_monate} Mon.</Chip>
          <Chip art="warn">{d.wiedereinbestellung.bald_monate}–{d.wiedereinbestellung.ueberfaellig_monate} Mon.</Chip></span>} />
      <Kennzahl titel="Termine überfällig" wert={zahl(z.termine_ueberfaellig)} unter={z.termine_ueberfaellig ? "offen, Datum vorbei" : "keine"}
        zu="/kalender" testid="kz-ueberfaellig" />
    </section>
  );
}

// ---------------------------------------------------------------- Startseite anpassen (S11, S17)
type Zug = { art: "verschieben"; id: KartenId; ziel: KartenId | null }
  | { art: "groesse"; id: KartenId; breite: 1 | 2; hoehe: 1 | 2; links: number; oben: number; zelleB: number; zelleH: number; abstand: number };

function useKartenSpeichern() {
  const ich = useIch();
  const { setIch } = useAuth();
  const melden = useHinweis();
  /** ``karten: []`` setzt auf den Standard der Rolle zurück; ohne ``karten`` bleiben die Kacheln unverändert */
  return (startseite: { karten?: Karte[]; notfallhinweis_bei?: number; zweifaktorhinweis_aus?: boolean }) => {
    const vorher: Ich = ich;
    if (startseite.karten?.length || startseite.notfallhinweis_bei !== undefined || startseite.zweifaktorhinweis_aus !== undefined) {
      setIch({ ...ich, startseite: { ...ich.startseite, ...(startseite.karten?.length ? { karten: startseite.karten } : {}),
        ...(startseite.notfallhinweis_bei !== undefined ? { notfallhinweis_bei: startseite.notfallhinweis_bei } : {}),
        ...(startseite.zweifaktorhinweis_aus !== undefined ? { zweifaktorhinweis_aus: startseite.zweifaktorhinweis_aus } : {}) } });
    }
    api<Ich>("auth/ich/", { method: "PATCH", body: { startseite } })
      .then((antwort) => setIch(antwort))
      .catch((e: Error) => { setIch(vorher); melden(`Startseite nicht gespeichert: ${e.message}`, "fehler"); });
  };
}

function Bearbeitungsleiste({ karte, titel, spalten, onGroesse, onAusblenden, griff }: {
  karte: Karte; titel: string; spalten: number; onGroesse: (b: 1 | 2, h: 1 | 2) => void; onAusblenden: () => void;
  griff: { onPointerDown: (e: PointerEvent<HTMLButtonElement>) => void; onPointerMove: (e: PointerEvent<HTMLButtonElement>) => void;
    onPointerUp: (e: PointerEvent<HTMLButtonElement>) => void; onKeyDown: (e: KeyboardEvent<HTMLButtonElement>) => void };
}) {
  return (
    <div className="absolute top-2.5 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 p-1 rounded-[0.625rem] bg-flaeche border border-rand shadow-md"
      data-testid={`leiste-${karte.id}`}>
      <button type="button" className="btn icon klein geist cursor-grab touch-none" data-griff={karte.id}
        aria-label={`${titel} verschieben (Pfeiltasten; Umschalt + Pfeiltasten: Größe)`} title="Ziehen oder mit Pfeiltasten verschieben"
        {...griff}><Icon name="griff" groesse={16} /></button>
      <div role="group" aria-label={`Größe ${titel}`} className="segmente">
        {GROESSEN.map(([b, h]) => (
          <button key={`${b}${h}`} type="button" className="segment !px-2" aria-pressed={karte.breite === b && karte.hoehe === h}
            disabled={b > spalten} onClick={() => onGroesse(b, h)}>{b}×{h}</button>
        ))}
      </div>
      <button type="button" className="btn icon klein geist" aria-label={`${titel} ausblenden`} title="Ausblenden" onClick={onAusblenden}>
        <Icon name="auge_zu" groesse={16} /></button>
    </div>
  );
}

function AnpassenBanner({ ausgeblendet, onEinblenden, onStandard, onFertig, spalten }: {
  ausgeblendet: Karte[]; onEinblenden: (id: KartenId) => void; onStandard: () => void; onFertig: () => void; spalten: number;
}) {
  return (
    <div className="flex items-start justify-between gap-4 flex-wrap px-[1.125rem] py-3.5 rounded-[0.875rem] bg-akzent-weich text-akzent-text border border-akzent/30"
      data-testid="anpassen">
      <div className="flex flex-col gap-1 max-w-[110ch]">
        <h2 className="m-0 text-[0.9375rem] font-semibold">Startseite anpassen</h2>
        <span className="text-[0.84375rem] leading-normal text-text2">Kachel am Griff ziehen = verschieben · an der Ecke unten rechts ziehen =
          vergrößern, rastet in 1×1, 2×1, 1×2 und 2×2 ein · Tastatur: Griff wählen, Pfeiltasten verschieben, Umschalt + Pfeiltasten Größe.
          Gilt nur für dich. Fenster jetzt: {spalten} {spalten === 1 ? "Spalte" : "Spalten"} (unter 900 px 1, bis 1439 px 2, bis 1919 px 3,
          bis 2559 px 4, ab 2560 px 5).</span>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        {ausgeblendet.length ? <span className="text-[0.8125rem] text-text2">Ausgeblendet:</span> : null}
        {ausgeblendet.map((k) => (
          <Knopf key={k.id} klein icon="plus" onClick={() => onEinblenden(k.id)} aria-label={`${KACHELN[k.id].titel} einblenden`}>
            {KACHELN[k.id].titel}</Knopf>
        ))}
        <Knopf klein variante="geist" onClick={onStandard}>Standard</Knopf>
        <Knopf klein variante="pri" onClick={onFertig}>Fertig</Knopf>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Seite
export function Start() {
  const ich = useIch();
  const { darf } = useAuth();
  const stufe = useStufe();
  const spalten = RASTER_SPALTEN[stufe];
  const [bearbeiten, setBearbeiten] = useState(false);
  const [zug, setZug] = useState<Zug | null>(null);
  const [ansage, setAnsage] = useState("");
  const [dialog, setDialog] = useState<null | "kontakt" | "gewicht" | "termin">(null);
  const [vorgabe, setVorgabe] = useState<Vorgabe | null>(null);
  const raster = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const speichern = useKartenSpeichern();
  useEffect(() => {
    if ((location.state as { anpassen?: number } | null)?.anpassen) setBearbeiten(true); // „Startseite anpassen“ aus Mein Konto
  }, [location.state]);
  const lesen = darf("akten_lesen");
  const daten = useQuery({ queryKey: ["startseite"], queryFn: () => api<Startdaten>("startseite/"), enabled: lesen });
  const konten = useKonten(darf("benutzer_verwalten"));
  const d = daten.data;
  const erfassen = darf("eintraege_erfassen");

  const karten = ich.startseite.karten;
  const erlaubt = (k: Karte) => darf(KACHELN[k.id].recht);
  const sichtbar = karten.filter((k) => k.sichtbar && erlaubt(k));
  const ausgeblendet = karten.filter((k) => !k.sichtbar && erlaubt(k));

  const aendern = (id: KartenId, aenderung: Partial<Karte>) => speichern({ karten: karten.map((k) => (k.id === id ? { ...k, ...aenderung } : k)) });
  const fokus = (id: KartenId) => window.requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-griff="${id}"]`)?.focus());
  const verschieben = (id: KartenId, ziel: KartenId) => {
    const von = karten.findIndex((k) => k.id === id), nach = karten.findIndex((k) => k.id === ziel);
    if (von < 0 || nach < 0 || von === nach) return;
    speichern({ karten: verschiebe(karten, von, nach) });
  };

  const griff = (k: Karte) => ({
    onPointerDown: (e: PointerEvent<HTMLButtonElement>) => {
      if (e.button !== 0) return;
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);
      setZug({ art: "verschieben", id: k.id, ziel: null });
    },
    onPointerMove: (e: PointerEvent<HTMLButtonElement>) => {
      if (zug?.art !== "verschieben" || zug.id !== k.id) return;
      const unter = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>("[data-kachel]");
      const ziel = (unter?.dataset.kachel as KartenId | undefined) ?? null;
      if (ziel !== zug.ziel) setZug({ ...zug, ziel: ziel === k.id ? null : ziel });
    },
    onPointerUp: () => {
      if (zug?.art === "verschieben" && zug.id === k.id && zug.ziel) {
        verschieben(k.id, zug.ziel);
        setAnsage(`${KACHELN[k.id].titel} verschoben.`);
      }
      setZug(null);
    },
    onKeyDown: (e: KeyboardEvent<HTMLButtonElement>) => {
      const titel = KACHELN[k.id].titel;
      if (e.shiftKey && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)) {
        e.preventDefault();
        const breite = e.key === "ArrowRight" ? 2 : e.key === "ArrowLeft" ? 1 : k.breite;
        const hoehe = e.key === "ArrowDown" ? 2 : e.key === "ArrowUp" ? 1 : k.hoehe;
        if (breite !== k.breite || hoehe !== k.hoehe) {
          aendern(k.id, { breite, hoehe });
          setAnsage(`${titel}: ${breite} × ${hoehe}`);
        }
        fokus(k.id);
        return;
      }
      const zurueck = e.key === "ArrowLeft" || e.key === "ArrowUp";
      const vor = e.key === "ArrowRight" || e.key === "ArrowDown";
      if (!zurueck && !vor) return;
      e.preventDefault();
      const i = sichtbar.findIndex((x) => x.id === k.id);
      const nachbar = sichtbar[zurueck ? i - 1 : i + 1];
      if (!nachbar) return;
      verschieben(k.id, nachbar.id);
      setAnsage(`${titel}: Position ${zurueck ? i : i + 2} von ${sichtbar.length}`);
      fokus(k.id);
    },
  });

  /** Ecke unten rechts: Größe ziehen, rastet in ganzen Rasterzellen ein (höchstens 2 × 2) */
  const ecke = (k: Karte) => ({
    onPointerDown: (e: PointerEvent<HTMLDivElement>) => {
      if (e.button !== 0 || !raster.current) return;
      e.preventDefault();
      e.stopPropagation();
      e.currentTarget.setPointerCapture(e.pointerId);
      const stil = getComputedStyle(raster.current);
      const spalt = parseFloat(stil.columnGap);
      const abstand = Number.isNaN(spalt) ? 20 : spalt;
      const zelleB = (raster.current.clientWidth - (spalten - 1) * abstand) / spalten;
      const zelleH = parseFloat(stil.gridAutoRows) || 300;
      const kachel = e.currentTarget.closest<HTMLElement>("[data-kachel]")!.getBoundingClientRect();
      const r = raster.current.getBoundingClientRect();
      setZug({ art: "groesse", id: k.id, breite: Math.min(k.breite, spalten) as 1 | 2, hoehe: k.hoehe, links: kachel.left - r.left,
        oben: kachel.top - r.top, zelleB, zelleH, abstand });
    },
    onPointerMove: (e: PointerEvent<HTMLDivElement>) => {
      if (zug?.art !== "groesse" || zug.id !== k.id || !raster.current) return;
      const r = raster.current.getBoundingClientRect();
      const b = Math.round((e.clientX - r.left - zug.links + zug.abstand) / (zug.zelleB + zug.abstand));
      const h = Math.round((e.clientY - r.top - zug.oben + zug.abstand) / (zug.zelleH + zug.abstand));
      const breite = Math.min(Math.max(b, 1), Math.min(2, spalten)) as 1 | 2;
      const hoehe = Math.min(Math.max(h, 1), 2) as 1 | 2;
      if (breite !== zug.breite || hoehe !== zug.hoehe) setZug({ ...zug, breite, hoehe });
    },
    onPointerUp: () => {
      if (zug?.art === "groesse" && zug.id === k.id && (zug.breite !== Math.min(k.breite, spalten) || zug.hoehe !== k.hoehe)) {
        aendern(k.id, { breite: zug.breite, hoehe: zug.hoehe });
        setAnsage(`${KACHELN[k.id].titel}: ${zug.breite} × ${zug.hoehe}`);
      }
      setZug(null);
    },
  });

  const oeffne = (art: "kontakt" | "gewicht" | "termin", v: Vorgabe | null = null) => { setVorgabe(v); setDialog(art); };
  const inhalt = (k: Karte): ReactNode => {
    const breit = Math.min(k.breite, spalten) === 2;
    if (["sicherung", "server", "updates", "konten", "angemeldet", "hinweis", "zugriffe", "testumgebung"].includes(k.id)) {
      return k.id === "sicherung" ? <SicherungKachel /> : k.id === "server" ? <ServerKachel /> : k.id === "updates" ? <UpdatesKachel />
        : k.id === "konten" ? <KontenKachel /> : k.id === "angemeldet" ? <AngemeldetKachel /> : k.id === "hinweis" ? <HinweisKachel />
        : k.id === "zugriffe" ? <ZugriffeKachel /> : <TestKachel />;
    }
    if (k.id === "meine") return <MeineKachel />;
    if (!d) return daten.error ? <div className="p-5"><Fehleranzeige fehler={daten.error} /></div> : <Laden />;
    switch (k.id) {
      case "termine": return <TermineKachel daten={d} breit={breit} />;
      case "wieder": return <WiederKachel daten={d} onKontakt={(v) => oeffne("kontakt", v)} onTermin={(v) => oeffne("termin", v)} />;
      case "gewicht": return <GewichtKachel daten={d} />;
      case "plaene": return <PlaeneKachel daten={d} />;
      case "pruefen": return <PruefenKachel daten={d} />;
      default: return <AktivKachel daten={d} breit={breit} />;
    }
  };

  // S08: Hinweis „Nur noch n Notfall-Codes übrig“ (ausgeblendet bis weniger übrig sind)
  const codes = d?.notfallcodes;
  const codesHinweis = codes && codes.eingerichtet && codes.uebrig <= codes.warnen_ab
    && !(ich.startseite.notfallhinweis_bei != null && codes.uebrig >= ich.startseite.notfallhinweis_bei);
  const gesperrt = (konten.data ?? []).filter((k) => k.probleme.includes("gesperrt") && /Fehlversuche/.test(k.sperrgrund));
  const verwaltung = ich.rolle === "admin";

  return (
    <Seite pfad={[{ text: "Start" }]}>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-[1.375rem] sm:text-[1.625rem] font-semibold">{langesDatum()}</h1>
          {verwaltung && ich.schreibt_nur_testpatienten ? (
            <span className="text-sm gedaempft">Administration · echte Akten sind für dich nur lesbar</span>
          ) : d ? (
            <span className="text-sm gedaempft" data-testid="start-zahlen">
              <span className="num">{d.termine.heute.length}</span> offene Termine heute · <span className="num">{d.termine.ueberfaellig.length}</span> überfällig
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-2.5 flex-wrap">
          {d?.sicherung ? <BackupStatus s={d.sicherung} verweis={darf("backup_verwalten")} />
            : daten.isLoading ? <Chip className="h-7 invisible" aria-hidden="true">Backup-Status wird geladen</Chip> : null}
          {erfassen && lesen ? <>
            <Knopf variante="pri" icon="telefon" onClick={() => oeffne("kontakt")}>Kontakt erfassen</Knopf>
            <Knopf icon="waage" onClick={() => oeffne("gewicht")}>Gewicht</Knopf>
            <Knopf icon="kalender" onClick={() => oeffne("termin")}>Termin</Knopf>
          </> : null}
          {darf("benutzer_verwalten") && verwaltung ? <KnopfLink to="/admin/benutzer?neu=1" icon="benutzer">Benutzer anlegen</KnopfLink> : null}
          <Knopf variante="geist" icon="stift" onClick={() => setBearbeiten((b) => !b)} aria-expanded={bearbeiten}>Startseite anpassen</Knopf>
        </div>
      </div>

      {gesperrt.map((k) => (
        <div key={k.id} role="alert" className="meldung fehler flex items-center gap-2.5" data-testid="konto-gesperrt">
          <Icon name="warnung" groesse={18} />
          <span className="grow">Konto <strong>{k.benutzername}</strong> gesperrt: {k.sperrgrund}{k.gesperrt_am ? `, ${relativ(k.gesperrt_am, true)}` : ""}.</span>
          <Link to={`/admin/benutzer?id=${k.id}`} className="font-medium whitespace-nowrap text-fehler">Zum Benutzer</Link>
        </div>
      ))}
      <ScansHinweis />
      {ich.rolle === "keine" ? (
        <div role="status" className="meldung info flex items-center gap-2.5" data-testid="keine-berechtigung">
          <Icon name="info" groesse={18} />
          <span>Dein Konto hat die Rolle „Keine Berechtigung“: Du bist angemeldet, siehst aber keine Patientendaten. Rolle und Rechte vergibt die Administration.</span>
        </div>
      ) : null}
      {/* Zwei-Faktor-Anmeldung ist freiwillig (Fehlerliste 02.10.2026, 6.5): einmal darauf hinweisen, ausblendbar */}
      {!ich.zweiter_faktor && !ich.startseite.zweifaktorhinweis_aus ? (
        <div role="status" className="meldung info flex items-center gap-2.5" data-testid="zweifaktor-hinweis">
          <Icon name="schloss" groesse={18} />
          <span className="grow">Dein Konto ist nur mit dem Passwort geschützt. Die Zwei-Faktor-Anmeldung (Code aus einer Authenticator-App) ist freiwillig
            und in zwei Minuten eingerichtet.</span>
          <Link to="/konto#zwei-faktor" className="font-medium whitespace-nowrap">Jetzt einrichten</Link>
          <button type="button" className="btn icon geist klein" aria-label="Hinweis zur Zwei-Faktor-Anmeldung ausblenden"
            onClick={() => speichern({ zweifaktorhinweis_aus: true })}><Icon name="x" /></button>
        </div>
      ) : null}
      {/* Infoblatt an die Praxis (F177): rechtzeitig vor der nächsten Woche bzw. dem nächsten Monat, bis es erstellt ist */}
      {erfassen && d?.infoblatt ? <InfoblattHinweis h={d.infoblatt} /> : null}
      {codesHinweis && codes ? (
        <div role="status" className="meldung warn flex items-center gap-2.5" data-testid="notfallcodes-hinweis">
          <Icon name="warnung" groesse={18} />
          <span className="grow">{codes.uebrig ? <>Nur noch <strong>{codes.uebrig} von {codes.gesamt}</strong> Notfall-Codes übrig.</>
            : <>Keine Notfall-Codes mehr übrig.</>} Ohne Codes ist bei Verlust des Telefons keine Anmeldung möglich.</span>
          <Link to="/konto" state={{ sicherheit: Date.now() }} className="font-medium whitespace-nowrap text-warn">Neue Codes erzeugen</Link>
          <button type="button" className="btn icon geist klein text-warn" aria-label="Hinweis zu den Notfall-Codes ausblenden"
            onClick={() => speichern({ notfallhinweis_bei: codes.uebrig })}><Icon name="x" /></button>
        </div>
      ) : null}

      {bearbeiten ? (
        <AnpassenBanner ausgeblendet={ausgeblendet} spalten={spalten} onFertig={() => setBearbeiten(false)}
          onEinblenden={(id) => { aendern(id, { sichtbar: true }); setAnsage(`${KACHELN[id].titel} eingeblendet.`); }}
          onStandard={() => { speichern({ karten: [] }); setAnsage("Standard wiederhergestellt."); }} />
      ) : null}
      <span className="sr-only" aria-live="polite">{ansage}</span>

      {/* beim Laden gleich hoch mit Platzhaltern, damit die Kacheln darunter nicht springen (Lighthouse 09.10.2026) */}
      {lesen && (d || daten.isLoading) ? <Kennzahlen d={d} /> : null}

      <div ref={raster} className="raster" data-testid="raster" data-spalten={spalten}>
        {sichtbar.map((k) => {
          const b = Math.min(k.breite, spalten);
          const zieht = zug?.art === "verschieben" && zug.id === k.id;
          return (
            <KarteBox key={k.id} className={cx("kachel", bearbeiten && "bearbeiten", zieht && "zieht",
              zug?.art === "verschieben" && zug.ziel === k.id && "ziel")}
              style={{ gridColumn: `span ${b}`, gridRow: `span ${k.hoehe}` }} aria-labelledby={`k-${k.id}`}
              data-kachel={k.id} data-groesse={`${b}x${k.hoehe}`}>
              <div className="contents" inert={bearbeiten || undefined}>{inhalt(k)}</div>
              {bearbeiten ? (
                <>
                  <div aria-hidden="true" className="absolute inset-0 rounded-[inherit] bg-grund/50 z-10" />
                  <Bearbeitungsleiste karte={k} titel={KACHELN[k.id].titel} spalten={spalten} griff={griff(k)}
                    onGroesse={(breite, hoehe) => { aendern(k.id, { breite, hoehe }); setAnsage(`${KACHELN[k.id].titel}: ${breite} × ${hoehe}`); }}
                    onAusblenden={() => { aendern(k.id, { sichtbar: false }); setAnsage(`${KACHELN[k.id].titel} ausgeblendet.`); }} />
                  <div aria-hidden="true" title="Größe ziehen" data-testid={`ecke-${k.id}`}
                    className="absolute right-1 bottom-1 z-20 w-5 h-5 flex items-center justify-center text-akzent-text cursor-nwse-resize touch-none"
                    {...ecke(k)}><Icon name="ecke" groesse={14} strokeWidth={2.2} /></div>
                </>
              ) : null}
            </KarteBox>
          );
        })}
        {zug?.art === "groesse" ? (
          <div aria-hidden="true" className="absolute z-30 rounded-[0.875rem] border-2 border-akzent bg-akzent/5 pointer-events-none flex items-end justify-end p-3"
            style={{ left: zug.links, top: zug.oben, width: zug.breite * zug.zelleB + (zug.breite - 1) * zug.abstand,
              height: zug.hoehe * zug.zelleH + (zug.hoehe - 1) * zug.abstand }}>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-akzent text-auf-akzent text-[0.8125rem] font-medium">
              <Icon name="ecke" groesse={14} />{zug.breite} × {zug.hoehe} · loslassen zum Einrasten</span>
          </div>
        ) : null}
      </div>
      {sichtbar.length === 0 ? (
        <KarteBox className="px-5 py-6 text-sm gedaempft text-center">Alle Kacheln sind ausgeblendet. Unter „Startseite anpassen“ lassen sie sich wieder einblenden.</KarteBox>
      ) : null}

      {erfassen ? <>
        <KontaktDialog offen={dialog === "kontakt"} onOffen={(o) => setDialog(o ? "kontakt" : null)} vorgabe={vorgabe} />
        <GewichtDialog offen={dialog === "gewicht"} onOffen={(o) => setDialog(o ? "gewicht" : null)} vorgabe={vorgabe} />
        <TerminDialog offen={dialog === "termin"} onOffen={(o) => setDialog(o ? "termin" : null)} patientId={vorgabe?.id} patientName={vorgabe?.name} />
      </> : null}
    </Seite>
  );
}
