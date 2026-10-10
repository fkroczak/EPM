/**
 * Administration › System: Wartung ohne SSH (Wunsch 10.10.2026, F179 – „Der Praxismanager soll sich nie wieder per SSH
 * auf den Server schalten müssen“). Dienste einzeln neu starten, Version zurückschalten, Update-Paket hochladen bzw.
 * erstellen, OCR-Modelle einspielen, Zertifikat erneuern oder importieren, Protokolle ansehen. Alles als Auftrag an den
 * Systemagenten (feste Liste), gefährliches mit Passwort und zweitem Faktor, alles im Audit-Log.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useIch } from "@/lib/auth";
import { dateigroesse, relativ, uhrzeit, zeitpunkt } from "@/lib/format";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { ZweiFaktorFehlt } from "@/components/ZweiFaktorFehlt";
import { useZweiterFaktor } from "@/components/ZweiterFaktor";
import type { Auftrag, Uebersicht, VerwaltungAktion } from "./System";

const warten = (ms: number) => new Promise((r) => setTimeout(r, ms));

// ---------------------------------------------------------------- Bestätigen (wie unter Tätigkeiten)
/**
 * Auftrag an den Server mit der Bestätigung, die das Backend für diese Aktion verlangt: „einfach“ = Rückfrage,
 * „2fa“ = eigenes Passwort und zweiter Faktor; „warnen“ = Beginn und Hinweis an die angemeldeten Benutzer.
 */
export function AuftragDialog({ offen, titel, aktion, pfad, body, daten, knopf, children, onZu, onFertig }: {
  offen: boolean; titel: string; aktion: VerwaltungAktion | undefined; pfad: string; body?: Record<string, unknown>;
  daten: Uebersicht; knopf: string; children?: ReactNode; onZu: () => void; onFertig?: (a: Auftrag) => void;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const ich = useIch();
  const zf = useZweiterFaktor();
  const [kennwort, setKennwort] = useState("");
  const [minuten, setMinuten] = useState("0");
  const [text, setText] = useState("");
  const los = useMutation({
    mutationFn: () => api<Auftrag>(pfad, { body: {
      ...(body ?? {}), ...(aktion?.warnen ? { minuten: Number(minuten), hinweis: text.trim() || undefined } : {}),
      ...(aktion?.bestaetigung === "2fa" ? { kennwort, ...zf.body } : {}) } }),
    onSuccess: (a) => {
      void qc.invalidateQueries({ queryKey: ["system"] });
      void qc.invalidateQueries({ queryKey: ["systemhinweis"] });
      melden(`${a.name}: Auftrag an den Server übergeben.`);
      onFertig?.(a);
      onZu();
    },
  });
  useEffect(() => {
    if (offen) { setKennwort(""); zf.zuruecksetzen(); setMinuten(aktion?.warnen && daten.angemeldet.some((s) => !s.eigene) ? "5" : "0"); setText(""); los.reset(); }
  }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!offen || !aktion) return null;
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const zfa = aktion.bestaetigung === "2fa";
  const namen = [...new Set(daten.angemeldet.filter((s) => !s.eigene).map((s) => s.name))];
  const bereit = !zfa || (!!ich.zweiter_faktor && !!kennwort && zf.bereit);
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel={titel} beschreibung={aktion.beschreibung} breite={zfa ? 600 : 520}
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante={zfa ? "dng" : "pri"} laedt={los.isPending} disabled={!bereit} onClick={() => los.mutate()}>{knopf}</Knopf></>}>
      <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); if (bereit) los.mutate(); }}>
        {children}
        {aktion.sichern ? <Meldung art="info">Vorher erstellt der Server automatisch eine Sicherung. Schlägt sie fehl, wird nichts verändert.</Meldung> : null}
        {!daten.agent.erreichbar ? <Meldung art="warn">Der Systemagent auf dem Server meldet sich gerade nicht.</Meldung> : null}
        {aktion.warnen ? (
          <>
            <Feld label="Beginn" hinweis={namen.length ? `Angemeldet: ${namen.join(", ")} – sie sehen den Hinweis oben auf jeder Seite.`
              : "Gerade ist niemand sonst angemeldet."}>
              {(p) => <Auswahl {...p} value={minuten} onChange={(e) => setMinuten(e.target.value)}>
                {daten.minuten.map((m) => <option key={m} value={m}>{m === 0 ? "sofort" : `in ${m} Minuten`}</option>)}
              </Auswahl>}
            </Feld>
            <Feld label="Hinweis an die Benutzer" hinweis="leer = Standardtext; Uhrzeit des Beginns wird angehängt" fehler={f.hinweis}>
              {(p) => <Textfeld {...p} rows={2} maxLength={400} value={text} onChange={(e) => setText(e.target.value)} />}
            </Feld>
          </>
        ) : null}
        {zfa ? (
          <>
            <ZweiFaktorFehlt />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
              <Feld label="Ihr Passwort" fehler={f.kennwort} pflicht>
                {(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}
              </Feld>
              {zf.feld(f.code)}
            </div>
          </>
        ) : null}
        {Object.entries(f).filter(([k]) => !["kennwort", "code", "hinweis"].includes(k)).map(([k, t]) => <Meldung key={k} art="fehler">{t}</Meldung>)}
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

function Zeile({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(8.125rem,36%)_1fr] gap-3 py-1 text-sm border-b border-rand last:border-b-0">
      <dt className="gedaempft">{label}</dt>
      <dd className="m-0 min-w-0 break-words">{children}</dd>
    </div>
  );
}

