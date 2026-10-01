/** Entwurf 18 · Vorlagen: Briefkopf und Logo, Auswahllisten und Präparate (Reihenfolge), Grenzwerte. */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useBriefkopf } from "@/lib/daten";
import type { Absender, Briefkopf } from "@/lib/daten";
import { eingabeZahl, zahl } from "@/lib/format";
import type { Auswahlwert, Einstellungen, Praeparat } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, Seitenkopf, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { useSortierbar } from "@/components/ui/sortierbar";
import { LOGO_URL, Logo } from "@/components/layout/logo";

type Bereich = "briefkopf" | "listen" | "grenzwerte";
type SpeichernRef = { current: (() => void) | null };

const ABSENDER_FELDER: { k: keyof Absender; label: string; span: number; num?: boolean }[] = [
  { k: "name", label: "Name", span: 4 }, { k: "strasse", label: "Straße", span: 2 }, { k: "plz", label: "PLZ", span: 1, num: true },
  { k: "ort", label: "Ort", span: 1 }, { k: "telefon", label: "Telefon", span: 2, num: true }, { k: "fax", label: "Fax", span: 2, num: true },
  { k: "email", label: "E-Mail", span: 2 }, { k: "internet", label: "Internet", span: 2 }, { k: "fusszeile", label: "Fußzeile", span: 4 },
];

