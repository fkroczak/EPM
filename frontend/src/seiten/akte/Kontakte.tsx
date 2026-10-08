/** Entwurf 6 · Kontakte: Protokoll der Kommunikation. Nach dem Speichern unveränderlich, Korrektur nur per Storno. */
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, api } from "@/lib/api";
import type { Feldfehler, Seite as ApiSeite } from "@/lib/api";
import { useIch, useOhneRechtSchliessen } from "@/lib/auth";
import { useAuswahl, useVersorgerListe } from "@/lib/daten";
import { datum, eingabeDatum, heuteIso, terminZeit, uhrzeit, zeitpunkt } from "@/lib/format";
import { TERMINARTEN } from "@/lib/typen";
import type { Kontakt } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Editor, Richtext, klartext } from "@/components/Editor";
import { useAkte } from "./Akte";
import { Abschnitt, Aktenseite, Detail, Eintrag, Eintragsliste, useWahl } from "./Aktenseite";
import { TermineKarte } from "./Uebersicht";

function inTagen(tage: number) {
  const d = new Date();
  d.setDate(d.getDate() + tage);
  return datum(d);
}

/** Text als einfacher Absatz für den Editor (Kürzelzeile der Karteikarte) */
function absatz(text: string) {
  return `<p>${text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p>`;
}

