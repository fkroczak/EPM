/**
 * Menü „Freigaben“ (16.11.2026): alles, was ein Mensch freigeben muss, an einer Stelle – Datenpflege-Vorschläge aus
 * dem Altbestand (vorbereitet von Regeln und nachts von der KI), Infusionsplan-Entwürfe und der Weg zur KI-Prüfung.
 *
 * Jeder Vorschlag zeigt den Ablauf: links die Stelle in der Akte (vorher, mit nummerierten Markierungen), daneben die
 * Schritte (abwählbar und bearbeitbar), unten die Akte vorher und nachher. „Freigeben“ setzt nicht sofort um: 60
 * Sekunden lang lässt sich die Freigabe mit einem Klick zurücknehmen, danach wird sie umgesetzt.
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { datum, zeitpunkt } from "@/lib/format";
import type { Anlass, ArztFeld, Arztdublette, ArztWerte, Datenpflege, Filter, FreigabenDaten, LaufendeFreigabe, PersonWerte, PlanEntwurf, Schritt } from "@/lib/freigaben";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Karte, KartenKopf, Knopf, KnopfLink, Laden, Leer, Meldung, Seitenkopf, Segmente, Textfeld, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Seite } from "@/components/layout/Shell";

const ROLLEN: Record<string, string> = {
  hausarzt: "Hausarzt", facharzt: "Facharzt", ueberweisend: "Überweisend", klinik: "Klinik", sonstige: "Sonstige",
};
const BEZIEHUNGEN = ["Ehefrau", "Ehemann", "Ehepartner/in", "Lebensgefährte/in", "Tochter", "Sohn", "Mutter", "Vater",
  "Schwester", "Bruder", "Betreuer/in", "Enkel/in", "Nachbar/in", "Freund/in", "Pflegedienst"];
const THEMEN: Record<string, string> = {
  telefon: "Telefon", hausarzt: "Hausarzt", ueberweisung_durch: "Überweisung durch",
  hinweise: "Hinweise aus der Altdaten-Übernahme", inaktiv: "Name mit „+“ / „INAKTIV“",
};
const ANLAESSE: { wert: Anlass; text: string; erklaerung: string }[] = [
  { wert: "verstorben", text: "Verstorben", erklaerung: "„+“ – der Patient ist verstorben" },
  { wert: "therapie_beendet", text: "Keine Betreuung mehr gewünscht", erklaerung: "Therapie beendet, möchte nicht mehr betreut werden" },
  { wert: "betreuung_gewechselt", text: "Betreuung gewechselt", erklaerung: "wird jetzt woanders betreut" },
];
const FILTER: { wert: Filter; text: string }[] = [
  { wert: "alle", text: "Alle" }, { wert: "eindeutig", text: "Eindeutig" }, { wert: "fragen", text: "Mit Frage" },
  { wert: "inaktiv", text: "„+“ / INAKTIV" },
];

function thema(s: Schritt): string {
  if (s.art === "abschluss" || (s.art === "feld" && (s.feld === "nachname" || s.feld === "vorname") && s.quelle !== "bemerkung")) return "inaktiv";
  if (s.art === "hinweis") {
    return s.titel.startsWith("Telefon") ? "telefon" : s.titel.startsWith("Hausarzt") ? "hausarzt"
      : s.titel.startsWith("Überweisung") ? "ueberweisung_durch" : "hinweise";
  }
  if (s.quelle === "bemerkung" || s.art === "kontakt") return "hinweise";
  return s.quelle === "telefon2" ? "telefon" : s.quelle;
}

function fehlerText(e: unknown): string {
  if (e instanceof ApiFehler && e.daten && typeof e.daten === "object") {
    return Object.values(e.daten as Record<string, unknown>).map(String).join(" ") || e.message;
  }
  return e instanceof Error ? e.message : String(e);
}

type Sammel = { gruppe: string; anzahl: number; mit_frage: number; uebersprungen: { id: number; patient: string; grund: string }[] };

export function Freigaben() {
  const [params, setParams] = useSearchParams();
  const patient = params.get("patient");
  const filter = (params.get("filter") as Filter | null) ?? "alle";
  const qc = useQueryClient();
  const melden = useHinweis();
  const q = useQuery({
    queryKey: ["freigaben", patient, filter],
    queryFn: () => api<FreigabenDaten>(`freigaben/?filter=${filter}${patient ? `&patient=${patient}` : ""}`),
    // läuft ein Countdown, alle 2 s nachsehen – sonst halbminütlich
    refetchInterval: (query) => (query.state.data?.laufend.some((l) => l.status === "wartet") ? 2000 : 30_000),
  });
  const suchen = useMutation({
    mutationFn: () => api<{ neu: number; dubletten: number }>("freigaben/suchen/", { body: patient ? { patient: Number(patient) } : {} }),
    onSuccess: (r) => {
      const teile = [r.neu ? `${r.neu} neue Vorschläge` : "", r.dubletten ? `${r.dubletten} mögliche doppelte Ärzte` : ""].filter(Boolean);
      melden(teile.length ? `${teile.join(" und ")} vorbereitet.` : "Keine neuen Vorschläge – alles aufgeräumt oder schon vorgeschlagen.", "ok");
      void qc.invalidateQueries({ queryKey: ["freigaben"] });
    },
    onError: (e) => melden(fehlerText(e), "fehler"),
  });
  const sammel = useMutation({
    mutationFn: () => api<Sammel>("freigaben/datenpflege/sammel/", { body: {} }),
    onSuccess: (r) => {
      melden(`${r.anzahl} Vorschläge freigegeben – 60 Sekunden zum Zurücknehmen.${r.uebersprungen.length ? ` ${r.uebersprungen.length} übersprungen (siehe unten).` : ""}`, "ok");
      void qc.invalidateQueries({ queryKey: ["freigaben"] });
    },
    onError: (e) => melden(fehlerText(e), "fehler"),
  });
  const d = q.data;
  const anzahl = d ? d.datenpflege.length + d.plaene.length + d.aerzte.length : 0;
  const eindeutige = d?.zahlen.eindeutig ?? 0;
  const setzeFilter = (f: Filter) => setParams((alt) => { const n = new URLSearchParams(alt); if (f === "alle") n.delete("filter"); else n.set("filter", f); return n; });
  return (
    // im Seitenrahmen (Kopfzeile, <main>) wie jede Seite – ohne ihn fehlten Pfad, Suche und Hilfe (Browsertest audit-firmen)
    <Seite pfad={[{ text: "Freigaben" }]}>
    <div className="flex flex-col gap-4 min-w-0" data-testid="seite-freigaben">
      <Seitenkopf titel="Freigaben"
        unter="Vorschläge prüfen, bei Bedarf anpassen und mit einem Klick freigeben – 60 Sekunden lang lässt sich jede Freigabe zurücknehmen."
        rechts={d?.darf.datenpflege ? (
          <Knopf icon="suche" laedt={suchen.isPending} onClick={() => suchen.mutate()} data-testid="altbestand-durchsuchen"
            title="Akten nach Freitext aus der Altdaten-Übernahme durchsuchen (Telefon mit Namen, Hausarzt mit Adresse, Hinweise, „+“/INAKTIV im Namen) und doppelte Ärzte finden">
            {patient ? "Diese Akte durchsuchen" : "Altbestand durchsuchen"}
          </Knopf>
        ) : null} />
      {patient ? (
        <div className="flex items-center gap-2 text-sm">
          <Chip art="akzent">nur eine Akte</Chip>
          <Knopf klein variante="geist" icon="x" onClick={() => setParams({})}>alle Akten zeigen</Knopf>
        </div>
      ) : null}
      {q.isPending ? <Laden /> : q.isError ? <Fehleranzeige fehler={q.error} /> : d ? <>
        <Laufleiste laufend={d.laufend} />
        {sammel.data?.uebersprungen.length ? (
          <Meldung art="warn">
            Nicht in der Sammelfreigabe: {sammel.data.uebersprungen.map((u) => `${u.patient} (${u.grund})`).join(" · ")}
          </Meldung>
        ) : null}
        {d.darf.ki && d.ki_zur_pruefung > 0 ? (
          <Karte className="p-4 flex items-center justify-between gap-3 flex-wrap" data-testid="freigaben-ki">
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-akzent-text"><Icon name="stern" groesse={20} /></span>
              <div className="flex flex-col min-w-0">
                <strong className="text-sm">{d.ki_zur_pruefung} {d.ki_zur_pruefung === 1 ? "Dokument wartet" : "Dokumente warten"} in der KI-Prüfung</strong>
                <span className="text-[0.8125rem] gedaempft">Laborwerte, Medikation, Diagnosen … aus Dokumenten – Feld für Feld in der Prüfansicht.</span>
              </div>
            </div>
            <KnopfLink to="/ki" klein>Zur KI-Prüfung</KnopfLink>
          </Karte>
        ) : null}
        {d.darf.plaene && d.plaene.length ? (
          <section className="flex flex-col gap-3 min-w-0" aria-label="Infusionspläne">
            <h2 className="lbl m-0">Infusionspläne zur Freigabe ({d.plaene.length})</h2>
            {d.plaene.map((p) => <PlanKarte key={p.id} plan={p} />)}
          </section>
        ) : null}
        {d.aerzte.length ? (
          <section className="flex flex-col gap-3 min-w-0" aria-label="Doppelte Ärzte">
            <h2 className="lbl m-0">Doppelte Ärzte zusammenführen ({d.aerzte.length})</h2>
            {d.aerzte.map((a) => <AerzteKarte key={a.id} d={a} />)}
          </section>
        ) : null}
        {d.darf.datenpflege ? (
          <section className="flex flex-col gap-3 min-w-0" aria-label="Datenpflege">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <h2 className="lbl m-0 flex items-center gap-2 flex-wrap">Datenpflege aus dem Altbestand
                {d.lernstand?.beispiele ? (
                  <Chip art="neutral" title="Die Vorschläge richten sich nach früheren Entscheidungen (z. B. Beziehung, gewählter Arzt, Anlass des Abschlusses)"
                    data-testid="lernstand">lernt aus {d.lernstand.beispiele} Entscheidungen{d.lernstand.regeln ? ` · ${d.lernstand.regeln} Regeln` : ""}</Chip>
                ) : null}
              </h2>
              {d.darf.sammel && eindeutige > 0 ? (
                <Knopf variante="pri" icon="haken" laedt={sammel.isPending} onClick={() => sammel.mutate()} data-testid="sammelfreigabe"
                  title="Alle Vorschläge ohne offene Frage freigeben – 60 Sekunden lang für alle gemeinsam zurücknehmbar">
                  Alle {eindeutige} eindeutigen freigeben
                </Knopf>
              ) : null}
            </div>
            <Segmente<Filter> label="Vorschläge filtern" wert={filter} onWahl={setzeFilter}
              werte={FILTER.map((f) => ({ wert: f.wert, text: `${f.text} ${d.zahlen[f.wert] ?? 0}` }))} />
            {d.datenpflege.length
              ? d.datenpflege.map((v) => <DatenpflegeKarte key={v.id} v={v} aerzteAnlegen={d.darf.aerzte_anlegen} />)
              : <Karte className="p-4"><Leer>{filter === "alle"
                ? `Keine offenen Vorschläge. „${patient ? "Diese Akte" : "Altbestand"} durchsuchen“ sucht nach Freitext, den die KI aufräumen kann.`
                : "Keine Vorschläge in dieser Auswahl."}</Leer></Karte>}
            {(d.datenpflege_gesamt ?? 0) > d.datenpflege.length
              ? <p className="m-0 text-[0.8125rem] gedaempft">{(d.datenpflege_gesamt ?? 0) - d.datenpflege.length} weitere erscheinen, sobald diese erledigt sind.</p> : null}
          </section>
        ) : null}
        {!anzahl && !d.ki_zur_pruefung && !d.darf.datenpflege ? <Karte className="p-4"><Leer>Nichts freizugeben.</Leer></Karte> : null}
      </> : null}
    </div>
    </Seite>
  );
}

/* ------------------------------------------------------------------------------------------------ Rückgängig */
type Eintrag = { schluessel: string; gruppe: string; liste: LaufendeFreigabe[] };

