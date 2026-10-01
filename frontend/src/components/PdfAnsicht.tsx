/**
 * PDF-Anzeige mit pdf.js direkt in EPM – ohne das PDF-Programm des Browsers (Adobe Reader o. Ä.), das in der
 * eingebetteten Vorschau eigene Leisten einblendet. Die Seiten werden auf <canvas> gezeichnet, offline, mit der
 * strengen CSP (kein eval, kein WebAssembly): Decoder für gescannte Dokumente (JBIG2, JPEG 2000) laufen über die
 * mitgelieferten JavaScript-Fassungen aus /pdfjs/ (siehe vite.config.ts).
 */
import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { Knopf, Ladekreis, cx } from "@/components/ui/basis";

type PdfJs = typeof import("pdfjs-dist");
let pdfjsLaden: Promise<PdfJs> | null = null;

/** pdf.js erst laden, wenn eine PDF angezeigt wird (hält das Hauptpaket klein). */
function pdfjs(): Promise<PdfJs> {
  pdfjsLaden ??= Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?worker&url"),
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
        data: daten,
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
      <div ref={ref} className="rounded-lg border border-rand bg-fein overflow-auto p-2" style={{ height: hoehe }}>
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

/** Große Ansicht: alle Seiten untereinander, Zoom. */
export function PdfLeser({ url, className, laden }: { url: string; className?: string; laden?: () => Promise<Uint8Array> }) {
  const { doc, fehler } = useDokument(url, laden);
  const [stufe, setStufe] = useState(2);
  const { ref, breite } = useBreite();
  const zoom = ZOOM[stufe];
  return (
    <div className={cx("flex flex-col gap-2 min-h-0", className)} data-testid="pdf-leser">
      <div className="flex items-center gap-2 text-[0.8125rem]">
        <Knopf klein icon="minus" aria-label="Verkleinern" disabled={stufe <= 0} onClick={() => setStufe(stufe - 1)} />
        <span className="num w-12 text-center">{Math.round(zoom * 100)} %</span>
        <Knopf klein icon="plus" aria-label="Vergrößern" disabled={stufe >= ZOOM.length - 1} onClick={() => setStufe(stufe + 1)} />
        {doc ? <span className="num gedaempft ml-2">{doc.numPages} {doc.numPages === 1 ? "Seite" : "Seiten"}</span> : null}
      </div>
      <div ref={ref} className="flex-1 min-h-0 overflow-auto rounded-lg border border-rand bg-fein p-3">
        {fehler ? <div className="py-10 text-center text-sm gedaempft">Anzeige nicht möglich: {fehler}</div>
          : doc && breite ? (
            <div className="flex flex-col gap-3">
              {Array.from({ length: doc.numPages }, (_, i) => <Seite key={i} doc={doc} nummer={i + 1} breite={breite - 24} zoom={zoom} />)}
            </div>
          ) : <div className="py-10 flex justify-center gedaempft"><Ladekreis /></div>}
      </div>
    </div>
  );
}

