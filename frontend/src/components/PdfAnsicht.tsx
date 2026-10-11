/**
 * PDF-Anzeige mit pdf.js direkt in EPM – ohne das PDF-Programm des Browsers (Adobe Reader o. Ä.), das in der
 * eingebetteten Vorschau eigene Leisten einblendet. Die Seiten werden auf <canvas> gezeichnet, offline, mit der
 * strengen CSP (kein eval, kein WebAssembly): Decoder für gescannte Dokumente (JBIG2, JPEG 2000) laufen über die
 * mitgelieferten JavaScript-Fassungen aus /pdfjs/ (siehe vite.config.ts).
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { Knopf, Ladekreis, cx } from "@/components/ui/basis";
import { rem } from "@/lib/masse";

type PdfJs = typeof import("pdfjs-dist");
let pdfjsLaden: Promise<PdfJs> | null = null;

/** pdf.js erst laden, wenn eine PDF angezeigt wird (hält das Hauptpaket klein). Die „legacy“-Fassung aus demselben
 *  Paket bringt Ersatz für sehr neue JavaScript-Funktionen mit (z. B. Math.sumPrecise): Mit der Standardfassung blieben
 *  die Seiten in nicht ganz aktuellen Browsern beim Laden stehen (gefunden 10.10.2026 mit Chromium 141). */
function pdfjs(): Promise<PdfJs> {
  pdfjsLaden ??= Promise.all([
    import("pdfjs-dist/legacy/build/pdf.mjs") as Promise<PdfJs>,
    import("pdfjs-dist/legacy/build/pdf.worker.min.mjs?worker&url"),
  ]).then(([bibliothek, worker]) => {
    bibliothek.GlobalWorkerOptions.workerSrc = worker.default;
    return bibliothek;
  });
  return pdfjsLaden;
}

/** Lädt die PDF über ``url`` oder – z. B. für eine Vorschau per POST – über ``laden`` (``url`` ist dann nur der Schlüssel). */
function useDokument(url: string, laden?: () => Promise<Uint8Array>) {
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [fehler, setFehler] = useState<string | null>(null);
  useEffect(() => {
    let aktiv = true;
    let geladen: PDFDocumentProxy | null = null;
    setDoc(null);
    setFehler(null);
    (async () => {
      let daten: Uint8Array;
      if (laden) {
        daten = await laden();
      } else {
        const antwort = await fetch(url, { credentials: "same-origin" });
        if (!antwort.ok) throw new Error(`Datei nicht verfügbar (${antwort.status}).`);
        daten = new Uint8Array(await antwort.arrayBuffer());
      }
      const bib = await pdfjs();
      const basis = new URL("/pdfjs/", window.location.origin).href;
      geladen = await bib.getDocument({
        // Kopie: pdf.js übergibt den Puffer an seinen Worker (danach ist er leer). Ohne Kopie schlug ein zweites Laden
        // derselben Daten fehl („ArrayBuffer … already detached“), z. B. im Entwicklungsmodus (StrictMode) (F180)
        data: daten.slice(),
        useWasm: false,
        wasmUrl: `${basis}wasm/`,
        standardFontDataUrl: `${basis}standard_fonts/`,
        cMapUrl: `${basis}cmaps/`,
        iccUrl: `${basis}iccs/`,
        enableXfa: false,
      }).promise;
      if (aktiv) setDoc(geladen);
      else void geladen.destroy();
    })().catch((e: unknown) => {
      if (aktiv) setFehler(e instanceof Error ? e.message : "Die PDF konnte nicht gelesen werden.");
    });
    return () => {
      aktiv = false;
      if (geladen) void geladen.destroy();
    };
  }, [url]);
  return { doc, fehler };
}