// ---------------------------------------------------------------- Dienste (Container) einzeln neu starten
const DIENST_TEXT: Record<string, string> = {
  backend: "Django – Anmeldung, Akten, alle Daten; Neustart dauert etwa 30 Sekunden",
  web: "Nginx – liefert die Oberfläche aus; Neustart in wenigen Sekunden",
  ocr: "Texterkennung für Scans; laufende Erkennungen beginnen danach neu",
  db: "PostgreSQL – die Datenbank; EPM ist während des Neustarts nicht erreichbar",
};

export function DiensteKarte({ daten, offen }: { daten: Uebersicht; offen: Set<string> }) {
  const [wahl, setWahl] = useState<string | null>(null);
  const container = daten.host?.container?.liste ?? [];
  return (
    <Karte className="px-5 py-4 flex flex-col gap-2" data-testid="dienste-karte">
      <KartenKopf titel="Dienste" unter="Einzelne Container neu starten, z. B. wenn die Texterkennung hängt – statt „docker compose restart“ per SSH." />
      {(daten.dienste ?? []).map((d) => {
        const c = container.find((x) => x.dienst === d);
        const gut = c && c.zustand === "running" && (!c.gesundheit || c.gesundheit === "healthy");
        return (
          <div key={d} className="flex items-start justify-between gap-3 py-2 border-b border-rand last:border-b-0" data-testid={`dienst-${d}`}>
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-sm font-medium flex items-center gap-2 flex-wrap">{d}
                {c ? <Chip art={gut ? "ok" : "fehler"}>{c.zustand === "running" ? "läuft" : c.zustand}{c.gesundheit ? ` · ${c.gesundheit === "healthy" ? "gesund" : c.gesundheit}` : ""}</Chip>
                  : <Chip>Zustand unbekannt</Chip>}</span>
              <span className="text-xs gedaempft">{DIENST_TEXT[d] ?? ""}{c?.status ? ` · ${c.status}` : ""}</span>
            </div>
            <Knopf klein variante="dng" disabled={!daten.agent.verzeichnis || offen.has("server:dienst_neustart")}
              laedt={offen.has("server:dienst_neustart")} onClick={() => setWahl(d)} aria-label={`${d} neu starten`}>Neu starten</Knopf>
          </div>
        );
      })}
      <AuftragDialog offen={!!wahl} titel={`Dienst „${wahl}“ neu starten`} aktion={daten.verwaltung?.dienst_neustart}
        pfad="system/dienste/neustart/" body={{ dienst: wahl }} daten={daten} knopf="Bestätigen und neu starten" onZu={() => setWahl(null)}>
        {wahl ? <Meldung art="info">{DIENST_TEXT[wahl]}</Meldung> : null}
      </AuftragDialog>
    </Karte>
  );
}

// ---------------------------------------------------------------- Hochladen in Stücken (wie bei den Sicherungen)
type Upload = NonNullable<Uebersicht["uploads"]>[number];

