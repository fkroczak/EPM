/** Übersicht „Datenschutz“: was zu tun ist (offene Anfragen mit Frist, Akten mit abgelaufener Aufbewahrung),
 *  welche Akten eingeschränkt sind, und das Löschprotokoll. Die Vorgänge selbst liegen im Reiter „Datenschutz“ der Akte. */
import { Link } from "react-router";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, nummer, zeitpunkt } from "@/lib/format";
import { ERKLAERUNGEN_KURZ } from "@/lib/typen";
import type { DatenschutzUebersicht } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Fehleranzeige, Karte, Laden, Seitenkopf, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";

function Test({ ja }: { ja: boolean }) {
  return ja ? <Chip art="warn">Test</Chip> : null;
}

type Ton = "fehler" | "warn" | "ok";

/** Kennzahl in der Leiste oben: Ampelfarbe nach Lage (0 = erledigt), auf Wunsch ein Weg zur passenden Liste */
function Zahl({ titel, wert, ton, zu, testid }: { titel: string; wert: number; ton: Ton; zu?: string; testid: string }) {
  const inhalt = (<>
    <span className="flex items-center gap-2">
      <span className={cx("ds-punkt", ton)} aria-hidden="true" />
      <span className="num text-[1.625rem] font-semibold leading-none" data-testid={testid}>{wert}</span>
    </span>
    <span className="text-[0.8125rem] gedaempft leading-snug">{titel}</span>
  </>);
  const klasse = "ds-zahl flex flex-col gap-1.5 px-4 py-3.5 min-w-0";
  return zu
    ? <Link to={zu} className={cx(klasse, "no-underline text-tinte hover:bg-fein")}>{inhalt}</Link>
    : <div className={klasse}>{inhalt}</div>;
}

/** Abschnitt: Symbol, Titel mit Anzahl, Erklärung; leer zeigt er „erledigt“ statt einer leeren Tabelle */
function Abschnitt({ icon, titel, anzahl, ton, unter, leer, children, fuss, testid }: {
  icon: string; titel: string; anzahl: number; ton: Ton; unter?: ReactNode; leer: string; children: ReactNode; fuss?: ReactNode; testid?: string;
}) {
  return (
    <Karte className="overflow-hidden" data-testid={testid}>
      <div className="px-5 pt-4 pb-3 flex items-start gap-3">
        <span className={cx("ds-symbol", anzahl ? ton : "ok")} aria-hidden="true"><Icon name={icon} groesse={18} /></span>
        <div className="flex flex-col gap-1 min-w-0">
          <h2 className="lbl m-0 text-[0.9375rem] flex items-center gap-2 flex-wrap">
            {titel}{anzahl ? <Chip art={ton === "ok" ? "neutral" : ton}>{anzahl}</Chip> : null}
          </h2>
          {unter ? <span className="text-[0.8125rem] gedaempft leading-normal">{unter}</span> : null}
        </div>
      </div>
      {anzahl ? children : (
        <div className="mx-5 mb-4 px-3.5 py-2.5 rounded-lg bg-ok-bg text-ok text-sm flex items-center gap-2">
          <Icon name="haken" groesse={16} /> {leer}
        </div>
      )}
      {fuss}
    </Karte>
  );
}

