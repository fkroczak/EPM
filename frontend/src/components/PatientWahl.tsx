/** Patient auswählen (Suche nach Name, Nummer oder Geburtsdatum), z. B. für einen Termin von der Startseite. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import type { Seite } from "@/lib/api";
import { datum, nummer } from "@/lib/format";
import type { PatientZeile } from "@/lib/typen";
import { Knopf, cx } from "@/components/ui/basis";

export function PatientWahl({ id, wert, onWahl, fehler }: {
  id?: string; wert: PatientZeile | null; onWahl: (p: PatientZeile | null) => void; fehler?: boolean;
}) {
  const [text, setText] = useState("");
  const begriff = text.trim();
  const treffer = useQuery({
    queryKey: ["patientwahl", begriff],
    queryFn: () => api<Seite<PatientZeile>>(`patienten/${abfrage({ suche: begriff, status: "in_betreuung", seitengroesse: 6, ordering: "nachname" })}`),
    enabled: begriff.length >= 2 && !wert,
  });
  if (wert) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="num gedaempft">{nummer(wert.nummer)}</span>
        <span className="font-medium">{wert.nachname}, {wert.vorname}</span>
        <span className="gedaempft">{datum(wert.geburtsdatum)}</span>
        <Knopf klein variante="geist" onClick={() => onWahl(null)}>ändern</Knopf>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <input id={id} className="inp" type="search" placeholder="Name, Nr. oder Geburtsdatum" value={text}
        aria-invalid={fehler || undefined} onChange={(e) => setText(e.target.value)} autoComplete="off" />
      {begriff.length >= 2 ? (
        <ul className="m-0 p-0 list-none border border-rand rounded-lg max-h-56 overflow-auto" role="listbox" aria-label="Treffer">
          {(treffer.data?.results ?? []).map((p) => (
            <li key={p.id}>
              <button type="button" role="option" aria-selected={false}
                className={cx("w-full text-left px-3 py-2 text-sm flex gap-3 bg-transparent border-0 cursor-pointer hover:bg-fein")}
                onClick={() => onWahl(p)}>
                <span className="num gedaempft">{nummer(p.nummer)}</span>
                <span className="font-medium">{p.nachname}, {p.vorname}</span>
                <span className="gedaempft">{datum(p.geburtsdatum)}</span>
              </button>
            </li>
          ))}
          {treffer.data && treffer.data.results.length === 0 ? <li className="px-3 py-2 text-sm gedaempft">Kein Patient gefunden.</li> : null}
        </ul>
      ) : null}
    </div>
  );
}
