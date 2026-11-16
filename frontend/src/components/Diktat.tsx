/**
 * Diktate (Wunsch 23.10.2026): im Browser aufnehmen, auf dem Server offline abschreiben lassen (whisper.cpp im
 * OCR-Dienst), nachhören und in den Text übernehmen.
 *
 * - ``DiktatAufnahme``: Mikrofon-Knopf mit Zeit und Pegel, Pause, danach „sofort / heute Nacht“ und „selbst /
 *   Sekretariat“. Die Aufnahme geht direkt an den Server (WebM/Opus, ≈ 15 MB je Stunde); auf dem Gerät bleibt nichts.
 * - ``DiktatListe``: Diktate eines Berichts mit Stand, Abschrift (unsichere Wörter markiert), Nachhören (ein Klick
 *   auf ein Wort springt an die Stelle, das gesprochene Wort ist hervorgehoben) und „In den Text übernehmen“.
 * - ``KommentarDiktat``: kurzer Kommentar zum Infusionsplan – aufnehmen, abschreiben, direkt einfügen.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, uhrzeit } from "@/lib/format";
import { useDiktatStand } from "@/lib/diktate";
import type { Diktat, DiktatWort } from "@/lib/typen";
import { Chip, Fehleranzeige, Knopf, Meldung, Segmente, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { DiktatKi } from "@/components/DiktatKi";

const HOECHSTENS_S = 60 * 60;
/** ab dieser Länge ist „heute Nacht“ vorgewählt (der Server bleibt tagsüber frei) */
const LANG_AB_S = 10 * 60;
const UNSICHER_UNTER = 0.5;

export function dauerText(s: number) {
  const m = Math.floor(s / 60);
  const r = Math.floor(s % 60);
  return `${m}:${String(r).padStart(2, "0")}`;
}

function formatWaehlen(): string {
  const kandidaten = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4;codecs=mp4a.40.2", "audio/mp4"];
  if (typeof MediaRecorder === "undefined") return "";
  return kandidaten.find((k) => MediaRecorder.isTypeSupported?.(k)) ?? "";
}

/** Sperrt der Server das Mikrofon (Kopf „Permissions-Policy“ in nginx/epm.conf)? Nur Chrome/Edge können das melden. */
function serverSperrt(): boolean {
  const fp = (document as Document & { featurePolicy?: { allowsFeature(f: string): boolean } }).featurePolicy;
  return !!fp && !fp.allowsFeature("microphone");
}

const SERVER_GESPERRT = "Der EPM-Server sperrt das Mikrofon (Einstellung „Permissions-Policy“ im Nginx). Bitte die IT informieren.";
const SO_ERLAUBEN = "Das Mikrofon ist für EPM gesperrt. So freigeben: links neben der Adresse auf das Schloss-Symbol klicken → "
  + "„Mikrofon“ auf „Zulassen“ stellen → Seite neu laden.";

function mikrofonFehler(e: unknown): string {
  if (!window.isSecureContext) return "Das Mikrofon geht nur über die sichere Verbindung (https).";
  const name = e instanceof DOMException ? e.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") return serverSperrt() ? SERVER_GESPERRT : SO_ERLAUBEN;
  if (name === "NotFoundError") return "Kein Mikrofon gefunden. Bitte Headset anschließen.";
  return "Das Mikrofon ließ sich nicht starten.";
}

/**
 * Prüft vorab, ob das Mikrofon benutzt werden darf, und hört auf Änderungen (wird es in den Seiteneinstellungen
 * erlaubt, verschwindet der Hinweis von selbst). „frei“ heißt auch: der Browser fragt beim ersten Klick nach.
 */
function useMikrofonStatus(): string {
  const [gesperrt, setGesperrt] = useState("");
  useEffect(() => {
    if (!window.isSecureContext) { setGesperrt("Das Mikrofon geht nur über die sichere Verbindung (https)."); return; }
    if (serverSperrt()) { setGesperrt(SERVER_GESPERRT); return; }
    let status: PermissionStatus | null = null;
    let weg = false;
    const setzen = () => setGesperrt(status?.state === "denied" ? SO_ERLAUBEN : "");
    navigator.permissions?.query({ name: "microphone" as PermissionName })
      .then((s) => { if (weg) return; status = s; setzen(); s.addEventListener("change", setzen); })
      .catch(() => setGesperrt("")); // z. B. ältere Browser kennen die Abfrage nicht – dann fragt der Klick
    return () => { weg = true; status?.removeEventListener("change", setzen); };
  }, []);
  return gesperrt;
}

