/**
 * KI (Experimentell) › Prüfansicht eines Dokuments (Auftrag 5): links das Original, rechts was die KI erkannt hat.
 *
 * Sicherheitsprinzip: Nichts geht ohne aktive Bestätigung in die Akte. Jedes Feld zeigt, ob es **neu** wäre, etwas
 * **ergänzt**, etwas **überschreiben** würde oder schon **vorhanden** ist, dazu **unsichere** Erkennung und niedrige
 * OCR-Sicherheit. Bei Konflikten entscheidet der Mitarbeiter je Feld (neu anlegen / ergänzen / ersetzen / verwerfen).
 */
import { Fragment, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { datum, zeitpunkt } from "@/lib/format";
import {
  AKTION_TEXT, DOKUMENTTYPEN, ENTSCHEIDUNG_TEXT, FEHLERARTEN, FELD_ANGABEN, STATUS_ART, feldText, prozentText,
} from "@/lib/ki";
import type { KiEntscheidung, KiFeld, KiFeldGruppe, KiVorgang, KiVorschau } from "@/lib/ki";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Seitenkopf, Textfeld, cx,
} from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Reiter, ReiterInhalt } from "@/components/ui/reiter";
import { PdfLeser } from "@/components/PdfAnsicht";
import { Seite } from "@/components/layout/Shell";

const GRUPPEN: { wert: KiFeldGruppe; text: string }[] = [
  { wert: "meta", text: "Dokument" }, { wert: "labor", text: "Laborwerte" }, { wert: "infusion", text: "Infusionsplan" },
  { wert: "medikation", text: "Medikation" }, { wert: "diagnose", text: "Diagnosen" }, { wert: "text", text: "Texte" },
];
const IN_ARBEIT = ["neu", "in_verarbeitung", "ocr_fertig", "analyse_fertig"];
const AKTION_ART: Record<KiVorschau["aktion"], "ok" | "warn" | "fehler" | "akzent" | "neutral"> = {
  neu: "ok", ergaenzen: "akzent", ueberschreiben: "warn", identisch: "neutral", konflikt: "fehler", nur_info: "neutral",
};
const OCR_SCHWACH = 0.85;

