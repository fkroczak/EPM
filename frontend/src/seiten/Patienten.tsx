/** Entwurf 3 · Patientenliste (Variante 21 über die Darstellung „Hoher Kontrast“). */
import type { ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuswahl, useVersorgerListe } from "@/lib/daten";
import { datum, heuteIso, kg, nummer, prozent, relativ, terminZeit, zahl } from "@/lib/format";
import { ab, useMobil, useStufe } from "@/lib/stufen";
import { ABSCHLUSSANLAESSE, ERKLAERUNGEN_KURZ, TERMINARTEN } from "@/lib/typen";
import type { Kontakt, Patient, PatientZeile, Trend } from "@/lib/typen";
import { Richtext, klartext } from "@/components/Editor";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Fehleranzeige, Karte, KnopfLink, Knopf, Laden, Leer, Seitenkopf, Segmente, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { HinweisChips } from "@/components/HinweisChips";
import { Begriff } from "@/components/ui/Begriff";

type Zaehler = { in_betreuung: number; abgeschlossen: number; mit_hinweisen: number; gewichtsverlust: number; termin_woche: number };
/** Testpatienten zählen nicht mit; ihre Anzahl kommt getrennt (nicht für Testbenutzer). */
type ZaehlerAntwort = Zaehler & { testpatienten?: { in_betreuung: number; abgeschlossen: number } };

const SEITENGROESSE = 50;

/** „+6 Test“ neben dem Zähler, wenn Testpatienten sichtbar sind. */
function testZahl(n: number | undefined) {
  return n ? <span className="num opacity-70 text-[0.75rem] ml-1" title={`${n} Testpatienten, nicht mitgezählt`}>+{n} Test</span> : null;
}

const SCHNELLFILTER: { wert: string; text: string; zahl: keyof Zaehler }[] = [
  { wert: "hinweise", text: "Nur mit Hinweisen", zahl: "mit_hinweisen" },
  { wert: "gewichtsverlust", text: "Gewichtsverlust", zahl: "gewichtsverlust" },
  { wert: "termin_woche", text: "Termin diese Woche", zahl: "termin_woche" },
];

const PRUEFEN: Record<string, string> = {
  altdokumente: "Altdokumente ohne geprüften Typ",
  nickelallergie: "Nickelallergie nicht erfasst",
  kein_versorger: "Versorger nicht erfasst",
  labor_faellig: "Laborbefund fehlt oder ist zu alt",
  bia_faellig: "BIA-Messung fehlt oder ist zu alt",
  ohne_plan: "Kein Infusionsplan (nicht als „kein Plan nötig“ bestätigt)",
  kein_kontakt: "Kontakt fällig (bald fällig und überfällig)",
  kontakt_bald: "Kontakt bald fällig",
  kontakt_ueberfaellig: "Kontakt überfällig",
  wiedereinbestellung: "Wiedereinbestellung fällig (kein Termin geplant)",
  erklaerungen: "Erklärungen zum Datenschutz fehlen",
  abschluss_pruefen: "Abschluss prüfen (lange kein Kontakt)",
  // fehlende Angaben (F186), aus der Tagesliste der Startseite
  ohne_telefon: "Keine Telefonnummer",
  ohne_hausarzt: "Kein Hausarzt erfasst",
  ohne_diagnose: "Keine Diagnose",
  ohne_gewicht: "Kein aktuelles Gewicht",
  termin_ohne_ort: "Praxistermin ohne Ort",
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
  const { darfBei } = useAuth();
  return (
    <span className="inline-flex gap-1.5 flex-wrap">
      {p.nickelallergie === "ja" ? <Chip art="fehler">Nickelallergie</Chip> : null}
      {p.nickelallergie === "unbekannt" ? <Chip title="Nickelallergie nicht erfasst">Nickel ?</Chip> : null}
      {/* Kontakt fällig in zwei Stufen (S04): überfällig rot, bald fällig gelb.
          Jeder Hinweis lässt sich mit „×“ wegklicken (F119). */}
      <HinweisChips hinweise={p.kennzahlen?.hinweise ?? []} patientId={p.id}
        ausblendbar={!p.ist_abgeschlossen && darfBei("akten_bearbeiten", p)} />
    </span>
  );
}

function NaechsterTermin({ p }: { p: PatientZeile }) {
  const t = p.kennzahlen?.naechster_termin;
  if (!t) return <span className="gedaempft">—</span>;
  return (
    <span className={cx("text-[0.8125rem]", t.faellig_am < heuteIso() && "text-fehler")} title={t.titel}>
      {terminZeit(t.faellig_am, t.uhrzeit)}<br /><span className="gedaempft">{TERMINARTEN[t.art] ?? t.art}</span>
    </span>
  );
}

