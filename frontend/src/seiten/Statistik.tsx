/**
 * Menüpunkt „Statistik“ (F193): anonymisierte Auswertung für Berichte der Stiftung – Kennzahlen als Kacheln,
 * Verteilungen als Balken (eigenes SVG wie GewichtsDiagramm/Sparkline, keine weitere Bibliothek), jeweils mit dem
 * Vorzeitraum. Export als PDF (Briefkopf) und CSV (Excel); jeder Export steht im Audit-Log.
 *
 * Die Seite zeigt nur, was der Server schickt: kleine Zahlen (1–4) kommen schon als „< 5“ ohne Wert, im Bestand ist
 * dann alles gerundet („≈“). Differenzen zum Vorzeitraum werden nur aus angezeigten Werten gebildet und entfallen bei
 * „< 5“. Gedacht für 1920 × 1080 ohne Scrollen: Kopf, eine Reihe Kacheln, darunter vier Diagramme im Raster 2 × 2.
 */
import { useState } from "react";
import { useSearchParams } from "react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { abfrage, api, apiDatei } from "@/lib/api";
import { useIch } from "@/lib/auth";
import { datum, zeitpunkt } from "@/lib/format";
import type { Statistik as Daten, StatistikVerteilung, StatistikZelle } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Segmente, Seitenkopf, cx } from "@/components/ui/basis";
import { PdfDialog } from "@/components/PdfDialog";
import { useHinweis } from "@/components/ui/hinweise";

type Art = "jahr" | "quartal" | "frei";

function heute() {
  const d = new Date();
  return { jahr: d.getFullYear(), quartal: Math.floor(d.getMonth() / 3) + 1, iso: d.toLocaleDateString("sv-SE", { timeZone: "Europe/Berlin" }) };
}

/** Parameter aus der Adresse (so lässt sich eine Auswertung als Lesezeichen merken); Standard: laufendes Jahr */
function useWahl() {
  const [params, setParams] = useSearchParams();
  const h = heute();
  const art = (["jahr", "quartal", "frei"].includes(params.get("art") ?? "") ? params.get("art") : "jahr") as Art;
  const wahl = {
    art,
    jahr: Number(params.get("jahr")) || h.jahr,
    quartal: Number(params.get("quartal")) || h.quartal,
    von: params.get("von") ?? `${h.jahr}-01-01`,
    bis: params.get("bis") ?? h.iso,
  };
  const setzen = (neu: Partial<typeof wahl>) => {
    const w = { ...wahl, ...neu };
    setParams(new URLSearchParams(Object.entries(w.art === "jahr" ? { art: w.art, jahr: w.jahr }
      : w.art === "quartal" ? { art: w.art, jahr: w.jahr, quartal: w.quartal } : { art: w.art, von: w.von, bis: w.bis })
      .map(([k, v]) => [k, String(v)])), { replace: true });
  };
  const anfrage = art === "jahr" ? { art, jahr: wahl.jahr } : art === "quartal" ? { art, jahr: wahl.jahr, quartal: wahl.quartal }
    : { art, von: wahl.von, bis: wahl.bis };
  return { wahl, setzen, anfrage };
}

/** Veränderung zum Vorzeitraum – nur aus angezeigten Werten; bei „< 5“ keine Angabe, bei gerundeten „≈“. */
function differenz(jetzt: StatistikZelle, vorher: StatistikZelle): { text: string; titel: string } | null {
  if (jetzt.wert == null || vorher.wert == null) return null;
  const d = jetzt.wert - vorher.wert;
  const ca = jetzt.status === "gerundet" || vorher.status === "gerundet" ? "≈ " : "";
  const text = d === 0 ? "±0" : `${d > 0 ? "+" : "−"}${Math.abs(d).toLocaleString("de-DE")}`;
  return { text: `${ca}${text}`, titel: ca ? "Veränderung aus gerundeten Werten (ungefähr)" : "Veränderung zum Vorzeitraum" };
}

function Wert({ z, className }: { z: StatistikZelle; className?: string }) {
  return (
    <span className={cx("num", z.status === "klein" && "gedaempft", className)}
      title={z.status === "klein" ? "1 bis 4 Fälle – zum Schutz der Patienten nicht genau angegeben"
        : z.status === "gerundet" ? "auf volle 5 gerundet, damit kleine Zahlen nicht zurückrechenbar sind" : undefined}>
      {z.anzeige}
    </span>
  );
}

function Kachel({ text, jetzt, vorher, vergleich, testid }: { text: string; jetzt: StatistikZelle; vorher: StatistikZelle;
  vergleich: string; testid: string }) {
  const d = differenz(jetzt, vorher);
  return (
    <Karte className="px-4 py-3 flex flex-col gap-1 min-w-0" data-testid={testid}>
      <span className="text-[0.8125rem] gedaempft leading-tight min-h-[2lh]">{text}</span>
      <Wert z={jetzt} className="text-[1.625rem] font-semibold leading-tight" />
      <span className="text-xs gedaempft truncate" title={`${vergleich}: ${vorher.anzeige}`}>
        {vergleich}: <Wert z={vorher} />{d ? <span className="ml-1.5" title={d.titel}>({d.text})</span> : null}
      </span>
    </Karte>
  );
}

