/**
 * Infoblatt an die Praxis (F177, baut auf der Patientenankündigung F173 auf): alle Patienten mit einem Sprechstundentermin
 * in der Praxis Dr. Holtmeier in einem Zeitraum – als PDF (Fax) oder fertige E-Mail.
 *
 * Oben der Zeitraum (nächste Woche, übernächste Woche, nächster Monat oder eigener), darunter Ort und Telefontermine,
 * dann die Vorschau: wer auf dem Blatt steht (nach Tagen, „neu“ seit dem letzten Infoblatt), Termine ohne Ort als Warnung
 * und wann zuletzt ein Infoblatt erstellt wurde. Die Vorschau kommt aus POST /api/kalender/ankuendigung/ mit
 * ``ausgabe: "liste"``; PDF und E-Mail wie bei den anderen Schreiben (SchreibenDialog).
 */
import { useState } from "react";
import { Link } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuswahl } from "@/lib/daten";
import { datum, heuteIso, zeitpunkt } from "@/lib/format";
import type { Termin } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Knopf, Laden, Meldung, cx } from "@/components/ui/basis";
import { SchreibenDialog } from "@/components/SchreibenDialog";
import { TerminDialog } from "@/components/TerminDialog";

type Zeile = { termin: number; patient: number; name: string; datum: string; uhrzeit: string | null; hinweis?: string; neu?: boolean;
  vorher?: { datum: string; uhrzeit: string | null } | null };
export type InfoblattVorschau = {
  von: string; bis: string; ort: { id: number; wert: string } | null; telefon_mit: boolean; anzahl: number;
  termine: Zeile[]; ohne_ort: Zeile[];
  entfallen: { termin: number; patient: number | null; name: string | null; datum: string; uhrzeit: string | null }[];
  letzte: { erstellt_am: string; von_name: string | null; von: string; bis: string; anzahl: number; ausgabe: "pdf" | "eml" } | null;
};
type Wahl = "woche" | "woche2" | "monat" | "eigen";

const WOCHENTAGE = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];
const tag = (iso: string) => new Date(`${iso}T00:00:00Z`);
const iso = (d: Date) => d.toISOString().slice(0, 10);
const plus = (isoDatum: string, tage: number) => { const d = tag(isoDatum); d.setUTCDate(d.getUTCDate() + tage); return iso(d); };
const kurz = (isoDatum: string) => datum(isoDatum).slice(0, 6);
const langerTag = (isoDatum: string) => `${WOCHENTAGE[tag(isoDatum).getUTCDay()]}, ${datum(isoDatum)}`;
const zeitraumText = (von: string, bis: string) => (von === bis ? datum(von) : `${kurz(von)} bis ${datum(bis)}`);

/** Nächste Woche (Mo–So), übernächste Woche und nächster Kalendermonat ab heute */
function vorschlaege(heute: string): Record<Exclude<Wahl, "eigen">, [string, string]> {
  const montag = plus(heute, 7 - ((tag(heute).getUTCDay() + 6) % 7));
  const h = tag(heute);
  const erster = new Date(Date.UTC(h.getUTCFullYear(), h.getUTCMonth() + 1, 1));
  const letzter = new Date(Date.UTC(h.getUTCFullYear(), h.getUTCMonth() + 2, 0));
  return { woche: [montag, plus(montag, 6)], woche2: [plus(montag, 7), plus(montag, 13)], monat: [iso(erster), iso(letzter)] };
}

const WAHLEN: { wert: Wahl; text: string }[] = [
  { wert: "woche", text: "Nächste Woche" }, { wert: "woche2", text: "Übernächste Woche" },
  { wert: "monat", text: "Nächster Monat" }, { wert: "eigen", text: "Eigener Zeitraum" },
];