type Aufnahme = { blob: Blob; dauer: number; mime: string };

/** Aufnahme mit MediaRecorder: Zeit, Pegel (0–1), Pause; ``stoppen`` liefert die fertige Datei. */
function useAufnahme() {
  const [zustand, setZustand] = useState<"aus" | "laeuft" | "pause">("aus");
  const [sekunden, setSekunden] = useState(0);
  const [pegel, setPegel] = useState(0);
  const [fehler, setFehler] = useState("");
  const rec = useRef<MediaRecorder | null>(null);
  const teile = useRef<Blob[]>([]);
  const strom = useRef<MediaStream | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const takt = useRef<number>(0);
  const zeit = useRef({ seit: 0, vorher: 0 });
  const fertig = useRef<((a: Aufnahme | null) => void) | null>(null);

  const aufraeumen = useCallback(() => {
    window.clearInterval(takt.current);
    strom.current?.getTracks().forEach((t) => t.stop());
    strom.current = null;
    void ctx.current?.close().catch(() => undefined);
    ctx.current = null;
    setPegel(0);
  }, []);
  useEffect(() => () => { rec.current?.state !== "inactive" && rec.current?.stop(); aufraeumen(); }, [aufraeumen]);

  const vergangen = () => zeit.current.vorher + (zeit.current.seit ? (Date.now() - zeit.current.seit) / 1000 : 0);

  const starten = async () => {
    setFehler("");
    let s: MediaStream;
    try {
      s = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      setFehler(mikrofonFehler(e));
      return;
    }
    const mime = formatWaehlen();
    let r: MediaRecorder;
    try {
      r = new MediaRecorder(s, { ...(mime ? { mimeType: mime } : {}), audioBitsPerSecond: 32000 });
    } catch {
      s.getTracks().forEach((t) => t.stop());
      setFehler("Dieser Browser kann nicht aufnehmen. Bitte einen aktuellen Browser verwenden.");
      return;
    }
    strom.current = s;
    teile.current = [];
    r.ondataavailable = (ev) => { if (ev.data.size) teile.current.push(ev.data); };
    r.onstop = () => {
      const typ = r.mimeType || mime || "audio/webm";
      const dauer = vergangen();
      aufraeumen();
      setZustand("aus");
      const blob = new Blob(teile.current, { type: typ });
      fertig.current?.(blob.size ? { blob, dauer, mime: typ } : null);
      fertig.current = null;
    };
    // Pegel: zeigt, dass das Mikrofon etwas hört
    try {
      const ac = new AudioContext();
      const analyse = ac.createAnalyser();
      analyse.fftSize = 512;
      ac.createMediaStreamSource(s).connect(analyse);
      ctx.current = ac;
      const puffer = new Uint8Array(analyse.fftSize);
      takt.current = window.setInterval(() => {
        analyse.getByteTimeDomainData(puffer);
        let summe = 0;
        for (const v of puffer) summe += ((v - 128) / 128) ** 2;
        setPegel(Math.min(1, Math.sqrt(summe / puffer.length) * 4));
        const t = vergangen();
        setSekunden(t);
        if (t >= HOECHSTENS_S && r.state === "recording") r.stop();
      }, 200);
    } catch { /* ohne Pegel weiter */ }
    rec.current = r;
    zeit.current = { seit: Date.now(), vorher: 0 };
    setSekunden(0);
    r.start(1000);
    setZustand("laeuft");
  };

  const pausieren = () => {
    if (rec.current?.state !== "recording") return;
    rec.current.pause();
    zeit.current = { vorher: vergangen(), seit: 0 };
    setZustand("pause");
  };
  const fortsetzen = () => {
    if (rec.current?.state !== "paused") return;
    rec.current.resume();
    zeit.current = { ...zeit.current, seit: Date.now() };
    setZustand("laeuft");
  };
  const stoppen = () => new Promise<Aufnahme | null>((ok) => {
    if (!rec.current || rec.current.state === "inactive") { ok(null); return; }
    fertig.current = ok;
    rec.current.stop();
  });
  return { zustand, sekunden, pegel, fehler, starten, pausieren, fortsetzen, stoppen };
}