function Laufleiste({ laufend }: { laufend: LaufendeFreigabe[] }) {
  const qc = useQueryClient();
  const [jetzt, setJetzt] = useState(() => Date.now());
  const angestossen = useRef(new Set<number>());
  const wartet = laufend.some((l) => l.status === "wartet");
  useEffect(() => {
    if (!wartet) return;
    const t = window.setInterval(() => setJetzt(Date.now()), 250);
    return () => window.clearInterval(t);
  }, [wartet]);
  // Countdown abgelaufen: sofort umsetzen lassen (sonst beim nächsten Abruf); bei einer Sammelfreigabe ein Aufruf genügt
  useEffect(() => {
    for (const l of laufend) {
      if (l.status === "wartet" && new Date(l.umsetzen_ab).getTime() <= jetzt && !angestossen.current.has(l.id)) {
        angestossen.current.add(l.id);
        void api(`freigaben/${l.id}/umsetzen/`, { method: "POST", hintergrund: true })
          .finally(() => void qc.invalidateQueries({ queryKey: ["freigaben"] }));
        break;
      }
    }
  }, [jetzt, laufend, qc]);
  const zurueck = useMutation({
    mutationFn: (e: Eintrag) => e.gruppe
      ? api(`freigaben/gruppe/${e.gruppe}/zuruecknehmen/`, { method: "POST" })
      : api(`freigaben/${e.liste[0].id}/zuruecknehmen/`, { method: "POST" }),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["freigaben"] }),
  });
  const sichtbar = laufend.filter((l) => l.status === "wartet" || Date.now() - new Date(l.umsetzen_ab).getTime() < 120_000);
  // Sammelfreigaben als eine Zeile
  const eintraege: Eintrag[] = [];
  for (const l of sichtbar) {
    const vorhanden = l.gruppe ? eintraege.find((e) => e.gruppe === l.gruppe) : undefined;
    if (vorhanden) vorhanden.liste.push(l);
    else eintraege.push({ schluessel: l.gruppe || String(l.id), gruppe: l.gruppe, liste: [l] });
  }
  if (!eintraege.length) return null;
  return (
    <div className="flex flex-col gap-2 sticky top-2 z-10 min-w-0" aria-live="polite" data-testid="freigaben-laufend">
      {eintraege.map((e) => {
        const l = e.liste[0];
        const n = e.liste.length;
        const warten = e.liste.filter((x) => x.status === "wartet");
        const fehler = e.liste.filter((x) => x.status === "fehler");
        const status = warten.length ? "wartet" : fehler.length === n ? "fehler" : e.liste.every((x) => x.status === "zurueck") ? "zurueck" : "umgesetzt";
        const rest = Math.max(0, Math.ceil((new Date(l.umsetzen_ab).getTime() - jetzt) / 1000));
        const anteil = Math.min(100, Math.max(0, (rest / 60) * 100));
        const titel = e.gruppe ? `Sammelfreigabe · ${n} ${n === 1 ? "Akte" : "Akten"}` : l.titel;
        return (
          <div key={e.schluessel} className={cx("card px-4 py-3 flex items-center gap-3 flex-wrap shadow-md",
            status === "fehler" && "bg-fehler-bg", status === "umgesetzt" && "bg-ok-bg")} data-testid={`laufend-${e.schluessel}`}>
            <span className={cx(status === "umgesetzt" ? "text-ok" : status === "fehler" ? "text-fehler" : "text-akzent-text")}>
              <Icon name={status === "umgesetzt" ? "haken" : status === "fehler" ? "warnung" : status === "zurueck" ? "zurueck" : "sanduhr"} groesse={18} />
            </span>
            <div className="flex flex-col gap-1 min-w-0 flex-1">
              <span className="text-sm font-medium">{titel}</span>
              {status === "wartet" ? <>
                <span className="text-[0.8125rem] gedaempft">Freigegeben – wird in <strong className="num">{rest} s</strong> umgesetzt.</span>
                <div className="h-1.5 rounded-full bg-fein overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={60} aria-valuenow={rest}>
                  <div className="h-full bg-akzent transition-[width] duration-200" style={{ width: `${anteil}%` }} />
                </div>
              </> : status === "umgesetzt" ? (
                <span className="text-[0.8125rem]">Umgesetzt{fehler.length ? ` – ${fehler.length} nicht: ${fehler.map((x) => `${x.titel}: ${x.fehler}`).join(" · ")}` : "."}
                  {!e.gruppe && l.patient_id ? <> <Link to={`/patienten/${l.patient_id}`}>Akte öffnen</Link></> : null}</span>
              ) : status === "zurueck" ? <span className="text-[0.8125rem] gedaempft">Zurückgenommen – {n === 1 ? "der Vorschlag steht" : "die Vorschläge stehen"} wieder unten.</span>
                : <span className="text-[0.8125rem] text-fehler">Nicht umgesetzt: {fehler.map((x) => x.fehler).join(" · ")}</span>}
            </div>
            {status === "wartet" ? (
              <Knopf variante="pri" icon="zurueck" laedt={zurueck.isPending && zurueck.variables?.schluessel === e.schluessel}
                onClick={() => zurueck.mutate(e)} data-testid={`rueckgaengig-${e.schluessel}`}>Rückgängig</Knopf>
            ) : null}
          </div>
        );
      })}
      {zurueck.isError ? <Meldung art="fehler">{fehlerText(zurueck.error)}</Meldung> : null}
    </div>
  );
}

