/**
 * Entwurf 6 · Kontakte: Protokoll der Kommunikation. Nach dem Speichern unveränderlich, Korrektur nur per Storno.
 *
 * Neu gestaltet 10.10.2026: oben die Schnelleingabe (Art antippen, schreiben, Wiedervorlage, speichern – ohne
 * Dialog), darunter die Kontakte als Zeitleiste nach Monaten, jeder vollständig lesbar; „Stornieren“ im Menü ⋯.
 * Rechts, wen man wie erreicht. „Kontakt“ im Aktenkopf und „Notiz“ am Telefon öffnen weiter den Dialog.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, api } from "@/lib/api";
import type { Feldfehler, Seite as ApiSeite } from "@/lib/api";
import { useOhneRechtSchliessen } from "@/lib/auth";
import { useAuswahl } from "@/lib/daten";
import { useVersorgerListe } from "@/lib/daten";
import { datum, eingabeDatum, heuteIso, terminZeit, uhrzeit, zeitpunkt } from "@/lib/format";
import { TERMINARTEN } from "@/lib/typen";
import type { Kontakt } from "@/lib/typen";
import { Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog, Menue } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Richtext } from "@/components/Editor";
import { useWiedervorlageTage } from "@/components/Schnellerfassung";
import { useAkte } from "./Akte";
import { useWahl } from "./Aktenseite";

function StornoDialog({ kontakt, onZu }: { kontakt: Kontakt | null; onZu: () => void }) {
  const { patient } = useAkte();
  const [grund, setGrund] = useState("");
  const qc = useQueryClient();
  const melden = useHinweis();
  useEffect(() => { if (kontakt) setGrund(""); }, [kontakt]);
  const storno = useMutation({
    mutationFn: () => api<Kontakt>(`kontakte/${kontakt!.id}/storno/`, { body: { grund } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden("Kontakt storniert.");
      onZu();
    },
  });
  const f: Feldfehler = storno.error instanceof ApiFehler ? storno.error.felder : {};
  return (
    <Dialog offen={!!kontakt} onOffen={(o) => { if (!o) onZu(); }} titel="Kontakt stornieren" breite={560}
      beschreibung="Der Kontakt bleibt durchgestrichen sichtbar. Den richtigen Inhalt bitte als neuen Kontakt erfassen."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf><Knopf variante="dng" laedt={storno.isPending} onClick={() => storno.mutate()}>Stornieren</Knopf></>}>
      {kontakt ? <div className="border border-rand rounded-lg p-3 text-sm"><Richtext html={kontakt.text} /></div> : null}
      <Feld label="Grund" pflicht fehler={f.grund ?? f.storno_grund ?? (storno.error ? storno.error.message : undefined)}>
        {(p) => <Textfeld {...p} rows={2} value={grund} onChange={(e) => setGrund(e.target.value)} placeholder="z. B. Tippfehler, falscher Patient" />}
      </Feld>
    </Dialog>
  );
}

/** Eine Telefonnummer als Zeile mit „Anrufen“ (tel:-Link: am Telefon direkt wählen) */
function Nummer({ wer, zusatz, nummer }: { wer: string; zusatz?: string; nummer: string }) {
  return (
    <a href={`tel:${nummer.replace(/[^\d+]/g, "")}`} className="flex items-center justify-between gap-3 min-h-11 -mx-2 px-2 rounded-lg no-underline text-tinte hover:bg-fein">
      <span className="flex flex-col min-w-0">
        <span className="font-medium [overflow-wrap:anywhere]">{wer}{zusatz ? <span className="font-normal gedaempft"> · {zusatz}</span> : null}</span>
        <span className="num text-[0.8125rem] text-text2">{nummer}</span>
      </span>
      <span className="text-[0.8125rem] font-medium text-akzent-text shrink-0">Anrufen</span>
    </a>
  );
}

