/** Übersicht „Datenschutz“: was zu tun ist (offene Anfragen mit Frist, Akten mit abgelaufener Aufbewahrung),
 *  welche Akten eingeschränkt sind, und das Löschprotokoll. Die Vorgänge selbst liegen im Reiter „Datenschutz“ der Akte. */
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, nummer, zeitpunkt } from "@/lib/format";
import { ERKLAERUNGEN_KURZ } from "@/lib/typen";
import type { DatenschutzUebersicht } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Fehleranzeige, Karte, Laden, Leer, Seitenkopf } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";

function Test({ ja }: { ja: boolean }) {
  return ja ? <Chip art="warn">Test</Chip> : null;
}

function Zahl({ titel, wert, zu, testid }: { titel: string; wert: number; zu?: string; testid: string }) {
  const inhalt = (<>
    <span className="num text-[1.5rem] font-semibold leading-none" data-testid={testid}>{wert}</span>
    <span className="text-[0.8125rem] gedaempft">{titel}</span>
  </>);
  return zu
    ? <Link to={zu} className="card px-4 py-3 flex flex-col gap-1 no-underline text-tinte hover:bg-fein">{inhalt}</Link>
    : <div className="card px-4 py-3 flex flex-col gap-1">{inhalt}</div>;
}

export function Datenschutz() {
  const { darf } = useAuth();
  const daten = useQuery({ queryKey: ["datenschutz"], queryFn: () => api<DatenschutzUebersicht>("datenschutz/") });
  const d = daten.data;
  return (
    <Seite pfad={[{ text: "Datenschutz" }]}>
      <Seitenkopf titel="Datenschutz" unter="Anfragen betroffener Personen, Aufbewahrungsfristen, eingeschränkte Akten und das Löschprotokoll." />
      {daten.isLoading ? <Laden /> : !d ? <Fehleranzeige fehler={daten.error ?? "Nicht geladen."} /> : (<>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="datenschutz-zahlen">
          <Zahl titel="offene Anfragen" wert={d.anfragen_offen.length} testid="zahl-anfragen" />
          <Zahl titel="davon überfällig" wert={d.anfragen_ueberfaellig} testid="zahl-ueberfaellig" />
          <Zahl titel="Akten mit abgelaufener Aufbewahrung" wert={d.aufbewahrung_abgelaufen.length} testid="zahl-abgelaufen" />
          <Zahl titel="Akten, in denen Erklärungen fehlen" wert={d.erklaerungen_fehlen} zu="/patienten?pruefen=erklaerungen" testid="zahl-erklaerungen" />
          <Zahl titel={`Abschluss prüfen (kein Kontakt seit ${d.einstellungen.abschluss_pruefen_monate} Monaten)`} wert={d.abschluss_pruefen}
            zu="/patienten?pruefen=abschluss_pruefen" testid="zahl-abschluss" />
        </div>

        <Karte className="overflow-hidden">
          <h2 className="lbl m-0 px-5 pt-[18px] pb-2 text-[0.9375rem]">Offene Anfragen</h2>
          {d.anfragen_offen.length ? (
            <table className="tabelle" data-testid="offene-anfragen">
              <thead><tr><th className="th">Frist</th><th className="th">Anfrage</th><th className="th">Akte</th><th className="th">eingegangen</th><th className="th">erfasst von</th></tr></thead>
              <tbody>
                {d.anfragen_offen.map((a) => (
                  <tr key={a.id}>
                    <td className="td"><Chip art={a.ueberfaellig ? "fehler" : "warn"}>{a.ueberfaellig ? "überfällig seit" : "bis"} {datum(a.frist_bis)}{a.frist_verlaengert ? " (verlängert)" : ""}</Chip></td>
                    <td className="td">{a.art_name}{a.gestellt_von ? <span className="gedaempft"> · {a.gestellt_von}</span> : null}</td>
                    <td className="td"><Link to={`/patienten/${a.patient}/datenschutz`} className="font-medium no-underline">{a.patient_name}</Link>{" "}
                      <span className="num gedaempft">Nr. {nummer(a.patient_nummer)}</span> <Test ja={a.patient_ist_test} />
                      {a.patient_eingeschraenkt ? <> <Chip art="warn">eingeschränkt</Chip></> : null}</td>
                    <td className="td num">{datum(a.eingegangen_am)}</td>
                    <td className="td">{a.erfasst_von_name ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <Leer>Keine offenen Anfragen.</Leer>}
          {d.anfragen_verborgen ? (
            <div className="px-5 py-3 border-t border-rand text-[0.8125rem] gedaempft" data-testid="anfragen-verborgen">
              Dazu {d.anfragen_verborgen === 1 ? "kommt 1 offene Anfrage" : `kommen ${d.anfragen_verborgen} offene Anfragen`} zu Akten mit eingeschränkter Verarbeitung – sichtbar für Personen, die über Anfragen entscheiden.
            </div>
          ) : null}
        </Karte>

        <div className="stapel grid grid-cols-1 hd:grid-cols-2 fhd:grid-cols-3 gap-5 items-start">
          <Karte className="overflow-hidden">
            <div className="px-5 pt-[18px] pb-2 flex flex-col gap-1">
              <h2 className="lbl m-0 text-[0.9375rem]">Aufbewahrung abgelaufen</h2>
              <span className="text-[0.8125rem] gedaempft">Abgeschlossen vor mehr als {d.einstellungen.aufbewahrung_jahre} Jahren. Löschen kann ein
                Mediziner im Reiter „Datenschutz“ der Akte – oder die Aufbewahrung im Einzelfall verlängern.</span>
            </div>
            {d.aufbewahrung_abgelaufen.length ? (
              <table className="tabelle" data-testid="abgelaufen">
                <thead><tr><th className="th">Akte</th><th className="th">abgeschlossen</th><th className="th">Frist bis</th></tr></thead>
                <tbody>
                  {d.aufbewahrung_abgelaufen.map((p) => (
                    <tr key={p.id}>
                      <td className="td"><Link to={`/patienten/${p.id}/datenschutz`} className="font-medium no-underline">{p.name ?? "Akte"}</Link>{" "}
                        <span className="num gedaempft">Nr. {nummer(p.nummer)}</span> <Test ja={p.ist_test} />
                        {p.eingeschraenkt ? <> <Chip art="warn">eingeschränkt</Chip></> : null}</td>
                      <td className="td num">{datum(p.abgeschlossen_am)}</td>
                      <td className="td num">{datum(p.aufbewahrung_bis)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Leer>Keine Akte mit abgelaufener Frist.</Leer>}
            {d.aufbewahrung_laeuft_ab.length ? (
              <div className="px-5 py-3 border-t border-rand text-[0.8125rem]" data-testid="laeuft-ab">
                <span className="gedaempft">Frist läuft in den nächsten 12 Monaten ab: </span>
                {d.aufbewahrung_laeuft_ab.map((p, i) => (
                  <span key={p.id}>{i ? " · " : ""}<Link to={`/patienten/${p.id}/datenschutz`}>{p.name ?? `Akte Nr. ${nummer(p.nummer)}`}</Link> ({datum(p.aufbewahrung_bis)})</span>
                ))}
              </div>
            ) : null}
          </Karte>

          <Karte className="overflow-hidden">
            <div className="px-5 pt-[18px] pb-2 flex flex-col gap-1">
              <h2 className="lbl m-0 text-[0.9375rem]">Verarbeitung eingeschränkt</h2>
              <span className="text-[0.8125rem] gedaempft">Diese Akten erscheinen in keiner Liste und keiner Suche. Lesbar sind sie nur mit begründeter Einsicht. Name und Grund sieht hier nur, wer Einsicht nehmen darf (wer über Anfragen entscheidet; die Administration nur bei Testpatienten) – alle anderen sehen die Nummer.</span>
            </div>
            {d.eingeschraenkt.length ? (
              <table className="tabelle" data-testid="eingeschraenkte">
                <thead><tr><th className="th">Akte</th><th className="th">seit</th><th className="th">Grund</th></tr></thead>
                <tbody>
                  {d.eingeschraenkt.map((p) => (
                    <tr key={p.id}>
                      <td className="td"><Link to={`/patienten/${p.id}`} className="font-medium no-underline">{p.name ?? "Akte"}</Link>{" "}
                        <span className="num gedaempft">Nr. {nummer(p.nummer)}</span> <Test ja={p.ist_test} /></td>
                      <td className="td num">{datum(p.am)}</td>
                      <td className="td text-sm">{p.grund ?? <span className="gedaempft">—</span>}{p.von ? <span className="gedaempft"> · {p.von}</span> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <Leer>Keine eingeschränkte Akte.</Leer>}
          </Karte>
        </div>

        <Karte className="overflow-hidden">
          <div className="px-5 pt-[18px] pb-2 flex flex-col gap-1">
            <h2 className="lbl m-0 text-[0.9375rem]">Löschprotokoll</h2>
            <span className="text-[0.8125rem] gedaempft">Endgültig gelöschte Akten – ohne Namen und Inhalte. Der Nachweis, dass und warum gelöscht wurde; unveränderlich.</span>
          </div>
          {d.loeschprotokoll.length ? (
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
          ) : <Leer>Noch keine Akte gelöscht.</Leer>}
        </Karte>

        <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal" data-testid="datenschutz-einstellungen">
          <Icon name="info" />
          <span>Eingestellt: Aufbewahrung {d.einstellungen.aufbewahrung_jahre} Jahre nach Abschluss der Akte · Audit-Log{" "}
            {d.einstellungen.protokoll_aufbewahrung_jahre ? `${d.einstellungen.protokoll_aufbewahrung_jahre} Jahre` : "unbegrenzt"} ·
            Erklärungen, die vorliegen sollen: {d.einstellungen.pflicht_erklaerungen.map((a) => ERKLAERUNGEN_KURZ[a]).join(", ") || "keine"}.
            {darf("vorlagen_pflegen") ? <> Ändern unter <Link to="/admin/vorlagen">Vorlagen › Grenzwerte</Link>.</> : null}</span>
        </div>
      </>)}
    </Seite>
  );
}
