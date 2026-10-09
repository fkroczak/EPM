/**
 * Spalten mit Teilern zum Ziehen wie bei einem Fenster (S17, Festlegungen 01./02.10.2026): Der Teiler rastet bei ⅓, ½
 * und ⅔ ein (dazu beim Standard der Seite), Doppelklick setzt auf den Standard zurück, per Tastatur springen ← und → zum
 * nächsten Einrastpunkt. Gespeichert je Seite, Fensterstufe und Person (PATCH /api/auth/ich/ {aufteilung}).
 */
import { useRef, useState } from "react";
import type { KeyboardEvent, PointerEvent, ReactNode } from "react";
import { api } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import type { Ich } from "@/lib/typen";
import { useHinweis } from "./hinweise";
import { cx } from "./basis";

export type TeilerSeite = "patientenliste" | "akte_uebersicht" | "akte_kontakte" | "plan_editor";
const TEILER_BREITE = 12; // schmaler seit 08.10.2026 (weniger Leerraum)
const MIN_SPALTE = 0.15;
const EINRASTEN = [1 / 3, 1 / 2, 2 / 3];

const BRUECHE: [number, string, string][] = [
  [1 / 4, "¼", "ein Viertel"], [1 / 3, "⅓", "ein Drittel"], [2 / 5, "⅖", "zwei Fünftel"], [1 / 2, "½", "die Hälfte"],
  [3 / 5, "⅗", "drei Fünftel"], [2 / 3, "⅔", "zwei Drittel"], [3 / 4, "¾", "drei Viertel"],
];

export function bruch(wert: number): string {
  return BRUECHE.find(([b]) => Math.abs(b - wert) < 0.005)?.[1] ?? `${Math.round(wert * 100)} %`;
}

function bruchText(wert: number): string {
  return BRUECHE.find(([b]) => Math.abs(b - wert) < 0.005)?.[2] ?? `${Math.round(wert * 100)} Prozent`;
}

/** Einrastpunkte für Teiler ``i``: ⅓, ½, ⅔ und der Standard – mit Platz für die Nachbarspalten */
function punkte(werte: number[], i: number, standard: number[]): number[] {
  const links = (i > 0 ? werte[i - 1] : 0) + MIN_SPALTE;
  const rechts = (i < werte.length - 1 ? werte[i + 1] : 1) - MIN_SPALTE;
  const alle = [...EINRASTEN, standard[i]].filter((p) => p >= links - 1e-6 && p <= rechts + 1e-6).sort((a, b) => a - b);
  return alle.filter((p, j) => j === 0 || p - alle[j - 1] > 0.001);
}

function naechster(liste: number[], wert: number): number {
  return liste.reduce((best, p) => (Math.abs(p - wert) < Math.abs(best - wert) ? p : best), liste[0] ?? wert);
}

function gueltig(werte: unknown, anzahl: number): werte is number[] {
  if (!Array.isArray(werte) || werte.length !== anzahl || !werte.every((w) => typeof w === "number")) return false;
  const grenzen = [0, ...werte, 1];
  return grenzen.every((g, j) => j === 0 || g - grenzen[j - 1] >= MIN_SPALTE - 1e-6);
}

