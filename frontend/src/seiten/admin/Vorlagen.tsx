/** Entwurf 18 · Vorlagen: Übersicht mit Suche (F180), Briefkopf und Logo, Grenzwerte; Auswahllisten und Präparate in
 *  Auswahllisten.tsx, Dokumentvorlagen in Dokumentvorlagen.tsx. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useT } from "@/lib/sprache";
import { useBlocker, useLocation, useNavigate, useSearchParams } from "react-router";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Feldfehler } from "@/lib/api";
import { useBriefkopf } from "@/lib/daten";
import type { Absender, Briefkopf } from "@/lib/daten";
import { datum, eingabeZahl, zahl } from "@/lib/format";
import { ERKLAERUNGEN } from "@/lib/typen";
import type { Einstellungen, ErklaerungsArt } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Eingabe, Feld, Karte, Knopf, Laden, Meldung, Seitenkopf, Segmente, Textfeld } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { LOGO_URL, Logo } from "@/components/layout/logo";
import { DokumentvorlagenBereich } from "@/seiten/admin/Dokumentvorlagen";
import { KatalogeBereich } from "@/seiten/admin/Kataloge";
import { AnlagenBereich } from "@/seiten/admin/Anlagen";
import { KiPromptsBereich } from "@/seiten/admin/KiPrompts";
import { ListenBereich } from "@/seiten/admin/Auswahllisten";
import { VorlagenStart } from "@/seiten/admin/VorlagenStart";

type Bereich = "start" | "briefkopf" | "listen" | "kataloge" | "grenzwerte" | "anlagen" | "ki" | "dokumente";
type SpeichernRef = { current: (() => void) | null };

const ABSENDER_FELDER: { k: keyof Absender; label: string; span: number; num?: boolean }[] = [
  { k: "name", label: "Name", span: 4 }, { k: "strasse", label: "Straße", span: 2 }, { k: "plz", label: "PLZ", span: 1, num: true },
  { k: "ort", label: "Ort", span: 1 }, { k: "telefon", label: "Telefon", span: 2, num: true }, { k: "fax", label: "Fax", span: 2, num: true },
  { k: "email", label: "E-Mail", span: 2 }, { k: "internet", label: "Internet", span: 2 }, { k: "fusszeile", label: "Fußzeile", span: 4 },
  // in der Fußzeile der Dokumentvorlagen als „Vorstand“ und „Spendenkonto“ (14.10.2026)
  { k: "vorstand", label: "Vorstand", span: 4 }, { k: "bankverbindung", label: "Bankverbindung (Spendenkonto)", span: 4 },
];

function BriefkopfBereich({ speichernRef }: { speichernRef: SpeichernRef }) {
  const briefkopf = useBriefkopf();
  // Briefkopf und Logo je Firma (11.10.2026): eine weitere Firma hat einen festen eigenen Absender
  const firma = briefkopf.data?.firma;
  const fest = firma && firma.kuerzel !== "dskm" && firma.absender ? firma.absender : null;
  const qc = useQueryClient();
  const melden = useHinweis();
  const [aktiv, setAktiv] = useState<string>("stiftung");
  const [absender, setAbsender] = useState<Briefkopf["absender"] | null>(null);
  const [logoFehler, setLogoFehler] = useState("");
  const datei = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (briefkopf.data && !absender) { setAktiv(fest ?? briefkopf.data.aktiv); setAbsender(structuredClone(briefkopf.data.absender)); }
  }, [briefkopf.data, absender]);
  const speichern = useMutation({
    // weitere Firma: nur ihr eigener Absender; die Wahl Stiftung/GuG gilt für die DSKM
    mutationFn: () => api<Briefkopf>("briefkopf/", { method: "PATCH", body: fest ? { absender: { [fest]: absender![fest] } } : { aktiv, absender } }),
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
    <div className="stapel grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_26.25rem] gap-5 items-start">
      <div className="flex flex-col gap-4 min-w-0">
        <Karte className="px-5 py-[1.125rem] flex flex-col gap-3" data-testid="logo">
          <h2 className="lbl m-0">Logo{firma && (briefkopf.data.arten.length > 2 || fest) ? ` · ${firma.name}` : ""}</h2>
          <div className="flex items-center gap-5 flex-wrap">
            <Logo className="h-[4.5rem] w-[15rem] border border-rand rounded-lg p-1.5 bg-white" version={version} firma={firma?.kuerzel} name={firma?.name} />
            <div className="flex flex-col gap-1.5">
              <Knopf icon="hochladen" laedt={hochladen.isPending} onClick={() => datei.current?.click()}>Neues Logo hochladen</Knopf>
              <span className="text-xs gedaempft">PNG oder SVG, quer, mind. 600 px breit</span>
              <input ref={datei} type="file" hidden aria-label="Logo-Datei" accept=".png,.svg,image/png,image/svg+xml"
                onChange={(e) => { const x = e.target.files?.[0]; if (x) hochladen.mutate(x); e.target.value = ""; }} />
            </div>
          </div>
          {logoFehler ? <Meldung art="fehler">{logoFehler}</Meldung> : null}
          {briefkopf.data.logo.vorhanden ? <span className="text-xs gedaempft">{briefkopf.data.logo.mime === "image/svg+xml" ? "SVG" : `PNG ${briefkopf.data.logo.breite} × ${briefkopf.data.logo.hoehe} px`} · <a href={`${LOGO_URL}?v=${version?.slice(0, 12)}`} target="_blank" rel="noopener">öffnen</a></span>
            : <span className="text-xs gedaempft">{fest ? `Noch kein Logo für ${firma!.name} hochgeladen – angezeigt wird der Name.`
              : "Noch kein eigenes Logo hochgeladen – angezeigt wird das mitgelieferte Stiftungslogo."}</span>}
        </Karte>
        <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5" data-testid="absender">
          <h2 className="lbl m-0">Absender auf Infusionsplänen und PDFs{fest ? ` · ${firma!.name}` : ""}</h2>
          {fest ? null : (
            <div role="radiogroup" aria-label="Absender" className="flex gap-5 flex-wrap">
              {/* der Absender einer weiteren Firma (z. B. Regeneration Clinic) wird in deren Firma gepflegt */}
              {briefkopf.data.arten.filter((x) => x.code === "stiftung" || x.code === "gug").map((x) => (
                <label key={x.code} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="radio" name="absender" checked={aktiv === x.code} onChange={() => setAktiv(x.code)} />{x.name}
                </label>
              ))}
            </div>
          )}
          <div className="grid grid-cols-4 gap-3">
            {ABSENDER_FELDER.map((x) => (
              <Feld key={x.k} label={x.label} className={x.span === 4 ? "col-span-4" : x.span === 2 ? "col-span-2" : undefined} fehler={f[`absender.${aktiv}.${x.k}`]}>
                {(p) => <Eingabe {...p} className={x.num ? "num" : undefined} value={a[x.k]} onChange={(e) => setAbsender({ ...absender, [aktiv]: { ...a, [x.k]: e.target.value } })} />}
              </Feld>
            ))}
          </div>
          <span className="text-xs gedaempft">{fest ? `Steht auf allen PDFs, die in der ${firma!.name} erstellt werden.`
            : "Beide Absender bleiben gespeichert; ausgewählt wird, welcher auf neuen PDFs steht."}</span>
          {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
        </Karte>
      </div>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3">
        <h2 className="lbl m-0">Vorschau Briefkopf</h2>
        <div className="pdf-blatt px-6 py-5 flex flex-col gap-3 text-[#1b1932]" data-testid="briefkopf-vorschau">
          <div className="flex items-start justify-between gap-4">
            <Logo className="h-[3rem] w-[10rem] min-w-0 shrink" version={version} firma={firma?.kuerzel} name={firma?.name} />
            <div className="flex flex-col items-end text-right text-[0.625rem] leading-snug min-w-0 [overflow-wrap:anywhere]">
              <span>{a.strasse} · {a.plz} {a.ort}</span>
              {a.telefon ? <span>Tel. {a.telefon}</span> : null}
              {a.email ? <span>{a.email}</span> : null}
            </div>
          </div>
          <div className="text-base font-semibold border-b border-[#1b1932] pb-1">Infusionsplan</div>
          <div className="h-2 rounded bg-[#e6e5ee] w-4/5" /><div className="h-2 rounded bg-[#e6e5ee] w-3/5" /><div className="h-2 rounded bg-[#e6e5ee] w-2/3" />
          <div className="text-[0.5625rem] text-[#5d5b72] text-center border-t border-[#e6e5ee] pt-1.5">{[a.name, a.fusszeile].filter(Boolean).join(" · ")}</div>
        </div>
        <span className="text-xs gedaempft">Gilt für neue PDFs. Bereits freigegebene Pläne behalten ihren Briefkopf.</span>
      </Karte>
    </div>
  );
}

