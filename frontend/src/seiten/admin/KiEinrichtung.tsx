/**
 * Administration › KI › Einrichtung (Wunsch 15.10.2026: „alles aus der Oberfläche steuern, auch welches Modell“).
 *
 * Modell aus der Liste wählen und laden (Test-VM) bzw. als Paket hochladen (Server ohne Internet), KI einrichten und
 * starten, Grenzen der Auslastung, Benchmark, Modelldateien löschen, KI ausschalten. Ausgeführt vom Systemagenten auf
 * dem Server – mit Passwort und zweitem Faktor für alles, was den Server verändert. Welches Modell aktiv ist, wird im
 * Reiter „Modelle“ gewechselt (mit Evaluation und Zurückschalten).
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { dateigroesse, zeitpunkt } from "@/lib/format";
import { Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";

type Variante = {
  schluessel: string; name: string; repo: string; quant: string; groesse_gb: number; ki_speicher: string; server_ram_gb: number;
  tempo: string; beschreibung: string; passt: boolean; empfohlen?: boolean; eingespielt: boolean;
};
type Auftrag = { id: number; aktion: string; name: string; status: string; status_name: string; offen: boolean;
  angefordert_am: string; beendet_am: string | null; ergebnis: string; ausgabe: string; angefordert_von_name: string };
type Upload = { upload: string; name: string; groesse: number; erhalten: number; vollstaendig: boolean };
type Einrichtung = {
  agent: { aktuell: boolean; alter_s: number | null };
  server: { eingerichtet?: boolean; werkzeug?: boolean; download_erlaubt?: boolean; modelle?: { datei: string; groesse: number }[];
    varianten?: { name: string; datei: string; projektor: string; quant: string }[]; aktiv_datei?: string; image_tag?: string;
    grenzen?: Record<string, string>; avx2?: boolean; fehler?: string };
  hardware: { ram: number | null; ram_frei: number | null; kerne: number | null; avx2?: boolean };
  katalog: Variante[]; auftraege: Auftrag[]; uploads: Upload[]; upload_max: number;
};
type Benchmark = { datei: string; zeit: string; varianten: { variante: string; laden_s: number | null; ram_max_gb: number | null;
  cpu_mittel: number | null; je_kategorie: Record<string, { sekunden_je_seite: number | null; cer: number | null; laborwerte_f1: number | null }> }[] };

const TEIL = 4 * 1024 * 1024;
const warten = (ms: number) => new Promise((r) => window.setTimeout(r, ms));
const GB = 1024 ** 3;

/** Bestätigung mit Passwort und zweitem Faktor (für Aufträge mit „2fa“) */
function Bestaetigung({ titel, text, onZu, onLos, laedt, fehler }: { titel: string; text: string; onZu: () => void;
  onLos: (kennwort: string, code: string) => void; laedt: boolean; fehler: unknown }) {
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  const f = fehler instanceof ApiFehler ? fehler.felder : {};
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel={titel} beschreibung={text}
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={laedt} disabled={!kennwort || !code} onClick={() => onLos(kennwort, code)}>Bestätigen</Knopf></>}>
      <Feld label="Ihr Passwort" fehler={f.kennwort}>{(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}</Feld>
      <Feld label="Code aus der Authenticator-App" fehler={f.code}>{(p) => <Eingabe {...p} inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}</Feld>
      {!f.kennwort && !f.code ? <Fehleranzeige fehler={fehler} /> : null}
    </Dialog>
  );
}

type Vorhaben = { titel: string; text: string; pfad: string; body: Record<string, unknown> };

