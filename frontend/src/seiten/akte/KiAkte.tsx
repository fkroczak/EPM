/**
 * Akte › KI (Experimentell): historische Zusammenhänge Labor ↔ Infusionsplan (Auftrag 4), Dokumente dieses Patienten
 * in der KI-Verarbeitung und Berichtsentwürfe auf ausdrückliche Anforderung (Auftrag 6).
 *
 * Alles hier ist Entscheidungshilfe – keine medizinische Bewertung, Diagnose oder Empfehlung. In die Akte kommt nur,
 * was ein Mitarbeiter prüft und bestätigt.
 */
import { useState } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { abfrage, alle, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, zeitpunkt } from "@/lib/format";
import { STATUS_ART, STATUS_TEXT } from "@/lib/ki";
import type { KiBericht, KiHinweis, KiVorgangKurz } from "@/lib/ki";
import type { Dokument } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Textfeld, cx,
} from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { useAkte } from "./Akte";

const QUELLEN: Record<string, string> = {
  labor: "Laborbefunde", infusion: "Infusionspläne", medikation: "Medikamente", diagnosen: "Diagnosen", verlauf: "Verlauf, Kontakte",
};
const QUELLEN_JE_ART: Record<KiBericht["art"], string[]> = {
  labor: ["labor"], infusion: ["infusion", "medikation"], verlauf: ["diagnosen", "verlauf", "labor", "infusion", "medikation"],
};
const LESBAR = ["application/pdf", "image/jpeg", "image/png", "image/tiff", "image/webp", "image/bmp", "image/heic", "image/heif"];

export function KiAkte() {
  const { patient } = useAkte();
  const { darf } = useAuth();
  return (
    <div className="flex flex-col gap-4" data-testid="akte-ki">
      <Meldung art="warn" className="flex gap-2.5 items-start text-[0.8125rem]">
        <Icon name="warnung" />
        <span><strong>KI (Experimentell):</strong> Hinweise und Entwürfe sind Entscheidungshilfen für Mitarbeiter – keine
          medizinische Bewertung, keine Diagnose, keine Empfehlung und keine automatische Maßnahme.</span>
      </Meldung>
      <Hinweise patient={patient.id} />
      <Vorgaenge patient={patient.id} />
      {darf("ki_berichte") ? <Berichte patient={patient.id} /> : null}
    </div>
  );
}

