/**
 * Aufbau der Patientenakte je Person (Wunsch 08.10.2026, Mein Konto › Darstellung › Patientenakte):
 *   kopfzeile    Kopf mit den Angaben in Gruppen (wie die Seitenleiste), darunter waagerechte Reiter; die Höhe des
 *                Kopfs lässt sich am Griff unten in drei Stufen ziehen (nur Name · eine Zeile · alle Angaben)
 *   seitenleiste Angaben und Knöpfe links in einer Leiste, deren Breite sich ziehen lässt (240–480 px, rastet ein),
 *                rechts davon senkrechte Reiter
 *   karteikarte  wie in einer Arztsoftware: schmale Kopfzeile mit CAVE, chronologische Karteikarte mit Kürzelzeile,
 *                rechts eine feste Spalte mit den Angaben
 * Gespeichert in der Darstellung der Person (PATCH /api/auth/ich/ {darstellung}).
 */
import { useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import { api } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import { AKTENLEISTE, STANDARD_DARSTELLUNG } from "@/lib/darstellung";
import type { Darstellung } from "@/lib/darstellung";
import type { Ich } from "@/lib/typen";
import { useHinweis } from "@/components/ui/hinweise";
import { cx } from "@/components/ui/basis";

export type Kopfstufe = Darstellung["aktenkopf"];
export const KOPFSTUFEN: { wert: Kopfstufe; text: string; lang: string }[] = [
  { wert: "minimal", text: "Nur Name", lang: "nur Name und Hinweise" },
  { wert: "kompakt", text: "Eine Zeile", lang: "eine Zeile mit den wichtigsten Angaben" },
  { wert: "voll", text: "Alle Angaben", lang: "alle Angaben in Gruppen" },
];

/** Darstellung der angemeldeten Person (mit Standardwerten) und Ändern einzelner Werte – sofort sichtbar, dann gespeichert */
export function useDarstellung(): [Darstellung, (teil: Partial<Darstellung>) => void] {
  const ich = useIch();
  const { setIch } = useAuth();
  const melden = useHinweis();
  const d: Darstellung = { ...STANDARD_DARSTELLUNG, ...ich.darstellung };
  const aendern = (teil: Partial<Darstellung>) => {
    const vorher: Ich = ich;
    const neu: Darstellung = { ...d, ...teil };
    setIch({ ...ich, darstellung: neu });
    api<Ich>("auth/ich/", { method: "PATCH", body: { darstellung: neu } })
      .then((antwort) => setIch(antwort))
      .catch((e: Error) => { setIch(vorher); melden(`Darstellung nicht gespeichert: ${e.message}`, "fehler"); });
  };
  return [d, aendern];
}

const GRIFF_PUNKTE = (
  <g fill="currentColor"><circle cx="4" cy="2" r="1.2" /><circle cx="8" cy="2" r="1.2" /><circle cx="12" cy="2" r="1.2" />
    <circle cx="4" cy="6" r="1.2" /><circle cx="8" cy="6" r="1.2" /><circle cx="12" cy="6" r="1.2" /></g>
);

/**
 * Griff unter dem Aktenkopf: nach oben ziehen macht den Kopf kleiner, nach unten größer. Er rastet in drei Stufen ein
 * (je 36 px Weg eine Stufe); ↑ ↓ per Tastatur, Doppelklick setzt auf „Alle Angaben“ zurück.
 */
export function Kopfgriff({ stufe, onStufe }: { stufe: Kopfstufe; onStufe: (s: Kopfstufe) => void }) {
  const [zug, setZug] = useState<{ start: number; ziel: Kopfstufe } | null>(null);
  const index = KOPFSTUFEN.findIndex((s) => s.wert === stufe);
  const zielBei = (clientY: number, start: number): Kopfstufe => {
    const schritte = Math.round((clientY - start) / 36);
    return KOPFSTUFEN[Math.min(KOPFSTUFEN.length - 1, Math.max(0, index + schritte))].wert;
  };
  const anzeige = KOPFSTUFEN.find((s) => s.wert === (zug?.ziel ?? stufe))!;
  return (
    <div role="separator" aria-orientation="horizontal" tabIndex={0} data-testid="kopfgriff" data-stufe={stufe}
      aria-label="Höhe des Aktenkopfs" aria-valuemin={0} aria-valuemax={KOPFSTUFEN.length - 1} aria-valuenow={index}
      aria-valuetext={anzeige.lang}
      title={`Ziehen: ${KOPFSTUFEN.map((s) => s.text).join(" · ")} · Doppelklick: Alle Angaben · Tastatur: ↑ ↓`}
      className={cx("kopfgriff nicht-drucken", zug && "aktiv")}
      onPointerDown={(e: PointerEvent<HTMLDivElement>) => {
        if (e.button !== 0) return;
        e.preventDefault();
        e.currentTarget.setPointerCapture(e.pointerId);
        setZug({ start: e.clientY, ziel: stufe });
      }}
      onPointerMove={(e: PointerEvent<HTMLDivElement>) => { if (zug) setZug({ ...zug, ziel: zielBei(e.clientY, zug.start) }); }}
      onPointerUp={(e: PointerEvent<HTMLDivElement>) => {
        if (!zug) return;
        const ziel = zielBei(e.clientY, zug.start);
        setZug(null);
        if (ziel !== stufe) onStufe(ziel);
      }}
      onPointerCancel={() => setZug(null)}
      onDoubleClick={() => { if (stufe !== "voll") onStufe("voll"); }}
      onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
        let neu = index;
        if (e.key === "ArrowUp") neu = index - 1;
        else if (e.key === "ArrowDown") neu = index + 1;
        else if (e.key === "Home") neu = 0;
        else if (e.key === "End") neu = KOPFSTUFEN.length - 1;
        else if (e.key === "Enter" || e.key === " ") neu = KOPFSTUFEN.length - 1;
        else return;
        e.preventDefault();
        neu = Math.min(KOPFSTUFEN.length - 1, Math.max(0, neu));
        if (neu !== index) onStufe(KOPFSTUFEN[neu].wert);
      }}>
      <span className="kopfgriff-griff" aria-hidden="true"><svg width="16" height="8" viewBox="0 0 16 8">{GRIFF_PUNKTE}</svg></span>
      {zug ? <span className="kopfgriff-hinweis" role="status">{anzeige.text} · rastet ein</span> : null}
    </div>
  );
}

