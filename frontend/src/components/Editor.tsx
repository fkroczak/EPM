/**
 * Formatierter Text: Editor (TipTap, erst bei Bedarf geladen – Lighthouse 09.10.2026: TipTap und ProseMirror machten ein
 * Drittel des Startpakets aus), Anzeige und Klartext.
 */
import { useEffect, useState } from "react";
import type { ComponentType } from "react";
import { rem } from "@/lib/masse";
import { cx } from "./ui/basis";

export type EditorProps = {
  wert: string;
  onAenderung: (html: string) => void;
  label: string;
  werkzeuge?: boolean;
  platzhalter?: string;
  hoehe?: number;
  autofokus?: boolean;
  className?: string;
  deaktiviert?: boolean;
};

/** Einmal geladen, für alle Editoren. Bewusst ohne React.lazy/Suspense: TipTap legt die Editor-Instanz schon beim
 *  Rendern an, und ein von Suspense verworfenes Rendern ließ eine bereits zerstörte Instanz zurück (Absturz im Plan). */
let geladen: ComponentType<EditorProps> | null = null;
let laden: Promise<ComponentType<EditorProps>> | null = null;
function tiptapLaden() {
  laden ??= import("./EditorTiptap").then((m) => (geladen = m.default));
  return laden;
}

/** Solange TipTap lädt: gleich hoher Platzhalter, damit nichts springt */
function Platzhalter({ werkzeuge = true, hoehe = 120, className }: EditorProps) {
  return (
    <div className={cx("flex flex-col gap-2", className)} aria-busy="true">
      {werkzeuge ? <div className="h-8" /> : null}
      <div className="inp h-auto py-2"><div style={{ minHeight: rem(hoehe) }} /></div>
    </div>
  );
}

export function Editor(props: EditorProps) {
  const [Feld, setFeld] = useState(() => geladen);
  useEffect(() => {
    if (Feld) return;
    let aktiv = true;
    void tiptapLaden().then((k) => { if (aktiv) setFeld(() => k); });
    return () => { aktiv = false; };
  }, [Feld]);
  return Feld ? <Feld {...props} /> : <Platzhalter {...props} />;
}

/** Gespeicherten, vom Backend bereinigten Text anzeigen */
export function Richtext({ html, className, leer = "—" }: { html: string; className?: string; leer?: string }) {
  if (!html) return <p className={cx("m-0 gedaempft text-sm", className)}>{leer}</p>;
  return <div className={cx("richtext", className)} dangerouslySetInnerHTML={{ __html: html }} />;
}

/** Text ohne Formatierung (für kurze Vorschauen) */
export function klartext(html: string): string {
  const d = document.createElement("div");
  d.innerHTML = html;
  return (d.textContent ?? "").replace(/\s+/g, " ").trim();
}