export function KiEinrichtung() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const q = useQuery({
    queryKey: ["ki", "einrichtung"], queryFn: () => api<Einrichtung>("ki/einrichtung/", { hintergrund: true }),
    refetchInterval: (a) => ((a.state.data?.auftraege ?? []).some((x) => x.offen) ? 5000 : 30_000),
  });
  const bench = useQuery({ queryKey: ["ki", "benchmarks"], queryFn: () => api<Benchmark[]>("ki/benchmarks/") });
  const [vorhaben, setVorhaben] = useState<Vorhaben | null>(null);
  const auftrag = useMutation({
    mutationFn: ({ v, kennwort, code }: { v: Vorhaben; kennwort?: string; code?: string }) =>
      api(v.pfad, { body: { ...v.body, kennwort, code } }),
    onSuccess: () => { setVorhaben(null); void qc.invalidateQueries({ queryKey: ["ki"] }); melden("Auftrag an den Server übergeben – Fortschritt unten unter „Aufträge“."); },
  });
  const d = q.data;
  if (!d) return q.isLoading ? <Laden /> : <Fehleranzeige fehler={q.error} />;
  const s = d.server;
  const offen = d.auftraege.some((a) => a.offen);
  const ramGb = d.hardware.ram ? d.hardware.ram / GB : 0;
  const mit2fa = (v: Vorhaben) => { auftrag.reset(); setVorhaben(v); };
  const einfach = (body: Record<string, unknown>, frage: string) => { if (window.confirm(frage)) auftrag.mutate({ v: { titel: "", text: "", pfad: "ki/einrichtung/", body } }); };

  const schritte: { text: string; ok: boolean | undefined; info: string }[] = [
    { text: "Systemagent erreichbar", ok: d.agent.aktuell, info: d.agent.aktuell ? "meldet sich jede Minute" : "meldet sich nicht – Administration › System prüfen" },
    { text: "Server groß genug", ok: ramGb >= 11.5 && (d.hardware.kerne ?? 0) >= 4,
      info: `${ramGb ? ramGb.toFixed(1) : "?"} GB RAM, ${d.hardware.kerne ?? "?"} Kerne (nötig: 12 GB, 4 Kerne)` },
    { text: "CPU mit AVX2", ok: d.hardware.avx2, info: d.hardware.avx2 ? "ja" : "nein – im Hypervisor den CPU-Typ „host“ wählen" },
    { text: "Werkzeug epm-ki auf dem Server", ok: s.werkzeug, info: s.werkzeug ? "vorhanden" : "kommt mit „EPM aktualisieren“" },
    { text: "Modell auf dem Server", ok: (s.modelle ?? []).length > 0, info: `${(s.modelle ?? []).length} Datei(en)` },
    { text: "KI eingerichtet", ok: s.eingerichtet, info: s.eingerichtet ? "Container laufen mit (compose.ki.yaml)" : "noch nicht – „KI einrichten“" },
  ];
  return (
    <div className="flex flex-col gap-4" data-testid="ki-einrichtung">
      {s.fehler ? <Meldung art="warn">Stand vom Server unvollständig: {s.fehler}</Meldung> : null}
      <Karte className="flex flex-col gap-3">
        <KartenKopf titel="Stand der Einrichtung" unter="Ausgeführt vom Systemagenten auf dem Server – ohne SSH"
          rechts={<>
            <Knopf variante="pri" disabled={offen || !s.werkzeug || !(s.modelle ?? []).length} onClick={() => mit2fa({ titel: s.eingerichtet ? "KI neu einrichten und starten" : "KI einrichten und starten",
              text: "Secrets und Ordner anlegen, Grenzen nach Hardware setzen (eigene Werte bleiben), Container starten, Modelle registrieren. Dauert einige Minuten.",
              pfad: "ki/einrichtung/", body: { aktion: "einrichten" } })}>{s.eingerichtet ? "Neu einrichten" : "KI einrichten und starten"}</Knopf>
            {s.eingerichtet ? <Knopf variante="dng" disabled={offen} onClick={() => mit2fa({ titel: "KI ausschalten",
              text: "Die KI-Container werden gestoppt und aus der Konfiguration genommen. Prüf-Queue, Hinweise, Modelle und Einstellungen bleiben.",
              pfad: "ki/einrichtung/", body: { aktion: "aus" } })}>Ausschalten</Knopf> : null}
          </>} />
        <ul className="m-0 p-0 list-none grid gap-1.5 sm:grid-cols-2 text-sm">
          {schritte.map((x) => (
            <li key={x.text} className="flex items-start gap-2">
              <span className={x.ok ? "text-ok" : "text-warn"}><Icon name={x.ok ? "haken" : "warnung"} /></span>
              <span><strong className="font-medium">{x.text}</strong><span className="gedaempft"> – {x.info}</span></span>
            </li>))}
        </ul>
      </Karte>

      <Karte className="flex flex-col gap-3 overflow-x-auto">
        <KartenKopf titel="Modell auswählen" unter="Schätzungen für CPU-Betrieb – was wirklich passt, zeigt der Benchmark. Aktiv geschaltet wird im Reiter „Modelle“." />
        <table className="tabelle text-sm" data-testid="ki-katalog">
          <thead><tr><th className="th">Modell</th><th className="th">Größe</th><th className="th">Speicher KI</th><th className="th">Server ab</th>
            <th className="th">Tempo</th><th className="th" /></tr></thead>
          <tbody>{d.katalog.map((k) => (
            <tr key={k.schluessel}>
              <td className="td"><div className="font-medium flex items-center gap-1.5 flex-wrap">{k.name}
                {k.empfohlen ? <Chip art="ok">Empfehlung</Chip> : null}
                {k.eingespielt ? <Chip art="akzent">auf dem Server</Chip> : null}
                {!k.passt ? <Chip art="warn">zu groß für diesen Server</Chip> : null}</div>
                <div className="text-[0.75rem] gedaempft">{k.beschreibung}</div></td>
              <td className="td num whitespace-nowrap">{k.groesse_gb.toLocaleString("de-DE")} GB</td>
              <td className="td num">{k.ki_speicher}</td>
              <td className="td num whitespace-nowrap">{k.server_ram_gb} GB RAM</td>
              <td className="td">{k.tempo}</td>
              <td className="td whitespace-nowrap">
                {s.download_erlaubt ? (
                  <Knopf klein disabled={offen || k.eingespielt} onClick={() => mit2fa({ titel: `${k.name} laden`,
                    text: `Der Server lädt ${k.repo} (${k.quant}) mit dem Vision-Projektor, prüft die Prüfsummen und spielt es ein (${k.groesse_gb} GB, je nach Leitung 5–30 Minuten). Geladen wird vom Systemagenten – die KI-Container selbst bleiben ohne Internet. Lizenz bitte an der Modellkarte prüfen.`,
                    pfad: "ki/einrichtung/", body: { aktion: "laden", variante: k.schluessel } })}>Auf den Server laden</Knopf>
                ) : <span className="text-[0.75rem] gedaempft">als Paket hochladen</span>}
              </td>
            </tr>))}</tbody>
        </table>
        {!s.download_erlaubt ? (
          <Meldung className="text-[0.8125rem]">Dieser Server lädt nichts aus dem Internet. Auf einem PC mit Internet vorbereiten, z. B.
            <code className="mx-1">werkzeuge/ki.sh vorbereiten Q4_K_M --repo bartowski/Qwen_Qwen3.5-4B-GGUF --mit-image</code>
            (Windows: in WSL), und die Datei unten hochladen.</Meldung>) : null}
        <Hochladen max={d.upload_max} uploads={d.uploads} offen={offen}
          onEinspielen={(u) => mit2fa({ titel: `${u.name} einspielen`, text: "Der Server prüft Inhalt und Prüfsummen und legt die Modelle ab (bei eingerichteter KI werden neue Varianten gleich registriert).",
            pfad: `ki/hochladen/${u.upload}/einspielen/`, body: {} })} />
      </Karte>

      <Karte className="flex flex-col gap-3">
        <KartenKopf titel="Modelldateien auf dem Server" unter={s.image_tag ? `Image ki-modell: ${s.image_tag}` : "Image ki-modell: noch keins"} />
        {(s.modelle ?? []).length ? (
          <ul className="m-0 p-0 list-none flex flex-col divide-y divide-rand text-sm">
            {(s.modelle ?? []).map((m) => {
              const projektor = (s.varianten ?? []).some((v) => v.projektor === m.datei);
              const aktiv = m.datei === s.aktiv_datei;
              return (
                <li key={m.datei} className="py-2 flex items-center gap-2.5 flex-wrap">
                  <span className="font-mono text-[0.8125rem] break-all">{m.datei}</span>
                  <span className="gedaempft">{dateigroesse(m.groesse)}</span>
                  {aktiv ? <Chip art="ok">aktiv</Chip> : null}
                  {projektor ? <Chip>Vision-Projektor</Chip> : null}
                  <span className="flex-1" />
                  {!aktiv && !projektor ? <Knopf klein variante="geist" disabled={offen} onClick={() => mit2fa({ titel: `${m.datei} löschen`,
                    text: "Die Datei wird auf dem Server gelöscht; der Eintrag in der Modell-Liste wird gesperrt. Das aktive Modell lässt sich nicht löschen.",
                    pfad: "ki/einrichtung/", body: { aktion: "loeschen", datei: m.datei } })}>Löschen</Knopf> : null}
                </li>);
            })}
          </ul>) : <Leer>Noch keine Modelle auf dem Server.</Leer>}
      </Karte>

      <Grenzen werte={s.grenzen ?? {}} offen={offen} kerne={d.hardware.kerne} onSpeichern={(w) => einfach({ aktion: "grenzen", ...w },
        "Grenzen speichern? Laufende KI-Container starten dafür neu.")} />

      <Karte className="flex flex-col gap-3 overflow-x-auto">
        <KartenKopf titel="Benchmark" unter="Misst alle eingespielten Varianten: Sekunden je Seite, Zeichenfehler, Laborwerte, Speicher – am besten nachts"
          rechts={<BenchmarkStart offen={offen || !s.eingerichtet} onStart={(eigene) => einfach({ aktion: "benchmark", eigene },
            "Benchmark starten? Er lastet die CPU je Variante mehrere Minuten voll aus.")} />} />
        {(bench.data ?? []).map((b) => (
          <div key={b.datei} className="flex flex-col gap-1">
            <div className="text-[0.8125rem] gedaempft">Lauf {b.zeit.replace(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})$/, "$3.$2.$1 $4:$5")}</div>
            <table className="tabelle text-sm">
              <thead><tr><th className="th">Variante</th><th className="th">Laden</th><th className="th">RAM max</th><th className="th">s/Seite Scan</th>
                <th className="th">s/Seite Foto</th><th className="th">CER Scan</th><th className="th">Labor-F1</th></tr></thead>
              <tbody>{b.varianten.map((v) => (
                <tr key={v.variante}><td className="td">{v.variante}</td><td className="td num">{v.laden_s ?? "—"} s</td>
                  <td className="td num">{v.ram_max_gb ?? "—"} GB</td><td className="td num">{v.je_kategorie.tabelle?.sekunden_je_seite ?? "—"}</td>
                  <td className="td num">{v.je_kategorie.foto?.sekunden_je_seite ?? "—"}</td><td className="td num">{v.je_kategorie.tabelle?.cer ?? "—"}</td>
                  <td className="td num">{v.je_kategorie.tabelle?.laborwerte_f1 ?? "—"}</td></tr>))}</tbody>
            </table>
          </div>))}
        {bench.data && !bench.data.length ? <Leer>Noch kein Benchmark.</Leer> : null}
      </Karte>

      <Karte className="flex flex-col gap-2">
        <KartenKopf titel="Aufträge" unter="Einrichtung, Modelle, Grenzen, Benchmark – mit Ausgabe des Servers" />
        {d.auftraege.length ? (
          <ul className="m-0 p-0 list-none flex flex-col divide-y divide-rand text-sm">
            {d.auftraege.map((a) => (
              <li key={a.id} className="py-2 flex flex-col gap-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium">{a.name}</span>
                  <Chip art={a.status === "erledigt" ? "ok" : a.status === "fehler" ? "fehler" : a.offen ? "akzent" : undefined}>{a.status_name}</Chip>
                  <span className="gedaempft text-[0.8125rem]">{zeitpunkt(a.angefordert_am)} · {a.angefordert_von_name}</span>
                </div>
                {a.ergebnis ? <div className="text-[0.8125rem]">{a.ergebnis}</div> : null}
                {a.ausgabe ? <details className="text-[0.75rem]"><summary>Ausgabe</summary>
                  <pre className="m-0 mt-1 whitespace-pre-wrap font-mono bg-fein rounded p-2 max-h-72 overflow-auto">{a.ausgabe}</pre></details> : null}
              </li>))}
          </ul>) : <Leer>Noch keine Aufträge.</Leer>}
      </Karte>

      {vorhaben ? <Bestaetigung titel={vorhaben.titel} text={vorhaben.text} laedt={auftrag.isPending} fehler={auftrag.error}
        onZu={() => setVorhaben(null)} onLos={(kennwort, code) => auftrag.mutate({ v: vorhaben, kennwort, code })} /> : null}
      {!vorhaben ? <Fehleranzeige fehler={auftrag.error} /> : null}
    </div>
  );
}