/* ------------------------------------------------------------------------------------------------ Datenpflege */
function Nr({ n, aus }: { n: number; aus?: boolean }) {
  return (
    <span className={cx("inline-flex items-center justify-center rounded-full text-[0.6875rem] font-semibold w-5 h-5 shrink-0",
      aus ? "bg-fein gedaempft" : "bg-akzent text-white")} aria-label={`Schritt ${n}`}>{n}</span>
  );
}

/** Text mit nummerierten Markierungen der Stellen, die ein Schritt verarbeitet */
function Markiert({ text, marken }: { text: string; marken: { suche: string; nr: number; aus: boolean }[] }) {
  const teile: ReactNode[] = [];
  const treffer = marken
    .map((m) => {
      let i = m.suche ? text.indexOf(m.suche) : -1;
      let laenge = m.suche.length;
      if (i < 0) {
        const nummer = m.suche.split(" (")[0];
        i = nummer ? text.indexOf(nummer) : -1;
        laenge = nummer.length;
      }
      return { ...m, i, laenge };
    })
    .filter((m) => m.i >= 0)
    .sort((a, b) => a.i - b.i);
  let pos = 0;
  for (const m of treffer) {
    if (m.i < pos) continue;
    teile.push(text.slice(pos, m.i));
    teile.push(
      <mark key={m.i} className={cx("rounded px-0.5 inline-flex items-baseline gap-1", m.aus ? "bg-fein" : "bg-warn-bg text-tinte")}>
        <Nr n={m.nr} aus={m.aus} />{text.slice(m.i, m.i + m.laenge)}
      </mark>,
    );
    pos = m.i + m.laenge;
  }
  teile.push(text.slice(pos));
  return <span className="whitespace-pre-wrap break-words">{teile}</span>;
}

function Pfeil() {
  return (
    <div className="flex md:flex-col items-center justify-center text-akzent-text py-1" aria-hidden="true">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
        strokeLinejoin="round" className="max-md:rotate-90"><path d="M5 12h14" /><path d="M13 6l6 6-6 6" /></svg>
    </div>
  );
}

type Aenderung = Partial<{ an: boolean; werte: Partial<ArztWerte & PersonWerte & { text: string; anlass: string; datum: string; notiz: string }>;
  neu: string; rolle: string; arzt_wahl: number | "neu" }>;