/**
 * Waagerechte Balken je Gruppe: dunkel der Zeitraum, hell der Vorzeitraum. „< 5“ hat keinen Balken (die Länge
 * verriete den Wert), nur den Text. Die Zahlen stehen immer als Text daneben; Farbe trägt keine eigene Information.
 */
function Balken({ zeilen, titel, jetzt, vorher }: { titel: string; jetzt: string; vorher: string;
  zeilen: { schluessel: string; text: string; a: StatistikZelle; b: StatistikZelle | null }[] }) {
  const oben = Math.max(1, ...zeilen.flatMap((z) => [z.a.wert ?? 0, z.b?.wert ?? 0]));
  const B = 100;
  if (!zeilen.length) return <Leer>Keine Akten in diesem Zeitraum.</Leer>;
  return (
    <table className="w-full text-sm border-collapse" aria-label={titel}>
      <thead className="sr-only"><tr><th>Gruppe</th><th>{jetzt}</th><th>{vorher}</th></tr></thead>
      <tbody>
        {zeilen.map((z) => (
          <tr key={z.schluessel} className="align-middle">
            <th scope="row" className="font-normal text-left py-1 pr-3 w-[38%] max-w-0 truncate" title={z.text}>{z.text}</th>
            <td className="py-1 pr-2" aria-hidden="true">
              <svg viewBox={`0 0 ${B} 12`} preserveAspectRatio="none" className="w-full h-[0.875rem] block" focusable="false">
                {z.a.wert ? <rect x="0" y="0" width={(z.a.wert / oben) * B} height="7" rx="1" fill="var(--reihe-1)" /> : null}
                {z.b?.wert ? <rect x="0" y="8" width={(z.b.wert / oben) * B} height="4" rx="1" fill="var(--rand)" /> : null}
              </svg>
            </td>
            <td className="py-1 text-right whitespace-nowrap w-[4.5rem]"><Wert z={z.a} className="font-medium" /></td>
            <td className="py-1 pl-2 text-right whitespace-nowrap w-[4rem] text-xs">{z.b ? <Wert z={z.b} className="gedaempft" /> : <span className="gedaempft">0</span>}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Verteilung({ d, name, text }: { d: Daten; name: StatistikVerteilung; text: string }) {
  const vorher = new Map(d.vorher.verteilungen[name].map((z) => [z.schluessel, z.zelle]));
  const zeilen = d.werte.verteilungen[name].map((z) => ({ schluessel: z.schluessel, text: z.text, a: z.zelle, b: vorher.get(z.schluessel) ?? null }));
  // Gruppen, die es nur im Vorzeitraum gab (z. B. ein Versorger ohne aktive Patienten mehr)
  for (const z of d.vorher.verteilungen[name]) {
    if (!zeilen.some((x) => x.schluessel === z.schluessel)) {
      zeilen.push({ schluessel: z.schluessel, text: z.text, a: { wert: 0, anzeige: "0", status: "exakt" }, b: z.zelle });
    }
  }
  return (
    <Karte className="px-4 py-3 flex flex-col gap-2 min-h-0 min-w-0" data-testid={`statistik-${name}`}>
      <KartenKopf titel={text} rechts={<span className="text-xs gedaempft flex items-center gap-3" aria-hidden="true">
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-2 rounded-sm" style={{ background: "var(--reihe-1)" }} />{d.zeitraum.titel}</span>
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-1 rounded-sm" style={{ background: "var(--rand)" }} />{d.vergleich.titel}</span>
      </span>} />
      <div className="min-h-0 overflow-y-auto">
        <Balken zeilen={zeilen} titel={text} jetzt={d.zeitraum.titel} vorher={d.vergleich.titel} />
      </div>
    </Karte>
  );
}

function speichern(daten: Uint8Array, typ: string, dateiname: string) {
  const url = URL.createObjectURL(new Blob([daten as BlobPart], { type: typ }));
  const a = document.createElement("a");
  a.href = url;
  a.download = dateiname;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function dateinameAus(kopf: Headers, ersatz: string) {
  const m = /filename\*=UTF-8''([^;]+)/.exec(kopf.get("Content-Disposition") ?? "");
  return m ? decodeURIComponent(m[1]) : ersatz;
}

export function Statistik() {
  const ich = useIch();
  const melden = useHinweis();
  const { wahl, setzen, anfrage } = useWahl();
  const [pdf, setPdf] = useState(false);
  const h = heute();
  const jahre = Array.from({ length: 12 }, (_, i) => h.jahr - i);
  const daten = useQuery({
    // je Firma eigener Stand (Umschalter oben links)
    queryKey: ["statistik", ich.firma, anfrage],
    queryFn: () => api<Daten>(`statistik/${abfrage(anfrage)}`),
    placeholderData: (vorher: Daten | undefined) => vorher,
  });
  const csv = useMutation({
    mutationFn: () => apiDatei(`statistik/csv/${abfrage(anfrage)}`),
    onSuccess: ({ daten: d, kopf }) => {
      speichern(d, "text/csv;charset=utf-8", dateinameAus(kopf, "Statistik.csv"));
      melden("CSV heruntergeladen. Der Export steht im Audit-Log.");
    },
  });
  const d = daten.data;
  const unter = d ? `${d.firma?.name ?? ""} · Stichtag ${datum(d.zeitraum.stichtag)} · Vergleich: ${d.vergleich.titel}` : "Anonymisierte Auswertung";
  return (
    <Seite pfad={[{ text: "Statistik" }]} className="statistik-seite">
      <Seitenkopf titel="Statistik" unter={unter} rechts={<>
        <Knopf icon="dokument" disabled={!d} onClick={() => setPdf(true)}>PDF</Knopf>
        <Knopf icon="herunterladen" disabled={!d} laedt={csv.isPending} onClick={() => csv.mutate()}>CSV</Knopf>
      </>} />
      <div className="flex items-center gap-3 flex-wrap" data-testid="statistik-zeitraum">
        <Segmente label="Zeitraum" wert={wahl.art} onWahl={(art) => setzen({ art })} werte={[
          { wert: "jahr", text: "Kalenderjahr" }, { wert: "quartal", text: "Quartal" }, { wert: "frei", text: "Frei von–bis" },
        ]} />
        {wahl.art !== "frei" ? (
          <Auswahl aria-label="Jahr" className="w-auto" value={wahl.jahr} onChange={(e) => setzen({ jahr: Number(e.target.value) })}>
            {jahre.map((j) => <option key={j} value={j}>{j}</option>)}
          </Auswahl>
        ) : null}
        {wahl.art === "quartal" ? (
          <Segmente label="Quartal" wert={String(wahl.quartal)} onWahl={(q) => setzen({ quartal: Number(q) })}
            werte={["1", "2", "3", "4"].map((q) => ({ wert: q, text: `${q}. Q.` }))} />
        ) : null}
        {wahl.art === "frei" ? <>
          <label className="flex items-center gap-1.5 text-sm">von
            <Eingabe type="date" aria-label="von" className="w-auto" value={wahl.von} max={h.iso} onChange={(e) => e.target.value && setzen({ von: e.target.value })} />
          </label>
          <label className="flex items-center gap-1.5 text-sm">bis
            <Eingabe type="date" aria-label="bis" className="w-auto" value={wahl.bis} max={h.iso} onChange={(e) => e.target.value && setzen({ bis: e.target.value })} />
          </label>
        </> : null}
        {d && (d.werte.gerundet || d.vorher.gerundet) ? <Chip art="warn" title={d.regel} data-testid="statistik-gerundet">kleine Zahlen geschützt, Werte gerundet</Chip> : null}
        {daten.isFetching ? <span className="text-xs gedaempft">wird geladen …</span> : null}
      </div>
      <Fehleranzeige fehler={daten.error ?? csv.error} />
      {daten.isLoading ? <Laden /> : d ? <>
        <div className="grid gap-[var(--abstand,0.75rem)] grid-cols-2 sm:grid-cols-4 hd:grid-cols-7" data-testid="statistik-kacheln">
          {d.kennzahlen.map((k) => (
            <Kachel key={k.schluessel} text={k.text} jetzt={d.werte.kennzahlen[k.schluessel]} vorher={d.vorher.kennzahlen[k.schluessel]}
              vergleich={d.vergleich.titel} testid={`kennzahl-${k.schluessel}`} />
          ))}
        </div>
        <div className="grid gap-[var(--abstand,0.75rem)] schmal:grid-cols-2 statistik-diagramme min-h-0">
          {d.verteilungen.map((v) => <Verteilung key={v.schluessel} d={d} name={v.schluessel} text={v.text} />)}
        </div>
        <p className="m-0 text-xs gedaempft leading-normal" data-testid="statistik-regel">
          {d.regel} {d.hinweise.join(" ")} Stand {zeitpunkt(d.erstellt_am)}.
        </p>
      </> : null}
      {d ? <PdfDialog offen={pdf} onOffen={setPdf} titel={`Statistik ${d.zeitraum.titel}`} pfad={`statistik/pdf/${abfrage(anfrage)}`}
        dateiname={`Statistik-${d.zeitraum.titel.replace(/[^0-9A-Za-zÄÖÜäöüß]+/g, "-")}.pdf`} /> : null}
    </Seite>
  );
}
