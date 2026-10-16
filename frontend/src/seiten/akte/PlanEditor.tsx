/** Entwurf 7 · Neuer Infusionsplan bzw. Entwurf bearbeiten: vorbelegt, Änderungen markiert, kcal wie im Altsystem. */
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, alle, api, apiDatei } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useEinstellungen, usePraeparate } from "@/lib/daten";
import { datum, eingabeDatum, eingabeZahl, heuteIso, kg, nummer, uhrzeit, zahl } from "@/lib/format";
import { useStufe } from "@/lib/stufen";
import type { Stufe } from "@/lib/stufen";
import { PPI_ZEITEN, PROTONENPUMPENHEMMER, ppiZeiten } from "@/lib/typen";
import type { Plan, Praeparat } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, KnopfLink, Laden, Meldung, cx } from "@/components/ui/basis";
import { Spalten } from "@/components/ui/spalten";
import { PdfLeser } from "@/components/PdfAnsicht";
import { PdfDialog } from "@/components/PdfDialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Begriff } from "@/components/ui/Begriff";
import { Icon } from "@/components/ui/icon";
import { anlageOeffnen } from "@/seiten/admin/Anlagen";
import { Editor } from "@/components/Editor";
import { name, useAkte } from "./Akte";

const ZAHLEN = ["basis_ml", "glucose_g", "aminosaeuren_g", "lipide_g", "albumin_ml", "natrium_mmol", "kalium_mmol",
  "phosphat_mmol", "calcium_mmol", "magnesium_mmol", "laufzeit_h", "tage_pro_woche", "zusatz_tage_pro_woche",
  "freie_tage_pro_woche", "pantozol_tage", "kcal_manuell"] as const;
const AUSWAHL = ["basis_praeparat", "glucose_praeparat", "aminosaeuren_praeparat", "lipide_praeparat", "albumin_praeparat",
  "spurenelemente", "katheterschutz"] as const;
type ZahlFeld = (typeof ZAHLEN)[number];
type AuswahlFeld = (typeof AUSWAHL)[number];
/** Weitere Bestandteile (Erweiterungen): beliebiges Präparat aus den Auswahllisten mit Menge, Einheit, Häufigkeit */
type Position = { praeparat: string; menge: string; einheit: string; haeufigkeit: string; bemerkung: string };
type Formular = Record<ZahlFeld | AuswahlFeld, string> & {
  vitamine: number[]; bemerkung: string; pantozol_stufe: string; gueltig_ab: string; positionen: Position[];
};
const EINHEITEN = ["ml", "g", "mg", "µg", "mmol", "IE", "Amp.", "Stück"];

// Energie wie im Altsystem (EPM_infuplan.php): Glucose und Aminosäuren 4 kcal/g, Lipide 9,15 kcal/g;
// Humanalbumin wird dort in ml erfasst und zählt nicht zur Energie (Festlegung 01.10.2026)
const MAKRO: { feld: "glucose" | "aminosaeuren" | "lipide" | "albumin"; menge: ZahlFeld; einheit: string; text: string; kategorie: string; kcal: number | null }[] = [
  { feld: "glucose", menge: "glucose_g", einheit: "g", text: "Glucose", kategorie: "glucose", kcal: 4 },
  { feld: "aminosaeuren", menge: "aminosaeuren_g", einheit: "g", text: "Aminosäuren", kategorie: "aminosaeuren", kcal: 4 },
  { feld: "lipide", menge: "lipide_g", einheit: "g", text: "Lipide", kategorie: "lipide", kcal: 9.15 },
  { feld: "albumin", menge: "albumin_ml", einheit: "ml", text: "Humanalbumin", kategorie: "albumin", kcal: null },
];
/** Vorbelegung des ersten Plans je kg Körpergewicht – kommt vom Server (wie im Altsystem) */
type Vorbelegung = { gewicht_kg: number | null; je_kg: Record<string, number | string>; werte: Record<string, number> | null;
  /** wann die Praxis die Mengen je kg zuletzt geändert hat (Vorlagen › Grenzwerte, F190); null = Startwerte des Altsystems */
  stand: string | null };
const JE_KG_TEXT: [string, string, string][] = [
  ["glucose_g", "Glucose", "g"], ["aminosaeuren_g", "Aminosäuren", "g"], ["lipide_g", "Lipide", "g"], ["natrium_mmol", "Natrium", "mmol"],
  ["kalium_mmol", "Kalium", "mmol"], ["phosphat_mmol", "Phosphat", "mmol"], ["calcium_mmol", "Calcium", "mmol"], ["magnesium_mmol", "Magnesium", "mmol"],
];
/** Gesamtvolumen wie im Altsystem: Körpergewicht × 35 ml, auf 2 Stellen gerundet */
const ML_JE_KG = 35;
/** Stabilität wie im Altsystem: Calcium + Magnesium (mmol) höchstens Gesamtvolumen ÷ 100 */
const CA_MG_ML_JE_MMOL = 100;
const ELEKTROLYTE: { feld: ZahlFeld; text: string }[] = [
  { feld: "natrium_mmol", text: "Natrium" }, { feld: "kalium_mmol", text: "Kalium" }, { feld: "phosphat_mmol", text: "Phosphat" },
  { feld: "calcium_mmol", text: "Calcium" }, { feld: "magnesium_mmol", text: "Magnesium" },
];

function leer(): Formular {
  const f = Object.fromEntries([...ZAHLEN, ...AUSWAHL].map((k) => [k, ""])) as Record<ZahlFeld | AuswahlFeld, string>;
  return { ...f, vitamine: [], bemerkung: "", pantozol_stufe: "0", gueltig_ab: datum(heuteIso()), positionen: [] };
}

function ausPlan(p: Plan, gueltig?: string): Formular {
  const f = leer();
  for (const k of ZAHLEN) f[k] = p[k] != null ? zahl(p[k] as number) : "";
  for (const k of AUSWAHL) f[k] = p[k] != null ? String(p[k]) : "";
  return { ...f, vitamine: [...p.vitamine], bemerkung: p.bemerkung, pantozol_stufe: String(p.pantozol_stufe ?? 0),
    gueltig_ab: gueltig ?? datum(p.gueltig_ab),
    positionen: (p.positionen ?? []).map((x) => ({ praeparat: String(x.praeparat), menge: x.menge != null ? zahl(x.menge) : "",
      einheit: x.einheit ?? "", haeufigkeit: x.haeufigkeit ?? "", bemerkung: x.bemerkung ?? "" })) };
}

/** Letzter freigegebener Plan für einen Entwurf – dieselbe Regel wie ``Infusionsplan.letzter_freigegebener`` im
 *  Backend (Festlegung 16.10.2026): der aktuell gültige Plan (jede Freigabe macht den freigegebenen Plan zum aktuellen);
 *  ohne ihn der späteste abgelöste nach „gültig ab“, bei gleichem Tag nach dem Zeitpunkt der Freigabe (ohne Freigabe,
 *  z. B. aus dem Altsystem: davor), zuletzt nach der ID. Entwürfe zählen nie. */
function letzterFreigegebener(plaene: Plan[]): Plan | undefined {
  const aktuell = plaene.find((p) => p.status === "aktuell");
  if (aktuell) return aktuell;
  const freigabe = (p: Plan) => (p.freigegeben_am ? Date.parse(p.freigegeben_am) : -Infinity);
  const spaeter = (a: Plan, b: Plan) => a.gueltig_ab !== b.gueltig_ab ? a.gueltig_ab > b.gueltig_ab
    : freigabe(a) !== freigabe(b) ? freigabe(a) > freigabe(b) : a.id > b.id;
  return plaene.filter((p) => p.status === "abgeloest")
    .reduce<Plan | undefined>((bester, p) => (!bester || spaeter(p, bester) ? p : bester), undefined);
}

