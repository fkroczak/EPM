/**
 * Gemeinsames Gerüst für alle Reiter der Akte (Wunsch 07.10.2026, F122).
 *
 * Alle Reiter sehen gleich aus und die Knöpfe stehen überall an derselben Stelle – nach dem Muster, das sich
 * beim Infusionsplan bewährt hat: links die Einträge mit Datum, rechts der gewählte Eintrag.
 *
 *   ┌─ links ─────────────┐ ┌─ rechts ───────────────────────┐
 *   │ 7 Diagnosen         │ │ Kurzdarmsyndrom [K91.2G]  ⟨…⟩  │  ⟨…⟩ = Aktionen zum Eintrag, immer oben rechts
 *   │ [+ Diagnose]        │ │ seit 14.03.2019                │
 *   │ ├ 14.03.2019 …      │ │                                │
 *   │ ├ 02.08.2021 …      │ │ Inhalt                         │
 *   └─────────────────────┘ └────────────────────────────────┘
 *
 * Feste Plätze: Überschrift mit Anzahl links oben, darunter der Hauptknopf („Neuer …“), darunter die Liste,
 * darunter der erklärende Satz. Rechts der Kopf mit Titel und Zusatz, die Aktionen in derselben Zeile rechts.
 * Die Abstände sind knapper als in den alten Karten, damit der Bildschirm nicht überfüllt wirkt.
 */
import { createContext, useContext } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router";
import { detailZeigen } from "@/lib/stufen";
import { Karte, Laden, Leer, cx } from "@/components/ui/basis";

/** Kennung des Detailbereichs dieses Reiters – ein gewählter Eintrag holt ihn am Telefon in den Blick */
const DetailKennung = createContext("akte-detail");

/**
 * Welcher Eintrag rechts steht – in der Adresse, damit ein Link darauf zeigen kann und ein Neuladen die Auswahl
 * behält (wie beim Infusionsplan mit ``?plan=``).
 */
export function useWahl(name: string): [string, (wert: string) => void] {
  const [params, setParams] = useSearchParams();
  const setzen = (wert: string) => {
    const neu = new URLSearchParams(params);
    if (wert) neu.set(name, wert); else neu.delete(name);
    setParams(neu, { replace: true });
  };
  return [params.get(name) ?? "", setzen];
}

/** Rahmen eines Reiters: links Liste, rechts Detail. */
export function Aktenseite({ titel, anzahl, aktion, kopfrechts, liste, fuss, detail, laedt, leer, testid }: {
  /** Überschrift der linken Spalte, z. B. „Diagnosen“ (Einzahl/Mehrzahl macht ``anzahl``) */
  titel: string;
  /** Zahl vor der Überschrift; ohne Angabe nur die Überschrift */
  anzahl?: number;
  /** Hauptknopf unter der Überschrift („Neue Diagnose“) – auf jedem Reiter an derselben Stelle */
  aktion?: ReactNode;
  /** Zusatz über der Liste (Hinweise, Filter) */
  kopfrechts?: ReactNode;
  liste: ReactNode;
  fuss?: ReactNode;
  detail: ReactNode;
  laedt?: boolean;
  /** Text, wenn es keinen Eintrag gibt */
  leer?: string;
  testid?: string;
}) {
  // Ab 1280 px links Kopf und Liste, rechts das Detail. Darunter (Telefon, schmale Fenster, Festlegung 08.10.2026)
  // der Kopf mit dem Hauptknopf, dann das gewählte Detail, dann die Liste – der Blick in die Akte braucht kein Scrollen.
  const kennung = `${testid ?? "akte"}-detailbereich`;
  return (
    <DetailKennung.Provider value={kennung}>
    <div className="stapel grid grid-cols-1 xl:grid-cols-[290px_minmax(0,1fr)] fhd:grid-cols-[340px_minmax(0,1fr)] gap-x-5 gap-y-4 xl:gap-y-2.5 items-start
      [grid-template-areas:'kopf'_'detail'_'liste'] xl:[grid-template-areas:'kopf_detail'_'liste_detail'] xl:grid-rows-[auto_1fr]"
      data-testid={testid}>
      <div className="flex flex-col gap-2.5 [grid-area:kopf]">
        <h2 className="lbl m-0">{anzahl != null ? <span className="num mr-1.5">{anzahl}</span> : null}{titel}</h2>
        {aktion}
        {kopfrechts}
      </div>
      <div className="flex flex-col gap-2.5 [grid-area:liste]">
        {laedt ? <Laden /> : null}
        {liste}
        {fuss ? <span className="text-[0.8125rem] gedaempft leading-normal">{fuss}</span> : null}
      </div>
      {/* Ohne Einträge sagt die Liste, was fehlt, und der Hauptknopf steht direkt darüber – kein zweiter Hinweis
          „Links … wählen“ (Vorschlag „Weniger Erklärtext“, 08.10.2026) */}
      <div className="min-w-0 [grid-area:detail] scroll-mt-20" data-testid={kennung}>{detail ?? (leer && !(anzahl === 0 && !laedt) ? <Hinweiskarte>{leer}</Hinweiskarte> : null)}</div>
    </div>
    </DetailKennung.Provider>
  );
}