function Erreichbarkeit() {
  const { patient: p } = useAkte();
  const versorger = useVersorgerListe();
  const v = (versorger.data ?? []).find((x) => x.id === p.versorger);
  const ap = v?.ansprechpartner.find((a) => a.id === p.ansprechpartner);
  const arzt = p.kopf?.hausarzt;
  const fehlt = [!p.email ? "keine E-Mail" : "", !arzt ? "kein Hausarzt" : ""].filter(Boolean).join(" · ");
  return (
    <Karte className="px-5 py-4 flex flex-col gap-1" data-testid="erreichbarkeit">
      <h2 className="lbl m-0 mb-1.5">Erreichbarkeit</h2>
      {p.telefon ? <Nummer wer="Patient/in" nummer={p.telefon} /> : null}
      {p.telefon2 ? <Nummer wer="Patient/in" zusatz="2. Nummer" nummer={p.telefon2} /> : null}
      {v?.telefon ? <Nummer wer={v.name} zusatz="Versorger" nummer={v.telefon} /> : null}
      {ap && (ap.telefon || ap.mobil) ? <Nummer wer={ap.name} zusatz="Ansprechpartner" nummer={ap.telefon || ap.mobil} /> : null}
      {arzt?.telefon ? <Nummer wer={arzt.name} zusatz="Hausarzt" nummer={arzt.telefon} /> : null}
      {p.email ? <a href={`mailto:${p.email}`} className="text-sm truncate py-1.5">{p.email}</a> : null}
      {!p.telefon && !p.telefon2 && !v?.telefon ? <span className="text-sm gedaempft">Keine Telefonnummer eingetragen.</span> : null}
      {fehlt ? <span className="text-[0.8125rem] gedaempft pt-1">{fehlt}</span> : null}
    </Karte>
  );
}

function NaechsteWiedervorlage() {
  const { patient } = useAkte();
  const t = patient.kopf?.naechster_termin;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-1">
      <h2 className="lbl m-0 mb-1">Nächster Termin</h2>
      {t ? <>
        <span className="text-lg font-semibold">{terminZeit(t.faellig_am, t.uhrzeit)}</span>
        <span className="text-[0.8125rem] gedaempft">{[t.titel, t.ort ?? TERMINARTEN[t.art]].filter(Boolean).join(" · ")}</span>
      </> : <span className="text-sm gedaempft">Kein offener Termin.</span>}
    </Karte>
  );
}

function absatz(text: string): string {
  return text.trim().split(/\n{2,}/).map((t) => `<p>${t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>")}</p>`).join("");
}

function inTagen(tage: number) {
  const d = new Date(`${heuteIso()}T12:00:00`);
  d.setDate(d.getDate() + tage);
  return datum(d.toISOString().slice(0, 10));
}

/** Schnelleingabe oben im Reiter: der häufigste Vorgang ohne Dialog (Wunsch 10.10.2026) */
function Schnelleingabe() {
  const { patient, kontaktErfassen } = useAkte();
  const arten = useAuswahl("kontaktart");
  const wvTage = useWiedervorlageTage();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [art, setArt] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [wv, setWv] = useState<"keine" | "standard" | "datum">("keine");
  const [wvDatum, setWvDatum] = useState("");
  const wvText = wvTage % 7 === 0 ? `in ${wvTage / 7} Woche${wvTage === 7 ? "" : "n"}` : `in ${wvTage} Tagen`;
  const name = `${patient.nachname}, ${patient.vorname}`;
  const speichern = useMutation({
    mutationFn: () => {
      let wiedervorlage: Record<string, unknown> | null = null;
      if (wv !== "keine") {
        const iso = eingabeDatum(wv === "standard" ? inTagen(wvTage) : wvDatum);
        if (!iso) throw new ApiFehler(400, "", null, { "wiedervorlage.faellig_am": "Bitte als TT.MM.JJJJ eingeben." });
        wiedervorlage = { art: "wiedervorlage", faellig_am: iso };
      }
      return api<Kontakt>("kontakte/", { body: { patient: patient.id, text: absatz(text), zeitpunkt: new Date().toISOString(),
        art: art, wiedervorlage } });
    },
    onSuccess: () => {
      for (const k of [["startseite"], ["patienten"], ["kalender"], ["termine"], ["meine-akten"], ["patient", patient.id]]) {
        void qc.invalidateQueries({ queryKey: k });
      }
      melden(wv !== "keine" ? `Kontakt und Wiedervorlage für ${name} gespeichert.` : `Kontakt für ${name} gespeichert.`);
      setText(""); setArt(null); setWv("keine"); setWvDatum("");
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const wvFehler = f["wiedervorlage.faellig_am"] ?? (f.wiedervorlage ? String(f.wiedervorlage) : undefined);
  const wahl = (an: boolean) => cx("h-9 px-3 rounded-full border text-[0.8125rem] font-medium cursor-pointer",
    an ? "bg-akzent border-akzent text-auf-akzent" : "bg-flaeche border-rand text-tinte hover:bg-fein");
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="kontakt-schnell" aria-label="Neuer Kontakt">
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) speichern.mutate(); }}>
        {(arten.data ?? []).length ? (
          <div role="group" aria-label="Art des Kontakts" className="flex gap-1.5 flex-wrap">
            {(arten.data ?? []).map((a) => (
              <button key={a.id} type="button" aria-pressed={art === a.id} className={wahl(art === a.id)}
                onClick={() => setArt(art === a.id ? null : a.id)}>{a.wert}</button>
            ))}
          </div>
        ) : null}
        <Feld label="Was wurde besprochen?" fehler={f.text}>
          {(p) => <Textfeld {...p} rows={2} value={text} onChange={(e) => setText(e.target.value)}
            placeholder="z. B. Gewicht durchgegeben, Befinden stabil …"
            onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && text.trim()) { e.preventDefault(); speichern.mutate(); } }} />}
        </Feld>
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div role="group" aria-label="Wiedervorlage" className="flex items-center gap-1.5 flex-wrap text-[0.8125rem]">
            <span className="text-text2 mr-0.5">Wiedervorlage:</span>
            <button type="button" aria-pressed={wv === "keine"} className={wahl(wv === "keine")} onClick={() => setWv("keine")}>keine</button>
            <button type="button" aria-pressed={wv === "standard"} className={wahl(wv === "standard")} onClick={() => setWv("standard")}>{wvText}</button>
            <button type="button" aria-pressed={wv === "datum"} className={wahl(wv === "datum")}
              onClick={() => { setWv("datum"); if (!wvDatum) setWvDatum(inTagen(wvTage)); }}>Datum …</button>
            {wv === "datum" ? <Eingabe className="num !w-32" aria-label="Datum der Wiedervorlage" value={wvDatum} onChange={(e) => setWvDatum(e.target.value)} /> : null}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Knopf variante="geist" onClick={() => kontaktErfassen(text)} title="Dialog mit Uhrzeit, Gewicht und Termin">Mehr Angaben …</Knopf>
            <Knopf type="submit" variante="pri" icon="haken" laedt={speichern.isPending} disabled={!text.trim()}>Kontakt speichern</Knopf>
          </div>
        </div>
        {wvFehler ? <span className="fehlertext" role="alert">{wvFehler}</span> : null}
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      </form>
    </Karte>
  );
}

