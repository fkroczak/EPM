/**
 * Karten im Raster mit einstellbarer Größe (Fehlerliste 02.10.2026, Punkt 2 und 4.1): wie die Kacheln der Startseite,
 * aber für die Karten der Übersicht einer Akte und der Systemseite. Jede Karte hat oben
 * rechts ein Menü „⋯“ für Breite (Spalten des Rasters) und Höhe (automatisch nach Inhalt oder 1–4 feste Rasterzeilen,
 * der Inhalt scrollt dann in der Karte). Gespeichert je Seite, Karte und Person (PATCH /api/auth/ich/ {bereiche}).
 *
 * Das Raster packt die Karten ohne Lücken untereinander: Es hat sehr flache Zeilen (8 px), jede Karte belegt so viele,
 * wie sie hoch ist (gemessen mit ResizeObserver) – so rutscht eine kurze Karte unter eine kurze Nachbarin, statt auf
 * die Höhe der längsten in ihrer Reihe zu warten.
 */
import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Menu as BaseMenu } from "@base-ui/react/menu";
import { api } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import type { Bereichsgroesse, Ich } from "@/lib/typen";
import { useHinweis } from "./hinweise";
import { cx } from "./basis";
import { Icon } from "./icon";

export type BereichSeite = "akte_uebersicht" | "akte_kontakte" | "system";

/** Höhe einer Zeile des Rasters in px (siehe .bereiche in index.css) */
const EINHEIT = 8;
const BREITEN = [1, 2, 3, 4, 5];
const HOEHEN = [0, 1, 2, 3, 4];

const Kontext = createContext<{ seite: BereichSeite; spalten: number } | null>(null);

function gueltig(g: unknown): g is Bereichsgroesse {
  const w = g as Bereichsgroesse | null | undefined;
  return !!w && BREITEN.includes(w.breite) && HOEHEN.includes(w.hoehe);
}

/** Raster einer Seite. ``spalten``: Spalten bei der aktuellen Fensterbreite (lib/stufen.ts). */
export function Bereiche({ seite, spalten, children, testid, className }: {
  seite: BereichSeite; spalten: number; children: ReactNode; testid?: string; className?: string;
}) {
  return (
    <Kontext.Provider value={{ seite, spalten }}>
      <div className={cx("bereiche", className)} style={{ gridTemplateColumns: `repeat(${spalten}, minmax(0, 1fr))` }}
        data-testid={testid} data-spalten={spalten}>
        {children}
      </div>
    </Kontext.Provider>
  );
}

/**
 * Eine Karte im Raster. ``standard``: Größe, solange die Person nichts gewählt hat (Breite wird auf die Spalten des
 * Fensters begrenzt; 5 = volle Breite). ``menue={false}``: feste Größe ohne Menü (z. B. Hinweistexte).
 */