function DatenpflegeKarte({ v, aerzteAnlegen }: { v: Datenpflege; aerzteAnlegen: boolean }) {
  const qc = useQueryClient();
  const [schritte, setSchritte] = useState<Schritt[]>(v.schritte);
  useEffect(() => setSchritte(v.schritte), [v]);
  const nr = useMemo(() => new Map(schritte.map((s, i) => [s.id, i + 1])), [schritte]);

  function aendern(id: string, e: Aenderung) {
    setSchritte((alt) => {
      let neu = alt.map((s) => (s.id === id ? ({ ...s, ...e, werte: e.werte ? { ...(s as { werte: object }).werte, ...e.werte } : (s as { werte?: object }).werte } as Schritt) : s));
      if (e.an === false) {
        // abhängige Schritte mit abwählen (z. B. Telefonfeld bereinigen ohne Bezugsperson)
        for (let i = 0; i < 3; i++) {
          const aus = new Set(neu.filter((s) => !s.an).map((s) => s.id));
          neu = neu.map((s) => (s.an && s.abhaengig_von.some((d) => aus.has(d)) ? { ...s, an: false } : s));
        }
      } else if (e.an === true) {
        const noetig = new Set(neu.find((s) => s.id === id)?.abhaengig_von ?? []);
        neu = neu.map((s) => (noetig.has(s.id) ? { ...s, an: true } : s));
      }
      return neu;
    });
  }

  const freigeben = useMutation({
    mutationFn: () => api(`freigaben/datenpflege/${v.id}/freigeben/`, {
      body: { schritte: schritte.map((s) => ({ id: s.id, an: s.an, ...("werte" in s ? { werte: s.werte } : {}),
        ...(s.art === "feld" ? { neu: s.neu } : {}), ...(s.art === "arzt" ? { rolle: s.rolle, arzt_wahl: s.arzt_wahl } : {}) })) },
    }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["freigaben"] }),
  });
  const verwerfen = useMutation({
    mutationFn: () => api(`freigaben/datenpflege/${v.id}/verwerfen/`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["freigaben"] }),
  });
  const gruppen = useMemo(() => {
    const g = new Map<string, Schritt[]>();
    for (const s of schritte) g.set(thema(s), [...(g.get(thema(s)) ?? []), s]);
    return [...g.entries()];
  }, [schritte]);
  const felder = freigeben.error instanceof ApiFehler && freigeben.error.daten && typeof freigeben.error.daten === "object"
    ? (freigeben.error.daten as Record<string, string>) : {};
  const anzahlAn = schritte.filter((s) => s.an).length;

  return (
    <Karte className="p-4 sm:p-5 flex flex-col gap-4 min-w-0" data-testid={`datenpflege-${v.id}`}>
      <KartenKopf
        titel={<span className="flex items-center gap-2 flex-wrap">
          <Link to={`/patienten/${v.patient.id}`}>{v.patient.name}</Link>
          <span className="gedaempft font-normal text-[0.8125rem]">Nr. {v.patient.nummer} · geb. {datum(v.patient.geburtsdatum)}</span>
        </span>}
        unter={<span className="flex items-center gap-2 flex-wrap">
          <Chip art={v.verfahren.includes("ki") ? "akzent" : "neutral"}>{v.verfahren.includes("ki") ? "vorbereitet von Regeln + KI" : "vorbereitet von Regeln"}</Chip>
          <span>{zeitpunkt(v.erstellt_am)}</span>
          {schritte.some((s) => s.art === "abschluss") ? <Chip art="fehler">Akte wird abgeschlossen</Chip> : null}
          {v.eindeutig ? <Chip art="ok" title="ohne offene Frage – kommt in „Alle eindeutigen freigeben“">eindeutig</Chip>
            : schritte.some((s) => !s.sicher) ? <Chip art="warn">bitte prüfen</Chip> : null}
        </span>}
        rechts={<>
          <Knopf klein variante="geist" laedt={verwerfen.isPending} onClick={() => verwerfen.mutate()}>Verwerfen</Knopf>
          <Knopf variante="pri" icon="haken" laedt={freigeben.isPending} disabled={!anzahlAn} onClick={() => freigeben.mutate()}
            data-testid={`freigeben-${v.id}`}>
            {anzahlAn === schritte.length ? "Alles freigeben" : `${anzahlAn} von ${schritte.length} freigeben`}
          </Knopf>
        </>} />
      {freigeben.isError ? <Meldung art="fehler">{fehlerText(freigeben.error)}</Meldung> : null}
      {verwerfen.isError ? <Meldung art="fehler">{fehlerText(verwerfen.error)}</Meldung> : null}

      {gruppen.map(([t, liste]) => (
        <div key={t} className="grid grid-cols-1 md:grid-cols-[minmax(0,0.9fr)_auto_minmax(0,1.4fr)] gap-3 items-start min-w-0" data-testid={`ablauf-${t}`}>
          <Vorher t={t} v={v} liste={liste} nr={nr} />
          <Pfeil />
          <div className="flex flex-col gap-2 min-w-0">
            {liste.map((s) => (
              <SchrittAnsicht key={s.id} s={s} n={nr.get(s.id)!} nr={nr} schritte={schritte} aendern={aendern}
                fehler={felder} aerzteAnlegen={aerzteAnlegen} />
            ))}
          </div>
        </div>
      ))}
      <VorherNachher v={v} schritte={schritte} />
    </Karte>
  );
}