const HINWEISE: { k: string; label: string; einheit: string }[] = [
  { k: "gewicht_warnung_prozent", label: "Warnung Gewichtsverlust", einheit: "%" },
  { k: "gewicht_warnung_monate", label: "Zeitraum dafür", einheit: "Monaten" },
  { k: "plan_alter_warnung_monate", label: "Infusionsplan gilt als alt nach", einheit: "Monaten" },
  // Befunde (Festlegung 07.10.2026, F120)
  { k: "labor_alter_warnung_monate", label: "Laborbefund gilt als alt nach", einheit: "Monaten" },
  { k: "bia_alter_warnung_monate", label: "BIA-Messung gilt als alt nach", einheit: "Monaten" },
  // Kontakt fällig in zwei Stufen (S04): erst „bald fällig“, dann „überfällig“
  { k: "kontakt_bald_monate", label: "Kontakt bald fällig nach", einheit: "Monaten" },
  { k: "kontakt_ueberfaellig_monate", label: "Kontakt überfällig nach", einheit: "Monaten" },
  // Wunsch 08.10.2026: Vorgabe für „Wiedervorlage anlegen“ beim Erfassen eines Kontakts (im Dialog änderbar)
  { k: "wiedervorlage_tage", label: "Wiedervorlage nach Kontakt in", einheit: "Tagen" },
  // Fehlende Angaben (F186): Hinweis „Kein Gewicht seit … Monaten“ in Akte, Liste und Tagesliste
  { k: "gewicht_fehlt_monate", label: "Gewicht fehlt, wenn keine Messung seit", einheit: "Monaten" },
];
// Datenschutz (docs/DATENSCHUTZ.md): Fristen und die Erklärungen, die in jeder Akte vorliegen sollen
const DATENSCHUTZ: { k: string; label: string; einheit: string; hinweis?: string }[] = [
  { k: "aufbewahrung_jahre", label: "Aufbewahrung nach Abschluss der Akte", einheit: "Jahre", hinweis: "danach kann die Akte gelöscht werden" },
  { k: "abschluss_pruefen_monate", label: "„Abschluss prüfen“, wenn kein Kontakt seit", einheit: "Monaten" },
  { k: "protokoll_aufbewahrung_jahre", label: "Audit-Log aufbewahren", einheit: "Jahre", hinweis: "0 = unbegrenzt; sonst werden ältere Einträge täglich endgültig entfernt" },
];
// Scans (Festlegung 08.10.2026, F165): Aufbewahrung nicht zugeordneter Scans und Obergrenzen
const SCANS: { k: string; label: string; einheit: string; hinweis?: string }[] = [
  { k: "scans_frist_tage", label: "Nicht zugeordnete Scans löschen nach", einheit: "Tagen" },
  { k: "scans_verlaengerung_tage", label: "„Verlängern“ verschiebt um", einheit: "Tage" },
  { k: "scans_hoechst_tage", label: "Höchstens aufbewahren", einheit: "Tage", hinweis: "ab dem Hochladen, auch mit Verlängern" },
  { k: "scans_max_anzahl", label: "Höchstens", einheit: "Scans" },
  { k: "scans_max_mb", label: "Speicher für Scans", einheit: "MB", hinweis: "ab 80 % Hinweis auf der Startseite" },
];
const GRENZEN: { text: string; min: string; max: string; einheit: string }[] = [
  { text: "Energie", min: "kcal_min_tag", max: "kcal_max_tag", einheit: "kcal" },
  { text: "Volumen im Mischbeutel", min: "volumen_min_ml", max: "volumen_max_ml", einheit: "ml" },
  { text: "Glucose", min: "glucose_min_g", max: "glucose_max_g", einheit: "g" },
  { text: "Aminosäuren", min: "aminosaeuren_min_g", max: "aminosaeuren_max_g", einheit: "g" },
  { text: "Lipide", min: "lipide_min_g", max: "lipide_max_g", einheit: "g" },
  { text: "Natrium", min: "natrium_min_mmol", max: "natrium_max_mmol", einheit: "mmol" },
  { text: "Kalium", min: "kalium_min_mmol", max: "kalium_max_mmol", einheit: "mmol" },
  { text: "Gewicht", min: "gewicht_min_kg", max: "gewicht_max_kg", einheit: "kg" },
  { text: "Größe", min: "groesse_min_cm", max: "groesse_max_cm", einheit: "cm" },
];