/** Eine Seite in der verfügbaren Breite (oder mit festem Zoom) zeichnen, scharf auch auf hochauflösenden Bildschirmen. */
function Seite({ doc, nummer, breite, zoom = 1 }: { doc: PDFDocumentProxy; nummer: number; breite: number; zoom?: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [fertig, setFertig] = useState(false);
  // Text der Seite für Bildschirmleser (und Tests): die Seite selbst ist nur ein Bild
  const [text, setText] = useState("");
  useEffect(() => {
    let aktiv = true;
    void doc.getPage(nummer).then((seite) => seite.getTextContent()).then((inhalt) => {
      if (!aktiv) return;
      setText(inhalt.items.map((i) => ("str" in i ? i.str + (i.hasEOL ? "\n" : " ") : "")).join("").replace(/[ \t]+/g, " ").trim());
    }).catch(() => undefined);
    return () => { aktiv = false; };
  }, [doc, nummer]);
  useEffect(() => {
    if (!breite || !canvas.current) return;
    let abbrechen: (() => void) | null = null;
    let aktiv = true;
    setFertig(false);
    void doc.getPage(nummer).then((seite) => {
      if (!aktiv || !canvas.current) return;
      const basis = seite.getViewport({ scale: 1 });
      const massstab = (breite / basis.width) * zoom;
      const dpr = window.devicePixelRatio || 1;
      const ansicht = seite.getViewport({ scale: massstab * dpr });
      const el = canvas.current;
      el.width = Math.floor(ansicht.width);
      el.height = Math.floor(ansicht.height);
      el.style.width = `${Math.floor(ansicht.width / dpr)}px`;
      el.style.height = `${Math.floor(ansicht.height / dpr)}px`;
      const auftrag = seite.render({ canvas: el, viewport: ansicht });
      abbrechen = () => auftrag.cancel();
      auftrag.promise.then(() => aktiv && setFertig(true)).catch(() => undefined);
    });
    return () => {
      aktiv = false;
      abbrechen?.();
    };
  }, [doc, nummer, breite, zoom]);
  return (
    <div className="relative bg-white shadow-sm border border-rand mx-auto" style={{ width: "fit-content" }}>
      <canvas ref={canvas} aria-label={`Seite ${nummer}`} role="img" data-testid="pdf-seite" data-fertig={fertig ? "1" : undefined} />
      <div className="sr-only" data-testid="pdf-text">{text}</div>
      {!fertig ? <span className="absolute inset-0 flex items-center justify-center gedaempft"><Ladekreis /></span> : null}
    </div>
  );
}

function useBreite() {
  const ref = useRef<HTMLDivElement>(null);
  const [breite, setBreite] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const beobachter = new ResizeObserver(([e]) => setBreite(Math.floor(e.contentRect.width)));
    beobachter.observe(ref.current);
    return () => beobachter.disconnect();
  }, []);
  return { ref, breite };
}

/** Kleine Vorschau: eine Seite, blättern. */
export function PdfVorschau({ url, titel, hoehe = 320, laden }: { url: string; titel: string; hoehe?: number; laden?: () => Promise<Uint8Array> }) {
  const { doc, fehler } = useDokument(url, laden);
  const [seite, setSeite] = useState(1);
  const { ref, breite } = useBreite();
  useEffect(() => setSeite(1), [url]);
  const anzahl = doc?.numPages ?? 0;
  return (
    <div className="flex flex-col gap-2" data-testid="pdf-vorschau" aria-label={`Vorschau ${titel}`}>
      {/* per Tastatur scrollbar (tabIndex): Bereiche mit eigenem Scrollbalken müssen fokussierbar sein (WCAG 2.1.1) */}
      <div ref={ref} className="rounded-lg border border-rand bg-fein overflow-auto p-2" style={{ height: rem(hoehe) }} tabIndex={0} role="region" aria-label={`Seite der Vorschau ${titel}`}>
        {fehler ? <div className="h-full flex items-center justify-center text-sm gedaempft text-center px-4">Vorschau nicht möglich: {fehler}</div>
          : doc && breite ? <Seite doc={doc} nummer={seite} breite={breite - 16} />
          : <div className="h-full flex items-center justify-center gedaempft"><Ladekreis /></div>}
      </div>
      {anzahl > 1 ? (
        <div className="flex items-center justify-between text-[0.8125rem]">
          <Knopf klein variante="geist" icon="pfeilLinks" aria-label="Vorherige Seite" disabled={seite <= 1} onClick={() => setSeite(seite - 1)} />
          <span className="num gedaempft">Seite {seite} von {anzahl}</span>
          <Knopf klein variante="geist" icon="pfeilRechts" aria-label="Nächste Seite" disabled={seite >= anzahl} onClick={() => setSeite(seite + 1)} />
        </div>
      ) : null}
    </div>
  );
}

const ZOOM = [0.5, 0.75, 1, 1.25, 1.5, 2];