function NeuerKontakt({ onFertig, vorlage }: { onFertig?: () => void; vorlage?: string }) {
  const { patient } = useAkte();
  const ich = useIch();
  const location = useLocation();
  // Kürzelzeile der Karteikarte („K Text“): Text vorbelegen, gespeichert wird erst mit „Kontakt speichern“
  const [text, setText] = useState(() => (vorlage ? absatz(vorlage) : ""));
  const [kontaktart, setKontaktart] = useState("");
  const [mitTermin, setMitTermin] = useState(false);
  const [art, setArt] = useState("rueckruf");
  const [faellig, setFaellig] = useState(inTagen(7));
  const [uhr, setUhr] = useState("");
  const [fokus, setFokus] = useState(() => (vorlage ? 1 : 0));
  const orte = useAuswahl("terminort");
  const kontaktarten = useAuswahl("kontaktart");
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
      return api<Kontakt>("kontakte/", { body: { patient: patient.id, text, art: kontaktart ? Number(kontaktart) : null, wiedervorlage } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      melden(mitTermin ? "Kontakt und Wiedervorlage gespeichert." : "Kontakt gespeichert.");
      setText("");
      setKontaktart("");
      setMitTermin(false);
      setUhr("");
      setFaellig(inTagen(7));
      onFertig?.();
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <div className="flex flex-col gap-3" data-testid="neuer-kontakt">
      <span className="num text-[0.8125rem] gedaempft">{datum(heuteIso())}, jetzt · {ich.anzeigename}</span>
      <Editor key={fokus} wert={text} onAenderung={setText} label="Neuer Kontakt" werkzeuge={false} hoehe={84} autofokus={fokus > 0}
        platzhalter="Telefonat, Ambulanz, Absprache mit Versorger …" />
      {f.text ? <span className="fehlertext" role="alert">{f.text}</span> : null}
      {/* Kontaktart seit 03.10.2026 sichtbar (Klärung U6); Liste unter Vorlagen › Auswahllisten */}
      <div className="flex items-center gap-2.5 flex-wrap">
        <Auswahl aria-label="Kontaktart" className="w-[260px]" value={kontaktart} onChange={(e) => setKontaktart(e.target.value)}>
          <option value="">Kontaktart: — ohne Angabe —</option>
          {(kontaktarten.data ?? []).map((o) => <option key={o.id} value={o.id}>{o.wert}</option>)}
        </Auswahl>
        {f.art ? <span className="fehlertext" role="alert">{f.art}</span> : null}
      </div>
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
  const [wahl, setWahl] = useWahl("kontakt");
  const [suche, setSuche] = useState("");
  const [begriff, setBegriff] = useState("");
  const [anzahl, setAnzahl] = useState(50);
  const [neu, setNeu] = useState(false);
  const [vorlage, setVorlage] = useState("");
  const [storno, setStorno] = useState<Kontakt | null>(null);
  // Kürzelzeile der Karteikarte („K Text“): Dialog „Neuer Kontakt“ gleich mit dem Text öffnen
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const st = location.state as { neu?: number; text?: string } | null;
    if (!st?.neu || typeof st.text !== "string" || !erfassen) return;
    setVorlage(st.text);
    setNeu(true);
    navigate(location.pathname, { replace: true, state: null }); // beim Zurückblättern nicht noch einmal öffnen
  }, [location.state, location.pathname, erfassen, navigate]);
  useOhneRechtSchliessen(erfassen, () => setStorno(null));
  useOhneRechtSchliessen(erfassen, () => setNeu(false));
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
  const gewaehlt = liste.find((k) => String(k.id) === wahl) ?? liste[0];

  return (
    <>
      <Aktenseite
        testid="kontakte"
        titel={daten?.count === 1 ? "Kontakt" : "Kontakte"}
        anzahl={daten?.count}
        laedt={abfrageliste.isLoading}
        aktion={erfassen ? <Knopf variante="pri" icon="plus" onClick={() => setNeu(true)}>Neuer Kontakt</Knopf> : undefined}
        kopfrechts={<>
          <label className="relative block">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
            <input className="inp pl-[34px] w-full" type="search" aria-label="In Kontakten suchen" placeholder="In Kontakten suchen"
              value={suche} onChange={(e) => setSuche(e.target.value)} />
          </label>
          <Fehleranzeige fehler={abfrageliste.error} />
        </>}
        liste={
          <Eintragsliste name="Kontakte" testid="kontaktliste"
            leer={liste.length ? undefined : begriff ? "Keine Kontakte mit diesem Text." : "Noch keine Kontakte erfasst."}>
            {liste.map((k) => (
              <Eintrag key={k.id} aktiv={gewaehlt?.id === k.id} onWahl={() => setWahl(String(k.id))} warnung={!!k.storniert_am}
                datum={`${datum(k.zeitpunkt)}, ${uhrzeit(k.zeitpunkt)}`}
                merkmal={k.storniert_am ? <Chip art="fehler">storniert</Chip>
                  : k.art_name ? <Chip data-testid="kontaktart">{k.art_name}</Chip> : null}
                zeile={<span className={cx("line-clamp-2", k.storniert_am && "line-through opacity-60")}>{klartext(k.text)}</span>}
                unten={[k.erfasst_von_name, k.termine.length ? `${k.termine.length} Termin${k.termine.length === 1 ? "" : "e"}` : ""]
                  .filter(Boolean).join(" · ")} />
            ))}
            {daten?.next ? <Knopf klein className="self-start" onClick={() => setAnzahl(anzahl + 50)}>Weitere laden</Knopf> : null}
          </Eintragsliste>
        }
        fuss={<>Kontakte sind das Protokoll der Kommunikation mit dem Patienten. Ein gespeicherter Kontakt wird nicht
          mehr geändert; wurde etwas falsch erfasst, wird er mit Grund storniert und neu geschrieben. Beides bleibt
          sichtbar.</>}
        detail={gewaehlt ? (
          <div className="flex flex-col gap-4" data-testid="kontakt">
            <Detail testid="kontakt-detail"
              titel={<span className="num">{datum(gewaehlt.zeitpunkt)}, {uhrzeit(gewaehlt.zeitpunkt)}</span>}
              unter={[gewaehlt.art_name, gewaehlt.erfasst_von_name].filter(Boolean).join(" · ")}
              aktionen={erfassen && !gewaehlt.storniert_am
                ? <Knopf klein variante="dng" onClick={() => setStorno(gewaehlt)}>Stornieren</Knopf> : undefined}>
              <Richtext html={gewaehlt.text} className={cx("text-sm", gewaehlt.storniert_am && "line-through opacity-60")} />
              {gewaehlt.termine.length ? (
                <Abschnitt titel="Termine aus diesem Kontakt">
                  <span className="flex gap-2 flex-wrap">
                    {gewaehlt.termine.map((x) => (
                      <Chip key={x.id} art={x.erledigt ? "ok" : "akzent"}><Icon name="kalender" />
                        {x.ort ?? TERMINARTEN[x.art]} · {terminZeit(x.faellig_am, x.uhrzeit)}{x.erledigt ? " · erledigt" : ""}</Chip>
                    ))}
                  </span>
                </Abschnitt>
              ) : null}
              {gewaehlt.storniert_am ? (
                <span className="text-[0.8125rem] text-fehler">
                  Storniert {zeitpunkt(gewaehlt.storniert_am)}{gewaehlt.storniert_von_name ? ` von ${gewaehlt.storniert_von_name}` : ""} ·
                  Grund: {gewaehlt.storno_grund}
                </span>
              ) : null}
            </Detail>
            <div className="grid gap-4 xl:grid-cols-2 items-start">
              <Erreichbarkeit />
              <TermineKarte />
            </div>
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2 items-start">
            <Erreichbarkeit />
            <TermineKarte />
          </div>
        )}
      />
      {erfassen ? <>
        <Dialog offen={neu} onOffen={(o) => { setNeu(o); if (!o) setVorlage(""); }} titel="Neuer Kontakt" breite={760}
          beschreibung="Ein gespeicherter Kontakt wird nicht mehr geändert.">
          <NeuerKontakt onFertig={() => { setNeu(false); setVorlage(""); }} vorlage={vorlage || undefined} />
        </Dialog>
        <StornoDialog kontakt={storno} onZu={() => setStorno(null)} />
      </> : null}
    </>
  );
}