/** „Mengen nach Praxisvorgabe“ im Plan-Editor (F190): Mengen je kg des letzten Gewichts; Start wie im Altsystem */
const VORGABE_JE_KG: { k: string; text: string; einheit: string }[] = [
  { k: "vorgabe_glucose_g_kg", text: "Glucose", einheit: "g/kg" },
  { k: "vorgabe_aminosaeuren_g_kg", text: "Aminosäuren", einheit: "g/kg" },
  { k: "vorgabe_lipide_g_kg", text: "Lipide", einheit: "g/kg" },
  { k: "vorgabe_natrium_mmol_kg", text: "Natrium", einheit: "mmol/kg" },
  { k: "vorgabe_kalium_mmol_kg", text: "Kalium", einheit: "mmol/kg" },
  { k: "vorgabe_phosphat_mmol_kg", text: "Phosphat", einheit: "mmol/kg" },
  { k: "vorgabe_calcium_mmol_kg", text: "Calcium", einheit: "mmol/kg" },
  { k: "vorgabe_magnesium_mmol_kg", text: "Magnesium", einheit: "mmol/kg" },
];

function Einheit({ children, einheit }: { children: ReactNode; einheit: string }) {
  return <span className="relative block">{children}<span className="absolute right-3 top-1/2 -translate-y-1/2 text-[0.8125rem] gedaempft pointer-events-none">{einheit}</span></span>;
}