export function KiPruefung() {
  const { id } = useParams();
  const qc = useQueryClient();
  const melden = useHinweis();
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ["ki", "vorgang", id],
    queryFn: () => api<KiVorgang>(`ki/vorgaenge/${id}/`),
    refetchInterval: (abfrage) => (IN_ARBEIT.includes(abfrage.state.data?.status ?? "") ? 5000 : false),
  });
  const v = q.data;
  const [ansicht, setAnsicht] = useState<"original" | "text" | "zusammenfassung">("original");
  const [gewaehlt, setGewaehlt] = useState<number[]>([]);
  const [bearbeiten, setBearbeiten] = useState<KiFeld | null>(null);
  const [uebernehmen, setUebernehmen] = useState(false);
  const [ablehnen, setAblehnen] = useState(false);
  const [konflikte, setKonflikte] = useState<number[]>([]);
  const neu = () => { void qc.invalidateQueries({ queryKey: ["ki"] }); };
  const vorschau = useMemo(() => new Map((v?.vorschau ?? []).map((x) => [x.feld, x])), [v]);
  const schwacheSeiten = new Set((v?.seiten_liste ?? []).filter((s) => s.konfidenz !== null && s.konfidenz < OCR_SCHWACH).map((s) => s.nr));
  const pruefbar = !!v && ["zur_pruefung", "teilweise"].includes(v.status);
  const darfPruefen = !!v?.rechte.ki_pruefen && pruefbar;

  const status = useMutation({
    mutationFn: (d: { felder?: number[]; alle?: boolean; status: string }) => api<{ geaendert: number }>(`ki/vorgaenge/${id}/freigeben/`, { body: d }),
    onSuccess: (r, d) => { setGewaehlt([]); neu(); melden(`${r.geaendert} Feld${r.geaendert === 1 ? "" : "er"} ${d.status === "freigegeben" ? "freigegeben" : d.status === "verworfen" ? "verworfen" : "wieder offen"}.`); },
  });
  const entscheiden = useMutation({
    mutationFn: ({ feld, entscheidung }: { feld: number; entscheidung: KiEntscheidung }) =>
      api(`ki/vorgaenge/${id}/felder/${feld}/`, { method: "PATCH", body: { entscheidung } }),
    onSuccess: neu,
  });
  const erneut = useMutation({
    mutationFn: () => api(`ki/vorgaenge/${id}/erneut/`, { body: {} }),
    onSuccess: () => { neu(); melden("Wird erneut verarbeitet – angefordert, läuft auch tagsüber."); },
  });

  if (q.isLoading) return <Seite pfad={[{ text: "KI (Experimentell)", zu: "/ki" }, { text: "Prüfung" }]}><Laden /></Seite>;
  if (!v) return <Seite pfad={[{ text: "KI (Experimentell)", zu: "/ki" }, { text: "Prüfung" }]}><Fehleranzeige fehler={q.error} /></Seite>;

  const offeneFelder = v.felder.filter((f) => f.status === "offen" || f.status === "freigegeben");
  const freigegeben = v.felder.filter((f) => f.status === "freigegeben" && vorschau.get(f.id)?.aktion !== "nur_info");
  const dateiUrl = `/api/dokumente/${v.dokument}/datei/?anzeigen=1`;

  return (
    <Seite pfad={[{ text: "KI (Experimentell)", zu: "/ki" }, { text: v.dokument_titel }]}>
      <Seitenkopf titel={v.dokument_titel}
        unter={<>Akte <Link to={`/patienten/${v.patient}/ki`}>{v.patient_name} ({v.patient_nummer})</Link>
          {v.dokument_datum ? ` · Dokument vom ${datum(v.dokument_datum)}` : ""}{v.firma_name ? ` · ${v.firma_name}` : ""}</>}
        rechts={<>
          <Chip art={STATUS_ART[v.status]} data-testid="ki-status">{v.status_name}</Chip>
          {v.rechte.ki_pruefen && !IN_ARBEIT.includes(v.status) ? (
            <Knopf klein icon="neustart" laedt={erneut.isPending} onClick={() => erneut.mutate()}>Erneut verarbeiten</Knopf>) : null}
          {darfPruefen ? <Knopf klein variante="dng" onClick={() => setAblehnen(true)}>Ablehnen …</Knopf> : null}
        </>} />
      <Meldung art="warn" className="flex gap-2.5 items-start text-[0.8125rem]">
        <Icon name="warnung" />
        <span><strong>KI (Experimentell):</strong> Das sind Vorschläge, keine Inhalte der Akte. Bitte jeden Wert mit dem Original
          vergleichen. In die Akte kommt nur, was Sie freigeben und mit „In die Akte übernehmen“ ausdrücklich bestätigen.</span>
      </Meldung>
      {IN_ARBEIT.includes(v.status) ? <Meldung>Wird verarbeitet{v.schritt ? `: ${v.schritt}` : ""} ({v.fortschritt} %).</Meldung> : null}
      {v.fehler ? <Meldung art="fehler">{v.fehler}</Meldung> : null}
      {typeof v.metadaten?.hinweis === "string" ? <Meldung art="warn">{v.metadaten.hinweis as string}</Meldung> : null}
      {v.ablehnungsgrund ? <Meldung>Abgelehnt von {v.geprueft_von_name}: {v.ablehnungsgrund}</Meldung> : null}

      <div className="grid gap-4 xl:grid-cols-2 items-start">
        <Karte className="flex flex-col gap-3 min-w-0">
          <Reiter label="Ansicht" wert={ansicht} onWahl={setAnsicht} eintraege={[
            { wert: "original", text: "Original" }, { wert: "text", text: "Erkannter Text" },
            { wert: "zusammenfassung", text: "Zusammenfassung" }]} />
          <ReiterInhalt>
            {ansicht === "original" ? (v.dokument_mime === "application/pdf"
              ? <PdfLeser url={dateiUrl} className="h-[70vh]" />
              : <img src={dateiUrl} alt={`Original ${v.dokument_titel}`} className="max-w-full rounded-lg border border-rand" />) : null}
            {ansicht === "text" ? (
              <div className="flex flex-col gap-3 max-h-[70vh] overflow-auto" tabIndex={0} role="region" aria-label="Erkannter Text">
                {v.seiten_liste.map((s) => (
                  <div key={s.nr} className="flex flex-col gap-1">
                    <div className="text-xs gedaempft">Seite {s.nr} · OCR-Sicherheit {prozentText(s.konfidenz)} · {s.verfahren.join(", ")}
                      {s.konfidenz !== null && s.konfidenz < OCR_SCHWACH ? <Chip art="warn" className="ml-2">niedrige OCR-Sicherheit</Chip> : null}</div>
                    <pre className="m-0 whitespace-pre-wrap text-[0.8125rem] font-mono bg-fein rounded p-2">{s.text || "—"}</pre>
                    {s.vision_text ? <>
                      <div className="text-xs gedaempft">Seite {s.nr} · vom KI-Modell gelesen</div>
                      <pre className="m-0 whitespace-pre-wrap text-[0.8125rem] font-mono bg-fein rounded p-2">{s.vision_text}</pre>
                    </> : null}
                  </div>
                ))}
                {!v.seiten_liste.length ? <Leer>Noch kein Text erkannt.</Leer> : null}
              </div>) : null}
            {ansicht === "zusammenfassung" ? (
              <div className="flex flex-col gap-2 text-sm">
                <p className="m-0 whitespace-pre-line">{v.zusammenfassung || "Keine Zusammenfassung."}</p>
                <dl className="m-0 text-[0.8125rem] gedaempft grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                  <dt>Dokumenttyp</dt><dd className="m-0">{DOKUMENTTYPEN[v.dokumenttyp] ?? "—"} ({prozentText(v.typ_konfidenz)})</dd>
                  <dt>OCR-Sicherheit</dt><dd className="m-0">{prozentText(v.ocr_konfidenz)} im Mittel, {v.seiten} Seite{v.seiten === 1 ? "" : "n"}</dd>
                  <dt>Verfahren</dt><dd className="m-0">{v.verfahren.join(", ") || "—"}</dd>
                  <dt>Modell</dt><dd className="m-0">{v.modell ? `${v.modell.name} (${v.modell.sha256.slice(0, 12)})` : "keins (nur Regeln)"}{v.prompt_version ? ` · Prompt ${v.prompt_version}` : ""}</dd>
                  <dt>Verarbeitet</dt><dd className="m-0">{v.fertig_am ? zeitpunkt(v.fertig_am) : "—"}{v.dauer_s ? ` in ${Math.round(v.dauer_s)} s` : ""}</dd>
                  {v.uebernahmen.map((u, i) => (
                    <Fragment key={i}><dt>Übernommen</dt><dd className="m-0">{zeitpunkt(u.zeitpunkt)} von {u.benutzer} ({u.felder} Felder)</dd></Fragment>))}
                </dl>
              </div>) : null}
          </ReiterInhalt>
        </Karte>

        <div className="flex flex-col gap-3 min-w-0" data-testid="ki-felder">
          {GRUPPEN.map((g) => {
            const felder = v.felder.filter((f) => f.gruppe === g.wert);
            if (!felder.length) return null;
            return (
              <Karte key={g.wert} className="flex flex-col gap-2">
                <KartenKopf titel={g.text} unter={`${felder.length} Vorschl${felder.length === 1 ? "ag" : "äge"}`} />
                <ul className="m-0 p-0 list-none flex flex-col divide-y divide-rand">
                  {felder.map((f) => (
                    <FeldZeile key={f.id} f={f} vorschau={vorschau.get(f.id)} schwach={!!f.belege.seite && schwacheSeiten.has(f.belege.seite)}
                      darf={darfPruefen} gewaehlt={gewaehlt.includes(f.id)} konflikt={konflikte.includes(f.id)}
                      onWahl={(an) => setGewaehlt(an ? [...gewaehlt, f.id] : gewaehlt.filter((x) => x !== f.id))}
                      onBearbeiten={() => setBearbeiten(f)}
                      onStatus={(s) => status.mutate({ felder: [f.id], status: s })}
                      onEntscheidung={(e) => entscheiden.mutate({ feld: f.id, entscheidung: e })} />
                  ))}
                </ul>
              </Karte>
            );
          })}
          {!v.felder.length && !IN_ARBEIT.includes(v.status) ? <Karte><Leer>Keine Vorschläge.</Leer></Karte> : null}
          <Fehleranzeige fehler={status.error ?? entscheiden.error ?? erneut.error} />
          {darfPruefen ? (
            <div className="sticky bottom-2 card flex items-center gap-2 flex-wrap p-3" data-testid="ki-aktionen">
              <Knopf disabled={!gewaehlt.length} onClick={() => status.mutate({ felder: gewaehlt, status: "freigegeben" })}>
                Ausgewählte freigeben ({gewaehlt.length})</Knopf>
              <Knopf disabled={!gewaehlt.length} variante="geist" onClick={() => status.mutate({ felder: gewaehlt, status: "verworfen" })}>Verwerfen</Knopf>
              <Knopf variante="geist" disabled={!offeneFelder.length} onClick={() => status.mutate({ alle: true, status: "freigegeben" })}
                title="Gibt alle sicher erkannten Felder frei – unsichere bleiben offen">Alle sicheren freigeben</Knopf>
              <span className="flex-1" />
              {v.rechte.ki_uebernehmen ? (
                <Knopf variante="pri" icon="haken" disabled={!freigegeben.length} onClick={() => setUebernehmen(true)} data-testid="ki-uebernehmen">
                  In die Akte übernehmen … ({freigegeben.length})</Knopf>) : null}
            </div>) : null}
        </div>
      </div>
      {bearbeiten ? <FeldDialog vorgang={v.id} feld={bearbeiten} onZu={() => setBearbeiten(null)} onFertig={neu} /> : null}
      <UebernahmeDialog offen={uebernehmen} onOffen={setUebernehmen} vorgang={v} felder={freigegeben} vorschau={vorschau}
        onKonflikte={setKonflikte} onFertig={(stand) => { neu(); melden("In die Akte übernommen."); if (stand === "uebernommen") navigate("/ki"); }} />
      <AblehnenDialog offen={ablehnen} onOffen={setAblehnen} vorgang={v.id} onFertig={() => { neu(); navigate("/ki"); }} />
    </Seite>
  );
}