function Grenzen({ werte, offen, kerne, onSpeichern }: { werte: Record<string, string>; offen: boolean; kerne: number | null;
  onSpeichern: (w: Record<string, string>) => void }) {
  const [w, setW] = useState<Record<string, string>>(werte);
  useEffect(() => setW(werte), [werte]);
  const felder: { name: string; text: string; hinweis: string }[] = [
    { name: "KI_SPEICHER", text: "Speichergrenze Modell", hinweis: "z. B. 6g (4B Q4), 8g (4B Q8), 10g (9B)" },
    { name: "KI_THREADS", text: "Rechenkerne des Modells", hinweis: `Empfehlung: Kerne − 2${kerne ? ` = ${Math.max(1, kerne - 2)}` : ""}` },
    { name: "KI_WORKER_SPEICHER", text: "Speichergrenze KI-Dienst", hinweis: "z. B. 3g" },
    { name: "KI_WORKER_MAX", text: "Höchstens parallele Aufträge", hinweis: "Obergrenze für „parallel nachts“" },
    { name: "KI_KONTEXT", text: "Kontext (Tokens)", hinweis: "wie viel Text das Modell auf einmal liest; Standard 32768, mehr braucht mehr Speicher" },
  ];
  return (
    <Karte className="flex flex-col gap-3">
      <KartenKopf titel="Grenzen auf dem Server" unter="Harte Grenzen der Container (in .env). Zeitfenster und Lastgrenzen: Reiter „Zeitfenster und Grenzen“." />
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {felder.map((f) => (
          <Feld key={f.name} label={f.text} hinweis={f.hinweis}>
            {(p) => <Eingabe {...p} value={w[f.name] ?? ""} onChange={(e) => setW({ ...w, [f.name]: e.target.value.trim() })} />}
          </Feld>))}
      </div>
      <div><Knopf disabled={offen} onClick={() => onSpeichern(w)}>Grenzen speichern</Knopf></div>
    </Karte>
  );
}