export function Bereich({ id, titel, standard, children, menue = true, className }: {
  id: string; titel: string; standard?: Partial<Bereichsgroesse>; children: ReactNode; menue?: boolean; className?: string;
}) {
  const k = useContext(Kontext);
  if (!k) throw new Error("Bereich außerhalb von Bereiche");
  const ich = useIch();
  const { setIch } = useAuth();
  const melden = useHinweis();
  const vorgabe: Bereichsgroesse = { breite: standard?.breite ?? 1, hoehe: standard?.hoehe ?? 0 };
  const gespeichert = ich.bereiche?.[k.seite]?.[id];
  const eigen = menue && gueltig(gespeichert);
  const g = eigen ? gespeichert : vorgabe;
  const breite = Math.min(g.breite, k.spalten);
  const ref = useRef<HTMLDivElement>(null);
  const [zeilen, setZeilen] = useState(1);

  const messen = () => {
    const el = ref.current;
    if (!el || !el.parentElement) return;
    const abstand = parseFloat(getComputedStyle(el.parentElement).columnGap) || 20;
    setZeilen(Math.max(1, Math.ceil((el.getBoundingClientRect().height + abstand) / EINHEIT)));
  };
  // vor dem ersten Zeichnen messen (sonst lägen die Karten kurz übereinander), danach bei jeder Größenänderung
  useLayoutEffect(messen);
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === "undefined") return;
    const beobachter = new ResizeObserver(messen);
    beobachter.observe(ref.current);
    return () => beobachter.disconnect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const speichern = (neu: Bereichsgroesse | null) => {
    const vorher: Ich = ich;
    const seite = { ...(ich.bereiche?.[k.seite] ?? {}) };
    if (neu) seite[id] = neu; else delete seite[id];
    setIch({ ...ich, bereiche: { ...(ich.bereiche ?? {}), [k.seite]: seite } });
    api<Ich>("auth/ich/", { method: "PATCH", body: { bereiche: { [k.seite]: { [id]: neu } } } })
      .then((antwort) => setIch(antwort))
      .catch((e: Error) => { setIch(vorher); melden(`Größe nicht gespeichert: ${e.message}`, "fehler"); });
  };

  const eintrag = "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm cursor-pointer outline-none data-[highlighted]:bg-fein data-[disabled]:opacity-50 data-[disabled]:cursor-not-allowed";
  const marke = (an: boolean) => <span className="w-4 shrink-0 text-akzent-text">{an ? <Icon name="haken" groesse={14} /> : null}</span>;
  return (
    <div ref={ref} className={cx("bereich", g.hoehe > 0 && "fest", !menue && "ohne-menue", className)}
      data-bereich={id} data-breite={breite} data-hoehe={g.hoehe} data-eigen={eigen ? "1" : undefined}
      style={{
        gridColumn: `span ${breite}`,
        gridRowEnd: `span ${zeilen}`,
        ...(g.hoehe > 0 ? { height: `calc(${g.hoehe} * var(--raster-zeile) + ${g.hoehe - 1} * var(--raster-abstand))` } : {}),
      }}>
      {children}
      {menue ? (
        <BaseMenu.Root>
          <BaseMenu.Trigger className="bereich-menue btn geist icon" aria-label={`Größe: ${titel}`} title="Größe dieser Karte (gilt nur für dich)"
            data-testid={`groesse-${id}`}>
            <Icon name="mehr" />
          </BaseMenu.Trigger>
          <BaseMenu.Portal>
            <BaseMenu.Positioner side="bottom" align="end" sideOffset={4} className="z-50">
              <BaseMenu.Popup className="card min-w-[210px] p-1 flex flex-col outline-none" data-testid="groesse-menue">
                <div className="px-3 pt-1.5 pb-1 text-xs font-medium gedaempft">Breite</div>
                {BREITEN.filter((b) => b <= k.spalten).map((b) => (
                  <BaseMenu.Item key={`b${b}`} className={eintrag} onClick={() => speichern({ breite: b, hoehe: g.hoehe })}>
                    {marke(breite === b)}Breite: {b} {b === 1 ? "Spalte" : "Spalten"}{b === k.spalten && b > 1 ? " (ganze Breite)" : ""}
                  </BaseMenu.Item>
                ))}
                <div className="px-3 pt-2 pb-1 text-xs font-medium gedaempft border-t border-rand mt-1">Höhe</div>
                {HOEHEN.map((h) => (
                  <BaseMenu.Item key={`h${h}`} className={eintrag} onClick={() => speichern({ breite: g.breite, hoehe: h })}>
                    {marke(g.hoehe === h)}{h === 0 ? "Höhe: automatisch" : `Höhe: ${h} ${h === 1 ? "Zeile" : "Zeilen"}`}
                  </BaseMenu.Item>
                ))}
                <BaseMenu.Item className={cx(eintrag, "border-t border-rand mt-1 rounded-t-none")} disabled={!eigen} onClick={() => speichern(null)}>
                  {marke(false)}Standardgröße
                </BaseMenu.Item>
              </BaseMenu.Popup>
            </BaseMenu.Positioner>
          </BaseMenu.Portal>
        </BaseMenu.Root>
      ) : null}
    </div>
  );
}