function FeldZeile({ f, vorschau, schwach, darf, gewaehlt, konflikt, onWahl, onBearbeiten, onStatus, onEntscheidung }: {
  f: KiFeld; vorschau?: KiVorschau; schwach: boolean; darf: boolean; gewaehlt: boolean; konflikt: boolean;
  onWahl: (an: boolean) => void; onBearbeiten: () => void; onStatus: (s: string) => void; onEntscheidung: (e: KiEntscheidung) => void;
}) {
  const { titel, wert } = feldText(f);
  const aktiv = f.status === "offen" || f.status === "freigegeben";
  const bestehend = vorschau?.bestehend as Record<string, unknown> | null | undefined;
  return (
    <li className={cx("py-2.5 flex flex-col gap-1.5", f.status === "verworfen" && "opacity-55", konflikt && "bg-warn-bg")}
      data-testid={`ki-feld-${f.id}`}>
      <div className="flex items-start gap-2.5">
        {darf && aktiv && vorschau?.aktion !== "nur_info" ? (
          <input type="checkbox" className="mt-1" aria-label={`${titel} auswählen`} checked={gewaehlt} onChange={(e) => onWahl(e.target.checked)} />
        ) : <span className="w-[0.8125rem]" aria-hidden="true" />}
        <div className="flex flex-col gap-0.5 min-w-0 flex-1">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="font-medium text-sm">{titel}</span>
            <span className="text-sm num break-words">{wert || "—"}</span>
          </div>
          <div className="flex items-center gap-1.5 flex-wrap text-[0.75rem]">
            <Chip art={f.status === "freigegeben" ? "ok" : f.status === "uebernommen" ? "ok" : f.status === "verworfen" ? "neutral" : undefined}>{f.status_name}</Chip>
            {vorschau && aktiv ? <Chip art={AKTION_ART[vorschau.aktion]}>{AKTION_TEXT[vorschau.aktion]}</Chip> : null}
            {f.unsicher ? <Chip art="warn">unsicher erkannt ({prozentText(f.konfidenz)})</Chip>
              : f.konfidenz !== null ? <span className="gedaempft">Sicherheit {prozentText(f.konfidenz)}</span> : null}
            {schwach ? <Chip art="warn">niedrige OCR-Sicherheit</Chip> : null}
            {f.korrigiert ? <Chip art="akzent">korrigiert{f.korrekturen > 1 ? ` (${f.korrekturen}×)` : ""}</Chip> : null}
            <span className="gedaempft">{{ vision: "KI-Modell", regeln: "Regeln", "vision+regeln": "KI-Modell + Regeln", ocr: "Texterkennung" }[f.quelle] ?? f.quelle}
              {f.belege.seite ? ` · Seite ${f.belege.seite}` : ""}</span>
          </div>
          {bestehend && vorschau && ["ueberschreiben", "identisch", "konflikt", "ergaenzen"].includes(vorschau.aktion) ? (
            <div className="text-[0.75rem] gedaempft">In der Akte: {Object.entries(bestehend).filter(([k]) => !["modell", "id", "befund"].includes(k))
              .map(([k, w]) => `${k} ${w ?? "—"}`).join(" · ")}</div>) : null}
          {(f.belege.hinweise ?? []).length ? (
            <ul className="m-0 pl-4 text-[0.75rem] gedaempft">{(f.belege.hinweise ?? []).map((h, i) => <li key={i}>{h}</li>)}</ul>) : null}
          {vorschau?.fehler && aktiv ? <div className="text-[0.75rem] fehlertext">{vorschau.fehler}</div> : null}
          {darf && aktiv && vorschau?.optionen.length ? (
            <label className="flex items-center gap-2 text-[0.8125rem]">
              <span className={cx(!f.entscheidung && "font-medium")}>Entscheidung{!f.entscheidung ? " nötig" : ""}:</span>
              <Auswahl className="h-8 w-auto" value={f.entscheidung} onChange={(e) => onEntscheidung(e.target.value as KiEntscheidung)}
                aria-label={`Entscheidung für ${titel}`}>
                <option value="">– bitte wählen –</option>
                {vorschau.optionen.filter(Boolean).map((o) => <option key={o} value={o}>{ENTSCHEIDUNG_TEXT[o as Exclude<KiEntscheidung, "">]}</option>)}
              </Auswahl>
            </label>) : null}
        </div>
        {darf && aktiv ? (
          <div className="flex items-center gap-1 shrink-0">
            <Knopf klein variante="geist" icon="stift" aria-label={`${titel} bearbeiten`} onClick={onBearbeiten} />
            {f.status === "offen"
              ? <Knopf klein variante="geist" icon="haken" aria-label={`${titel} freigeben`} onClick={() => onStatus("freigegeben")} />
              : <Knopf klein variante="geist" icon="zurueck" aria-label={`${titel} wieder offen`} onClick={() => onStatus("offen")} />}
            <Knopf klein variante="geist" icon="x" aria-label={`${titel} verwerfen`} onClick={() => onStatus("verworfen")} />
          </div>) : null}
      </div>
    </li>
  );
}