function Vorher({ t, v, liste, nr }: { t: string; v: Datenpflege; liste: Schritt[]; nr: Map<string, number> }) {
  const hinweis = liste.find((s) => s.art === "hinweis") as Extract<Schritt, { art: "hinweis" }> | undefined;
  const marken = liste.filter((s) => s.art === "bezugsperson" || s.art === "arzt")
    .map((s) => ({ suche: s.art === "arzt" ? "" : s.auszug, nr: nr.get(s.id)!, aus: !s.an }));
  const zeilen: { label: string; text: string }[] = t === "telefon"
    ? [{ label: "Telefon", text: v.bestand.felder.telefon }, { label: "Telefon 2", text: v.bestand.felder.telefon2 }]
    : t === "inaktiv" ? [{ label: "Name", text: `${v.bestand.felder.nachname}, ${v.bestand.felder.vorname}` }]
      : t === "hinweise" ? [] : [{ label: THEMEN[t] ?? t, text: v.bestand.felder[t as "hausarzt"] ?? "" }];
  const arzt = liste.find((s) => s.art === "arzt");
  const abschluss = liste.find((s) => s.art === "abschluss") as Extract<Schritt, { art: "abschluss" }> | undefined;
  if (t === "hinweise") {
    const hw = liste.filter((s): s is Extract<Schritt, { art: "hinweis" }> => s.art === "hinweis");
    return (
      <div className="rounded-lg border border-rand bg-fein/50 p-3 flex flex-col gap-2 text-sm min-w-0">
        <span className="lbl text-[0.75rem] uppercase tracking-wide gedaempft">Vorher · {THEMEN[t]}</span>
        {hw.map((h) => (
          <div key={h.id} className="flex flex-col">
            <span className="text-[0.75rem] gedaempft">{h.titel}</span>
            <span className="flex items-baseline gap-1.5 break-words"><Nr n={nr.get(h.id)!} aus={!h.an} />{h.text}</span>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-rand bg-fein/50 p-3 flex flex-col gap-2 text-sm min-w-0">
      <span className="lbl text-[0.75rem] uppercase tracking-wide gedaempft">Vorher · {THEMEN[t] ?? t}</span>
      {zeilen.filter((z) => z.text).map((z) => (
        <div key={z.label} className="flex flex-col">
          <span className="text-[0.75rem] gedaempft">{z.label}</span>
          <span className="flex items-baseline gap-1.5">{arzt ? <Nr n={nr.get(arzt.id)!} aus={!arzt.an} /> : null}<Markiert text={z.text} marken={marken} /></span>
        </div>
      ))}
      {abschluss ? (
        <div className="flex flex-col gap-1 border-t border-rand pt-2" data-testid="belege">
          <span className="text-[0.75rem] gedaempft">Die letzten {abschluss.belege.length} Kontakte (gelesen von Regeln{v.verfahren.includes("ki") ? " und KI" : ""})</span>
          {abschluss.belege.length ? abschluss.belege.map((b) => (
            <div key={b.id} className={cx("rounded px-2 py-1 text-[0.8125rem]", b.anlass ? "bg-warn-bg" : "")}>
              <span className="gedaempft num">{datum(b.zeitpunkt)}</span> {b.text || "—"}
              {b.anlass ? <> <Chip art="warn">{ANLAESSE.find((a) => a.wert === b.anlass)?.text}</Chip></> : null}
            </div>
          )) : <span className="text-[0.8125rem] gedaempft">keine Kontakte in der Akte</span>}
        </div>
      ) : null}
      {hinweis ? (
        <div className="flex flex-col border-t border-rand pt-2">
          <span className="text-[0.75rem] gedaempft">Hinweis aus der Altdaten-Übernahme: {hinweis.titel}</span>
          <Markiert text={hinweis.text} marken={marken} />
        </div>
      ) : null}
    </div>
  );
}

const TITEL: Record<Schritt["art"], string> = { arzt: "Arzt zuordnen", bezugsperson: "Als Bezugsperson anlegen", feld: "Feld bereinigen",
  hinweis: "Hinweis entfernen", kontakt: "In die Karteikarte übernehmen", abschluss: "Akte abschließen" };

function SchrittAnsicht({ s, n, nr, schritte, aendern, fehler, aerzteAnlegen }: {
  s: Schritt; n: number; nr: Map<string, number>; schritte: Schritt[]; aendern: (id: string, e: Aenderung) => void;
  fehler: Record<string, string>; aerzteAnlegen: boolean;
}) {
  const abhaengig = s.abhaengig_von.map((d) => nr.get(d)).filter(Boolean);
  const blockiert = s.abhaengig_von.some((d) => !schritte.find((x) => x.id === d)?.an);
  const titel = s.art === "bezugsperson" ? `Neue Bezugsperson${s.werte.beziehung ? ` (${s.werte.beziehung})` : ""}`
    : s.art === "arzt" ? `${ROLLEN[s.rolle] ?? s.rolle} aus der Ärzteliste zuordnen`
      : s.art === "feld" ? (!s.alt ? `${s.label} eintragen` : !s.neu ? `${s.label}-Freitext leeren` : `${s.label} bereinigen`)
        : s.art === "kontakt" ? "In die Karteikarte übernehmen" : s.art === "abschluss" ? "Akte abschließen"
          : `Hinweis „${s.titel}“ entfernen`;
  const f = (k: string) => fehler[`${s.id}.${k}`];
  return (
    <div className={cx("rounded-lg border p-3 flex flex-col gap-2 text-sm min-w-0", s.an ? "border-akzent/40 bg-white dark:bg-transparent" : "border-rand opacity-60",
      s.an && s.art === "abschluss" && "border-fehler/50")}
      data-testid={`schritt-${s.id}`}>
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={s.an} onChange={(e) => aendern(s.id, { an: e.target.checked })} aria-label={`Schritt ${n}: ${TITEL[s.art]}`} />
        <Nr n={n} aus={!s.an} />
        <span className="font-medium">{titel}</span>
        {!s.sicher ? <Chip art="warn">bitte prüfen</Chip> : null}
      </label>
      {s.hinweis ? <span className="text-[0.8125rem] gedaempft">{s.hinweis}</span> : null}
      {abhaengig.length ? (
        <span className={cx("text-[0.75rem]", blockiert ? "text-warn" : "gedaempft")}>
          Nur zusammen mit Schritt {abhaengig.join(", ")}{blockiert ? " – dort abgewählt, daher hier auch" : ""}.
        </span>
      ) : null}
      {s.an ? <>
        {s.art === "bezugsperson" ? (
          <div className="grid sm:grid-cols-2 gap-2">
            <Klein label="Beziehung" fehler={f("beziehung")}>
              <Eingabe list="freigaben-beziehungen" value={s.werte.beziehung} placeholder="z. B. Ehefrau"
                onChange={(e) => aendern(s.id, { werte: { beziehung: e.target.value } })} />
            </Klein>
            <Klein label="Name" fehler={f("name")}><Eingabe value={s.werte.name} onChange={(e) => aendern(s.id, { werte: { name: e.target.value } })} /></Klein>
            <Klein label="Mobil" fehler={f("mobil")}><Eingabe className="num" value={s.werte.mobil} onChange={(e) => aendern(s.id, { werte: { mobil: e.target.value } })} /></Klein>
            <Klein label="Telefon" fehler={f("telefon")}><Eingabe className="num" value={s.werte.telefon} onChange={(e) => aendern(s.id, { werte: { telefon: e.target.value } })} /></Klein>
            <datalist id="freigaben-beziehungen">{BEZIEHUNGEN.map((b) => <option key={b} value={b} />)}</datalist>
          </div>
        ) : s.art === "feld" ? (
          <div className="grid gap-1.5">
            {s.alt ? <span className="rounded px-2 py-1 bg-fehler-bg line-through decoration-fehler/70 num break-words" title="bisher">{s.alt}</span>
              : <span className="text-[0.75rem] gedaempft">bisher leer</span>}
            <Klein label="neu" fehler={f("neu")}>
              <Eingabe className="num bg-ok-bg" value={s.neu} placeholder="(leer)" onChange={(e) => aendern(s.id, { neu: e.target.value })} />
            </Klein>
          </div>
        ) : s.art === "hinweis" ? (
          <span className="rounded px-2 py-1 bg-fehler-bg line-through decoration-fehler/70 break-words">{s.text}</span>
        ) : s.art === "kontakt" ? (
          <Klein label="Eintrag in der Karteikarte (heute, unter Ihrem Namen)" fehler={f("text")}>
            <Textfeld rows={3} className="bg-ok-bg" value={s.werte.text} onChange={(e) => aendern(s.id, { werte: { text: e.target.value } })} />
          </Klein>
        ) : s.art === "abschluss" ? (
          <AbschlussFrage s={s} aendern={aendern} f={f} />
        ) : (
          <ArztWahl s={s} aendern={aendern} f={f} aerzteAnlegen={aerzteAnlegen} />
        )}
      </> : null}
    </div>
  );
}

/** Akte abschließen: Was unklar ist, fragt die Karte ab – ohne Anlass lässt sich nicht freigeben */
function AbschlussFrage({ s, aendern, f }: { s: Extract<Schritt, { art: "abschluss" }>; aendern: (id: string, e: Aenderung) => void;
  f: (k: string) => string | undefined }) {
  const offen = !s.werte.anlass;
  return (
    <div className="flex flex-col gap-2" data-testid="abschluss-frage">
      <div className={cx("rounded-md px-3 py-2 flex gap-2 items-start", offen ? "bg-warn-bg" : "bg-fein")}>
        <span className={offen ? "text-warn" : "gedaempft"}><Icon name={offen ? "hilfe" : "info"} groesse={16} /></span>
        <span className="text-[0.8125rem]">{s.frage}</span>
      </div>
      <fieldset className="flex flex-col gap-1 border-0 p-0 m-0">
        <legend className="text-[0.75rem] gedaempft mb-1">Anlass</legend>
        {ANLAESSE.map((a) => (
          <label key={a.wert} className="flex items-start gap-2 cursor-pointer">
            <input type="radio" name={`anlass-${s.id}`} checked={s.werte.anlass === a.wert}
              onChange={() => aendern(s.id, { werte: { anlass: a.wert } })} />
            <span><strong className="font-medium">{a.text}</strong> <span className="gedaempft">– {a.erklaerung}</span></span>
          </label>
        ))}
        {f("anlass") ? <span className="text-fehler text-[0.75rem]">{f("anlass")}</span> : null}
      </fieldset>
      <div className="grid sm:grid-cols-[10rem_1fr] gap-2">
        <Klein label="Datum" fehler={f("datum")}>
          <Eingabe type="date" value={s.werte.datum} onChange={(e) => aendern(s.id, { werte: { datum: e.target.value } })} />
        </Klein>
        <Klein label="Notiz zum Abschluss" fehler={f("notiz")}>
          <Textfeld rows={2} value={s.werte.notiz} onChange={(e) => aendern(s.id, { werte: { notiz: e.target.value } })} />
        </Klein>
      </div>
      <span className="text-[0.75rem] gedaempft">Danach ist die Akte schreibgeschützt (Wieder öffnen nur mit dem Recht dazu).</span>
    </div>
  );
}

function Klein({ label, fehler, children }: { label: string; fehler?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-0.5 text-[0.75rem] gedaempft">
      {label}{children}{fehler ? <span className="text-fehler">{fehler}</span> : null}
    </label>
  );
}

function ArztWahl({ s, aendern, f, aerzteAnlegen }: { s: Extract<Schritt, { art: "arzt" }>; aendern: (id: string, e: Aenderung) => void;
  f: (k: string) => string | undefined; aerzteAnlegen: boolean }) {
  const felder: [keyof ArztWerte, string][] = [["name", "Name"], ["praxis", "Praxis / Klinik"], ["fachrichtung", "Fachrichtung"],
    ["strasse", "Straße"], ["plz", "PLZ"], ["ort", "Ort"], ["telefon", "Telefon"], ["fax", "Fax"], ["email", "E-Mail"]];
  return (
    <div className="flex flex-col gap-2">
      <Klein label="Rolle beim Patienten">
        <Auswahl value={s.rolle} onChange={(e) => aendern(s.id, { rolle: e.target.value })}>
          {Object.entries(ROLLEN).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
        </Auswahl>
      </Klein>
      <fieldset className="flex flex-col gap-1 border-0 p-0 m-0">
        <legend className="text-[0.75rem] gedaempft mb-1">Ärzteliste</legend>
        {s.treffer.map((t) => (
          <label key={t.id} className="flex items-start gap-2 cursor-pointer">
            <input type="radio" name={`arzt-${s.id}`} checked={s.arzt_wahl === t.id} onChange={() => aendern(s.id, { arzt_wahl: t.id })} />
            <span>Vorhandenen Arzt verwenden: <strong>{t.name}</strong>
              <span className="gedaempft"> {[t.praxis, [t.plz, t.ort].filter(Boolean).join(" "), t.telefon].filter(Boolean).join(" · ")}</span></span>
          </label>
        ))}
        <label className={cx("flex items-start gap-2", aerzteAnlegen ? "cursor-pointer" : "opacity-60")}>
          <input type="radio" name={`arzt-${s.id}`} checked={s.arzt_wahl === "neu"} disabled={!aerzteAnlegen}
            onChange={() => aendern(s.id, { arzt_wahl: "neu" })} />
          <span>Neu in der Ärzteliste anlegen{aerzteAnlegen ? "" : " (dafür fehlt das Recht „Ärzte pflegen“)"}</span>
        </label>
        {f("arzt_wahl") ? <span className="text-fehler text-[0.75rem]">{f("arzt_wahl")}</span> : null}
      </fieldset>
      {s.arzt_wahl === "neu" ? (
        <div className="grid sm:grid-cols-3 gap-2">
          {felder.map(([k, label]) => (
            <Klein key={k} label={label} fehler={f(k)}>
              <Eingabe className={k === "telefon" || k === "fax" || k === "plz" ? "num" : undefined} value={s.werte[k]}
                onChange={(e) => aendern(s.id, { werte: { [k]: e.target.value } })} />
            </Klein>
          ))}
        </div>
      ) : null}
    </div>
  );
}

const FELD_NAMEN: [keyof Datenpflege["bestand"]["felder"], string][] = [
  ["nachname", "Nachname"], ["vorname", "Vorname"], ["telefon", "Telefon"], ["telefon2", "Telefon 2"], ["email", "E-Mail"],
  ["strasse", "Straße"], ["plz", "PLZ"], ["ort", "Ort"], ["groesse_cm", "Größe (cm)"], ["hausarzt", "Hausarzt (Freitext)"],
  ["ueberweisung_durch", "Überweisung"],
];

/** Die Akte vorher und nachher – geänderte Zeilen hervorgehoben */
function VorherNachher({ v, schritte }: { v: Datenpflege; schritte: Schritt[] }) {
  const b = v.bestand;
  const an = schritte.filter((s) => s.an);
  const felder = { ...b.felder };
  for (const s of an) if (s.art === "feld") felder[s.feld as keyof typeof felder] = s.neu;
  const neuePersonen = an.filter((s) => s.art === "bezugsperson").map((s) => s.werte as PersonWerte);
  const neueAerzte = an.filter((s): s is Extract<Schritt, { art: "arzt" }> => s.art === "arzt").map((s) => {
    const t = s.treffer.find((x) => x.id === s.arzt_wahl);
    return { rolle: ROLLEN[s.rolle] ?? s.rolle, name: t ? t.name : s.werte.name, neu: !t };
  });
  const weg = new Set(an.filter((s) => s.art === "hinweis").map((s) => (s as { titel: string }).titel));
  const karteikarte = an.filter((s): s is Extract<Schritt, { art: "kontakt" }> => s.art === "kontakt").map((s) => s.werte.text);
  const abschluss = an.find((s): s is Extract<Schritt, { art: "abschluss" }> => s.art === "abschluss");
  const person = (p: { name: string; beziehung: string; telefon: string; mobil: string }) =>
    [p.beziehung ? `${p.name} (${p.beziehung})` : p.name, p.mobil || p.telefon].filter(Boolean).join(" · ");
  const zeilen: { label: string; vorher: ReactNode; nachher: ReactNode; anders: boolean }[] = [
    ...FELD_NAMEN.filter(([k]) => ["telefon", "telefon2", "hausarzt"].includes(k) || b.felder[k] !== felder[k])
      .map(([k, label]) => ({ label, vorher: b.felder[k] || "—", nachher: felder[k] || "—", anders: b.felder[k] !== felder[k] })),
    {
      label: "Bezugspersonen", anders: neuePersonen.length > 0,
      vorher: b.bezugspersonen.length ? b.bezugspersonen.map((p) => <div key={p.id}>{person(p)}</div>) : "—",
      nachher: <>{b.bezugspersonen.map((p) => <div key={p.id}>{person(p)}</div>)}
        {neuePersonen.map((p, i) => <div key={`n${i}`}><Chip art="ok">neu</Chip> {person(p)}</div>)}
        {!b.bezugspersonen.length && !neuePersonen.length ? "—" : null}</>,
    },
    {
      label: "Ärzte (Reiter)", anders: neueAerzte.length > 0,
      vorher: b.aerzte.length ? b.aerzte.map((a) => <div key={a.id}>{a.rolle_name}: {a.name}</div>) : "—",
      nachher: <>{b.aerzte.map((a) => <div key={a.id}>{a.rolle_name}: {a.name}</div>)}
        {neueAerzte.map((a, i) => <div key={`n${i}`}><Chip art="ok">{a.neu ? "neu angelegt" : "zugeordnet"}</Chip> {a.rolle}: {a.name}</div>)}
        {!b.aerzte.length && !neueAerzte.length ? "—" : null}</>,
    },
    {
      label: "Hinweise aus der Übernahme", anders: weg.size > 0,
      vorher: b.hinweise.length ? b.hinweise.map((h) => <div key={h.titel}>{h.titel}</div>) : "—",
      nachher: !b.hinweise.length ? "—" : b.hinweise.filter((h) => !weg.has(h.titel)).map((h) => <div key={h.titel}>{h.titel}</div>).concat(
        b.hinweise.every((h) => weg.has(h.titel)) ? [<Fragment key="leer">— (die Karte in der Übersicht entfällt)</Fragment>] : []),
    },
    ...(karteikarte.length ? [{
      label: "Karteikarte", anders: true, vorher: "—",
      nachher: karteikarte.map((k, i) => <div key={i}><Chip art="ok">neuer Eintrag</Chip> {k}</div>),
    }] : []),
    ...(abschluss ? [{
      label: "Akte", anders: true, vorher: "offen",
      nachher: <><Chip art="fehler">abgeschlossen</Chip> {abschluss.werte.anlass
        ? `${ANLAESSE.find((a) => a.wert === abschluss.werte.anlass)?.text} · ${datum(abschluss.werte.datum)}` : "Anlass noch offen"}</>,
    }] : []),
  ];
  return (
    <details className="rounded-lg border border-rand min-w-0" open data-testid={`vorher-nachher-${v.id}`}>
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium">Akte vorher und nachher</summary>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead><tr className="text-left text-[0.75rem] gedaempft">
            <th className="px-3 py-1.5 font-medium w-40">Angabe</th><th className="px-3 py-1.5 font-medium">Vorher</th><th className="px-3 py-1.5 font-medium">Nachher</th>
          </tr></thead>
          <tbody>
            {zeilen.map((z) => (
              <tr key={z.label} className="border-t border-rand align-top">
                <td className="px-3 py-1.5 gedaempft">{z.label}</td>
                <td className={cx("px-3 py-1.5 break-words", z.anders && "bg-fehler-bg/50")}>{z.vorher}</td>
                <td className={cx("px-3 py-1.5 break-words", z.anders && "bg-ok-bg/60 font-medium")}>{z.nachher}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

/* ------------------------------------------------------------------------------------------------ Pläne */
function PlanKarte({ plan }: { plan: PlanEntwurf }) {
  const qc = useQueryClient();
  const freigeben = useMutation({
    mutationFn: () => api(`freigaben/plaene/${plan.id}/freigeben/`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["freigaben"] }),
  });
  return (
    <Karte className="p-4 sm:p-5 flex flex-col gap-3 min-w-0" data-testid={`plan-${plan.id}`}>
      <KartenKopf
        titel={<span className="flex items-center gap-2 flex-wrap"><Link to={`/patienten/${plan.patient.id}/plaene`}>{plan.patient.name}</Link>
          <span className="gedaempft font-normal text-[0.8125rem]">Nr. {plan.patient.nummer}</span></span>}
        unter={`Entwurf gültig ab ${datum(plan.gueltig_ab)}${plan.erstellt_von ? ` · angelegt von ${plan.erstellt_von}` : ""} · ${
          plan.vorgaenger ? `${plan.anzahl_geaendert} Änderung${plan.anzahl_geaendert === 1 ? "" : "en"} zum Plan vom ${datum(plan.vorgaenger.gueltig_ab)}` : "erster Plan"}`}
        rechts={<>
          <KnopfLink klein variante="geist" icon="stift" to={`/patienten/${plan.patient.id}/plaene/${plan.id}/bearbeiten`}>Bearbeiten</KnopfLink>
          <Knopf variante="pri" icon="haken" laedt={freigeben.isPending} onClick={() => freigeben.mutate()} data-testid={`plan-freigeben-${plan.id}`}>Freigeben</Knopf>
        </>} />
      {freigeben.isError ? <Meldung art="fehler">{fehlerText(freigeben.error)}</Meldung> : null}
      {plan.zeilen.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead><tr className="text-left text-[0.75rem] gedaempft">
              <th className="px-3 py-1.5 font-medium">Bestandteil</th>
              {plan.vorgaenger ? <th className="px-3 py-1.5 font-medium">Bisher</th> : null}
              <th className="px-3 py-1.5 font-medium">{plan.vorgaenger ? "Neu" : "Plan"}</th>
            </tr></thead>
            <tbody>
              {plan.zeilen.map((z) => (
                <tr key={z.schluessel} className="border-t border-rand">
                  <td className="px-3 py-1.5 gedaempft">{z.wert}</td>
                  {plan.vorgaenger ? <td className={cx("px-3 py-1.5", z.geaendert && "bg-fehler-bg/50 line-through decoration-fehler/60")}>{z.vorher ?? "—"}</td> : null}
                  <td className={cx("px-3 py-1.5", z.geaendert && "bg-ok-bg/60 font-medium")}>{z.jetzt ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <Leer>Keine Änderungen zum bisherigen Plan.</Leer>}
    </Karte>
  );
}

/* ------------------------------------------------------------------------------------------------ Ärzte */
const ARZT_FELDER: ArztFeld[] = ["name", "praxis", "fachrichtung", "strasse", "plz", "ort", "telefon", "fax", "email"];

/** Doppelte Ärzte: Einträge nebeneinander, Ergebnis je Feld wählbar bzw. bearbeitbar, welcher Eintrag bleibt */
function AerzteKarte({ d }: { d: Arztdublette }) {
  const qc = useQueryClient();
  const [ziel, setZiel] = useState<number | null>(d.ziel);
  const [werte, setWerte] = useState(d.werte);
  useEffect(() => { setZiel(d.ziel); setWerte(d.werte); }, [d]);
  const freigeben = useMutation({
    mutationFn: () => api(`freigaben/aerzte/${d.id}/freigeben/`, { body: { ziel, werte } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["freigaben"] }),
  });
  const verwerfen = useMutation({
    mutationFn: () => api(`freigaben/aerzte/${d.id}/verwerfen/`, { method: "POST" }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["freigaben"] }),
  });
  const patienten = d.aerzte.reduce((n, a) => n + a.patienten, 0);
  return (
    <Karte className="p-4 sm:p-5 flex flex-col gap-3 min-w-0" data-testid={`aerzte-${d.id}`}>
      <KartenKopf titel={`${d.aerzte.length} Einträge sind vermutlich derselbe Arzt`}
        unter={<span className="flex gap-2 flex-wrap">{d.gruende.map((g) => <Chip key={g} art="neutral">{g}</Chip>)}
          <span>{patienten} Patienten insgesamt</span></span>}
        rechts={<>
          <Knopf klein variante="geist" laedt={verwerfen.isPending} onClick={() => verwerfen.mutate()}
            title="Kein Doppel – wird nicht wieder vorgeschlagen">Keine Dublette</Knopf>
          <Knopf variante="pri" icon="haken" laedt={freigeben.isPending} disabled={!ziel} onClick={() => freigeben.mutate()}
            data-testid={`aerzte-freigeben-${d.id}`}>Zusammenführen</Knopf>
        </>} />
      {freigeben.isError ? <Meldung art="fehler">{fehlerText(freigeben.error)}</Meldung> : null}
      {verwerfen.isError ? <Meldung art="fehler">{fehlerText(verwerfen.error)}</Meldung> : null}
      <div className="overflow-x-auto min-w-0">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left text-[0.75rem] gedaempft align-bottom">
              <th className="px-2 py-1.5 font-medium w-28">Feld</th>
              {d.aerzte.map((a) => (
                <th key={a.id} className="px-2 py-1.5 font-medium min-w-36">
                  <label className="flex items-center gap-1.5 cursor-pointer text-tinte">
                    <input type="radio" name={`ziel-${d.id}`} checked={ziel === a.id} onChange={() => setZiel(a.id)} />
                    Nr. {a.id} {ziel === a.id ? <Chip art="ok">bleibt</Chip> : <Chip art="neutral">wird deaktiviert</Chip>}
                  </label>
                  <span className="font-normal">{a.patienten} {a.patienten === 1 ? "Patient" : "Patienten"}</span>
                </th>
              ))}
              <th className="px-2 py-1.5 font-medium min-w-48">Ergebnis</th>
            </tr>
          </thead>
          <tbody>
            {ARZT_FELDER.map((f) => {
              const verschieden = new Set(d.aerzte.map((a) => a[f]).filter(Boolean)).size > 1;
              return (
                <tr key={f} className="border-t border-rand align-top">
                  <td className="px-2 py-1.5 gedaempft">{d.felder[f]}</td>
                  {d.aerzte.map((a) => (
                    <td key={a.id} className="px-2 py-1.5 break-words">
                      {a[f] ? (
                        <button type="button" className={cx("text-left border-0 bg-transparent p-0 cursor-pointer", werte[f] === a[f] ? "font-medium" : "gedaempft")}
                          title="Diesen Wert übernehmen" onClick={() => setWerte({ ...werte, [f]: a[f] })}>
                          {werte[f] === a[f] ? "✓ " : ""}{a[f]}
                        </button>
                      ) : <span className="gedaempft">—</span>}
                    </td>
                  ))}
                  <td className="px-2 py-1">
                    <Eingabe className={cx(verschieden && "bg-warn-bg")} value={werte[f]} aria-label={`Ergebnis ${d.felder[f]}`}
                      onChange={(e) => setWerte({ ...werte, [f]: e.target.value })} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <span className="text-[0.75rem] gedaempft">Alle Patienten des deaktivierten Eintrags zeigen danach auf den bleibenden. Gelb: Die Einträge unterscheiden sich – bitte den richtigen Wert wählen (anklicken) oder eintragen.</span>
    </Karte>
  );
}
