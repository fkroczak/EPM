/**
 * Menüpunkt „KI (Experimentell)“ (Auftrag 5): Prüf-Queue aller Dokumente, die der KI-Dienst gelesen hat, mit Filtern,
 * Stand des Dienstes und dem Qualitäts-Dashboard aus den Korrekturen der Mitarbeiter (Auftrag 7).
 * Sichtbar ist nur, was zur aktiven Firma gehört.
 */
import { useState } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { abfrage, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { datum, zahl, zeitpunkt } from "@/lib/format";
import { DOKUMENTTYPEN, MODUS_TEXT, STATUS_ART, STATUS_TEXT, prozentText } from "@/lib/ki";
import type { KiStand, KiStatus, KiVorgangKurz } from "@/lib/ki";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Seitenkopf } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { Reiter, ReiterInhalt, useReiter } from "@/components/ui/reiter";
import { Seite } from "@/components/layout/Shell";
import { useAuth } from "@/lib/auth";

const FILTER_STATUS: { wert: string; text: string }[] = [
  { wert: "zur_pruefung,teilweise", text: "Zur Prüfung" },
  { wert: "neu,in_verarbeitung,ocr_fertig,analyse_fertig", text: "In Arbeit" },
  { wert: "nachverarbeitung", text: "Nachverarbeitung" },
  { wert: "fehler", text: "Fehler" },
  { wert: "uebernommen", text: "Übernommen" },
  { wert: "abgelehnt", text: "Abgelehnt" },
  { wert: "", text: "Alle" },
];

export function KiStandKarte({ stand }: { stand?: KiStand }) {
  if (!stand) return null;
  const d = stand.dienst;
  const e = d?.entscheidung;
  return (
    <Meldung art={!d?.laeuft ? "warn" : e?.modus === "pause" || e?.modus === "aus" ? "warn" : "info"} className="flex gap-2.5 items-start text-[0.8125rem]">
      <Icon name="aktivitaet" />
      <span data-testid="ki-stand">
        {!d ? "Der KI-Dienst ist nicht eingerichtet oder hat sich noch nicht gemeldet (sudo epm-ki einrichten)."
          : !d.laeuft ? `Der KI-Dienst meldet sich nicht (zuletzt vor ${Math.round((d.alter_s ?? 0) / 60)} Minuten).`
          : <>
            <strong>{MODUS_TEXT[e?.modus ?? ""] ?? e?.modus}</strong>
            {e?.grund ? ` – ${e.grund}` : ""}
            {` · Nachtfenster ${stand.nachtfenster.beginn.slice(0, 5)}–${stand.nachtfenster.ende.slice(0, 5)} Uhr`}
            {` · Modell: ${d.modell.eingerichtet ? (d.modell.bereit ? "bereit" : "nicht bereit / schläft") : "keins (nur Regeln)"}`}
            {d.laufend.length ? ` · in Arbeit: ${d.laufend.length}` : ""}
          </>}
      </span>
    </Meldung>
  );
}

export function KiQueue() {
  const [reiter, setReiter] = useReiter(["queue", "qualitaet"] as const);
  const stand = useQuery({ queryKey: ["ki", "stand"], queryFn: () => api<KiStand>("ki/stand/", { hintergrund: true }), refetchInterval: 30_000 });
  return (
    <Seite pfad={[{ text: "KI (Experimentell)" }]}>
      <Seitenkopf titel="KI (Experimentell)" unter="Vorschläge der lokalen KI zur Prüfung – nichts geht ohne Ihre Bestätigung in die Akte." />
      <KiStandKarte stand={stand.data} />
      <Reiter label="Bereiche" wert={reiter} onWahl={setReiter}
        eintraege={[{ wert: "queue", text: "Prüf-Queue" }, { wert: "qualitaet", text: "Qualität" }]} />
      <ReiterInhalt>{reiter === "queue" ? <Queue /> : <Qualitaet />}</ReiterInhalt>
    </Seite>
  );
}

