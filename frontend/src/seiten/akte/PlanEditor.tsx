/** Entwurf 7 · Neuer Infusionsplan bzw. Entwurf bearbeiten: vorbelegt, Änderungen markiert, kcal wie im Altsystem. */
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useEinstellungen, usePraeparate } from "@/lib/daten";
import { datum, eingabeDatum, eingabeZahl, heuteIso, kg, nummer, zahl } from "@/lib/format";
import type { Plan, Praeparat } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Karte, Knopf, KnopfLink, Laden, Meldung, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Editor } from "@/components/Editor";
import { name, useAkte } from "./Akte";

const ZAHLEN = ["basis_ml", "glucose_g", "aminosaeuren_g", "lipide_g", "albumin_g", "natrium_mmol", "kalium_mmol",
  "phosphat_mmol", "calcium_mmol", "magnesium_mmol", "laufzeit_h", "tage_pro_woche", "pantozol_tage"] as const;
const AUSWAHL = ["basis_praeparat", "glucose_praeparat", "aminosaeuren_praeparat", "lipide_praeparat", "albumin_praeparat",
  "spurenelemente", "katheterschutz"] as const;
type ZahlFeld = (typeof ZAHLEN)[number];
type AuswahlFeld = (typeof AUSWAHL)[number];
type Formular = Record<ZahlFeld | AuswahlFeld, string> & { vitamine: number[]; bemerkung: string; pantozol_stufe: string; gueltig_ab: string };

const MAKRO: { feld: "glucose" | "aminosaeuren" | "lipide" | "albumin"; text: string; kategorie: string; kcal: number }[] = [
  { feld: "glucose", text: "Glucose", kategorie: "glucose", kcal: 4 },
  { feld: "aminosaeuren", text: "Aminosäuren", kategorie: "aminosaeuren", kcal: 4 },
  { feld: "lipide", text: "Lipide", kategorie: "lipide", kcal: 9 },
  { feld: "albumin", text: "Humanalbumin", kategorie: "albumin", kcal: 4 },
];
const ELEKTROLYTE: { feld: ZahlFeld; text: string }[] = [
  { feld: "natrium_mmol", text: "Natrium" }, { feld: "kalium_mmol", text: "Kalium" }, { feld: "phosphat_mmol", text: "Phosphat" },
  { feld: "calcium_mmol", text: "Calcium" }, { feld: "magnesium_mmol", text: "Magnesium" },
];

function leer(): Formular {
  const f = Object.fromEntries([...ZAHLEN, ...AUSWAHL].map((k) => [k, ""])) as Record<ZahlFeld | AuswahlFeld, string>;
  return { ...f, vitamine: [], bemerkung: "", pantozol_stufe: "0", gueltig_ab: datum(heuteIso()) };
}

function ausPlan(p: Plan, gueltig?: string): Formular {
  const f = leer();
  for (const k of ZAHLEN) f[k] = p[k] != null ? zahl(p[k] as number) : "";
  for (const k of AUSWAHL) f[k] = p[k] != null ? String(p[k]) : "";
  return { ...f, vitamine: [...p.vitamine], bemerkung: p.bemerkung, pantozol_stufe: String(p.pantozol_stufe ?? 0),
    gueltig_ab: gueltig ?? datum(p.gueltig_ab) };
}

function zahlWert(t: string): number | null {
  const z = eingabeZahl(t);
  return z && z !== "ungueltig" ? Number(z) : null;
}