/** Datei in Stücken hochladen; setzt nach einer Unterbrechung an der Stelle fort, die der Server meldet. */
function useStueckweise(art: "paket" | "ocr") {
  const qc = useQueryClient();
  const abbruch = useRef(false);
  const [stand, setStand] = useState<{ upload?: string; erhalten: number; laeuft: boolean; fehler?: string }>({ erhalten: 0, laeuft: false });
  const start = async (datei: File, teil: number) => {
    abbruch.current = false;
    let upload = stand.upload;
    let versatz = stand.erhalten;
    setStand((s) => ({ ...s, laeuft: true, fehler: undefined }));
    try {
      if (!upload) {
        const r = await api<{ upload: string; erhalten: number }>("system/hochladen/", { body: { art, name: datei.name, groesse: datei.size } });
        upload = r.upload;
        versatz = r.erhalten;
      }
      let versuche = 0;
      while (versatz < datei.size) {
        if (abbruch.current) return null;
        try {
          const r = await api<{ erhalten: number }>(`system/hochladen/${upload}/?versatz=${versatz}`, { method: "PUT", roh: datei.slice(versatz, versatz + teil) });
          versatz = r.erhalten;
          versuche = 0;
        } catch (e) {
          const erhalten = e instanceof ApiFehler && e.status === 409 ? (e.daten as { erhalten?: number } | null)?.erhalten : undefined;
          if (typeof erhalten === "number") { versatz = erhalten; continue; }
          if (e instanceof ApiFehler || ++versuche > 5) throw e;
          await warten(1500 * versuche);
        }
        setStand({ upload, erhalten: versatz, laeuft: true });
      }
      setStand({ upload, erhalten: versatz, laeuft: false });
      void qc.invalidateQueries({ queryKey: ["system", "uebersicht"] });
      return upload;
    } catch (e) {
      setStand({ upload, erhalten: versatz, laeuft: false, fehler: e instanceof Error && e.message ? e.message : "Die Verbindung wurde unterbrochen." });
      return null;
    }
  };
  const zuruecksetzen = () => { abbruch.current = true; setStand({ erhalten: 0, laeuft: false }); };
  return { stand, start, zuruecksetzen };
}