/** Höhe ÷ Breite der ersten Seite (für „Ganze Seite“) */
function useSeitenverhaeltnis(doc: PDFDocumentProxy | null) {
  const [verhaeltnis, setVerhaeltnis] = useState(Math.SQRT2);
  useEffect(() => {
    if (!doc) return;
    let aktiv = true;
    void doc.getPage(1).then((seite) => {
      const v = seite.getViewport({ scale: 1 });
      if (aktiv && v.width > 0) setVerhaeltnis(v.height / v.width);
    }).catch(() => undefined);
    return () => { aktiv = false; };
  }, [doc]);
  return verhaeltnis;
}

/** Große Ansicht: alle Seiten untereinander, Zoom. ``einpassen``: beginnt mit „Ganze Seite“ – eine Seite passt ganz in
 *  die Fläche, ohne zu scrollen (Infusionsplan neben dem Plan, Wunsch 10.10.2026: „PDFs einfach einsehbar“). */
export function PdfLeser({ url, className, laden, einpassen, werkzeuge }: { url: string; className?: string; laden?: () => Promise<Uint8Array>; einpassen?: boolean;
  /** weitere Knöpfe rechts in der Werkzeugzeile (z. B. „Groß ansehen“, „Herunterladen“) */
  werkzeuge?: ReactNode }) {
  const { doc, fehler } = useDokument(url, laden);
  const [stufe, setStufe] = useState(2);
  // null = noch nicht gewählt: dann „Ganze Seite“, sofern die Seite dabei lesbar groß bleibt (sonst auf die Breite)
  const [ganzGewaehlt, setGanz] = useState<boolean | null>(einpassen ? null : false);
  const { ref, breite } = useBreite();
  const [hoehe, setHoehe] = useState(0);
  useEffect(() => {
    if (!ref.current) return;
    const beobachter = new ResizeObserver(([e]) => setHoehe(Math.floor(e.contentRect.height)));
    beobachter.observe(ref.current);
    return () => beobachter.disconnect();
  }, [ref]);
  const verhaeltnis = useSeitenverhaeltnis(doc);
  const zoom = ZOOM[stufe];
  // „Ganze Seite“: so breit, dass die Seite in die Höhe passt (höchstens die volle Breite)
  // Rand (Innenabstand 2 × 12 px, Rahmen der Seite) großzügig abziehen: ein Scrollbalken, der kommt und geht, würde die
  // Breite und damit die Seite immer wieder ändern
  const ganzBreite = hoehe > 0 ? Math.min(breite - 24, Math.floor((hoehe - 36) / verhaeltnis)) : breite - 24;
  const ganz = ganzGewaehlt ?? ganzBreite >= 360;
  return (
    <div className={cx("flex flex-col gap-2 min-h-0", className)} data-testid="pdf-leser">
      <div className="flex items-center gap-2 text-[0.8125rem] flex-wrap">
        <Knopf klein icon="minus" aria-label="Verkleinern" disabled={!ganz && stufe <= 0} onClick={() => { if (ganz) setGanz(false); else setStufe(stufe - 1); }} />
        <span className="num w-12 text-center">{ganz ? "Seite" : `${Math.round(zoom * 100)} %`}</span>
        <Knopf klein icon="plus" aria-label="Vergrößern" disabled={!ganz && stufe >= ZOOM.length - 1} onClick={() => { if (ganz) setGanz(false); else setStufe(stufe + 1); }} />
        <Knopf klein variante={ganz ? "pri" : undefined} aria-pressed={ganz} onClick={() => setGanz(!ganz)}
          title="Eine Seite ganz zeigen (aus: auf die Breite vergrößern)">Ganze Seite</Knopf>
        {doc ? <span className="num gedaempft ml-2">{doc.numPages} {doc.numPages === 1 ? "Seite" : "Seiten"}</span> : null}
        {werkzeuge ? <span className="ml-auto flex gap-2 flex-wrap">{werkzeuge}</span> : null}
      </div>
      <div ref={ref} className="flex-1 min-h-0 overflow-auto rounded-lg border border-rand bg-fein p-3 [scrollbar-gutter:stable]" tabIndex={0} role="region" aria-label="PDF-Seiten">
        {fehler ? <div className="py-10 text-center text-sm gedaempft">Anzeige nicht möglich: {fehler}</div>
          : doc && breite ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: doc.numPages }, (_, i) => <Seite key={i} doc={doc} nummer={i + 1}
                breite={ganz ? Math.max(120, ganzBreite) : breite - 24} zoom={ganz ? 1 : zoom} />)}
            </div>
          ) : <div className="py-10 flex justify-center gedaempft"><Ladekreis /></div>}
      </div>
    </div>
  );
}