/** Vergleichbare Form eines Werts (Komma/Punkt, leer, Zahlformat) */
function norm(f: Formular, k: keyof Formular): string {
  const v = f[k];
  if (Array.isArray(v)) return [...v].sort((a, b) => a - b).join(",");
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

export function PlanEditor() {
  const { patient } = useAkte();
  const { planId } = useParams();
  const [params] = useSearchParams();
  const vorlageId = params.get("vorlage");
  const navigate = useNavigate();
  const { darf } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const praeparate = usePraeparate();
  const einstellungen = useEinstellungen();
  const [f, setF] = useState<Formular | null>(null);
  const [leerBegonnen, setLeerBegonnen] = useState(false);
  const [lokal, setLokal] = useState<Feldfehler>({});
  const [neueId, setNeueId] = useState<number | null>(null); // Entwurf, der beim ersten Speichern angelegt wurde

  const entwurf = useQuery({ queryKey: ["plan", planId], queryFn: () => api<Plan>(`infusionsplaene/${planId}/`), enabled: !!planId });
  const aktuellId = patient.kopf?.aktueller_plan?.id;
  const vorgaengerId = planId ? entwurf.data?.vorgaenger : aktuellId;
  const vorgaenger = useQuery({ queryKey: ["plan", vorgaengerId], queryFn: () => api<Plan>(`infusionsplaene/${vorgaengerId}/`), enabled: !!vorgaengerId });
  const quelleId = vorlageId ?? (aktuellId ? String(aktuellId) : null);
  const quelle = useQuery({ queryKey: ["plan", quelleId], queryFn: () => api<Plan>(`infusionsplaene/${quelleId}/`), enabled: !planId && !!quelleId });

  // Formular einmal füllen: Entwurf, sonst Vorlage bzw. aktueller Plan, sonst leer
  useEffect(() => {
    if (f) return;
    if (planId) { if (entwurf.data) setF(ausPlan(entwurf.data)); return; }
    if (quelleId) { if (quelle.data) setF(ausPlan(quelle.data, datum(heuteIso()))); return; }
    setF(leer());
  }, [f, planId, entwurf.data, quelleId, quelle.data]);

  // höchstens ein Entwurf je Patient: einen vorhandenen Entwurf bearbeiten statt einen zweiten anzulegen
  const offeneEntwuerfe = useQuery({
    queryKey: ["patient", patient.id, "plaene", "entwurf"],
    queryFn: () => api<{ results: Plan[] }>(`infusionsplaene/?patient=${patient.id}&status=entwurf`),
    enabled: !planId,
  });
  useEffect(() => {
    const vorhanden = offeneEntwuerfe.data?.results[0];
    if (!planId && !neueId && vorhanden && !speichern.isPending) navigate(`/patienten/${patient.id}/plaene/${vorhanden.id}/bearbeiten`, { replace: true });
  }, [offeneEntwuerfe.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const vorher = useMemo(() => (vorgaenger.data ? ausPlan(vorgaenger.data) : null), [vorgaenger.data]);
  const geaendert = (k: keyof Formular) => !!(vorher && f && k !== "gueltig_ab" && norm(f, k) !== norm(vorher, k));

  const speichern = useMutation({
    mutationFn: async (freigeben: boolean) => {
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
      setLokal(fehler);
      if (Object.keys(fehler).length) throw new ApiFehler(400, "Bitte die markierten Felder prüfen.", null, fehler);
      Object.assign(daten, { gueltig_ab: gueltig, vitamine: f!.vitamine, bemerkung: f!.bemerkung, pantozol_stufe: Number(f!.pantozol_stufe) });
      let id = planId ? Number(planId) : neueId;
      if (!id) {
        const neu = await api<Plan>("infusionsplaene/entwurf/", {
          body: { patient: patient.id, ...(leerBegonnen ? { leer: true } : vorlageId ? { vorlage: Number(vorlageId) } : {}) },
        });
        id = neu.id;
        setNeueId(neu.id);
      }
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

  if (patient.ist_abgeschlossen || !darf("plaene_anlegen")) {
    return <Meldung art="warn">Infusionspläne anlegen darf nur, wer das Recht „Pläne anlegen“ hat, und nur bei offenen Akten.</Meldung>;
  }
  if (!f || praeparate.isLoading) return <Laden />;
  if (planId && entwurf.data && entwurf.data.status !== "entwurf") {
    return <Meldung art="warn">Dieser Plan ist freigegeben und unveränderlich. Bitte einen neuen Plan anlegen.</Meldung>;
  }

  const server: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const e: Feldfehler = { ...server, ...lokal };
  const p = praeparate.data ?? [];
  const setze = (k: keyof Formular) => (wert: string) => setF((a) => ({ ...a!, [k]: wert }));
  const kcalZeile = (feld: string, faktor: number) => { const g = zahlWert(f[`${feld}_g` as ZahlFeld]); return g == null ? null : Math.round(g * faktor); };
  const kcal = MAKRO.reduce((s, m) => s + (kcalZeile(m.feld, m.kcal) ?? 0), 0);
  const kcalVorher = vorher ? MAKRO.reduce((s, m) => s + (zahlWert(vorher[`${m.feld}_g` as ZahlFeld]) ?? 0) * m.kcal, 0) : null;
  const gewicht = patient.kopf?.gewicht ? Number(patient.kopf.gewicht.kg) : null;
  const anzahlGeaendert = vorher ? ([...ZAHLEN, ...AUSWAHL, "vitamine", "bemerkung", "pantozol_stufe"] as (keyof Formular)[]).filter(geaendert).length : 0;
  const es = einstellungen.data;
  const warnungen: string[] = [];
  if (es) {
    const pruefe = (wert: number | null, unten: unknown, oben: unknown, text: string, einheit: string) => {
      if (wert != null && (wert < Number(unten) || wert > Number(oben))) warnungen.push(`${text} ${zahl(wert)} ${einheit} außerhalb ${zahl(Number(unten))}–${zahl(Number(oben))} ${einheit}`);
    };
    pruefe(kcal, es.kcal_min_tag, es.kcal_max_tag, "Energie", "kcal");
    pruefe(zahlWert(f.glucose_g), es.glucose_min_g, es.glucose_max_g, "Glucose", "g");
    pruefe(zahlWert(f.aminosaeuren_g), es.aminosaeuren_min_g, es.aminosaeuren_max_g, "Aminosäuren", "g");
    pruefe(zahlWert(f.lipide_g), es.lipide_min_g, es.lipide_max_g, "Lipide", "g");
    pruefe(zahlWert(f.natrium_mmol), es.natrium_min_mmol, es.natrium_max_mmol, "Natrium", "mmol");
    pruefe(zahlWert(f.kalium_mmol), es.kalium_min_mmol, es.kalium_max_mmol, "Kalium", "mmol");
  }
  const vitamineListe = p.filter((x) => x.kategorie === "vitamine");
  const zahlFeld = (k: ZahlFeld, label: string, einheit: string, extra?: ReactNode) => (
    <Feld label={label} fehler={e[k]} hinweis={extra}>
      {(pp) => <Einheit einheit={einheit}><Eingabe {...pp} className={cx("num pr-14", geaendert(k) && "border-warn bg-warn-bg")} value={f[k]}
        onChange={(ev) => setze(k)(ev.target.value)} inputMode="decimal" /></Einheit>}
    </Feld>
  );

  return (
    <form className="flex flex-col gap-5" noValidate onSubmit={(ev) => { ev.preventDefault(); speichern.mutate(false); }} data-testid="plan-editor">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-1">
          <span className="text-sm gedaempft">
            <Link to={`/patienten/${patient.id}`} className="no-underline">{name(patient)}</Link> · Nr. {nummer(patient.nummer)}
            {patient.kopf?.gewicht ? ` · ${kg(patient.kopf.gewicht.kg)} am ${datum(patient.kopf.gewicht.am)}` : ""}
          </span>
          <h2 className="m-0 text-[1.625rem] font-semibold">{planId ? "Entwurf bearbeiten" : "Neuer Infusionsplan"}</h2>
          <span className="text-sm gedaempft">
            {leerBegonnen ? "Leer begonnen. " : vorgaenger.data ? `${planId ? "Vorgänger" : vorlageId ? "Vorlage geladen, Vorgänger" : "Vorbelegt mit dem aktuellen Plan"} vom ${datum(vorgaenger.data.gueltig_ab)}. ` : "Erster Plan dieses Patienten. "}
            {vorher ? <>Geänderte Werte sind <span className="bg-warn-bg border border-warn rounded px-1">markiert</span>.</> : null}
          </span>
        </div>
        <div className="flex gap-2">
          {!planId ? <Knopf onClick={() => { setF(leer()); setLeerBegonnen(true); }}>Leer beginnen</Knopf> : null}
          <KnopfLink to={`/patienten/${patient.id}/plaene`}>Frühere Pläne</KnopfLink>
        </div>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-5 items-start">
        <div className="flex flex-col gap-4 min-w-0">
          <Karte className="px-5 py-[18px] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Basislösung</h3>
            <div className="grid grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-3">
              <Feld label="Präparat" fehler={e.basis_praeparat}>
                {(pp) => <PraeparatAuswahl id={pp.id} wert={f.basis_praeparat} onWahl={setze("basis_praeparat")} kategorie="basisloesung" praeparate={p} markiert={geaendert("basis_praeparat")} invalid={!!e.basis_praeparat} />}
              </Feld>
              {zahlFeld("basis_ml", "Volumen", "ml")}
            </div>
          </Karte>

          <Karte className="px-5 py-[18px] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Makronährstoffe</h3>
            <table className="tabelle">
              <thead><tr><th className="th">Komponente</th><th className="th">Präparat</th><th className="th text-right">vorher</th><th className="th">Menge g</th><th className="th text-right">kcal/g</th><th className="th text-right">kcal</th></tr></thead>
              <tbody>
                {MAKRO.map((m) => {
                  const gFeld = `${m.feld}_g` as ZahlFeld;
                  const pFeld = `${m.feld}_praeparat` as AuswahlFeld;
                  const z = kcalZeile(m.feld, m.kcal);
                  return (
                    <tr key={m.feld}>
                      <td className="td">{m.text}</td>
                      <td className="td">
                        <PraeparatAuswahl wert={f[pFeld]} onWahl={setze(pFeld)} kategorie={m.kategorie} praeparate={p} label={`Präparat ${m.text}`}
                          markiert={geaendert(pFeld)} invalid={!!e[pFeld]} />
                        {e[pFeld] ? <span className="fehlertext" role="alert">{e[pFeld]}</span> : null}
                      </td>
                      <td className="td num text-right gedaempft">{vorher?.[gFeld] || "—"}</td>
                      <td className="td w-[120px]">
                        <Eingabe aria-label={`Menge ${m.text} in g`} className={cx("num", geaendert(gFeld) && "border-warn bg-warn-bg")} value={f[gFeld]}
                          onChange={(ev) => setze(gFeld)(ev.target.value)} inputMode="decimal" aria-invalid={e[gFeld] ? true : undefined} />
                        {e[gFeld] ? <span className="fehlertext" role="alert">{e[gFeld]}</span> : null}
                      </td>
                      <td className="td num text-right">{m.kcal}</td>
                      <td className="td num text-right">{z != null ? zahl(z) : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <span className="text-[0.8125rem] gedaempft">kcal werden berechnet wie im Altsystem: Glucose, Aminosäuren und Albumin 4 kcal/g, Lipide 9 kcal/g.</span>
          </Karte>

          <Karte className="px-5 py-[18px] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Elektrolyte</h3>
            <div className="grid grid-cols-5 gap-3">{ELEKTROLYTE.map((x) => <div key={x.feld}>{zahlFeld(x.feld, x.text, "mmol")}</div>)}</div>
          </Karte>

          <Karte className="px-5 py-[18px] flex flex-col gap-3.5">
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
                  <button key={v.id} type="button" className="bg-transparent border border-dashed border-rand rounded-md px-2 h-[22px] text-xs cursor-pointer text-text2"
                    onClick={() => setF((a) => ({ ...a!, vitamine: [...a!.vitamine, v.id] }))}>+ {v.anzeige}</button>
                ))}
              </div>
              {e.vitamine ? <span className="fehlertext" role="alert">{e.vitamine}</span> : null}
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium" id="plan-kommentar">Kommentar</span>
              <Editor wert={f.bemerkung} onAenderung={setze("bemerkung")} label="Kommentar" werkzeuge={false} hoehe={56} />
            </div>
          </Karte>
        </div>

        <aside className="flex flex-col gap-4">
          <Karte className="px-5 py-[18px] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Gültigkeit, Laufzeit</h3>
            <div className="grid grid-cols-2 gap-3">
              <Feld label="gültig ab" fehler={e.gueltig_ab}>{(pp) => <Eingabe {...pp} className="num" value={f.gueltig_ab} onChange={(ev) => setze("gueltig_ab")(ev.target.value)} />}</Feld>
              {zahlFeld("laufzeit_h", "Laufzeit", "h", vorher ? (norm(f, "laufzeit_h") === norm(vorher, "laufzeit_h") ? "unverändert" : `vorher ${vorher.laufzeit_h || "—"} h`) : undefined)}
              {zahlFeld("tage_pro_woche", "Tage pro Woche", "×")}
            </div>
            <span className="text-xs gedaempft" title="Unklarheit U2">Gesamtvolumen und Laufrate (ml/h): Eingabe oder Berechnung ist noch nicht geklärt (U2).</span>
          </Karte>
          <Karte className="px-5 py-[18px] flex flex-col gap-3.5">
            <h3 className="lbl m-0">Pantozol</h3>
            <Feld label="Pantozol" hinweis="Bedeutung der Stufen noch offen (U1)" fehler={e.pantozol_stufe}>
              {(pp) => (
                <Auswahl {...pp} value={f.pantozol_stufe} onChange={(ev) => setF((a) => ({ ...a!, pantozol_stufe: ev.target.value, pantozol_tage: ev.target.value === "0" ? "" : a!.pantozol_tage }))}
                  className={cx(geaendert("pantozol_stufe") && "border-warn bg-warn-bg")}>
                  <option value="0">kein</option><option value="1">1</option><option value="2">2</option><option value="3">3</option>
                </Auswahl>
              )}
            </Feld>
            {zahlFeld("pantozol_tage", "Pantozol-Zeit", "", "Einheit noch offen (U1) · im Altsystem Werte 1–7, meist 5")}
          </Karte>
          <Karte className="px-5 py-[18px] flex flex-col gap-3">
            <h3 className="lbl m-0">Summe</h3>
            <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1.5 text-sm" data-testid="plan-summe">
              <span className="gedaempft">Energie</span>
              <span className="num">{zahl(kcal)} kcal{kcalVorher != null && Math.round(kcalVorher) !== kcal ? <span className="text-warn"> {kcal - Math.round(kcalVorher) > 0 ? "+" : "−"}{zahl(Math.abs(kcal - Math.round(kcalVorher)))}</span> : null}</span>
              <span className="gedaempft">je kg Körpergewicht</span><span className="num">{gewicht ? `${zahl(kcal / gewicht, 1)} kcal/kg` : "—"}</span>
              <span className="gedaempft">Geänderte Werte</span><span className="num">{anzahlGeaendert}</span>
            </div>
            {warnungen.length ? (
              <Meldung art="warn"><ul className="m-0 pl-4">{warnungen.map((w) => <li key={w}>{w}</li>)}</ul></Meldung>
            ) : <div className="meldung ok flex items-center gap-2 text-sm"><Icon name="haken" />Alle Werte im üblichen Bereich</div>}
          </Karte>
          {speichern.error && !Object.keys(server).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
          {Object.keys(e).length ? <Meldung art="fehler">Bitte die markierten Felder prüfen.{e.fehler ? ` ${e.fehler}` : ""}{e.kcal_manuell ? ` ${e.kcal_manuell}` : ""}</Meldung> : null}
          <div className="flex flex-col gap-2">
            {darf("plaene_freigeben") ? (
              <Knopf variante="pri" icon="haken" laedt={speichern.isPending && speichern.variables === true} disabled={speichern.isPending}
                onClick={() => speichern.mutate(true)}>Speichern und freigeben</Knopf>
            ) : null}
            <Knopf type="submit" laedt={speichern.isPending && speichern.variables === false} disabled={speichern.isPending}>Als Entwurf speichern</Knopf>
            <span className="text-xs gedaempft leading-normal">
              Freigeben darf, wer das Recht „Pläne freigeben“ hat (Mediziner). Der vorherige Plan bleibt im Verlauf erhalten.
              Die PDF bei Freigabe folgt mit der PDF-Erzeugung (F51).
            </span>
          </div>
        </aside>
      </div>
    </form>
  );
}