/** Datei wählen, hochladen, danach einspielen (Auftrag) – für Update-Pakete und OCR-Modelle */
function HochladenKarte({ art, titel, unter, hinweis, knopf, daten, offen, testid, children }: {
  art: "paket" | "ocr"; titel: string; unter: string; hinweis: string; knopf: string; daten: Uebersicht; offen: Set<string>; testid: string;
  children?: ReactNode;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const eingabe = useRef<HTMLInputElement>(null);
  const [datei, setDatei] = useState<File | null>(null);
  const [einspielen, setEinspielen] = useState<Upload | null>(null);
  const { stand, start, zuruecksetzen } = useStueckweise(art);
  const max = daten.upload?.max?.[art] ?? 0;
  const teil = daten.upload?.teil ?? 4 * 1024 * 1024;
  const falsch = !!datei && !datei.name.toLowerCase().endsWith(".tar");
  const zuGross = !!datei && !!max && datei.size > max;
  const aktion = art === "paket" ? "epm_paket" : "ocr_modelle";
  const liste = (daten.uploads ?? []).filter((u) => u.art === art);
  const verwerfen = useMutation({
    mutationFn: (u: Upload) => api(`system/hochladen/${u.upload}/`, { method: "DELETE" }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["system", "uebersicht"] }); melden("Hochgeladene Datei verworfen."); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const prozent = datei?.size ? Math.min(100, Math.round((100 * stand.erhalten) / datei.size)) : 0;
  const hochladen = async () => {
    if (!datei) return;
    const upload = await start(datei, teil);
    if (upload) {
      setEinspielen({ upload, art, name: datei.name, groesse: datei.size, erhalten: datei.size, vollstaendig: true, von: "", begonnen_am: null });
      setDatei(null);
      zuruecksetzen();
      if (eingabe.current) eingabe.current.value = "";
    }
  };
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid={testid}>
      <KartenKopf titel={titel} unter={unter} />
      {children}
      {daten.austausch === false ? <Meldung art="fehler">Die Ordner für das Hoch- und Herunterladen fehlen auf dem Server (einmal „EPM aktualisieren“).</Meldung> : null}
      <div className="flex items-center gap-2.5 flex-wrap">
        <Knopf icon="hochladen" disabled={stand.laeuft} onClick={() => eingabe.current?.click()}>Datei auswählen</Knopf>
        <span className="text-sm min-w-0 break-all">{datei ? <>{datei.name} <span className="gedaempft num">· {dateigroesse(datei.size)}</span></> : <span className="gedaempft">keine Datei gewählt</span>}</span>
        <input ref={eingabe} type="file" hidden aria-label={`Datei: ${titel}`} accept=".tar,application/x-tar"
          onChange={(e) => { setDatei(e.target.files?.[0] ?? null); zuruecksetzen(); }} />
        <Knopf variante="pri" icon="hochladen" laedt={stand.laeuft} disabled={!datei || falsch || zuGross || stand.laeuft || daten.austausch === false}
          onClick={() => void hochladen()}>{stand.upload ? "Fortsetzen" : "Hochladen"}</Knopf>
      </div>
      {falsch ? <span className="text-sm text-fehler" role="alert">Bitte eine .tar-Datei wählen.</span>
        : zuGross ? <span className="text-sm text-fehler" role="alert">Die Datei ist größer als erlaubt ({dateigroesse(max)}).</span>
        : <span className="text-xs gedaempft">{hinweis}</span>}
      {stand.laeuft || stand.upload ? (
        <div className="flex flex-col gap-1.5" data-testid={`${testid}-fortschritt`}>
          <div className="flex justify-between text-sm"><span>{datei?.name}</span><span className="num">{dateigroesse(stand.erhalten)} · {prozent} %</span></div>
          <div className="h-2 rounded-full bg-fein overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={prozent} aria-label="Fortschritt des Hochladens">
            <div className="h-full rounded-full bg-akzent transition-[width]" style={{ width: `${prozent}%` }} />
          </div>
        </div>
      ) : null}
      {stand.fehler ? <Meldung art="fehler">{stand.fehler}{stand.upload ? " Mit „Fortsetzen“ geht es an derselben Stelle weiter." : ""}</Meldung> : null}
      {liste.length ? (
        <div className="flex flex-col" data-testid={`${testid}-uploads`}>
          <span className="text-sm font-semibold">Hochgeladen, noch nicht eingespielt</span>
          {liste.map((u) => (
            <div key={u.upload} className="flex items-center justify-between gap-3 py-1.5 border-b border-rand last:border-b-0 text-sm flex-wrap">
              <span className="min-w-0 break-all">{u.name} <span className="gedaempft num">· {dateigroesse(u.erhalten)}{u.vollstaendig ? "" : ` von ${dateigroesse(u.groesse)}`}
                {u.begonnen_am ? ` · ${relativ(u.begonnen_am, true)}` : ""}</span>{u.vollstaendig ? null : <Chip art="warn" className="ml-2">unvollständig</Chip>}</span>
              <span className="flex gap-1.5">
                {u.vollstaendig ? <Knopf klein variante="pri" disabled={offen.has(`server:${aktion}`)} laedt={offen.has(`server:${aktion}`)}
                  onClick={() => setEinspielen(u)}>{knopf}</Knopf> : null}
                <Knopf klein variante="geist" disabled={offen.has(`server:${aktion}`)} onClick={() => verwerfen.mutate(u)}>Verwerfen</Knopf>
              </span>
            </div>
          ))}
        </div>
      ) : null}
      <AuftragDialog offen={!!einspielen} titel={einspielen ? `${knopf}: ${einspielen.name}` : knopf} aktion={daten.verwaltung?.[aktion]}
        pfad={`system/hochladen/${einspielen?.upload}/einspielen/`} daten={daten} knopf={`Bestätigen: ${knopf}`} onZu={() => setEinspielen(null)}>
        {einspielen ? <Meldung art="info">{einspielen.name} · {dateigroesse(einspielen.groesse)}. Der Server prüft den Inhalt (nur bekannte
          Dateien, Prüfsummen) und zeigt die SHA-256 der Datei in der Ausgabe – mit der Anzeige beim Erstellen vergleichen.</Meldung> : null}
      </AuftragDialog>
    </Karte>
  );
}

// ---------------------------------------------------------------- Software: Version, Zurückschalten, Pakete, OCR-Modelle
export function SoftwareBereich({ daten, offen, onAktualisieren }: { daten: Uebersicht; offen: Set<string>; onAktualisieren: () => void }) {
  const h = daten.host && daten.host.aktuell ? daten.host : null;
  const v = h?.versionen;
  const pakete = h?.pakete;
  const [zurueck, setZurueck] = useState<string | null>(null);
  const [erstellen, setErstellen] = useState(false);
  const update = daten.aktionen.find((a) => a.code === "epm_update");
  const ocr = daten.epm.texterkennung?.verfahren?.paddle;
  return (
    <div className="stapel grid grid-cols-1 hd:grid-cols-2 gap-4 items-start">
      <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="versionen-karte">
        <KartenKopf titel="EPM-Version" unter={`läuft: ${v?.aktiv || daten.epm.version}`}
          rechts={update ? <Knopf variante="dng" icon="neustart" disabled={!update.erlaubt || !daten.agent.verzeichnis || offen.has("server:epm_update")}
            laedt={offen.has("server:epm_update")} onClick={onAktualisieren}>EPM aktualisieren</Knopf> : null} />
        {v?.quelle === "paket" ? <Meldung art="info">Dieser Server bekommt Updates nur als Paket von der Test-VM (kein Internet) – rechts „Update-Paket einspielen“.</Meldung> : null}
        {!h ? <span className="text-sm gedaempft">Die Liste der Versionen kommt vom Systemagenten.</span>
          : !v?.verfuegbar ? <Meldung art="warn">Versionen nicht abrufbar{v?.hinweis ? `: ${v.hinweis}` : ""}.</Meldung> : (
          <table className="tabelle" data-testid="versionen">
            <thead><tr><th className="th">Version</th><th className="th">gebaut</th><th className="th" /></tr></thead>
            <tbody>{v.liste.map((x) => (
              <tr key={x.tag} data-testid={`version-${x.tag}`}>
                <td className="td num text-[0.8125rem]">{x.tag}</td>
                <td className="td text-[0.8125rem] gedaempft">{x.erstellt.slice(0, 16)}</td>
                <td className="td text-right">{x.aktiv ? <Chip art="ok">läuft</Chip> : !x.vollstaendig ? <Chip>unvollständig</Chip>
                  : <Knopf klein disabled={offen.has("server:epm_zurueck")} onClick={() => setZurueck(x.tag)} aria-label={`Auf ${x.tag} zurückschalten`}>Zurückschalten</Knopf>}</td>
              </tr>))}</tbody>
          </table>
        )}
        <span className="text-xs gedaempft">Der Server behält die Images der letzten Versionen. Zurückschalten dreht Datenbank-Migrationen nicht zurück –
          deshalb sichert der Server vorher.</span>
      </Karte>

      <div className="flex flex-col gap-4">
        <HochladenKarte art="paket" titel="Update-Paket einspielen" testid="paket-karte" daten={daten} offen={offen} knopf="Einspielen"
          unter="Für Server ohne Internet: das Paket der Test-VM hochladen statt per scp – dann prüfen und einspielen (epm-update --paket)."
          hinweis="epm-paket-<Version>.tar · der Server prüft Inhalt und Prüfsummen, sichert und stellt um; geht etwas schief, läuft die bisherige Version weiter." />
        <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="paket-erstellen-karte">
          <KartenKopf titel="Update-Paket erstellen" unter="Nur auf der Test-VM: Paket der laufenden, getesteten Version für den Server ohne Internet."
            rechts={<Knopf disabled={!daten.agent.verzeichnis || offen.has("server:epm_paket_erstellen")} laedt={offen.has("server:epm_paket_erstellen")}
              onClick={() => setErstellen(true)}>Paket erstellen</Knopf>} />
          {pakete?.bereit.length ? pakete.bereit.map((p) => (
            <div key={p.datei} className="flex items-center justify-between gap-3 text-sm flex-wrap">
              <span>{p.datei} <span className="gedaempft num">· {dateigroesse(p.groesse)}{p.bis ? ` · bis ${uhrzeit(p.bis)} Uhr` : ""}</span></span>
              <a className="btn sec klein" href={`/api/system/pakete/${p.datei}/`} download><Icon name="herunterladen" />Herunterladen</a>
            </div>
          )) : <span className="text-xs gedaempft">{pakete?.erstellt.length ? `Zuletzt erstellt: ${pakete.erstellt.map((p) => p.tag).join(", ")}. ` : ""}
            Nach dem Erstellen liegt das Paket 2 Stunden zum Herunterladen bereit.</span>}
        </Karte>
        <HochladenKarte art="ocr" titel="OCR-Modelle einspielen" testid="ocr-karte" daten={daten} offen={offen} knopf="Einspielen"
          unter="Modelle der zweiten Texterkennung (PP-OCRv5), offline vorbereitet mit werkzeuge/ocr-modelle.sh – statt scp und epm-ocr-modelle."
          hinweis="epm-ocr-modelle-<Revision>.tar · danach „EPM aktualisieren“, dann baut der Server die Modelle ins Image.">
          <dl className="m-0">
            <Zeile label="Vorrat auf dem Server">{h?.ocr_vorrat?.vorhanden ? `${h.ocr_vorrat.dateien} Dateien · ${dateigroesse(h.ocr_vorrat.groesse)}${h.ocr_vorrat.geaendert ? ` · ${relativ(h.ocr_vorrat.geaendert, true)}` : ""}` : "keiner"}</Zeile>
            <Zeile label="Im laufenden Image">{ocr ? <Chip art={ocr.bereit ? "ok" : "warn"}>{ocr.bereit ? "PP-OCRv5 bereit" : "nur Tesseract"}</Chip> : "—"}</Zeile>
          </dl>
        </HochladenKarte>
      </div>
      <AuftragDialog offen={!!zurueck} titel={`Auf Version ${zurueck} zurückschalten`} aktion={daten.verwaltung?.epm_zurueck}
        pfad="system/versionen/zurueck/" body={{ tag: zurueck }} daten={daten} knopf="Bestätigen und zurückschalten" onZu={() => setZurueck(null)}>
        <Meldung art="warn">EPM läuft danach mit {zurueck} (bisher {v?.aktiv}). Datenbank-Migrationen der neueren Version bleiben –
          startet die ältere Version damit nicht, die Sicherung von vorher wiederherstellen oder wieder aktualisieren.</Meldung>
      </AuftragDialog>
      <AuftragDialog offen={erstellen} titel="Update-Paket erstellen" aktion={daten.verwaltung?.epm_paket_erstellen} pfad="system/pakete/erstellen/"
        daten={daten} knopf="Paket erstellen" onZu={() => setErstellen(false)} />
    </div>
  );
}

// ---------------------------------------------------------------- Zertifikat
/** PEM-Datei lesen (Zertifikat, Schlüssel, CA): nur kleine Textdateien */
function PemFeld({ label, wert, onWert, fehler, pflicht }: { label: string; wert: string; onWert: (s: string) => void; fehler?: string; pflicht?: boolean }) {
  const eingabe = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  return (
    <div className="feld">
      <span>{label}{pflicht ? " *" : ""}</span>
      <div className="flex items-center gap-2.5 flex-wrap">
        <Knopf klein icon="hochladen" onClick={() => eingabe.current?.click()}>Datei wählen</Knopf>
        <span className="text-sm">{wert ? <>{name || "eingefügt"} <Chip art="ok">gelesen</Chip></> : <span className="gedaempft">keine Datei</span>}</span>
        <input ref={eingabe} type="file" hidden aria-label={label} accept=".pem,.crt,.cer,.key,text/plain"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            if (f.size > 20000) { onWert(""); setName(`${f.name} (zu groß)`); return; }
            setName(f.name);
            onWert(await f.text());
          }} />
      </div>
      {fehler ? <span className="fehlertext" role="alert">{fehler}</span> : null}
    </div>
  );
}

