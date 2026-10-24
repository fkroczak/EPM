/**
 * Diktate fürs Sekretariat (Wunsch 23.10.2026): ans Sekretariat abgegebene Diktate, deren Text noch nicht im Bericht
 * steht – älteste zuerst. Öffnen führt zum Bericht in der Akte; dort nachhören, übernehmen und fertig machen.
 */
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { datum, uhrzeit } from "@/lib/format";
import type { Diktat } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Fehleranzeige, Karte, Laden, Leer, Seitenkopf } from "@/components/ui/basis";
import { dauerText } from "@/components/Diktat";

export function Diktate() {
  const offen = useQuery({
    queryKey: ["diktate", "offen"],
    queryFn: () => api<Diktat[]>("diktate/offen/"),
    refetchInterval: 30_000,
  });
  const liste = offen.data ?? [];
  return (
    <Seite pfad={[{ text: "Diktate" }]}>
      <Seitenkopf titel="Diktate"
        unter="Ans Sekretariat gegebene Diktate, deren Text noch nicht im Bericht steht. Im Bericht: nachhören, „In den Text übernehmen“, korrigieren, speichern." />
      <Fehleranzeige fehler={offen.error} />
      <Karte className="overflow-x-auto">
        {offen.isPending ? <Laden /> : liste.length === 0 ? <Leer>Keine offenen Diktate.</Leer> : (
          <table className="tabelle" data-testid="diktate-offen">
            <thead>
              <tr>
                <th className="th">Patient</th><th className="th">Bericht</th><th className="th">Diktiert</th>
                <th className="th text-right">Länge</th><th className="th">Stand</th>
              </tr>
            </thead>
            <tbody>
              {liste.map((d) => (
                <tr key={d.id}>
                  <td className="td">
                    <Link to={`/patienten/${d.patient}`} className="font-medium no-underline">{d.patient_name}</Link>
                  </td>
                  <td className="td">
                    <Link to={`/patienten/${d.patient}/berichte?bericht=${d.bericht}`}>{d.bericht_titel ?? "Bericht"}</Link>
                  </td>
                  <td className="td text-[0.8125rem] whitespace-nowrap">
                    <span className="num">{datum(d.erstellt_am)} {uhrzeit(d.erstellt_am)}</span>
                    {d.erstellt_von_name ? <span className="gedaempft"> · {d.erstellt_von_name}</span> : null}
                  </td>
                  <td className="td num text-right">{dauerText(d.dauer_s)}</td>
                  <td className="td whitespace-nowrap">
                    <Chip art={d.status === "fertig" ? "warn" : d.status === "fehler" ? "fehler" : "neutral"}>
                      {d.status === "fertig" ? "zum Übernehmen" : d.status === "wartet" && d.wann === "nachts" ? "wartet auf die Nacht" : d.status_name}
                    </Chip>
                    {d.status === "fertig" && d.unsicher ? <Chip art="warn" className="ml-1.5">{d.unsicher} unsicher</Chip> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Karte>
    </Seite>
  );
}