export function Datenschutz() {
  const { darf } = useAuth();
  const daten = useQuery({ queryKey: ["datenschutz"], queryFn: () => api<DatenschutzUebersicht>("datenschutz/") });
  const d = daten.data;
  return (
    <Seite pfad={[{ text: "Datenschutz" }]}>
      <Seitenkopf titel="Datenschutz" unter="Anfragen von Betroffenen, Aufbewahrung, eingeschränkte Akten und Löschprotokoll – die Vorgänge selbst im Reiter „Datenschutz“ der Akte" />
      {daten.isLoading ? <Laden /> : !d ? <Fehleranzeige fehler={daten.error ?? "Nicht geladen."} /> : (<>
        <section aria-label="Kennzahlen" className="card ds-zahlen grid grid-cols-2 md:grid-cols-5 overflow-hidden" data-testid="datenschutz-zahlen">
          <Zahl titel="offene Anfragen" wert={d.anfragen_offen.length} ton={d.anfragen_offen.length ? "warn" : "ok"} testid="zahl-anfragen" />
          <Zahl titel="davon überfällig" wert={d.anfragen_ueberfaellig} ton={d.anfragen_ueberfaellig ? "fehler" : "ok"} testid="zahl-ueberfaellig" />
          <Zahl titel="Akten mit abgelaufener Aufbewahrung" wert={d.aufbewahrung_abgelaufen.length} ton={d.aufbewahrung_abgelaufen.length ? "warn" : "ok"}
            testid="zahl-abgelaufen" />
          <Zahl titel="Akten, in denen Erklärungen fehlen" wert={d.erklaerungen_fehlen} ton={d.erklaerungen_fehlen ? "warn" : "ok"}
            zu="/patienten?pruefen=erklaerungen" testid="zahl-erklaerungen" />
          <Zahl titel={`Abschluss prüfen (kein Kontakt seit ${d.einstellungen.abschluss_pruefen_monate} Monaten)`} wert={d.abschluss_pruefen}
            ton={d.abschluss_pruefen ? "warn" : "ok"} zu="/patienten?pruefen=abschluss_pruefen" testid="zahl-abschluss" />
        </section>

        {/* breite Fenster: links was zu tun ist und der Nachweis, rechts Fristen, Einschränkungen und Einstellungen */}
        <div className="grid grid-cols-1 hd:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)] gap-[var(--abstand)] items-start">
          <div className="stapel flex flex-col min-w-0">
            <Abschnitt icon="sprechblase" titel="Offene Anfragen" anzahl={d.anfragen_offen.length} ton={d.anfragen_ueberfaellig ? "fehler" : "warn"}
              unter="Auskunft, Berichtigung, Löschung, Einschränkung oder Widerspruch – mit Frist zur Antwort." leer="Keine offenen Anfragen."
              fuss={d.anfragen_verborgen ? (
                <div className="px-5 py-3 border-t border-rand text-[0.8125rem] gedaempft" data-testid="anfragen-verborgen">
                  Dazu {d.anfragen_verborgen === 1 ? "kommt 1 offene Anfrage" : `kommen ${d.anfragen_verborgen} offene Anfragen`} zu Akten mit eingeschränkter Verarbeitung – sichtbar für Personen, die über Anfragen entscheiden.
                </div>
              ) : null}>
              <table className="tabelle" data-testid="offene-anfragen">
                <thead><tr><th className="th">Frist</th><th className="th">Anfrage</th><th className="th">Akte</th><th className="th">eingegangen</th><th className="th">erfasst von</th></tr></thead>
                <tbody>
                  {d.anfragen_offen.map((a) => (
                    <tr key={a.id}>
                      <td className="td"><Chip art={a.ueberfaellig ? "fehler" : "warn"}>{a.ueberfaellig ? "überfällig seit" : "bis"} {datum(a.frist_bis)}{a.frist_verlaengert ? " (verlängert)" : ""}</Chip></td>
                      <td className="td">{a.art_name}{a.gestellt_von ? <span className="gedaempft"> · {a.gestellt_von}</span> : null}</td>
                      <td className="td"><Link to={`/patienten/${a.patient}/datenschutz`} className="font-medium underline underline-offset-2">{a.patient_name}</Link>{" "}
                        <span className="num gedaempft">Nr. {nummer(a.patient_nummer)}</span> <Test ja={a.patient_ist_test} />
                        {a.patient_eingeschraenkt ? <> <Chip art="warn">eingeschränkt</Chip></> : null}</td>
                      <td className="td num">{datum(a.eingegangen_am)}</td>
                      <td className="td">{a.erfasst_von_name ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Abschnitt>

            <Abschnitt icon="dokument" titel="Löschprotokoll" anzahl={d.loeschprotokoll.length} ton="ok" leer="Noch keine Akte gelöscht."
              unter="Endgültig gelöschte Akten – ohne Namen und Inhalte. Der Nachweis, dass und warum gelöscht wurde; unveränderlich.">
              <table className="tabelle" data-testid="loeschprotokoll">
                <thead><tr><th className="th">gelöscht am</th><th className="th">Akte</th><th className="th">Rechtsgrund</th><th className="th">Grund</th><th className="th">Umfang</th><th className="th">von</th></tr></thead>
                <tbody>
                  {d.loeschprotokoll.map((x) => (
                    <tr key={x.id}>
                      <td className="td num whitespace-nowrap">{zeitpunkt(x.geloescht_am)}</td>
                      <td className="td num">Nr. {nummer(x.nummer)} <Test ja={x.ist_test} /></td>
                      <td className="td">{x.rechtsgrund_name}{x.aufbewahrung_bis ? <span className="block text-[0.8125rem] gedaempft">Frist bis {datum(x.aufbewahrung_bis)}</span> : null}</td>
                      <td className="td text-sm">{x.grund}</td>
                      <td className="td text-[0.8125rem] gedaempft">{["kontakte", "gewichte", "termine", "infusionsplaene", "dokumente"].map((k) => `${x.umfang[k] ?? 0} ${({ kontakte: "Kontakte", gewichte: "Gewichte", termine: "Termine", infusionsplaene: "Pläne", dokumente: "Dokumente" } as Record<string, string>)[k]}`).join(" · ")}</td>
                      <td className="td">{x.geloescht_von ?? <span className="gedaempft">System</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Abschnitt>
          </div>

          <div className="stapel flex flex-col min-w-0">
            <Abschnitt icon="uhr" titel="Aufbewahrung abgelaufen" anzahl={d.aufbewahrung_abgelaufen.length} ton="warn" leer="Keine Akte mit abgelaufener Frist."
              unter={<>Abgeschlossen vor mehr als {d.einstellungen.aufbewahrung_jahre} Jahren. Löschen kann ein Mediziner im Reiter „Datenschutz“ der Akte –
                oder die Aufbewahrung im Einzelfall verlängern.</>}
              fuss={d.aufbewahrung_laeuft_ab.length ? (
                <div className="px-5 py-3 border-t border-rand text-[0.8125rem]" data-testid="laeuft-ab">
                  <span className="gedaempft">Frist läuft in den nächsten 12 Monaten ab: </span>
                  {d.aufbewahrung_laeuft_ab.map((p, i) => (
                    <span key={p.id}>{i ? " · " : ""}<Link to={`/patienten/${p.id}/datenschutz`}>{p.name ?? `Akte Nr. ${nummer(p.nummer)}`}</Link> ({datum(p.aufbewahrung_bis)})</span>
                  ))}
                </div>
              ) : null}>
              <table className="tabelle" data-testid="abgelaufen">
                <thead><tr><th className="th">Akte</th><th className="th">abgeschlossen</th><th className="th">Frist bis</th></tr></thead>
                <tbody>
                  {d.aufbewahrung_abgelaufen.map((p) => (
                    <tr key={p.id}>
                      <td className="td"><Link to={`/patienten/${p.id}/datenschutz`} className="font-medium underline underline-offset-2">{p.name ?? "Akte"}</Link>{" "}
                        <span className="num gedaempft">Nr. {nummer(p.nummer)}</span> <Test ja={p.ist_test} />
                        {p.eingeschraenkt ? <> <Chip art="warn">eingeschränkt</Chip></> : null}</td>
                      <td className="td num">{datum(p.abgeschlossen_am)}</td>
                      <td className="td num">{datum(p.aufbewahrung_bis)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Abschnitt>

            <Abschnitt icon="auge_zu" titel="Verarbeitung eingeschränkt" anzahl={d.eingeschraenkt.length} ton="warn" leer="Keine eingeschränkte Akte."
              unter="Diese Akten erscheinen in keiner Liste und keiner Suche; lesbar nur mit begründeter Einsicht. Name und Grund sieht nur, wer Einsicht nehmen darf (wer über Anfragen entscheidet; die Administration nur bei Testpatienten) – alle anderen sehen die Nummer.">
              <table className="tabelle" data-testid="eingeschraenkte">
                <thead><tr><th className="th">Akte</th><th className="th">seit</th><th className="th">Grund</th></tr></thead>
                <tbody>
                  {d.eingeschraenkt.map((p) => (
                    <tr key={p.id}>
                      <td className="td"><Link to={`/patienten/${p.id}`} className="font-medium underline underline-offset-2">{p.name ?? "Akte"}</Link>{" "}
                        <span className="num gedaempft">Nr. {nummer(p.nummer)}</span> <Test ja={p.ist_test} /></td>
                      <td className="td num">{datum(p.am)}</td>
                      <td className="td text-sm">{p.grund ?? <span className="gedaempft">—</span>}{p.von ? <span className="gedaempft"> · {p.von}</span> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Abschnitt>

            <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="datenschutz-einstellungen">
              <h2 className="lbl m-0 text-[0.9375rem] flex items-center gap-2"><Icon name="schloss" groesse={16} /> Eingestellt</h2>
              <span className="text-sm leading-normal">Aufbewahrung {d.einstellungen.aufbewahrung_jahre} Jahre nach Abschluss der Akte · Audit-Log{" "}
                {d.einstellungen.protokoll_aufbewahrung_jahre ? `${d.einstellungen.protokoll_aufbewahrung_jahre} Jahre` : "unbegrenzt"}</span>
              <div className="flex flex-col gap-1.5">
                <span className="text-[0.8125rem] gedaempft">Erklärungen, die vorliegen sollen:</span>
                <span className="flex gap-1.5 flex-wrap">
                  {d.einstellungen.pflicht_erklaerungen.length
                    ? d.einstellungen.pflicht_erklaerungen.map((a) => <Chip key={a} art="akzent">{ERKLAERUNGEN_KURZ[a]}</Chip>)
                    : <span className="text-sm gedaempft">keine</span>}
                </span>
              </div>
              {darf("vorlagen_pflegen") ? <Link to="/admin/vorlagen" className="text-[0.8125rem] font-medium self-start">Ändern unter Vorlagen › Grenzwerte</Link> : null}
            </Karte>
          </div>
        </div>
      </>)}
    </Seite>
  );
}
