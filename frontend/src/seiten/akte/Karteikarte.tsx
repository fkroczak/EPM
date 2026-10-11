/**
 * Karteikarte (Ansicht „Karteikarte“, Wunsch 08.10.2026): alle Einträge der Akte chronologisch auf einer Seite – wie in
 * einer Arztsoftware – mit Kürzel je Art, Filter und Zeitraum. Darunter die Kürzelzeile: „K Text“ öffnet einen neuen
 * Kontakt mit diesem Text, „G 61,2“ das Gewicht, „T“ einen Termin, „P“ einen neuen Infusionsplan. Gespeichert wird
 * immer erst im jeweiligen Formular (Kontakte sind nach dem Speichern nicht mehr änderbar). Ein Klick auf eine Zeile öffnet
 * genau diesen Eintrag in seinem Reiter; offene Termine öffnen „Termin bearbeiten“ (08.10.2026).
 */
import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { abfrage, alle, api } from "@/lib/api";
import { datum, kg, uhrzeit, zahl } from "@/lib/format";
import { GEWICHTSQUELLEN, TERMINARTEN } from "@/lib/typen";
import type { Bericht, BiaMessung, Diagnose, Dokument, Gewicht, Kontakt, Laborbefund, Plan, Termin } from "@/lib/typen";
import { Auswahl, Chip, Karte, Laden, Leer, cx } from "@/components/ui/basis";
import { klartext } from "@/components/Editor";
import { useAkte } from "./Akte";

type Art = "K" | "G" | "T" | "P" | "L" | "D" | "DOK" | "B";

const ARTEN: { art: Art; text: string }[] = [
  { art: "K", text: "Kontakte" }, { art: "G", text: "Gewicht" }, { art: "T", text: "Termine" }, { art: "P", text: "Pläne" },
  { art: "L", text: "Labor und BIA" }, { art: "D", text: "Diagnosen" }, { art: "DOK", text: "Dokumente" }, { art: "B", text: "Berichte" },
];

const ZEITRAEUME: Record<string, { text: string; monate: number | null }> = {
  m12: { text: "letzte 12 Monate", monate: 12 },
  j3: { text: "letzte 3 Jahre", monate: 36 },
  alle: { text: "alle Einträge", monate: null },
};

const MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];

type Eintrag = {
  schluessel: string;
  art: Art;
  /** Kürzel in der Zeile (BIA und WV weichen von der Filterart ab) */
  kuerzel: string;
  /** ISO-Datum oder -Zeitpunkt zum Sortieren */
  wann: string;
  zeit?: string;
  text: string;
  zusatz?: string;
  person: string | null;
  durchgestrichen?: boolean;
  zu: string;
  /** offener Termin: Klick öffnet „Termin bearbeiten“ statt die Seite zu wechseln */
  termin?: Termin;
};

function nurDatum(wert: string) {
  return wert.slice(0, 10);
}

function grenze(monate: number | null): string {
  if (monate === null) return "";
  const d = new Date();
  d.setMonth(d.getMonth() - monate);
  return d.toISOString().slice(0, 10);
}

/** Kürzelzeile: „K Text“, „G 61,2“, „T“, „WV“, „P“ */
function zerlegen(eingabe: string): { kuerzel: string; rest: string } | null {
  const m = /^\s*(WV|DOK|[A-Za-z])\b\s*(.*)$/s.exec(eingabe);
  return m ? { kuerzel: m[1].toUpperCase(), rest: m[2].trim() } : null;
}

