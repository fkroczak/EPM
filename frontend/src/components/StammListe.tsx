/**
 * Gemeinsamer Aufbau von Versorger und Ärzte (Entwürfe vom 08.10.2026, PC/Tablet/Telefon):
 *   links  eine schmale Liste mit Suche, „Aktiv | Inaktiv | Alle“ (mit Zahlen) und je Eintrag Name, Ort und
 *          Patientenzahl; sie scrollt in sich, die Seite nicht
 *   rechts der gewählte Eintrag zum Lesen (Anschrift, Erreichbarkeit, Notiz nebeneinander), „Bearbeiten“ öffnet das
 *          Formular an derselben Stelle; Deaktivieren steckt mit Rückfrage im Menü „⋯“
 *   Telefon: entweder Liste oder Eintrag, „‹ Liste“ führt zurück
 */
import type { ReactNode } from "react";
import { Link } from "react-router";
import { zahl } from "@/lib/format";
import { Chip, Karte, Leer, Segmente, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";

export type Filter = "aktiv" | "inaktiv" | "alle";

export function ListenSpalte<T extends { id: number; aktiv: boolean }>({ eintraege, alle, gewaehlt, onWahl, suche, onSuche,
  platzhalter, sucheLabel, filter, onFilter, titel, unter, zahl: anzahl, fuss, testid, leer, versteckt }: {
  eintraege: T[]; alle: T[]; gewaehlt: number | null; onWahl: (id: number) => void; suche: string; onSuche: (s: string) => void;
  platzhalter: string; sucheLabel: string; filter: Filter; onFilter: (f: Filter) => void; titel: (e: T) => ReactNode;
  unter: (e: T) => ReactNode; zahl: (e: T) => number; fuss: ReactNode; testid: string; leer: string; versteckt?: boolean;
}) {
  const aktive = alle.filter((e) => e.aktiv).length;
  return (
    <Karte className={cx("stamm-liste flex flex-col min-h-0 overflow-hidden", versteckt && "max-md:hidden")}>
      <div className="flex flex-col gap-2 p-2.5 border-b border-rand">
        <label className="relative block">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
          <input className="inp pl-[2.125rem]" type="search" aria-label={sucheLabel} placeholder={platzhalter}
            value={suche} onChange={(e) => onSuche(e.target.value)} />
        </label>
        <Segmente label="Filter" wert={filter} onWahl={onFilter} className="self-start" werte={[
          { wert: "aktiv", text: <>Aktiv <span className="num opacity-70">{zahl(aktive)}</span></> },
          { wert: "inaktiv", text: <>Inaktiv <span className="num opacity-70">{zahl(alle.length - aktive)}</span></> },
          { wert: "alle", text: "Alle" },
        ]} />
      </div>
      <div className="grow min-h-0 overflow-y-auto overscroll-contain" role="list" aria-label={sucheLabel.replace(" filtern", "")} data-testid={testid}>
        {eintraege.map((e) => (
          <div role="listitem" key={e.id} className="flex">
            <button type="button" aria-current={e.id === gewaehlt ? "true" : undefined} onClick={() => onWahl(e.id)}
              className={cx("stamm-eintrag w-full text-left border-0 border-b border-rand bg-transparent cursor-pointer px-3.5 py-2.5 flex items-start gap-3",
                e.id === gewaehlt && "aktiv")}>
              <span className="grow min-w-0 flex flex-col gap-0.5">
                <span className="font-medium text-sm truncate">{titel(e)}{!e.aktiv ? <Chip className="ml-2">inaktiv</Chip> : null}</span>
                <span className="text-[0.8125rem] gedaempft truncate">{unter(e)}</span>
              </span>
              <span className="num text-[0.8125rem] gedaempft shrink-0" title="Patienten in Betreuung">{zahl(anzahl(e))}</span>
            </button>
          </div>
        ))}
        {!eintraege.length ? <Leer>{leer}</Leer> : null}
      </div>
      <div className="px-3.5 py-2 border-t border-rand text-xs gedaempft">{fuss}</div>
    </Karte>
  );
}

/** Kopf des gewählten Eintrags: Name, Status, Zahl der Patienten, rechts Aktionen; am Telefon „‹ Liste“ davor */
export function DetailKopf({ titel, aktiv, patienten, patientenLink, rechts, onListe }: {
  titel: ReactNode; aktiv?: boolean; patienten?: number; patientenLink?: string; rechts?: ReactNode; onListe?: () => void;
}) {
  return (
    <div className="flex items-center gap-x-3 gap-y-2 flex-wrap px-4 sm:px-5 py-3.5 border-b border-rand">
      {onListe ? <button type="button" className="btn sec klein md:hidden" onClick={onListe}><Icon name="zurueck" groesse={14} />Liste</button> : null}
      <h2 className="m-0 text-lg font-semibold min-w-0 break-words">{titel}</h2>
      {aktiv === undefined ? null : aktiv ? <Chip art="ok">aktiv</Chip> : <Chip>inaktiv</Chip>}
      {patienten !== undefined ? (
        <span className="text-[0.8125rem] gedaempft">
          <span className="num">{zahl(patienten)}</span> Patienten
          {patientenLink && patienten > 0 ? <> · <Link to={patientenLink}>anzeigen</Link></> : null}
        </span>
      ) : null}
      {rechts ? <div className="ml-auto flex items-center gap-2">{rechts}</div> : null}
    </div>
  );
}

/** Lesender Block: Überschrift und Zeilen „Bezeichnung | Wert“ (Telefonnummern in Ziffernschrift) */
export function Infoblock({ titel, zeilen, children }: {
  titel: string; zeilen?: [string, ReactNode, boolean?][]; children?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 min-w-0">
      <h3 className="lbl m-0 text-[0.75rem] tracking-wide uppercase gedaempft">{titel}</h3>
      {zeilen ? (
        <dl className="m-0 grid grid-cols-[6.5rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
          {zeilen.map(([l, w, num]) => (
            <div key={l} className="contents">
              <dt className="gedaempft">{l}</dt>
              <dd className={cx("m-0 break-words", num && "num", (w === "" || w == null) && "gedaempft")}>{w === "" || w == null ? "—" : w}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {children}
    </div>
  );
}
