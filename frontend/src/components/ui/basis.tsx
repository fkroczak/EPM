/**
 * Grundbausteine im Stil von shadcn/ui, gestaltet nach dem Entwurf (Klassen in index.css).
 */
import { forwardRef, useId } from "react";
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes,
  TextareaHTMLAttributes } from "react";
import { Link } from "react-router";
import type { LinkProps } from "react-router";
import { rem } from "@/lib/masse";
import { Icon } from "./icon";

export function cx(...klassen: (string | false | null | undefined)[]) {
  return klassen.filter(Boolean).join(" ");
}

type Variante = "pri" | "sec" | "dng" | "geist";

export const Knopf = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: Variante; klein?: boolean; icon?: string; laedt?: boolean;
}>(function Knopf({ variante = "sec", klein, icon, laedt, className, children, disabled, type, ...rest }, ref) {
  return (
    <button ref={ref} type={type ?? "button"} className={cx("btn", variante, klein && "klein", className)}
      disabled={disabled || laedt} aria-busy={laedt || undefined} {...rest}>
      {laedt ? <Ladekreis /> : icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
});

export function KnopfLink({ variante = "sec", klein, icon, className, children, ...rest }: LinkProps & {
  variante?: Variante; klein?: boolean; icon?: string;
}) {
  return (
    <Link className={cx("btn", variante, klein && "klein", className)} {...rest}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </Link>
  );
}

export function Karte({ className, children, ...rest }: HTMLAttributes<HTMLElement> & { as?: "section" | "div" }) {
  return <section className={cx("card", className)} {...rest}>{children}</section>;
}

export function KartenKopf({ titel, rechts, unter, className }: { titel: ReactNode; rechts?: ReactNode; unter?: ReactNode;
  className?: string }) {
  return (
    <div className={cx("flex items-start justify-between gap-3 flex-wrap", className)}>
      <div className="flex flex-col gap-1 min-w-0">
        <h2 className="lbl m-0 text-[0.9375rem]">{titel}</h2>
        {unter ? <span className="text-[0.8125rem] gedaempft">{unter}</span> : null}
      </div>
      {rechts ? <div className="flex items-center gap-2 flex-wrap">{rechts}</div> : null}
    </div>
  );
}

export function Chip({ art, className, children, ...rest }: HTMLAttributes<HTMLSpanElement> & {
  art?: "warn" | "fehler" | "ok" | "akzent" | "neutral";
}) {
  return <span className={cx("chip", art !== "neutral" && art, className)} {...rest}>{children}</span>;
}

type FeldProps = { label: ReactNode; hinweis?: ReactNode; fehler?: string; className?: string; pflicht?: boolean };

/** Beschriftetes Eingabefeld; das Kind bekommt id und aria-Attribute über `children(id)`. */
export function Feld({ label, hinweis, fehler, className, pflicht, children }: FeldProps & {
  children: (props: { id: string; "aria-invalid"?: boolean; "aria-describedby"?: string }) => ReactNode;
}) {
  const id = useId();
  const hinweisId = `${id}-hinweis`;
  return (
    <div className={cx("feld", className)}>
      <label htmlFor={id}>{label}{pflicht ? <span aria-hidden="true"> *</span> : null}</label>
      {children({ id, "aria-invalid": fehler ? true : undefined, "aria-describedby": fehler || hinweis ? hinweisId : undefined })}
      {fehler ? <span id={hinweisId} className="fehlertext" role="alert">{fehler}</span>
        : hinweis ? <span id={hinweisId} className="hinweis">{hinweis}</span> : null}
    </div>
  );
}

/** Nur lesen: Bezeichnung und Wert als Text – statt eines ausgegrauten Eingabefelds, wenn jemand nichts ändern darf. */
export function Anzeige({ label, children, className, mehrzeilig }: { label: ReactNode; children: ReactNode; className?: string;
  mehrzeilig?: boolean }) {
  const leer = children === null || children === undefined || children === "";
  return (
    <div className={cx("feld", className)}>
      <span>{label}</span>
      <span className={cx("font-normal text-sm min-h-[1.25rem] break-words", mehrzeilig && "whitespace-pre-line", leer && "gedaempft")}>
        {leer ? "—" : children}
      </span>
    </div>
  );
}

export const Eingabe = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Eingabe(
  { className, ...rest }, ref) {
  return <input ref={ref} className={cx("inp", className)} {...rest} />;
});

export const Textfeld = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textfeld(
  { className, ...rest }, ref) {
  return <textarea ref={ref} className={cx("inp", className)} {...rest} />;
});

export const Auswahl = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Auswahl(
  { className, children, ...rest }, ref) {
  return <select ref={ref} className={cx("inp", className)} {...rest}>{children}</select>;
});

/** Umschalter wie im Entwurf („In Betreuung | Abgeschlossen“, „12 Monate | 3 Jahre …“) */
export function Segmente<T extends string>({ werte, wert, onWahl, label, className }: {
  werte: { wert: T; text: ReactNode }[]; wert: T; onWahl: (w: T) => void; label: string; className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={cx("segmente", className)}>
      {werte.map((w) => (
        <button key={w.wert} type="button" className="segment" aria-pressed={w.wert === wert} onClick={() => onWahl(w.wert)}>
          {w.text}
        </button>
      ))}
    </div>
  );
}

