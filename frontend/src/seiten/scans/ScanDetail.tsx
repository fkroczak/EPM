/**
 * Ein Scan (F160–F165): Seiten mit markierten unsicheren Wörtern, Text zum Kopieren, Anpassen und Neu-Erkennen,
 * Zuordnen mit Prüfansicht der Werte. Während der Erkennung fragt die Seite alle anderthalb Sekunden nach dem Stand.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, apiDatei } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, zahl, zeitpunkt } from "@/lib/format";
import type { Scan, ScanVorschlag, ScanZeile } from "@/lib/typen";
import { Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, Segmente, cx } from "@/components/ui/basis";
import { Dialog, Menue } from "@/components/ui/dialog";
import type { MenuEintrag } from "@/components/ui/dialog";
import { Bestaetigen } from "@/components/Bestaetigen";
import { Icon } from "@/components/ui/icon";
import { useHinweis } from "@/components/ui/hinweise";
import { ARTEN, STATUS, UNSICHER, bildUrl, bisDatum, hatErgebnis, inZwischenablage, prozent, seitenText } from "./hilfen";
import { Seitenansicht } from "./Seitenansicht";
import { SeiteBearbeiten } from "./SeiteBearbeiten";
import { Zuordnen } from "./Zuordnen";
import type { Stelle, Ziel } from "./Zuordnen";
import { PatientVorschlag } from "./PatientVorschlag";

function Fortschritt({ scan }: { scan: Scan }) {
  return (
    <div className="flex flex-col gap-1.5 px-4 sm:px-5 py-3 border-b border-rand" role="status" data-testid="scan-fortschritt">
      <div className="flex items-center gap-2 text-sm">
        <Icon name="sanduhr" />
        <span className="font-medium">{scan.status === "wartet" ? "In der Warteschlange" : "Text wird erkannt"}</span>
        <span className="gedaempft">{scan.schritt}</span>
        <span className="num ml-auto gedaempft">{scan.fortschritt} %</span>
      </div>
      <div className="fortschritt"><div className="fortschritt-fuellung" style={{ width: `${Math.max(3, scan.fortschritt)}%` }} /></div>
    </div>
  );
}

/** Text einer Seite mit gelb unterlegten unsicheren Wörtern (beim Überfahren: Sicherheit, andere Lesart) */
function SeitenText({ scan, nr }: { scan: Scan; nr: number | null }) {
  const seiten = nr === null ? scan.seiten : scan.seiten.filter((s) => s.nr === nr);
  return (
    <div className="scan-text font-mono text-[0.8125rem] leading-relaxed whitespace-pre-wrap break-words max-h-[70vh] overflow-auto
      border border-rand rounded-lg p-3 bg-flaeche" data-testid="scan-text" tabIndex={0}>
      {seiten.map((s, i) => (
        <div key={s.id} className={cx(i > 0 && "mt-4 pt-3 border-t border-dashed border-rand")}>
          {nr === null && scan.seiten.length > 1 ? <div className="text-xs gedaempft mb-1 font-sans">Seite {s.nr}</div> : null}
          {hatErgebnis(s.ergebnis) ? s.ergebnis.reihen.map((r, ri) => (
            <div key={ri}>
              {r.map((st, si) => (
                <span key={si}>
                  {si > 0 ? "\t" : null}
                  {st.w.map((w, wi) => (
                    <span key={wi}>
                      {wi > 0 ? " " : null}
                      {w[5] < UNSICHER
                        ? <span className="scan-wort-unsicher" title={`Sicherheit ${Math.round(w[5] * 100)} %${w[6] ? ` · andere Lesart: „${w[6]}“` : ""}`}>{w[0]}</span>
                        : w[0]}
                    </span>
                  ))}
                </span>
              ))}
            </div>
          )) : <span className="gedaempft font-sans">{s.status === "fehler" ? s.fehler || "Seite nicht erkannt." : "noch nicht erkannt"}</span>}
        </div>
      ))}
    </div>
  );
}

