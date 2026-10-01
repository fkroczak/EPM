/** Entwurf 3 · Patientenliste (Variante 21 über die Darstellung „Hoher Kontrast“). */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuswahl, useVersorgerListe } from "@/lib/daten";
import { datum, kg, nummer, prozent, relativ, zahl } from "@/lib/format";
import { ABSCHLUSSANLAESSE } from "@/lib/typen";
import type { PatientZeile, Trend } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Fehleranzeige, Karte, KnopfLink, Knopf, Laden, Leer, Seitenkopf, Segmente, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";

type Zaehler = { in_betreuung: number; abgeschlossen: number; mit_hinweisen: number; gewichtsverlust: number; termin_woche: number };

const SEITENGROESSE = 50;

const SCHNELLFILTER: { wert: string; text: string; zahl: keyof Zaehler }[] = [
  { wert: "hinweise", text: "Nur mit Hinweisen", zahl: "mit_hinweisen" },
  { wert: "gewichtsverlust", text: "Gewichtsverlust", zahl: "gewichtsverlust" },
  { wert: "termin_woche", text: "Termin diese Woche", zahl: "termin_woche" },
];

const PRUEFEN: Record<string, string> = {
  altdokumente: "Altdokumente ohne geprüften Typ",
  nickelallergie: "Nickelallergie nicht erfasst",
  kein_versorger: "Kein Versorger eingetragen",
  kein_kontakt: "Lange kein Kontakt",
};

const SORTIERUNG_TEXT: Record<string, string> = {
  "-letzter_kontakt": "Sortiert nach letztem Kontakt",
  letzter_kontakt: "Sortiert nach letztem Kontakt (älteste zuerst)",
  nachname: "Sortiert nach Name",
  "-nachname": "Sortiert nach Name (Z–A)",
  nummer: "Sortiert nach Nummer",
  "-nummer": "Sortiert nach Nummer (absteigend)",
  geburtsdatum: "Sortiert nach Geburtsdatum",
  "-geburtsdatum": "Sortiert nach Geburtsdatum (jüngste zuerst)",
  "-abgeschlossen_am": "Sortiert nach Abschluss",
  abgeschlossen_am: "Sortiert nach Abschluss (älteste zuerst)",
};

export function TrendPfeil({ trend }: { trend: Trend | null }) {
  if (!trend || !trend.richtung) return null;
  const zeichen = trend.richtung === "down" ? "↓" : trend.richtung === "up" ? "↑" : "→";
  const wort = trend.richtung === "down" ? "fallend" : trend.richtung === "up" ? "steigend" : "gleichbleibend";
  return (
    <span className={cx("ml-1", trend.richtung === "down" ? "text-fehler" : "gedaempft")}
      title={`${prozent(trend.prozent)} im Vergleichszeitraum`} aria-label={`Trend ${wort}, ${prozent(trend.prozent)}`}>
      {zeichen}
    </span>
  );
}

function Spalte({ feld, sortierung, onSortieren, children, rechts, breite }: {
  feld?: string; sortierung: string; onSortieren: (o: string) => void; children: ReactNode; rechts?: boolean; breite?: string;
}) {
  if (!feld) return <th className="th" style={{ textAlign: rechts ? "right" : undefined, width: breite }}>{children}</th>;
  const aktiv = sortierung === feld || sortierung === `-${feld}`;
  const ab = sortierung === `-${feld}`;
  return (
    <th className="th" style={{ textAlign: rechts ? "right" : undefined, width: breite }}
      aria-sort={aktiv ? (ab ? "descending" : "ascending") : "none"}>
      <button type="button" className={cx("bg-transparent border-0 p-0 cursor-pointer font-medium inline-flex items-center gap-1",
        aktiv ? "text-akzent-text" : "text-tinte")}
        onClick={() => onSortieren(aktiv && !ab ? `-${feld}` : aktiv ? feld : feld === "letzter_kontakt" || feld === "abgeschlossen_am" ? `-${feld}` : feld)}>
        {children} <span aria-hidden="true">{aktiv ? (ab ? "↓" : "↑") : "↕"}</span>
      </button>
    </th>
  );
}

function Hinweise({ p }: { p: PatientZeile }) {
  return (
    <span className="inline-flex gap-1.5 flex-wrap">
      {p.nickelallergie === "ja" ? <Chip art="fehler">Nickelallergie</Chip> : null}
      {p.nickelallergie === "unbekannt" ? <Chip title="Nickelallergie nicht erfasst">Nickel ?</Chip> : null}
      {(p.kennzahlen?.hinweise ?? []).map((h) => <Chip key={h.art} art="warn">{h.text}</Chip>)}
    </span>
  );
}

