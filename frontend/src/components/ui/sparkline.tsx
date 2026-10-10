/**
 * Kleiner Verlauf ohne Achsen (Wunsch 10.10.2026: in Übersichten nur Kennzahl mit kleinem Verlauf, das große Diagramm
 * erst per Klick im Dialog). Lücken (fehlende Werte) werden nicht überbrückt. Die Werte stehen zusätzlich als Text
 * daneben – die Linie allein trägt keine Information, die sonst fehlt.
 */
import { cx } from "./basis";

export function Sparkline({ werte, max, hoehe = 32, farbe = "var(--reihe-1)", label, className, balken = false }: {
  werte: (number | null)[];
  /** obere Grenze der Achse (z. B. 100 für Prozent); ohne Angabe der größte Wert */
  max?: number;
  hoehe?: number;
  farbe?: string;
  label: string;
  className?: string;
  /** Säulen statt Linie (z. B. Größe je Sicherung) */
  balken?: boolean;
}) {
  const B = 120, H = hoehe;
  const zahlen = werte.filter((w): w is number => w != null);
  const oben = Math.max(max ?? 0, ...zahlen, 1e-9);
  const x = (i: number) => (werte.length < 2 ? B / 2 : (i / (werte.length - 1)) * B);
  const y = (w: number) => H - 2 - (Math.min(oben, Math.max(0, w)) / oben) * (H - 4);
  let linie = "";
  let flaeche = "";
  let offen: number | null = null;
  werte.forEach((w, i) => {
    if (w == null) {
      if (offen != null) flaeche += `L${x(i - 1).toFixed(1)},${H}Z`;
      offen = null;
      return;
    }
    if (offen == null) {
      linie += `M${x(i).toFixed(1)},${y(w).toFixed(1)}`;
      flaeche += `M${x(i).toFixed(1)},${H}L${x(i).toFixed(1)},${y(w).toFixed(1)}`;
      offen = i;
    } else {
      linie += `L${x(i).toFixed(1)},${y(w).toFixed(1)}`;
      flaeche += `L${x(i).toFixed(1)},${y(w).toFixed(1)}`;
    }
  });
  if (offen != null && werte.length) flaeche += `L${x(werte.length - 1).toFixed(1)},${H}Z`;
  const breite = werte.length ? Math.max(1.5, B / werte.length - 1.5) : 0;
  return (
    <svg viewBox={`0 0 ${B} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}
      className={cx("block w-full", className)} style={{ height: `${H / 16}rem` }} data-testid="sparkline" data-punkte={zahlen.length}>
      {balken ? werte.map((w, i) => w == null ? null : (
        <rect key={i} x={werte.length < 2 ? B / 2 - breite / 2 : (i / werte.length) * B + 0.75} y={y(w)} width={breite}
          height={Math.max(1, H - 2 - y(w) + 2)} rx={1} fill={farbe} opacity={0.85} />
      )) : (
        <>
          <path d={flaeche} fill={farbe} opacity={0.12} />
          <path d={linie} fill="none" stroke={farbe} strokeWidth={1.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        </>
      )}
    </svg>
  );
}