function zahlWert(t: string): number | null {
  const z = eingabeZahl(t);
  return z && z !== "ungueltig" ? Number(z) : null;
}

/** Vergleichbare Form eines Werts (Komma/Punkt, leer, Zahlformat) */
function norm(f: Formular, k: keyof Formular): string {
  if (k === "positionen") return JSON.stringify(f.positionen.map((x) => ({ ...x, menge: zahlWert(x.menge) })));
  const v = f[k];
  if (Array.isArray(v)) return [...(v as number[])].sort((a, b) => a - b).join(",");
  if ((ZAHLEN as readonly string[]).includes(k)) { const z = zahlWert(v); return z == null ? "" : String(z); }
  return String(v ?? "");
}

function Einheit({ children, einheit }: { children: ReactNode; einheit: string }) {
  return (
    <span className="relative block">
      {children}
      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[0.8125rem] gedaempft pointer-events-none">{einheit}</span>
    </span>
  );
}

function PraeparatAuswahl({ id, wert, onWahl, kategorie, praeparate, markiert, label, invalid }: {
  id?: string; wert: string; onWahl: (v: string) => void; kategorie: string; praeparate: Praeparat[]; markiert?: boolean; label?: string; invalid?: boolean;
}) {
  const liste = praeparate.filter((p) => p.kategorie === kategorie && (p.aktiv || String(p.id) === wert));
  return (
    <Auswahl id={id} aria-label={label} value={wert} onChange={(e) => onWahl(e.target.value)} aria-invalid={invalid || undefined}
      className={cx(markiert && "border-warn bg-warn-bg")}>
      <option value="">—</option>
      {liste.map((p) => <option key={p.id} value={p.id}>{p.anzeige}{p.aktiv ? "" : " (ausgeblendet)"}</option>)}
    </Auswahl>
  );
}

const KATEGORIE_TEXT: Record<string, string> = {
  medikament: "Medikamente", elektrolyte: "Elektrolytzusätze", sonstiges: "Sonstiges", vitamine: "Vitamine",
  spurenelemente: "Spurenelemente", katheterschutz: "Katheterblock", aminosaeuren: "Aminosäuren", lipide: "Lipide",
  glucose: "Glucose", basisloesung: "Basislösungen", albumin: "Albumin",
};