export function AnkuendigungDialog({ offen, onOffen, von: vonVorgabe, bis: bisVorgabe, rhythmus }: {
  offen: boolean; onOffen: (o: boolean) => void;
  /** fester Zeitraum (Hinweis auf der Startseite); sonst „Nächste Woche“ bzw. „Nächster Monat“ je nach Einstellung */
  von?: string; bis?: string;
  rhythmus?: string;
}) {
  const orte = useAuswahl("terminort");
  const qc = useQueryClient();
  const heute = heuteIso();
  const vorschlag = vorschlaege(heute);
  const vorgabe: Wahl = vonVorgabe && bisVorgabe
    ? ((Object.keys(vorschlag) as Exclude<Wahl, "eigen">[]).find((w) => vorschlag[w][0] === vonVorgabe && vorschlag[w][1] === bisVorgabe) ?? "eigen")
    : rhythmus === "monat" ? "monat" : "woche";
  const [wahl, setWahl] = useState<Wahl | null>(null);
  const [eigen, setEigen] = useState<{ von?: string; bis?: string }>({});
  const [ort, setOrt] = useState<string | null>(null);
  const [telefon, setTelefon] = useState(false);
  const [ortFehlt, setOrtFehlt] = useState<Termin | null>(null);
  const w = wahl ?? vorgabe;
  const [von, bis] = w === "eigen"
    ? [eigen.von ?? vonVorgabe ?? vorschlag.woche[0], eigen.bis ?? bisVorgabe ?? vorschlag.woche[1]]
    : vorschlag[w];
  const holtmeier = orte.data?.find((o) => /holtmeier/i.test(o.wert));
  const ortId = ort ?? (holtmeier ? String(holtmeier.id) : "");
  const datumOk = /^\d{4}-\d{2}-\d{2}$/.test(von) && /^\d{4}-\d{2}-\d{2}$/.test(bis) && von <= bis;
  const koerper = { von, bis, ort: ortId ? Number(ortId) : null, telefon_mit: telefon };
  const vorschau = useQuery({
    // beginnt mit „kalender“: nach dem Ändern eines Termins (auch hier über „Ort eintragen“) neu laden
    queryKey: ["kalender", "infoblatt", koerper],
    queryFn: () => api<InfoblattVorschau>("kalender/ankuendigung/", { body: { ...koerper, ausgabe: "liste" } }),
    enabled: offen && datumOk && !!orte.data,
    placeholderData: (vorher: InfoblattVorschau | undefined) => vorher,
  });
  const v = vorschau.data;
  const ortName = v?.ort?.wert ?? null;
  const schliessen = (o: boolean) => {
    if (!o) { setWahl(null); setEigen({}); setOrt(null); setTelefon(false); }
    onOffen(o);
  };
  const ortEintragen = async (id: number) => setOrtFehlt(await api<Termin>(`termine/${id}/`));

  // nach Tagen gruppiert
  const tage = new Map<string, Zeile[]>();
  for (const t of v?.termine ?? []) tage.set(t.datum, [...(tage.get(t.datum) ?? []), t]);
  const anzahl = v?.anzahl ?? 0;
  const neue = (v?.termine ?? []).filter((t) => t.neu).length;

  return (
    <>
      <SchreibenDialog offen={offen} onOffen={schliessen}
        titel="Infoblatt an die Praxis" pfad="kalender/ankuendigung/" bereit={datumOk && anzahl > 0}
        ohneEmpfaenger="E-Mail-Adresse der Praxis eintragen – oder hier leer lassen und im Entwurf ergänzen."
        koerper={koerper}
        onErzeugt={() => { void qc.invalidateQueries({ queryKey: ["kalender", "infoblatt"] }); void qc.invalidateQueries({ queryKey: ["startseite"] }); }}
        optionen={<div className="flex flex-col gap-4" data-testid="infoblatt">
          <fieldset className="border-0 p-0 m-0 flex flex-col gap-2">
            <legend className="text-sm font-medium mb-2">Für welchen Zeitraum?</legend>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" data-testid="infoblatt-zeitraum">
              {WAHLEN.map((x) => (
                <Knopf key={x.wert} variante={w === x.wert ? "pri" : "sec"} aria-pressed={w === x.wert}
                  className="min-h-12 justify-center whitespace-normal leading-tight" onClick={() => setWahl(x.wert)}>{x.text}</Knopf>
              ))}
            </div>
            {w === "eigen" ? (
              <div className="grid grid-cols-2 gap-3 sm:max-w-[22rem]">
                <Feld label="von">{(p) => <Eingabe {...p} type="date" value={von} onChange={(e) => setEigen({ von: e.target.value, bis })} />}</Feld>
                <Feld label="bis" fehler={datumOk || !von || !bis ? undefined : "„bis“ liegt vor „von“."}>
                  {(p) => <Eingabe {...p} type="date" value={bis} onChange={(e) => setEigen({ von, bis: e.target.value })} />}</Feld>
              </div>
            ) : <span className="text-sm gedaempft" data-testid="infoblatt-zeitraum-text">{langerTag(von)} bis {langerTag(bis)}</span>}
          </fieldset>
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:items-end">
            <Feld label="Ort der Sprechstunde">
              {(p) => (
                <Auswahl {...p} value={ortId} onChange={(e) => setOrt(e.target.value)}>
                  <option value="">– alle Praxistermine –</option>
                  {(orte.data ?? []).map((o) => <option key={o.id} value={o.id}>{o.wert}</option>)}
                </Auswahl>
              )}
            </Feld>
            <label className={cx("flex items-center gap-2 text-sm min-h-10", !ortId && "gedaempft")}>
              <input type="checkbox" checked={telefon} disabled={!ortId} onChange={(e) => setTelefon(e.target.checked)} />
              Telefon- und Videotermine auch aufführen (mit Telefonnummer)
            </label>
          </div>

          <section className="flex flex-col gap-2.5 border border-rand rounded-lg px-3 py-3" aria-labelledby="infoblatt-vorschau"
            data-testid="infoblatt-vorschau">
            <h3 id="infoblatt-vorschau" className="m-0 text-base font-semibold">
              {!v ? "Vorschau" : anzahl === 0 ? "Keine Patienten auf dem Infoblatt" : anzahl === 1 ? "Dieser Patient steht auf dem Infoblatt" : `Diese ${anzahl} Patienten stehen auf dem Infoblatt`}
              {neue ? <Chip art="akzent" className="ml-2 align-middle">{neue} neu</Chip> : null}
            </h3>
            {v?.letzte ? (
              <span className="text-[0.8125rem] gedaempft" data-testid="infoblatt-letzte">
                Zuletzt erstellt am {zeitpunkt(v.letzte.erstellt_am)} Uhr{v.letzte.von_name ? ` von ${v.letzte.von_name}` : ""} für{" "}
                {zeitraumText(v.letzte.von, v.letzte.bis)} ({v.letzte.anzahl} {v.letzte.anzahl === 1 ? "Patient" : "Patienten"},{" "}
                {v.letzte.ausgabe === "eml" ? "E-Mail" : "PDF"}). „neu“ = seitdem dazugekommen oder verschoben.
              </span>
            ) : v ? <span className="text-[0.8125rem] gedaempft">Für diesen Zeitraum wurde noch kein Infoblatt erstellt.</span> : null}
            {!datumOk ? null : !v && vorschau.isLoading ? <Laden text="Termine werden gesucht …" /> : <Fehleranzeige fehler={vorschau.error} />}
            {v && anzahl === 0 ? (
              <p className="m-0 py-2 text-sm" data-testid="infoblatt-leer">
                {ortName ? `In diesem Zeitraum sind keine Termine in der ${ortName} eingetragen.` : "In diesem Zeitraum sind keine Praxistermine eingetragen."}
                {" "}Termine trägst du im Kalender mit der Art „Praxistermin“ ein.
              </p>
            ) : null}
            {tage.size ? (
              <div className="flex flex-col gap-2.5 sm:max-h-[18rem] sm:overflow-y-auto overscroll-contain" data-testid="infoblatt-liste">
                {[...tage.entries()].map(([d, zeilen]) => (
                  <div key={d} className="flex flex-col gap-1">
                    <h4 className="m-0 lbl">{langerTag(d)}</h4>
                    <ul className="m-0 p-0 list-none flex flex-col gap-1">
                      {zeilen.map((t) => (
                        <li key={t.termin} className="flex items-baseline gap-x-3 gap-y-0.5 flex-wrap text-sm">
                          <span className="num w-12 shrink-0">{t.uhrzeit ?? "—"}</span>
                          <Link to={`/patienten/${t.patient}`} className="font-medium">{t.name}</Link>
                          {t.hinweis ? <span className="gedaempft">{t.hinweis}</span> : null}
                          {t.neu ? <Chip art="akzent" title={t.vorher ? undefined : "seit dem letzten Infoblatt dazugekommen"}>
                            {t.vorher ? `verschoben, vorher ${kurz(t.vorher.datum)}${t.vorher.uhrzeit ? ` ${t.vorher.uhrzeit}` : ""}` : "neu"}</Chip> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ) : null}
            {v?.ohne_ort.length ? (
              <Meldung art="warn" className="flex flex-col gap-1.5">
                <strong data-testid="infoblatt-ohne-ort">Bei diesen Terminen fehlt der Ort – bitte im Termin eintragen.</strong>
                <span className="text-[0.8125rem]">Ohne Ort stehen sie nicht auf dem Infoblatt.</span>
                <ul className="m-0 p-0 list-none flex flex-col gap-1">
                  {v.ohne_ort.map((t) => (
                    <li key={t.termin} className="flex items-center gap-x-3 gap-y-1 flex-wrap text-sm">
                      <span className="num">{kurz(t.datum)} {t.uhrzeit ?? ""}</span>
                      <Link to={`/patienten/${t.patient}`} className="font-medium">{t.name}</Link>
                      <Knopf klein onClick={() => void ortEintragen(t.termin)}>Ort eintragen</Knopf>
                    </li>
                  ))}
                </ul>
              </Meldung>
            ) : null}
            {v?.entfallen.length ? (
              <Meldung art="info" className="flex flex-col gap-1">
                <span>Stand auf dem letzten Infoblatt, jetzt nicht mehr (abgesagt, verschoben oder anderer Ort):</span>
                <ul className="m-0 pl-4">
                  {v.entfallen.map((t) => (
                    <li key={t.termin} className="text-sm">{kurz(t.datum)} {t.uhrzeit ?? ""} {t.name ?? "Termin entfernt"}</li>
                  ))}
                </ul>
              </Meldung>
            ) : null}
          </section>
          <span className="text-[0.8125rem] gedaempft">Hinweise wie „1 h, Neuaufnahme“ oder „+ Labor“ im Termin unter „bei/Ort“ eintragen –
            sie stehen auf dem Infoblatt hinter dem Namen. Testpatienten erscheinen nicht.</span>
        </div>} />
      <TerminDialog offen={!!ortFehlt} onOffen={(o) => { if (!o) setOrtFehlt(null); }} termin={ortFehlt}
        patientName={ortFehlt?.patient_name} />
    </>
  );
}