export function Ladekreis({ groesse = 16 }: { groesse?: number }) {
  return (
    <svg width={groesse} height={groesse} style={{ width: rem(groesse), height: rem(groesse) }} viewBox="0 0 24 24" aria-hidden="true" className="animate-spin">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity=".25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

const LADEN_TEXT = "Wird geladen …";
/** Breiten der Platzhalterzeilen: ungleich lang wie echter Text */
const ZEILEN_BREITE = ["92%", "74%", "84%", "58%", "88%", "66%"];

/** Platzhalter in der Form des Inhalts (Skelett), solange Daten laden (Performance-Prüfung 14.11.2026). */
export function Skelett({ className, breite, hoehe }: { className?: string; breite?: string; hoehe?: string }) {
  return <span aria-hidden="true" className={cx("skelett", className)} style={{ width: breite, height: hoehe ?? "0.875rem" }} />;
}

/**
 * Ladezustand. Ohne eigenen Text: Platzhalterzeilen (Skelett) statt Ladekreis – die Seite steht sofort in ihrer Form da.
 * Mit eigenem Text („PDF wird erzeugt …“): Ladekreis mit Text, weil er sagt, worauf gewartet wird.
 */
export function Laden({ text = LADEN_TEXT, zeilen = 3 }: { text?: string; zeilen?: number }) {
  if (text !== LADEN_TEXT) {
    return (
      <div role="status" className="flex items-center gap-2 p-6 text-sm gedaempft">
        <Ladekreis /> {text}
      </div>
    );
  }
  return (
    <div role="status" data-laden className="flex flex-col gap-2.5 px-1 py-3">
      <span className="sr-only">{text}</span>
      {Array.from({ length: zeilen }, (_, i) => <Skelett key={i} breite={ZEILEN_BREITE[i % ZEILEN_BREITE.length]} />)}
    </div>
  );
}

/** Gerüst der ganzen Anwendung beim ersten Laden (gleiches Bild wie in index.html, damit nichts springt). */
export function AppSkelett() {
  return (
    <div className="app-skelett" role="status" data-laden>
      <span className="sr-only">EPM wird geladen …</span>
      <div className="app-skelett-leiste" aria-hidden="true">
        <Skelett hoehe="3.5rem" />
        {Array.from({ length: 8 }, (_, i) => <Skelett key={i} hoehe="1.25rem" breite={i % 3 ? "80%" : "90%"} />)}
      </div>
      <div className="grow min-w-0" aria-hidden="true">
        <div className="app-skelett-kopf"><Skelett breite="6rem" /><Skelett breite="22rem" hoehe="2.25rem" /></div>
        <div className="app-skelett-inhalt">
          <Skelett breite="18rem" hoehe="1.75rem" />
          <div className="app-skelett-karten">
            {Array.from({ length: 3 }, (_, i) => (
              <div key={i} className="app-skelett-karte">
                <Skelett breite="45%" hoehe="1.125rem" /><Skelett breite="90%" /><Skelett breite="75%" /><Skelett breite="82%" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Meldung({ art = "info", children, className }: { art?: "info" | "warn" | "fehler" | "ok";
  children: ReactNode; className?: string }) {
  return <div role={art === "fehler" ? "alert" : "status"} className={cx("meldung", art, className)}>{children}</div>;
}

export function Leer({ children }: { children: ReactNode }) {
  return <p className="m-0 py-3 text-center text-sm gedaempft">{children}</p>;
}

export function Fehleranzeige({ fehler }: { fehler: unknown }) {
  if (!fehler) return null;
  const text = fehler instanceof Error ? fehler.message : String(fehler);
  return <Meldung art="fehler">{text}</Meldung>;
}

/**
 * Kopf jeder Seite – überall gleich hoch (Wunsch 08.10.2026: „wenn man zwischen den Menüs schaltet, springt alles“):
 * Titel und Unterzeile in einer Zeile (die Unterzeile wird gekürzt, ganz im Tooltip), rechts die Knöpfe in Steuerhöhe.
 */
export function Seitenkopf({ titel, unter, rechts }: { titel: ReactNode; unter?: ReactNode; rechts?: ReactNode }) {
  return (
    <div className="seitenkopf flex items-center justify-between gap-x-4 gap-y-2 flex-wrap">
      <div className="flex items-baseline gap-x-3 min-w-0 flex-1">
        <h1 className="m-0 text-[1.25rem] leading-tight font-semibold whitespace-nowrap">{titel}</h1>
        {unter ? <span className="seitenkopf-unter text-[0.8125rem] gedaempft min-w-0" title={typeof unter === "string" ? unter : undefined}>{unter}</span> : null}
      </div>
      {rechts ? <div className="flex items-center gap-2 flex-wrap min-w-0 max-w-full">{rechts}</div> : null}
    </div>
  );
}

export function Wertzeile({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(6.875rem,40%)_1fr] gap-3 py-1.5 text-sm">
      <dt className="gedaempft">{label}</dt>
      <dd className="m-0">{children}</dd>
    </div>
  );
}