function Queue() {
  const [status, setStatus] = useState("zur_pruefung,teilweise");
  const [typ, setTyp] = useState("");
  const [suche, setSuche] = useState("");
  const [konfidenz, setKonfidenz] = useState("");
  const [von, setVon] = useState("");
  const [bis, setBis] = useState("");
  const [anzahl, setAnzahl] = useState(50);
  const werte = { status: status || undefined, dokumenttyp: typ || undefined, suche: suche || undefined,
    konfidenz_unter: konfidenz || undefined, von: von || undefined, bis: bis || undefined, seitengroesse: anzahl };
  const liste = useQuery({
    queryKey: ["ki", "vorgaenge", werte],
    queryFn: () => api<ApiSeite<KiVorgangKurz>>(`ki/vorgaenge/${abfrage(werte)}`, { hintergrund: true }),
    placeholderData: (vorher: ApiSeite<KiVorgangKurz> | undefined) => vorher,
    refetchInterval: 30_000,
  });
  const d = liste.data;
  return (
    <>
      <div className="flex items-center gap-2.5 flex-wrap">
        <Auswahl aria-label="Status" className="w-[11rem]" value={status} onChange={(e) => setStatus(e.target.value)}>
          {FILTER_STATUS.map((s) => <option key={s.wert} value={s.wert}>{s.text}</option>)}
        </Auswahl>
        <Auswahl aria-label="Dokumenttyp" className="w-[11rem]" value={typ} onChange={(e) => setTyp(e.target.value)}>
          <option value="">Alle Dokumenttypen</option>
          {Object.entries(DOKUMENTTYPEN).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
        </Auswahl>
        <Auswahl aria-label="OCR-Sicherheit" className="w-[12rem]" value={konfidenz} onChange={(e) => setKonfidenz(e.target.value)}>
          <option value="">jede OCR-Sicherheit</option>
          <option value="0.85">OCR-Sicherheit unter 85 %</option>
          <option value="0.7">OCR-Sicherheit unter 70 %</option>
        </Auswahl>
        <Eingabe type="date" aria-label="Verarbeitet ab" className="w-[10rem]" value={von} onChange={(e) => setVon(e.target.value)} />
        <Eingabe type="date" aria-label="Verarbeitet bis" className="w-[10rem]" value={bis} onChange={(e) => setBis(e.target.value)} />
        <Eingabe type="search" aria-label="Suche" placeholder="Patient, Titel, Text …" className="w-[14rem]" value={suche}
          onChange={(e) => setSuche(e.target.value)} />
      </div>
      <Karte className="overflow-x-auto">
        {liste.isLoading ? <Laden /> : (
          <table className="tabelle" data-testid="ki-queue" aria-busy={liste.isFetching || undefined}>
            <thead><tr>
              <th className="th">Dokument</th><th className="th">Patient</th><th className="th">Typ</th><th className="th">Status</th>
              <th className="th">OCR</th><th className="th">Vorschläge</th><th className="th">Verarbeitet</th>
            </tr></thead>
            <tbody>
              {(d?.results ?? []).map((v) => (
                <tr key={v.id}>
                  <td className="td"><Link to={`/ki/${v.id}`} data-testid={`ki-vorgang-${v.id}`}>{v.dokument_titel}</Link>
                    {v.dokument_datum ? <span className="gedaempft text-[0.8125rem]"> · {datum(v.dokument_datum)}</span> : null}
                    {v.prioritaet >= 10 ? <Chip art="akzent" className="ml-1.5">angefordert</Chip> : null}</td>
                  <td className="td"><Link to={`/patienten/${v.patient}/ki`}>{v.patient_name}</Link>
                    <span className="gedaempft text-[0.8125rem]"> ({v.patient_nummer}){v.firma_name ? ` · ${v.firma_name}` : ""}</span></td>
                  <td className="td">{v.dokumenttyp_name || "—"}</td>
                  <td className="td"><Chip art={STATUS_ART[v.status as KiStatus]}>{STATUS_TEXT[v.status as KiStatus]}</Chip>
                    {v.status === "in_verarbeitung" && v.schritt ? <div className="text-[0.75rem] gedaempft">{v.schritt}</div> : null}
                    {v.fehler ? <div className="text-[0.75rem] fehlertext">{v.fehler.slice(0, 120)}</div> : null}</td>
                  <td className="td num">{prozentText(v.ocr_konfidenz)}</td>
                  <td className="td num">{v.felder_offen}{v.felder_unsicher ? <Chip art="warn" className="ml-1.5">{v.felder_unsicher} unsicher</Chip> : null}</td>
                  <td className="td num whitespace-nowrap text-[0.8125rem]">{v.fertig_am ? zeitpunkt(v.fertig_am) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {d && !d.count ? <Leer>Keine Dokumente für diese Auswahl.</Leer> : null}
        {d?.next ? <div className="px-4 py-3 border-t border-rand flex items-center gap-3"><Knopf klein onClick={() => setAnzahl(anzahl + 50)}>Weitere laden</Knopf>
          <span className="text-xs gedaempft">{zahl(d.results.length)} von {zahl(d.count)}</span></div> : null}
        <Fehleranzeige fehler={liste.error} />
      </Karte>
    </>
  );
}

type Qualitaetsdaten = {
  gruppen: { gruppe: string; name: string; entschieden: number; richtig?: number; korrigiert?: number; verworfen?: number; genauigkeit: number | null }[];
  ocr_fehlerrate: number | null; korrekturen: number; fehlerarten: { fehlerart: string; name: string; anzahl: number }[];
  verlauf: { monat: string; korrekturen: number; entschieden: number; quote: number | null }[];
  modelle: { modell: string; entschieden: number; richtig?: number; genauigkeit: number | null }[];
  vorgaenge: Record<string, number>; sekunden_je_seite: number | null;
};

function Balken({ wert }: { wert: number | null }) {
  return (
    <span className="inline-flex items-center gap-2 min-w-[8rem]">
      <span className="h-2 w-24 rounded bg-fein overflow-hidden" aria-hidden="true">
        <span className="block h-full bg-akzent" style={{ width: `${Math.round((wert ?? 0) * 100)}%` }} />
      </span>
      <span className="num text-[0.8125rem]">{prozentText(wert)}</span>
    </span>
  );
}

function Qualitaet() {
  const { darf } = useAuth();
  const q = useQuery({ queryKey: ["ki", "qualitaet"], queryFn: () => api<Qualitaetsdaten>("ki/qualitaet/") });
  const d = q.data;
  if (q.isLoading) return <Laden />;
  if (!d) return <Fehleranzeige fehler={q.error} />;
  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="ki-qualitaet">
      <Karte className="flex flex-col gap-3">
        <KartenKopf titel="Genauigkeit je Bereich" unter="unverändert übernommen ÷ entschiedene Vorschläge" />
        <table className="tabelle text-sm">
          <thead><tr><th className="th">Bereich</th><th className="th">entschieden</th><th className="th">korrigiert</th><th className="th">verworfen</th><th className="th">Genauigkeit</th></tr></thead>
          <tbody>{d.gruppen.map((g) => (
            <tr key={g.gruppe}><td className="td">{g.name}</td><td className="td num">{g.entschieden}</td><td className="td num">{g.korrigiert ?? 0}</td>
              <td className="td num">{g.verworfen ?? 0}</td><td className="td"><Balken wert={g.genauigkeit} /></td></tr>))}</tbody>
        </table>
        <div className="text-sm">OCR-Fehlerrate: <strong>{prozentText(d.ocr_fehlerrate)}</strong> · Korrekturen: {d.korrekturen}
          {d.sekunden_je_seite ? ` · ${d.sekunden_je_seite} s je Seite` : ""}</div>
      </Karte>
      <Karte className="flex flex-col gap-3">
        <KartenKopf titel="Häufigste Fehlerarten" />
        {d.fehlerarten.length ? <ul className="m-0 pl-4 text-sm">{d.fehlerarten.map((f) => <li key={f.fehlerart}>{f.name}: {f.anzahl}</li>)}</ul>
          : <Leer>Noch keine Korrekturen.</Leer>}
      </Karte>
      <Karte className="flex flex-col gap-3">
        <KartenKopf titel="Verbesserung über die Zeit" unter="Korrekturen je entschiedenem Vorschlag, je Monat (kleiner ist besser)" />
        {d.verlauf.length ? (
          <table className="tabelle text-sm"><thead><tr><th className="th">Monat</th><th className="th">Korrekturen</th><th className="th">entschieden</th><th className="th">Quote</th></tr></thead>
            <tbody>{d.verlauf.map((m) => <tr key={m.monat}><td className="td num">{m.monat}</td><td className="td num">{m.korrekturen}</td>
              <td className="td num">{m.entschieden}</td><td className="td"><Balken wert={m.quote} /></td></tr>)}</tbody></table>
        ) : <Leer>Noch kein Verlauf.</Leer>}
      </Karte>
      <Karte className="flex flex-col gap-3">
        <KartenKopf titel="Je Modell und Prompt-Fassung" />
        {d.modelle.length ? (
          <table className="tabelle text-sm"><thead><tr><th className="th">Modell · Prompt</th><th className="th">entschieden</th><th className="th">Genauigkeit</th></tr></thead>
            <tbody>{d.modelle.map((m) => <tr key={m.modell}><td className="td">{m.modell}</td><td className="td num">{m.entschieden}</td>
              <td className="td"><Balken wert={m.genauigkeit} /></td></tr>)}</tbody></table>
        ) : <Leer>Noch nichts entschieden.</Leer>}
        {darf("ki_verwalten") ? <Link to="/admin/ki?reiter=modelle" className="text-sm">Modelle vergleichen und wechseln</Link> : null}
      </Karte>
    </div>
  );
}
