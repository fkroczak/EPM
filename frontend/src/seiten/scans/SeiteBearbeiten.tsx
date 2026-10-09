/**
 * Seite vor der Erkennung anpassen (F161): Ecken des Blatts verschieben (Perspektive), drehen, glätten, Schräglage,
 * Darstellung (Graustufen, Farbe, Schwarz-Weiß), Kontrast und Helligkeit. Nach „Übernehmen“ wird die Seite neu
 * aufbereitet und erkannt; was automatisch erkannt wurde, steht vorbelegt da. Die Vorschau zeigt die Seite so
 * aufbereitet, wie sie mit den gewählten Einstellungen erkannt wird (vom Server, ohne Erkennung).
 */
import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Scan, ScanSeite, SeitenEinstellungen } from "@/lib/typen";
import { Dialog } from "@/components/ui/dialog";
import { Fehleranzeige, Feld, Knopf, Segmente, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { useHinweis } from "@/components/ui/hinweise";
import { bildUrl } from "./hilfen";

const STANDARD: SeitenEinstellungen = {
  ecken: "auto", glaetten: "auto", drehung: null, schraeglage: "auto", schatten: true, modus: "graustufen",
  kontrast: 0, helligkeit: 0, textebene: true,
};
const GANZ = [[0, 0], [1, 0], [1, 1], [0, 1]];

function anfang(seite: ScanSeite): SeitenEinstellungen {
  return { ...STANDARD, ...seite.einstellungen } as SeitenEinstellungen;
}

/** Ecken verschieben: vier Griffe über dem Rohbild */
function EckenWahl({ scanId, seite, ecken, onEcken }: {
  scanId: number; seite: ScanSeite; ecken: number[][]; onEcken: (e: number[][]) => void;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [griff, setGriff] = useState<number | null>(null);
  const b = seite.roh_breite || 1000;
  const h = seite.roh_hoehe || 1414;
  const bewegen = (ev: ReactPointerEvent) => {
    if (griff === null || !svg.current) return;
    const r = svg.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
    const y = Math.max(0, Math.min(1, (ev.clientY - r.top) / r.height));
    onEcken(ecken.map((p, i) => (i === griff ? [Number(x.toFixed(4)), Number(y.toFixed(4))] : p)));
  };
  const punkte = ecken.map(([x, y]) => `${x * b},${y * h}`).join(" ");
  const r = Math.max(b, h) * 0.014;
  return (
    <div className="relative mx-auto select-none" style={{ maxWidth: `min(100%, ${Math.round(56 * b / h)}vh)` }}>
      <img src={bildUrl(scanId, seite, "roh")} alt={`Seite ${seite.nr} (Original)`} draggable={false}
        className="block w-full h-auto rounded-md border border-rand bg-white" />
      <svg ref={svg} viewBox={`0 0 ${b} ${h}`} preserveAspectRatio="none" className="absolute inset-0 w-full h-full touch-none"
        onPointerMove={bewegen} onPointerUp={() => setGriff(null)} onPointerLeave={() => setGriff(null)}>
        <polygon points={punkte} className="scan-ecken" />
        {ecken.map(([x, y], i) => (
          <circle key={i} cx={x * b} cy={y * h} r={r} className="scan-griff" data-testid={`ecke-${i}`}
            onPointerDown={(ev) => { ev.currentTarget.ownerSVGElement?.setPointerCapture(ev.pointerId); setGriff(i); }}>
            <title>{["oben links", "oben rechts", "unten rechts", "unten links"][i]} – ziehen zum Verschieben</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

/** Die Seite mit den gewählten Einstellungen aufbereitet – vom Server, kurz nach der letzten Änderung */
function Vorschau({ scanId, seite, e }: { scanId: number; seite: ScanSeite; e: SeitenEinstellungen }) {
  const [url, setUrl] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(true);
  const [fehler, setFehler] = useState<unknown>(null);
  const aktuell = useRef<string | null>(null);
  const schluessel = JSON.stringify(e);
  useEffect(() => {
    const abbruch = new AbortController();
    setLaedt(true);
    const zeit = window.setTimeout(() => {
      api<Blob>(`scans/${scanId}/seiten/${seite.id}/vorschau/`, { body: { einstellungen: e }, alsBlob: true, signal: abbruch.signal })
        .then((bild) => {
          if (aktuell.current) URL.revokeObjectURL(aktuell.current);
          aktuell.current = URL.createObjectURL(bild);
          setUrl(aktuell.current);
          setFehler(null);
          setLaedt(false);
        })
        .catch((f: unknown) => {
          if (abbruch.signal.aborted) return;
          setFehler(f);
          setLaedt(false);
        });
    }, 350);
    return () => { window.clearTimeout(zeit); abbruch.abort(); };
  }, [scanId, seite.id, schluessel]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { if (aktuell.current) URL.revokeObjectURL(aktuell.current); }, []);
  return (
    <div className="relative flex flex-col items-center gap-2" aria-busy={laedt} data-testid="seite-vorschau">
      {url ? (
        <img src={url} alt={`Seite ${seite.nr} (Vorschau)`}
          className={cx("block max-w-full max-h-[60vh] w-auto h-auto rounded-md border border-rand bg-white transition-opacity", laedt && "opacity-60")} />
      ) : (
        <div className="w-full h-[40vh] rounded-md border border-rand grid place-items-center gedaempft text-sm">
          {fehler ? "" : "Vorschau wird erstellt …"}
        </div>
      )}
      {laedt && url ? <span className="absolute top-2 right-2 text-[0.75rem] rounded bg-white/90 px-2 py-0.5 border border-rand">aktualisiert …</span> : null}
      <Fehleranzeige fehler={fehler} />
    </div>
  );
}

export function SeiteBearbeiten({ scan, seite, offen, onOffen }: {
  scan: Scan; seite: ScanSeite; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const [e, setE] = useState<SeitenEinstellungen>(() => anfang(seite));
  const [ansicht, setAnsicht] = useState<"vorschau" | "ecken">("vorschau");
  // Einstellungen außer den Ecken: gleich in der Vorschau zeigen
  const setze = (neu: SeitenEinstellungen) => { setE(neu); setAnsicht("vorschau"); };
  const qc = useQueryClient();
  const melden = useHinweis();
  useEffect(() => { if (offen) { setE(anfang(seite)); setAnsicht("vorschau"); } }, [offen, seite.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const automatisch = seite.info.ecken ?? null;
  const ecken = Array.isArray(e.ecken) ? e.ecken : e.ecken === "auto" ? (automatisch ?? GANZ) : GANZ;
  const speichern = useMutation({
    mutationFn: () => api<Scan>(`scans/${scan.id}/seiten/${seite.id}/`, { method: "PATCH", body: { einstellungen: e } }),
    onSuccess: (neu) => {
      qc.setQueryData(["scan", scan.id], neu);
      void qc.invalidateQueries({ queryKey: ["scans"] });
      melden(`Seite ${seite.nr} wird neu aufbereitet und erkannt.`);
      onOffen(false);
    },
  });
  const drehung = e.drehung ?? (seite.info.drehung as SeitenEinstellungen["drehung"]) ?? 0;
  const drehen = (um: number) => setze({ ...e, drehung: (((drehung ?? 0) + um + 360) % 360) as SeitenEinstellungen["drehung"] });
  const schraeg = typeof e.schraeglage === "number" ? "wert" : e.schraeglage;
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={`Seite ${seite.nr} anpassen`} breite={980}
      beschreibung="Die Seite wird danach neu aufbereitet und erkannt. Was automatisch erkannt wurde, ist vorbelegt."
      fuss={<>
        <Knopf onClick={() => setze({ ...STANDARD })}>Alles automatisch</Knopf>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()} data-testid="seite-uebernehmen">Übernehmen und neu erkennen</Knopf>
      </>}>
      <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_18.75rem] gap-5 items-start">
        <div className="flex flex-col gap-2 min-w-0">
          <Segmente label="Ansicht" wert={ansicht} onWahl={setAnsicht}
            werte={[{ wert: "vorschau", text: "Vorschau" }, { wert: "ecken", text: e.ecken === "aus" ? "Original" : "Ecken setzen" }]} />
          {ansicht === "vorschau" ? <Vorschau scanId={scan.id} seite={seite} e={e} /> : e.ecken === "aus" ? (
            <img src={bildUrl(scan.id, seite, "roh")} alt={`Seite ${seite.nr} (Original)`} className="block w-full h-auto rounded-md border border-rand" />
          ) : <EckenWahl scanId={scan.id} seite={seite} ecken={ecken} onEcken={(neu) => setE({ ...e, ecken: neu })} />}
          <span className="text-[0.8125rem] gedaempft">
            {ansicht === "vorschau" ? "So wird die Seite aufbereitet und erkannt (verkleinert; Glätten gewellter Seiten erst beim Übernehmen)."
              : e.ecken === "aus" ? "Ohne Zuschnitt: die ganze Seite wird verwendet."
              : "Ecken des Blatts mit der Maus (oder dem Finger) an die Ecken des Papiers ziehen – die Seite wird danach gerade gezogen."}
            {ansicht === "ecken" && seite.info.ecken_quelle === "auto" && e.ecken === "auto" ? " Automatisch erkannt." : ""}
          </span>
        </div>
        <div className="flex flex-col gap-4">
          <Feld label="Zuschnitt">
            {() => <Segmente label="Zuschnitt" wert={Array.isArray(e.ecken) ? "hand" : e.ecken}
              onWahl={(w) => { setE({ ...e, ecken: w === "hand" ? ecken : w }); setAnsicht(w === "hand" ? "ecken" : "vorschau"); }}
              werte={[{ wert: "auto", text: "Automatisch" }, { wert: "hand", text: "Von Hand" }, { wert: "aus", text: "Ohne" }]} />}
          </Feld>
          <Feld label="Drehung" hinweis={e.drehung === null ? `automatisch${seite.info.drehung ? ` (${seite.info.drehung}°)` : ""}` : `${drehung}° im Uhrzeigersinn`}>
            {() => (
              <div className="flex gap-2 flex-wrap">
                <Knopf klein icon="drehen_links" onClick={() => drehen(-90)} aria-label="Nach links drehen">Links</Knopf>
                <Knopf klein icon="drehen_rechts" onClick={() => drehen(90)} aria-label="Nach rechts drehen">Rechts</Knopf>
                {e.drehung !== null ? <Knopf klein variante="geist" onClick={() => setze({ ...e, drehung: null })}>automatisch</Knopf> : null}
              </div>
            )}
          </Feld>
          <Feld label="Gewellte Seite glätten" hinweis="Automatisch nur bei Fotos.">
            {() => <Segmente label="Glätten" wert={e.glaetten} onWahl={(w) => setze({ ...e, glaetten: w })}
              werte={[{ wert: "auto", text: "Automatisch" }, { wert: "ein", text: "Ein" }, { wert: "aus", text: "Aus" }]} />}
          </Feld>
          <Feld label="Schräglage" hinweis={seite.info.schraeglage != null ? `zuletzt ${String(seite.info.schraeglage).replace(".", ",")}° ausgeglichen` : undefined}>
            {(p) => (
              <div className="flex gap-2 items-center flex-wrap">
                <Segmente label="Schräglage" wert={schraeg as "auto" | "aus" | "wert"}
                  onWahl={(w) => setze({ ...e, schraeglage: w === "wert" ? Number(seite.info.schraeglage ?? 0) : w })}
                  werte={[{ wert: "auto", text: "Auto" }, { wert: "aus", text: "Aus" }, { wert: "wert", text: "Grad" }]} />
                {typeof e.schraeglage === "number" ? (
                  <input {...p} className="inp num w-20" type="number" step={0.1} min={-45} max={45} value={e.schraeglage}
                    onChange={(ev) => setze({ ...e, schraeglage: Number(ev.target.value) })} aria-label="Schräglage in Grad" />
                ) : null}
              </div>
            )}
          </Feld>
          <Feld label="Darstellung">
            {() => <Segmente label="Darstellung" wert={e.modus} onWahl={(w) => setze({ ...e, modus: w })}
              werte={[{ wert: "graustufen", text: "Graustufen" }, { wert: "farbe", text: "Farbe" }, { wert: "sw", text: "Schwarz-Weiß" }]} />}
          </Feld>
          {(["kontrast", "helligkeit"] as const).map((k) => (
            <Feld key={k} label={k === "kontrast" ? `Kontrast ${e.kontrast > 0 ? "+" : ""}${e.kontrast}` : `Helligkeit ${e.helligkeit > 0 ? "+" : ""}${e.helligkeit}`}>
              {(p) => <input {...p} type="range" min={-50} max={50} step={5} value={e[k]} className="w-full"
                onChange={(ev) => {
                  const v = Number(ev.target.value);
                  setze(k === "kontrast" ? { ...e, kontrast: v } : { ...e, helligkeit: v });
                }} />}
            </Feld>
          ))}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={e.schatten} onChange={(ev) => setze({ ...e, schatten: ev.target.checked })} />
            Schatten und ungleichmäßige Ausleuchtung ausgleichen
          </label>
          {seite.textebene_vorhanden ? (
            <label className={cx("flex items-start gap-2 text-sm")}>
              <input type="checkbox" className="mt-1" checked={e.textebene !== false} onChange={(ev) => setze({ ...e, textebene: ev.target.checked })} />
              <span>Text der PDF übernehmen (statt neu zu erkennen)<span className="block text-[0.8125rem] gedaempft">Die Seite enthält bereits Text. Ausschalten, wenn er unbrauchbar ist (z. B. von einem Kopierer).</span></span>
            </label>
          ) : null}
          <span className="text-[0.8125rem] gedaempft flex items-center gap-1.5"><Icon name="info" />Für einen einzelnen unleserlichen Bereich gibt es „Bereich neu erkennen“ in der Seitenansicht.</span>
        </div>
      </div>
      <Fehleranzeige fehler={speichern.error} />
    </Dialog>
  );
}
