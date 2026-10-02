/**
 * Administration › Import (nur Admin, Recht „Altdaten übernehmen“): Übernahme der Altdaten aus dem bisherigen
 * System (F65). Schritte: Dump laden → Zuordnungen prüfen und korrigieren → Probelauf → Import → Dokumente →
 * Abschließen. Bis zum Abschließen lässt sich der Import vollständig zurücknehmen und mit einem frischen Dump
 * wiederholen; die Zuordnungen bleiben dabei erhalten.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { dateigroesse, zahl, zeitpunkt } from "@/lib/format";
import { Seite } from "@/components/layout/Shell";
import { Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Segmente, Seitenkopf } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Zuordnungen } from "./Zuordnungen";
import { BEREICHE, NICHT } from "./typen";
import type { Aenderung, Dokumentenstand, Etappe, Lauf, Protokollzeile, Stand, Zaehlung, Zahlen, Zuordnung } from "./typen";

type Schritt = "quelle" | "zuordnungen" | "import" | "dokumente" | "abschluss" | "protokolle";
const SCHRITTE: { wert: Schritt; text: string }[] = [
  { wert: "quelle", text: "1 · Dump" }, { wert: "zuordnungen", text: "2 · Zuordnungen" }, { wert: "import", text: "3 · Probelauf und Import" },
  { wert: "dokumente", text: "4 · Dokumente" }, { wert: "abschluss", text: "5 · Abschließen" }, { wert: "protokolle", text: "Protokolle" },
];
const STUFE: Record<Protokollzeile["stufe"], { text: string; art: "fehler" | "warn" | "neutral" | "ok" }> = {
  fehler: { text: "Fehler", art: "fehler" }, warnung: { text: "Warnung", art: "warn" }, hinweis: { text: "Hinweis", art: "neutral" },
  info: { text: "Regel", art: "ok" },
};

function neuLaden(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ["altimport"] });
}

// ---------------------------------------------------------------- Zählung und Protokoll
function Zaehltabelle({ zahlen }: { zahlen: Zahlen }) {
  const zeilen: [string, Zaehlung | undefined][] = [["Patienten", zahlen.patienten], ["Gewichte", zahlen.gewichte], ["Kontakte", zahlen.kontakte],
    ["Infusionspläne", zahlen.infusionen]];
  if (!zeilen.some(([, z]) => z)) return null;
  return (
    <table className="tabelle" data-testid="zaehlung">
      <thead><tr><th className="th">Zählung</th><th className="th text-right w-[120px]">im Altsystem</th><th className="th text-right w-[120px]">wird übernommen</th><th className="th">nicht übernommen</th></tr></thead>
      <tbody>
        {zeilen.map(([name, z]) => z ? (
          <tr key={name}>
            <td className="td font-medium">{name}{name === "Patienten" && z.abgeschlossen ? <span className="font-normal gedaempft"> · {z.abgeschlossen} als abgeschlossene Akten</span> : null}</td>
            <td className="td num text-right">{zahl(z.alt)}</td>
            <td className="td num text-right">{zahl(z.neu)}</td>
            <td className="td text-[0.8125rem]">{Object.entries(z.nicht ?? {}).map(([k, n]) => `${zahl(n)} ${NICHT[k] ?? k}`).join(" · ") || "—"}</td>
          </tr>
        ) : null)}
        <tr>
          <td className="td font-medium">Neu angelegt</td>
          <td className="td" colSpan={3}>
            <span className="text-[0.8125rem]">{zahlen.benutzer?.neu ?? 0} Benutzer ({zahlen.benutzer?.konten ?? 0} Konten) · {zahlen.versorger?.neu ?? 0} Versorger ·{" "}
              {zahlen.versorger?.ansprechpartner_neu ?? 0} Ansprechpartner · {zahlen.auswahlwerte_neu ?? 0} Katheter in der Auswahlliste · {zahlen.praeparate_neu ?? 0} Präparate</span>
          </td>
        </tr>
      </tbody>
    </table>
  );
}

function Protokoll({ zeilen }: { zeilen: Protokollzeile[] }) {
  if (!zeilen.length) return <Leer>Kein Protokoll.</Leer>;
  return (
    <table className="tabelle" data-testid="protokoll">
      <thead><tr><th className="th w-[90px]" /><th className="th w-[130px]">Bereich</th><th className="th w-[80px] text-right">Anzahl</th><th className="th">Was</th><th className="th w-[240px]">z. B. Nr.</th></tr></thead>
      <tbody>
        {zeilen.map((p, i) => (
          <tr key={i}>
            <td className="td"><Chip art={STUFE[p.stufe]?.art}>{p.stufe === "info" && p.regel ? `Regel ${p.regel}` : STUFE[p.stufe]?.text ?? p.stufe}</Chip></td>
            <td className="td text-[0.8125rem]">{BEREICHE[p.bereich] ?? p.bereich}{p.stufe !== "info" && p.regel ? <span className="gedaempft"> · Regel {p.regel}</span> : null}</td>
            <td className="td num text-right">{zahl(p.anzahl)}</td>
            <td className="td text-sm">{p.text}</td>
            <td className="td num text-[0.75rem] gedaempft break-words">{p.beispiele.join(", ")}{p.anzahl > p.beispiele.length && p.beispiele.length ? " …" : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function LaufErgebnis({ lauf }: { lauf: Lauf }) {
  const g = lauf.zahlen.geschrieben;
  return (
    <div className="flex flex-col gap-3" data-testid="lauf-ergebnis">
      <div className={`meldung ${lauf.erfolgreich ? "ok" : "fehler"} flex flex-col gap-1`}>
        <span className="font-medium flex items-center gap-2"><Icon name={lauf.erfolgreich ? "haken" : "warnung"} />
          {lauf.art_name} vom {zeitpunkt(lauf.begonnen_am)}: {lauf.erfolgreich ? "erfolgreich" : "nicht erfolgreich"}
          {lauf.art === "probelauf" && lauf.erfolgreich ? " – es wurde nichts gespeichert" : ""}</span>
        {lauf.fehler ? <span className="whitespace-pre-line text-[0.8125rem]">{lauf.fehler}</span> : null}
        {g ? <span className="text-[0.8125rem]">Geschrieben{lauf.art === "probelauf" ? " und wieder zurückgerollt" : ""}: {g.patienten} Akten ({g.abgeschlossen} abgeschlossen) · {g.gewichte} Gewichte ·{" "}
          {g.kontakte} Kontakte · {g.plaene} Infusionspläne · {g.benutzer} Benutzer · {g.versorger} Versorger · {g.praeparate} Präparate</span> : null}
      </div>
      <Zaehltabelle zahlen={lauf.zahlen} />
      {lauf.protokoll ? <Protokoll zeilen={lauf.protokoll} /> : null}
      <div><a className="btn sec klein" href={`/api/altimport/laeufe/${lauf.id}/text/`} download>Protokoll als Textdatei</a></div>
    </div>
  );
}

// ---------------------------------------------------------------- Bestätigen mit Passwort und zweitem Faktor
function Bestaetigung({ offen, onZu, titel, beschreibung, wort, knopf, pfad, zusatz, onFertig, children }: {
  offen: boolean; onZu: () => void; titel: string; beschreibung: string; wort?: string; knopf: string; pfad: string;
  zusatz?: Record<string, unknown>; onFertig: (lauf: Lauf) => void; children?: ReactNode;
}) {
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  const [eingabe, setEingabe] = useState("");
  useEffect(() => { if (offen) { setKennwort(""); setCode(""); setEingabe(""); } }, [offen]);
  const los = useMutation({
    mutationFn: () => api<Lauf>(pfad, { body: { kennwort, code, bestaetigung: eingabe, ...zusatz } }),
    onSuccess: (lauf) => { onFertig(lauf); onZu(); },
  });
  useEffect(() => { if (!offen) los.reset(); }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) onZu(); }} titel={titel} beschreibung={beschreibung} breite={560}
      fuss={<>
        <Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={los.isPending} disabled={!kennwort || !code || (!!wort && !eingabe)} onClick={() => los.mutate()}>{knopf}</Knopf>
      </>}>
      <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); los.mutate(); }}>
        {children}
        {wort ? (
          <Feld label={`Zur Bestätigung „${wort}“ eintippen`} fehler={f.bestaetigung} pflicht>
            {(p) => <Eingabe {...p} autoComplete="off" value={eingabe} onChange={(e) => setEingabe(e.target.value)} />}
          </Feld>
        ) : null}
        <div className="grid grid-cols-2 gap-3">
          <Feld label="Ihr Passwort" fehler={f.kennwort} pflicht>
            {(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}
          </Feld>
          <Feld label="Code aus der Authenticator-App" hinweis="oder ein Notfall-Code" fehler={f.code} pflicht>
            {(p) => <Eingabe {...p} inputMode="text" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
          </Feld>
        </div>
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------- 1 · Dump
function Quelle({ stand }: { stand: Stand }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const datei = useRef<HTMLInputElement>(null);
  const [gewaehlt, setGewaehlt] = useState<File | null>(null);
  const laden = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("datei", gewaehlt!);
      return api<Stand>("altimport/dump/", { form });
    },
    onSuccess: (s) => {
      qc.setQueryData(["altimport", "stand"], s);
      neuLaden(qc);
      setGewaehlt(null);
      if (datei.current) datei.current.value = "";
      melden(`Dump „${s.dump?.name}“ geladen.`);
    },
  });
  const entfernen = useMutation({
    mutationFn: () => api<Stand>("altimport/dump/", { method: "DELETE" }),
    onSuccess: () => { neuLaden(qc); melden("Dump entfernt. Die Zuordnungen bleiben erhalten."); },
  });
  const f: Feldfehler = laden.error instanceof ApiFehler ? laden.error.felder : {};
  const offen = stand.status === "leer" || stand.status === "geladen";
  return (
    <div className="flex flex-col gap-5">
      <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="dump-karte">
        <KartenKopf titel="Dump des Altsystems"
          unter="MySQL-Dump als .sql oder .sql.gz (mysqldump oder Export aus phpMyAdmin). Kennwörter werden beim Einlesen verworfen und nie gespeichert." />
        {stand.dump ? (
          <dl className="m-0 grid grid-cols-[160px_1fr] gap-x-3 gap-y-1.5 text-sm">
            <dt className="gedaempft">Datei</dt><dd className="m-0 font-medium" data-testid="dump-name">{stand.dump.name} <span className="font-normal gedaempft">· {dateigroesse(stand.dump.groesse)}</span></dd>
            <dt className="gedaempft">Geladen</dt><dd className="m-0">{zeitpunkt(stand.dump.geladen_am)}{stand.dump.geladen_von ? ` · ${stand.dump.geladen_von}` : ""}</dd>
            <dt className="gedaempft">Prüfsumme</dt><dd className="m-0 num text-[0.8125rem] break-all">SHA-256 {stand.dump.sha256}</dd>
            <dt className="gedaempft">Tabellen</dt>
            <dd className="m-0" data-testid="dump-tabellen">{stand.tabellen.map((t) => `${t.name} (${zahl(t.zeilen)})`).join(" · ")}</dd>
          </dl>
        ) : <span className="text-sm gedaempft">{stand.status === "abgeschlossen" ? "Der Dump wurde mit dem Abschließen gelöscht." : "Noch kein Dump geladen."}</span>}
        {(stand.dump?.hinweise ?? []).map((h, i) => <Meldung key={i} art="info">{h}</Meldung>)}
        {offen ? (
          <form className="flex items-end gap-3 flex-wrap" onSubmit={(e) => { e.preventDefault(); if (gewaehlt) laden.mutate(); }}>
            <Feld label={stand.dump ? "Anderen (frischen) Dump laden" : "Dump auswählen"} fehler={f.datei} hinweis={`höchstens ${stand.upload_max_mb} MB; größere Dumps gepackt als .sql.gz`}>
              {(p) => <input {...p} ref={datei} type="file" accept=".sql,.gz,.txt" className="inp h-auto py-1.5"
                onChange={(e) => { setGewaehlt(e.target.files?.[0] ?? null); laden.reset(); }} />}
            </Feld>
            <Knopf type="submit" variante="pri" icon="hochladen" laedt={laden.isPending} disabled={!gewaehlt}>Dump laden</Knopf>
            {stand.dump ? <Knopf laedt={entfernen.isPending} onClick={() => entfernen.mutate()}>Dump entfernen</Knopf> : null}
          </form>
        ) : null}
        {laden.error && !Object.keys(f).length ? <Fehleranzeige fehler={laden.error} /> : null}
        <Fehleranzeige fehler={entfernen.error} />
        {stand.dump && offen ? <span className="text-[0.8125rem] gedaempft">Ein neuer Dump ersetzt den bisherigen. Die Zuordnungen bleiben erhalten und gelten für den neuen Dump weiter.</span> : null}
      </Karte>
      <Karte className="px-5 py-4 flex flex-col gap-2">
        <KartenKopf titel="So läuft die Übernahme" />
        <ol className="m-0 pl-5 text-sm leading-relaxed">
          <li><strong>Dump laden</strong> – für den Go-live einen frischen Dump ziehen (im alten Dump fehlen die Zeitpunkte der Gewichte und Kontakte).</li>
          <li><strong>Zuordnungen</strong> prüfen und korrigieren: Spalten, Benutzer, Versorger, Katheter, Präparate, gelöschte Patienten, Auffälligkeiten.</li>
          <li><strong>Probelauf</strong> – schreibt alles und rollt es wieder zurück; zeigt Zählung und Protokoll. <strong>Import</strong> nur in ein System ohne echte Akten.</li>
          <li><strong>Dokumente</strong> aus dem Ordner auf dem Server übernehmen.</li>
          <li><strong>Abschließen</strong> zum Go-live. Bis dahin lässt sich der Import vollständig zurücknehmen und wiederholen.</li>
        </ol>
      </Karte>
    </div>
  );
}

// ---------------------------------------------------------------- 3 · Probelauf und Import
function ImportSchritt({ stand, zuordnung }: { stand: Stand; zuordnung: Zuordnung | undefined }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [ergebnis, setErgebnis] = useState<Lauf | null>(null);
  const [dialog, setDialog] = useState<"import" | "zurueck" | null>(null);
  const probe = useMutation({
    mutationFn: () => api<Lauf>("altimport/probelauf/", { method: "POST" }),
    onSuccess: (lauf) => { setErgebnis(lauf); neuLaden(qc); },
  });
  const nach = (lauf: Lauf, text: string) => {
    setErgebnis(lauf);
    neuLaden(qc);
    for (const k of ["patienten", "startseite", "versorger", "benutzer", "praeparate", "auswahlwerte"]) void qc.invalidateQueries({ queryKey: [k] });
    melden(lauf.erfolgreich ? text : `${lauf.art_name} nicht erfolgreich.`, lauf.erfolgreich ? undefined : "fehler");
  };
  const hindernisse = zuordnung?.hindernisse ?? [];
  const u = stand.uebernommen;
  return (
    <div className="flex flex-col gap-5">
      {stand.status === "leer" ? <Meldung art="info">Zuerst unter „1 · Dump“ einen Dump laden.</Meldung> : null}
      {stand.status === "geladen" ? (
        <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="import-karte">
          <KartenKopf titel="Probelauf und Import"
            unter="Der Probelauf schreibt alles wie der Import in die Datenbank und rollt es danach wieder zurück – beliebig oft wiederholbar. Der Import gilt bis zum Abschließen als vorläufig und lässt sich zurücknehmen." />
          {hindernisse.length ? (
            <div className="meldung warn flex flex-col gap-1" data-testid="hindernisse">
              <span className="font-medium flex items-center gap-2"><Icon name="warnung" />Noch nicht möglich</span>
              <ul className="m-0 pl-5 text-[0.8125rem]">{hindernisse.map((h, i) => <li key={i}>{h}</li>)}</ul>
            </div>
          ) : <div className="meldung ok flex items-center gap-2" data-testid="hindernisse"><Icon name="haken" />Zuordnungen vollständig, keine echten Akten im EPM: Probelauf und Import sind möglich.</div>}
          {zuordnung?.stand ? <Zaehltabelle zahlen={zuordnung.stand.zahlen} /> : <Laden />}
          <div className="flex gap-2 flex-wrap">
            <Knopf variante="pri" laedt={probe.isPending} disabled={!zuordnung?.stand} onClick={() => probe.mutate()}>Probelauf starten</Knopf>
            <Knopf variante="dng" disabled={!zuordnung?.stand || hindernisse.length > 0} onClick={() => setDialog("import")}>Altdaten übernehmen …</Knopf>
          </div>
          <Fehleranzeige fehler={probe.error} />
          {zuordnung?.stand && !ergebnis ? (
            <>
              <span className="lbl mt-1">Protokoll nach den Regeln der Datenanalyse (Vorschau)</span>
              <Protokoll zeilen={zuordnung.stand.protokoll} />
            </>
          ) : null}
        </Karte>
      ) : null}
      {stand.status === "importiert" && u ? (
        <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="uebernommen-karte">
          <KartenKopf titel="Die Altdaten sind übernommen"
            unter={`${zeitpunkt(stand.importiert_am)}${stand.importiert_von ? ` · ${stand.importiert_von}` : ""} · Dump „${stand.dump?.name ?? ""}“`} />
          <span className="text-sm" data-testid="uebernommen-bestand">In den übernommenen Akten stehen jetzt: <strong>{zahl(u.patienten)} Akten</strong> · {zahl(u.gewichte)} Gewichte · {zahl(u.kontakte)} Kontakte ·{" "}
            {zahl(u.plaene)} Infusionspläne · {zahl(u.dokumente)} Dokumente.</span>
          <Meldung art="info">Die Übernahme ist vorläufig, bis sie unter „5 · Abschließen“ bestätigt wird. Bis dahin: Akten prüfen, Dokumente übernehmen,
            bei Bedarf zurücknehmen, Zuordnungen korrigieren oder einen frischen Dump laden und erneut übernehmen.</Meldung>
          <div><Knopf variante="dng" onClick={() => setDialog("zurueck")}>Import zurücknehmen …</Knopf></div>
        </Karte>
      ) : null}
      {stand.status === "abgeschlossen" ? (
        <Meldung art="ok">Die Übernahme ist abgeschlossen ({zeitpunkt(stand.abgeschlossen_am)}{stand.abgeschlossen_von ? ` · ${stand.abgeschlossen_von}` : ""}).</Meldung>
      ) : null}
      {ergebnis ? <Karte className="px-5 py-4"><LaufErgebnis lauf={ergebnis} /></Karte> : null}
      <Bestaetigung offen={dialog === "import"} onZu={() => setDialog(null)} titel="Altdaten übernehmen" knopf="Bestätigen und übernehmen" pfad="altimport/import/"
        beschreibung="Die Akten des Altsystems werden mit ihren Patientennummern angelegt – mit Gewichten, Kontakten und Infusionsplänen. Der Vorgang steht im Audit-Log."
        onFertig={(lauf) => nach(lauf, "Altdaten übernommen.")}>
        <Meldung art="info">Bis zum Abschließen lässt sich die Übernahme vollständig zurücknehmen.</Meldung>
      </Bestaetigung>
      <Bestaetigung offen={dialog === "zurueck"} onZu={() => setDialog(null)} titel="Import zurücknehmen" wort="ZURÜCKNEHMEN" knopf="Bestätigen und zurücknehmen"
        pfad="altimport/zuruecknehmen/"
        beschreibung="Alle übernommenen Akten werden entfernt – mit allen Einträgen, der Historie und den Dateien. Der Dump und die Zuordnungen bleiben."
        onFertig={(lauf) => nach(lauf, "Import zurückgenommen.")}>
        {u ? (
          <Meldung art="warn"><span data-testid="zurueck-warnung">Entfernt werden {zahl(u.patienten)} Akten mit {zahl(u.gewichte)} Gewichten, {zahl(u.kontakte)} Kontakten, {zahl(u.plaene)} Infusionsplänen
            und {zahl(u.dokumente)} Dokumenten – auch alles, was seit dem Import in diesen Akten erfasst wurde. Akten, die seither neu angelegt wurden,
            und Testpatienten bleiben.</span></Meldung>
        ) : null}
      </Bestaetigung>
    </div>
  );
}

// ---------------------------------------------------------------- 4 · Dokumente
function Dokumente({ stand }: { stand: Stand }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const d = useQuery({ queryKey: ["altimport", "dokumente"], queryFn: () => api<Dokumentenstand>("altimport/dokumente/") });
  const [laeuft, setLaeuft] = useState(false);
  const [fortschritt, setFortschritt] = useState<Etappe | null>(null);
  const [fehler, setFehler] = useState<unknown>(null);
  const anhalten = useRef(false);
  useEffect(() => () => { anhalten.current = true; }, []);
  const starten = async () => {
    anhalten.current = false;
    setLaeuft(true);
    setFehler(null);
    try {
      // Etappe für Etappe, bis nichts mehr offen ist; jede Etappe ist für sich gespeichert (fortsetzbar)
      for (;;) {
        const e = await api<Etappe>("altimport/dokumente/", { method: "POST" });
        setFortschritt(e);
        if (e.fertig || e.uebernommen === 0 || anhalten.current) {
          if (e.fertig) melden("Alle Dokumente sind übernommen.");
          break;
        }
      }
    } catch (f) {
      setFehler(f);
    } finally {
      setLaeuft(false);
      neuLaden(qc);
    }
  };
  const s = d.data;
  const gesamt = s ? s.erledigt + s.offen : 0;
  const erledigt = fortschritt ? fortschritt.erledigt : s?.erledigt ?? 0;
  const offen = fortschritt ? fortschritt.offen : s?.offen ?? 0;
  return (
    <div className="flex flex-col gap-5">
      <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="dokumente-karte">
        <KartenKopf titel="Dokumente des Altsystems"
          unter="Die Dateien kommen nicht über den Browser, sondern aus einem Ordner auf dem Server. Sie werden in die Akten kopiert; der Ordner bleibt unverändert."
          rechts={<Knopf klein icon="neustart" laedt={d.isFetching} onClick={() => { setFortschritt(null); void d.refetch(); }}>Neu einlesen</Knopf>} />
        {!s ? (d.error ? <Fehleranzeige fehler={d.error} /> : <Laden />) : !s.vorhanden ? (
          <Meldung art="warn"><span data-testid="dokumente-fehlen">Der Ordner <code>{s.pfad}</code> ist im Backend nicht vorhanden. Auf dem Server liegt er im Projektordner unter{" "}
            <code>data/import/PatData/</code> – darin je Patient ein Ordner mit der Patientennummer, z. B. <code>data/import/PatData/123/</code>.
            Die Dateien mit Zeitstempel kopieren (z. B. <code>rsync -a</code>), damit das Dateidatum als Dokumentdatum erhalten bleibt, und für die Gruppe 101 lesbar machen.</span></Meldung>
        ) : (
          <>
            <dl className="m-0 grid grid-cols-[220px_1fr] gap-x-3 gap-y-1.5 text-sm" data-testid="dokumente-stand">
              <dt className="gedaempft">Ordner im Backend</dt><dd className="m-0 num text-[0.8125rem]">{s.pfad}</dd>
              <dt className="gedaempft">Gefunden</dt><dd className="m-0">{zahl(s.ordner)} Patientenordner · {zahl(s.dateien)} Dateien · {dateigroesse(s.bytes)}</dd>
              <dt className="gedaempft">Übernommen</dt><dd className="m-0"><strong>{zahl(erledigt)}</strong>{stand.status === "importiert" ? ` von ${zahl(gesamt)}` : ""}</dd>
              <dt className="gedaempft">Noch offen</dt><dd className="m-0">{zahl(offen)}{s.offen_bytes ? ` · ${dateigroesse(fortschritt ? fortschritt.offen_bytes : s.offen_bytes)}` : ""}</dd>
              {s.frei_bytes != null ? <><dt className="gedaempft">Freier Speicher für Dokumente</dt><dd className="m-0">{dateigroesse(s.frei_bytes)}</dd></> : null}
            </dl>
            {stand.status === "importiert" && gesamt > 0 ? (
              <div className="h-2 rounded-full bg-fein overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={gesamt} aria-valuenow={erledigt}
                aria-label={`Dokumente: ${erledigt} von ${gesamt} übernommen`}>
                <div className="h-full bg-akzent rounded-full" style={{ width: `${Math.round((100 * erledigt) / gesamt)}%` }} />
              </div>
            ) : null}
            {stand.status !== "importiert" ? (
              <Meldung art="info">{stand.status === "abgeschlossen" ? "Die Übernahme ist abgeschlossen." : "Dokumente werden übernommen, nachdem die Altdaten importiert sind (Schritt 3)."}</Meldung>
            ) : (
              <div className="flex gap-2 items-center flex-wrap">
                <Knopf variante="pri" laedt={laeuft} disabled={laeuft || offen === 0} onClick={() => void starten()}>{erledigt ? "Übernahme fortsetzen" : "Dokumente übernehmen"}</Knopf>
                {laeuft ? <Knopf onClick={() => { anhalten.current = true; }}>Anhalten</Knopf> : null}
                {offen === 0 && gesamt > 0 ? <Chip art="ok"><Icon name="haken" />alle Dokumente übernommen</Chip> : null}
                <span className="text-[0.8125rem] gedaempft">Titel = Dateiname, Typ „Sonstiges“, Datum aus der Datei (PDF, EXIF) oder das Dateidatum; die Dokumente erscheinen unter „Nach und nach prüfen“.</span>
              </div>
            )}
            <Fehleranzeige fehler={fehler} />
          </>
        )}
      </Karte>
      {s?.vorhanden && (s.nicht_uebernommen_anzahl > 0 || s.ohne_patient_anzahl > 0) ? (
        <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="dokumente-nicht">
          <KartenKopf titel="Wird nicht übernommen" unter="Diese Dateien bleiben im Ordner auf dem Server. Bitte prüfen, bevor der Ordner später gelöscht wird." />
          {s.ohne_patient_anzahl > 0 ? (
            <div className="text-sm"><span className="font-medium">{zahl(s.ohne_patient_anzahl)} Ordner ohne übernommenen Patienten:</span>{" "}
              <span className="num text-[0.8125rem]">{s.ohne_patient.map((o) => `${o.ordner} (${o.dateien})`).join(", ")}{s.ohne_patient_anzahl > s.ohne_patient.length ? " …" : ""}</span></div>
          ) : null}
          {s.nicht_uebernommen_anzahl > 0 ? (
            <table className="tabelle">
              <thead><tr><th className="th">Datei ({zahl(s.nicht_uebernommen_anzahl)})</th><th className="th">Grund</th></tr></thead>
              <tbody>{s.nicht_uebernommen.map((n) => <tr key={n.pfad}><td className="td num text-[0.8125rem] break-all">{n.pfad}</td><td className="td text-[0.8125rem]">{n.grund}</td></tr>)}</tbody>
            </table>
          ) : null}
        </Karte>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- 5 · Abschließen
function Abschluss({ stand }: { stand: Stand }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [dialog, setDialog] = useState(false);
  const [ohne, setOhne] = useState(false);
  const d = useQuery({ queryKey: ["altimport", "dokumente"], queryFn: () => api<Dokumentenstand>("altimport/dokumente/"), enabled: stand.status === "importiert" });
  const offen = d.data?.vorhanden ? d.data.offen : 0;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="abschluss-karte">
      <KartenKopf titel="Übernahme abschließen (Go-live)" unter="Der letzte Schritt, wenn die übernommenen Akten geprüft sind und das EPM das Altsystem ablöst." />
      {stand.status === "abgeschlossen" ? (
        <Meldung art="ok"><span data-testid="abgeschlossen">Abgeschlossen am {zeitpunkt(stand.abgeschlossen_am)}{stand.abgeschlossen_von ? ` von ${stand.abgeschlossen_von}` : ""}. Der Dump und die Zuordnungen sind gelöscht; die Protokolle enthalten nur noch die Zählungen.</span></Meldung>
      ) : (
        <>
          <ul className="m-0 pl-5 text-sm leading-relaxed">
            <li>Das <strong>Zurücknehmen</strong> ist danach nicht mehr möglich – die übernommenen Akten sind dann Akten wie alle anderen.</li>
            <li>Der <strong>Dump</strong> (mit den Daten aller Patienten, auch der nicht übernommenen) und die <strong>Zuordnungen</strong> werden gelöscht.</li>
            <li>Die <strong>Protokolle</strong> behalten die Zählungen und verlieren die einzelnen Nummern. Wer sie aufbewahren will, lädt sie vorher als Textdatei herunter (Protokolle).</li>
            <li>Der Dokumentenordner auf dem Server und ältere Sicherungen aus der Testphase enthalten weiterhin Altdaten – bitte getrennt löschen.</li>
          </ul>
          {stand.status !== "importiert" ? <Meldung art="info">Abschließen ist erst möglich, wenn die Altdaten übernommen sind (Schritt 3).</Meldung> : null}
          {stand.status === "importiert" && offen > 0 ? (
            <Meldung art="warn">Es sind noch {zahl(offen)} Dokumente nicht übernommen (Schritt 4).
              <label className="flex items-center gap-2 mt-1.5"><input type="checkbox" checked={ohne} onChange={(e) => setOhne(e.target.checked)} />
                Trotzdem abschließen – die offenen Dokumente werden nicht mehr übernommen</label></Meldung>
          ) : null}
          <div><Knopf variante="dng" disabled={stand.status !== "importiert" || (offen > 0 && !ohne)} onClick={() => setDialog(true)}>Übernahme abschließen …</Knopf></div>
        </>
      )}
      <Bestaetigung offen={dialog} onZu={() => setDialog(false)} titel="Übernahme abschließen" wort="ABSCHLIESSEN" knopf="Bestätigen und abschließen"
        pfad="altimport/abschliessen/" zusatz={{ ohne_dokumente: ohne }}
        beschreibung="Danach lässt sich die Übernahme nicht mehr zurücknehmen. Der Dump und die Zuordnungen werden gelöscht."
        onFertig={() => { neuLaden(qc); melden("Übernahme abgeschlossen."); }} />
    </Karte>
  );
}

// ---------------------------------------------------------------- Protokolle
function Protokolle({ stand }: { stand: Stand }) {
  const [auf, setAuf] = useState<number | null>(null);
  const lauf = useQuery({ queryKey: ["altimport", "lauf", auf], queryFn: () => api<Lauf>(`altimport/laeufe/${auf}/`), enabled: auf !== null });
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="laeufe">
      <KartenKopf titel="Läufe" unter="Die letzten 30 Probeläufe, Importe und weiteren Schritte – jeder Import, jedes Zurücknehmen und das Abschließen stehen auch im Audit-Log (Gruppe „System“)." />
      {stand.laeufe.length === 0 ? <Leer>Noch keine Läufe.</Leer> : (
        <table className="tabelle">
          <thead><tr><th className="th">Zeit</th><th className="th">Schritt</th><th className="th">Person</th><th className="th">Dump</th><th className="th">Ergebnis</th><th className="th" /></tr></thead>
          <tbody>
            {stand.laeufe.map((l) => (
              <tr key={l.id} data-testid="lauf" className={auf === l.id ? "gewaehlt" : undefined}>
                <td className="td num whitespace-nowrap text-[0.8125rem]">{zeitpunkt(l.begonnen_am)}</td>
                <td className="td font-medium">{l.art_name}</td>
                <td className="td text-[0.8125rem]">{l.person ?? "—"}</td>
                <td className="td text-[0.8125rem]">{l.dump_name || "—"}</td>
                <td className="td">{l.erfolgreich ? <Chip art="ok">erfolgreich</Chip> : l.beendet_am ? <Chip art="fehler">nicht erfolgreich</Chip> : <Chip art="warn">läuft</Chip>}</td>
                <td className="td text-right"><Knopf klein variante="geist" aria-expanded={auf === l.id} onClick={() => setAuf(auf === l.id ? null : l.id)}>{auf === l.id ? "Schließen" : "Ansehen"}</Knopf></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {auf !== null ? (lauf.data ? <LaufErgebnis lauf={lauf.data} /> : lauf.error ? <Fehleranzeige fehler={lauf.error} /> : <Laden />) : null}
    </Karte>
  );
}

// ---------------------------------------------------------------- Seite
export function Import() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const schritt = (SCHRITTE.some((s) => s.wert === params.get("schritt")) ? params.get("schritt") : "quelle") as Schritt;
  const stand = useQuery({ queryKey: ["altimport", "stand"], queryFn: () => api<Stand>("altimport/") });
  const geladen = stand.data?.status === "geladen";
  const zuordnung = useQuery({ queryKey: ["altimport", "zuordnung"], queryFn: () => api<Zuordnung>("altimport/zuordnung/"),
    enabled: geladen && (schritt === "zuordnungen" || schritt === "import") });
  const speichern = useMutation({
    mutationFn: (a: Aenderung) => api<Zuordnung>("altimport/zuordnung/", { method: "PATCH", body: a }),
    onSuccess: (z) => qc.setQueryData(["altimport", "zuordnung"], z),
  });
  const s = stand.data;
  const pfad = [{ text: "Administration" }, { text: "Import" }];
  if (!s) {
    return <Seite pfad={pfad}><Seitenkopf titel="Import" />{stand.error ? <Fehleranzeige fehler={stand.error} /> : <Laden />}</Seite>;
  }
  const art = s.status === "importiert" ? "akzent" : s.status === "abgeschlossen" ? "ok" : s.status === "geladen" ? "warn" : "neutral";
  return (
    <Seite pfad={pfad}>
      <Seitenkopf titel="Import" unter="Übernahme der Altdaten aus dem bisherigen System. Nur für die Administration."
        rechts={<Chip art={art} data-testid="import-status">{s.status_name}</Chip>} />
      {s.echte_akten.anzahl > 0 && (s.status === "leer" || s.status === "geladen") ? (
        <Meldung art="warn"><span data-testid="echte-akten">Im EPM gibt es {zahl(s.echte_akten.anzahl)} echte Akten (Nr. {s.echte_akten.nummern.join(", ")}{s.echte_akten.anzahl > s.echte_akten.nummern.length ? " …" : ""}).
          Übernommen wird nur in ein System ohne echte Akten, weil die Patientennummern des Altsystems frei sein müssen. Zuordnungen lassen sich trotzdem vorbereiten.</span></Meldung>
      ) : null}
      <Segmente label="Schritte der Übernahme" wert={schritt} onWahl={(w) => setParams(w === "quelle" ? new URLSearchParams() : new URLSearchParams({ schritt: w }), { replace: true })}
        werte={SCHRITTE} className="self-start flex-wrap" />
      {schritt === "quelle" ? <Quelle stand={s} /> : null}
      {schritt === "zuordnungen" ? (
        s.status === "geladen" ? (
          zuordnung.data?.stand ? (
            <Zuordnungen daten={zuordnung.data} speichern={(a) => speichern.mutate(a)} laeuft={speichern.isPending}
              fehler={speichern.error ? <Fehleranzeige fehler={speichern.error} /> : null} />
          ) : zuordnung.error ? <Fehleranzeige fehler={zuordnung.error} /> : <Laden text="Dump wird ausgewertet …" />
        ) : (
          <Meldung art="info"><span data-testid="zuordnungen-gesperrt">{s.status === "leer" ? "Zuerst unter „1 · Dump“ einen Dump laden. Gespeicherte Zuordnungen bleiben erhalten und gelten für den nächsten Dump."
            : s.status === "importiert" ? "Die Zuordnungen sind gesperrt, solange die Altdaten übernommen sind. Zum Ändern den Import zurücknehmen (Schritt 3)."
            : "Die Übernahme ist abgeschlossen; die Zuordnungen wurden gelöscht."}</span></Meldung>
        )
      ) : null}
      {schritt === "import" ? <ImportSchritt stand={s} zuordnung={geladen ? zuordnung.data : undefined} /> : null}
      {schritt === "dokumente" ? <Dokumente stand={s} /> : null}
      {schritt === "abschluss" ? <Abschluss stand={s} /> : null}
      {schritt === "protokolle" ? <Protokolle stand={s} /> : null}
    </Seite>
  );
}
