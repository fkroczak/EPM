/** Patient auswählen (Suche nach Name, Nummer oder Geburtsdatum), z. B. für einen Termin von der Startseite. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import type { Seite } from "@/lib/api";
import { datum, nummer } from "@/lib/format";
import type { PatientZeile } from "@/lib/typen";
import { useAuth } from "@/lib/auth";
import { Knopf, cx } from "@/components/ui/basis";

export function PatientWahl({ id, wert, onWahl, fehler, test, ohne }: {
  id?: string; wert: PatientZeile | null; onWahl: (p: PatientZeile | null) => void; fehler?: boolean;
  /** nur Testpatienten bzw. nur echte Akten anbieten; ``ohne``: diesen Patienten nicht anbieten */
  test?: "nur" | "ohne"; ohne?: number;
}) {
  const [text, setText] = useState("");
  const begriff = text.trim();
  // Admins schreiben nur bei Testpatienten – also nur diese zur Auswahl anbieten; gibt die Seite selbst vor, welche
  // Akten in Frage kommen (``test``, z. B. beim Zuordnen eines Dokuments auch echte), gilt das
  const nurTest = test ? test === "nur" : !!useAuth().ich?.schreibt_nur_testpatienten;
  const treffer = useQuery({
    queryKey: ["patientwahl", begriff, nurTest, test],
    queryFn: () => api<Seite<PatientZeile>>(`patienten/${abfrage({ suche: begriff, status: "in_betreuung", seitengroesse: 6, ordering: "nachname", test: test ?? (nurTest ? "nur" : undefined) })}`),
    enabled: begriff.length >= 2 && !wert,
  });
  if (wert) {
    return (
      // lange Namen brechen um, „ändern“ bleibt rechts im Feld (am Telefon ragte der Knopf sonst aus dem Dialog)
      <div className="flex items-center gap-3 text-sm min-w-0">
        <span className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 min-w-0 grow">
          <span className="font-medium min-w-0 [overflow-wrap:anywhere]">{wert.nachname}, {wert.vorname}</span>
          <span className="gedaempft whitespace-nowrap"><span className="num">{nummer(wert.nummer)}</span> · {datum(wert.geburtsdatum)}</span>
        </span>
        <Knopf klein variante="geist" className="shrink-0" onClick={() => onWahl(null)}>ändern</Knopf>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <input id={id} className="inp" type="search" placeholder={nurTest ? "Testpatient: Name, Nr. oder Geburtsdatum" : "Name, Nr. oder Geburtsdatum"}
        value={text} aria-invalid={fehler || undefined} onChange={(e) => setText(e.target.value)} autoComplete="off" />
      {begriff.length >= 2 ? (
        <ul className="m-0 p-0 list-none border border-rand rounded-lg max-h-56 overflow-auto" role="listbox" aria-label="Treffer">
          {(treffer.data?.results ?? []).filter((p) => p.id !== ohne).map((p) => (
            <li key={p.id}>
              <button type="button" role="option" aria-selected={false}
                className={cx("w-full text-left px-3 py-2 text-sm flex flex-wrap items-baseline gap-x-3 gap-y-0.5 bg-transparent border-0 cursor-pointer hover:bg-fein")}
                onClick={() => onWahl(p)}>
                <span className="num gedaempft">{nummer(p.nummer)}</span>
                <span className="font-medium min-w-0 [overflow-wrap:anywhere]">{p.nachname}, {p.vorname}</span>
                <span className="gedaempft whitespace-nowrap">{datum(p.geburtsdatum)}</span>
              </button>
            </li>
          ))}
          {treffer.data && treffer.data.results.length === 0 ? <li className="px-3 py-2 text-sm gedaempft">Kein Patient gefunden. Nur einen
            Teil des Namens, die Nummer oder das Geburtsdatum (14.03.1968) versuchen. Abgeschlossene Akten stehen hier nicht zur Wahl.</li> : null}
        </ul>
      ) : begriff.length === 1 ? <span className="text-[0.8125rem] gedaempft">Bitte mindestens zwei Zeichen eingeben.</span> : null}
    </div>
  );
}