function herunterladen(daten: Uint8Array, name: string, mime: string) {
  const url = URL.createObjectURL(new Blob([daten as BlobPart], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export function ScanDetail({ id, alle, onListe, onWeg, onZugeordnet }: {
  id: number; alle: ScanZeile[]; onListe: () => void; onWeg: () => void;
  onZugeordnet: (patientId: number, dokumentId: number, titel: string) => void;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const { darf } = useAuth();
  const scan = useQuery({
    queryKey: ["scan", id],
    queryFn: () => api<Scan>(`scans/${id}/`),
    refetchInterval: (q) => (q.state.data && ["wartet", "laeuft"].includes(q.state.data.status) ? 1500 : false),
  });
  const s = scan.data;
  const [seiteIndex, setSeiteIndex] = useState(0);
  const [ansicht, setAnsicht] = useState<"seite" | "alle">("alle");
  const [zuordnen, setZuordnen] = useState(false);
  // F183: in der Ansicht mit einem Klick übernommener Patientenvorschlag (zugeordnet wird erst beim Speichern)
  const [startPatient, setStartPatient] = useState<ScanVorschlag | null>(null);
  const [stelle, setStelle] = useState<Stelle>(null);
  // Zuordnen: gewähltes Feld, in das ein Klick auf ein Wort im Bild den Wert schreibt
  const [ziel, setZiel] = useState<Ziel>(null);
  const [unsicher, setUnsicher] = useState(true);
  const [original, setOriginal] = useState(false);
  const [bereichModus, setBereichModus] = useState(false);
  // F189: Rahmen beim Zuordnen = „richtigen Bereich markieren“ (nur diesen Teil neu lesen, Zeilen als neue Werte)
  const [bereichWerte, setBereichWerte] = useState(false);
  const [neueWerte, setNeueWerte] = useState<{ nr: number; indices: number[] } | null>(null);
  const [bereich, setBereich] = useState<number[] | null>(null);
  const [staerke, setStaerke] = useState(0);
  const [bearbeiten, setBearbeiten] = useState(false);
  const [loeschen, setLoeschen] = useState(false);
  const [umbenennen, setUmbenennen] = useState<string | null>(null);
  const [zusammen, setZusammen] = useState(false);
  const [zusammenMit, setZusammenMit] = useState("");

  // beim Wechsel des Scans von vorn
  useEffect(() => { setSeiteIndex(0); setZuordnen(false); setStartPatient(null); setStelle(null); setZiel(null); setBereichModus(false); setBereichWerte(false); setNeueWerte(null); setOriginal(false); }, [id]);
  // eine markierte Stelle auf einer anderen Seite: dorthin blättern
  useEffect(() => {
    if (stelle && s && s.seiten[seiteIndex]?.nr !== stelle.seite + 1) {
      const i = s.seiten.findIndex((x) => x.nr === stelle.seite + 1);
      if (i >= 0) setSeiteIndex(i);
    }
  }, [stelle]); // eslint-disable-line react-hooks/exhaustive-deps
  // Liste aktualisieren, sobald die Erkennung fertig ist
  const status = s?.status;
  useEffect(() => { if (status) void qc.invalidateQueries({ queryKey: ["scans"] }); }, [status]); // eslint-disable-line react-hooks/exhaustive-deps

  const neu = (daten: Scan) => {
    qc.setQueryData(["scan", id], daten);
    void qc.invalidateQueries({ queryKey: ["scans"] });
  };
  const aktion = useMutation({
    mutationFn: ({ pfad, body, method }: { pfad: string; body?: unknown; method?: "POST" | "PATCH" | "DELETE" }) =>
      api<Scan>(`scans/${id}/${pfad}`, { method: method ?? "POST", body: body ?? {} }),
    onSuccess: neu,
    onError: (e) => melden(e instanceof Error ? e.message : String(e), "fehler"),
  });
  const ausschnitt = useMutation({
    mutationFn: ({ sid, box }: { sid: number; box: number[] }) =>
      api<{ scan: Scan; neu: number[] }>(`scans/${id}/seiten/${sid}/ausschnitt/`, { body: { box } }),
    onSuccess: (e) => {
      qc.setQueryData(["scan", id], e.scan);
      setNeueWerte((alt) => ({ nr: (alt?.nr ?? 0) + 1, indices: e.neu }));
    },
    onError: (e) => melden(e instanceof Error ? e.message : String(e), "fehler"),
  });
  const weg = useMutation({
    mutationFn: () => api(`scans/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      melden("Scan gelöscht.");
      setLoeschen(false);
      qc.removeQueries({ queryKey: ["scan", id] });
      void qc.invalidateQueries({ queryKey: ["scans"] });
      onWeg();
    },
  });
  const aufteilen = useMutation({
    mutationFn: (ab: number) => api<{ scan: Scan; neu: number }>(`scans/${id}/aufteilen/`, { body: { ab } }),
    onSuccess: (e) => { neu(e.scan); melden("Aufgeteilt – die folgenden Seiten sind jetzt ein eigener Scan."); setSeiteIndex(0); },
    onError: (e) => melden(e instanceof Error ? e.message : String(e), "fehler"),
  });
  const laden = useMutation({
    mutationFn: async (art: "pdf" | "textdatei") => {
      const { daten } = await apiDatei(`scans/${id}/${art}/`);
      herunterladen(daten, `${s?.titel || "Scan"}.${art === "pdf" ? "pdf" : "txt"}`, art === "pdf" ? "application/pdf" : "text/plain");
    },
    onError: (e) => melden(e instanceof Error ? e.message : String(e), "fehler"),
  });

  if (scan.isLoading) return <Karte className="min-w-0"><Laden /></Karte>;
  if (!s) return <Karte className="min-w-0 p-4"><Fehleranzeige fehler={scan.error ?? "Nicht gefunden."} /></Karte>;

  const seite = s.seiten[Math.min(seiteIndex, Math.max(0, s.seiten.length - 1))];
  const laeuft = s.status === "wartet" || s.status === "laeuft";
  const fertig = s.status === "fertig";
  const arten = s.auswertung?.arten ?? [];
  const kopieren = async (text: string) => {
    melden(await inZwischenablage(text) ? "Text kopiert." : "Kopieren nicht möglich – bitte den Text markieren und mit Strg C kopieren.",
      text ? "ok" : "fehler");
  };
  const andere = alle.filter((x) => x.id !== s.id && x.status === "fertig" && x.ist_test === s.ist_test);
  const menue: MenuEintrag[] = [
    { text: "Durchsuchbare PDF herunterladen", onClick: () => laden.mutate("pdf"), aus: !fertig },
    { text: "Text herunterladen (.txt)", onClick: () => laden.mutate("textdatei"), aus: !fertig },
    { text: "Umbenennen …", onClick: () => setUmbenennen(s.titel) },
    { text: "Alle Seiten neu erkennen", onClick: () => aktion.mutate({ pfad: "erneut/" }), aus: laeuft },
    { text: "Werte neu ermitteln", hinweis: "z. B. nach Änderungen am Laborkatalog", onClick: () => aktion.mutate({ pfad: "auswerten/" }), aus: !fertig },
    ...(s.seiten.length > 1 && seite && seite.nr > 1 ? [{
      text: `Ab Seite ${seite.nr} als eigenen Scan abtrennen`, onClick: () => aufteilen.mutate(seite.id), aus: !fertig,
      hinweis: "Stapel mit Dokumenten mehrerer Patienten trennen" }] : []),
    ...(andere.length ? [{ text: "Anderen Scan hinten anhängen …", onClick: () => { setZusammenMit(""); setZusammen(true); }, aus: !fertig }] : []),
    { text: "Löschen …", gefaehrlich: true, onClick: () => { weg.reset(); setLoeschen(true); } },
  ];

  return (
    <Karte className="min-w-0 flex flex-col" data-testid="scan-detail">
      {/* Kopf */}
      <div className="flex items-center gap-x-3 gap-y-2 flex-wrap px-4 sm:px-5 py-3 border-b border-rand">
        <button type="button" className="btn sec klein md:hidden" onClick={onListe}><Icon name="zurueck" groesse={14} />Liste</button>
        <h2 className="m-0 text-lg font-semibold min-w-0 break-words" data-testid="scan-titel">{s.titel}</h2>
        <Chip art={s.status === "fertig" ? "ok" : s.status === "fehler" ? "fehler" : "warn"} data-testid="scan-status">{STATUS[s.status]}</Chip>
        {s.quelle ? (
          <Chip title="Arbeitskopie eines Dokuments der Akte – beim Übernehmen entsteht kein neues Dokument" data-testid="scan-quelle">
            aus der Akte: {s.quelle.patient.nachname}, {s.quelle.patient.vorname}
          </Chip>
        ) : null}
        {fertig && s.sicherheit != null ? (
          <Chip art={s.unsicher ? "warn" : "neutral"} title="Sicherheit der Erkennung, nach Zeichen gewichtet">
            {prozent(s.sicherheit)} sicher{s.unsicher ? ` · ${zahl(s.unsicher)} unsichere Wörter` : ""}
          </Chip>
        ) : null}
        {arten.map((a) => <Chip key={a} art="akzent">{ARTEN[a] ?? a}</Chip>)}
        {s.ist_test ? <Chip art="warn">Test</Chip> : null}
        <div className="ml-auto flex items-center gap-2">
          {fertig && !zuordnen && darf("eintraege_erfassen") ? (
            <Knopf variante="pri" icon="patienten" onClick={() => setZuordnen(true)} data-testid="scan-zuordnen">{s.quelle ? "Werte übernehmen" : "Zuordnen"}</Knopf>
          ) : null}
          {fertig ? <Knopf icon="kopieren" onClick={() => void kopieren(s.text)} data-testid="scan-kopieren">Text kopieren</Knopf> : null}
          <Menue label="Weitere Aktionen" eintraege={menue} />
        </div>
      </div>
      <div className="flex items-center gap-x-4 gap-y-1 flex-wrap px-4 sm:px-5 py-2 border-b border-rand text-[0.8125rem] gedaempft" data-testid="scan-ablauf">
        <span>{zahl(s.seiten_anzahl || s.seiten.length)} Seite{(s.seiten_anzahl || s.seiten.length) === 1 ? "" : "n"} · hochgeladen {zeitpunkt(s.hochgeladen_am)}
          {s.hochgeladen_von_name ? ` von ${s.hochgeladen_von_name}` : ""}</span>
        <span className={cx(bisDatum(s.laeuft_ab_am) === "heute" || bisDatum(s.laeuft_ab_am) === "morgen" ? "text-warn font-medium" : undefined)}>
          wird {bisDatum(s.laeuft_ab_am)} gelöscht ({datum(s.laeuft_ab_am)})</span>
        {s.verlaengerbar ? (
          <button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer text-[0.8125rem]"
            onClick={() => aktion.mutate({ pfad: "verlaengern/" })} data-testid="scan-verlaengern">verlängern</button>
        ) : <span>Höchstdauer erreicht ({datum(s.hoechst_bis)})</span>}
        {/* Programmnamen nur im Tooltip – für die Arbeit zählt, wie der Text zustande kam (Bedienung für Pflegekräfte, 10.10.2026) */}
        {s.verfahren.length ? <span title={`gelesen mit ${s.verfahren.map((v) => ({ paddle: "PP-OCR", tesseract: "Tesseract", textebene: "Text der PDF" }[v] ?? v)).join(" + ")}`}>
          {s.verfahren.every((v) => v === "textebene") ? "Text aus der PDF übernommen" : "Text automatisch erkannt – bitte prüfen"}</span> : null}
      </div>
      {laeuft ? <Fortschritt scan={s} /> : null}
      {fertig && !zuordnen && !s.quelle && darf("eintraege_erfassen") && s.vorschlaege?.length ? (
        <div className="px-4 sm:px-5 py-3 border-b border-rand">
          <PatientVorschlag vorschlaege={s.vorschlaege} knopf="Übernehmen und zuordnen"
            onWahl={(v) => { setStartPatient(v); setZuordnen(true); }} />
        </div>
      ) : null}
      {s.status === "fehler" ? (
        <div className="px-4 sm:px-5 py-3 border-b border-rand">
          <Meldung art="fehler"><span className="flex items-center gap-3 flex-wrap">{s.fehler || "Die Erkennung ist fehlgeschlagen."}
            <Knopf klein onClick={() => aktion.mutate({ pfad: "erneut/" })}>Erneut versuchen</Knopf></span></Meldung>
        </div>
      ) : null}

      {seite ? (
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-5 px-4 sm:px-5 py-4">
          {/* Seite – beim Zuordnen bleibt sie stehen, während rechts die Felder gescrollt werden */}
          <div className={cx("flex flex-col gap-2.5 min-w-0", zuordnen && "xl:sticky xl:top-2 xl:self-start xl:max-h-[calc(100dvh-1rem)] xl:overflow-y-auto")}
            data-testid="scan-seite-spalte">
            <div className="flex items-center gap-2 flex-wrap">
              {s.seiten.length > 1 ? (
                <span className="flex items-center gap-1">
                  <Knopf klein variante="geist" aria-label="Vorige Seite" disabled={seiteIndex === 0} onClick={() => setSeiteIndex(seiteIndex - 1)}>‹</Knopf>
                  <span className="text-sm num">Seite {seite.nr} von {s.seiten.length}</span>
                  <Knopf klein variante="geist" aria-label="Nächste Seite" disabled={seiteIndex >= s.seiten.length - 1} onClick={() => setSeiteIndex(seiteIndex + 1)}>›</Knopf>
                </span>
              ) : <span className="text-sm">Seite 1</span>}
              <span className="grow" />
              <Knopf klein icon="rahmen" disabled={laeuft} onClick={() => setBearbeiten(true)} data-testid="seite-bearbeiten">Anpassen</Knopf>
              <Knopf klein icon="scan" disabled={laeuft || seite.status !== "fertig" || original} aria-pressed={bereichModus}
                variante={bereichModus && !bereichWerte ? "pri" : "sec"} onClick={() => { setBereichWerte(false); setBereichModus(!bereichModus || bereichWerte); }} data-testid="bereich-modus"
                title="Einen schlecht lesbaren Bereich mit der Maus markieren und neu erkennen lassen">Bereich neu erkennen</Knopf>
              <label className="flex items-center gap-1.5 text-[0.8125rem]">
                <input type="checkbox" checked={unsicher} onChange={(e) => setUnsicher(e.target.checked)} />unsichere Wörter
              </label>
              <label className="flex items-center gap-1.5 text-[0.8125rem]">
                <input type="checkbox" checked={original} onChange={(e) => { setOriginal(e.target.checked); setBereichModus(false); }} />Original
              </label>
            </div>
            {bereichModus ? (
              <Meldung art="info"><span className="flex items-center gap-2 flex-wrap" data-testid="bereich-anleitung">
                <span className="grow">{bereichWerte
                  ? "Mit Maus oder Finger einen Rahmen um die richtigen Zeilen ziehen. EPM liest nur diesen Teil noch einmal und zeigt die Zeilen rechts als neue Werte."
                  : "Rahmen um den Bereich aufziehen, der neu erkannt werden soll."}</span>
                <Knopf klein variante="geist" onClick={() => { setBereichModus(false); setBereichWerte(false); }}>Abbrechen</Knopf>
              </span></Meldung>
            ) : null}
            {zuordnen && ziel && !bereichModus && !original ? (
              <div className="meldung info flex items-center gap-2" role="status" data-testid="wort-waehlen">
                <Icon name="info" groesse={16} />
                <span className="grow">Für <strong className="font-semibold">{ziel.name}</strong> eine Zahl oder ein Wort im Bild anklicken.</span>
                <Knopf klein variante="geist" onClick={() => setZiel(null)}>Fertig</Knopf>
              </div>
            ) : null}
            <Seitenansicht scanId={s.id} seite={seite} unsicher={unsicher && !(zuordnen && ziel)} original={original} bereichModus={bereichModus}
              markiert={stelle && stelle.seite + 1 === seite.nr ? stelle.box : null}
              onWort={zuordnen && ziel ? (w, box) => { const st = { seite: seite.nr - 1, box }; ziel.setzen(w[0], st); setStelle(st); } : undefined}
              onBereich={(b) => {
                setBereichModus(false);
                if (bereichWerte) { setBereichWerte(false); ausschnitt.mutate({ sid: seite.id, box: b }); return; }
                setBereich(b); setStaerke(0);
              }} />
            {s.seiten.length > 1 ? (
              <div className="flex gap-2 overflow-x-auto pb-1" role="list" aria-label="Seiten" data-testid="scan-seiten">
                {s.seiten.map((x, i) => (
                  <div key={x.id} role="listitem" className={cx("shrink-0 flex flex-col items-center gap-1 rounded-md p-1 border",
                    i === seiteIndex ? "border-akzent bg-akzent-weich" : "border-transparent")}>
                    <button type="button" className="p-0 border-0 bg-transparent cursor-pointer" onClick={() => setSeiteIndex(i)}
                      aria-label={`Seite ${x.nr}`} aria-current={i === seiteIndex ? "true" : undefined}>
                      {x.status === "fertig" && x.breite ? <img src={bildUrl(s.id, x, "klein")} alt="" className="h-20 w-auto rounded border border-rand bg-white" />
                        : <span className="h-20 w-14 flex items-center justify-center rounded border border-dashed border-rand text-xs gedaempft">{x.nr}</span>}
                    </button>
                    <span className="flex items-center gap-0.5">
                      <button type="button" className="btn geist icon klein" aria-label={`Seite ${x.nr} nach vorn`} disabled={i === 0 || laeuft}
                        onClick={() => { const ids = s.seiten.map((y) => y.id); [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]]; aktion.mutate({ pfad: "reihenfolge/", body: { seiten: ids } }); setSeiteIndex(i - 1); }}>
                        <Icon name="zurueck" groesse={12} /></button>
                      <span className="text-xs num gedaempft">{x.nr}</span>
                      <button type="button" className="btn geist icon klein rotate-180" aria-label={`Seite ${x.nr} nach hinten`} disabled={i === s.seiten.length - 1 || laeuft}
                        onClick={() => { const ids = s.seiten.map((y) => y.id); [ids[i + 1], ids[i]] = [ids[i], ids[i + 1]]; aktion.mutate({ pfad: "reihenfolge/", body: { seiten: ids } }); setSeiteIndex(i + 1); }}>
                        <Icon name="zurueck" groesse={12} /></button>
                      <button type="button" className="btn geist icon klein" aria-label={`Seite ${x.nr} entfernen`} disabled={laeuft}
                        onClick={() => { aktion.mutate({ pfad: `seiten/${x.id}/entfernen/`, method: "DELETE" }); setSeiteIndex(0); }}>
                        <Icon name="x" groesse={12} /></button>
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
            {seite.info.foto || seite.info.ecken_quelle ? (
              <span className="text-xs gedaempft">
                {[seite.info.ecken_quelle === "auto" ? "Blatt automatisch gefunden und entzerrt" : seite.info.ecken_quelle === "hand" ? "Ecken von Hand gesetzt" : "",
                  seite.info.geglaettet ? "geglättet" : "", seite.info.drehung ? `um ${seite.info.drehung}° gedreht` : "",
                  seite.info.schraeglage ? `Schräglage ${String(seite.info.schraeglage).replace(".", ",")}° ausgeglichen` : "",
                  seite.info.entrauscht ? "Rauschen entfernt" : ""].filter(Boolean).join(" · ")}
              </span>
            ) : null}
            {seite.info.sparstufe ? (
              <span className="text-xs text-warn" data-testid="seite-sparsam">
                <span title={seite.info.sparstufe >= 2 ? "nur mit Tesseract erkannt" : "sparsam erkannt (ohne Glätten, kleinere Zeilensuche)"}>
                  Vereinfacht erkannt</span>
                {" "}– für diese Seite reichte der Arbeitsspeicher des Servers nicht. Bitte den Text besonders genau prüfen;
                „Anpassen“ erkennt die Seite erneut.
              </span>
            ) : null}
          </div>

          {/* Text oder Zuordnen */}
          <div className="flex flex-col gap-3 min-w-0">
            {zuordnen && fertig ? (
              <Zuordnen key={s.id} scan={s} onStelle={setStelle} ziel={ziel} onZiel={setZiel} startPatient={startPatient}
                bereichAktiv={bereichModus && bereichWerte} bereichLaedt={ausschnitt.isPending} neueWerte={neueWerte}
                onBereich={() => { const an = !(bereichModus && bereichWerte); setOriginal(false); setZiel(null); setBereichWerte(an); setBereichModus(an); }}
                onAbbrechen={() => { setZuordnen(false); setStartPatient(null); setStelle(null); setZiel(null); }}
                onFertig={(patientId, dokumentId) => { setZuordnen(false); setZiel(null); onZugeordnet(patientId, dokumentId, s.titel); }} />
            ) : (
              <>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="m-0 text-base font-semibold grow">Erkannter Text</h3>
                  {s.seiten.length > 1 ? (
                    <Segmente label="Umfang" wert={ansicht} onWahl={setAnsicht}
                      werte={[{ wert: "alle", text: "Alle Seiten" }, { wert: "seite", text: `Seite ${seite.nr}` }]} />
                  ) : null}
                  <Knopf klein icon="kopieren" disabled={!fertig}
                    onClick={() => void kopieren(ansicht === "seite" ? seitenText(seite.ergebnis) : s.text)}>Kopieren</Knopf>
                </div>
                <SeitenText scan={s} nr={ansicht === "seite" && s.seiten.length > 1 ? seite.nr : null} />
                {fertig ? (
                  <span className="text-[0.8125rem] gedaempft">
                    Gelb unterlegt: unsicher gelesen – beim Überfahren steht die Lesart des anderen Verfahrens. Tabellen werden mit
                    Tabulator kopiert und lassen sich so in eine Tabelle einfügen.
                  </span>
                ) : null}
                {fertig && arten.length ? (
                  <Meldung art="info">
                    <span className="flex items-center gap-3 flex-wrap">
                      <span>Erkannt als {arten.map((a) => ARTEN[a] ?? a).join(" und ")}
                        {s.auswertung.datum ? ` vom ${datum(s.auswertung.datum)}` : ""}
                        {s.auswertung.labor?.werte.length ? ` · ${s.auswertung.labor.werte.filter((w) => w.vorschlag).length} Laborwerte` : ""}
                        {s.auswertung.diagnosen?.length ? ` · ${s.auswertung.diagnosen.length} Diagnosen mit ICD-Code` : ""}.</span>
                      {darf("eintraege_erfassen") ? <Knopf klein onClick={() => setZuordnen(true)}>Zuordnen und Werte übernehmen</Knopf> : null}
                    </span>
                  </Meldung>
                ) : null}
              </>
            )}
          </div>
        </div>
      ) : laeuft ? null : <div className="p-5"><Meldung art="info">Keine Seiten.</Meldung></div>}

      {seite ? <SeiteBearbeiten scan={s} seite={seite} offen={bearbeiten} onOffen={setBearbeiten} /> : null}
      <Dialog offen={!!bereich} onOffen={(o) => { if (!o) setBereich(null); }} titel="Bereich neu erkennen" breite={460}
        beschreibung="Der markierte Bereich wird vergrößert und mit beiden Verfahren neu gelesen; der übrige Text der Seite bleibt."
        fuss={<>
          <Knopf onClick={() => setBereich(null)}>Abbrechen</Knopf>
          <Knopf variante="pri" laedt={aktion.isPending} data-testid="bereich-erkennen"
            onClick={() => { if (bereich && seite) aktion.mutate({ pfad: `seiten/${seite.id}/bereich/`, body: { box: bereich, staerke } }); setBereich(null); }}>Neu erkennen</Knopf>
        </>}>
        <Feld label={`Kontrast ${staerke > 0 ? "+" : ""}${staerke}`} hinweis="Bei blasser Schrift erhöhen, bei verschmierter verringern.">
          {(p) => <input {...p} type="range" min={-50} max={50} step={5} value={staerke} className="w-full" onChange={(e) => setStaerke(Number(e.target.value))} />}
        </Feld>
      </Dialog>
      <Dialog offen={umbenennen !== null} onOffen={(o) => { if (!o) setUmbenennen(null); }} titel="Scan umbenennen" breite={460}
        fuss={<>
          <Knopf onClick={() => setUmbenennen(null)}>Abbrechen</Knopf>
          <Knopf variante="pri" disabled={!umbenennen?.trim()} laedt={aktion.isPending}
            onClick={() => { aktion.mutate({ pfad: "", method: "PATCH", body: { titel: umbenennen } }); setUmbenennen(null); }}>Speichern</Knopf>
        </>}>
        <Feld label="Titel">{(p) => <Eingabe {...p} value={umbenennen ?? ""} maxLength={200} onChange={(e) => setUmbenennen(e.target.value)} />}</Feld>
      </Dialog>
      <Dialog offen={zusammen} onOffen={setZusammen} titel="Anderen Scan anhängen" breite={520}
        beschreibung="Die Seiten des gewählten Scans kommen hinter die Seiten dieses Scans; der andere Scan entfällt."
        fuss={<>
          <Knopf onClick={() => setZusammen(false)}>Abbrechen</Knopf>
          <Knopf variante="pri" disabled={!zusammenMit} laedt={aktion.isPending}
            onClick={() => { aktion.mutate({ pfad: "zusammenfuehren/", body: { mit: Number(zusammenMit) } }); setZusammen(false); }}>Anhängen</Knopf>
        </>}>
        <div className="flex flex-col gap-1.5">
          {andere.map((x) => (
            <label key={x.id} className="flex items-center gap-2 text-sm">
              <input type="radio" name="zusammen" value={x.id} checked={zusammenMit === String(x.id)} onChange={() => setZusammenMit(String(x.id))} />
              <span className="font-medium">{x.titel}</span><span className="gedaempft">{x.seiten_anzahl} Seiten · {zeitpunkt(x.hochgeladen_am)}</span>
            </label>
          ))}
        </div>
      </Dialog>
      <Bestaetigen offen={loeschen} onOffen={setLoeschen} titel="Scan löschen" knopf="Löschen" laedt={weg.isPending} fehler={weg.error}
        text={<>„{s.titel}“ wird mit allen Seiten und dem erkannten Text endgültig gelöscht.</>} onJa={() => weg.mutate()} />
    </Karte>
  );
}
