/**
 * Reiter „Katheter“ – Katheter-Historie (F192, Wunsch 15.10.2026).
 *
 * Oben die Kennzahlen: aktueller Katheter mit Liegedauer in Tagen und Infektionen je 1000 Kathetertage (übliche
 * Kennzahl der heimparenteralen Ernährung). Darunter die Zeitachse: je Katheter ein Balken von der Anlage bis zur
 * Entfernung (liegende bis heute), Komplikationen als Markierungen – ab 768 px waagerecht, darunter senkrecht. Die
 * Achse wird nur aus den geladenen Daten berechnet (feste Höhen je Zeile), damit beim Laden nichts springt. Darunter die
 * Liste zum Erfassen und Bearbeiten (am PC Tabelle, am Telefon Karten), wie im Reiter „Medikamente“.
 *
 * Kerndaten (Festlegung vom 16.10.2026): Ein neuer, noch liegender Katheter wird vom Backend in das Katheterfeld der
 * Akte übernommen; ein noch offener vorheriger Katheter wird nicht automatisch beendet – dazu erscheint der Hinweis
 * „Vorheriger Katheter noch nicht als entfernt eingetragen“. Steht in den Kerndaten ein Katheter, aber in der Historie
 * keiner (z. B. aus dem Altsystem, das nur den Typ kennt), bittet die Seite „Anlagedatum nicht erfasst – bitte
 * nachtragen“ statt einer leeren Zeitachse; erfunden wird kein Datum. „?eintrag=<id>“ hebt einen Katheter hervor.
 */
import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuswahl } from "@/lib/daten";
import { alsDatum, datum, eingabeDatum, heuteIso, zahl } from "@/lib/format";
import type { Katheter as KatheterT, KatheterKennzahlen, KatheterKomplikation } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Karte, Knopf, Laden, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Begriff } from "@/components/ui/Begriff";
import { FirmaMarke } from "@/components/FirmenWahl";
import { Bestaetigen } from "@/components/Bestaetigen";
import { useAkte } from "./Akte";
import { useWahl } from "./Aktenseite";

const TAG_MS = 86_400_000;

/** „2026-10-15“ → Tagesnummer (lokal, ohne Sommerzeit-Versatz) */
function tagNr(iso: string): number {
  const d = alsDatum(iso)!;
  return Math.round(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / TAG_MS);
}

function tage(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n === 1 ? "1 Tag" : `${zahl(n)} Tage`;
}

function useNeuLaden() {
  const qc = useQueryClient();
  const { patient } = useAkte();
  return () => {
    void qc.invalidateQueries({ queryKey: ["katheter", patient.id] });
    // Zähler im Reiter, Katheter im Aktenkopf (Kerndaten) und Karteikarte
    void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
  };
}

/** Datum als TT.MM.JJJJ eingeben (wie in den übrigen Dialogen); leer = null */
function isoOderFehler(text: string, feld: string, pflicht: boolean): string | null {
  if (!text.trim()) {
    if (pflicht) throw new ApiFehler(400, "", null, { [feld]: "Bitte das Datum angeben." });
    return null;
  }
  const iso = eingabeDatum(text);
  if (!iso) throw new ApiFehler(400, "", null, { [feld]: "Bitte als TT.MM.JJJJ eingeben." });
  return iso;
}

// ---------------------------------------------------------------------------------------------- Dialoge