function Hinweise({ patient }: { patient: number }) {
  const qc = useQueryClient();
  const [alle_, setAlle] = useState(false);
  const q = useQuery({
    queryKey: ["ki", "hinweise", patient, alle_],
    queryFn: () => api<KiHinweis[]>(`ki/hinweise/${abfrage({ patient, alle: alle_ ? 1 : undefined })}`),
  });
  const status = useMutation({
    mutationFn: ({ id, s }: { id: number; s: string }) => api(`ki/hinweise/${id}/`, { method: "PATCH", body: { status: s } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ki", "hinweise", patient] }),
  });
  const [offen, setOffen] = useState<number | null>(null);
  return (
    <Karte className="flex flex-col gap-3" data-testid="ki-hinweise">
      <KartenKopf titel="Labor und Infusionsplan – historische Zusammenhänge"
        unter="Regelbasiert aus Laborwerten und Infusionsplänen der Akte sowie geprüften KI-Vorschlägen"
        rechts={<label className="text-[0.8125rem] flex items-center gap-1.5"><input type="checkbox" checked={alle_} onChange={(e) => setAlle(e.target.checked)} />ausgeblendete zeigen</label>} />
      {q.isLoading ? <Laden /> : null}
      <ul className="m-0 p-0 list-none flex flex-col divide-y divide-rand">
        {(q.data ?? []).map((h) => (
          <li key={h.id} className={cx("py-2.5 flex flex-col gap-1", h.status === "ausgeblendet" && "opacity-55")}>
            <div className="flex items-start gap-2.5">
              <Chip art={h.stufe === "gesichert" ? "ok" : "warn"} title={h.stufe === "gesichert"
                ? "Laborwert und Plan sind freigegebene Inhalte der Akte, Reihenfolge und Dosisänderung sind belegt"
                : "mindestens eine Angabe nur als KI-Vorschlag, ohne Uhrzeit oder ohne belegte Dosisänderung"}>{h.stufe_name}</Chip>
              <span className={cx("text-sm flex-1", h.status === "neu" && "font-medium")}>{h.text}</span>
              <span className="flex gap-1 shrink-0">
                <Knopf klein variante="geist" icon="info" aria-label="Belege zeigen" onClick={() => setOffen(offen === h.id ? null : h.id)} />
                {h.status !== "gesehen" ? <Knopf klein variante="geist" icon="haken" aria-label="Als gesehen markieren" onClick={() => status.mutate({ id: h.id, s: "gesehen" })} /> : null}
                {h.status !== "ausgeblendet"
                  ? <Knopf klein variante="geist" icon="auge_zu" aria-label="Ausblenden" onClick={() => status.mutate({ id: h.id, s: "ausgeblendet" })} />
                  : <Knopf klein variante="geist" icon="auge" aria-label="Wieder einblenden" onClick={() => status.mutate({ id: h.id, s: "neu" })} />}
              </span>
            </div>
            {offen === h.id ? (
              <div className="text-[0.75rem] gedaempft pl-2 flex flex-col gap-0.5">
                {(h.belege.labor ?? []).map((b, i) => <span key={`l${i}`}>Laborwert ({b.quelle === "akte" ? "Akte" : "KI-Vorschlag"}): {b.wert} {b.einheit}, {zeitpunkt(b.zeit)}</span>)}
                {(h.belege.plan ?? []).map((b, i) => <span key={`p${i}`}>Infusionsplan ({b.quelle === "akte" ? "Akte" : "KI-Vorschlag"}): {b.feld} {b.vorher ?? "–"} → {b.menge ?? "–"}, ab {datum(b.zeit)}</span>)}
                {(h.belege.folge ?? []).map((b, i) => <span key={`f${i}`}>Folgewert: {b.wert} {b.einheit}, {zeitpunkt(b.zeit)}</span>)}
                {(h.belege.wiederholungen ?? []).length ? <span>Wiederholungsmessungen am selben Tag: {(h.belege.wiederholungen ?? []).map((b) => b.wert).join(", ")}</span> : null}
              </div>) : null}
          </li>
        ))}
      </ul>
      {q.data && !q.data.length ? <Leer>Keine Zusammenhänge erkannt.</Leer> : null}
      <Fehleranzeige fehler={q.error ?? status.error} />
    </Karte>
  );
}

function Vorgaenge({ patient }: { patient: number }) {
  const { darf } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const q = useQuery({
    queryKey: ["ki", "vorgaenge", "patient", patient],
    queryFn: () => api<ApiSeite<KiVorgangKurz>>(`ki/vorgaenge/${abfrage({ patient, seitengroesse: 200 })}`),
  });
  const dokumente = useQuery({
    queryKey: ["dokumente", "ki", patient],
    queryFn: () => alle<Dokument>(`dokumente/${abfrage({ patient, ausgeblendet: "false" })}`),
    enabled: darf("ki_pruefen"),
  });
  const [dok, setDok] = useState("");
  const anfordern = useMutation({
    mutationFn: () => api("ki/vorgaenge/anfordern/", { body: { dokument: Number(dok) } }),
    onSuccess: () => { setDok(""); void qc.invalidateQueries({ queryKey: ["ki"] }); melden("Angefordert – wird verarbeitet, auch tagsüber."); },
  });
  const vorhanden = new Set((q.data?.results ?? []).map((v) => v.dokument));
  const lesbar = (dokumente.data ?? []).filter((d) => LESBAR.includes(d.mime));
  return (
    <Karte className="flex flex-col gap-3">
      <KartenKopf titel="Dokumente in der KI-Verarbeitung" unter="Gelesen werden die Dokumente der Akte, nachts und nur lesend" />
      <ul className="m-0 p-0 list-none flex flex-col divide-y divide-rand">
        {(q.data?.results ?? []).map((v) => (
          <li key={v.id} className="py-2 flex items-center gap-2.5 flex-wrap text-sm">
            <Link to={`/ki/${v.id}`}>{v.dokument_titel}</Link>
            {v.dokument_datum ? <span className="gedaempft">{datum(v.dokument_datum)}</span> : null}
            <Chip art={STATUS_ART[v.status]}>{STATUS_TEXT[v.status]}</Chip>
            {v.felder_offen ? <span className="gedaempft text-[0.8125rem]">{v.felder_offen} Vorschläge</span> : null}
          </li>
        ))}
      </ul>
      {q.data && !q.data.count ? <Leer>Noch keine Dokumente dieser Akte gelesen.</Leer> : null}
      {darf("ki_pruefen") ? (
        <div className="flex items-end gap-2 flex-wrap">
          <Feld label="Dokument jetzt verarbeiten lassen" className="min-w-[16rem] flex-1">
            {(p) => <Auswahl {...p} value={dok} onChange={(e) => setDok(e.target.value)}>
              <option value="">– Dokument wählen –</option>
              {lesbar.map((d) => <option key={d.id} value={d.id}>{d.titel}{d.datum ? ` (${datum(d.datum)})` : ""}{vorhanden.has(d.id) ? " – schon gelesen" : ""}</option>)}
            </Auswahl>}
          </Feld>
          <Knopf disabled={!dok} laedt={anfordern.isPending} onClick={() => anfordern.mutate()}>Anfordern</Knopf>
        </div>) : null}
      <Fehleranzeige fehler={q.error ?? anfordern.error} />
    </Karte>
  );
}

function Berichte({ patient }: { patient: number }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [art, setArt] = useState<KiBericht["art"]>("labor");
  const [von, setVon] = useState("");
  const [bis, setBis] = useState("");
  const [quellen, setQuellen] = useState<string[]>(QUELLEN_JE_ART.labor);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const liste = useQuery({
    queryKey: ["ki", "berichte", patient],
    queryFn: () => api<KiBericht[]>(`ki/berichte/${abfrage({ patient })}`),
    refetchInterval: (abfrage_) => ((abfrage_.state.data ?? []).some((b) => b.status === "wartet" || b.status === "laeuft") ? 5000 : false),
  });
  const anfordern = useMutation({
    mutationFn: () => api<KiBericht>("ki/berichte/", { body: { patient, art, von: von || null, bis: bis || null, dokumenttypen: quellen } }),
    onSuccess: (b) => { setGewaehlt(b.id); void qc.invalidateQueries({ queryKey: ["ki", "berichte", patient] }); melden("Angefordert – der Entwurf entsteht im KI-Dienst."); },
  });
  const b = (liste.data ?? []).find((x) => x.id === gewaehlt);
  return (
    <Karte className="flex flex-col gap-3" data-testid="ki-berichte">
      <KartenKopf titel="Berichtsentwurf auf Anforderung"
        unter="Nur aus freigegebenen Inhalten der Akte, mit Quellenangaben – immer ein Entwurf, nie automatisch in der Akte" />
      <div className="grid gap-3 sm:grid-cols-4 items-end">
        <Feld label="Berichtsart">{(p) => (
          <Auswahl {...p} value={art} onChange={(e) => { const a = e.target.value as KiBericht["art"]; setArt(a); setQuellen(QUELLEN_JE_ART[a]); }}>
            <option value="labor">Laborzusammenfassung</option><option value="infusion">Medikations-/Infusionsübersicht</option>
            <option value="verlauf">Verlaufsbericht</option></Auswahl>)}</Feld>
        <Feld label="von">{(p) => <Eingabe {...p} type="date" value={von} onChange={(e) => setVon(e.target.value)} />}</Feld>
        <Feld label="bis">{(p) => <Eingabe {...p} type="date" value={bis} onChange={(e) => setBis(e.target.value)} />}</Feld>
        <Knopf variante="pri" laedt={anfordern.isPending} disabled={!quellen.length} onClick={() => anfordern.mutate()}>Entwurf anfordern</Knopf>
      </div>
      <div className="flex gap-3 flex-wrap text-[0.8125rem]">
        {Object.entries(QUELLEN).map(([k, t]) => (
          <label key={k} className="flex items-center gap-1.5"><input type="checkbox" checked={quellen.includes(k)}
            onChange={(e) => setQuellen(e.target.checked ? [...quellen, k] : quellen.filter((x) => x !== k))} />{t}</label>))}
      </div>
      <Fehleranzeige fehler={anfordern.error} />
      <ul className="m-0 p-0 list-none flex flex-col divide-y divide-rand">
        {(liste.data ?? []).filter((x) => x.status !== "verworfen").map((x) => (
          <li key={x.id} className="py-2 flex items-center gap-2.5 flex-wrap text-sm">
            <button type="button" className="btn geist klein" onClick={() => setGewaehlt(x.id === gewaehlt ? null : x.id)}>{x.art_name}</button>
            <span className="gedaempft text-[0.8125rem]">{zeitpunkt(x.angefordert_am)} · {x.angefordert_von_name}</span>
            <Chip art={x.status === "fertig" ? "akzent" : x.status === "fehler" ? "fehler" : x.status === "gespeichert" ? "ok" : undefined}>{x.status_name}</Chip>
            {x.bericht ? <Link to="../berichte" className="text-[0.8125rem]">zum Bericht-Entwurf</Link> : null}
          </li>))}
      </ul>
      {b ? <Entwurf b={b} onFertig={() => { setGewaehlt(null); void qc.invalidateQueries({ queryKey: ["ki", "berichte", patient] }); void qc.invalidateQueries({ queryKey: ["berichte"] }); }} /> : null}
    </Karte>
  );
}

function Entwurf({ b, onFertig }: { b: KiBericht; onFertig: () => void }) {
  const melden = useHinweis();
  const [text, setText] = useState(b.entwurf);
  const speichern = useMutation({
    mutationFn: () => api("ki/berichte/" + b.id + "/speichern/", { body: { text } }),
    onSuccess: () => { melden("Als Bericht-Entwurf in der Akte gespeichert (Reiter „Berichte“)."); onFertig(); },
  });
  const verwerfen = useMutation({ mutationFn: () => api(`ki/berichte/${b.id}/verwerfen/`, { body: {} }), onSuccess: onFertig });
  if (b.status === "wartet" || b.status === "laeuft") return <Laden text="Der Entwurf wird erstellt …" />;
  const p = b.pruefung ?? {};
  return (
    <div className="flex flex-col gap-3 border-t border-rand pt-3" data-testid="ki-entwurf">
      <Meldung art="warn"><strong>{b.kennzeichnung}</strong>{b.modell ? ` Modell: ${b.modell}.` : " Ohne KI-Modell direkt aus den Fakten erstellt."}</Meldung>
      {b.fehler ? <Meldung art="warn">{b.fehler}</Meldung> : null}
      {p.ok === false ? (
        <Meldung art="warn">
          <strong>Gegenprüfung:</strong>
          <ul className="m-0 pl-4">
            {p.unbelegte_werte?.length ? <li>Zahlen/Daten ohne Beleg in den Quellen: {p.unbelegte_werte.join(", ")}</li> : null}
            {p.unbekannte_belege?.length ? <li>Verweise auf nicht vorhandene Quellen: {p.unbekannte_belege.map((n) => `[${n}]`).join(", ")}</li> : null}
            {p.empfehlung_oder_bewertung?.length ? <li>Klingt nach Empfehlung oder Bewertung: „{p.empfehlung_oder_bewertung.join("“, „")}“</li> : null}
          </ul>
        </Meldung>) : p.ok ? <Meldung art="ok">Gegenprüfung: jede Zahl und jedes Datum ist in den Quellen belegt.</Meldung> : null}
      {p.saetze_ohne_beleg?.length ? <div className="text-[0.75rem] gedaempft">Sätze ohne Quellenangabe: {p.saetze_ohne_beleg.length}</div> : null}
      <Feld label="Entwurf (bearbeitbar)">{(pp) => <Textfeld {...pp} rows={12} value={text} onChange={(e) => setText(e.target.value)}
        readOnly={b.status !== "fertig"} />}</Feld>
      <details className="text-[0.8125rem]">
        <summary>Quellen ({b.fakten.length})</summary>
        <ol className="m-0 pl-5">{b.fakten.map((f) => <li key={f.nr}>{f.text}</li>)}</ol>
      </details>
      {b.status === "fertig" ? (
        <div className="flex gap-2 flex-wrap">
          <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Als Bericht-Entwurf speichern</Knopf>
          <Knopf variante="geist" laedt={verwerfen.isPending} onClick={() => verwerfen.mutate()}>Verwerfen</Knopf>
        </div>) : null}
      <Fehleranzeige fehler={speichern.error ?? verwerfen.error} />
    </div>
  );
}