/** Solange aufgenommen wird oder eine Aufnahme nicht hochgeladen ist: Rückfrage beim Verlassen der Seite */
function useVerlassenWarnen(aktiv: boolean) {
  useEffect(() => {
    if (!aktiv) return;
    const warnen = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", warnen);
    return () => window.removeEventListener("beforeunload", warnen);
  }, [aktiv]);
}

function Pegel({ wert }: { wert: number }) {
  return (
    <span className="inline-flex h-2 w-24 rounded-full bg-fein overflow-hidden" aria-hidden="true">
      <span className="h-full bg-akzent transition-[width] duration-150" style={{ width: `${Math.round(wert * 100)}%` }} />
    </span>
  );
}

export function BegriffeDialog({ offen, onOffen }: { offen: boolean; onOffen: (o: boolean) => void }) {
  const melden = useHinweis();
  const qc = useQueryClient();
  const daten = useQuery({ queryKey: ["diktate", "begriffe"], queryFn: () => api<{ begriffe: string }>("diktate/begriffe/"), enabled: offen });
  const [text, setText] = useState<string | null>(null);
  const wert = text ?? daten.data?.begriffe ?? "";
  const speichern = useMutation({
    mutationFn: () => api<{ begriffe: string }>("diktate/begriffe/", { method: "PUT", body: { begriffe: wert } }),
    onSuccess: (d) => { qc.setQueryData(["diktate", "begriffe"], d); setText(null); melden("Fachbegriffe gespeichert."); onOffen(false); },
  });
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) setText(null); onOffen(o); }} titel="Eigene Fachbegriffe"
      beschreibung="Namen, Präparate und Abkürzungen, die beim Abschreiben richtig geschrieben werden sollen – einer je Zeile. Diagnosen der Akte und Präparate kennt die Abschrift schon."
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <Textfeld aria-label="Fachbegriffe" rows={8} value={wert} maxLength={5000} onChange={(e) => setText(e.target.value)}
        placeholder={"Teduglutid\nSMOFKabiven\nPort-Katheter"} />
      <Fehleranzeige fehler={speichern.error} />
    </Dialog>
  );
}

/**
 * Aufnahme für einen Bericht oder einen Kommentar. ``vorHochladen`` legt bei einem neuen Bericht erst den Entwurf an
 * und gibt seine Nummer zurück.
 */