export function ZertifikatBereich({ daten, offen }: { daten: Uebersicht; offen: Set<string> }) {
  const h = daten.host && daten.host.aktuell ? daten.host : null;
  const z = h?.zertifikat;
  const [erneuern, setErneuern] = useState(false);
  const [importieren, setImportieren] = useState(false);
  const [pem, setPem] = useState({ zertifikat: "", schluessel: "", ca: "" });
  const tage = z?.tage ?? null;
  const art = tage == null ? undefined : tage < 7 ? "fehler" : tage < 30 ? "warn" : "ok";
  return (
    <div className="stapel grid grid-cols-1 hd:grid-cols-2 gap-4 items-start">
      <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="zertifikat-karte">
        <KartenKopf titel="Serverzertifikat" unter="Für HTTPS und Passkeys; Geräte, die der eigenen CA vertrauen, zeigen keine Warnung."
          rechts={z?.vorhanden && tage != null ? <Chip art={art}>{tage < 0 ? "abgelaufen" : `noch ${tage} Tage`}</Chip> : null} />
        {!h ? <span className="text-sm gedaempft">Der Stand des Zertifikats kommt vom Systemagenten.</span> : !z?.vorhanden ? (
          <Meldung art="warn">Kein Zertifikat gefunden.</Meldung>
        ) : (
          <dl className="m-0">
            <Zeile label="Inhaber">{z.inhaber || "—"}</Zeile>
            <Zeile label="Namen">{z.namen || "—"}</Zeile>
            <Zeile label="Aussteller">{z.aussteller || "—"}{z.eigene_ca ? <Chip art="ok" className="ml-1.5">eigene CA</Chip> : z.selbst_signiert ? <Chip art="warn" className="ml-1.5">selbst signiert</Chip> : null}</Zeile>
            <Zeile label="Gültig bis"><span data-testid="zertifikat-ablauf">{z.gueltig_bis ? zeitpunkt(z.gueltig_bis) : "—"}</span></Zeile>
          </dl>
        )}
        {z?.selbst_signiert ? <Meldung art="warn">Selbst signiert: Browser warnen, Passkeys gehen so nicht. Abhilfe: eigene CA einrichten (einmalig bei der
          Ersteinrichtung) oder ein Zertifikat der OPNsense importieren.</Meldung> : null}
        {tage != null && tage < 30 && z?.ca_schluessel ? <Meldung art="warn">Läuft bald ab – bitte „Zertifikat erneuern“.</Meldung> : null}
        <div className="flex gap-2 flex-wrap">
          <Knopf variante={tage != null && tage < 30 ? "dng" : "sec"} disabled={!z?.ca_schluessel || offen.has("server:zertifikat_erneuern")}
            title={z?.ca_schluessel ? undefined : "nur mit eigener CA auf dem Server"} laedt={offen.has("server:zertifikat_erneuern")}
            onClick={() => setErneuern(true)}>Zertifikat erneuern</Knopf>
          <Knopf disabled={offen.has("server:zertifikat_importieren")} onClick={() => { setPem({ zertifikat: "", schluessel: "", ca: "" }); setImportieren(true); }}>Zertifikat importieren</Knopf>
          {z?.ca_download ? <a className="btn geist" href="/epm-ca.crt" download><Icon name="herunterladen" />Stammzertifikat (CA)</a> : null}
        </div>
      </Karte>
      <Karte className="px-5 py-4 flex flex-col gap-2 text-sm">
        <KartenKopf titel="Stammzertifikat auf Geräten" />
        <p className="m-0">Einmal je PC und Telefon installieren: <a href="/epm-ca.crt" download>epm-ca.crt herunterladen</a>, dann</p>
        <ul className="m-0 pl-5 flex flex-col gap-1">
          <li>Windows: Doppelklick › Zertifikat installieren › Lokaler Computer › „Vertrauenswürdige Stammzertifizierungsstellen“</li>
          <li>iPhone: Profil laden › Einstellungen › Allgemein › VPN und Geräteverwaltung › installieren; danach unter Info ›
            Zertifikatsvertrauenseinstellungen einschalten</li>
          <li>Android: Einstellungen › Sicherheit › Verschlüsselung und Anmeldedaten › Zertifikat installieren › CA-Zertifikat</li>
        </ul>
        <span className="text-xs gedaempft">Ausführlich in der Hilfe unter „Passkey statt Code“. Erneuern ändert nichts an den Geräten, solange die CA dieselbe bleibt.</span>
      </Karte>
      <AuftragDialog offen={erneuern} titel="Zertifikat erneuern" aktion={daten.verwaltung?.zertifikat_erneuern} pfad="system/zertifikat/erneuern/"
        daten={daten} knopf="Bestätigen und erneuern" onZu={() => setErneuern(false)} />
      <AuftragDialog offen={importieren} titel="Zertifikat importieren" aktion={daten.verwaltung?.zertifikat_importieren} pfad="system/zertifikat/importieren/"
        body={{ zertifikat: pem.zertifikat, schluessel: pem.schluessel, ca: pem.ca || undefined }} daten={daten} knopf="Bestätigen und übernehmen"
        onZu={() => setImportieren(false)}>
        <span className="text-sm">PEM-Dateien wählen (Text, „-----BEGIN …“). Der Schlüssel geht nur an den Server – er steht nie in der Datenbank
          oder im Audit-Log. Er darf nicht mit einem Passwort geschützt sein.</span>
        <PemFeld label="Zertifikat (CRT)" pflicht wert={pem.zertifikat} onWert={(s) => setPem((p) => ({ ...p, zertifikat: s }))} />
        <PemFeld label="Privater Schlüssel (KEY)" pflicht wert={pem.schluessel} onWert={(s) => setPem((p) => ({ ...p, schluessel: s }))} />
        <PemFeld label="CA-Zertifikat (optional)" wert={pem.ca} onWert={(s) => setPem((p) => ({ ...p, ca: s }))} />
      </AuftragDialog>
    </div>
  );
}