function BriefkopfBereich({ speichernRef }: { speichernRef: SpeichernRef }) {
  const briefkopf = useBriefkopf();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [aktiv, setAktiv] = useState<"stiftung" | "gug">("stiftung");
  const [absender, setAbsender] = useState<Briefkopf["absender"] | null>(null);
  const [logoFehler, setLogoFehler] = useState("");
  const datei = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (briefkopf.data && !absender) { setAktiv(briefkopf.data.aktiv); setAbsender(structuredClone(briefkopf.data.absender)); }
  }, [briefkopf.data, absender]);
  const speichern = useMutation({
    mutationFn: () => api<Briefkopf>("briefkopf/", { method: "PATCH", body: { aktiv, absender } }),
    onSuccess: (b) => { qc.setQueryData(["briefkopf"], b); setAbsender(structuredClone(b.absender)); melden("Briefkopf gespeichert."); },
  });
  speichernRef.current = () => speichern.mutate();
  const hochladen = useMutation({
    mutationFn: (f: File) => { const form = new FormData(); form.append("datei", f); return api("briefkopf/logo/", { form }); },
    onSuccess: () => { setLogoFehler(""); void qc.invalidateQueries({ queryKey: ["briefkopf"] }); melden("Neues Logo gespeichert."); },
    onError: (e) => setLogoFehler(e instanceof ApiFehler ? Object.values(e.felder)[0] || e.message : String(e)),
  });
  if (!briefkopf.data || !absender) return <Laden />;
  const a = absender[aktiv];
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const version = briefkopf.data.logo.sha256;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_420px] gap-5 items-start">
      <div className="flex flex-col gap-4 min-w-0">
        <Karte className="px-5 py-[18px] flex flex-col gap-3" data-testid="logo">
          <h2 className="lbl m-0">Logo</h2>
          <div className="flex items-center gap-5 flex-wrap">
            <Logo className="h-[72px] w-[240px] border border-rand rounded-lg p-1.5 bg-white" version={version} />
            <div className="flex flex-col gap-1.5">
              <Knopf icon="hochladen" laedt={hochladen.isPending} onClick={() => datei.current?.click()}>Neues Logo hochladen</Knopf>
              <span className="text-xs gedaempft">PNG oder SVG, quer, mind. 600 px breit</span>
              <input ref={datei} type="file" hidden aria-label="Logo-Datei" accept=".png,.svg,image/png,image/svg+xml"
                onChange={(e) => { const x = e.target.files?.[0]; if (x) hochladen.mutate(x); e.target.value = ""; }} />
            </div>
          </div>
          {logoFehler ? <Meldung art="fehler">{logoFehler}</Meldung> : null}
          {briefkopf.data.logo.vorhanden ? <span className="text-xs gedaempft">{briefkopf.data.logo.mime === "image/svg+xml" ? "SVG" : `PNG ${briefkopf.data.logo.breite} × ${briefkopf.data.logo.hoehe} px`} · <a href={`${LOGO_URL}?v=${version?.slice(0, 12)}`} target="_blank" rel="noopener">öffnen</a></span>
            : <span className="text-xs gedaempft">Noch kein eigenes Logo hochgeladen – angezeigt wird das mitgelieferte Stiftungslogo.</span>}
        </Karte>
        <Karte className="px-5 py-[18px] flex flex-col gap-3.5" data-testid="absender">
          <h2 className="lbl m-0">Absender auf Infusionsplänen und PDFs</h2>
          <div role="radiogroup" aria-label="Absender" className="flex gap-5">
            {briefkopf.data.arten.map((x) => (
              <label key={x.code} className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="radio" name="absender" checked={aktiv === x.code} onChange={() => setAktiv(x.code as "stiftung" | "gug")} />{x.name}
              </label>
            ))}
          </div>
          <div className="grid grid-cols-4 gap-3">
            {ABSENDER_FELDER.map((x) => (
              <Feld key={x.k} label={x.label} className={x.span === 4 ? "col-span-4" : x.span === 2 ? "col-span-2" : undefined} fehler={f[`absender.${aktiv}.${x.k}`]}>
                {(p) => <Eingabe {...p} className={x.num ? "num" : undefined} value={a[x.k]} onChange={(e) => setAbsender({ ...absender, [aktiv]: { ...a, [x.k]: e.target.value } })} />}
              </Feld>
            ))}
          </div>
          <span className="text-xs gedaempft">Beide Absender bleiben gespeichert; ausgewählt wird, welcher auf neuen PDFs steht.</span>
          {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
        </Karte>
      </div>
      <Karte className="px-5 py-[18px] flex flex-col gap-3">
        <h2 className="lbl m-0">Vorschau Briefkopf</h2>
        <div className="pdf-blatt px-6 py-5 flex flex-col gap-3 text-[#1b1932]" data-testid="briefkopf-vorschau">
          <div className="flex items-start justify-between gap-4">
            <Logo className="h-[48px] w-[160px]" version={version} />
            <div className="flex flex-col items-end text-[10px] leading-snug">
              <span>{a.strasse} · {a.plz} {a.ort}</span>
              {a.telefon ? <span>Tel. {a.telefon}</span> : null}
              {a.email ? <span>{a.email}</span> : null}
            </div>
          </div>
          <div className="text-base font-semibold border-b border-[#1b1932] pb-1">Infusionsplan</div>
          <div className="h-2 rounded bg-[#e6e5ee] w-4/5" /><div className="h-2 rounded bg-[#e6e5ee] w-3/5" /><div className="h-2 rounded bg-[#e6e5ee] w-2/3" />
          <div className="text-[9px] text-[#5d5b72] text-center border-t border-[#e6e5ee] pt-1.5">{[a.name, a.fusszeile].filter(Boolean).join(" · ")}</div>
        </div>
        <span className="text-xs gedaempft">Gilt für neue PDFs. Bereits freigegebene Pläne behalten ihren Briefkopf.</span>
      </Karte>
    </div>
  );
}

type Liste = { schluessel: string; titel: string; art: "praeparat" | "auswahl" };
const LISTEN: Liste[] = [
  { schluessel: "aminosaeuren", titel: "Aminosäuren", art: "praeparat" }, { schluessel: "lipide", titel: "Lipide", art: "praeparat" },
  { schluessel: "basisloesung", titel: "Basislösungen", art: "praeparat" }, { schluessel: "glucose", titel: "Glucose", art: "praeparat" },
  { schluessel: "albumin", titel: "Albumin", art: "praeparat" }, { schluessel: "spurenelemente", titel: "Spurenelemente", art: "praeparat" },
  { schluessel: "vitamine", titel: "Vitamine", art: "praeparat" }, { schluessel: "katheterschutz", titel: "Katheterblock", art: "praeparat" },
  { schluessel: "elektrolyte", titel: "Elektrolytzusätze", art: "praeparat" }, { schluessel: "medikament", titel: "Medikamente", art: "praeparat" },
  { schluessel: "katheter", titel: "Katheter", art: "auswahl" }, { schluessel: "terminort", titel: "Terminorte", art: "auswahl" },
  { schluessel: "dokumenttyp", titel: "Dokumenttypen", art: "auswahl" },
  { schluessel: "beziehung", titel: "Beziehungen (Bezugspersonen)", art: "auswahl" },
];