export function DiktatAufnahme({ patientId, zweck = "bericht", berichtId, vorHochladen, onHochgeladen, kompakt, onAktiv }: {
  /** null: ohne Patient aufnehmen und danach unter „Diktate“ zuordnen (27.10.2026) */
  patientId: number | null;
  zweck?: "bericht" | "plan";
  berichtId?: number | null;
  vorHochladen?: () => Promise<number>;
  onHochgeladen?: (d: Diktat) => void;
  /** nur Knopf und Zeit (Kommentar): sofort abschreiben, selbst fertig machen */
  kompakt?: boolean;
  /** Aufnahme läuft oder ist noch nicht gesendet – z. B. damit der Dialog vor dem Schließen nachfragt */
  onAktiv?: (aktiv: boolean) => void;
}) {
  const a = useAufnahme();
  const gesperrt = useMikrofonStatus();
  const stand = useDiktatStand();
  const qc = useQueryClient();
  const [aufnahme, setAufnahme] = useState<Aufnahme | null>(null);
  const [wann, setWann] = useState<"sofort" | "nachts">("sofort");
  const [uebergabe, setUebergabe] = useState<"selbst" | "sekretariat">("selbst");
  const [begriffe, setBegriffe] = useState(false);
  const aktiv = a.zustand !== "aus" || !!aufnahme;
  useVerlassenWarnen(aktiv);
  useEffect(() => { onAktiv?.(aktiv); }, [aktiv, onAktiv]);

  const hochladen = useMutation({
    mutationFn: async (x: Aufnahme) => {
      const bericht = zweck === "bericht" && patientId != null ? berichtId ?? (vorHochladen ? await vorHochladen() : null) : null;
      const form = new FormData();
      if (patientId != null) form.append("patient", String(patientId));
      if (bericht) form.append("bericht", String(bericht));
      form.append("zweck", zweck);
      form.append("wann", kompakt ? "sofort" : wann);
      form.append("uebergabe", kompakt ? "selbst" : uebergabe);
      form.append("dauer_s", x.dauer.toFixed(1));
      const endung = x.mime.includes("mp4") ? "m4a" : x.mime.includes("ogg") ? "ogg" : "webm";
      form.append("datei", new File([x.blob], `diktat.${endung}`, { type: x.mime.split(";")[0] }));
      return api<Diktat>("diktate/", { form });
    },
    onSuccess: (d) => {
      setAufnahme(null);
      // sofort in die Liste des Berichts (eine Abfrage, die während des Hochladens lief, kennt es noch nicht)
      if (d.bericht) qc.setQueryData<Diktat[]>(["diktate", "bericht", d.bericht], (alt) => [d, ...(alt ?? []).filter((x) => x.id !== d.id)]);
      void qc.invalidateQueries({ queryKey: ["diktate", "stand"] });
      onHochgeladen?.(d);
    },
  });

  const fertig = async () => {
    const x = await a.stoppen();
    if (!x) return;
    if (kompakt) { hochladen.mutate(x); return; }
    setWann(x.dauer >= LANG_AB_S ? "nachts" : "sofort");
    setAufnahme(x);
  };

  const ohneDienst = stand.data && !stand.data.bereit;
  if (a.zustand === "aus" && !aufnahme) {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <Knopf klein={kompakt} icon="mikrofon" laedt={hochladen.isPending} onClick={() => void a.starten()} data-testid="diktat-start">
            {hochladen.isPending ? "Wird hochgeladen …" : kompakt ? "Diktieren" : "Diktat aufnehmen"}
          </Knopf>
          {!kompakt ? <Knopf klein variante="geist" onClick={() => setBegriffe(true)}>Fachbegriffe</Knopf> : null}
        </div>
        {ohneDienst ? (kompakt
          ? <span className="text-[0.75rem] text-warn" title={stand.data?.grund}>Abschrift gerade nicht bereit – das Diktat wartet.</span>
          : <span className="text-[0.75rem] text-warn">Die Abschrift ist auf dem Server gerade nicht bereit – das Diktat
            wartet, bis sie es ist.{stand.data?.grund ? ` ${stand.data.grund}` : ""}</span>) : null}
        {a.fehler || gesperrt ? (
          <Meldung art="fehler">
            <span data-testid="diktat-mikrofon-gesperrt">{a.fehler || gesperrt}</span>{" "}
            <Knopf klein variante="geist" onClick={() => window.location.reload()}>Seite neu laden</Knopf>
          </Meldung>
        ) : null}
        <Fehleranzeige fehler={hochladen.error} />
        {!kompakt ? <BegriffeDialog offen={begriffe} onOffen={setBegriffe} /> : null}
      </div>
    );
  }

  if (a.zustand !== "aus") {
    return (
      <div className={cx("rounded-lg border border-rand bg-grund flex items-center gap-3 flex-wrap", kompakt ? "px-2.5 py-1.5" : "px-3.5 py-3")}
        role="status" aria-live="polite" data-testid="diktat-laeuft">
        <span className={cx("inline-flex items-center gap-1.5 font-medium text-sm", a.zustand === "laeuft" ? "text-fehler" : "gedaempft")}>
          <span className={cx("inline-block w-2.5 h-2.5 rounded-full", a.zustand === "laeuft" ? "bg-fehler animate-pulse" : "bg-gedaempft")} />
          {a.zustand === "laeuft" ? "Aufnahme" : "Pause"}
        </span>
        <span className="num text-sm">{dauerText(a.sekunden)}</span>
        <Pegel wert={a.pegel} />
        <span className="flex gap-2 ml-auto">
          {a.zustand === "laeuft"
            ? <Knopf klein icon="pause" onClick={a.pausieren}>Pause</Knopf>
            : <Knopf klein icon="mikrofon" onClick={a.fortsetzen}>Weiter</Knopf>}
          <Knopf klein variante="pri" icon="stopp" onClick={() => void fertig()} data-testid="diktat-stopp">Fertig</Knopf>
        </span>
      </div>
    );
  }

  // Aufnahme fertig: wann abschreiben, wer macht fertig
  return (
    <div className="rounded-lg border border-rand bg-grund px-3.5 py-3 flex flex-col gap-3" data-testid="diktat-senden">
      <span className="text-sm"><span className="font-medium">Aufnahme {dauerText(aufnahme!.dauer)}</span>
        <span className="gedaempft"> · {aufnahme!.blob.size < 1024 * 1024 ? `${Math.max(1, Math.round(aufnahme!.blob.size / 1024))} KB`
          : `${(aufnahme!.blob.size / 1024 / 1024).toFixed(1)} MB`}</span></span>
      <div className="flex gap-x-5 gap-y-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <span className="text-[0.75rem] gedaempft">Abschreiben</span>
          <Segmente label="Wann abschreiben" wert={wann} onWahl={setWann}
            werte={[{ wert: "sofort", text: "sofort" }, { wert: "nachts", text: "heute Nacht" }]} />
        </div>
        {zweck === "bericht" ? (
          <div className="flex flex-col gap-1">
            <span className="text-[0.75rem] gedaempft">Fertig machen</span>
            <Segmente label="Wer macht den Text fertig" wert={uebergabe} onWahl={setUebergabe}
              werte={[{ wert: "selbst", text: "ich selbst" }, { wert: "sekretariat", text: "Sekretariat" }]} />
          </div>
        ) : null}
      </div>
      <div className="flex gap-2 flex-wrap">
        <Knopf variante="pri" icon="hochladen" laedt={hochladen.isPending} onClick={() => hochladen.mutate(aufnahme!)} data-testid="diktat-senden-knopf">
          Zum Abschreiben senden
        </Knopf>
        <Knopf variante="dng" onClick={() => { if (window.confirm("Aufnahme verwerfen?")) { hochladen.reset(); setAufnahme(null); } }}>Verwerfen</Knopf>
      </div>
      {hochladen.error ? <Meldung art="fehler">{hochladen.error.message} Die Aufnahme bleibt hier, bis sie gesendet ist.</Meldung> : null}
    </div>
  );
}