// ---------------------------------------------------------------- Protokolle (nur lesend)
type Protokoll = { quelle: string; name: string; zeilen: number; abgerufen_am: string; text: string };

export function ProtokolleBereich({ daten, auftraege }: { daten: Uebersicht; auftraege: Auftrag[] }) {
  const qc = useQueryClient();
  const quellen = daten.host?.protokolle ?? [];
  const [quelle, setQuelle] = useState("backend");
  const [zeilen, setZeilen] = useState("500");
  const [filter, setFilter] = useState("");
  const [kennung, setKennung] = useState<string | null>(null);
  const abrufen = useMutation({
    mutationFn: () => api<Auftrag>("system/protokolle/", { body: { quelle, zeilen: Number(zeilen) } }),
    onSuccess: (a) => { setKennung(a.kennung); void qc.invalidateQueries({ queryKey: ["system", "auftraege"] }); },
  });
  const auftrag = kennung ? auftraege.find((a) => a.kennung === kennung) : undefined;
  const fertig = !!auftrag && !auftrag.offen;
  const text = useQuery({
    queryKey: ["system", "protokoll", kennung],
    queryFn: () => api<Protokoll>(`system/protokolle/${kennung}/`),
    enabled: !!kennung && fertig, retry: false,
  });
  const frueher = auftraege.filter((a) => a.aktion === "protokoll" && !a.offen && Date.now() - Date.parse(a.angefordert_am) < 3600_000).slice(0, 8);
  const zeilenListe = useMemo(() => {
    const alle = (text.data?.text ?? "").split("\n");
    if (!filter.trim()) return alle;
    const f = filter.trim().toLowerCase();
    return alle.filter((z) => z.toLowerCase().includes(f));
  }, [text.data, filter]);
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3 min-w-0" data-testid="protokolle">
      <KartenKopf titel="Protokolle" unter="Letzte Zeilen der Container, des Systemagenten, der Sicherung und des Updates – nur lesend. Ein Abruf liegt eine Stunde bereit und steht im Audit-Log." />
      <div className="flex gap-2.5 items-end flex-wrap">
        <Feld label="Protokoll">
          {(p) => <Auswahl {...p} value={quelle} onChange={(e) => setQuelle(e.target.value)}>
            {(quellen.length ? quellen : [{ quelle: "backend", name: "Container backend (Django)" }]).map((q) => <option key={q.quelle} value={q.quelle}>{q.name}</option>)}
          </Auswahl>}
        </Feld>
        <Feld label="Zeilen">
          {(p) => <Auswahl {...p} value={zeilen} onChange={(e) => setZeilen(e.target.value)}>
            {[100, 500, 2000].map((z) => <option key={z} value={z}>letzte {z}</option>)}</Auswahl>}
        </Feld>
        <Knopf variante="pri" icon="aktivitaet" laedt={abrufen.isPending || (!!auftrag && auftrag.offen)} disabled={!daten.agent.verzeichnis}
          onClick={() => abrufen.mutate()}>Abrufen</Knopf>
      </div>
      <Fehleranzeige fehler={abrufen.error} />
      {frueher.length ? (
        <div className="flex gap-1.5 flex-wrap text-xs items-center"><span className="gedaempft">Zuletzt abgerufen:</span>
          {frueher.map((a) => <button key={a.id} type="button" className={cx("chip cursor-pointer border-0", a.kennung === kennung && "akzent")}
            onClick={() => setKennung(a.kennung)}>{a.parameter.quelle} · {uhrzeit(a.angefordert_am)}</button>)}</div>
      ) : null}
      {kennung && !fertig ? <Meldung art="info"><span className="flex items-center gap-2"><Icon name="sanduhr" groesse={14} />Der Server liest das Protokoll …</span></Meldung> : null}
      {auftrag && fertig && auftrag.status !== "erledigt" ? <Meldung art="warn">{auftrag.ergebnis}</Meldung> : null}
      {text.error ? <Fehleranzeige fehler={text.error} /> : null}
      {text.data ? (
        <>
          <div className="flex gap-2.5 items-end flex-wrap">
            <Feld label="Filtern" className="grow">
              {(p) => <Eingabe {...p} value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="z. B. ERROR, 500, backup" />}
            </Feld>
            <a className="btn sec" href={`/api/system/protokolle/${kennung}/?herunterladen=1`} download data-testid="protokoll-herunterladen">
              <Icon name="herunterladen" />Herunterladen</a>
          </div>
          <span className="text-xs gedaempft">{text.data.name} · {zeilenListe.length} Zeilen{filter ? " (gefiltert)" : ""} · abgerufen {relativ(text.data.abgerufen_am, true)}</span>
          {zeilenListe.join("").trim() ? (
            <pre className="m-0 max-h-[32rem] overflow-auto text-[0.75rem] leading-snug bg-grund rounded-lg p-3 whitespace-pre-wrap break-all" data-testid="protokoll-text">
              {zeilenListe.join("\n")}</pre>
          ) : <Leer>Keine Zeilen{filter ? " mit diesem Filter" : ""}.</Leer>}
        </>
      ) : !kennung ? <span className="text-sm gedaempft">Protokoll wählen und „Abrufen“.</span> : text.isLoading ? <Laden /> : null}
    </Karte>
  );
}
