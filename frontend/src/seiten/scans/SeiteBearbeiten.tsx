/**
 * Seite vor der Erkennung anpassen (F161): Ecken des Blatts verschieben (Perspektive), drehen, glätten, Schräglage,
 * Darstellung (Graustufen, Farbe, Schwarz-Weiß), Kontrast und Helligkeit. Nach „Übernehmen“ wird die Seite neu
 * aufbereitet und erkannt; was automatisch erkannt wurde, steht vorbelegt da.
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

export function SeiteBearbeiten({ scan, seite, offen, onOffen }: {
  scan: Scan; seite: ScanSeite; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const [e, setE] = useState<SeitenEinstellungen>(() => anfang(seite));
  const qc = useQueryClient();
  const melden = useHinweis();
  useEffect(() => { if (offen) setE(anfang(seite)); }, [offen, seite.id]); // eslint-disable-line react-hooks/exhaustive-deps
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
  const drehen = (um: number) => setE({ ...e, drehung: (((drehung ?? 0) + um + 360) % 360) as SeitenEinstellungen["drehung"] });
  const schraeg = typeof e.schraeglage === "number" ? "wert" : e.schraeglage;
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={`Seite ${seite.nr} anpassen`} breite={980}
      beschreibung="Die Seite wird danach neu aufbereitet und erkannt. Was automatisch erkannt wurde, ist vorbelegt."
      fuss={<>
        <Knopf onClick={() => setE({ ...STANDARD })}>Alles automatisch</Knopf>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()} data-testid="seite-uebernehmen">Übernehmen und neu erkennen</Knopf>
      </>}>
      <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_18.75rem] gap-5 items-start">
        <div className="flex flex-col gap-2 min-w-0">
          {e.ecken === "aus" ? (
            <img src={bildUrl(scan.id, seite, "roh")} alt={`Seite ${seite.nr} (Original)`} className="block w-full h-auto rounded-md border border-rand" />
          ) : <EckenWahl scanId={scan.id} seite={seite} ecken={ecken} onEcken={(neu) => setE({ ...e, ecken: neu })} />}
          <span className="text-[0.8125rem] gedaempft">
            {e.ecken === "aus" ? "Ohne Zuschnitt: die ganze Seite wird verwendet."
              : "Ecken des Blatts mit der Maus (oder dem Finger) an die Ecken des Papiers ziehen – die Seite wird danach gerade gezogen."}
            {seite.info.ecken_quelle === "auto" && e.ecken === "auto" ? " Automatisch erkannt." : ""}
          </span>
        </div>
        <div className="flex flex-col gap-4">
          <Feld label="Zuschnitt">
            {() => <Segmente label="Zuschnitt" wert={Array.isArray(e.ecken) ? "hand" : e.ecken}
              onWahl={(w) => setE({ ...e, ecken: w === "hand" ? ecken : w })}
              werte={[{ wert: "auto", text: "Automatisch" }, { wert: "hand", text: "Von Hand" }, { wert: "aus", text: "Ohne" }]} />}
          </Feld>
          <Feld label="Drehung" hinweis={e.drehung === null ? `automatisch${seite.info.drehung ? ` (${seite.info.drehung}°)` : ""}` : `${drehung}° im Uhrzeigersinn`}>
            {() => (
              <div className="flex gap-2 flex-wrap">
                <Knopf klein icon="drehen_links" onClick={() => drehen(-90)} aria-label="Nach links drehen">Links</Knopf>
                <Knopf klein icon="drehen_rechts" onClick={() => drehen(90)} aria-label="Nach rechts drehen">Rechts</Knopf>
                {e.drehung !== null ? <Knopf klein variante="geist" onClick={() => setE({ ...e, drehung: null })}>automatisch</Knopf> : null}
              </div>
            )}
          </Feld>
          <Feld label="Gewellte Seite glätten" hinweis="Automatisch nur bei Fotos.">
            {() => <Segmente label="Glätten" wert={e.glaetten} onWahl={(w) => setE({ ...e, glaetten: w })}
              werte={[{ wert: "auto", text: "Automatisch" }, { wert: "ein", text: "Ein" }, { wert: "aus", text: "Aus" }]} />}
          </Feld>
          <Feld label="Schräglage" hinweis={seite.info.schraeglage != null ? `zuletzt ${String(seite.info.schraeglage).replace(".", ",")}° ausgeglichen` : undefined}>
            {(p) => (
              <div className="flex gap-2 items-center flex-wrap">
                <Segmente label="Schräglage" wert={schraeg as "auto" | "aus" | "wert"}
                  onWahl={(w) => setE({ ...e, schraeglage: w === "wert" ? Number(seite.info.schraeglage ?? 0) : w })}
                  werte={[{ wert: "auto", text: "Auto" }, { wert: "aus", text: "Aus" }, { wert: "wert", text: "Grad" }]} />
                {typeof e.schraeglage === "number" ? (
                  <input {...p} className="inp num w-20" type="number" step={0.1} min={-45} max={45} value={e.schraeglage}
                    onChange={(ev) => setE({ ...e, schraeglage: Number(ev.target.value) })} aria-label="Schräglage in Grad" />
                ) : null}
              </div>
            )}
          </Feld>
          <Feld label="Darstellung">
            {() => <Segmente label="Darstellung" wert={e.modus} onWahl={(w) => setE({ ...e, modus: w })}
              werte={[{ wert: "graustufen", text: "Graustufen" }, { wert: "farbe", text: "Farbe" }, { wert: "sw", text: "Schwarz-Weiß" }]} />}
          </Feld>
          {(["kontrast", "helligkeit"] as const).map((k) => (
            <Feld key={k} label={k === "kontrast" ? `Kontrast ${e.kontrast > 0 ? "+" : ""}${e.kontrast}` : `Helligkeit ${e.helligkeit > 0 ? "+" : ""}${e.helligkeit}`}>
              {(p) => <input {...p} type="range" min={-50} max={50} step={5} value={e[k]} className="w-full"
                onChange={(ev) => {
                  const v = Number(ev.target.value);
                  setE(k === "kontrast" ? { ...e, kontrast: v } : { ...e, helligkeit: v });
                }} />}
            </Feld>
          ))}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={e.schatten} onChange={(ev) => setE({ ...e, schatten: ev.target.checked })} />
            Schatten und ungleichmäßige Ausleuchtung ausgleichen
          </label>
          {seite.textebene_vorhanden ? (
            <label className={cx("flex items-start gap-2 text-sm")}>
              <input type="checkbox" className="mt-1" checked={e.textebene !== false} onChange={(ev) => setE({ ...e, textebene: ev.target.checked })} />
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