function KatheterDialog({ katheter, entfernen, offen, onOffen }: {
  katheter: KatheterT | null; entfernen?: boolean; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const { patient } = useAkte();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const typen = useAuswahl("katheter", false);
  const gruende = useAuswahl("katheter_entfernung", false);
  const [typ, setTyp] = useState("");
  const [lage, setLage] = useState("");
  const [anlage, setAnlage] = useState("");
  const [entfernt, setEntfernt] = useState("");
  const [grund, setGrund] = useState("");
  const [notiz, setNotiz] = useState("");
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${katheter?.id ?? "neu"}-${entfernen ? "e" : ""}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setTyp(katheter ? String(katheter.typ) : "");
    setLage(katheter?.lage ?? "");
    setAnlage(katheter ? datum(katheter.anlage_am) : "");
    setEntfernt(katheter?.entfernt_am ? datum(katheter.entfernt_am) : entfernen ? datum(heuteIso()) : "");
    setGrund(katheter?.entfernungsgrund ? String(katheter.entfernungsgrund) : "");
    setNotiz(katheter?.notiz ?? "");
  }
  // geschlossen: beim nächsten Öffnen neu vorbelegen (sonst stünde der zuletzt gespeicherte Katheter noch drin)
  if (!offen && gesetzt) setGesetzt("");

  const speichern = useMutation({
    mutationFn: () => {
      const koerper = {
        patient: patient.id, typ: typ ? Number(typ) : null, lage, notiz,
        anlage_am: isoOderFehler(anlage, "anlage_am", true),
        entfernt_am: isoOderFehler(entfernt, "entfernt_am", false),
        entfernungsgrund: entfernt.trim() && grund ? Number(grund) : null,
      };
      return katheter
        ? api<KatheterT>(`katheter/${katheter.id}/`, { method: "PATCH", body: koerper })
        : api<KatheterT>("katheter/", { body: koerper });
    },
    onSuccess: (k) => {
      neuLaden();
      // der Hinweis „Vorheriger Katheter noch nicht als entfernt eingetragen“ bleibt danach als Meldung über der Zeitachse
      // stehen (aus den Kennzahlen), bis die Entfernung eingetragen ist
      melden(katheter ? (entfernen ? "Entfernung eingetragen." : "Katheter geändert.")
        : [k.kerndaten_aktualisiert ? "Katheter eingetragen – in die Kerndaten der Akte übernommen." : "Katheter eingetragen.",
          ...(k.hinweise ?? []).map((h) => `${h}.`)].join(" "));
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const titel = entfernen ? "Katheter entfernen" : katheter ? "Katheter ändern" : "Neuer Katheter";

  return (
    <Dialog offen={offen} onOffen={onOffen} breite={620} titel={titel}
      beschreibung={entfernen ? `${katheter?.typ_name ?? "Katheter"} seit ${datum(katheter?.anlage_am)}: Datum und Grund der Entfernung.`
        : "Typ, Lage und Anlagedatum; bei einem schon entfernten Katheter auch das Datum der Entfernung."}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!typ || !anlage.trim() || (entfernen && !entfernt.trim())}
          onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      {entfernen ? null : <>
        <div className="grid gap-3 sm:grid-cols-2">
          <Feld label="Katheter-Typ" fehler={f.typ} pflicht>
            {(p) => (
              <Auswahl {...p} value={typ} onChange={(e) => setTyp(e.target.value)}>
                <option value="">– bitte wählen –</option>
                {(typen.data ?? []).filter((t) => t.aktiv || String(t.id) === typ).map((t) => <option key={t.id} value={t.id}>{t.wert}</option>)}
              </Auswahl>
            )}
          </Feld>
          <Feld label="Lage/Zugang" fehler={f.lage} hinweis="z. B. „V. subclavia rechts“">
            {(p) => <Eingabe {...p} value={lage} maxLength={200} onChange={(e) => setLage(e.target.value)} />}
          </Feld>
        </div>
        <Feld label="Anlagedatum" fehler={f.anlage_am} pflicht className="max-w-[12rem]">
          {(p) => <Eingabe {...p} className="num" value={anlage} placeholder="TT.MM.JJJJ" onChange={(e) => setAnlage(e.target.value)} />}
        </Feld>
      </>}
      <div className="grid gap-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
        <Feld label="Entfernt am" fehler={f.entfernt_am} pflicht={entfernen}
          hinweis={entfernen ? undefined : "leer, solange der Katheter liegt"}>
          {(p) => <Eingabe {...p} className="num" value={entfernt} placeholder="TT.MM.JJJJ" onChange={(e) => setEntfernt(e.target.value)} />}
        </Feld>
        <Feld label="Entfernungsgrund" fehler={f.entfernungsgrund}>
          {(p) => (
            <Auswahl {...p} value={grund} disabled={!entfernt.trim()} onChange={(e) => setGrund(e.target.value)}>
              <option value="">– ohne Angabe –</option>
              {(gruende.data ?? []).filter((g) => g.aktiv || String(g.id) === grund).map((g) => <option key={g.id} value={g.id}>{g.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
      </div>
      {entfernen ? null : (
        <Feld label="Notiz" fehler={f.notiz}>
          {(p) => <Textfeld {...p} rows={2} maxLength={500} value={notiz} onChange={(e) => setNotiz(e.target.value)} />}
        </Feld>
      )}
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      {f.fehler ? <Meldung art="fehler">{f.fehler}</Meldung> : null}
    </Dialog>
  );
}

function KomplikationDialog({ katheter, komplikation, offen, onOffen }: {
  katheter: KatheterT | null; komplikation: KatheterKomplikation | null; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const arten = useAuswahl("katheter_komplikation", false);
  const [tag, setTag] = useState("");
  const [art, setArt] = useState("");
  const [notiz, setNotiz] = useState("");
  const [gesetzt, setGesetzt] = useState("");
  const schluessel = `${katheter?.id}-${komplikation?.id ?? "neu"}-${offen}`;
  if (offen && gesetzt !== schluessel) {
    setGesetzt(schluessel);
    setTag(komplikation ? datum(komplikation.datum) : datum(katheter?.entfernt_am ?? heuteIso()));
    setArt(komplikation ? String(komplikation.art) : "");
    setNotiz(komplikation?.notiz ?? "");
  }
  if (!offen && gesetzt) setGesetzt("");
  const speichern = useMutation({
    mutationFn: () => {
      const koerper = { katheter: katheter!.id, datum: isoOderFehler(tag, "datum", true), art: art ? Number(art) : null, notiz };
      return komplikation
        ? api<KatheterKomplikation>(`katheter-komplikationen/${komplikation.id}/`, { method: "PATCH", body: koerper })
        : api<KatheterKomplikation>("katheter-komplikationen/", { body: koerper });
    },
    onSuccess: () => { neuLaden(); melden(komplikation ? "Komplikation geändert." : "Komplikation eingetragen."); onOffen(false); },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const liegezeit = katheter ? `${datum(katheter.anlage_am)} – ${katheter.entfernt_am ? datum(katheter.entfernt_am) : "heute"}` : "";
  return (
    <Dialog offen={offen} onOffen={onOffen} breite={520} titel={komplikation ? "Komplikation ändern" : "Neue Komplikation"}
      beschreibung={`${katheter?.typ_name ?? "Katheter"} · Liegezeit ${liegezeit}. Das Datum muss in der Liegezeit liegen.`}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!art || !tag.trim()} onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-[12rem_minmax(0,1fr)]">
        <Feld label="Datum" fehler={f.datum} pflicht>
          {(p) => <Eingabe {...p} className="num" value={tag} placeholder="TT.MM.JJJJ" onChange={(e) => setTag(e.target.value)} />}
        </Feld>
        <Feld label="Art" fehler={f.art} pflicht>
          {(p) => (
            <Auswahl {...p} value={art} onChange={(e) => setArt(e.target.value)}>
              <option value="">– bitte wählen –</option>
              {(arten.data ?? []).filter((a) => a.aktiv || String(a.id) === art).map((a) => <option key={a.id} value={a.id}>{a.wert}</option>)}
            </Auswahl>
          )}
        </Feld>
      </div>
      <Feld label="Notiz" fehler={f.notiz}>
        {(p) => <Textfeld {...p} rows={2} maxLength={500} value={notiz} onChange={(e) => setNotiz(e.target.value)} />}
      </Feld>
      {f.katheter ? <Meldung art="fehler">{f.katheter}</Meldung> : null}
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

// ---------------------------------------------------------------------------------------------- Zeitachse

type Spanne = { von: number; bis: number };

/** Gemeinsamer Zeitraum aller Katheter (mit etwas Rand), mindestens 30 Tage */
function zeitraum(liste: KatheterT[], heute: number): Spanne {
  const von = Math.min(...liste.map((k) => tagNr(k.anlage_am)));
  const bis = Math.max(heute, ...liste.map((k) => (k.entfernt_am ? tagNr(k.entfernt_am) : heute)));
  const breite = Math.max(30, bis - von);
  const rand = Math.round(breite * 0.02);
  return { von: von - rand, bis: von + breite + rand };
}

/** Beschriftung der Achse: Jahre, bei kurzen Zeiträumen Monate */
function achsenMarken(s: Spanne): { tag: number; text: string }[] {
  const start = new Date(s.von * TAG_MS);
  const ende = new Date(s.bis * TAG_MS);
  const jahre = ende.getUTCFullYear() - start.getUTCFullYear();
  const marken: { tag: number; text: string }[] = [];
  if (jahre >= 2) {
    const schritt = jahre > 8 ? 2 : 1;
    for (let j = start.getUTCFullYear() + 1; j <= ende.getUTCFullYear(); j += schritt) {
      marken.push({ tag: Date.UTC(j, 0, 1) / TAG_MS, text: String(j) });
    }
  } else {
    const monate = (ende.getUTCFullYear() - start.getUTCFullYear()) * 12 + ende.getUTCMonth() - start.getUTCMonth();
    const schritt = monate > 12 ? 3 : monate > 5 ? 2 : 1;
    for (let m = 1; m <= monate; m += schritt) {
      const d = Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + m, 1);
      const dd = new Date(d);
      marken.push({ tag: d / TAG_MS, text: `${String(dd.getUTCMonth() + 1).padStart(2, "0")}/${String(dd.getUTCFullYear()).slice(2)}` });
    }
  }
  return marken.filter((m) => m.tag > s.von && m.tag < s.bis);
}

function anteil(tag: number, s: Spanne) {
  return ((tag - s.von) / (s.bis - s.von)) * 100;
}

function balkenTitel(k: KatheterT) {
  return `${k.typ_name ?? "Katheter"}${k.lage ? ` · ${k.lage}` : ""}: ${datum(k.anlage_am)} – ${k.entfernt_am ? datum(k.entfernt_am) : "liegt"}`
    + ` (${tage(k.liegedauer_tage)})${k.entfernungsgrund_name ? ` · ${k.entfernungsgrund_name}` : ""}`;
}

function markeTitel(x: KatheterKomplikation) {
  return `${x.art_name ?? "Komplikation"} am ${datum(x.datum)}${x.notiz ? ` · ${x.notiz}` : ""}`;
}

/** Markierung einer Komplikation: Raute; Infektionen gefüllt in der Fehlerfarbe, andere als Umriss */
function Marke({ x, stil, onWahl }: { x: KatheterKomplikation; stil: CSSProperties; onWahl: () => void }) {
  return (
    <button type="button" className={cx("katheter-marke", x.ist_infektion && "infektion")} style={stil}
      title={markeTitel(x)} aria-label={markeTitel(x)} data-testid="katheter-marke" onClick={onWahl} />
  );
}

function Zeitachse({ liste, wahl, onWahl }: { liste: KatheterT[]; wahl: string; onWahl: (id: number) => void }) {
  const heute = tagNr(heuteIso());
  // älteste zuerst, damit die Achse von links nach rechts bzw. von oben nach unten liest
  const reihe = [...liste].sort((a, b) => a.anlage_am.localeCompare(b.anlage_am) || a.id - b.id);
  const s = zeitraum(reihe, heute);
  const marken = achsenMarken(s);
  const heuteLinks = anteil(heute, s);
  const beschreibung = `Zeitachse mit ${reihe.length} Kathetern: `
    + reihe.map((k) => `${balkenTitel(k)}, ${k.komplikationen.filter((x) => x.aktiv).length} Komplikationen`).join("; ");
  return (
    <div data-testid="katheter-zeitachse">
      {/* waagerecht ab 768 px */}
      <div className="max-md:hidden px-5 pb-4">
        <div className="katheter-achse" role="img" aria-label={beschreibung}>
          {reihe.map((k) => {
            const von = anteil(tagNr(k.anlage_am), s);
            const bis = anteil(k.entfernt_am ? tagNr(k.entfernt_am) : heute, s);
            return (
              <div key={k.id} className="katheter-zeile" data-testid="katheter-balken-zeile">
                <span className="katheter-zeile-name text-[0.8125rem] truncate" title={k.typ_name ?? ""}>{k.typ_name}</span>
                <div className="katheter-spur">
                  <button type="button" data-testid="katheter-balken" title={balkenTitel(k)} aria-label={balkenTitel(k)}
                    className={cx("katheter-balken", k.liegt && "liegt", String(k.id) === wahl && "gewaehlt")}
                    style={{ left: `${von}%`, width: `max(0.375rem, ${bis - von}%)` }} onClick={() => onWahl(k.id)} />
                  {k.komplikationen.filter((x) => x.aktiv).map((x) => (
                    <Marke key={x.id} x={x} onWahl={() => onWahl(k.id)} stil={{ left: `${anteil(tagNr(x.datum), s)}%` }} />
                  ))}
                </div>
              </div>
            );
          })}
          <div className="katheter-zeile" aria-hidden="true">
            <span />
            <div className="katheter-skala">
              {marken.map((m) => <span key={m.tag} className="katheter-skala-marke num" style={{ left: `${anteil(m.tag, s)}%` }}>{m.text}</span>)}
              <span className="katheter-heute" style={{ left: `${heuteLinks}%` }}>heute</span>
            </div>
          </div>
        </div>
      </div>
      {/* senkrecht am Telefon: je Katheter eine Zeile, die Länge des Strichs entspricht der Liegedauer */}
      <ol className="md:hidden m-0 px-3 pb-3 list-none katheter-senkrecht" role="img" aria-label={beschreibung}>
        {[...reihe].reverse().map((k) => {
          const hoehe = Math.max(2.5, Math.min(9, ((k.liegedauer_tage ?? 0) / Math.max(1, s.bis - s.von)) * 18 + 2.5));
          const aktiv = k.komplikationen.filter((x) => x.aktiv);
          const dauer = Math.max(1, (k.entfernt_am ? tagNr(k.entfernt_am) : heute) - tagNr(k.anlage_am));
          return (
            <li key={k.id} className="katheter-senkrecht-eintrag" data-testid="katheter-balken-zeile">
              <div className="katheter-senkrecht-spur" style={{ height: `${hoehe}rem` }}>
                <button type="button" data-testid="katheter-balken" title={balkenTitel(k)} aria-label={balkenTitel(k)}
                  className={cx("katheter-balken senkrecht", k.liegt && "liegt", String(k.id) === wahl && "gewaehlt")} onClick={() => onWahl(k.id)} />
                {aktiv.map((x) => (
                  <Marke key={x.id} x={x} onWahl={() => onWahl(k.id)}
                    stil={{ top: `${100 - ((tagNr(x.datum) - tagNr(k.anlage_am)) / dauer) * 100}%` }} />
                ))}
              </div>
              <div className="flex flex-col gap-0.5 min-w-0 text-[0.8125rem]">
                <span className="font-medium text-sm">{k.typ_name}{k.lage ? <span className="gedaempft font-normal"> · {k.lage}</span> : null}</span>
                <span className="num">{k.entfernt_am ? datum(k.entfernt_am) : "liegt"} ↑</span>
                <span className="gedaempft">{tage(k.liegedauer_tage)}{aktiv.length ? ` · ${aktiv.length === 1 ? "1 Komplikation" : `${aktiv.length} Komplikationen`}` : ""}</span>
                <span className="num">{datum(k.anlage_am)} Anlage</span>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="px-5 max-md:px-3 pb-3 flex items-center gap-x-4 gap-y-1 flex-wrap text-[0.75rem] gedaempft" aria-hidden="true">
        <span className="inline-flex items-center gap-1.5"><span className="katheter-legende-balken liegt" /> liegt</span>
        <span className="inline-flex items-center gap-1.5"><span className="katheter-legende-balken" /> entfernt</span>
        <span className="inline-flex items-center gap-1.5"><span className="katheter-marke legende infektion" /> Katheterinfektion</span>
        <span className="inline-flex items-center gap-1.5"><span className="katheter-marke legende" /> andere Komplikation</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- Liste

type Aktionen = {
  bearbeiten: boolean;
  onAendern: (k: KatheterT) => void; onEntfernen: (k: KatheterT) => void; onKomplikation: (k: KatheterT, x: KatheterKomplikation | null) => void;
  onZuruecknehmen: (z: { katheter?: KatheterT; komplikation?: KatheterKomplikation }) => void;
};

function Komplikationen({ k, a }: { k: KatheterT; a: Aktionen }) {
  if (!k.komplikationen.length) return <span className="gedaempft">—</span>;
  return (
    <ul className="m-0 p-0 list-none flex flex-col gap-1">
      {k.komplikationen.map((x) => (
        <li key={x.id} className={cx("flex items-start gap-1.5 flex-wrap", !x.aktiv && "gedaempft")} data-testid="katheter-komplikation">
          <span className={cx("katheter-marke legende mt-1", x.ist_infektion && "infektion")} aria-hidden="true" />
          <span className={cx("min-w-0", !x.aktiv && "line-through")}>
            <span className="num">{datum(x.datum)}</span> {x.art_name}{x.notiz ? <span className="gedaempft"> · {x.notiz}</span> : null}
            <FirmaMarke kurz={x.firma_kurz} className="ml-1.5" />
          </span>
          {a.bearbeiten && x.aktiv && k.aktiv ? (
            <span className="inline-flex gap-0.5">
              <Knopf klein variante="geist" icon="stift" aria-label={`Komplikation vom ${datum(x.datum)} bearbeiten`} title="Bearbeiten"
                onClick={() => a.onKomplikation(k, x)} />
              <Knopf klein variante="geist" icon="x" aria-label={`Komplikation vom ${datum(x.datum)} zurücknehmen`} title="Als falsch erfasst zurücknehmen"
                onClick={() => a.onZuruecknehmen({ komplikation: x })} />
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function Knoepfe({ k, a }: { k: KatheterT; a: Aktionen }) {
  if (!a.bearbeiten || !k.aktiv) return null;
  return (
    <span className="flex items-center gap-1 justify-end flex-wrap">
      <Knopf klein variante="geist" icon="plus" onClick={() => a.onKomplikation(k, null)} aria-label={`Komplikation am ${k.typ_name} erfassen`}>Komplikation</Knopf>
      {k.liegt ? <Knopf klein variante="geist" onClick={() => a.onEntfernen(k)} aria-label={`${k.typ_name} entfernen`}>Entfernen</Knopf> : null}
      <Knopf klein variante="geist" icon="stift" onClick={() => a.onAendern(k)} aria-label={`${k.typ_name} vom ${datum(k.anlage_am)} bearbeiten`} title="Bearbeiten" />
      <Knopf klein variante="geist" icon="x" onClick={() => a.onZuruecknehmen({ katheter: k })} aria-label={`${k.typ_name} vom ${datum(k.anlage_am)} zurücknehmen`}
        title="Als falsch erfasst zurücknehmen" />
    </span>
  );
}

function Stand({ k }: { k: KatheterT }) {
  if (k.liegt) return <Chip art="ok">liegt</Chip>;
  return <span className="text-[0.8125rem]"><span className="num">{datum(k.entfernt_am)}</span>{k.entfernungsgrund_name ? <span className="block gedaempft">{k.entfernungsgrund_name}</span> : null}</span>;
}

function Liste({ liste, wahl, a, testid }: { liste: KatheterT[]; wahl: string; a: Aktionen; testid: string }) {
  const markiert = useRef<HTMLElement | null>(null);
  useEffect(() => { markiert.current?.scrollIntoView({ block: "center", behavior: "smooth" }); }, [wahl]);
  const merke = (k: KatheterT) => (el: HTMLElement | null) => { if (String(k.id) === wahl && el && el.offsetParent) markiert.current = el; };
  return (
    <div data-testid={testid}>
      <div className="max-md:hidden overflow-x-auto">
        <table className="tabelle tabelle-fest">
          <thead>
            <tr>
              <th className="th pl-5">Typ / Lage</th>
              <th className="th">Anlage</th>
              <th className="th">Entfernt</th>
              <th className="th text-right">Liegedauer</th>
              <th className="th">Komplikationen</th>
              <th className="th">Notiz</th>
              <th className="th pr-5"><span className="sr-only">Aktionen</span></th>
            </tr>
          </thead>
          <tbody>
            {liste.map((k) => (
              <tr key={k.id} ref={merke(k)} data-testid="katheter-zeile" className={cx(String(k.id) === wahl && "gewaehlt", !k.aktiv && "gedaempft")}>
                <td className="td pl-5 align-top">
                  <span className={cx("font-medium flex items-center gap-1.5 flex-wrap", !k.aktiv && "line-through")}>{k.typ_name}<FirmaMarke kurz={k.firma_kurz} /></span>
                  {k.lage ? <span className="block text-[0.8125rem] gedaempft">{k.lage}</span> : null}
                  {!k.aktiv ? <span className="block text-[0.8125rem]">als falsch erfasst zurückgenommen</span> : null}
                </td>
                <td className="td align-top num whitespace-nowrap">{datum(k.anlage_am)}</td>
                <td className="td align-top"><Stand k={k} /></td>
                <td className="td align-top text-right num whitespace-nowrap">{tage(k.liegedauer_tage)}</td>
                <td className="td align-top text-[0.8125rem]"><Komplikationen k={k} a={a} /></td>
                <td className="td align-top text-[0.8125rem]">{k.notiz || "—"}</td>
                <td className="td pr-5 align-top"><Knoepfe k={k} a={a} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="md:hidden m-0 p-0 list-none">
        {liste.map((k) => (
          <li key={k.id} ref={merke(k)} data-testid="katheter-karte"
            className={cx("px-3 py-3 border-t border-fein flex flex-col gap-1.5 min-w-0", String(k.id) === wahl && "bg-akzent-weich", !k.aktiv && "gedaempft")}>
            <div className="flex items-start justify-between gap-2 min-w-0">
              <span className="flex flex-col gap-0.5 min-w-0">
                <span className={cx("font-medium flex items-center gap-1.5 flex-wrap", !k.aktiv && "line-through")}>{k.typ_name}<FirmaMarke kurz={k.firma_kurz} /></span>
                {k.lage ? <span className="text-[0.8125rem] gedaempft break-words">{k.lage}</span> : null}
              </span>
              <Stand k={k} />
            </div>
            <span className="text-[0.8125rem] num">{datum(k.anlage_am)} – {k.entfernt_am ? datum(k.entfernt_am) : "heute"} · {tage(k.liegedauer_tage)}</span>
            {k.komplikationen.length ? <div className="text-[0.8125rem]"><Komplikationen k={k} a={a} /></div> : null}
            {k.notiz ? <span className="text-[0.8125rem] break-words">{k.notiz}</span> : null}
            <Knoepfe k={k} a={a} />
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- Seite

function Kennzahl({ titel, children, unter, testid }: { titel: ReactNode; children: ReactNode; unter?: ReactNode; testid: string }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-0 px-5 max-md:px-3 py-3 border-l border-rand first:border-l-0 max-sm:border-l-0 max-sm:border-t max-sm:first:border-t-0" data-testid={testid}>
      <span className="lbl text-[0.78rem] gedaempft font-medium">{titel}</span>
      <span className="text-[0.9375rem] font-medium min-h-[1.375rem]">{children}</span>
      {unter ? <span className="text-[0.8125rem] gedaempft">{unter}</span> : null}
    </div>
  );
}

export function Katheter() {
  const { patient, bearbeiten } = useAkte();
  const melden = useHinweis();
  const neuLaden = useNeuLaden();
  const [wahl, setWahl] = useWahl("eintrag");
  const [dialog, setDialog] = useState<{ offen: boolean; katheter: KatheterT | null; entfernen?: boolean }>({ offen: false, katheter: null });
  const [kompl, setKompl] = useState<{ offen: boolean; katheter: KatheterT | null; komplikation: KatheterKomplikation | null }>(
    { offen: false, katheter: null, komplikation: null });
  const [zurueck, setZurueck] = useState<{ katheter?: KatheterT; komplikation?: KatheterKomplikation } | null>(null);
  const [zurueckgenommeneAn, setZurueckgenommene] = useState(false);

  const katheter = useQuery({
    queryKey: ["katheter", patient.id, "liste"],
    queryFn: () => api<KatheterT[]>(`katheter/?patient=${patient.id}`),
  });
  const kennzahlen = useQuery({
    queryKey: ["katheter", patient.id, "kennzahlen"],
    queryFn: () => api<KatheterKennzahlen>(`katheter/kennzahlen/?patient=${patient.id}`),
  });
  const zuruecknehmen = useMutation({
    mutationFn: (z: { katheter?: KatheterT; komplikation?: KatheterKomplikation }) => z.katheter
      ? api(`katheter/${z.katheter.id}/`, { method: "PATCH", body: { aktiv: false } })
      : api(`katheter-komplikationen/${z.komplikation!.id}/`, { method: "PATCH", body: { aktiv: false } }),
    onSuccess: () => { neuLaden(); melden("Zurückgenommen – bleibt im Verlauf der Akte."); setZurueck(null); },
  });

  const alle = katheter.data ?? [];
  const aktiv = alle.filter((k) => k.aktiv);
  const zurueckgenommen = alle.filter((k) => !k.aktiv);
  const z = kennzahlen.data;
  const a: Aktionen = {
    bearbeiten,
    onAendern: (k) => setDialog({ offen: true, katheter: k }),
    onEntfernen: (k) => setDialog({ offen: true, katheter: k, entfernen: true }),
    onKomplikation: (k, x) => setKompl({ offen: true, katheter: k, komplikation: x }),
    onZuruecknehmen: (zz) => { zuruecknehmen.reset(); setZurueck(zz); },
  };
  const rate = z?.infektionen_je_1000 ?? null;

  return (
    <>
      <Karte className="overflow-hidden min-w-0" data-testid="katheter">
        <div className="px-5 max-md:px-3 pt-4 pb-2 flex items-center justify-between gap-3 flex-wrap">
          <h2 className="lbl m-0 text-[0.9375rem] flex items-center gap-2">
            Katheter-Historie{aktiv.length ? <Chip>{aktiv.length}</Chip> : null}
          </h2>
          {bearbeiten ? <Knopf variante="pri" icon="plus" onClick={() => setDialog({ offen: true, katheter: null })}>Katheter</Knopf> : null}
        </div>

        {/* Kennzahlen: feste Höhe auch während des Ladens (nichts springt) */}
        <div className="grid grid-cols-1 sm:grid-cols-3 border-t border-rand" data-testid="katheter-kennzahlen">
          <Kennzahl titel="Aktueller Katheter" testid="katheter-aktuell"
            unter={z?.aktuell ? `seit ${datum(z.aktuell.anlage_am)}${z.aktuell.lage ? ` · ${z.aktuell.lage}` : ""}` : undefined}>
            {kennzahlen.isPending ? <span className="gedaempft">…</span>
              : z?.aktuell ? <>{z.aktuell.typ} · <span className="num">{tage(z.aktuell.liegedauer_tage)}</span></>
              : <span className="gedaempft">{z?.kerndaten_typ ? `${z.kerndaten_typ} (laut Kerndaten)` : "keiner liegt"}</span>}
          </Kennzahl>
          <Kennzahl titel={<Begriff erklaerung={"Katheterinfektionen geteilt durch die Summe der Liegetage aller Katheter, "
            + "mal 1000 – die übliche Kennzahl in der heimparenteralen Ernährung. Gezählt werden Komplikationen, deren Art "
            + "„Infektion“ im Namen trägt."}>Infektionen je 1000 Kathetertage</Begriff>} testid="katheter-rate"
            unter={z ? `${z.infektionen === 1 ? "1 Infektion" : `${zahl(z.infektionen)} Infektionen`} in ${tage(z.kathetertage)}` : undefined}>
            {kennzahlen.isPending ? <span className="gedaempft">…</span> : rate === null ? <span className="gedaempft">—</span> : <span className="num">{zahl(rate, 2)}</span>}
          </Kennzahl>
          <Kennzahl titel="Katheter erfasst" testid="katheter-anzahl"
            unter={z && z.offen > 0 ? `${z.offen === 1 ? "1 liegt" : `${z.offen} liegen`}` : undefined}>
            {kennzahlen.isPending ? <span className="gedaempft">…</span> : <span className="num">{zahl(z?.anzahl ?? 0)}</span>}
          </Kennzahl>
        </div>

        {/* Hinweise */}
        {z?.hinweise.length || z?.anlagedatum_fehlt ? (
          <div className="px-5 max-md:px-3 pb-3 flex flex-col gap-2" data-testid="katheter-hinweise">
            {z.hinweise.map((h) => (
              <Meldung key={h} art="warn">
                <span className="inline-flex items-start gap-1.5"><Icon name="warnung" /> {h}. Bitte beim früheren Katheter
                  „Entfernen“ wählen und Datum und Grund eintragen – EPM beendet ihn nicht von selbst.</span>
              </Meldung>
            ))}
            {z.anlagedatum_fehlt ? (
              <Meldung art="warn">
                <span className="inline-flex items-start gap-1.5 flex-wrap"><Icon name="warnung" />
                  <span>Anlagedatum nicht erfasst – bitte nachtragen. In den Kerndaten steht „{z.kerndaten_typ}“, in der
                    Katheter-Historie aber noch kein Katheter.</span>
                  {bearbeiten ? <Knopf klein onClick={() => setDialog({ offen: true, katheter: null })}>Anlagedatum nachtragen</Knopf> : null}
                </span>
              </Meldung>
            ) : null}
          </div>
        ) : null}

        <section className="border-t border-rand">
          <h3 className="lbl m-0 px-5 max-md:px-3 pt-3 pb-2 text-[0.8125rem]">Zeitachse</h3>
          {katheter.isPending ? <div className="px-5 pb-4 min-h-[6rem]"><Laden /></div>
            : aktiv.length ? <Zeitachse liste={aktiv} wahl={wahl} onWahl={(id) => setWahl(String(id))} />
            : <p className="m-0 px-5 max-md:px-3 pb-4 text-sm gedaempft">
                {z?.anlagedatum_fehlt ? "Die Zeitachse erscheint, sobald das Anlagedatum nachgetragen ist." : "Noch kein Katheter eingetragen."}
              </p>}
        </section>

        <section className="border-t border-rand">
          <h3 className="lbl m-0 px-5 max-md:px-3 pt-3 pb-2 text-[0.8125rem]">Alle Katheter</h3>
          {katheter.isPending ? null : aktiv.length ? <Liste liste={aktiv} wahl={wahl} a={a} testid="katheter-liste" />
            : <p className="m-0 px-5 max-md:px-3 pb-4 text-sm gedaempft">Keine Einträge.</p>}
        </section>
        {zurueckgenommen.length ? (
          <section className="border-t border-rand">
            <button type="button" className="w-full text-left px-5 max-md:px-3 py-2.5 bg-transparent border-0 text-[0.8125rem] gedaempft cursor-pointer hover:bg-fein"
              aria-expanded={zurueckgenommeneAn} onClick={() => setZurueckgenommene((b) => !b)} data-testid="zurueckgenommene-umschalten">
              {zurueckgenommeneAn ? "Zurückgenommene ausblenden" : `Als falsch erfasst zurückgenommen (${zurueckgenommen.length}) anzeigen`}
            </button>
            {zurueckgenommeneAn ? <Liste liste={zurueckgenommen} wahl={wahl} a={a} testid="katheter-zurueckgenommen" /> : null}
          </section>
        ) : null}
      </Karte>

      {bearbeiten ? <>
        <KatheterDialog katheter={dialog.katheter} entfernen={dialog.entfernen} offen={dialog.offen}
          onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} />
        <KomplikationDialog katheter={kompl.katheter} komplikation={kompl.komplikation} offen={kompl.offen}
          onOffen={(o) => setKompl((d) => ({ ...d, offen: o }))} />
        <Bestaetigen offen={!!zurueck} onOffen={(o) => { if (!o) setZurueck(null); }} knopf="Zurücknehmen"
          titel={zurueck?.katheter ? "Katheter zurücknehmen" : "Komplikation zurücknehmen"}
          text={zurueck?.katheter
            ? <>„{zurueck.katheter.typ_name}“ vom {datum(zurueck.katheter.anlage_am)} als falsch erfasst zurücknehmen? Er zählt dann in keiner Kennzahl mehr, bleibt aber im Verlauf der Akte. Die Kerndaten bleiben unverändert.</>
            : <>„{zurueck?.komplikation?.art_name}“ vom {datum(zurueck?.komplikation?.datum)} als falsch erfasst zurücknehmen? Sie bleibt im Verlauf der Akte.</>}
          laedt={zuruecknehmen.isPending} fehler={zuruecknehmen.error} onJa={() => zurueck && zuruecknehmen.mutate(zurueck)} />
      </> : null}
    </>
  );
}