function FeldDialog({ vorgang, feld, onZu, onFertig }: { vorgang: number; feld: KiFeld; onZu: () => void; onFertig: () => void }) {
  const angaben = FELD_ANGABEN[feld.gruppe];
  const [werte, setWerte] = useState<Record<string, string>>(() => Object.fromEntries(angaben.map((a) => {
    const w = feld.endwert[a.name];
    return [a.name, w === null || w === undefined ? "" : String(w)];
  })));
  const [fehlerart, setFehlerart] = useState("lesefehler");
  const [kommentar, setKommentar] = useState("");
  const speichern = useMutation({
    mutationFn: () => {
      const neu: Record<string, string | null> = {};
      const zahlen = feld.gruppe === "labor" ? ["wert", "referenz_von", "referenz_bis"] : feld.gruppe === "infusion" ? ["menge"] : [];
      for (const a of angaben) {
        const alt = feld.endwert[a.name];
        const altText = alt === null || alt === undefined ? "" : String(alt);
        if (werte[a.name] === altText) continue;
        // Zahlen mit Punkt speichern (3,1 → 3.1); den Parameter ordnet der Server dem Laborkatalog neu zu
        neu[a.name] = werte[a.name] === "" ? null : zahlen.includes(a.name) ? werte[a.name].replace(",", ".") : werte[a.name];
      }
      return api(`ki/vorgaenge/${vorgang}/felder/${feld.id}/`, { method: "PATCH", body: { wert: neu, fehlerart, kommentar } });
    },
    onSuccess: () => { onFertig(); onZu(); },
  });
  const { titel } = feldText(feld);
  const istTyp = feld.gruppe === "meta" && feld.schluessel === "dokumenttyp";
  const fehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel={`${titel} korrigieren`} breite={620}
      beschreibung="Der Vorschlag der KI bleibt erhalten; Ihre Korrektur wird mit Fehlerart versioniert gespeichert (Qualitäts-Dashboard)."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf><Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        {angaben.map((a) => (
          <Feld key={a.name} label={a.text} className={cx(a.breit && "sm:col-span-2")} fehler={fehler[`wert.${a.name}`]}>
            {(p) => istTyp ? (
              <Auswahl {...p} value={werte.wert} onChange={(e) => setWerte({ ...werte, wert: e.target.value })}>
                {Object.entries(DOKUMENTTYPEN).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
              </Auswahl>
            ) : a.auswahl ? (
              <Auswahl {...p} value={werte[a.name]} onChange={(e) => setWerte({ ...werte, [a.name]: e.target.value })}>
                {Object.entries(a.auswahl).map(([k, t]) => <option key={k} value={k}>{t}</option>)}
              </Auswahl>
            ) : a.breit && feld.gruppe === "text" ? (
              <Textfeld {...p} rows={6} value={werte[a.name]} onChange={(e) => setWerte({ ...werte, [a.name]: e.target.value })} />
            ) : (
              <Eingabe {...p} value={werte[a.name]} onChange={(e) => setWerte({ ...werte, [a.name]: e.target.value })} />
            )}
          </Feld>
        ))}
        <Feld label="Fehlerart">
          {(p) => <Auswahl {...p} value={fehlerart} onChange={(e) => setFehlerart(e.target.value)}>
            {Object.entries(FEHLERARTEN).map(([k, t]) => <option key={k} value={k}>{t}</option>)}</Auswahl>}
        </Feld>
        <Feld label="Kommentar (freiwillig)">{(p) => <Eingabe {...p} value={kommentar} maxLength={300} onChange={(e) => setKommentar(e.target.value)} />}</Feld>
      </div>
      <Fehleranzeige fehler={speichern.error} />
    </Dialog>
  );
}

