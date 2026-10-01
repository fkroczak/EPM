/** Entwurf 6 · Kontakte: Protokoll der Kommunikation. Nach dem Speichern unveränderlich, Korrektur nur per Storno. */
import { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, api } from "@/lib/api";
import type { Feldfehler, Seite as ApiSeite } from "@/lib/api";
import { useIch } from "@/lib/auth";
import { useAuswahl, useVersorgerListe } from "@/lib/daten";
import { datum, eingabeDatum, heuteIso, terminZeit, uhrzeit, zahl, zeitpunkt } from "@/lib/format";
import { TERMINARTEN } from "@/lib/typen";
import type { Kontakt } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Leer, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Editor, Richtext } from "@/components/Editor";
import { useAkte } from "./Akte";

function inTagen(tage: number) {
  const d = new Date();
  d.setDate(d.getDate() + tage);
  return datum(d);
}

function NeuerKontakt() {
  const { patient } = useAkte();
  const ich = useIch();
  const location = useLocation();
  const [text, setText] = useState("");
  const [mitTermin, setMitTermin] = useState(false);
  const [art, setArt] = useState("rueckruf");
  const [faellig, setFaellig] = useState(inTagen(7));
  const [uhr, setUhr] = useState("");
  const [fokus, setFokus] = useState(0);
  const orte = useAuswahl("terminort");
  const qc = useQueryClient();
  const melden = useHinweis();
  useEffect(() => {
    const st = location.state as { neu?: number } | null;
    if (st?.neu) setFokus(st.neu);
  }, [location.state]);
  const speichern = useMutation({
    mutationFn: () => {
      let wiedervorlage: Record<string, unknown> | null = null;
      if (mitTermin) {
        const iso = eingabeDatum(faellig);
        if (!iso) throw new ApiFehler(400, "", null, { "wiedervorlage.faellig_am": "Bitte als TT.MM.JJJJ eingeben." });
        const [a, ort] = art.startsWith("ort:") ? ["praxistermin", Number(art.slice(4))] : [art, null];
        wiedervorlage = { art: a, ort, faellig_am: iso, uhrzeit: uhr || null };
      }
      return api<Kontakt>("kontakte/", { body: { patient: patient.id, text, wiedervorlage } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      melden(mitTermin ? "Kontakt und Wiedervorlage gespeichert." : "Kontakt gespeichert.");
      setText("");
      setMitTermin(false);
      setUhr("");
      setFaellig(inTagen(7));
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <div className="flex flex-col gap-3 px-[22px] py-[18px] border-b border-rand" data-testid="neuer-kontakt">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="lbl m-0">Neuer Kontakt</h2>
        <span className="num text-[0.8125rem] gedaempft">{datum(heuteIso())}, jetzt · {ich.anzeigename}</span>
      </div>
      <Editor key={fokus} wert={text} onAenderung={setText} label="Neuer Kontakt" werkzeuge={false} hoehe={84} autofokus={fokus > 0}
        platzhalter="Telefonat, Ambulanz, Absprache mit Versorger …" />
      {f.text ? <span className="fehlertext" role="alert">{f.text}</span> : null}
      <div className="flex items-center gap-2.5 flex-wrap">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={mitTermin} onChange={(e) => setMitTermin(e.target.checked)} /> Wiedervorlage
        </label>
        <Auswahl aria-label="Art" className="w-[220px]" value={art} disabled={!mitTermin} onChange={(e) => setArt(e.target.value)}>
          <option value="rueckruf">{TERMINARTEN.rueckruf}</option>
          <option value="wiedervorlage">{TERMINARTEN.wiedervorlage}</option>
          {(orte.data ?? []).map((o) => <option key={o.id} value={`ort:${o.id}`}>{o.wert}</option>)}
          <option value="sonstiges">{TERMINARTEN.sonstiges}</option>
        </Auswahl>
        <Eingabe aria-label="Datum" className="num w-[120px]" value={faellig} disabled={!mitTermin} onChange={(e) => setFaellig(e.target.value)}
          aria-invalid={f["wiedervorlage.faellig_am"] ? true : undefined} />
        <Eingabe aria-label="Uhrzeit" type="time" className="num w-[110px]" value={uhr} disabled={!mitTermin} onChange={(e) => setUhr(e.target.value)} />
      </div>
      {Object.entries(f).filter(([k]) => k.startsWith("wiedervorlage")).map(([k, v]) => <span key={k} className="fehlertext" role="alert">{v}</span>)}
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className="text-[0.8125rem] gedaempft">Nach dem Speichern nicht mehr änderbar. Die Wiedervorlage erscheint auf der Startseite.</span>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!text} onClick={() => speichern.mutate()}>Kontakt speichern</Knopf>
      </div>
    </div>
  );
}

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

function Erreichbarkeit() {
  const { patient: p } = useAkte();
  const versorger = useVersorgerListe();
  const v = (versorger.data ?? []).find((x) => x.id === p.versorger);
  const ap = v?.ansprechpartner.find((a) => a.id === p.ansprechpartner);
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3">
      <h2 className="lbl m-0">Erreichbarkeit</h2>
      <div className="grid grid-cols-[90px_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
        <span className="gedaempft">Telefon</span><span className="num">{p.telefon || "—"}</span>
        <span className="gedaempft">E-Mail</span><span className="truncate">{p.email || "—"}</span>
        <span className="gedaempft">Versorger</span><span>{v ? <>{v.name}{v.telefon ? <> · <span className="num">{v.telefon}</span></> : null}</> : "—"}</span>
        <span className="gedaempft">Ansprechp.</span><span>{ap ? <>{ap.name}{ap.telefon || ap.mobil ? <> · <span className="num">{ap.telefon || ap.mobil}</span></> : null}</> : "—"}</span>
        <span className="gedaempft">Hausarzt</span><span>{p.hausarzt || "—"}</span>
      </div>
    </Karte>
  );
}

export function Kontakte() {
  const { patient, erfassen } = useAkte();
  const [suche, setSuche] = useState("");
  const [begriff, setBegriff] = useState("");
  const [anzahl, setAnzahl] = useState(50);
  const [storno, setStorno] = useState<Kontakt | null>(null);
  useEffect(() => {
    const t = window.setTimeout(() => setBegriff(suche.trim()), 300);
    return () => window.clearTimeout(t);
  }, [suche]);
  const liste = useQuery({
    queryKey: ["patient", patient.id, "kontakte", begriff, anzahl],
    queryFn: () => api<ApiSeite<Kontakt>>(`kontakte/${abfrage({ patient: patient.id, search: begriff, seitengroesse: anzahl })}`),
    placeholderData: (vorher: ApiSeite<Kontakt> | undefined) => vorher,
  });
  const daten = liste.data;
  return (
    <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] gap-5 items-start">
      <Karte className="flex flex-col min-w-0 overflow-hidden">
        {erfassen ? <NeuerKontakt /> : null}
        <div className="flex items-center justify-between gap-3 px-[22px] pt-4 pb-2 flex-wrap">
          <h2 className="lbl m-0">Kontakte · <span className="num">{daten ? zahl(daten.count) : "…"}</span> · neueste oben</h2>
          <label className="relative w-[240px] block">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
            <input className="inp pl-[34px]" type="search" aria-label="In Kontakten suchen" placeholder="In Kontakten suchen"
              value={suche} onChange={(e) => setSuche(e.target.value)} />
          </label>
        </div>
        {liste.isLoading ? <Laden /> : (
          <ol className="m-0 p-0 list-none flex flex-col" data-testid="kontaktliste" aria-busy={liste.isFetching || undefined}>
            {(daten?.results ?? []).map((k) => (
              <li key={k.id} className="px-[22px] py-3.5 border-t border-rand flex flex-col gap-1.5" data-testid="kontakt">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2.5 text-[0.8125rem] gedaempft">
                    <span className="num">{datum(k.zeitpunkt)}, {uhrzeit(k.zeitpunkt)}</span><span>{k.erfasst_von_name}</span>
                    {k.storniert_am ? <Chip art="fehler">storniert</Chip> : null}
                  </span>
                  {erfassen && !k.storniert_am ? (
                    <button type="button" className="bg-transparent border-0 p-0 text-[0.8125rem] gedaempft hover:text-fehler cursor-pointer"
                      onClick={() => setStorno(k)} aria-label={`Kontakt vom ${datum(k.zeitpunkt)}, ${uhrzeit(k.zeitpunkt)} stornieren`}>Stornieren</button>
                  ) : null}
                </div>
                <Richtext html={k.text} className={cx("text-sm", k.storniert_am && "line-through opacity-60")} />
                {k.termine.length ? (
                  <span className="flex gap-2 flex-wrap">
                    {k.termine.map((t) => (
                      <Chip key={t.id} art={t.erledigt ? "ok" : "akzent"}><Icon name="kalender" />{t.ort ?? TERMINARTEN[t.art]} · {terminZeit(t.faellig_am, t.uhrzeit)}{t.erledigt ? " · erledigt" : ""}</Chip>
                    ))}
                  </span>
                ) : null}
                {k.storniert_am ? (
                  <span className="text-[0.8125rem] text-fehler">Storniert {zeitpunkt(k.storniert_am)}{k.storniert_von_name ? ` von ${k.storniert_von_name}` : ""} · Grund: {k.storno_grund}</span>
                ) : null}
              </li>
            ))}
          </ol>
        )}
        {daten && !daten.count ? <Leer>{begriff ? "Keine Kontakte mit diesem Text." : "Noch keine Kontakte erfasst."}</Leer> : null}
        {daten?.next ? <div className="px-[22px] py-3 border-t border-rand"><Knopf klein onClick={() => setAnzahl(anzahl + 50)}>Weitere laden</Knopf></div> : null}
        <Fehleranzeige fehler={liste.error} />
      </Karte>
      <div className="flex flex-col gap-4 min-w-0">
        <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
          <Icon name="info" />
          <span>Kontakte sind das Protokoll der Kommunikation mit dem Patienten. Ein gespeicherter Kontakt wird nicht mehr geändert.
            Wurde etwas falsch erfasst, wird der Kontakt mit Grund storniert und neu geschrieben. Beides bleibt sichtbar.</span>
        </div>
        <Erreichbarkeit />
      </div>
      <StornoDialog kontakt={storno} onZu={() => setStorno(null)} />
    </div>
  );
}
