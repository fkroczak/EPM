/**
 * Administration › KI (Experimentell): Stand des Dienstes, Zeitfenster und Grenzen der Auslastung (Auftrag 2/3),
 * Modelle mit Evaluation, Aktivieren und Zurückschalten (Auftrag 7), Evaluationsfälle und Trainingsfreigabe.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { zahl, zeitpunkt } from "@/lib/format";
import { MODUS_TEXT, STATUS_TEXT, prozentText } from "@/lib/ki";
import type { KiStand, KiStatus } from "@/lib/ki";
import { Anzeige, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Seitenkopf, Textfeld,
} from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Reiter, ReiterInhalt, useReiter } from "@/components/ui/reiter";
import { Seite } from "@/components/layout/Shell";
import { KiStandKarte } from "../ki/KiQueue";
import { KiEinrichtung } from "./KiEinrichtung";

type Einstellungen = {
  aktiv: boolean; nacht_beginn: string; nacht_ende: string; zeitzone: string; worker_nacht: number; worker_tag: number;
  max_cpu_prozent: number; min_ram_frei_mb: number; max_last_je_kern: number; pause_bei_sicherung: boolean; altbestand_lesen: boolean;
  max_seiten: number; bild_max_px: number; ocr_schwelle: number; feld_unsicher: number; verknuepfung_stunden: number;
  aufbewahrung_tage: number; training_erlaubt: boolean; training_nur_wochenende: boolean; rechtsgrundlage: string;
  rechtsgrundlage_geprueft_am: string | null; rechtsgrundlage_geprueft_von_name: string; geaendert_am: string;
  geaendert_von_name: string; worker_max: number;
};
type Modell = {
  id: number; name: string; rolle: string; datei: string; projektor: string; sha256: string; groesse: number; quantisierung: string;
  status: "eingespielt" | "evaluation" | "aktiv" | "vorherig" | "gesperrt"; status_name: string; notiz: string;
  evaluation: { dokumenttyp_genauigkeit?: number | null; laborwerte?: { f1: number }; infusionen?: { f1: number }; dauer_s_mittel?: number | null; faelle?: number; am?: string };
  eingespielt_am: string; aktiviert_am: string | null; aktiviert_von_name: string;
};
type Evaluation = {
  faelle: number; training_freigegeben: number; je_typ: Record<string, number>;
  liste: { id: number; dokumenttyp: string; eingabe_text: string; erwartet: unknown; training_freigegeben: boolean; freigegeben_von: string; erstellt_am: string }[];
  laeufe: { id: number; modell: string; gestartet_am: string; fertig_am: string | null; faelle: number; fehler: string }[];
};

export function KiVerwaltung() {
  const [reiter, setReiter] = useReiter(["einrichtung", "stand", "einstellungen", "modelle", "training"] as const);
  const stand = useQuery({ queryKey: ["ki", "stand"], queryFn: () => api<KiStand>("ki/stand/"), refetchInterval: 15_000 });
  return (
    <Seite pfad={[{ text: "Administration" }, { text: "KI (Experimentell)" }]}>
      <Seitenkopf titel="KI (Experimentell)" unter="Lokale Modelle, ohne Internet – Zeitfenster, Auslastung, Modelle, Qualität" />
      <KiStandKarte stand={stand.data} />
      <Reiter label="Bereiche" wert={reiter} onWahl={setReiter} eintraege={[
        { wert: "einrichtung", text: "Einrichtung" }, { wert: "stand", text: "Stand" },
        { wert: "einstellungen", text: "Zeitfenster und Grenzen" },
        { wert: "modelle", text: "Modelle" }, { wert: "training", text: "Evaluation und Training" }]} />
      <ReiterInhalt>
        {reiter === "einrichtung" ? <KiEinrichtung /> : null}
        {reiter === "stand" ? <Stand stand={stand.data} /> : null}
        {reiter === "einstellungen" ? <EinstellungenForm /> : null}
        {reiter === "modelle" ? <Modelle /> : null}
        {reiter === "training" ? <Training /> : null}
      </ReiterInhalt>
    </Seite>
  );
}

function Stand({ stand }: { stand?: KiStand }) {
  if (!stand) return <Laden />;
  const d = stand.dienst;
  const l = d?.entscheidung.last;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Karte className="flex flex-col gap-2">
        <KartenKopf titel="KI-Dienst" />
        <Anzeige label="Modus">{d ? `${MODUS_TEXT[d.entscheidung.modus] ?? d.entscheidung.modus}${d.entscheidung.sparsam ? " (sparsam)" : ""}` : "nicht eingerichtet"}</Anzeige>
        <Anzeige label="Grund">{d?.entscheidung.grund}</Anzeige>
        <Anzeige label="Parallele Aufträge erlaubt">{d ? d.entscheidung.parallel : null}</Anzeige>
        <Anzeige label="Modell">{stand.modell?.name ?? "keins aktiviert"}{d ? ` · ${d.modell.bereit ? "bereit" : "nicht bereit / schläft"}` : ""}</Anzeige>
        <Anzeige label="Erste Texterkennung">{d ? (d.pp_ocr ? "Tesseract + PP-OCR" : "nur Tesseract") : null}</Anzeige>
        <Anzeige label="Verarbeitet seit dem Start">{d?.bearbeitet}</Anzeige>
      </Karte>
      <Karte className="flex flex-col gap-2">
        <KartenKopf titel="Auslastung des Servers" unter="Grundlage der Steuerung – EPM und Datenbank haben Vorrang" />
        <Anzeige label="CPU">{l?.cpu_prozent != null ? `${Math.round(l.cpu_prozent)} %` : null}</Anzeige>
        <Anzeige label="Freier Speicher">{l?.ram_frei_mb != null ? `${zahl(l.ram_frei_mb)} MB von ${zahl(l.ram_gesamt_mb ?? 0)} MB` : null}</Anzeige>
        <Anzeige label="Systemlast (1 min)">{l?.last1 != null ? `${l.last1} bei ${l.kerne} Kernen` : null}</Anzeige>
      </Karte>
      {stand.queue ? (
        <Karte className="flex flex-col gap-2 lg:col-span-2">
          <KartenKopf titel="Bestand" unter={`${zahl(stand.queue.gesamt)} Dokumente insgesamt, davon ${zahl(stand.queue.noch_nicht_vorgemerkt)} noch nicht vorgemerkt`} />
          <div className="flex gap-2 flex-wrap text-sm">
            {Object.entries(stand.queue.je_status).map(([s, n]) => <Chip key={s}>{STATUS_TEXT[s as KiStatus] ?? s}: {n}</Chip>)}
          </div>
        </Karte>) : null}
    </div>
  );
}

const ZAHLFELDER: { name: keyof Einstellungen; text: string; hinweis?: string; schritt?: string }[] = [
  { name: "worker_nacht", text: "Parallele Aufträge nachts" },
  { name: "worker_tag", text: "Parallele Aufträge tagsüber", hinweis: "0 = nur ausdrücklich angeforderte, einer nach dem anderen" },
  { name: "max_cpu_prozent", text: "CPU-Grenze (%)", hinweis: "darüber pausiert die KI" },
  { name: "min_ram_frei_mb", text: "Mindestens frei (MB RAM)" },
  { name: "max_last_je_kern", text: "Systemlast je Kern höchstens", schritt: "0.1" },
  { name: "max_seiten", text: "Seiten je Dokument höchstens" },
  { name: "bild_max_px", text: "Bildgröße für das Modell (px)", hinweis: "kleiner = schneller, aber ungenauer" },
  { name: "ocr_schwelle", text: "OCR-Schwelle (0–1)", hinweis: "darunter liest das Modell die Seite selbst", schritt: "0.01" },
  { name: "feld_unsicher", text: "Unsicher unter (0–1)", schritt: "0.01" },
  { name: "verknuepfung_stunden", text: "Zeitfenster Labor → Maßnahme (h)" },
  { name: "aufbewahrung_tage", text: "Zwischendateien löschen nach (Tagen)" },
];

function EinstellungenForm() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const q = useQuery({ queryKey: ["ki", "einstellungen"], queryFn: () => api<Einstellungen>("ki/einstellungen/") });
  const [werte, setWerte] = useState<Partial<Einstellungen>>({});
  useEffect(() => { if (q.data) setWerte(q.data); }, [q.data]);
  const speichern = useMutation({
    mutationFn: () => api<Einstellungen>("ki/einstellungen/", { method: "PUT", body: werte }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["ki"] }); melden("Gespeichert – gilt ab dem nächsten Durchlauf des KI-Dienstes."); },
  });
  if (!q.data) return q.isLoading ? <Laden /> : <Fehleranzeige fehler={q.error} />;
  const fehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const setz = (k: keyof Einstellungen, v: unknown) => setWerte({ ...werte, [k]: v });
  return (
    <Karte className="flex flex-col gap-4">
      <KartenKopf titel="Zeitfenster und Grenzen" unter={q.data.geaendert_von_name ? `zuletzt geändert ${zeitpunkt(q.data.geaendert_am)} von ${q.data.geaendert_von_name}` : undefined} />
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!werte.aktiv} onChange={(e) => setz("aktiv", e.target.checked)} />
        KI-Dienst aktiv (aus: nimmt nichts Neues an)</label>
      <div className="grid gap-3 sm:grid-cols-3">
        <Feld label="Nachtfenster von" fehler={fehler.nacht_beginn}>{(p) => <Eingabe {...p} type="time" value={(werte.nacht_beginn ?? "").slice(0, 5)} onChange={(e) => setz("nacht_beginn", e.target.value)} />}</Feld>
        <Feld label="bis" fehler={fehler.nacht_ende}>{(p) => <Eingabe {...p} type="time" value={(werte.nacht_ende ?? "").slice(0, 5)} onChange={(e) => setz("nacht_ende", e.target.value)} />}</Feld>
        <Feld label="Zeitzone" fehler={fehler.zeitzone}>{(p) => <Eingabe {...p} value={werte.zeitzone ?? ""} onChange={(e) => setz("zeitzone", e.target.value)} />}</Feld>
        {ZAHLFELDER.map((f) => (
          <Feld key={f.name} label={f.text} hinweis={f.name === "worker_nacht" ? `höchstens ${q.data.worker_max} (KI_WORKER_MAX)` : f.hinweis} fehler={fehler[f.name]}>
            {(p) => <Eingabe {...p} type="number" step={f.schritt ?? "1"} value={String(werte[f.name] ?? "")}
              onChange={(e) => setz(f.name, e.target.value === "" ? "" : Number(e.target.value))} />}
          </Feld>))}
      </div>
      <div className="flex flex-col gap-2 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={!!werte.pause_bei_sicherung} onChange={(e) => setz("pause_bei_sicherung", e.target.checked)} />
          Pause, solange die Sicherung läuft</label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={!!werte.altbestand_lesen} onChange={(e) => setz("altbestand_lesen", e.target.checked)} />
          vorhandene Dokumente der Akten nach und nach lesen (sonst nur neue)</label>
      </div>
      <div className="flex gap-2"><Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf></div>
      <Fehleranzeige fehler={speichern.error} />
    </Karte>
  );
}

function BestaetigenDialog({ offen, onOffen, titel, text, onBestaetigt, laedt, fehler }: {
  offen: boolean; onOffen: (o: boolean) => void; titel: string; text: string; laedt: boolean; fehler: unknown;
  onBestaetigt: (kennwort: string, code: string) => void;
}) {
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  const f = fehler instanceof ApiFehler ? fehler.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={titel} beschreibung={text}
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={laedt} disabled={!kennwort || !code} onClick={() => onBestaetigt(kennwort, code)}>Bestätigen</Knopf></>}>
      <Feld label="Ihr Passwort" fehler={f.kennwort}>{(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}</Feld>
      <Feld label="Code aus der Authenticator-App" fehler={f.code}>{(p) => <Eingabe {...p} inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}</Feld>
      {!f.kennwort && !f.code ? <Fehleranzeige fehler={fehler} /> : null}
    </Dialog>
  );
}

function Modelle() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const q = useQuery({ queryKey: ["ki", "modelle"], queryFn: () => api<Modell[]>("ki/modelle/") });
  const [aktivieren, setAktivieren] = useState<Modell | null>(null);
  const [neu, setNeu] = useState(false);
  const wechseln = useMutation({
    mutationFn: ({ m, kennwort, code }: { m: Modell; kennwort: string; code: string }) =>
      api(`ki/modelle/${m.id}/aktivieren/`, { body: { kennwort, code, ohne_evaluation: m.status === "eingespielt" } }),
    onSuccess: () => { setAktivieren(null); void qc.invalidateQueries({ queryKey: ["ki"] }); melden("Aktiviert – der Modell-Container lädt es neu (ein bis zwei Minuten)."); },
  });
  const evaluieren = useMutation({
    mutationFn: (m: Modell) => api(`ki/modelle/${m.id}/evaluieren/`, { body: {} }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["ki", "modelle"] }); melden("Evaluation angelegt – läuft in der nächsten Nacht."); },
  });
  const sperren = useMutation({
    mutationFn: (m: Modell) => api(`ki/modelle/${m.id}/sperren/`, { body: {} }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ki", "modelle"] }),
  });
  const aktiv = (q.data ?? []).find((m) => m.status === "aktiv");
  return (
    <Karte className="flex flex-col gap-3 overflow-x-auto">
      <KartenKopf titel="Modelle" unter="Produktivmodelle werden nie überschrieben: neue Version evaluieren, vergleichen, aktivieren – die vorherige bleibt zum Zurückschalten."
        rechts={<Knopf klein icon="plus" onClick={() => setNeu(true)}>Registrieren</Knopf>} />
      {q.isLoading ? <Laden /> : (
        <table className="tabelle text-sm" data-testid="ki-modelle">
          <thead><tr><th className="th">Modell</th><th className="th">Status</th><th className="th">Dokumenttyp</th><th className="th">Labor-F1</th>
            <th className="th">Infusion-F1</th><th className="th">s/Fall</th><th className="th" /></tr></thead>
          <tbody>{(q.data ?? []).map((m) => (
            <tr key={m.id}>
              <td className="td"><div className="font-medium">{m.name}</div>
                <div className="text-[0.75rem] gedaempft">{m.datei} · {m.sha256.slice(0, 12)}{m.groesse ? ` · ${(m.groesse / 1e9).toFixed(1)} GB` : ""}</div></td>
              <td className="td"><Chip art={m.status === "aktiv" ? "ok" : m.status === "gesperrt" ? "fehler" : m.status === "vorherig" ? "akzent" : undefined}>{m.status_name}</Chip>
                {m.aktiviert_am ? <div className="text-[0.75rem] gedaempft">{zeitpunkt(m.aktiviert_am)} {m.aktiviert_von_name}</div> : null}</td>
              <td className="td num">{prozentText(m.evaluation.dokumenttyp_genauigkeit)}</td>
              <td className="td num">{m.evaluation.laborwerte ? m.evaluation.laborwerte.f1.toFixed(2) : "—"}</td>
              <td className="td num">{m.evaluation.infusionen ? m.evaluation.infusionen.f1.toFixed(2) : "—"}</td>
              <td className="td num">{m.evaluation.dauer_s_mittel ?? "—"}</td>
              <td className="td whitespace-nowrap">
                {m.status !== "aktiv" && m.status !== "gesperrt" ? <>
                  <Knopf klein variante="geist" laedt={evaluieren.isPending} onClick={() => evaluieren.mutate(m)}>Evaluieren</Knopf>
                  <Knopf klein onClick={() => setAktivieren(m)}>{m.status === "vorherig" ? "Zurückschalten" : "Aktivieren"}</Knopf>
                  <Knopf klein variante="geist" onClick={() => sperren.mutate(m)}>Sperren</Knopf>
                </> : null}
              </td>
            </tr>))}</tbody>
        </table>)}
      {q.data && !q.data.length ? <Leer>Noch kein Modell registriert (sudo epm-ki einspielen … und einrichten).</Leer> : null}
      <Fehleranzeige fehler={q.error ?? evaluieren.error ?? sperren.error} />
      {aktivieren ? (
        <BestaetigenDialog offen onOffen={(o) => { if (!o) setAktivieren(null); }} laedt={wechseln.isPending} fehler={wechseln.error}
          titel={`${aktivieren.name} aktivieren`}
          text={`${aktiv ? `Bisher aktiv: ${aktiv.name} – bleibt als vorherige Version. ` : ""}${aktivieren.status === "eingespielt"
            ? "Achtung: noch nicht evaluiert. " : ""}Bestätigung mit Passwort und zweitem Faktor; steht im Audit-Log.`}
          onBestaetigt={(kennwort, code) => wechseln.mutate({ m: aktivieren, kennwort, code })} />) : null}
      {neu ? <ModellNeu onZu={() => setNeu(false)} /> : null}
    </Karte>
  );
}

function ModellNeu({ onZu }: { onZu: () => void }) {
  const qc = useQueryClient();
  const [w, setW] = useState({ name: "", datei: "", projektor: "", sha256: "", quantisierung: "" });
  const los = useMutation({
    mutationFn: () => api("ki/modelle/", { body: w }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["ki", "modelle"] }); onZu(); },
  });
  const f = los.error instanceof ApiFehler ? los.error.felder : {};
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel="Modell registrieren"
      beschreibung="Die Dateien müssen offline eingespielt im Modellordner liegen (sudo epm-ki einspielen). Einfacher: sudo epm-ki einrichten registriert alle eingespielten Varianten mit Prüfsumme."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf><Knopf variante="pri" laedt={los.isPending} onClick={() => los.mutate()}>Registrieren</Knopf></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        {(["name", "quantisierung", "datei", "projektor", "sha256"] as const).map((k) => (
          <Feld key={k} label={{ name: "Name", quantisierung: "Quantisierung", datei: "GGUF-Datei", projektor: "Vision-Projektor (mmproj)", sha256: "SHA-256 der GGUF-Datei" }[k]}
            fehler={f[k]} className={k === "sha256" ? "sm:col-span-2" : undefined}>
            {(p) => <Eingabe {...p} value={w[k]} onChange={(e) => setW({ ...w, [k]: e.target.value.trim() })} />}
          </Feld>))}
      </div>
      <Fehleranzeige fehler={los.error} />
    </Dialog>
  );
}

function Training() {
  const { darf } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const ev = useQuery({ queryKey: ["ki", "evaluation"], queryFn: () => api<Evaluation>("ki/evaluation/") });
  const einst = useQuery({ queryKey: ["ki", "einstellungen"], queryFn: () => api<Einstellungen>("ki/einstellungen/"), enabled: darf("ki_verwalten") });
  const [rg, setRg] = useState(false);
  const [text, setText] = useState("");
  const [wahl, setWahl] = useState<number[]>([]);
  const erzeugen = useMutation({
    mutationFn: () => api<{ neu: number }>("ki/evaluation/", { body: { aktion: "erzeugen" } }),
    onSuccess: (r) => { void qc.invalidateQueries({ queryKey: ["ki", "evaluation"] }); melden(`${r.neu} neue Evaluationsfälle (pseudonymisiert).`); },
  });
  const freigeben = useMutation({
    mutationFn: () => api<{ freigegeben: number }>("ki/evaluation/", { body: { aktion: "training_freigeben", faelle: wahl } }),
    onSuccess: (r) => { setWahl([]); void qc.invalidateQueries({ queryKey: ["ki", "evaluation"] }); melden(`${r.freigegeben} Beispiele für das Training freigegeben.`); },
  });
  const rechtsgrundlage = useMutation({
    mutationFn: ({ kennwort, code }: { kennwort: string; code: string }) => api("ki/rechtsgrundlage/", { body: { rechtsgrundlage: text, kennwort, code } }),
    onSuccess: () => { setRg(false); void qc.invalidateQueries({ queryKey: ["ki"] }); melden("Rechtsgrundlage dokumentiert."); },
  });
  const d = ev.data;
  const geprueft = einst.data?.rechtsgrundlage_geprueft_am;
  return (
    <div className="flex flex-col gap-4">
      <Meldung art="info" className="text-[0.8125rem]">
        Evaluationsfälle entstehen aus geprüften Dokumenten (Eingabe = OCR-Text, Erwartung = bestätigte Werte) und werden
        <strong> pseudonymisiert</strong> (Namen, Geburtsdatum, Nummern, Anschrift, Kontaktdaten). Pseudonymisiert ist nicht anonym:
        Für das Training gehen Beispiele nur nach Sichtprüfung und Freigabe – und erst, wenn die Rechtsgrundlagen-Prüfung dokumentiert ist.
        Trainiert wird nie auf dem Produktivmodell: Ergebnis ist eine neue Modellversion, die evaluiert und ausdrücklich aktiviert werden muss.
      </Meldung>
      <Karte className="flex flex-col gap-3">
        <KartenKopf titel="Rechtsgrundlage für das Training"
          rechts={darf("ki_training_freigeben") ? <Knopf klein onClick={() => { setText(einst.data?.rechtsgrundlage ?? ""); setRg(true); }}>{geprueft ? "Neu dokumentieren" : "Dokumentieren"}</Knopf> : null} />
        {geprueft ? <div className="text-sm whitespace-pre-line">{einst.data?.rechtsgrundlage}<div className="text-[0.75rem] gedaempft mt-1">
          dokumentiert {zeitpunkt(geprueft)} von {einst.data?.rechtsgrundlage_geprueft_von_name}</div></div>
          : <Meldung art="warn">Noch nicht dokumentiert – Training und Trainingsfreigabe sind gesperrt.</Meldung>}
      </Karte>
      <Karte className="flex flex-col gap-3 overflow-x-auto">
        <KartenKopf titel="Evaluationsfälle" unter={d ? `${d.faelle} Fälle, davon ${d.training_freigegeben} für das Training freigegeben` : undefined}
          rechts={<>
            {darf("ki_verwalten") ? <Knopf klein laedt={erzeugen.isPending} onClick={() => erzeugen.mutate()}>Aus geprüften Dokumenten erzeugen</Knopf> : null}
            {darf("ki_training_freigeben") ? <Knopf klein variante="pri" disabled={!wahl.length || !geprueft} laedt={freigeben.isPending}
              onClick={() => freigeben.mutate()}>Ausgewählte für Training freigeben ({wahl.length})</Knopf> : null}
          </>} />
        {ev.isLoading ? <Laden /> : null}
        <ul className="m-0 p-0 list-none flex flex-col divide-y divide-rand">
          {(d?.liste ?? []).map((f) => (
            <li key={f.id} className="py-2 flex gap-2.5 items-start text-sm">
              {darf("ki_training_freigeben") && !f.training_freigegeben ? (
                <input type="checkbox" className="mt-1" aria-label={`Fall ${f.id} auswählen`} checked={wahl.includes(f.id)}
                  onChange={(e) => setWahl(e.target.checked ? [...wahl, f.id] : wahl.filter((x) => x !== f.id))} />) : <span className="w-[0.8125rem]" />}
              <details className="flex-1 min-w-0">
                <summary>Fall {f.id} · {f.dokumenttyp || "—"} {f.training_freigegeben ? <Chip art="ok">freigegeben ({f.freigegeben_von})</Chip> : null}</summary>
                <pre className="m-0 mt-1 whitespace-pre-wrap text-[0.75rem] font-mono bg-fein rounded p-2 max-h-64 overflow-auto">{f.eingabe_text}</pre>
              </details>
            </li>))}
        </ul>
        {d && !d.faelle ? <Leer>Noch keine Fälle.</Leer> : null}
        <Fehleranzeige fehler={ev.error ?? erzeugen.error ?? freigeben.error} />
      </Karte>
      {d?.laeufe.length ? (
        <Karte className="flex flex-col gap-2">
          <KartenKopf titel="Evaluationsläufe" />
          <ul className="m-0 pl-4 text-sm">{d.laeufe.map((l) => <li key={l.id}>{l.modell}: {zeitpunkt(l.gestartet_am)} · {l.fertig_am ? `fertig, ${l.faelle} Fälle` : "wartet auf die Nacht"}{l.fehler ? ` – ${l.fehler}` : ""}</li>)}</ul>
        </Karte>) : null}
      {rg ? (
        <Dialog offen onOffen={(o) => { if (!o) setRg(false); }} titel="Rechtsgrundlage dokumentieren" breite={640}
          beschreibung="Rechtsgrundlage (z. B. Art. 9 Abs. 2 lit. h DSGVO i. V. m. § 22 BDSG, Qualitätssicherung), Zweck, Umfang, Pseudonymisierung, Beteiligung der bzw. des Datenschutzbeauftragten, DSFA."
          fuss={null}>
          <Feld label="Dokumentation">{(p) => <Textfeld {...p} rows={8} value={text} onChange={(e) => setText(e.target.value)} />}</Feld>
          <BestaetigenInline laedt={rechtsgrundlage.isPending} fehler={rechtsgrundlage.error}
            onBestaetigt={(kennwort, code) => rechtsgrundlage.mutate({ kennwort, code })} />
        </Dialog>) : null}
    </div>
  );
}

function BestaetigenInline({ laedt, fehler, onBestaetigt }: { laedt: boolean; fehler: unknown; onBestaetigt: (k: string, c: string) => void }) {
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  const f = fehler instanceof ApiFehler ? fehler.felder : {};
  return (
    <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] items-end">
      <Feld label="Ihr Passwort" fehler={f.kennwort}>{(p) => <Eingabe {...p} type="password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}</Feld>
      <Feld label="Code (Authenticator)" fehler={f.code}>{(p) => <Eingabe {...p} inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} />}</Feld>
      <Knopf variante="pri" laedt={laedt} disabled={!kennwort || !code} onClick={() => onBestaetigt(kennwort, code)}>Bestätigen</Knopf>
      {!f.kennwort && !f.code ? <div className="sm:col-span-3"><Fehleranzeige fehler={fehler} /></div> : null}
    </div>
  );
}