export function Patienten() {
  const [params, setParams] = useSearchParams();
  const { darf } = useAuth();
  const archiv = params.get("status") === "abgeschlossen";
  const versorgerId = params.get("versorger") ?? "";
  const apId = params.get("ansprechpartner") ?? "";
  const katheterId = params.get("katheter") ?? "";
  const schnell = params.get("schnellfilter") ?? "";
  const pruefen = params.get("pruefen") ?? "";
  const sortierung = params.get("ordering") ?? (archiv ? "-abgeschlossen_am" : "-letzter_kontakt");
  const seite = Math.max(1, Number(params.get("seite") ?? "1") || 1);
  const [suche, setSuche] = useState(params.get("suche") ?? "");

  // Grundlage ist immer die aktuelle Adresse, nicht der Stand beim letzten Rendern: Der Router übernimmt eine neue
  // Adresse verzögert (Transition). Sonst überschreibt die verzögerte Suche einen kurz danach gewählten Filter.
  const setze = (aenderung: Record<string, string | null>, seiteBehalten = false) => {
    const neu = new URLSearchParams(window.location.search);
    for (const [k, v] of Object.entries(aenderung)) {
      if (v) neu.set(k, v); else neu.delete(k);
    }
    if (!seiteBehalten) neu.delete("seite");
    setParams(neu, { replace: true });
  };

  // Freitext mit kurzer Verzögerung in die Adresse übernehmen (Liste bleibt teilbar und „Zurück“ funktioniert)
  useEffect(() => {
    const t = window.setTimeout(() => {
      const inAdresse = new URLSearchParams(window.location.search).get("suche") ?? "";
      if (inAdresse !== suche.trim()) setze({ suche: suche.trim() || null });
    }, 300);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suche]);

  const versorger = useVersorgerListe();
  const katheter = useAuswahl("katheter", false);
  const zaehler = useQuery({ queryKey: ["patienten", "zaehler"], queryFn: () => api<Zaehler>("patienten/zaehler/") });
  const abfrageWerte = {
    status: archiv ? "abgeschlossen" : "in_betreuung",
    suche: params.get("suche") ?? undefined,
    versorger: versorgerId || undefined,
    ansprechpartner: apId || undefined,
    katheter: katheterId || undefined,
    schnellfilter: !archiv && schnell ? schnell : undefined,
    pruefen: pruefen || undefined,
    ordering: sortierung,
    page: seite,
    seitengroesse: SEITENGROESSE,
  };
  const liste = useQuery({
    queryKey: ["patienten", "liste", abfrageWerte],
    queryFn: () => api<ApiSeite<PatientZeile>>(`patienten/${abfrage(abfrageWerte)}`),
    placeholderData: (vorher: ApiSeite<PatientZeile> | undefined) => vorher,
  });

  const ansprechpartner = (versorger.data ?? [])
    .filter((v) => !versorgerId || String(v.id) === versorgerId)
    .flatMap((v) => v.ansprechpartner.map((a) => ({ ...a, versorger_name: v.name })));
  const z = zaehler.data;
  const daten = liste.data;
  const von = daten && daten.count ? (seite - 1) * SEITENGROESSE + 1 : 0;
  const bis = daten ? Math.min(seite * SEITENGROESSE, daten.count) : 0;
  const gefiltert = !!(params.get("suche") || versorgerId || apId || katheterId || schnell || pruefen);

  const umschalter = (
    <Segmente label="Ansicht" wert={archiv ? "abgeschlossen" : "in_betreuung"}
      onWahl={(w) => {
        const neu = new URLSearchParams();
        if (w === "abgeschlossen") neu.set("status", "abgeschlossen");
        setSuche("");
        setParams(neu);
      }}
      werte={[
        { wert: "in_betreuung", text: <>In Betreuung <span className="num opacity-70">{z ? zahl(z.in_betreuung) : ""}</span></> },
        { wert: "abgeschlossen", text: <>Abgeschlossen <span className="num opacity-70">{z ? zahl(z.abgeschlossen) : ""}</span></> },
      ]} />
  );

  return (
    <Seite pfad={[{ text: "Patienten" }]}>
      {archiv ? (
        <Seitenkopf titel="Abgeschlossene Akten"
          unter={<span className="max-w-[70ch] leading-normal inline-block">Hier liegen Akten, deren Betreuung beendet ist. Sie bleiben
            vollständig lesbar und lassen sich als PDF ausgeben, werden aber nicht mehr verändert.</span>}
          rechts={umschalter} />
      ) : (
        <Seitenkopf titel="Patienten"
          unter={<><span className="num">{z ? zahl(z.in_betreuung) : "…"}</span> Patienten in Betreuung</>}
          rechts={<>
            {umschalter}
            {darf("akten_bearbeiten") ? <KnopfLink to="/patienten/neu" variante="pri" icon="plus">Neuer Patient</KnopfLink> : null}
          </>} />
      )}

      <div className="flex items-center gap-2.5 flex-wrap">
        <label className="relative w-[280px] block">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
          <input className="inp pl-[34px]" type="search" aria-label="Liste filtern" placeholder="Liste filtern"
            value={suche} onChange={(e) => setSuche(e.target.value)} />
        </label>
        <Auswahl aria-label="Versorger" className="w-[190px]" value={versorgerId}
          onChange={(e) => setze({ versorger: e.target.value || null, ansprechpartner: null })}>
          <option value="">Alle Versorger</option>
          {(versorger.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.name}{v.aktiv ? "" : " (inaktiv)"}</option>)}
        </Auswahl>
        <Auswahl aria-label="Ansprechpartner" className="w-[210px]" value={apId}
          onChange={(e) => setze({ ansprechpartner: e.target.value || null })}>
          <option value="">Alle Ansprechpartner</option>
          {ansprechpartner.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.versorger_name})</option>)}
        </Auswahl>
        <Auswahl aria-label="Katheter" className="w-[160px]" value={katheterId}
          onChange={(e) => setze({ katheter: e.target.value || null })}>
          <option value="">Alle Katheter</option>
          {(katheter.data ?? []).map((k) => <option key={k.id} value={k.id}>{k.wert}</option>)}
        </Auswahl>
        {!archiv ? (
          <>
            <span className="w-px h-6 bg-rand" aria-hidden="true" />
            {SCHNELLFILTER.map((f) => (
              <button key={f.wert} type="button" aria-pressed={schnell === f.wert}
                className={cx("chip h-[30px] cursor-pointer border", schnell === f.wert ? "akzent border-akzent" : "border-rand bg-flaeche text-text2")}
                onClick={() => setze({ schnellfilter: schnell === f.wert ? null : f.wert })}>
                {f.text} <span className="num gedaempft">{z ? zahl(z[f.zahl]) : ""}</span>
              </button>
            ))}
          </>
        ) : null}
        {pruefen ? (
          <Chip art="akzent" className="h-[30px]">
            {PRUEFEN[pruefen] ?? pruefen}
            <button type="button" className="bg-transparent border-0 p-0 cursor-pointer text-inherit inline-flex"
              aria-label="Prüffilter entfernen" onClick={() => setze({ pruefen: null })}><Icon name="x" /></button>
          </Chip>
        ) : null}
        {gefiltert ? (
          <Knopf variante="geist" klein onClick={() => { setSuche(""); setParams(archiv ? new URLSearchParams("status=abgeschlossen") : new URLSearchParams()); }}>
            Filter zurücksetzen
          </Knopf>
        ) : null}
      </div>

      <Fehleranzeige fehler={liste.error} />
      <Karte className="overflow-hidden">
        {liste.isLoading ? <Laden /> : (
          <table className="tabelle" aria-busy={liste.isFetching || undefined} data-testid="patientenliste">
            <thead>
              {archiv ? (
                <tr>
                  <Spalte feld="nummer" breite="64px" sortierung={sortierung} onSortieren={(o) => setze({ ordering: o })}>Nr.</Spalte>
                  <Spalte feld="nachname" sortierung={sortierung} onSortieren={(o) => setze({ ordering: o })}>Name</Spalte>
                  <Spalte feld="geburtsdatum" sortierung={sortierung} onSortieren={(o) => setze({ ordering: o })}>Geboren</Spalte>
                  <Spalte sortierung={sortierung} onSortieren={() => undefined}>Katheter</Spalte>
                  <Spalte sortierung={sortierung} onSortieren={() => undefined}>Versorger</Spalte>
                  <Spalte feld="abgeschlossen_am" sortierung={sortierung} onSortieren={(o) => setze({ ordering: o })}>Abgeschlossen</Spalte>
                  <Spalte sortierung={sortierung} onSortieren={() => undefined}>Anlass</Spalte>
                </tr>
              ) : (
                <tr>
                  <Spalte feld="nummer" breite="64px" sortierung={sortierung} onSortieren={(o) => setze({ ordering: o })}>Nr.</Spalte>
                  <Spalte feld="nachname" sortierung={sortierung} onSortieren={(o) => setze({ ordering: o })}>Name</Spalte>
                  <Spalte feld="geburtsdatum" sortierung={sortierung} onSortieren={(o) => setze({ ordering: o })}>Geboren</Spalte>
                  <Spalte sortierung={sortierung} onSortieren={() => undefined}>Katheter</Spalte>
                  <Spalte sortierung={sortierung} onSortieren={() => undefined}>Versorger</Spalte>
                  <Spalte rechts sortierung={sortierung} onSortieren={() => undefined}>Gewicht</Spalte>
                  <Spalte feld="letzter_kontakt" sortierung={sortierung} onSortieren={(o) => setze({ ordering: o })}>Letzter Kontakt</Spalte>
                  <Spalte sortierung={sortierung} onSortieren={() => undefined}>Hinweise</Spalte>
                </tr>
              )}
            </thead>
            <tbody>
              {(daten?.results ?? []).map((p) => archiv ? (
                <tr key={p.id}>
                  <td className="td num gedaempft">{nummer(p.nummer)}</td>
                  <td className="td"><Link to={`/patienten/${p.id}`} className="font-medium no-underline text-text2">{p.nachname}, {p.vorname}</Link></td>
                  <td className="td num text-text2">{datum(p.geburtsdatum)}</td>
                  <td className="td text-text2">{p.katheter_name ?? "—"}</td>
                  <td className="td text-text2">{p.versorger_name ?? "—"}</td>
                  <td className="td num text-text2">{datum(p.abgeschlossen_am)}</td>
                  <td className="td gedaempft">{ABSCHLUSSANLAESSE[p.abschluss_anlass] ?? p.abschluss_anlass}</td>
                </tr>
              ) : (
                <tr key={p.id}>
                  <td className="td num gedaempft">{nummer(p.nummer)}</td>
                  <td className="td">
                    <span className="inline-flex items-center gap-2">
                      <Link to={`/patienten/${p.id}`} className="font-medium no-underline">{p.nachname}, {p.vorname}</Link>
                      {p.ist_test ? <Chip art="warn">Testpatient</Chip> : null}
                    </span>
                  </td>
                  <td className="td"><span className="num">{datum(p.geburtsdatum)}</span> <span className="gedaempft">({p.alter})</span></td>
                  <td className="td">{p.katheter_name ?? "—"}</td>
                  <td className="td text-text2">
                    {p.versorger_name ?? "—"}
                    {p.ansprechpartner_name ? <><br /><span className="text-[0.78rem] gedaempft">{p.ansprechpartner_name}</span></> : null}
                  </td>
                  <td className="td num text-right whitespace-nowrap">
                    {kg(p.kennzahlen?.gewicht?.kg)}<TrendPfeil trend={p.kennzahlen?.trend ?? null} />
                  </td>
                  <td className="td text-text2">{relativ(p.kennzahlen?.letzter_kontakt)}</td>
                  <td className="td"><Hinweise p={p} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {daten && daten.count === 0 ? (
          <Leer>{gefiltert ? "Keine Patienten passen zu diesen Filtern." : archiv ? "Noch keine abgeschlossenen Akten." : "Noch keine Patienten angelegt."}</Leer>
        ) : null}
      </Karte>

      <div className="flex justify-between items-center gap-4 text-[0.8125rem] gedaempft flex-wrap">
        <span>
          {archiv
            ? "Eine Akte wieder öffnen kann nur die Administration, zum Beispiel nach einem Versehen."
            : `${SORTIERUNG_TEXT[sortierung] ?? "Sortiert"} · Klick auf den Namen öffnet die Akte · Testpatienten (Nr. ab 9001) zählen in keiner Statistik`}
        </span>
        <span className="flex items-center gap-3">
          <span className="num" data-testid="listen-bereich">{daten ? `${zahl(von)}–${zahl(bis)} von ${zahl(daten.count)}` : ""}</span>
          {daten && daten.count > SEITENGROESSE ? (
            <>
              <Knopf klein disabled={!daten.previous} onClick={() => setze({ seite: String(seite - 1) }, true)}>Zurück</Knopf>
              <Knopf klein disabled={!daten.next} onClick={() => setze({ seite: String(seite + 1) }, true)}>Weiter</Knopf>
            </>
          ) : null}
        </span>
      </div>
    </Seite>
  );
}