/** Die Liste links; jeder Eintrag ein ``Eintrag``. */
export function Eintragsliste({ name, children, leer, testid }: {
  name: string; children: ReactNode; leer?: string; testid?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5" role="list" aria-label={name} data-testid={testid ?? "eintragsliste"}>
      {children}
      {leer ? <Leer>{leer}</Leer> : null}
    </div>
  );
}

/**
 * Ein Eintrag in der Liste links: oben Datum und ein Merkmal (Status, Anzahl), darunter zwei knappe Zeilen.
 * Gewählt wird er durch Anklicken; ``aktiv`` zeichnet ihn aus.
 */
export function Eintrag({ datum: datumText, merkmal, zeile, unten, aktiv, onWahl, warnung }: {
  datum: ReactNode;
  merkmal?: ReactNode;
  zeile?: ReactNode;
  unten?: ReactNode;
  aktiv?: boolean;
  onWahl: () => void;
  /** hebt den Eintrag hervor (z. B. Entwurf, storniert) */
  warnung?: boolean;
}) {
  const kennung = useContext(DetailKennung);
  // Listenpunkt und Knopf getrennt: ``role="listitem"`` direkt auf dem Knopf würde dessen Rolle ersetzen – er
  // wäre dann für Hilfsmittel (und Tests) kein Knopf mehr.
  return (
    <div role="listitem" className="flex">
      <button type="button" aria-current={aktiv ? "true" : undefined}
        className={cx("card w-full text-left px-3 py-2 flex flex-col gap-0.5 cursor-pointer border",
          aktiv ? "border-akzent bg-akzent-weich" : "hover:bg-fein", warnung && !aktiv && "border-warn")}
        onClick={() => { onWahl(); detailZeigen(kennung); }}>
        <span className="flex items-center justify-between gap-2 w-full">
          <span className="num font-medium text-sm">{datumText}</span>
          {merkmal}
        </span>
        {zeile ? <span className="text-[0.8125rem] leading-snug">{zeile}</span> : null}
        {unten ? <span className="text-xs gedaempft leading-snug">{unten}</span> : null}
      </button>
    </div>
  );
}

/**
 * Der Detailbereich rechts: Kopf mit Titel und Zusatz, die Aktionen immer oben rechts in derselben Zeile,
 * darunter der Inhalt.
 */
export function Detail({ titel, unter, aktionen, children, testid }: {
  titel: ReactNode; unter?: ReactNode; aktionen?: ReactNode; children?: ReactNode; testid?: string;
}) {
  return (
    <Karte className="p-4 flex flex-col gap-3 min-w-0" data-testid={testid}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-0.5 min-w-0">
          <span className="text-base font-semibold leading-tight">{titel}</span>
          {unter ? <span className="text-[0.8125rem] gedaempft leading-snug">{unter}</span> : null}
        </div>
        {aktionen ? <div className="flex items-center gap-2 flex-wrap shrink-0" data-testid="detail-aktionen">{aktionen}</div> : null}
      </div>
      {children}
    </Karte>
  );
}

/** Platzhalter rechts, solange nichts gewählt ist. */
export function Hinweiskarte({ children }: { children: ReactNode }) {
  return <Karte className="p-4" data-testid="detail-leer"><Leer>{children}</Leer></Karte>;
}

/** Werte in zwei Spalten, knapp gesetzt – für Messwerte und Kennzahlen im Detail. */
export function Wertetabelle({ werte, spalten = 3 }: {
  werte: [ReactNode, ReactNode][]; spalten?: 2 | 3;
}) {
  return (
    <div className={cx("grid gap-x-5 gap-y-0.5", spalten === 3 ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2")}>
      {werte.map(([label, wert], i) => (
        <div key={i} className="flex items-baseline justify-between gap-2 text-sm border-b border-rand py-1 last:border-0">
          <span className="gedaempft">{label}</span>
          <span className="num">{wert}</span>
        </div>
      ))}
    </div>
  );
}

/** Abschnitt im Detail mit knapper Überschrift. */
export function Abschnitt({ titel, children, rechts }: { titel: string; children: ReactNode; rechts?: ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5 min-w-0">
      <div className="flex items-center justify-between gap-2">
        <h3 className="lbl m-0 text-[0.8125rem]">{titel}</h3>
        {rechts}
      </div>
      {children}
    </section>
  );
}