export function Spalten({ seite, stufe, standard, spalten, namen, className, testid }: {
  seite: TeilerSeite;
  stufe: "hd" | "fhd" | "qhd";
  /** Positionen der Teiler (0–1) im Standard dieser Stufe */
  standard: number[];
  /** Inhalt je Spalte (eine mehr als Teiler) */
  spalten: ReactNode[];
  /** Bezeichnung je Spalte für Bildschirmleser */
  namen: string[];
  className?: string;
  testid?: string;
}) {
  const ich = useIch();
  const { setIch } = useAuth();
  const melden = useHinweis();
  const schluessel = `${seite}@${stufe}`;
  const gespeichert = ich.aufteilung?.[schluessel];
  const werte = gueltig(gespeichert, standard.length) ? gespeichert : standard;
  const [zug, setZug] = useState<{ i: number; pos: number } | null>(null);
  const flaeche = useRef<HTMLDivElement>(null);

  const speichern = (neu: number[] | null) => {
    const vorher: Ich = ich;
    const aufteilung = { ...(ich.aufteilung ?? {}) };
    if (neu) aufteilung[schluessel] = neu; else delete aufteilung[schluessel];
    setIch({ ...ich, aufteilung });
    api<Ich>("auth/ich/", { method: "PATCH", body: { aufteilung: { [schluessel]: neu } } })
      .then((antwort) => setIch(antwort))
      .catch((e: Error) => { setIch(vorher); melden(`Aufteilung nicht gespeichert: ${e.message}`, "fehler"); });
  };
  const setze = (i: number, pos: number) => {
    const neu = werte.map((w, j) => (j === i ? Math.round(pos * 10000) / 10000 : w));
    const gleichStandard = neu.every((w, j) => Math.abs(w - standard[j]) < 0.0005);
    speichern(gleichStandard ? null : neu);
  };

  const position = (i: number, clientX: number) => {
    const r = flaeche.current?.getBoundingClientRect();
    if (!r) return werte[i];
    const nutzbar = r.width - standard.length * TEILER_BREITE;
    const roh = (clientX - r.left - i * TEILER_BREITE - TEILER_BREITE / 2) / Math.max(nutzbar, 1);
    const links = (i > 0 ? werte[i - 1] : 0) + MIN_SPALTE;
    const rechts = (i < werte.length - 1 ? werte[i + 1] : 1) - MIN_SPALTE;
    return Math.min(rechts, Math.max(links, roh));
  };

  const anzeige = zug ? werte.map((w, j) => (j === zug.i ? zug.pos : w)) : werte;
  const breiten = [...anzeige, 1].map((p, j) => p - (j ? anzeige[j - 1] : 0));
  const vorlage = breiten.map((b) => `minmax(0, ${b.toFixed(4)}fr)`).join(` ${TEILER_BREITE}px `);

  const inhalt: ReactNode[] = [];
  spalten.forEach((spalte, j) => {
    inhalt.push(<div key={`s${j}`} className="stapel flex flex-col gap-5 min-w-0" data-spalte={j}>{spalte}</div>);
    if (j < standard.length) {
      const i = j;
      const ziele = punkte(werte, i, standard);
      const einrasten = zug?.i === i ? naechster(ziele, zug.pos) : null;
      inhalt.push(
        <div key={`t${i}`} role="separator" aria-orientation="vertical" tabIndex={0} data-testid={`teiler-${seite}-${i}`}
          className={cx("teiler", zug?.i === i && "aktiv")}
          aria-label={`Spaltenteiler zwischen ${namen[i]} und ${namen[i + 1]}`}
          aria-valuemin={Math.round(ziele[0] * 100)} aria-valuemax={Math.round(ziele[ziele.length - 1] * 100)}
          aria-valuenow={Math.round(werte[i] * 100)} aria-valuetext={`links ${bruchText(werte[i])}`}
          title={`Ziehen: rastet bei ${ziele.map(bruch).join(", ")} ein · Doppelklick: Standard ${bruch(standard[i])} · Tastatur: ← →`}
          onPointerDown={(e: PointerEvent<HTMLDivElement>) => {
            if (e.button !== 0) return;
            e.preventDefault();
            e.currentTarget.setPointerCapture(e.pointerId);
            setZug({ i, pos: werte[i] });
          }}
          onPointerMove={(e: PointerEvent<HTMLDivElement>) => { if (zug?.i === i) setZug({ i, pos: position(i, e.clientX) }); }}
          onPointerUp={(e: PointerEvent<HTMLDivElement>) => {
            if (zug?.i !== i) return;
            const ziel = naechster(ziele, position(i, e.clientX));
            setZug(null);
            if (Math.abs(ziel - werte[i]) > 0.0005) setze(i, ziel);
          }}
          onPointerCancel={() => setZug(null)}
          onDoubleClick={() => speichern(null)}
          onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
            let ziel: number | undefined;
            if (e.key === "ArrowLeft") ziel = [...ziele].reverse().find((p) => p < werte[i] - 0.001);
            else if (e.key === "ArrowRight") ziel = ziele.find((p) => p > werte[i] + 0.001);
            else if (e.key === "Home") ziel = ziele[0];
            else if (e.key === "End") ziel = ziele[ziele.length - 1];
            else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); speichern(null); return; }
            else return;
            e.preventDefault();
            if (ziel !== undefined) setze(i, ziel);
          }}>
          <span className="teiler-griff" aria-hidden="true">
            <svg width="8" height="16" viewBox="0 0 8 16"><g fill="currentColor"><circle cx="2" cy="4" r="1.2" /><circle cx="6" cy="4" r="1.2" />
              <circle cx="2" cy="8" r="1.2" /><circle cx="6" cy="8" r="1.2" /><circle cx="2" cy="12" r="1.2" /><circle cx="6" cy="12" r="1.2" /></g></svg>
          </span>
          {einrasten !== null ? (
            <span className="absolute top-[10.75rem] left-[1.375rem] z-10 whitespace-nowrap px-2.5 py-1.5 rounded-lg bg-akzent text-auf-akzent text-[0.8125rem] font-medium shadow-lg"
              role="status">{bruch(einrasten)} · rastet ein · Doppelklick: Standard {bruch(standard[i])}</span>
          ) : null}
        </div>,
      );
    }
  });

  return (
    <div ref={flaeche} className={cx("grid items-start", className)} style={{ gridTemplateColumns: vorlage }} data-testid={testid}
      data-aufteilung={werte.map((w) => w.toFixed(4)).join(",")}>
      {inhalt}
    </div>
  );
}