function BenchmarkStart({ offen, onStart }: { offen: boolean; onStart: (eigene: boolean) => void }) {
  const [eigene, setEigene] = useState(false);
  return (
    <span className="flex items-center gap-2 flex-wrap">
      <label className="text-[0.8125rem] flex items-center gap-1.5" title="Dateien in /srv/epm/data/ki/benchmark (z. B. hand_rezept.jpg + hand_rezept.txt)">
        <input type="checkbox" checked={eigene} onChange={(e) => setEigene(e.target.checked)} />mit eigenen Seiten</label>
      <Knopf klein disabled={offen} onClick={() => onStart(eigene)}>Benchmark starten</Knopf>
    </span>
  );
}

function Hochladen({ max, uploads, offen, onEinspielen }: { max: number; uploads: Upload[]; offen: boolean; onEinspielen: (u: Upload) => void }) {
  const qc = useQueryClient();
  const eingabe = useRef<HTMLInputElement>(null);
  const abbruch = useRef(false);
  const [datei, setDatei] = useState<File | null>(null);
  const [stand, setStand] = useState<{ upload?: string; erhalten: number; laeuft: boolean; fehler?: string }>({ erhalten: 0, laeuft: false });
  const entfernen = useMutation({
    mutationFn: (u: string) => api(`ki/hochladen/${u}/`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ki", "einrichtung"] }),
  });
  const falsch = !!datei && !/^epm-ki-modelle-.*\.tar$/i.test(datei.name);
  const zuGross = !!datei && datei.size > max;
  const los = async () => {
    if (!datei) return;
    abbruch.current = false;
    let upload = stand.upload;
    let versatz = stand.erhalten;
    setStand((x) => ({ ...x, laeuft: true, fehler: undefined }));
    try {
      if (!upload) {
        const r = await api<{ upload: string; erhalten: number }>("ki/hochladen/", { body: { name: datei.name, groesse: datei.size } });
        upload = r.upload;
        versatz = r.erhalten;
      }
      let versuche = 0;
      while (versatz < datei.size) {
        if (abbruch.current) return;
        try {
          const r = await api<{ erhalten: number }>(`ki/hochladen/${upload}/?versatz=${versatz}`, { method: "PUT", roh: datei.slice(versatz, versatz + TEIL) });
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
      setStand({ erhalten: 0, laeuft: false });
      setDatei(null);
      void qc.invalidateQueries({ queryKey: ["ki", "einrichtung"] });
    } catch (e) {
      setStand({ upload, erhalten: versatz, laeuft: false, fehler: e instanceof Error && e.message ? e.message : "Die Verbindung wurde unterbrochen." });
    }
  };
  const prozent = datei ? Math.floor((100 * stand.erhalten) / datei.size) : 0;
  return (
    <div className="flex flex-col gap-2 border-t border-rand pt-3">
      <div className="text-sm font-medium">Modell-Paket hochladen</div>
      <div className="flex items-center gap-2 flex-wrap">
        <input ref={eingabe} type="file" accept=".tar" className="hidden" onChange={(e) => { setDatei(e.target.files?.[0] ?? null); setStand({ erhalten: 0, laeuft: false }); }} />
        <Knopf icon="hochladen" disabled={stand.laeuft} onClick={() => eingabe.current?.click()}>Datei auswählen</Knopf>
        {datei ? <span className="text-sm">{datei.name} · {dateigroesse(datei.size)}</span> : <span className="text-[0.8125rem] gedaempft">epm-ki-modelle-&lt;Datum&gt;.tar</span>}
        <Knopf variante="pri" laedt={stand.laeuft} disabled={!datei || falsch || zuGross || stand.laeuft} onClick={() => void los()}>{stand.upload ? "Fortsetzen" : "Hochladen"}</Knopf>
        {stand.laeuft ? <Knopf variante="geist" onClick={() => { abbruch.current = true; }}>Anhalten</Knopf> : null}
      </div>
      {falsch ? <div className="fehlertext text-[0.8125rem]">Bitte das vorbereitete Modell-Paket wählen (epm-ki-modelle-&lt;Datum&gt;.tar).</div> : null}
      {zuGross ? <div className="fehlertext text-[0.8125rem]">Die Datei ist zu groß (höchstens {dateigroesse(max)}).</div> : null}
      {stand.laeuft || stand.erhalten ? (
        <div className="h-2 rounded-full bg-fein overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={prozent} aria-label="Fortschritt des Hochladens">
          <div className="h-full bg-akzent" style={{ width: `${prozent}%` }} /></div>) : null}
      {stand.fehler ? <Meldung art="fehler">{stand.fehler} – „Fortsetzen“ macht an der Stelle weiter.</Meldung> : null}
      {uploads.map((u) => (
        <div key={u.upload} className="flex items-center gap-2 flex-wrap text-sm">
          <span>{u.name}</span><span className="gedaempft">{dateigroesse(u.erhalten)} von {dateigroesse(u.groesse)}</span>
          {u.vollstaendig ? <Knopf klein variante="pri" disabled={offen} onClick={() => onEinspielen(u)}>Einspielen</Knopf> : <Chip art="warn">unvollständig</Chip>}
          <Knopf klein variante="geist" onClick={() => entfernen.mutate(u.upload)}>Entfernen</Knopf>
        </div>))}
      <Fehleranzeige fehler={entfernen.error} />
    </div>
  );
}
