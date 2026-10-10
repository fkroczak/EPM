/**
 * Eine Seite eines Scans: aufbereitetes Bild, darüber unsichere Wörter gelb markiert (beim Überfahren Sicherheit und
 * die andere Lesart), die Stelle eines gewählten Werts (Prüfansicht) und – in den Modi „Bereich neu erkennen“ und
 * „Bereich markieren“ (F189) – ein Rahmen, der mit Maus oder Finger aufgezogen wird (Pointer-Ereignisse, relativ zur
 * angezeigten Größe, daher auch bei Zoom richtig).
 */
import { useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { ScanSeite, ScanWort } from "@/lib/typen";
import { cx } from "@/components/ui/basis";
import { UNSICHER, bildUrl, hatErgebnis, woerter } from "./hilfen";

type Rahmen = { x0: number; y0: number; x1: number; y1: number };

function begrenzen(v: number) {
  return Math.max(0, Math.min(1, v));
}

export function Seitenansicht({ scanId, seite, markiert, unsicher = true, bereichModus = false, onBereich, original = false,
  onWort }: {
  scanId: number;
  seite: ScanSeite;
  /** Stelle eines Werts (relativ 0–1: x, y, Breite, Höhe) */
  markiert?: number[] | null;
  unsicher?: boolean;
  bereichModus?: boolean;
  onBereich?: (box: number[]) => void;
  /** Rohbild (vor der Aufbereitung) statt der aufbereiteten Seite */
  original?: boolean;
  /** Wort anklicken übernimmt es in das gewählte Feld (Zuordnen); Lage relativ 0–1 */
  onWort?: (wort: ScanWort, box: number[]) => void;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [ziehen, setZiehen] = useState<Rahmen | null>(null);
  const e = hatErgebnis(seite.ergebnis) ? seite.ergebnis : null;
  const breite = e?.breite || seite.breite || 1;
  const hoehe = e?.hoehe || seite.hoehe || 1;
  const fertig = seite.status === "fertig" && (!!seite.breite || original);

  const punkt = (ev: ReactPointerEvent) => {
    const r = svg.current!.getBoundingClientRect();
    return { x: begrenzen((ev.clientX - r.left) / r.width), y: begrenzen((ev.clientY - r.top) / r.height) };
  };
  const box = (r: Rahmen) => [Math.min(r.x0, r.x1), Math.min(r.y0, r.y1), Math.abs(r.x1 - r.x0), Math.abs(r.y1 - r.y0)];

  if (!fertig && !original) {
    return (
      <div className="w-full aspect-[1/1.414] rounded-md border border-dashed border-rand bg-fein flex items-center justify-center text-sm gedaempft"
        data-testid="scan-seite">
        {seite.status === "fehler" ? `Seite ${seite.nr}: ${seite.fehler || "nicht erkannt"}` : `Seite ${seite.nr} wird aufbereitet …`}
      </div>
    );
  }
  return (
    <div className="relative w-full select-none" data-testid="scan-seite" data-seite={seite.nr}>
      <img src={bildUrl(scanId, seite, original ? "roh" : "bild")} alt={`Seite ${seite.nr}${original ? " (Original)" : ""}`}
        className="block w-full h-auto rounded-md border border-rand bg-white" draggable={false} />
      {original ? null : (
        <svg ref={svg} viewBox={`0 0 ${breite} ${hoehe}`} preserveAspectRatio="none"
          className={cx("absolute inset-0 w-full h-full", bereichModus && "cursor-crosshair touch-none")}
          onPointerDown={(ev) => {
            if (!bereichModus) return;
            try {
              ev.currentTarget.setPointerCapture(ev.pointerId);
            } catch { /* nachgestellte Ereignisse (Tests) haben keinen echten Zeiger */ }
            const p = punkt(ev);
            setZiehen({ x0: p.x, y0: p.y, x1: p.x, y1: p.y });
          }}
          onPointerMove={(ev) => {
            if (!ziehen) return;
            const p = punkt(ev);
            setZiehen({ ...ziehen, x1: p.x, y1: p.y });
          }}
          onPointerUp={() => {
            if (!ziehen) return;
            const b = box(ziehen);
            setZiehen(null);
            if (b[2] > 0.01 && b[3] > 0.005) onBereich?.(b);
          }}
          // Touch: bricht der Browser die Geste ab (z. B. Scrollen mit zwei Fingern), keinen halben Rahmen stehen lassen
          onPointerCancel={() => setZiehen(null)}
          data-testid={bereichModus ? "bereich-flaeche" : undefined}>
          {unsicher ? woerter(seite.ergebnis).filter((w) => w[5] < UNSICHER).map((w, i) => (
            <rect key={i} x={w[1]} y={w[2]} width={w[3]} height={w[4]} className="scan-unsicher" data-testid="unsicheres-wort">
              <title>{`„${w[0]}“ – Sicherheit ${Math.round(w[5] * 100)} %${w[6] ? ` · andere Lesart: „${w[6]}“` : ""}`}</title>
            </rect>
          )) : null}
          {(e?.bereiche ?? []).map((b, i) => (
            <rect key={`b${i}`} x={b[0] * breite} y={b[1] * hoehe} width={b[2] * breite} height={b[3] * hoehe} className="scan-neu-erkannt">
              <title>neu erkannter Bereich</title>
            </rect>
          ))}
          {onWort && !bereichModus ? woerter(seite.ergebnis).map((w, i) => (
            <rect key={`w${i}`} x={w[1]} y={w[2]} width={w[3]} height={w[4]} className="scan-wort-waehlbar"
              data-testid="waehlbares-wort" data-wort={w[0]}
              onClick={(ev) => { ev.stopPropagation(); onWort(w, [w[1] / breite, w[2] / hoehe, w[3] / breite, w[4] / hoehe]); }}>
              <title>{`„${w[0]}“ übernehmen`}</title>
            </rect>
          )) : null}
          {markiert ? (
            <rect x={markiert[0] * breite - breite * 0.004} y={markiert[1] * hoehe - breite * 0.004}
              width={markiert[2] * breite + breite * 0.008} height={markiert[3] * hoehe + breite * 0.008} rx={breite * 0.004}
              className="scan-markiert" data-testid="markierte-stelle" />
          ) : null}
          {ziehen ? (() => {
            const b = box(ziehen);
            return <rect x={b[0] * breite} y={b[1] * hoehe} width={b[2] * breite} height={b[3] * hoehe} className="scan-bereich" />;
          })() : null}
        </svg>
      )}
    </div>
  );
}