/** Abschrift zum Nachhören: Klick auf ein Wort springt hin, das gesprochene Wort ist hervorgehoben, unsichere markiert */
export function Abschrift({ diktat }: { diktat: Diktat }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [url, setUrl] = useState("");
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState("");
  const [jetzt, setJetzt] = useState(-1);
  const [spielt, setSpielt] = useState(false);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  const woerter: DiktatWort[] = diktat.woerter ?? [];

  const laden = async () => {
    if (url) return url;
    setLaedt(true);
    setFehler("");
    try {
      const blob = await api<Blob>(`diktate/${diktat.id}/audio/`, { alsBlob: true });
      const neu = URL.createObjectURL(blob);
      setUrl(neu);
      return neu;
    } catch (e) {
      setFehler(e instanceof Error ? e.message : "Die Aufnahme ließ sich nicht laden.");
      return "";
    } finally {
      setLaedt(false);
    }
  };
  const abspielen = async (ab?: number) => {
    const quelle = await laden();
    const el = audio.current;
    if (!quelle || !el) return;
    if (el.src !== quelle) el.src = quelle;
    if (ab !== undefined) el.currentTime = ab / 1000;
    await el.play().catch(() => undefined);
  };
  const zeit = () => {
    const ms = (audio.current?.currentTime ?? 0) * 1000;
    let i = -1;
    for (let k = 0; k < woerter.length; k++) { if (woerter[k][1] <= ms) i = k; else break; }
    setJetzt(i);
  };

  return (
    <div className="flex flex-col gap-2">
      <audio ref={audio} onTimeUpdate={zeit} onPlay={() => setSpielt(true)} onPause={() => setSpielt(false)} onEnded={() => { setSpielt(false); setJetzt(-1); }} preload="none" />
      {diktat.audio ? (
        <div className="flex items-center gap-2 flex-wrap">
          {spielt
            ? <Knopf klein icon="pause" onClick={() => audio.current?.pause()}>Anhalten</Knopf>
            : <Knopf klein icon="abspielen" laedt={laedt} onClick={() => void abspielen()}>Anhören</Knopf>}
          <span className="text-[0.75rem] gedaempft">Ein Klick auf ein Wort spielt ab dieser Stelle.</span>
        </div>
      ) : null}
      {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
      <p className="m-0 leading-relaxed text-sm" data-testid="diktat-abschrift">
        {woerter.map((w, i) => {
          const unsicher = w[3] < UNSICHER_UNTER;
          return (
            <span key={i}>
              {w[0].startsWith(" ") ? " " : ""}
              <span role={diktat.audio ? "button" : undefined} tabIndex={diktat.audio ? 0 : undefined}
                title={unsicher ? "unsicher erkannt – bitte nachhören" : undefined}
                onClick={diktat.audio ? () => void abspielen(w[1]) : undefined}
                onKeyDown={diktat.audio ? (e) => { if (e.key === "Enter") void abspielen(w[1]); } : undefined}
                className={cx("rounded-sm", diktat.audio && "cursor-pointer", unsicher && "bg-warn-bg text-warn underline decoration-dotted",
                  i === jetzt && "bg-akzent-weich text-akzent-text")}>
                {w[0].trimStart()}
              </span>
            </span>
          );
        })}
      </p>
    </div>
  );
}

export function statusArt(d: Diktat): "warn" | "fehler" | "ok" | "neutral" {
  if (d.status === "fehler") return "fehler";
  if (d.status === "fertig") return d.uebernommen_am ? "ok" : "warn";
  return "neutral";
}

function DiktatEintrag({ d, onUebernehmen }: { d: Diktat; onUebernehmen?: (html: string) => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const { darf } = useAuth();
  const [offen, setOffen] = useState(!d.uebernommen_am);
  const neu = () => void qc.invalidateQueries({ queryKey: ["diktate"] });
  // html: die Abschrift selbst oder der gegliederte Entwurf der KI (DiktatKi)
  const uebernehmen = useMutation({
    mutationFn: (_html: string) => api<Diktat>(`diktate/${d.id}/uebernommen/`, { body: {} }),
    onSuccess: (_d, html) => { onUebernehmen?.(html); neu(); melden("Diktat in den Text übernommen – bitte prüfen und speichern."); },
  });
  const erneut = useMutation({ mutationFn: () => api<Diktat>(`diktate/${d.id}/erneut/`, { body: {} }), onSuccess: neu });
  const verwerfen = useMutation({ mutationFn: () => api(`diktate/${d.id}/`, { method: "DELETE" }), onSuccess: () => { neu(); melden("Diktat verworfen."); } });
  const darfAendern = darf("eintraege_erfassen");
  const laufend = d.status === "wartet" || d.status === "laeuft";

  return (
    <li className="rounded-lg border border-rand bg-flaeche px-3 py-2.5 flex flex-col gap-2" data-testid="diktat-eintrag">
      <div className="flex items-center gap-2 flex-wrap text-sm">
        <Icon name="mikrofon" />
        <span className="font-medium num">{dauerText(d.dauer_s)}</span>
        <span className="gedaempft">{[d.erstellt_von_name, `${datum(d.erstellt_am)} ${uhrzeit(d.erstellt_am)}`,
          d.uebergabe === "sekretariat" ? "ans Sekretariat" : ""].filter(Boolean).join(" · ")}</span>
        <Chip art={statusArt(d)} data-testid="diktat-status">
          {laufend && d.wann === "nachts" && d.status === "wartet" ? "wartet auf die Nacht"
            : d.status === "fertig" && d.uebernommen_am ? "übernommen" : d.status_name}
        </Chip>
        {d.status === "fertig" && d.unsicher ? <Chip art="warn">{d.unsicher} unsicher</Chip> : null}
        {d.status === "fertig" ? (
          <Knopf klein variante="geist" className="ml-auto" onClick={() => setOffen(!offen)} aria-expanded={offen}>
            {offen ? "Zuklappen" : "Abschrift"}
          </Knopf>
        ) : null}
      </div>
      {laufend ? <span className="text-[0.8125rem] gedaempft">{d.schritt || (d.wann === "nachts"
        ? "Wird heute Nacht abgeschrieben." : "Wartet auf die Abschrift – meist nach wenigen Minuten fertig.")}</span> : null}
      {d.status === "fehler" ? <Meldung art="fehler">{d.fehler}</Meldung> : null}
      {d.status === "fertig" && offen ? <Abschrift diktat={d} /> : null}
      {d.status === "fertig" && onUebernehmen && darfAendern && darf("ki_berichte")
        ? <DiktatKi diktatId={d.id} uebernimmt={uebernehmen.isPending} onUebernehmen={(html) => uebernehmen.mutate(html)} /> : null}
      {darfAendern ? (
        <div className="flex gap-2 flex-wrap">
          {d.status === "fertig" && onUebernehmen ? (
            <Knopf klein variante={d.uebernommen_am ? "sec" : "pri"} icon="plus" laedt={uebernehmen.isPending}
              onClick={() => uebernehmen.mutate(d.text ?? "")} data-testid="diktat-uebernehmen">
              {d.uebernommen_am ? "Noch einmal übernehmen" : "In den Text übernehmen"}
            </Knopf>
          ) : null}
          {d.status === "fehler" && d.audio ? <Knopf klein icon="neustart" laedt={erneut.isPending} onClick={() => erneut.mutate()}>Erneut abschreiben</Knopf> : null}
          <Knopf klein variante="dng" laedt={verwerfen.isPending}
            onClick={() => { if (window.confirm("Diktat mit Aufnahme und Abschrift verwerfen?")) verwerfen.mutate(); }}>Verwerfen</Knopf>
        </div>
      ) : null}
      <Fehleranzeige fehler={uebernehmen.error ?? erneut.error ?? verwerfen.error} />
    </li>
  );
}

/** Diktate eines Berichts; aktualisiert sich alle 5 Sekunden, solange eins abgeschrieben wird. */
export function useDiktate(berichtId: number | null | undefined) {
  return useQuery({
    queryKey: ["diktate", "bericht", berichtId],
    queryFn: () => api<Diktat[]>(`diktate/?bericht=${berichtId}`),
    enabled: !!berichtId,
    refetchInterval: (q) => (q.state.data ?? []).some((d) => d.status === "wartet" || d.status === "laeuft") ? 5000 : false,
  });
}

export function DiktatListe({ berichtId, onUebernehmen, hinweis }: {
  berichtId: number | null | undefined;
  /** fehlt außerhalb des Bearbeitens (Ansicht): dann nur Stand und Abschrift */
  onUebernehmen?: (html: string) => void;
  hinweis?: string;
}) {
  const diktate = useDiktate(berichtId);
  const liste = diktate.data ?? [];
  if (!liste.length) return null;
  return (
    <div className="flex flex-col gap-2" data-testid="diktate">
      <span className="text-sm font-medium">{liste.length === 1 ? "Diktat" : `Diktate (${liste.length})`}</span>
      <ul className="m-0 p-0 list-none flex flex-col gap-2">
        {liste.map((d) => <DiktatEintrag key={d.id} d={d} onUebernehmen={onUebernehmen} />)}
      </ul>
      {hinweis ? <span className="text-[0.75rem] gedaempft">{hinweis}</span> : null}
    </div>
  );
}

/** Kommentar zum Infusionsplan diktieren: nach der Abschrift kommt der Text von selbst ans Ende des Kommentars. */
export function KommentarDiktat({ patientId, onText }: { patientId: number; onText: (html: string) => void }) {
  const { darf } = useAuth();
  const qc = useQueryClient();
  const [id, setId] = useState<number | null>(null);
  const diktat = useQuery({
    queryKey: ["diktate", "kommentar", id],
    queryFn: () => api<Diktat>(`diktate/${id}/`),
    enabled: !!id,
    refetchInterval: (q) => q.state.data && q.state.data.status !== "wartet" && q.state.data.status !== "laeuft" ? false : 3000,
  });
  const uebernehmen = useMutation({
    mutationFn: (d: Diktat) => api<Diktat>(`diktate/${d.id}/uebernommen/`, { body: {} }),
    onSuccess: () => { setId(null); void qc.invalidateQueries({ queryKey: ["diktate"] }); },
  });
  const d = diktat.data;
  const { mutate } = uebernehmen;
  const erledigt = useRef(new Set<number>());
  useEffect(() => {
    if (d?.status === "fertig" && !d.uebernommen_am && !erledigt.current.has(d.id)) {
      erledigt.current.add(d.id);  // genau einmal einfügen
      onText(d.text ?? "");
      mutate(d);
    }
  }, [d, mutate, onText]);
  if (!darf("diktieren")) return null;
  if (id && d?.status !== "fehler") {
    return <span className="text-[0.8125rem] gedaempft inline-flex items-center gap-1.5" role="status" data-testid="kommentar-diktat-laeuft">
      <Icon name="sanduhr" /> {d?.schritt || "Wird abgeschrieben …"}</span>;
  }
  return (
    <div className="flex flex-col gap-1">
      <DiktatAufnahme patientId={patientId} zweck="plan" kompakt onHochgeladen={(x) => setId(x.id)} />
      {d?.status === "fehler" ? <Meldung art="fehler">{d.fehler}</Meldung> : null}
    </div>
  );
}