function EintragDialog({ liste, eintrag, onZu }: { liste: Liste; eintrag: Praeparat | Auswahlwert | null | "neu"; onZu: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [name, setName] = useState("");
  const [konz, setKonz] = useState("");
  const [einheit, setEinheit] = useState("ml");
  useEffect(() => {
    if (eintrag && eintrag !== "neu") {
      if ("kategorie" in eintrag) { setName(eintrag.name); setKonz(eintrag.konzentration); setEinheit(eintrag.einheit); }
      else setName(eintrag.wert);
    } else { setName(""); setKonz(""); setEinheit("ml"); }
  }, [eintrag]);
  const speichern = useMutation({
    mutationFn: () => {
      const neu = eintrag === "neu";
      if (liste.art === "praeparat") {
        const daten = { name, konzentration: konz, einheit, ...(neu ? { kategorie: liste.schluessel } : {}) };
        return neu ? api("praeparate/", { body: daten }) : api(`praeparate/${(eintrag as Praeparat).id}/`, { method: "PATCH", body: daten });
      }
      return neu ? api("auswahlwerte/", { body: { liste: liste.schluessel, wert: name } })
        : api(`auswahlwerte/${(eintrag as Auswahlwert).id}/`, { method: "PATCH", body: { wert: name } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [liste.art === "praeparat" ? "praeparate" : "auswahlwerte"] });
      melden("Gespeichert.");
      onZu();
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} titel={`${liste.titel}: ${eintrag === "neu" ? "neuer Eintrag" : "bearbeiten"}`} breite={520}
      beschreibung="Änderungen gelten für neue Einträge und Pläne; bestehende Pläne behalten ihre Werte."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf><Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <form className="grid grid-cols-3 gap-3" onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        <Feld label={liste.art === "praeparat" ? "Name" : "Wert"} className={liste.art === "praeparat" ? "col-span-3" : "col-span-3"} fehler={f.name ?? f.wert ?? f.non_field_errors}>
          {(p) => <Eingabe {...p} value={name} onChange={(e) => setName(e.target.value)} autoFocus />}
        </Feld>
        {liste.art === "praeparat" ? <>
          <Feld label="Konzentration" hinweis="z. B. 13,4 %" className="col-span-2" fehler={f.konzentration}>{(p) => <Eingabe {...p} value={konz} onChange={(e) => setKonz(e.target.value)} />}</Feld>
          <Feld label="Einheit" fehler={f.einheit}>{(p) => <Eingabe {...p} value={einheit} onChange={(e) => setEinheit(e.target.value)} />}</Feld>
        </> : null}
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler" className="col-span-3">{speichern.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

function ListenBereich() {
  const [gewaehlt, setGewaehlt] = useState<Liste>(LISTEN[0]);
  const [dialog, setDialog] = useState<Praeparat | Auswahlwert | null | "neu">(null);
  const qc = useQueryClient();
  const melden = useHinweis();
  const praeparate = useQuery({ queryKey: ["praeparate", "alle"], queryFn: () => api<Praeparat[]>("praeparate/") });
  const auswahl = useQuery({ queryKey: ["auswahlwerte", "verwaltung"], queryFn: () => api<Auswahlwert[]>("auswahlwerte/") });
  const eintraege: (Praeparat | Auswahlwert)[] = gewaehlt.art === "praeparat"
    ? (praeparate.data ?? []).filter((p) => p.kategorie === gewaehlt.schluessel)
    : (auswahl.data ?? []).filter((a) => a.liste === gewaehlt.schluessel);
  const [reihe, setReihe] = useState<(Praeparat | Auswahlwert)[]>([]);
  const signatur = eintraege.map((e) => `${e.id}:${e.reihenfolge}:${e.aktiv}:${"name" in e ? e.anzeige : e.wert}`).join("|");
  useEffect(() => setReihe(eintraege), [signatur, gewaehlt.schluessel]); // eslint-disable-line react-hooks/exhaustive-deps
  const pfad = gewaehlt.art === "praeparat" ? "praeparate" : "auswahlwerte";
  const neuLaden = () => {
    void qc.invalidateQueries({ queryKey: ["praeparate"] });
    void qc.invalidateQueries({ queryKey: ["auswahlwerte"] });
  };
  const reihenfolge = useMutation({
    mutationFn: (ids: number[]) => api(`${pfad}/reihenfolge/`, { body: { ids } }),
    onSuccess: () => { neuLaden(); melden("Reihenfolge gespeichert."); },
  });
  const aktiv = useMutation({
    mutationFn: (e: Praeparat | Auswahlwert) => api(`${pfad}/${e.id}/`, { method: "PATCH", body: { aktiv: !e.aktiv } }),
    // Häkchen sofort umschalten; bei einem Fehler den gespeicherten Stand wieder anzeigen
    onMutate: (e) => setReihe((r) => r.map((x) => (x.id === e.id ? { ...x, aktiv: !e.aktiv } : x))),
    onError: (_f, e) => setReihe((r) => r.map((x) => (x.id === e.id ? { ...x, aktiv: e.aktiv } : x))),
    onSettled: () => neuLaden(),
  });
  const sort = useSortierbar(reihe, (neu) => { setReihe(neu); reihenfolge.mutate(neu.map((e) => e.id)); });
  const anzahl = (l: Liste) => l.art === "praeparat" ? (praeparate.data ?? []).filter((p) => p.kategorie === l.schluessel).length
    : (auswahl.data ?? []).filter((a) => a.liste === l.schluessel).length;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[240px_minmax(0,1fr)] gap-5 items-start">
      <nav aria-label="Listen" className="card p-1.5 flex flex-col">
        {LISTEN.map((l) => (
          <button key={l.schluessel} type="button" aria-current={gewaehlt.schluessel === l.schluessel ? "true" : undefined}
            className={cx("flex items-center justify-between px-3 py-2 rounded-md border-0 cursor-pointer text-sm text-left", gewaehlt.schluessel === l.schluessel ? "bg-akzent-weich text-akzent-text font-medium" : "bg-transparent hover:bg-fein")}
            onClick={() => setGewaehlt(l)}>
            <span>{l.titel}</span><span className="num text-xs gedaempft">{anzahl(l)}</span>
          </button>
        ))}
      </nav>
      <Karte className="px-5 py-[18px] flex flex-col gap-3" data-testid="liste">
        <div className="flex items-center justify-between gap-3">
          <h2 className="lbl m-0">{gewaehlt.titel} · {gewaehlt.art === "praeparat" ? "Präparate" : "Auswahlwerte"}</h2>
          <Knopf klein icon="plus" onClick={() => setDialog("neu")}>{gewaehlt.art === "praeparat" ? "Präparat" : "Wert"}</Knopf>
        </div>
        {praeparate.isLoading || auswahl.isLoading ? <Laden /> : (
          <table className="tabelle">
            <thead><tr><th className="th w-10" /><th className="th">Name</th>{gewaehlt.art === "praeparat" ? <><th className="th">Konzentration</th><th className="th text-right">in Plänen</th></> : null}<th className="th">Auswahl</th></tr></thead>
            <tbody>
              {reihe.map((e, i) => (
                <tr key={e.id} {...sort.zeile(i)} className={cx(sort.ueber === i && "outline-2 outline-akzent", sort.zieht === i && "opacity-50", !e.aktiv && "opacity-70")}>
                  <td className="td"><button type="button" className="border-0 bg-transparent cursor-grab gedaempft p-0 tracking-[-2px]" {...sort.griff(i, "name" in e ? e.anzeige : e.wert, "vorlagen")}>⋮⋮</button></td>
                  <td className="td">
                    <button type="button" className="bg-transparent border-0 p-0 cursor-pointer text-left text-akzent-text font-medium" onClick={() => setDialog(e)}>
                      {"name" in e ? e.anzeige : e.wert}
                    </button>
                  </td>
                  {"name" in e ? <><td className="td num">{e.konzentration || "—"}</td><td className="td num text-right">{zahl(e.in_plaenen)}</td></> : null}
                  <td className="td">
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input type="checkbox" checked={e.aktiv} aria-label={`${"name" in e ? e.anzeige : e.wert} in der Auswahl`} onChange={() => aktiv.mutate(e)} />
                      {e.aktiv ? "aktiv" : "ausgeblendet"}
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <Fehleranzeige fehler={reihenfolge.error ?? aktiv.error} />
        <div className="text-[0.8125rem] gedaempft leading-normal">
          Reihenfolge per Ziehen am Griff oder mit den Pfeiltasten. Ausgeblendete Einträge erscheinen nicht mehr bei neuen Plänen und Akten, bestehende behalten sie. Gelöscht wird nichts.
        </div>
      </Karte>
      <EintragDialog liste={gewaehlt} eintrag={dialog} onZu={() => setDialog(null)} />
    </div>
  );
}

const HINWEISE: { k: string; label: string; einheit: string }[] = [
  { k: "gewicht_warnung_prozent", label: "Warnung Gewichtsverlust", einheit: "%" },
  { k: "gewicht_warnung_monate", label: "Zeitraum dafür", einheit: "Monaten" },
  { k: "plan_alter_warnung_monate", label: "Infusionsplan gilt als alt nach", einheit: "Monaten" },
  { k: "kontakt_ueberfaellig_monate", label: "Kontakt überfällig nach", einheit: "Monaten" },
];
const GRENZEN: { text: string; min: string; max: string; einheit: string }[] = [
  { text: "Energie", min: "kcal_min_tag", max: "kcal_max_tag", einheit: "kcal" },
  { text: "Gesamtvolumen", min: "volumen_min_ml", max: "volumen_max_ml", einheit: "ml" },
  { text: "Glucose", min: "glucose_min_g", max: "glucose_max_g", einheit: "g" },
  { text: "Aminosäuren", min: "aminosaeuren_min_g", max: "aminosaeuren_max_g", einheit: "g" },
  { text: "Lipide", min: "lipide_min_g", max: "lipide_max_g", einheit: "g" },
  { text: "Natrium", min: "natrium_min_mmol", max: "natrium_max_mmol", einheit: "mmol" },
  { text: "Kalium", min: "kalium_min_mmol", max: "kalium_max_mmol", einheit: "mmol" },
  { text: "Gewicht", min: "gewicht_min_kg", max: "gewicht_max_kg", einheit: "kg" },
  { text: "Größe", min: "groesse_min_cm", max: "groesse_max_cm", einheit: "cm" },
];

function Einheit({ children, einheit }: { children: ReactNode; einheit: string }) {
  return <span className="relative block">{children}<span className="absolute right-3 top-1/2 -translate-y-1/2 text-[0.8125rem] gedaempft pointer-events-none">{einheit}</span></span>;
}

function GrenzwerteBereich({ speichernRef }: { speichernRef: SpeichernRef }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const daten = useQuery({ queryKey: ["einstellungen"], queryFn: () => api<Einstellungen>("einstellungen/") });
  const [w, setW] = useState<Record<string, string> | null>(null);
  useEffect(() => {
    if (daten.data && !w) setW(Object.fromEntries(Object.entries(daten.data).map(([k, v]) => [k, typeof v === "number" ? zahl(v).replace(/\./g, "") : String(v)])));
  }, [daten.data, w]);
  const speichern = useMutation({
    mutationFn: () => {
      const felder = [...HINWEISE.map((h) => h.k), ...GRENZEN.flatMap((g) => [g.min, g.max])];
      const fehler: Feldfehler = {};
      const body: Record<string, string | null> = {};
      for (const k of felder) {
        const z = eingabeZahl(w![k] ?? "");
        if (!z || z === "ungueltig") fehler[k] = "Bitte eine Zahl eingeben.";
        body[k] = z;
      }
      if (Object.keys(fehler).length) throw new ApiFehler(400, "Bitte die markierten Werte prüfen.", null, fehler);
      return api<Einstellungen>("einstellungen/", { method: "PATCH", body });
    },
    onSuccess: (e) => {
      qc.setQueryData(["einstellungen"], e);
      setW(null);
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden("Grenzwerte gespeichert.");
    },
  });
  speichernRef.current = () => speichern.mutate();
  if (!w) return <Laden />;
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const eingabe = (k: string, label: string) => (
    <Eingabe aria-label={label} className="num" value={w[k] ?? ""} onChange={(e) => setW({ ...w, [k]: e.target.value })} aria-invalid={f[k] ? true : undefined} />
  );
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-5 items-start" data-testid="grenzwerte">
      <Karte className="px-5 py-[18px] flex flex-col gap-3.5">
        <h2 className="lbl m-0">Hinweise auf Startseite und in der Liste</h2>
        <div className="grid grid-cols-2 gap-3">
          {HINWEISE.map((h) => (
            <Feld key={h.k} label={h.label} fehler={f[h.k]}>
              {(p) => <Einheit einheit={h.einheit}><Eingabe {...p} className="num pr-20" value={w[h.k] ?? ""} onChange={(e) => setW({ ...w, [h.k]: e.target.value })} /></Einheit>}
            </Feld>
          ))}
        </div>
        <span className="text-[0.8125rem] gedaempft">Beispiel: Warnung, wenn ein Patient mehr als {w.gewicht_warnung_prozent} % in {w.gewicht_warnung_monate} Monaten abnimmt.</span>
      </Karte>
      <Karte className="px-5 py-[18px] flex flex-col gap-3">
        <h2 className="lbl m-0">Plausibilitätsgrenzen bei der Eingabe</h2>
        <table className="tabelle">
          <thead><tr><th className="th">Wert</th><th className="th">Minimum</th><th className="th">Maximum</th><th className="th">Einheit</th></tr></thead>
          <tbody>
            {GRENZEN.map((g) => (
              <tr key={g.text}>
                <td className="td">{g.text}</td>
                <td className="td">{eingabe(g.min, `${g.text} minimal`)}{f[g.min] ? <span className="fehlertext" role="alert">{f[g.min]}</span> : null}</td>
                <td className="td">{eingabe(g.max, `${g.text} maximal`)}{f[g.max] ? <span className="fehlertext" role="alert">{f[g.max]}</span> : null}</td>
                <td className="td">{g.einheit}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <span className="text-xs gedaempft">Das Gesamtvolumen wird wie im Altsystem berechnet (Körpergewicht × 35 ml) und gegen diese Grenzen geprüft.</span>
        <div className="text-[0.8125rem] gedaempft">Werte außerhalb werden nicht gespeichert. Im Altsystem standen z. B. 433.564 kcal und 9.999 kg.</div>
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      </Karte>
    </div>
  );
}

export function Vorlagen() {
  const [bereich, setBereich] = useState<Bereich>("briefkopf");
  const speichern = useRef<(() => void) | null>(null);
  return (
    <Seite pfad={[{ text: "Administration" }, { text: "Vorlagen" }]}>
      <Seitenkopf titel="Vorlagen" unter="Alles, was sich ohne IT anpassen lassen soll. Jede Änderung steht im Audit-Log."
        rechts={bereich !== "listen" ? <Knopf variante="pri" onClick={() => speichern.current?.()}>Speichern</Knopf> : null} />
      <div className="flex items-center gap-3 flex-wrap">
        <Segmente label="Bereich" wert={bereich} onWahl={setBereich}
          werte={[{ wert: "briefkopf", text: "Briefkopf und Logo" }, { wert: "listen", text: "Auswahllisten" }, { wert: "grenzwerte", text: "Grenzwerte" }]} />
        <span className="btn sec opacity-60 cursor-not-allowed" aria-disabled="true" title="Dokumentvorlagen (WYSIWYG) folgen mit F50">
          Dokumentvorlagen <span className="chip">folgt</span>
        </span>
      </div>
      {bereich === "briefkopf" ? <BriefkopfBereich speichernRef={speichern} /> : bereich === "listen" ? <ListenBereich /> : <GrenzwerteBereich speichernRef={speichern} />}
    </Seite>
  );
}