const MONAT = new Intl.DateTimeFormat("de-DE", { month: "long", year: "numeric" });

/** Ein Kontakt in der Zeitleiste */
function KontaktZeile({ k, markiert, onStorno }: { k: Kontakt; markiert: boolean; onStorno?: () => void }) {
  const ref = useRef<HTMLLIElement>(null);
  useEffect(() => { if (markiert) ref.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [markiert]);
  const d = new Date(k.zeitpunkt);
  return (
    <li ref={ref} className={cx("kontakt-zeile", markiert && "markiert", k.storniert_am && "storniert")}
      data-testid={markiert ? "kontakt-detail" : undefined}>
      <span className="flex flex-col">
        <span className="font-medium">{datum(k.zeitpunkt).slice(0, 6)}</span>
        <span className="num text-xs gedaempft">{uhrzeit(d)}</span>
      </span>
      <div className="flex flex-col gap-1.5 min-w-0">
        <span className="flex items-center gap-1.5 flex-wrap text-xs gedaempft">
          {k.storniert_am ? <Chip art="fehler">storniert</Chip> : null}
          {k.art_name ? <Chip data-testid="kontaktart">{k.art_name}</Chip> : null}
          <span>{k.erfasst_von_name ?? ""}</span>
          <span className="sr-only">{datum(k.zeitpunkt)}</span>
        </span>
        <Richtext html={k.text} className={cx("text-sm", k.storniert_am && "line-through opacity-60")} />
        {k.termine.length ? (
          <span className="flex gap-1.5 flex-wrap">
            {k.termine.map((x) => (
              <Chip key={x.id} art={x.erledigt ? "ok" : "akzent"}><Icon name="kalender" groesse={12} />
                {TERMINARTEN[x.art]}{x.ort ? ` · ${x.ort}` : ""} · {terminZeit(x.faellig_am, x.uhrzeit)}{x.erledigt ? " · erledigt" : ""}</Chip>
            ))}
          </span>
        ) : null}
        {k.storniert_am ? (
          <span className="text-[0.8125rem] text-fehler">
            Storniert {zeitpunkt(k.storniert_am)}{k.storniert_von_name ? ` von ${k.storniert_von_name}` : ""} · Grund: {k.storno_grund}
          </span>
        ) : null}
      </div>
      {onStorno && !k.storniert_am
        ? <Menue label={`Weitere Aktionen zum Kontakt vom ${datum(k.zeitpunkt)}`} eintraege={[{ text: "Stornieren …", onClick: onStorno, gefaehrlich: true }]} />
        : <span />}
    </li>
  );
}

export function Kontakte() {
  const { patient, erfassen } = useAkte();
  const [wahl] = useWahl("kontakt");
  const [suche, setSuche] = useState("");
  const [begriff, setBegriff] = useState("");
  const [anzahl, setAnzahl] = useState(50);
  const [storno, setStorno] = useState<Kontakt | null>(null);
  useOhneRechtSchliessen(erfassen, () => setStorno(null));
  useEffect(() => {
    const t = window.setTimeout(() => setBegriff(suche.trim()), 300);
    return () => window.clearTimeout(t);
  }, [suche]);
  const abfrageliste = useQuery({
    queryKey: ["patient", patient.id, "kontakte", begriff, anzahl],
    queryFn: () => api<ApiSeite<Kontakt>>(`kontakte/${abfrage({ patient: patient.id, search: begriff, seitengroesse: anzahl })}`),
    placeholderData: (vorher: ApiSeite<Kontakt> | undefined) => vorher,
  });
  const daten = abfrageliste.data;
  const liste = daten?.results ?? [];
  // nach Monaten gruppiert, neueste zuerst
  const monate: { name: string; kontakte: Kontakt[] }[] = [];
  for (const k of liste) {
    const name = MONAT.format(new Date(k.zeitpunkt));
    if (monate[monate.length - 1]?.name !== name) monate.push({ name, kontakte: [] });
    monate[monate.length - 1].kontakte.push(k);
  }

  return (
    <>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(17.5rem,22rem)] gap-[var(--abstand)] items-start" data-testid="kontakte">
        <div className="flex flex-col gap-[var(--abstand)] min-w-0">
          {erfassen ? <Schnelleingabe /> : null}
          <Karte className="overflow-hidden">
            <div className="px-5 py-3 flex items-center justify-between gap-3 flex-wrap border-b border-rand">
              <h2 className="lbl m-0 text-[0.9375rem]">{daten ? `${daten.count} ${daten.count === 1 ? "Kontakt" : "Kontakte"}` : "Kontakte"}</h2>
              <label className="relative block w-full sm:w-64">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
                <input className="inp pl-[2.125rem] w-full" type="search" aria-label="In Kontakten suchen" placeholder="In Kontakten suchen"
                  value={suche} onChange={(e) => setSuche(e.target.value)} />
              </label>
            </div>
            <Fehleranzeige fehler={abfrageliste.error} />
            {abfrageliste.isLoading ? <Laden /> : null}
            <div data-testid="kontaktliste">
              {monate.map((m) => (
                <section key={m.name} aria-label={m.name}>
                  <h3 className="m-0 px-5 pt-3 pb-1 text-[0.6875rem] font-semibold tracking-[.06em] uppercase gedaempft">{m.name}</h3>
                  <ul className="m-0 p-0 list-none">
                    {m.kontakte.map((k) => (
                      <KontaktZeile key={k.id} k={k} markiert={String(k.id) === wahl} onStorno={erfassen ? () => setStorno(k) : undefined} />
                    ))}
                  </ul>
                </section>
              ))}
              {!abfrageliste.isLoading && !liste.length ? (
                <p className="m-0 px-5 py-4 text-sm gedaempft">{begriff ? "Keine Kontakte mit diesem Text." : "Noch keine Kontakte erfasst."}</p>
              ) : null}
            </div>
            {daten?.next ? <div className="px-5 py-3 border-t border-rand"><Knopf klein onClick={() => setAnzahl(anzahl + 50)}>Weitere laden</Knopf></div> : null}
            <p className="m-0 px-5 py-2.5 border-t border-rand text-xs gedaempft">Gespeicherte Kontakte werden nicht geändert, sondern über ⋯ storniert.</p>
          </Karte>
        </div>
        <aside className="flex flex-col gap-[var(--abstand)] min-w-0" aria-label="Erreichbarkeit">
          <Erreichbarkeit />
          <NaechsteWiedervorlage />
        </aside>
      </div>
      {erfassen ? <StornoDialog kontakt={storno} onZu={() => setStorno(null)} /> : null}
    </>
  );
}