function naechster(wert: number): number {
  return AKTENLEISTE.punkte.reduce((best, p) => (Math.abs(p - wert) < Math.abs(best - wert) ? p : best), AKTENLEISTE.standard);
}

/**
 * Griff am rechten Rand der Seitenleiste: Breite ziehen (240–480 px), rastet bei 240, 300, 360, 420 und 480 px ein;
 * ← → per Tastatur, Doppelklick setzt auf 300 px zurück.
 */
export function Leistengriff({ breite, onBreite, onZiehen }: {
  breite: number; onBreite: (px: number) => void; onZiehen: (px: number | null) => void;
}) {
  const [zug, setZug] = useState<{ start: number; px: number } | null>(null);
  const roh = (clientX: number, z: { start: number }) =>
    Math.min(AKTENLEISTE.max, Math.max(AKTENLEISTE.min, breite + clientX - z.start));
  return (
    <div role="separator" aria-orientation="vertical" tabIndex={0} data-testid="leistengriff" data-breite={breite}
      aria-label="Breite der Seitenleiste" aria-valuemin={AKTENLEISTE.min} aria-valuemax={AKTENLEISTE.max} aria-valuenow={breite}
      aria-valuetext={`${breite} Pixel`}
      title={`Ziehen: rastet bei ${AKTENLEISTE.punkte.join(", ")} px ein · Doppelklick: ${AKTENLEISTE.standard} px · Tastatur: ← →`}
      className={cx("teiler leistengriff nicht-drucken", zug && "aktiv")}
      onPointerDown={(e: PointerEvent<HTMLDivElement>) => {
        if (e.button !== 0) return;
        e.preventDefault();
        e.currentTarget.setPointerCapture(e.pointerId);
        setZug({ start: e.clientX, px: breite });
        onZiehen(breite);
      }}
      onPointerMove={(e: PointerEvent<HTMLDivElement>) => {
        if (!zug) return;
        const px = roh(e.clientX, zug);
        setZug({ ...zug, px });
        onZiehen(px);
      }}
      onPointerUp={(e: PointerEvent<HTMLDivElement>) => {
        if (!zug) return;
        const ziel = naechster(roh(e.clientX, zug));
        setZug(null);
        onZiehen(null);
        if (ziel !== breite) onBreite(ziel);
      }}
      onPointerCancel={() => { setZug(null); onZiehen(null); }}
      onDoubleClick={() => { if (breite !== AKTENLEISTE.standard) onBreite(AKTENLEISTE.standard); }}
      onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
        const p = AKTENLEISTE.punkte;
        let ziel: number | undefined;
        if (e.key === "ArrowLeft") ziel = [...p].reverse().find((x) => x < breite);
        else if (e.key === "ArrowRight") ziel = p.find((x) => x > breite);
        else if (e.key === "Home") ziel = p[0];
        else if (e.key === "End") ziel = p[p.length - 1];
        else if (e.key === "Enter" || e.key === " ") ziel = AKTENLEISTE.standard;
        else return;
        e.preventDefault();
        if (ziel !== undefined && ziel !== breite) onBreite(ziel);
      }}>
      <span className="teiler-griff" aria-hidden="true">
        <svg width="8" height="16" viewBox="0 0 8 16"><g fill="currentColor"><circle cx="2" cy="4" r="1.2" /><circle cx="6" cy="4" r="1.2" />
          <circle cx="2" cy="8" r="1.2" /><circle cx="6" cy="8" r="1.2" /><circle cx="2" cy="12" r="1.2" /><circle cx="6" cy="12" r="1.2" /></g></svg>
      </span>
      {zug ? <span className="leistengriff-hinweis" role="status">{naechster(zug.px)} px · rastet ein</span> : null}
    </div>
  );
}