/** Erweiterungen des Plans ohne eigenes Feld: jedes Präparat aus „Vorlagen › Auswahllisten“ */
function WeitereBestandteile({ positionen, praeparate, fehler, markiert, onAendern }: {
  positionen: Position[]; praeparate: Praeparat[]; fehler: Feldfehler; markiert: boolean; onAendern: (p: Position[]) => void;
}) {
  const setze = (i: number, neu: Partial<Position>) => onAendern(positionen.map((x, j) => (j === i ? { ...x, ...neu } : x)));
  const gruppen = Object.entries(KATEGORIE_TEXT).map(([k, t]) => [t, praeparate.filter((x) => x.kategorie === k)] as const);
  return (
    <div className={cx("flex flex-col gap-2 rounded-lg", markiert && "bg-warn-bg p-2 border border-warn")} role="group" aria-label="Weitere Bestandteile"
      data-testid="weitere-bestandteile">
      <span className="text-sm font-medium">Weitere Bestandteile</span>
      {positionen.length ? (
        <table className="tabelle">
          <thead><tr><th className="th">Präparat</th><th className="th w-[6rem]">Menge</th><th className="th w-[6rem]">Einheit</th><th className="th">Häufigkeit</th><th className="th">Bemerkung</th><th className="th w-[2.5rem]" /></tr></thead>
          <tbody>
            {positionen.map((x, i) => (
              <tr key={i}>
                <td className="td">
                  <Auswahl aria-label={`Bestandteil ${i + 1}`} value={x.praeparat} aria-invalid={fehler[`positionen.${i}.praeparat`] ? true : undefined}
                    onChange={(ev) => {
                      const pr = praeparate.find((y) => String(y.id) === ev.target.value);
                      setze(i, { praeparat: ev.target.value, einheit: x.einheit || pr?.einheit || "" });
                    }}>
                    <option value="">—</option>
                    {gruppen.map(([t, liste]) => liste.some((y) => y.aktiv || String(y.id) === x.praeparat) ? (
                      <optgroup key={t} label={t}>{liste.filter((y) => y.aktiv || String(y.id) === x.praeparat).map((y) => <option key={y.id} value={y.id}>{y.anzeige}{y.aktiv ? "" : " (ausgeblendet)"}</option>)}</optgroup>
                    ) : null)}
                  </Auswahl>
                  {fehler[`positionen.${i}.praeparat`] ? <span className="fehlertext" role="alert">{fehler[`positionen.${i}.praeparat`]}</span> : null}
                </td>
                <td className="td"><Eingabe aria-label={`Menge ${i + 1}`} className="num" inputMode="decimal" value={x.menge} onChange={(ev) => setze(i, { menge: ev.target.value })}
                  aria-invalid={fehler[`positionen.${i}.menge`] ? true : undefined} /></td>
                <td className="td"><Eingabe aria-label={`Einheit ${i + 1}`} list="epm-einheiten" maxLength={10} value={x.einheit} onChange={(ev) => setze(i, { einheit: ev.target.value })} /></td>
                <td className="td"><Eingabe aria-label={`Häufigkeit ${i + 1}`} maxLength={60} placeholder="z. B. täglich" value={x.haeufigkeit} onChange={(ev) => setze(i, { haeufigkeit: ev.target.value })} /></td>
                <td className="td"><Eingabe aria-label={`Bemerkung ${i + 1}`} maxLength={200} value={x.bemerkung} onChange={(ev) => setze(i, { bemerkung: ev.target.value })} /></td>
                <td className="td"><Knopf klein variante="geist" icon="x" aria-label={`Bestandteil ${i + 1} entfernen`} onClick={() => onAendern(positionen.filter((_, j) => j !== i))} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <span className="text-[0.8125rem] gedaempft">Keine. Für Zusätze ohne eigenes Feld, z. B. Medikamente oder neue Präparate aus „Vorlagen › Auswahllisten“.</span>}
      <datalist id="epm-einheiten">{EINHEITEN.map((u) => <option key={u} value={u} />)}</datalist>
      <Knopf klein icon="plus" className="self-start" onClick={() => onAendern([...positionen, { praeparat: "", menge: "", einheit: "", haeufigkeit: "", bemerkung: "" }])}>Bestandteil hinzufügen</Knopf>
      {fehler.positionen ? <span className="fehlertext" role="alert">{fehler.positionen}</span> : null}
    </div>
  );
}

export function PlanEditor() {
  const { patient } = useAkte();
  const { planId } = useParams();
  const [params] = useSearchParams();
  const vorlageId = params.get("vorlage");
  const navigate = useNavigate();
  const { darfBei } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const praeparate = usePraeparate();
  const einstellungen = useEinstellungen();
  const [f, setF] = useState<Formular | null>(null);
  const [leerBegonnen, setLeerBegonnen] = useState(false);
  const [lokal, setLokal] = useState<Feldfehler>({});
  const [neueId, setNeueId] = useState<number | null>(null); // Entwurf, der beim ersten Speichern angelegt wurde
  const stufe = useStufe();

  const entwurf = useQuery({ queryKey: ["plan", planId], queryFn: () => api<Plan>(`infusionsplaene/${planId}/`), enabled: !!planId });
  // aktueller Plan frisch vom Server: Der Aktenkopf kann direkt nach einer Freigabe noch den alten Stand zeigen,
  // dann würde das Formular leer statt mit dem gerade freigegebenen Plan beginnen
  const aktuellAbfrage = useQuery({
    queryKey: ["patient", patient.id, "plaene", "aktuell"],
    queryFn: () => api<{ results: Plan[] }>(`infusionsplaene/?patient=${patient.id}&status=aktuell`),
    enabled: !planId,
  });
  const aktuellBekannt = aktuellAbfrage.isFetchedAfterMount && !aktuellAbfrage.isFetching;
  const aktuellId = aktuellBekannt ? aktuellAbfrage.data?.results[0]?.id : undefined;
  // Markierung und Spalte „vorher“: gegen den letzten freigegebenen Plan (Festlegung 16.10.2026, wie der Vergleich in
  // der Akte); gibt es keinen, gegen den Vorgänger des Entwurfs. Eine Auswahl des Vergleichsplans gibt es nur in der
  // Akte (Infusionspläne › Vergleich): Im Kopf des Editors wäre sie neben „Mengen nach Praxisvorgabe“, „Leer beginnen“
  // und „Frühere Pläne“ je nach Breite in eine neue Zeile gerutscht (Layoutsprung) – deshalb hier nur der Standard.
  // Eigene Abfrage ohne Zwischenspeicher: direkt nach einer Freigabe darf kein alter Stand gelten.
  const vergleichsbasis = useQuery({
    queryKey: ["patient", patient.id, "plaene", "vergleichsbasis"],
    queryFn: () => alle<Plan>(`infusionsplaene/${abfrage({ patient: patient.id })}`),
    gcTime: 0,
  });
  const standardPlan = vergleichsbasis.data ? letzterFreigegebener(vergleichsbasis.data) : undefined;
  const vergleichGrund: "letzter_freigegebener" | "vorgaenger" = standardPlan ? "letzter_freigegebener" : "vorgaenger";
  const vergleichsplan = standardPlan
    ?? (planId && entwurf.data?.vorgaenger ? vergleichsbasis.data?.find((x) => x.id === entwurf.data!.vorgaenger) : undefined);
  const quelleId = vorlageId ?? (aktuellId ? String(aktuellId) : null);
  const quelle = useQuery({ queryKey: ["plan", quelleId], queryFn: () => api<Plan>(`infusionsplaene/${quelleId}/`), enabled: !planId && !!quelleId });
  // erster Plan: je kg Körpergewicht vorbelegt wie im Altsystem
  const ersterPlan = !planId && !vorlageId && aktuellBekannt && !aktuellId;
  const vorbelegung = useQuery({
    queryKey: ["patient", patient.id, "vorbelegung"],
    queryFn: () => api<Vorbelegung>(`infusionsplaene/vorbelegung/?patient=${patient.id}`),
  });
  const [vorschau, setVorschau] = useState<{ id: number; daten: Record<string, unknown> } | null>(null);

  // Formular einmal füllen: Entwurf, sonst Vorlage bzw. aktueller Plan, sonst leer
  useEffect(() => {
    if (f) return;
    if (planId) { if (entwurf.data) setF(ausPlan(entwurf.data)); return; }
    if (!vorlageId && !aktuellBekannt) return; // erst wissen, ob es einen aktuellen Plan gibt
    if (quelleId) { if (quelle.data) setF(ausPlan(quelle.data, datum(heuteIso()))); return; }
    if (!ersterPlan || !vorbelegung.isFetchedAfterMount || vorbelegung.isFetching) return;
    const werte = vorbelegung.data?.werte;
    setF(werte ? { ...leer(), ...Object.fromEntries(Object.entries(werte).map(([k, v]) => [k, zahl(v)])) } : leer());
  }, [f, planId, entwurf.data, vorlageId, aktuellBekannt, quelleId, quelle.data, ersterPlan, vorbelegung.data, vorbelegung.isFetching, vorbelegung.isFetchedAfterMount]);

  // höchstens ein Entwurf je Patient: einen vorhandenen Entwurf bearbeiten statt einen zweiten anzulegen
  const offeneEntwuerfe = useQuery({
    queryKey: ["patient", patient.id, "plaene", "entwurf"],
    queryFn: () => api<{ results: Plan[] }>(`infusionsplaene/?patient=${patient.id}&status=entwurf`),
    enabled: !planId,
  });
  useEffect(() => {
    // nur frisch geladene Daten zählen (im Zwischenspeicher kann noch ein inzwischen freigegebener Entwurf stehen)
    const vorhanden = offeneEntwuerfe.isFetchedAfterMount && !offeneEntwuerfe.isFetching ? offeneEntwuerfe.data?.results[0] : undefined;
    if (!planId && !neueId && vorhanden && !speichern.isPending) navigate(`/patienten/${patient.id}/plaene/${vorhanden.id}/bearbeiten`, { replace: true });
  }, [offeneEntwuerfe.data, offeneEntwuerfe.isFetching]); // eslint-disable-line react-hooks/exhaustive-deps

  const vorher = useMemo(() => (vergleichsplan ? ausPlan(vergleichsplan) : null), [vergleichsplan]);
  const geaendert = (k: keyof Formular) => !!(vorher && f && k !== "gueltig_ab" && norm(f, k) !== norm(vorher, k));

  /** Werte des Formulars für PATCH bzw. Vorschau; Eingabefehler stehen danach in ``lokal`` */
  const formularDaten = (): Record<string, unknown> => {
      const fehler: Feldfehler = {};
      const daten: Record<string, unknown> = {};
      for (const k of ZAHLEN) {
        const z = eingabeZahl(f![k]);
        if (z === "ungueltig") fehler[k] = "Bitte eine Zahl eingeben.";
        daten[k] = z;
      }
      for (const k of AUSWAHL) daten[k] = f![k] ? Number(f![k]) : null;
      const gueltig = eingabeDatum(f!.gueltig_ab);
      if (!gueltig) fehler.gueltig_ab = "Bitte als TT.MM.JJJJ eingeben.";
      if (f!.pantozol_stufe !== "0" && !zahlWert(f!.pantozol_tage)) fehler.pantozol_tage = "Bitte die Zeiten angeben (morgens, mittags, abends).";
      const positionen = f!.positionen.map((x, i) => {
        const menge = eingabeZahl(x.menge);
        if (!x.praeparat) fehler[`positionen.${i}.praeparat`] = "Bitte ein Präparat wählen.";
        if (menge === "ungueltig") fehler[`positionen.${i}.menge`] = "Bitte eine Zahl eingeben.";
        return { praeparat: Number(x.praeparat), menge: menge === "ungueltig" ? null : menge, einheit: x.einheit.trim(),
          haeufigkeit: x.haeufigkeit.trim(), bemerkung: x.bemerkung.trim(), reihenfolge: i };
      });
      setLokal(fehler);
      if (Object.keys(fehler).length) throw new ApiFehler(400, "Bitte die markierten Felder prüfen.", null, fehler);
      Object.assign(daten, { gueltig_ab: gueltig, vitamine: f!.vitamine, bemerkung: f!.bemerkung, pantozol_stufe: Number(f!.pantozol_stufe),
        positionen });
      return daten;
  };
  /** Entwurf beim ersten Speichern anlegen (vorher gibt es keinen) */
  const entwurfId = async (): Promise<number> => {
      let id = planId ? Number(planId) : neueId;
      if (!id) {
        const neu = await api<Plan>("infusionsplaene/entwurf/", {
          body: { patient: patient.id, ...(leerBegonnen ? { leer: true } : vorlageId ? { vorlage: Number(vorlageId) } : {}) },
        });
        id = neu.id;
        setNeueId(neu.id);
      }
      return id;
  };
  const speichern = useMutation({
    mutationFn: async (freigeben: boolean) => {
      const daten = formularDaten();
      const id = await entwurfId();
      await api<Plan>(`infusionsplaene/${id}/`, { method: "PATCH", body: daten });
      if (freigeben) await api<Plan>(`infusionsplaene/${id}/freigeben/`, { method: "POST" });
      return id;
    },
    onSuccess: (id, freigeben) => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      void qc.invalidateQueries({ queryKey: ["plan"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden(freigeben ? "Plan gespeichert und freigegeben." : "Entwurf gespeichert.");
      navigate(`/patienten/${patient.id}/plaene?plan=${id}`);
    },
    onError: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
    },
  });

  // PDF-Vorschau mit den Eingaben, wie sie gerade im Formular stehen (Wunsch 10.10.2026: „PDFs einfach einsehbar“).
  // Ein neuer Plan wird dafür einmal als Entwurf gespeichert – vorher gibt es nichts, wozu eine PDF gehört.
  const vorschauM = useMutation({
    mutationFn: async () => {
      const daten = formularDaten();
      const neu = !planId && !neueId;
      const id = await entwurfId();
      if (neu) await api<Plan>(`infusionsplaene/${id}/`, { method: "PATCH", body: daten });
      return { id, daten };
    },
    onSuccess: (v) => setVorschau(v),
  });

  // ohne Recht bzw. bei abgeschlossener Akte gibt es den Editor nicht: zurück zu den Plänen
  if (patient.ist_abgeschlossen || !darfBei("plaene_anlegen", patient)) {
    return <Navigate to={`/patienten/${patient.id}/plaene`} replace />;
  }
  if (!f || praeparate.isLoading || vergleichsbasis.isLoading) return <Laden />;
  if (planId && entwurf.data && entwurf.data.status !== "entwurf") {
    return <Meldung art="warn">Dieser Plan ist freigegeben und unveränderlich. Bitte einen neuen Plan anlegen.</Meldung>;
  }

  const fehlerQuelle = speichern.error ?? vorschauM.error;
  const server: Feldfehler = fehlerQuelle instanceof ApiFehler && fehlerQuelle !== null ? fehlerQuelle.felder : {};
  const e: Feldfehler = { ...server, ...lokal };
  const p = praeparate.data ?? [];
  const setze = (k: keyof Formular) => (wert: string) => setF((a) => ({ ...a!, [k]: wert }));
  const kcalRoh = (form: Formular) => MAKRO.reduce((s, m) => s + (m.kcal != null ? (zahlWert(form[m.menge]) ?? 0) * m.kcal : 0), 0);
  // Energie: berechnet wie im Altsystem, außer sie ist manuell gesetzt (dann gilt der manuelle Wert, auch für die Grenzen)
  const kcalBerechnet = Math.round(kcalRoh(f));
  const kcalManuell = zahlWert(f.kcal_manuell);
  const kcal = kcalManuell ?? kcalBerechnet;
  const kcalVorher = vorher ? zahlWert(vorher.kcal_manuell) ?? kcalRoh(vorher) : null;
  const gewicht = patient.kopf?.gewicht ? Number(patient.kopf.gewicht.kg) : null;
  // Gesamtvolumen aus dem letzten Gewicht (der Server rechnet beim Speichern genauso und friert es bei Freigabe ein); Laufzeit manuell
  const volumen = gewicht != null ? Math.round(gewicht * ML_JE_KG * 100) / 100 : null;
  const laufzeit = zahlWert(f.laufzeit_h);
  // Gesamtvolumen wie auf der alten PDF: Mischbeutel + Zusatzvolumen (Basislösung); die Rate wird aus der Summe berechnet
  const zusatz = zahlWert(f.basis_ml) ?? 0;
  const summe = volumen != null ? Math.round((volumen + zusatz) * 100) / 100 : null;
  const rate = summe != null && laufzeit ? Math.round((summe / laufzeit) * 10) / 10 : null;
  const volumenVorher = vergleichsplan?.volumen_summe_ml ?? null;
  const rateVorher = vergleichsplan?.rate_ml_h ?? null;
  const ppiMaske = zahlWert(f.pantozol_tage) ?? 0;
  const ca = zahlWert(f.calcium_mmol);
  const mg = zahlWert(f.magnesium_mmol);
  const caMg = ca == null && mg == null ? null : Math.round(((ca ?? 0) + (mg ?? 0)) * 10) / 10;
  const caMgGrenze = volumen != null ? Math.round((volumen / CA_MG_ML_JE_MMOL) * 100) / 100 : null;
  const caMgStabil = caMg != null && caMgGrenze != null ? caMg <= caMgGrenze : null;
  const anzahlGeaendert = vorher ? ([...ZAHLEN, ...AUSWAHL, "vitamine", "bemerkung", "pantozol_stufe", "positionen"] as (keyof Formular)[]).filter(geaendert).length : 0;
  const es = einstellungen.data;
  const warnungen: string[] = [];
  if (es) {
    const pruefe = (wert: number | null, unten: unknown, oben: unknown, text: string, einheit: string) => {
      if (wert != null && (wert < Number(unten) || wert > Number(oben))) warnungen.push(`${text} ${zahl(wert)} ${einheit} außerhalb ${zahl(Number(unten))}–${zahl(Number(oben))} ${einheit}`);
    };
    pruefe(kcal, es.kcal_min_tag, es.kcal_max_tag, "Energie", "kcal");
    pruefe(volumen, es.volumen_min_ml, es.volumen_max_ml, "Volumen im Mischbeutel", "ml");
    pruefe(zahlWert(f.glucose_g), es.glucose_min_g, es.glucose_max_g, "Glucose", "g");
    pruefe(zahlWert(f.aminosaeuren_g), es.aminosaeuren_min_g, es.aminosaeuren_max_g, "Aminosäuren", "g");
    pruefe(zahlWert(f.lipide_g), es.lipide_min_g, es.lipide_max_g, "Lipide", "g");
    pruefe(zahlWert(f.natrium_mmol), es.natrium_min_mmol, es.natrium_max_mmol, "Natrium", "mmol");
    pruefe(zahlWert(f.kalium_mmol), es.kalium_min_mmol, es.kalium_max_mmol, "Kalium", "mmol");
  }
  if (caMgStabil === false) warnungen.push(`Instabil: Calcium + Magnesium ${zahl(caMg)} mmol über ${zahl(caMgGrenze)} mmol (Mischbeutel ÷ 100)`);
  // Prüfung vor der Freigabe in Alltagssprache (Wunsch 10.10.2026: „Grenzwert-Warnungen verständlich, Freigabe klar“):
  // jeder Punkt grün oder mit dem, was zu tun ist. Der Server prüft beim Speichern und Freigeben dasselbe noch einmal.
  const pe = zahlWert(f.tage_pro_woche);
  const zusatzTage = zahlWert(f.zusatz_tage_pro_woche);
  const freiTage = zahlWert(f.freie_tage_pro_woche);
  // Entscheidung der Praxis 10.10.2026: nach 6 Monaten „bitte prüfen“ (Vorlagen › Grenzwerte, F190)
  const gewichtGrenzeMonate = Number(es?.plan_gewicht_alter_monate ?? 6);
  const gewichtAlterTage = patient.kopf?.gewicht ? Math.round((Date.parse(heuteIso()) - Date.parse(patient.kopf.gewicht.am.slice(0, 10))) / 86400000) : null;
  const ohnePraeparat = MAKRO.filter((m) => zahlWert(f[m.menge]) && !f[`${m.feld}_praeparat` as AuswahlFeld]).map((m) => m.text);
  const bestandteile = ([
    ["natrium", zahlWert(f.natrium_mmol)], ["kalium", zahlWert(f.kalium_mmol)], ["phosphat", zahlWert(f.phosphat_mmol)],
    ["calcium", zahlWert(f.calcium_mmol)], ["magnesium", zahlWert(f.magnesium_mmol)], ["albumin", zahlWert(f.albumin_ml)],
    ["glucose", zahlWert(f.glucose_g)], ["lipide", zahlWert(f.lipide_g)], ["spurenelemente", f.spurenelemente ? 1 : null],
    ["vitamine", f.vitamine.length || null],
  ] as const).filter(([, w]) => w).map(([k]) => k as string);
  const pruefpunkte: { ok: boolean; text: string }[] = [
    gewicht == null
      ? { ok: false, text: "Kein Gewicht erfasst: Gesamtvolumen (35 ml/kg) und Rate fehlen. Bitte zuerst das Gewicht eintragen." }
      : { ok: gewichtAlterTage == null || gewichtAlterTage <= gewichtGrenzeMonate * 30,
        text: `Gewicht ${kg(gewicht)} vom ${datum(patient.kopf!.gewicht!.am)}${gewichtAlterTage != null && gewichtAlterTage > gewichtGrenzeMonate * 30 ? ` – älter als ${gewichtGrenzeMonate} Monate, bitte prüfen` : ""}.` },
    ohnePraeparat.length
      ? { ok: false, text: `Präparat fehlt bei ${ohnePraeparat.join(", ")}.` }
      : { ok: true, text: "Zu jeder Menge ist ein Präparat gewählt." },
    caMgStabil === false
      ? { ok: false, text: `Mischung instabil: Calcium + Magnesium ${zahl(caMg)} mmol, erlaubt sind ${zahl(caMgGrenze)} mmol. Calcium oder Magnesium verringern.` }
      : { ok: true, text: caMgStabil == null ? "Stabilität Calcium + Magnesium: noch nicht prüfbar." : "Calcium + Magnesium stabil." },
    pe == null
      ? { ok: false, text: "Infusionstage pro Woche (PE) fehlen." }
      : pe > 7 || (freiTage != null && freiTage > 7 - Math.max(pe, zusatzTage ?? 0))
        ? { ok: false, text: "Infusionstage passen nicht zusammen: infusionsfreie Tage höchstens 7 − Infusionstage." }
        : { ok: true, text: `PE ${zahl(pe)}× pro Woche${zusatzTage ? `, Zusatzvolumen ${zahl(zusatzTage)}×` : ""}${freiTage ? `, ${zahl(freiTage)} infusionsfrei` : ""}.` },
    laufzeit
      ? { ok: true, text: `Laufzeit ${zahl(laufzeit)} h${rate != null ? ` – Rate ${zahl(rate)} ml/h` : ""}.` }
      : { ok: false, text: "Laufzeit fehlt – ohne sie gibt es keine Rate." },
    ...(f.pantozol_stufe !== "0" && !ppiMaske ? [{ ok: false, text: "Protonenpumpenhemmer gewählt, aber keine Zeit (morgens, mittags, abends)." }] : []),
  ];
  const vitamineListe = p.filter((x) => x.kategorie === "vitamine");
  const zahlFeld = (k: ZahlFeld, label: ReactNode, einheit: string, extra?: ReactNode) => (
    <Feld label={label} fehler={e[k]} hinweis={extra}>
      {(pp) => <Einheit einheit={einheit}><Eingabe {...pp} className={cx("num pr-14", geaendert(k) && "border-warn bg-warn-bg")} value={f[k]}
        onChange={(ev) => setze(k)(ev.target.value)} inputMode="decimal" /></Einheit>}
    </Feld>
  );

  return (
    <form className="stapel flex flex-col gap-5" noValidate onSubmit={(ev) => { ev.preventDefault(); speichern.mutate(false); }} data-testid="plan-editor">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-1">
          <span className="text-sm gedaempft">
            <Link to={`/patienten/${patient.id}`} className="underline">{name(patient)}</Link> · Nr. {nummer(patient.nummer)}
            {patient.kopf?.gewicht ? ` · ${kg(patient.kopf.gewicht.kg)} am ${datum(patient.kopf.gewicht.am)}` : ""}
          </span>
          <h2 className="m-0 text-[1.625rem] font-semibold">{planId ? "Entwurf bearbeiten" : "Neuer Infusionsplan"}</h2>
          <span className="text-sm gedaempft">
            {leerBegonnen ? "Leer begonnen. "
              : !planId && quelleId && quelle.data ? vorlageId ? `Vorlage geladen (Plan vom ${datum(quelle.data.gueltig_ab)}). ` : `Vorbelegt mit dem aktuellen Plan vom ${datum(quelle.data.gueltig_ab)}. `
              : vergleichsplan ? ""
              : `Erster Plan dieses Patienten. ${!planId && vorbelegung.data?.werte ? `Vorbelegt je kg Körpergewicht (${kg(vorbelegung.data.gewicht_kg)}) ${vorbelegung.data.stand ? `nach Praxisvorgabe vom ${datum(vorbelegung.data.stand)}` : "wie im Altsystem"}. ` : ""}`}
            {vorher && vergleichsplan ? <span data-testid="plan-vergleichsbasis">Geänderte Werte gegenüber dem {vergleichGrund === "vorgaenger" ? "Vorgänger" : "letzten freigegebenen Plan"} vom {datum(vergleichsplan.gueltig_ab)} sind <span className="bg-warn-bg border border-warn rounded px-1">markiert</span>.</span> : null}
          </span>
        </div>
        <div className="flex gap-2 flex-wrap">
          {/* Vorgabe der Praxis: Mengen je kg des letzten Gewichts (Vorlagen › Grenzwerte, F190); Präparate und Zusätze bleiben */}
          {vorbelegung.data?.werte ? (
            <span className="flex items-center gap-2 flex-wrap">
              <Knopf icon="waage" title={`Je kg Körpergewicht (${kg(vorbelegung.data.gewicht_kg)}): ${JE_KG_TEXT.map(([k, t, e]) => `${t} ${zahl(Number(vorbelegung.data!.je_kg[k] ?? 0))} ${e}`).join(" · ")}`}
                onClick={() => setF((a) => ({ ...a!, ...Object.fromEntries(Object.entries(vorbelegung.data!.werte!).map(([k, v]) => [k, zahl(Number(v))])) }))}>
                Mengen nach Praxisvorgabe</Knopf>
              <span className="text-xs gedaempft" data-testid="praxisvorgabe-stand">{vorbelegung.data.stand
                ? `nach Praxisvorgabe vom ${datum(vorbelegung.data.stand)}` : "Startwerte wie im Altsystem"}</span>
            </span>
          ) : null}
          {!planId ? <Knopf onClick={() => { setF(leer()); setLeerBegonnen(true); }}>Leer beginnen</Knopf> : null}
          <KnopfLink to={`/patienten/${patient.id}/plaene`}>Frühere Pläne</KnopfLink>
        </div>
      </div>

      <PlanSpalten stufe={stufe} vorschau={<PlanVorschau id={planId ? Number(planId) : neueId} />} eingabe={
        <div className="flex flex-col gap-4 min-w-0">
          <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Basislösung</h3>
            <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-3">
              <Feld label="Präparat" fehler={e.basis_praeparat}>
                {(pp) => <PraeparatAuswahl id={pp.id} wert={f.basis_praeparat} onWahl={setze("basis_praeparat")} kategorie="basisloesung" praeparate={p} markiert={geaendert("basis_praeparat")} invalid={!!e.basis_praeparat} />}
              </Feld>
              {zahlFeld("basis_ml", "Volumen", "ml")}
            </div>
          </Karte>

          <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Makronährstoffe</h3>
            <table className="tabelle">
              <thead><tr><th className="th">Komponente</th><th className="th">Präparat</th><th className="th text-right">vorher</th><th className="th">Menge</th><th className="th text-right">kcal/g</th><th className="th text-right">kcal</th></tr></thead>
              <tbody>
                {MAKRO.map((m) => {
                  const gFeld = m.menge;
                  const pFeld = `${m.feld}_praeparat` as AuswahlFeld;
                  const menge = zahlWert(f[gFeld]);
                  const z = m.kcal != null && menge != null ? Math.round(menge * m.kcal) : null;
                  return (
                    <tr key={m.feld}>
                      <td className="td">{m.text}</td>
                      <td className="td">
                        <PraeparatAuswahl wert={f[pFeld]} onWahl={setze(pFeld)} kategorie={m.kategorie} praeparate={p} label={`Präparat ${m.text}`}
                          markiert={geaendert(pFeld)} invalid={!!e[pFeld]} />
                        {e[pFeld] ? <span className="fehlertext" role="alert">{e[pFeld]}</span> : null}
                      </td>
                      <td className="td num text-right gedaempft">{vorher?.[gFeld] || "—"}</td>
                      <td className="td w-[7.5rem]">
                        <Eingabe aria-label={`Menge ${m.text} in ${m.einheit}`} className={cx("num", geaendert(gFeld) && "border-warn bg-warn-bg")} value={f[gFeld]}
                          onChange={(ev) => setze(gFeld)(ev.target.value)} inputMode="decimal" aria-invalid={e[gFeld] ? true : undefined} />
                        {e[gFeld] ? <span className="fehlertext" role="alert">{e[gFeld]}</span> : null}
                      </td>
                      <td className="td num text-right">{m.kcal != null ? zahl(m.kcal) : "—"}</td>
                      <td className="td num text-right">{z != null ? zahl(z) : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <span className="text-[0.8125rem] gedaempft">kcal werden berechnet wie im Altsystem: Glucose und Aminosäuren 4 kcal/g, Lipide 9,15 kcal/g. Humanalbumin in ml, ohne Energie.</span>
          </Karte>

          <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Elektrolyte</h3>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(6.5rem,1fr))] gap-3">{ELEKTROLYTE.map((x) => <div key={x.feld}>{zahlFeld(x.feld, x.text, "mmol")}</div>)}</div>
            <span className={cx("text-[0.8125rem]", caMgStabil === false ? "text-warn font-medium" : "gedaempft")} data-testid="ca-mg-stabilitaet">
              {caMgStabil == null ? "Stabilität Calcium + Magnesium: wird geprüft, sobald Mischbeutel-Volumen und Werte vorliegen."
                : `Calcium + Magnesium ${zahl(caMg)} mmol, Grenze ${zahl(caMgGrenze)} mmol (Mischbeutel ÷ 100): ${caMgStabil ? "stabil" : "instabil"}`}
            </span>
          </Karte>

          <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Zusätze</h3>
            <div className="grid grid-cols-2 gap-3">
              <Feld label="Spurenelemente" fehler={e.spurenelemente}>
                {(pp) => <PraeparatAuswahl id={pp.id} wert={f.spurenelemente} onWahl={setze("spurenelemente")} kategorie="spurenelemente" praeparate={p} markiert={geaendert("spurenelemente")} />}
              </Feld>
              <Feld label="Katheterblock / Medikament" fehler={e.katheterschutz}>
                {(pp) => <PraeparatAuswahl id={pp.id} wert={f.katheterschutz} onWahl={setze("katheterschutz")} kategorie="katheterschutz" praeparate={p} markiert={geaendert("katheterschutz")} />}
              </Feld>
            </div>
            <div className={cx("flex flex-col gap-2 rounded-lg", geaendert("vitamine") && "bg-warn-bg p-2 border border-warn")} role="group" aria-label="Vitamine">
              <span className="text-sm font-medium">Vitamine</span>
              <div className="flex flex-wrap gap-2 items-center">
                {f.vitamine.map((vid) => {
                  const v = p.find((x) => x.id === vid);
                  return (
                    <Chip key={vid} art="akzent">{v?.anzeige ?? vid}
                      <button type="button" className="bg-transparent border-0 p-0 cursor-pointer text-inherit inline-flex" aria-label={`${v?.anzeige ?? vid} entfernen`}
                        onClick={() => setF((a) => ({ ...a!, vitamine: a!.vitamine.filter((x) => x !== vid) }))}><Icon name="x" /></button>
                    </Chip>
                  );
                })}
                {vitamineListe.filter((v) => v.aktiv && !f.vitamine.includes(v.id)).map((v) => (
                  <button key={v.id} type="button" className="bg-transparent border border-dashed border-rand rounded-md px-2 h-[1.375rem] text-xs cursor-pointer text-text2"
                    onClick={() => setF((a) => ({ ...a!, vitamine: [...a!.vitamine, v.id] }))}>+ {v.anzeige}</button>
                ))}
              </div>
              {e.vitamine ? <span className="fehlertext" role="alert">{e.vitamine}</span> : null}
            </div>
            <WeitereBestandteile positionen={f.positionen} praeparate={p} fehler={e} markiert={geaendert("positionen")}
              onAendern={(positionen) => setF((a) => ({ ...a!, positionen }))} />
            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium" id="plan-kommentar">Kommentar</span>
              <Editor wert={f.bemerkung} onAenderung={setze("bemerkung")} label="Kommentar" werkzeuge={false} hoehe={56} />
            </div>
          </Karte>
        </div>} summen={

        <aside className="flex flex-col gap-4">
          <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Gültigkeit, Laufzeit</h3>
            <div className="grid grid-cols-2 gap-3">
              <Feld label="gültig ab" fehler={e.gueltig_ab}>{(pp) => <Eingabe {...pp} className="num" value={f.gueltig_ab} onChange={(ev) => setze("gueltig_ab")(ev.target.value)} />}</Feld>
              {zahlFeld("laufzeit_h", "Laufzeit", "h", vorher ? (norm(f, "laufzeit_h") === norm(vorher, "laufzeit_h") ? "unverändert" : `vorher ${vorher.laufzeit_h || "—"} h`) : undefined)}
            </div>
            {/* Infusionstage je Beutelart (Wunsch 06.10.2026, F110): unabhängig von der Zusammensetzung */}
            <h3 className="lbl m-0">Infusionstage pro Woche</h3>
            <div className="grid grid-cols-3 gap-3" data-testid="infusionstage">
              {zahlFeld("tage_pro_woche", <><Begriff name="pe">PE</Begriff> (Mischbeutel)</>, "×")}
              {zahlFeld("zusatz_tage_pro_woche", "Zusatzvolumen", "×")}
              {zahlFeld("freie_tage_pro_woche", "Infusionsfrei", "Tg")}
            </div>
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1.5 text-sm" data-testid="plan-volumen">
              <span className="gedaempft">Volumen im Mischbeutel</span>
              <span className="num text-right" data-testid="plan-mischbeutel">{volumen != null ? `${zahl(volumen)} ml` : "—"}</span>
              <span className="gedaempft">Zusatzvolumen (Basislösung)</span>
              <span className="num text-right" data-testid="plan-zusatzvolumen">{`${zahl(zusatz)} ml`}</span>
              <span className="gedaempft font-medium">Gesamtvolumen</span>
              <span className="num text-right font-medium" data-testid="plan-gesamtvolumen">
                {summe != null ? `${zahl(summe)} ml` : "—"}
                {volumenVorher != null && summe != null && Math.abs(volumenVorher - summe) >= 0.01 ? <span className="text-warn"> vorher {zahl(volumenVorher)} ml</span> : null}
              </span>
              <span className="gedaempft">Rate</span>
              <span className="num text-right" data-testid="plan-rate">
                {rate != null ? `${zahl(rate)} ml/h` : "—"}
                {rateVorher != null && rate != null && Math.abs(rateVorher - rate) >= 0.05 ? <span className="text-warn"> vorher {zahl(rateVorher)} ml/h</span> : null}
              </span>
            </div>
            <span className={cx("text-xs", e.gesamtvolumen_ml ? "fehlertext" : "gedaempft")} role={e.gesamtvolumen_ml ? "alert" : undefined}
              data-testid="plan-volumen-hinweis">
              {e.gesamtvolumen_ml ?? (gewicht != null
                ? `Mischbeutel: ${ML_JE_KG} ml/kg × ${kg(gewicht)} (letztes Gewicht). Rate = Gesamtvolumen ÷ Laufzeit. Bei Freigabe festgeschrieben.`
                : "Kein Gewicht erfasst: Volumen und Rate werden berechnet, sobald ein Gewicht eingetragen ist.")}
            </span>
          </Karte>
          <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Protonenpumpenhemmer</h3>
            <Feld label="Präparat (Kurzinfusion)" fehler={e.pantozol_stufe}>
              {(pp) => (
                <Auswahl {...pp} value={f.pantozol_stufe} onChange={(ev) => setF((a) => ({ ...a!, pantozol_stufe: ev.target.value, pantozol_tage: ev.target.value === "0" ? "" : a!.pantozol_tage }))}
                  className={cx(geaendert("pantozol_stufe") && "border-warn bg-warn-bg")}>
                  {PROTONENPUMPENHEMMER.map(([code, text]) => <option key={code} value={code}>{text}</option>)}
                </Auswahl>
              )}
            </Feld>
            <fieldset className={cx("m-0 flex flex-col gap-1.5 rounded-lg", geaendert("pantozol_tage") ? "bg-warn-bg border border-warn p-2" : "border-0 p-0")}
              disabled={f.pantozol_stufe === "0"} aria-describedby={e.pantozol_tage ? "ppi-zeiten-fehler" : undefined}>
              <legend className="text-sm font-medium p-0 mb-1">Zeiten</legend>
              <div className="flex gap-4 flex-wrap">
                {PPI_ZEITEN.map(([bit, text]) => (
                  <label key={bit} className="flex items-center gap-1.5 text-sm">
                    <input type="checkbox" checked={(ppiMaske & bit) !== 0}
                      onChange={(ev) => setze("pantozol_tage")(String((ev.target.checked ? ppiMaske | bit : ppiMaske & ~bit) || ""))} />
                    {text.charAt(0).toUpperCase() + text.slice(1)}
                  </label>
                ))}
              </div>
              {e.pantozol_tage ? <span id="ppi-zeiten-fehler" className="fehlertext" role="alert">{e.pantozol_tage}</span>
                : vorher && geaendert("pantozol_tage") ? <span className="hinweis">vorher {ppiZeiten(zahlWert(vorher.pantozol_tage)) || "—"}</span> : null}
            </fieldset>
          </Karte>
          <Karte className="px-5 py-[1.125rem] flex flex-col gap-3" data-testid="plan-summe">
            <h3 className="lbl m-0">Summe</h3>
            {zahlFeld("kcal_manuell", "Energie manuell", "kcal", kcalManuell != null
              ? `berechnet wären ${zahl(kcalBerechnet)} kcal` : "leer = berechnet aus den Makronährstoffen")}
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1.5 text-sm">
              <span className="gedaempft">Energie</span>
              <span className="num">{zahl(kcal)} kcal{kcalManuell != null ? " (manuell)" : ""}{kcalVorher != null && Math.round(kcalVorher) !== kcal ? <span className="text-warn"> {kcal - Math.round(kcalVorher) > 0 ? "+" : "−"}{zahl(Math.abs(kcal - Math.round(kcalVorher)))}</span> : null}</span>
              <span className="gedaempft">je kg Körpergewicht</span><span className="num">{gewicht ? `${zahl(kcal / gewicht, 1)} kcal/kg` : "—"}</span>
              <span className="gedaempft">Geänderte Werte</span><span className="num">{anzahlGeaendert}</span>
            </div>
            {warnungen.length ? (
              <Meldung art="warn"><ul className="m-0 pl-4">{warnungen.map((w) => <li key={w}>{w}</li>)}</ul></Meldung>
            ) : <div className="meldung ok flex items-center gap-2 text-sm"><Icon name="haken" />Alle Werte im üblichen Bereich</div>}
          </Karte>
          <Karte className="px-5 py-[1.125rem] flex flex-col gap-2" data-testid="plan-pruefung">
            <h3 className="lbl m-0">Prüfung vor der Freigabe</h3>
            <ul className="m-0 p-0 list-none flex flex-col gap-1.5 text-[0.8125rem]">
              {pruefpunkte.map((x) => (
                <li key={x.text} className="flex items-start gap-2" data-ok={x.ok ? "1" : "0"}>
                  <span className={cx("shrink-0 mt-0.5", x.ok ? "text-ok" : "text-warn")}><Icon name={x.ok ? "haken" : "warnung"} groesse={14} /></span>
                  <span>{x.text}</span>
                </li>
              ))}
            </ul>
            <Knopf icon="dokument" laedt={vorschauM.isPending} disabled={speichern.isPending} onClick={() => vorschauM.mutate()}
              title="So sieht die PDF mit den Werten aus, die gerade im Formular stehen">
              {planId || neueId ? "PDF-Vorschau" : "Speichern und PDF-Vorschau"}</Knopf>
          </Karte>
          <HinweiseAusLabor patientId={patient.id} planId={planId ? Number(planId) : neueId} bestandteile={bestandteile} />
          {fehlerQuelle && !Object.keys(server).length ? <Meldung art="fehler">{fehlerQuelle.message}</Meldung> : null}
          {Object.keys(e).length ? <Meldung art="fehler">Bitte die markierten Felder prüfen.{e.fehler ? ` ${e.fehler}` : ""}</Meldung> : null}
          <div className="flex flex-col gap-2">
            {darfBei("plaene_freigeben", patient) ? (
              <Knopf variante="pri" icon="haken" laedt={speichern.isPending && speichern.variables === true} disabled={speichern.isPending}
                onClick={() => speichern.mutate(true)}>Speichern und freigeben</Knopf>
            ) : null}
            <Knopf type="submit" laedt={speichern.isPending && speichern.variables === false} disabled={speichern.isPending}>Als Entwurf speichern</Knopf>
            <span className="text-xs gedaempft leading-normal">
              {darfBei("plaene_freigeben", patient)
                ? "Der vorherige Plan bleibt im Verlauf erhalten. Bei der Freigabe wird die PDF mit der aktiven Dokumentvorlage erzeugt und mit Prüfsumme gespeichert."
                : "Der Entwurf ist für das Team sichtbar und noch nicht beim Versorger."}
            </span>
          </div>
        </aside>
      } />
      {vorschau ? <PdfDialog offen onOffen={(o) => { if (!o) setVorschau(null); }} titel={`Vorschau Infusionsplan · ${name(patient)}`}
        pfad={`infusionsplaene/${vorschau.id}/vorschau/`} body={vorschau.daten} dateiname={`Infusionsplan-${patient.nummer}-Vorschau.pdf`} /> : null}
    </form>
  );
}

type PlanHinweis = {
  art: "labor" | "labor_alt" | "gewicht" | "plaene" | "referenz_fehlt"; stufe: "warn" | "info"; text: string;
  parameter?: string; bestandteil?: string; einheit?: string; richtung?: "niedrig" | "hoch";
  verlauf?: { am: string; wert: number | string }[]; trend?: "steigend" | "fallend" | "gleichbleibend" | "wechselnd" | null;
  anlage?: number | null;
};
const TREND_TEXT: Record<string, string> = { steigend: "steigend", fallend: "fallend", gleichbleibend: "gleichbleibend", wechselnd: "schwankend" };

/**
 * Hinweise aus Labor und Gewicht (F187): Laborwerte seit dem letzten Plan außerhalb des Referenzbereichs (nur für
 * Bestandteile, die gerade im Formular vorkommen), Verlauf der letzten drei Werte, deutliche Gewichtsänderung, wie sich
 * die eigenen Pläne entwickelt haben, fehlendes Labor.
 * WICHTIG: nur Hinweise zum Prüfen – EPM schlägt hier nie eine Menge vor und berechnet keine Dosis (sonst ggf.
 * Medizinprodukt nach MDR). Texte kommen vom Server (infusionen/hinweise.py) und sind dort so formuliert.
 */
function HinweiseAusLabor({ patientId, planId, bestandteile }: { patientId: number; planId: number | null; bestandteile: string[] }) {
  const { schreibenOeffnen } = useAkte();
  const { darf } = useAuth();
  const daten = useQuery({
    queryKey: ["patient", patientId, "plan-hinweise", planId, bestandteile.join(",")],
    queryFn: () => api<{ hinweise: PlanHinweis[]; seit: string }>(`infusionsplaene/hinweise/${abfrage({ patient: patientId, plan: planId ?? undefined, bestandteile: bestandteile.join(",") })}`),
    placeholderData: (vorher) => vorher,
  });
  const liste = daten.data?.hinweise ?? [];
  return (
    <Karte className="px-5 py-[1.125rem] flex flex-col gap-2" data-testid="plan-hinweise">
      <h3 className="lbl m-0">Hinweise aus Labor und Gewicht</h3>
      <span className="text-xs gedaempft leading-normal">
        Seit dem letzten Plan{daten.data?.seit ? ` (${datum(daten.data.seit)})` : ""}; Laborwerte nur zu Bestandteilen dieses Plans,
        außerhalb des <Begriff name="referenzbereich">Referenzbereichs</Begriff>. Zum Prüfen – EPM schlägt keine Mengen vor.
      </span>
      {daten.isLoading ? <Laden /> : liste.length ? (
        <ul className="m-0 p-0 list-none flex flex-col gap-2 text-[0.8125rem]">
          {liste.map((h, i) => (
            <li key={`${h.art}-${h.parameter ?? i}`} className="flex items-start gap-2 min-w-0" data-art={h.art} data-testid="plan-hinweis">
              <span className={cx("shrink-0 mt-0.5", h.stufe === "warn" ? "text-warn" : "gedaempft")}>
                <Icon name={h.art === "labor" ? (h.richtung === "hoch" ? "hoch" : "runter") : h.stufe === "warn" ? "warnung" : "info"} groesse={14} />
              </span>
              <span className={cx("flex flex-col gap-0.5 min-w-0 [overflow-wrap:anywhere]", h.art === "referenz_fehlt" && "gedaempft")}>
                <span>{h.text}</span>
                {/* fehlende Referenzbereiche pflegt die Praxis selbst (F190) – Link nur für „Vorlagen pflegen“ */}
                {h.art === "referenz_fehlt" && darf("vorlagen_pflegen") ? (
                  <Link to="/admin/vorlagen?bereich=kataloge&labor=ohne_referenz" className="self-start">Referenzbereiche im Laborkatalog nachtragen</Link>
                ) : null}
                {h.art === "labor" && h.verlauf && h.verlauf.length > 1 ? (
                  <span className="gedaempft">
                    Verlauf: {h.verlauf.map((v) => `${zahl(Number(v.wert))} (${datum(v.am).slice(0, 6)})`).join(" → ")}
                    {h.trend ? ` · ${TREND_TEXT[h.trend] ?? h.trend}` : ""}
                  </span>
                ) : null}
                {h.art === "labor_alt" ? (
                  <span className="flex gap-3 flex-wrap">
                    {schreibenOeffnen ? (
                      <button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer underline"
                        onClick={schreibenOeffnen} title="Schreiben und E-Mail öffnen – dort die Anlage „Blutuntersuchung“ anhaken">
                        Blutuntersuchung anfordern</button>
                    ) : null}
                    {h.anlage ? (
                      <button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer underline"
                        onClick={() => void anlageOeffnen({ id: h.anlage! })}>Schreiben „Blutuntersuchung“ ansehen</button>
                    ) : null}
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ) : <span className="text-[0.8125rem] flex items-center gap-2"><span className="text-ok"><Icon name="haken" groesse={14} /></span>Keine Auffälligkeiten.</span>}
      <Fehleranzeige fehler={daten.error} />
    </Karte>
  );
}

/** Aufteilung je Fensterstufe (S16, Entwurf 2): untereinander · Eingabe | Summen wie bisher · ab 1920 px ½ | ¼ | ¼ mit
 *  PDF-Vorschau · ab 2560 px ⅓ | ⅓ | ⅓ mit Teilern */
function PlanSpalten({ stufe, eingabe, summen, vorschau }: { stufe: Stufe; eingabe: ReactNode; summen: ReactNode; vorschau: ReactNode }) {
  if (stufe === "qhd") {
    return <Spalten seite="plan_editor" stufe="qhd" standard={[1 / 3, 2 / 3]} namen={["Eingabe", "Summen", "PDF-Vorschau"]}
      testid="plan-stufe" spalten={[eingabe, summen, vorschau]} />;
  }
  if (stufe === "fhd") {
    return (
      <div className="stapel grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)] gap-5 items-start" data-testid="plan-stufe">
        {eingabe}{summen}<div className="flex flex-col gap-4 min-w-0">{vorschau}</div>
      </div>
    );
  }
  return (
    <div className="stapel grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_21.25rem] gap-5 items-start" data-testid="plan-stufe">{eingabe}{summen}</div>
  );
}

/** PDF-Vorschau des Entwurfs mit der aktiven Dokumentvorlage (Wasserzeichen „ENTWURF“): zeigt den zuletzt gespeicherten
 *  Stand; ungespeicherte Eingaben erscheinen nach „Als Entwurf speichern“ und erneutem Öffnen des Entwurfs. */
function PlanVorschau({ id }: { id: number | null }) {
  const datei = useQuery({
    queryKey: ["plan", id, "ansicht"],
    queryFn: () => apiDatei(`infusionsplaene/${id}/ansicht/`),
    enabled: !!id,
    staleTime: 0,
    gcTime: 0,
  });
  return (
    <Karte className="px-4 py-3.5 flex flex-col gap-2 hd:sticky hd:top-4" data-testid="plan-pdf-vorschau">
      <h3 className="lbl m-0">PDF-Vorschau</h3>
      {!id ? <span className="text-sm gedaempft">Die Vorschau erscheint, sobald der Entwurf gespeichert ist.</span> : (
        <>
          <span className="text-[0.8125rem] gedaempft">Stand der letzten Speicherung{datei.dataUpdatedAt ? ` (geladen ${uhrzeit(new Date(datei.dataUpdatedAt))})` : ""} ·
            mit der aktiven Dokumentvorlage, Wasserzeichen „ENTWURF“. Ungespeicherte Änderungen sind noch nicht enthalten.</span>
          <Fehleranzeige fehler={datei.error} />
          {datei.isLoading ? <Laden text="PDF wird geladen …" /> : datei.data ? (
            <PdfLeser url={`plan-entwurf-${id}-${datei.dataUpdatedAt}`} laden={() => Promise.resolve(datei.data!.daten)} className="h-[70vh]" />
          ) : null}
        </>
      )}
    </Karte>
  );
}