export function Karteikarte() {
  const { patient, erfassen, planen, terminAnlegen, terminAendern, kontaktErfassen, gewichtErfassen } = useAkte();
  const navigate = useNavigate();
  const basis = `/patienten/${patient.id}`;
  const [filter, setFilter] = useState<Art | "">("");
  const [zeitraum, setZeitraum] = useState("m12");
  const [befehl, setBefehl] = useState("");
  const [hinweis, setHinweis] = useState("");
  const schluessel = (quelle: string) => ["patient", patient.id, "kartei", quelle];
  const nebenbei = { retry: false, staleTime: 30_000 } as const;
  const kontakte = useQuery({ queryKey: schluessel("kontakte"), queryFn: () => alle<Kontakt>(`kontakte/${abfrage({ patient: patient.id })}`), ...nebenbei });
  const gewichte = useQuery({ queryKey: schluessel("gewichte"), queryFn: () => alle<Gewicht>(`gewichte/${abfrage({ patient: patient.id })}`), ...nebenbei });
  const termine = useQuery({ queryKey: schluessel("termine"), queryFn: () => alle<Termin>(`termine/${abfrage({ patient: patient.id })}`), ...nebenbei });
  const plaene = useQuery({ queryKey: schluessel("plaene"), queryFn: () => alle<Plan>(`infusionsplaene/${abfrage({ patient: patient.id })}`), ...nebenbei });
  const labor = useQuery({ queryKey: schluessel("labor"), queryFn: () => api<Laborbefund[]>(`laborbefunde/?patient=${patient.id}`), ...nebenbei });
  const bia = useQuery({ queryKey: schluessel("bia"), queryFn: () => api<BiaMessung[]>(`bia-messungen/?patient=${patient.id}`), ...nebenbei });
  const diagnosen = useQuery({ queryKey: schluessel("diagnosen"), queryFn: () => api<Diagnose[]>(`diagnosen/?patient=${patient.id}`), ...nebenbei });
  const dokumente = useQuery({ queryKey: schluessel("dokumente"), queryFn: () => alle<Dokument>(`dokumente/${abfrage({ patient: patient.id, ausgeblendet: "false" })}`), ...nebenbei });
  const berichte = useQuery({ queryKey: schluessel("berichte"), queryFn: () => api<Bericht[]>(`berichte/?patient=${patient.id}`), ...nebenbei });
  const quellen = [kontakte, gewichte, termine, plaene, labor, bia, diagnosen, dokumente, berichte];
  const laedt = quellen.some((q) => q.isLoading);
  const fehlen = quellen.filter((q) => q.isError).length;

  const eintraege = useMemo<Eintrag[]>(() => {
    const e: Eintrag[] = [];
    for (const k of kontakte.data ?? []) {
      e.push({
        schluessel: `k${k.id}`, art: "K", kuerzel: "K", wann: k.zeitpunkt, zeit: uhrzeit(k.zeitpunkt),
        text: `${k.art_name ? `${k.art_name}: ` : ""}${klartext(k.text)}`,
        zusatz: k.storniert_am ? `storniert${k.storno_grund ? ` – ${k.storno_grund}` : ""}` : undefined,
        person: k.erfasst_von_name, durchgestrichen: !!k.storniert_am, zu: `${basis}/kontakte?kontakt=${k.id}`,
      });
    }
    for (const g of gewichte.data ?? []) {
      e.push({
        schluessel: `g${g.id}`, art: "G", kuerzel: "G", wann: g.gemessen_am,
        text: `${kg(g.gewicht_kg)}${g.datum_ungenau ? " (Datum ungefähr)" : ""} · ${GEWICHTSQUELLEN[g.quelle] ?? g.quelle}`,
        zusatz: g.notiz || undefined, person: g.erfasst_von_name, zu: basis,
      });
    }
    for (const t of termine.data ?? []) {
      const wv = t.art === "wiedervorlage" || t.art === "rueckruf";
      e.push({
        schluessel: `t${t.id}`, art: "T", kuerzel: wv ? "WV" : "T", wann: t.faellig_am, zeit: t.uhrzeit ? t.uhrzeit.slice(0, 5) : undefined,
        text: `${TERMINARTEN[t.art] ?? t.art}${t.titel ? `: ${t.titel}` : ""}${t.ort_name ? ` · ${t.ort_name}` : ""}`,
        zusatz: t.erledigt_am ? `erledigt am ${datum(t.erledigt_am)}` : t.ausgeblendet ? "offen · ausgeblendet" : "offen",
        person: t.angelegt_von_name, zu: basis, termin: t.erledigt_am ? undefined : t,
      });
    }
    for (const pl of plaene.data ?? []) {
      const status = pl.status === "entwurf" ? "Entwurf" : pl.status === "aktuell" ? "aktuell" : "abgelöst";
      e.push({
        schluessel: `p${pl.id}`, art: "P", kuerzel: "P", wann: pl.gueltig_ab,
        text: `Infusionsplan ab ${datum(pl.gueltig_ab)} · ${zahl(pl.kcal)} kcal${pl.gesamtvolumen_ml ? ` · ${zahl(pl.gesamtvolumen_ml)} ml` : ""}${pl.laufzeit_h ? ` · ${zahl(pl.laufzeit_h)} h` : ""}`,
        zusatz: pl.freigegeben_von_name ? `${status} · freigegeben von ${pl.freigegeben_von_name}` : status,
        person: pl.freigegeben_von_name, zu: `${basis}/plaene?plan=${pl.id}`,
      });
    }
    for (const l of labor.data ?? []) {
      e.push({
        schluessel: `l${l.id}`, art: "L", kuerzel: "L", wann: l.abgenommen_am,
        text: `Labor${l.labor ? ` ${l.labor}` : ""}: ${zahl(l.anzahl_werte)} Werte`,
        zusatz: l.beurteilung ? klartext(l.beurteilung) : undefined, person: l.erfasst_von_name, zu: `${basis}/labor?befund=${l.id}`,
      });
    }
    for (const b of bia.data ?? []) {
      const werte = [b.bcm_kg != null ? `BCM ${zahl(b.bcm_kg, 1)} kg` : "", b.fettmasse_kg != null ? `Fettmasse ${zahl(b.fettmasse_kg, 1)} kg` : "",
        b.ecw_prozent != null ? `ECW ${zahl(b.ecw_prozent, 1)} %` : ""].filter(Boolean).join(" · ");
      e.push({
        schluessel: `b${b.id}`, art: "L", kuerzel: "BIA", wann: b.gemessen_am, text: `BIA-Messung${werte ? `: ${werte}` : ""}`,
        zusatz: b.beurteilung ? klartext(b.beurteilung) : undefined, person: b.erfasst_von_name, zu: `${basis}/bia?messung=${b.id}`,
      });
    }
    for (const d of diagnosen.data ?? []) {
      e.push({
        schluessel: `d${d.id}`, art: "D", kuerzel: "D", wann: d.seit ?? d.angelegt_am,
        text: d.anzeige || [d.icd_code, d.bezeichnung].filter(Boolean).join(" "),
        zusatz: d.aktiv ? undefined : `beendet${d.beendet_am ? ` am ${datum(d.beendet_am)}` : ""}`,
        person: d.angelegt_von_name, durchgestrichen: !d.aktiv, zu: `${basis}/diagnosen?eintrag=${d.id}`,
      });
    }
    for (const d of dokumente.data ?? []) {
      e.push({
        schluessel: `o${d.id}`, art: "DOK", kuerzel: "DOK", wann: d.datum ?? d.hochgeladen_am,
        text: `${d.typ_name ?? "Dokument"}: ${d.titel || d.originalname}`, zusatz: d.notiz || undefined,
        person: d.hochgeladen_von_name, zu: `${basis}/dokumente?dokument=${d.id}`,
      });
    }
    for (const b of berichte.data ?? []) {
      e.push({
        schluessel: `r${b.id}`, art: "B", kuerzel: "B", wann: b.datum,
        text: `${b.art_name ?? "Bericht"}: ${b.titel}${b.empfaenger ? ` · an ${b.empfaenger}` : ""}`, zusatz: b.status_name,
        person: b.freigegeben_von_name ?? b.erstellt_von_name, zu: `${basis}/berichte?bericht=${b.id}`,
      });
    }
    // neueste zuerst; am selben Tag Einträge mit Uhrzeit vor denen ohne
    return e.sort((a, b) => b.wann.localeCompare(a.wann));
  }, [basis, kontakte.data, gewichte.data, termine.data, plaene.data, labor.data, bia.data, diagnosen.data, dokumente.data, berichte.data]);

  const ab = grenze(ZEITRAEUME[zeitraum].monate);
  const sichtbar = eintraege.filter((e) => (!filter || e.art === filter) && (!ab || nurDatum(e.wann) >= ab));
  const anzahl = (art: Art) => eintraege.filter((e) => e.art === art && (!ab || nurDatum(e.wann) >= ab)).length;

  const ausfuehren = (ev: FormEvent) => {
    ev.preventDefault();
    const b = zerlegen(befehl);
    setHinweis("");
    if (!b) return;
    if (b.kuerzel === "K") {
      kontaktErfassen(b.rest);
    } else if (b.kuerzel === "G") {
      gewichtErfassen(b.rest);
    } else if (b.kuerzel === "T" || b.kuerzel === "WV") {
      terminAnlegen();
    } else if (b.kuerzel === "P") {
      if (!planen) { setHinweis("Neue Infusionspläne darf hier nur anlegen, wer das Recht dazu hat."); return; }
      navigate(`${basis}/plaene/neu`);
    } else {
      setHinweis(`Unbekanntes Kürzel „${b.kuerzel}“. Möglich sind K, G, T, WV und P.`);
      return;
    }
    setBefehl("");
  };

  let monat = "";
  return (
    <Karte className="flex flex-col min-w-0 overflow-hidden" data-testid="karteikarte">
      <div className="flex items-center gap-2 flex-wrap px-4 py-3 border-b border-rand">
        <h2 className="lbl m-0 mr-1.5">Karteikarte</h2>
        <div role="group" aria-label="Einträge filtern" className="flex items-center gap-1.5 flex-wrap">
          <button type="button" className={cx("chip cursor-pointer", !filter && "akzent")} aria-pressed={!filter} onClick={() => setFilter("")}>Alle</button>
          {ARTEN.map((a) => (
            <button key={a.art} type="button" className={cx("chip cursor-pointer", filter === a.art && "akzent")} aria-pressed={filter === a.art}
              onClick={() => setFilter(filter === a.art ? "" : a.art)}>
              <span className="num font-semibold">{a.art}</span> {a.text} <span className="num opacity-85">{zahl(anzahl(a.art))}</span>
            </button>
          ))}
        </div>
        <label className="ml-auto flex items-center gap-2 text-[0.8125rem] gedaempft">
          Zeitraum
          <Auswahl aria-label="Zeitraum" className="w-auto" value={zeitraum} onChange={(e) => setZeitraum(e.target.value)}>
            {Object.entries(ZEITRAEUME).map(([k, z]) => <option key={k} value={k}>{z.text}</option>)}
          </Auswahl>
        </label>
      </div>

      {erfassen ? (
        <form className="flex items-center gap-3 flex-wrap px-4 py-3 border-b border-rand bg-grund" onSubmit={ausfuehren} data-testid="kuerzelzeile">
          <input className="inp num grow min-w-[16rem]" aria-label="Kürzelzeile" value={befehl} onChange={(e) => setBefehl(e.target.value)}
            placeholder="K Text · G 61,2 · T · P – Eingabetaste öffnet das Formular" />
          <span className="text-xs gedaempft">
            <span className="num font-semibold">K</span> Kontakt · <span className="num font-semibold">G</span> Gewicht ·{" "}
            <span className="num font-semibold">T</span>/<span className="num font-semibold">WV</span> Termin ·{" "}
            <span className="num font-semibold">P</span> Plan
          </span>
          {hinweis ? <span className="w-full text-[0.8125rem] text-warn" role="alert">{hinweis}</span> : null}
        </form>
      ) : null}

      {laedt ? <div className="p-4"><Laden /></div> : sichtbar.length === 0 ? (
        <div className="p-4"><Leer>Keine Einträge im gewählten Zeitraum.</Leer></div>
      ) : (
        <table className="tabelle" data-testid="karteieintraege">
          <tbody>
            {sichtbar.map((e) => {
              const m = nurDatum(e.wann).slice(0, 7);
              const kopf = m !== monat;
              monat = m;
              return [
                kopf ? (
                  <tr key={`m${m}`} className="bg-fein">
                    <td colSpan={4} className="px-4 py-1 text-xs font-semibold gedaempft tracking-[.03em]">
                      {MONATE[Number(m.slice(5, 7)) - 1]} {m.slice(0, 4)}
                    </td>
                  </tr>
                ) : null,
                <tr key={e.schluessel} data-testid="karteieintrag" data-art={e.art} className="cursor-pointer" onClick={() => (e.termin && erfassen ? terminAendern(e.termin) : navigate(e.zu))}>
                  <td className="td num whitespace-nowrap w-[1%] pl-4 align-top">{datum(nurDatum(e.wann))}{e.zeit ? <span className="gedaempft"> {e.zeit}</span> : null}</td>
                  <td className="td w-[1%] align-top"><Chip className={cx("num font-semibold justify-center min-w-[2.75rem]", `kartei-${e.art}`)}>{e.kuerzel}</Chip></td>
                  <td className="td align-top">
                    <span className={cx(e.durchgestrichen && "line-through gedaempft")}>{e.text}</span>
                    {e.zusatz ? <span className="gedaempft"> · {e.zusatz}</span> : null}
                  </td>
                  <td className="td text-right gedaempft whitespace-nowrap w-[1%] pr-4 align-top text-[0.8125rem]">{e.person ?? ""}</td>
                </tr>,
              ];
            })}
          </tbody>
        </table>
      )}
      {fehlen ? <span className="px-4 py-2 text-xs gedaempft border-t border-rand">Ein Teil der Einträge konnte nicht geladen werden ({fehlen} von {quellen.length} Bereichen).</span> : null}
    </Karte>
  );
}