function PlanZelle({ p }: { p: PatientZeile }) {
  const plan = p.kennzahlen?.plan;
  if (!plan) return <span className="gedaempft">{p.kennzahlen?.kein_plan ? "nicht nötig" : "—"}</span>;
  return (
    <span className="text-[0.8125rem] inline-flex flex-col gap-0.5 items-start">
      {plan.gueltig_ab ? <span className={cx("num", plan.alt && "text-warn")} title={plan.alt ? "älter als eingestellt" : undefined}>seit {datum(plan.gueltig_ab)}</span> : null}
      {plan.entwurf ? <Chip><Begriff name="entwurf">Entwurf</Begriff></Chip> : null}
    </span>
  );
}

function Erklaerungen({ p }: { p: PatientZeile }) {
  const fehlt = p.kennzahlen?.erklaerungen_fehlen ?? [];
  return fehlt.length ? <span className="inline-flex gap-1 flex-wrap">{fehlt.map((a) => <Chip key={a} art="warn">{ERKLAERUNGEN_KURZ[a]}</Chip>)}</span>
    : <Chip art="ok"><Icon name="haken" groesse={12} />vollständig</Chip>;
}


export function Patienten() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { darf } = useAuth();
  const archiv = params.get("status") === "abgeschlossen";
  const versorgerId = params.get("versorger") ?? "";
  const apId = params.get("ansprechpartner") ?? "";
  const katheterId = params.get("katheter") ?? "";
  const schnell = params.get("schnellfilter") ?? "";
  const pruefen = params.get("pruefen") ?? "";
  const sortierung = params.get("ordering") ?? (archiv ? "-abgeschlossen_am" : "-letzter_kontakt");
  const seite = Math.max(1, Number(params.get("seite") ?? "1") || 1);
  // Freitext kommt aus der Suche oben in der Kopfzeile (ein Suchfeld, Vorschlag „Weniger Wege“, 08.10.2026)
  const suche = params.get("suche") ?? "";
  const stufe = useStufe();
  const mobil = useMobil();

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

  const versorger = useVersorgerListe();
  const katheter = useAuswahl("katheter", false);
  const zaehler = useQuery({ queryKey: ["patienten", "zaehler"], queryFn: () => api<ZaehlerAntwort>("patienten/zaehler/") });
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

  // Spalten je Fensterstufe (S16, Entwurf 2): unter 1440 px Nr., Name, Kontakt, Termin, Hinweise; ab 1440 px dazu Geboren,
  // Katheter, Versorger, Gewicht mit Trend; ab 1920 px dazu Plan und Erklärungen (die Vorschau der Akte ab 2560 px entfällt seit 08.10.2026)
  const breit = ab(stufe, "hd");
  const sehrBreit = ab(stufe, "fhd");
  // Keine Vorschau der Akte mehr (Wunsch 08.10.2026): ein Klick auf die Zeile öffnet die Akte
  const oeffnen = (id: number) => (e: { target: EventTarget }) => {
    if ((e.target as HTMLElement).closest("a, button, input, select")) return;
    navigate(`/patienten/${id}`);
  };
  const sortieren = (o: string) => setze({ ordering: o });
  // Leere Liste: sagen, woran es liegen kann, und den nächsten Schritt anbieten (Bedienung für Pflegekräfte, 10.10.2026)
  const zuruecksetzen = () => setParams(archiv ? new URLSearchParams("status=abgeschlossen") : new URLSearchParams());
  const leer = (
    <div className="flex flex-col items-center gap-2.5 py-4 px-3 text-center text-sm" data-testid="liste-leer">
      <span className="gedaempft">
        {suche ? <>Kein Patient zu „{suche}“ {archiv ? "unter den abgeschlossenen Akten" : "in Betreuung"} gefunden.</>
          : gefiltert ? "Keine Patienten passen zu diesen Filtern."
          : archiv ? "Noch keine abgeschlossenen Akten." : "Noch keine Patienten angelegt."}
      </span>
      {suche ? <span className="gedaempft text-[0.8125rem]">Tipp: nur einen Teil des Namens eingeben (z. B. „Mül“), oder nach Nummer bzw.
        Geburtsdatum (14.03.1968) suchen.</span> : null}
      <span className="flex gap-2 flex-wrap justify-center">
        {gefiltert ? <Knopf klein onClick={zuruecksetzen}>Alle Filter entfernen</Knopf> : null}
        {suche && !archiv ? <Knopf klein onClick={() => setParams(new URLSearchParams({ status: "abgeschlossen", suche }))}>
          In abgeschlossenen Akten suchen</Knopf> : null}
        {!archiv && darf("akten_bearbeiten") && (suche || !gefiltert)
          ? <KnopfLink to="/patienten/neu" klein variante="pri" icon="plus">Neuer Patient</KnopfLink> : null}
      </span>
    </div>
  );
  const tabelle = (
    <Karte key="tabelle" className="overflow-x-auto">
      {liste.isLoading ? <Laden /> : (
        <table className="tabelle" aria-busy={liste.isFetching || undefined} data-testid="patientenliste">
          <thead>
            {archiv ? (
              <tr>
                <Spalte feld="nummer" breite="4rem" sortierung={sortierung} onSortieren={sortieren}>Nr.</Spalte>
                <Spalte feld="nachname" sortierung={sortierung} onSortieren={sortieren}>Name</Spalte>
                <Spalte feld="geburtsdatum" sortierung={sortierung} onSortieren={sortieren}>Geboren</Spalte>
                <Spalte sortierung={sortierung} onSortieren={() => undefined}>Katheter</Spalte>
                <Spalte sortierung={sortierung} onSortieren={() => undefined}>Versorger</Spalte>
                <Spalte feld="abgeschlossen_am" sortierung={sortierung} onSortieren={sortieren}>Abgeschlossen</Spalte>
                <Spalte sortierung={sortierung} onSortieren={() => undefined}>Anlass</Spalte>
              </tr>
            ) : (
              <tr>
                <Spalte feld="nummer" breite="4rem" sortierung={sortierung} onSortieren={sortieren}>Nr.</Spalte>
                <Spalte feld="nachname" sortierung={sortierung} onSortieren={sortieren}>Name</Spalte>
                {breit ? <Spalte feld="geburtsdatum" sortierung={sortierung} onSortieren={sortieren}>Geboren</Spalte> : null}
                {breit ? <Spalte sortierung={sortierung} onSortieren={() => undefined}>Katheter</Spalte> : null}
                {breit ? <Spalte sortierung={sortierung} onSortieren={() => undefined}>Versorger</Spalte> : null}
                {breit ? <Spalte rechts sortierung={sortierung} onSortieren={() => undefined}>Gewicht</Spalte> : null}
                {sehrBreit ? <Spalte sortierung={sortierung} onSortieren={() => undefined}>Plan</Spalte> : null}
                <Spalte feld="letzter_kontakt" sortierung={sortierung} onSortieren={sortieren}>Letzter Kontakt</Spalte>
                <Spalte sortierung={sortierung} onSortieren={() => undefined}>Nächster Termin</Spalte>
                {sehrBreit ? <Spalte sortierung={sortierung} onSortieren={() => undefined}>Erklärungen</Spalte> : null}
                <Spalte sortierung={sortierung} onSortieren={() => undefined}>Hinweise</Spalte>
              </tr>
            )}
          </thead>
          <tbody>
            {(daten?.results ?? []).map((p) => archiv ? (
              <tr key={p.id} className="cursor-pointer" onClick={oeffnen(p.id)}>
                <td className="td num gedaempft">{nummer(p.nummer)}</td>
                <td className="td"><Link to={`/patienten/${p.id}`} className="font-medium no-underline text-text2">{p.nachname}, {p.vorname}</Link></td>
                <td className="td num text-text2">{datum(p.geburtsdatum)}</td>
                <td className="td text-text2">{p.katheter_name ?? (p.kein_katheter ? "kein" : "—")}</td>
                <td className="td text-text2">{p.versorger_name ?? (p.kein_versorger ? "kein" : "—")}</td>
                <td className="td num text-text2">{datum(p.abgeschlossen_am)}</td>
                <td className="td gedaempft">{ABSCHLUSSANLAESSE[p.abschluss_anlass] ?? p.abschluss_anlass}</td>
              </tr>
            ) : (
              <tr key={p.id} className="cursor-pointer" onClick={oeffnen(p.id)} data-testid="patientenzeile">
                <td className="td num gedaempft">{nummer(p.nummer)}</td>
                <td className="td">
                  <span className="inline-flex items-center gap-2 flex-wrap">
                    <Link to={`/patienten/${p.id}`} className="font-medium no-underline">{p.nachname}, {p.vorname}</Link>
                    {p.ist_test ? <Chip art="warn"><Begriff name="testpatient">Testpatient</Begriff></Chip> : null}
                  </span>
                  {!breit ? <><br /><span className="text-[0.78rem] gedaempft"><span className="num">{datum(p.geburtsdatum)}</span> ({p.alter})</span></> : null}
                </td>
                {breit ? <td className="td"><span className="num">{datum(p.geburtsdatum)}</span> <span className="gedaempft">({p.alter})</span></td> : null}
                {breit ? <td className="td">{p.katheter_name ?? (p.kein_katheter ? "kein" : "—")}</td> : null}
                {breit ? (
                  <td className="td text-text2">
                    {p.versorger_name ?? (p.kein_versorger ? "kein" : "—")}
                    {p.ansprechpartner_name ? <><br /><span className="text-[0.78rem] gedaempft">{p.ansprechpartner_name}</span></> : null}
                  </td>
                ) : null}
                {breit ? (
                  <td className="td num text-right whitespace-nowrap">
                    {kg(p.kennzahlen?.gewicht?.kg)}<TrendPfeil trend={p.kennzahlen?.trend ?? null} />
                  </td>
                ) : null}
                {sehrBreit ? <td className="td"><PlanZelle p={p} /></td> : null}
                <td className="td text-text2">{relativ(p.kennzahlen?.letzter_kontakt)}</td>
                <td className="td"><NaechsterTermin p={p} /></td>
                {sehrBreit ? <td className="td"><Erklaerungen p={p} /></td> : null}
                <td className="td"><Hinweise p={p} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {daten && daten.count === 0 ? leer : null}
    </Karte>
  );

  // Telefon (Festlegung 08.10.2026): Karten statt Tabelle – Name, Nummer, Geburtsdatum, letzter Kontakt, Termin, Hinweise
  const karten = (
    <div className="flex flex-col gap-2" key="karten">
      {liste.isLoading ? <Laden /> : (
        <div role="list" aria-label={archiv ? "Abgeschlossene Akten" : "Patienten"} className="flex flex-col gap-2" data-testid="patientenliste">
          {(daten?.results ?? []).map((p) => (
            <div key={p.id} role="listitem" className="card flex flex-col">
              <Link to={`/patienten/${p.id}`} className="px-3.5 pt-3 pb-2 flex flex-col gap-0.5 no-underline text-tinte rounded-[0.75rem]">
                <span className="flex items-center justify-between gap-2">
                  <span className="font-medium truncate">{p.nachname}, {p.vorname}</span>
                  <span className="num text-xs gedaempft shrink-0">Nr. {nummer(p.nummer)}</span>
                </span>
                <span className="text-[0.8125rem] gedaempft">
                  <span className="num">{datum(p.geburtsdatum)}</span> ({p.alter})
                  {archiv ? <> · abgeschlossen <span className="num">{datum(p.abgeschlossen_am)}</span></>
                    : <> · Kontakt {relativ(p.kennzahlen?.letzter_kontakt)}{p.kennzahlen?.gewicht ? <> · <span className="num">{kg(p.kennzahlen.gewicht.kg)}</span><TrendPfeil trend={p.kennzahlen?.trend ?? null} /></> : null}</>}
                </span>
              </Link>
              {!archiv ? (
                <div className="px-3.5 pb-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[0.8125rem]">
                  {p.ist_test ? <Chip art="warn"><Begriff name="testpatient">Testpatient</Begriff></Chip> : null}
                  {p.kennzahlen?.naechster_termin ? <NaechsterTermin p={p} /> : null}
                  <Hinweise p={p} />
                </div>
              ) : <span className="pb-1" />}
            </div>
          ))}
        </div>
      )}
      {daten && daten.count === 0 ? leer : null}
    </div>
  );

  const umschalter = (
    <Segmente label="Ansicht" wert={archiv ? "abgeschlossen" : "in_betreuung"}
      onWahl={(w) => {
        const neu = new URLSearchParams();
        if (w === "abgeschlossen") neu.set("status", "abgeschlossen");
        setParams(neu);
      }}
      werte={[
        { wert: "in_betreuung", text: <>In Betreuung <span className="num opacity-70">{z ? zahl(z.in_betreuung) : ""}</span>{testZahl(z?.testpatienten?.in_betreuung)}</> },
        { wert: "abgeschlossen", text: <>Abgeschlossen <span className="num opacity-70">{z ? zahl(z.abgeschlossen) : ""}</span>{testZahl(z?.testpatienten?.abgeschlossen)}</> },
      ]} />
  );

  return (
    <Seite pfad={[{ text: "Patienten" }]}>
      {archiv ? (
        <Seitenkopf titel="Abgeschlossene Akten"
          rechts={umschalter} />
      ) : (
        <Seitenkopf titel="Patienten"
          unter={<span data-testid="zahl-in-betreuung"><span className="num">{z ? zahl(z.in_betreuung) : "…"}</span> Patienten in Betreuung
            {z?.testpatienten?.in_betreuung ? <> · zusätzlich <span className="num">{zahl(z.testpatienten.in_betreuung)}</span> {z.testpatienten.in_betreuung === 1 ? "Testpatient" : "Testpatienten"} (zählen in keiner Statistik)</> : null}</span>}
          rechts={<>
            {umschalter}
            {darf("akten_bearbeiten") ? <KnopfLink to="/patienten/neu" variante="pri" icon="plus">Neuer Patient</KnopfLink> : null}
          </>} />
      )}

      <div className="flex items-center gap-2.5 flex-wrap">
        {suche ? (
          <Chip art="akzent" className="h-[1.875rem]" data-testid="suchbegriff">
            <Icon name="suche" groesse={14} />„{suche}“
            <button type="button" className="bg-transparent border-0 p-0 cursor-pointer text-inherit inline-flex"
              aria-label="Suche entfernen" onClick={() => setze({ suche: null })}><Icon name="x" /></button>
          </Chip>
        ) : null}
        <Auswahl aria-label="Versorger" className="w-[calc(50%-0.35rem)] sm:w-[11.875rem]" value={versorgerId}
          onChange={(e) => setze({ versorger: e.target.value || null, ansprechpartner: null })}>
          <option value="">Alle Versorger</option>
          {(versorger.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.name}{v.aktiv ? "" : " (inaktiv)"}</option>)}
        </Auswahl>
        <Auswahl aria-label="Ansprechpartner" className="w-[calc(50%-0.35rem)] sm:w-[13.125rem]" value={apId}
          onChange={(e) => setze({ ansprechpartner: e.target.value || null })}>
          <option value="">Alle Ansprechpartner</option>
          {ansprechpartner.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.versorger_name})</option>)}
        </Auswahl>
        <Auswahl aria-label="Katheter" className="w-[calc(50%-0.35rem)] sm:w-[10rem]" value={katheterId}
          onChange={(e) => setze({ katheter: e.target.value || null })}>
          <option value="">Alle Katheter</option>
          {(katheter.data ?? []).map((k) => <option key={k.id} value={k.id}>{k.wert}</option>)}
        </Auswahl>
        {!archiv ? (
          <>
            <span className="w-px h-6 bg-rand max-sm:hidden" aria-hidden="true" />
            {SCHNELLFILTER.map((f) => (
              <button key={f.wert} type="button" aria-pressed={schnell === f.wert}
                className={cx("chip h-[1.875rem] cursor-pointer border", schnell === f.wert ? "akzent border-akzent" : "border-rand bg-flaeche text-text2")}
                onClick={() => setze({ schnellfilter: schnell === f.wert ? null : f.wert })}>
                {f.text} <span className="num gedaempft">{z ? zahl(z[f.zahl]) : ""}</span>
              </button>
            ))}
          </>
        ) : null}
        {/* Prüffilter direkt wählbar (vorher nur über Links von Startseite und Datenschutz; 08.10.2026) */}
        <Auswahl aria-label="Prüfen" className={cx("w-full sm:w-[14.375rem]", pruefen && "!border-akzent")} value={pruefen}
          onChange={(e) => setze({ pruefen: e.target.value || null })} data-testid="pruefen">
          <option value="">Prüfen …</option>
          {Object.entries(PRUEFEN).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
          {pruefen && !PRUEFEN[pruefen] ? <option value={pruefen}>{pruefen}</option> : null}
        </Auswahl>
        {gefiltert ? (
          <Knopf variante="geist" klein onClick={zuruecksetzen}>
            Filter zurücksetzen
          </Knopf>
        ) : null}
      </div>

      <Fehleranzeige fehler={liste.error} />
      {mobil ? karten : tabelle}

      <div className="flex justify-between items-center gap-4 text-[0.8125rem] gedaempft flex-wrap">
        <span>
          {archiv
            ? "Eine Akte wieder öffnen kann nur die Administration, zum Beispiel nach einem Versehen."
            : `${SORTIERUNG_TEXT[sortierung] ?? "Sortiert"} · Klick auf die Zeile öffnet die Akte`}
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