function UebernahmeDialog({ offen, onOffen, vorgang, felder, vorschau, onKonflikte, onFertig }: {
  offen: boolean; onOffen: (o: boolean) => void; vorgang: KiVorgang; felder: KiFeld[]; vorschau: Map<number, KiVorschau>;
  onKonflikte: (ids: number[]) => void; onFertig: (status: string) => void;
}) {
  const [geprueft, setGeprueft] = useState(false);
  const fehlend = felder.filter((f) => {
    const v = vorschau.get(f.id);
    return v && v.optionen.length > 0 && !v.optionen.includes(f.entscheidung);
  });
  const mit_fehler = felder.filter((f) => vorschau.get(f.id)?.fehler);
  const los = useMutation({
    mutationFn: () => api<{ status: string }>(`ki/vorgaenge/${vorgang.id}/uebernehmen/`, {
      body: { felder: felder.map((f) => f.id), bestaetigt: true,
        entscheidungen: Object.fromEntries(felder.filter((f) => f.entscheidung).map((f) => [String(f.id), f.entscheidung])) },
    }),
    onSuccess: (r) => { onKonflikte([]); setGeprueft(false); onOffen(false); onFertig(r.status); },
    onError: (e) => {
      if (e instanceof ApiFehler && e.status === 409) {
        const k = (e.daten as { konflikte?: KiVorschau[] }).konflikte ?? [];
        onKonflikte(k.map((x) => x.feld));
      }
    },
  });
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="In die Akte übernehmen" breite={720}
      beschreibung={`${vorgang.patient_name} (${vorgang.patient_nummer}) · ${vorgang.dokument_titel}`}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" icon="haken" laedt={los.isPending} disabled={!geprueft || fehlend.length > 0 || mit_fehler.length > 0}
          onClick={() => los.mutate()} data-testid="ki-uebernehmen-bestaetigen">In die Akte übernehmen</Knopf>
      </>}>
      <table className="tabelle text-sm">
        <thead><tr><th className="th">Feld</th><th className="th">Wert</th><th className="th">Wirkung</th></tr></thead>
        <tbody>
          {felder.map((f) => {
            const v = vorschau.get(f.id);
            const { titel, wert } = feldText(f);
            return (
              <tr key={f.id}>
                <td className="td">{titel}{f.unsicher ? <Chip art="warn" className="ml-1.5">unsicher</Chip> : null}</td>
                <td className="td num">{wert}</td>
                <td className="td">
                  {v ? <Chip art={AKTION_ART[v.aktion]}>{AKTION_TEXT[v.aktion]}</Chip> : null}
                  {f.entscheidung ? <span className="ml-1.5 text-[0.75rem]">→ {ENTSCHEIDUNG_TEXT[f.entscheidung as Exclude<KiEntscheidung, "">]}</span> : null}
                  {v?.fehler ? <div className="fehlertext text-[0.75rem]">{v.fehler}</div> : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {fehlend.length ? <Meldung art="warn">Für {fehlend.length} Feld{fehlend.length === 1 ? "" : "er"} mit Konflikt fehlt die Entscheidung
        (neu anlegen, ergänzen, ersetzen oder verwerfen). Es wird nichts automatisch überschrieben.</Meldung> : null}
      {mit_fehler.length ? <Meldung art="warn">Bitte zuerst die markierten Felder korrigieren.</Meldung> : null}
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" checked={geprueft} onChange={(e) => setGeprueft(e.target.checked)} data-testid="ki-geprueft" />
        <span>Ich habe die Werte mit dem Original verglichen und übernehme sie in die Akte. Die Übernahme steht mit meinem Namen im
          Verlauf der Akte und im Audit-Log.</span>
      </label>
      <Fehleranzeige fehler={los.error} />
    </Dialog>
  );
}

function AblehnenDialog({ offen, onOffen, vorgang, onFertig }: { offen: boolean; onOffen: (o: boolean) => void; vorgang: number; onFertig: () => void }) {
  const [grund, setGrund] = useState("");
  const los = useMutation({
    mutationFn: () => api(`ki/vorgaenge/${vorgang}/ablehnen/`, { body: { grund } }),
    onSuccess: () => { onOffen(false); onFertig(); },
  });
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Vorschläge ablehnen"
      beschreibung="Alle offenen Vorschläge dieses Dokuments werden verworfen. Das Dokument in der Akte bleibt unverändert."
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="dng" disabled={!grund.trim()} laedt={los.isPending} onClick={() => los.mutate()}>Ablehnen</Knopf></>}>
      <Feld label="Grund" pflicht>{(p) => <Textfeld {...p} rows={3} value={grund} onChange={(e) => setGrund(e.target.value)} />}</Feld>
      <Fehleranzeige fehler={los.error} />
    </Dialog>
  );
}