function GrenzwerteBereich({ speichernRef }: { speichernRef: SpeichernRef }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const daten = useQuery({ queryKey: ["einstellungen"], queryFn: () => api<Einstellungen>("einstellungen/") });
  const [w, setW] = useState<Record<string, string> | null>(null);
  const [pflicht, setPflicht] = useState<string[]>([]);
  // Fristen des Datenschutzes ändert nur, wer auch über Datenschutz-Anfragen entscheidet
  const datenschutz = useAuth().darf("datenschutz_entscheiden");
  useEffect(() => {
    if (daten.data && !w) {
      setW(Object.fromEntries(Object.entries(daten.data).map(([k, v]) => [k, typeof v === "number" ? zahl(v).replace(/\./g, "") : String(v)])));
      setPflicht((daten.data as unknown as { pflicht_erklaerungen?: string[] }).pflicht_erklaerungen ?? []);
    }
  }, [daten.data, w]);
  const speichern = useMutation({
    mutationFn: () => {
      const felder = [...HINWEISE.map((h) => h.k), ...(datenschutz ? DATENSCHUTZ.map((h) => h.k) : []), ...GRENZEN.flatMap((g) => [g.min, g.max]),
        ...SCANS.map((h) => h.k), ...VORGABE_JE_KG.map((v) => v.k), "plan_gewicht_alter_monate"];
      const fehler: Feldfehler = {};
      const body: Record<string, string | string[] | boolean | null> = datenschutz ? { pflicht_erklaerungen: pflicht } : {};
      // F185: nach dem Speichern eines Praxistermins „Terminbestätigung schicken?“ anbieten
      body.terminbestaetigung_anbieten = w!.terminbestaetigung_anbieten !== "false";
      body.ocr_fachwoerter = w!.ocr_fachwoerter ?? "";
      // Infoblatt an die Praxis (F177): Erinnerung auf der Startseite
      body.infoblatt_rhythmus = w!.infoblatt_rhythmus ?? "woche";
      felder.push("infoblatt_vorlauf_tage");
      for (const k of felder) {
        const z = eingabeZahl(w![k] ?? "");
        // Mengen je kg dürfen 0 sein (= nicht vorbelegen)
        if (z === "ungueltig" || (!z && !(k.startsWith("vorgabe_") && (w![k] ?? "").trim() === "0"))) fehler[k] = "Bitte eine Zahl eingeben.";
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
    <div className="stapel grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] gap-5 items-start" data-testid="grenzwerte">
      <div className="stapel flex flex-col gap-5 min-w-0">
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5">
        <h2 className="lbl m-0">Hinweise auf Startseite und in der Liste</h2>
        <div className="grid grid-cols-2 gap-3">
          {HINWEISE.map((h) => (
            <Feld key={h.k} label={h.label} fehler={f[h.k]}>
              {(p) => <Einheit einheit={h.einheit}><Eingabe {...p} className="num pr-20" value={w[h.k] ?? ""} onChange={(e) => setW({ ...w, [h.k]: e.target.value })} /></Einheit>}
            </Feld>
          ))}
        </div>
        <span className="text-[0.8125rem] gedaempft">Beispiel: Warnung, wenn ein Patient mehr als {w.gewicht_warnung_prozent} % in {w.gewicht_warnung_monate} Monaten abnimmt.
          Kontakt: „bald fällig“ nach {w.kontakt_bald_monate}, „überfällig“ nach {w.kontakt_ueberfaellig_monate} Monaten ohne Kontakt
          (Wiedereinbestellung auf der Startseite, Hinweis in der Liste, Kalender). Wiedervorlage beim Erfassen eines Kontakts
          standardmäßig in {w.wiedervorlage_tage} Tagen (im Dialog je Kontakt änderbar).</span>
      </Karte>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5" data-testid="grenzwerte-infoblatt">
        <h2 className="lbl m-0">Infoblatt an die Praxis</h2>
        <div className="grid grid-cols-2 gap-3">
          <Feld label="Erinnerung auf der Startseite" fehler={f.infoblatt_rhythmus}>
            {(p) => (
              <Auswahl {...p} value={w.infoblatt_rhythmus ?? "woche"} onChange={(e) => setW({ ...w, infoblatt_rhythmus: e.target.value })}>
                <option value="woche">wöchentlich (nächste Woche)</option>
                <option value="monat">monatlich (nächster Monat)</option>
                <option value="aus">keine Erinnerung</option>
              </Auswahl>
            )}
          </Feld>
          <Feld label="Erinnern ab" fehler={f.infoblatt_vorlauf_tage}>
            {(p) => <Einheit einheit="Tage vorher"><Eingabe {...p} className="num pr-28" disabled={w.infoblatt_rhythmus === "aus"}
              value={w.infoblatt_vorlauf_tage ?? ""} onChange={(e) => setW({ ...w, infoblatt_vorlauf_tage: e.target.value })} /></Einheit>}
          </Feld>
        </div>
        <span className="text-[0.8125rem] gedaempft">{w.infoblatt_rhythmus === "aus"
          ? "Die Startseite erinnert nicht an das Infoblatt. Es lässt sich jederzeit im Kalender unter „Praxis informieren“ erstellen."
          : `Die Startseite zeigt ${w.infoblatt_vorlauf_tage} Tage vor ${w.infoblatt_rhythmus === "monat" ? "dem nächsten Monat" : "der nächsten Woche (Montag)"}
            den Hinweis „Praxis informieren“ – bis das Infoblatt für diesen Zeitraum erstellt ist.`}</span>
      </Karte>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5" data-testid="grenzwerte-terminbestaetigung">
        <h2 className="lbl m-0">Terminbestätigung</h2>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={w.terminbestaetigung_anbieten !== "false"}
            onChange={(e) => setW({ ...w, terminbestaetigung_anbieten: String(e.target.checked) })} />
          <span>Nach dem Speichern eines neuen oder verschobenen Praxistermins fragen: „Terminbestätigung schicken?“</span>
        </label>
        <span className="text-[0.8125rem] gedaempft">Gilt für Patienten mit Anschrift oder E-Mail-Adresse. Die Tagesliste der Startseite zeigt dann auch
          Praxistermine der nächsten zwei Wochen ohne Bestätigung. Verschickt wird nie von allein.</span>
      </Karte>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5" data-testid="grenzwerte-datenschutz">
        <h2 className="lbl m-0">Datenschutz</h2>
        <div className="grid grid-cols-2 gap-3">
          {DATENSCHUTZ.map((h) => (
            <Feld key={h.k} label={h.label} fehler={f[h.k]} hinweis={h.hinweis}>
              {(p) => <Einheit einheit={h.einheit}><Eingabe {...p} className="num pr-20" disabled={!datenschutz} value={w[h.k] ?? ""} onChange={(e) => setW({ ...w, [h.k]: e.target.value })} /></Einheit>}
            </Feld>
          ))}
        </div>
        {datenschutz ? null : <span className="text-[0.8125rem] gedaempft" data-testid="datenschutz-nur-lesen">Diese Werte ändert, wer über Datenschutz-Anfragen entscheidet (Benutzer › Rechte).</span>}
        <fieldset className="border-0 p-0 m-0 flex flex-col gap-1.5">
          <legend className="text-sm font-medium mb-1.5">Erklärungen, die in jeder Akte vorliegen sollen</legend>
          {/* die Einwilligung zum Austausch zwischen den Firmen braucht nur eine Akte beider Firmen – keine Pflicht für alle */}
          {(Object.keys(ERKLAERUNGEN) as ErklaerungsArt[]).filter((art) => art !== "firmen").map((art) => (
            <label key={art} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={pflicht.includes(art)} disabled={!datenschutz}
                onChange={(e) => setPflicht(e.target.checked ? [...pflicht, art] : pflicht.filter((x) => x !== art))} />
              {ERKLAERUNGEN[art]}
            </label>
          ))}
          {f.pflicht_erklaerungen ? <span className="fehlertext" role="alert">{f.pflicht_erklaerungen}</span> : null}
          <span className="text-[0.8125rem] gedaempft">Fehlt eine davon oder ist sie widerrufen, steht es im Kopf der Akte und auf der Startseite unter „Nach und nach prüfen“.</span>
        </fieldset>
      </Karte>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3.5" data-testid="grenzwerte-scans">
        <h2 className="lbl m-0">Scans und Texterkennung</h2>
        <div className="grid grid-cols-2 gap-3">
          {SCANS.map((h) => (
            <Feld key={h.k} label={h.label} fehler={f[h.k]} hinweis={h.hinweis}>
              {(p) => <Einheit einheit={h.einheit}><Eingabe {...p} className="num pr-20" value={w[h.k] ?? ""} onChange={(e) => setW({ ...w, [h.k]: e.target.value })} /></Einheit>}
            </Feld>
          ))}
        </div>
        <Feld label="Fachwörter für die Texterkennung" fehler={f.ocr_fachwoerter}
          hinweis="Je Zeile ein Wort, z. B. Präparate, Wirkstoffe, Diagnosen. Die Erkennung liest diese Wörter dann zuverlässiger; die Namen des Laborkatalogs kennt sie schon.">
          {(p) => <Textfeld {...p} rows={5} className="font-mono text-[0.8125rem]" value={w.ocr_fachwoerter ?? ""}
            onChange={(e) => setW({ ...w, ocr_fachwoerter: e.target.value })} />}
        </Feld>
        <span className="text-[0.8125rem] gedaempft">Scans werden {w.scans_frist_tage} Tage nach dem Hochladen automatisch gelöscht, wenn sie
          keinem Patienten zugeordnet sind; jede Person mit Zugriff auf „Scans“ kann einen Scan um {w.scans_verlaengerung_tage} Tage verlängern,
          höchstens bis {w.scans_hoechst_tage} Tage nach dem Hochladen.</span>
      </Karte>
      </div>
      <div className="stapel flex flex-col gap-5 min-w-0">
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3">
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
        <span className="text-xs gedaempft">Das Volumen im Mischbeutel wird wie im Altsystem berechnet (Körpergewicht × 35 ml) und gegen diese Grenzen geprüft.</span>
        <div className="text-[0.8125rem] gedaempft">Werte außerhalb werden nicht gespeichert. Im Altsystem standen z. B. 433.564 kcal und 9.999 kg.</div>
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
      </Karte>
      {/* Entscheidung der Praxis 10.10.2026 (F190): die Werte je kg pflegt die Praxis selbst */}
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3" data-testid="grenzwerte-je-kg">
        <h2 className="lbl m-0">Mengen je kg für „Mengen nach Praxisvorgabe“</h2>
        <span className="text-[0.8125rem] gedaempft">Im Plan-Editor setzt „Mengen nach Praxisvorgabe“ (und der erste Plan eines Patienten)
          diese Mengen je kg des letzten Gewichts ein; Präparate und Zusätze bleiben. 0 = nicht vorbelegen. Startwerte wie im Altsystem.</span>
        <div className="grid grid-cols-2 gap-3">
          {VORGABE_JE_KG.map((v) => (
            <Feld key={v.k} label={v.text} fehler={f[v.k]}>
              {(p) => <Einheit einheit={v.einheit}><Eingabe {...p} className="num pr-24" inputMode="decimal" value={w[v.k] ?? ""}
                onChange={(e) => setW({ ...w, [v.k]: e.target.value })} /></Einheit>}
            </Feld>
          ))}
        </div>
        <Feld label="Gewicht für den Plan gilt als alt nach" fehler={f.plan_gewicht_alter_monate}
          hinweis="Ist das letzte Gewicht älter, sagt „Prüfung vor der Freigabe“: bitte prüfen (Mengen je kg und Gesamtvolumen hängen daran).">
          {(p) => <Einheit einheit="Monaten"><Eingabe {...p} className="num pr-24" value={w.plan_gewicht_alter_monate ?? ""}
            onChange={(e) => setW({ ...w, plan_gewicht_alter_monate: e.target.value })} /></Einheit>}
        </Feld>
        <span className="text-xs gedaempft" data-testid="je-kg-stand">{(daten.data as unknown as { vorgabe_geaendert_am?: string | null })?.vorgabe_geaendert_am
          ? `Zuletzt geändert am ${datum((daten.data as unknown as { vorgabe_geaendert_am: string }).vorgabe_geaendert_am)}.`
          : "Noch die Startwerte des Altsystems."} Jede Änderung steht mit Person und Zeitpunkt im Audit-Log.</span>
      </Karte>
      </div>
    </div>
  );
}

const BEREICHE: Bereich[] = ["start", "briefkopf", "listen", "kataloge", "grenzwerte", "anlagen", "ki", "dokumente"];

export function Vorlagen() {
  // Jeder Bereich hat eine Adresse (/admin/vorlagen?bereich=listen&liste=vitamine), damit die Übersicht und die Suche
  // dorthin verlinken und „Zurück“ im Browser funktioniert; Dokumentvorlagen unter /admin/vorlagen/dokumente (F180)
  const ort = useLocation();
  const navigate = useNavigate();
  const [parameter] = useSearchParams();
  const imPfad = ort.pathname.replace(/\/$/, "").endsWith("/vorlagen/dokumente");
  const gewuenscht = parameter.get("bereich") as Bereich | null;
  const bereich: Bereich = imPfad ? "dokumente" : gewuenscht && BEREICHE.includes(gewuenscht) ? gewuenscht : "start";
  const speichern = useRef<(() => void) | null>(null);
  const [aktionen, setAktionen] = useState<HTMLElement | null>(null);
  const dokUngespeichert = useRef(false);
  const t = useT();
  const merkeGeaendert = useCallback((g: boolean) => { dokUngespeichert.current = g; }, []);
  // Warnung beim Verlassen mit ungespeicherten Änderungen an einer Dokumentvorlage: in EPM (andere Seite, anderer
  // Bereich, andere Vorlage, „Zurück“) und beim Schließen oder Neuladen des Browserfensters
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dokUngespeichert.current
    && (currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search));
  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm("Ungespeicherte Änderungen an der Vorlage verwerfen?")) { dokUngespeichert.current = false; blocker.proceed(); }
    else blocker.reset();
  }, [blocker]);
  useEffect(() => {
    const warnen = (e: BeforeUnloadEvent) => { if (dokUngespeichert.current) e.preventDefault(); };
    window.addEventListener("beforeunload", warnen);
    return () => window.removeEventListener("beforeunload", warnen);
  }, []);
  const waehle = (b: Bereich) => {
    if (b === bereich) return;
    navigate(b === "dokumente" ? "/admin/vorlagen/dokumente" : b === "start" ? "/admin/vorlagen" : `/admin/vorlagen?bereich=${b}`);
  };
  return (
    <Seite pfad={[{ text: "Administration" }, { text: "Vorlagen" }]}>
      <Seitenkopf titel={t("Vorlagen")} unter={t("Was in EPM zur Auswahl steht und wie Briefe, E-Mails und PDFs aussehen. Jede Änderung steht im Audit-Log.")}
        rechts={bereich === "dokumente" ? <div ref={setAktionen} className="flex items-center gap-2.5 flex-wrap" />
          : bereich === "briefkopf" || bereich === "grenzwerte" ? <Knopf variante="pri" onClick={() => speichern.current?.()}>{t("Speichern")}</Knopf> : null} />
      <Segmente label={t("Bereich")} wert={bereich} onWahl={waehle} className="self-start"
        werte={([{ wert: "start", text: "Übersicht" }, { wert: "dokumente", text: "Dokumentvorlagen" },
          { wert: "briefkopf", text: "Briefkopf und Logo" }, { wert: "listen", text: "Auswahllisten" },
          { wert: "kataloge", text: "Labor und Diagnosen" }, { wert: "grenzwerte", text: "Grenzwerte" },
          { wert: "anlagen", text: "Anlagen für E-Mails" }, { wert: "ki", text: "KI-Prompts" }] as { wert: Bereich; text: string }[]).map((w) => ({ ...w, text: t(w.text) }))} />
      {bereich === "start" ? <VorlagenStart />
        : bereich === "briefkopf" ? <BriefkopfBereich speichernRef={speichern} />
        : bereich === "listen" ? <ListenBereich liste={parameter.get("liste")}
            onListe={(l) => navigate(`/admin/vorlagen?bereich=listen&liste=${l}`, { replace: true })} />
        : bereich === "kataloge" ? <KatalogeBereich />
        : bereich === "grenzwerte" ? <GrenzwerteBereich speichernRef={speichern} />
        : bereich === "anlagen" ? <AnlagenBereich />
        : bereich === "ki" ? <KiPromptsBereich />
        : <DokumentvorlagenBereich aktionenZiel={aktionen} onGeaendert={merkeGeaendert} />}
    </Seite>
  );
}
