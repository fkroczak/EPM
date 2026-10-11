/** Entwurf 14 · Mein Konto (Varianten 22/23): Darstellung, Profil, Anmeldung und Sicherheit, Sitzungen. */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import { AKTENLEISTE, AKZENTE, HINTERGRUENDE, STANDARD_DARSTELLUNG, aufAkzent, darstellungAnwenden, istHex, luminanz } from "@/lib/darstellung";
import { KOPFSTUFEN } from "./akte/ansicht";
import type { Aktenansicht, Darstellung } from "@/lib/darstellung";
import { datum, zeitpunkt } from "@/lib/format";
import { ROLLEN } from "@/lib/typen";
import type { Ich, Status } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Eingabe, Feld, Karte, Knopf, Laden, Meldung, Seitenkopf, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { useZweiterFaktor } from "@/components/ZweiterFaktor";
import type { PasskeyEintrag } from "@/lib/typen";
import { AuthenticatorEinrichten, NotfallcodesAnzeige, PasskeyEinrichten } from "./Anmeldung";

type Sicherheit = { kennwort_geaendert_am: string | null; authenticator_aktiv: boolean; authenticator_eingerichtet_am: string | null;
  notfallcodes_uebrig: number; notfallcodes_gesamt: number; zweiter_faktor_pflicht?: boolean; passkeys?: PasskeyEintrag[];
  passkey?: { verfuegbar: boolean; rp_id: string; grund: string } };
type Sitzung = { id: number; browser: string; ip: string | null; angemeldet_am: string; zuletzt_am: string; diese: boolean };

const SCHEMATA: { wert: Darstellung["schema"]; titel: string; text: string; farben: [string, string, string] }[] = [
  { wert: "standard", titel: "Standard", text: "Stiftungsfarben, abgestimmt", farben: ["#F3F4F6", "#FFFFFF", "#251F53"] },
  { wert: "individuell", titel: "Individuell", text: "Akzent und Hintergrund selbst wählen", farben: ["#EAF0F2", "#FFFFFF", "#0A6A86"] },
  { wert: "kontrast", titel: "Hoher Kontrast", text: "kräftige Kanten und Schrift", farben: ["#FFFFFF", "#FFFFFF", "#000000"] },
  { wert: "dunkel", titel: "Dunkel", text: "abends, blendet weniger", farben: ["#15131F", "#1F1C2C", "#B9B2F0"] },
];
/** Aufbau der Patientenakte (Wunsch 08.10.2026): drei Ansichten mit kleiner Skizze */
const AKTENANSICHTEN: { wert: Aktenansicht; titel: string; text: string }[] = [
  { wert: "kopfzeile", titel: "Kopfzeile", text: "Angaben in Gruppen oben, Reiter darunter; Höhe ziehbar" },
  { wert: "seitenleiste", titel: "Seitenleiste", text: "Angaben und Knöpfe links, senkrechte Reiter; Breite ziehbar" },
  { wert: "karteikarte", titel: "Karteikarte", text: "wie eine Arztsoftware: alle Einträge chronologisch, Kürzelzeile" },
];

function AktenSkizze({ art }: { art: Aktenansicht }) {
  const balken = (breite: string, stark = false) => (
    <span className="block h-1.5 rounded-sm" style={{ width: breite, background: "var(--akzent)", opacity: stark ? 0.85 : 0.25 }} />
  );
  const flaeche = "bg-flaeche border border-rand rounded-[0.1875rem]";
  return (
    <span aria-hidden="true" className="block h-[4.5rem] rounded-md border border-rand overflow-hidden bg-grund p-1.5">
      {art === "kopfzeile" ? (
        <span className="flex flex-col gap-1 h-full">
          <span className={cx(flaeche, "p-1 grid grid-cols-4 gap-1")}>{[0, 1, 2, 3].map((i) => <span key={i} className="flex flex-col gap-0.5">{balken("80%", i === 0)}{balken("60%")}</span>)}</span>
          <span className="flex gap-1">{balken("18%", true)}{balken("14%")}{balken("14%")}{balken("14%")}</span>
          <span className="grow grid grid-cols-3 gap-1"><span className={flaeche} /><span className={flaeche} /><span className={flaeche} /></span>
        </span>
      ) : art === "seitenleiste" ? (
        <span className="flex gap-1 h-full">
          <span className={cx(flaeche, "w-[28%] p-1 flex flex-col gap-1")}>{balken("90%", true)}{balken("70%")}{balken("80%")}{balken("60%")}</span>
          <span className="w-[16%] flex flex-col gap-1 pt-0.5">{balken("100%", true)}{balken("90%")}{balken("90%")}{balken("90%")}</span>
          <span className="grow grid grid-cols-2 gap-1"><span className={flaeche} /><span className={flaeche} /></span>
        </span>
      ) : (
        <span className="flex flex-col gap-1 h-full">
          <span className={cx(flaeche, "p-1 flex gap-1 items-center")}>{balken("30%", true)}<span className="block h-1.5 w-[12%] rounded-sm bg-fehler opacity-70" /></span>
          <span className="grow flex gap-1">
            <span className={cx(flaeche, "grow p-1 flex flex-col gap-1")}>{balken("90%")}{balken("75%")}{balken("85%")}{balken("60%")}</span>
            <span className={cx(flaeche, "w-[26%]")} />
          </span>
        </span>
      )}
    </span>
  );
}

const ZEILEN: Record<Darstellung["dichte"], string> = { grosszuegig: "ca. 13", normal: "ca. 17", kompakt: "ca. 21", sehrkompakt: "ca. 26" };

function Mini({ farben }: { farben: [string, string, string] }) {
  return (
    <span aria-hidden="true" className="block h-[4rem] rounded-md border border-rand overflow-hidden" style={{ background: farben[0] }}>
      <span className="flex h-full">
        <span className="w-[30%] h-full flex flex-col gap-1 p-1.5" style={{ background: farben[1] }}>
          <span className="h-1.5 rounded-sm" style={{ background: farben[2], opacity: 0.85 }} />
          <span className="h-1.5 rounded-sm opacity-30" style={{ background: farben[2] }} />
          <span className="h-1.5 rounded-sm opacity-30" style={{ background: farben[2] }} />
        </span>
        <span className="grow p-1.5 flex flex-col gap-1">
          <span className="h-3 rounded-sm" style={{ background: farben[1] }} />
          <span className="h-5 w-10 rounded-sm" style={{ background: farben[2] }} />
        </span>
      </span>
    </span>
  );
}

/** Farben je Firma (11.10.2026): „Standard“ sind die Farben der Firma; in der Regeneration Clinic schlägt „Individuell“
 *  zuerst deren Salbeigrün vor */
function firmenStandard(firma: string | undefined): Darstellung {
  return firma === "rg" ? { ...STANDARD_DARSTELLUNG, akzent: "salbei", hintergrund: "salbei" } : STANDARD_DARSTELLUNG;
}

function schemata(firma: string | undefined) {
  return firma === "rg"
    ? SCHEMATA.map((s) => s.wert === "standard" ? { ...s, text: "Farben der Regeneration Clinic", farben: ["#EEF1EF", "#BEC9C3", "#23262B"] as [string, string, string] }
      : s.wert === "individuell" ? { ...s, farben: ["#EEF1EF", "#FFFFFF", "#4E6358"] as [string, string, string] } : s)
    : SCHEMATA;
}

function DarstellungKarten({ zuruecksetzenRef }: { zuruecksetzenRef: { current: (() => void) | null } }) {
  const ich = useIch();
  const basis = firmenStandard(ich.firma);
  const { setIch } = useAuth();
  const melden = useHinweis();
  const [d, setD] = useState<Darstellung>(() => {
    // „form“ (rund/eckig, nur kurz am 08.10.2026) wird beim nächsten Speichern nicht mehr mitgeschickt
    const { form: _form, ...rest } = ich.darstellung as Partial<Darstellung> & { form?: string };
    return { ...basis, ...rest };
  });
  const [fehler, setFehler] = useState("");
  const timer = useRef<number>(0);
  const offen = useRef<Darstellung | null>(null); // Eingabe, deren verzögertes Speichern noch aussteht
  const speichern = useMutation({
    mutationFn: (neu: Darstellung) => api<Ich>("auth/ich/", { method: "PATCH", body: { darstellung: neu } }),
    onSuccess: (neu) => { setIch(neu); setFehler(""); },
    onError: (e) => setFehler(e instanceof ApiFehler ? Object.values(e.felder)[0] ?? e.message : String(e)),
  });
  const akzentFalsch = d.akzent === "eigen" && istHex(d.akzent_eigen) && aufAkzent(d.akzent_eigen) === null;
  const grundFalsch = d.hintergrund === "eigen" && istHex(d.hintergrund_eigen) && luminanz(d.hintergrund_eigen) < 0.6;
  const aendern = (teil: Partial<Darstellung>, sofort = true) => {
    const neu = { ...d, ...teil };
    setD(neu);
    darstellungAnwenden(neu); // Vorschau sofort, gespeichert wird nur Gültiges
    const ungueltig = (neu.akzent === "eigen" && (!istHex(neu.akzent_eigen) || aufAkzent(neu.akzent_eigen) === null))
      || (neu.hintergrund === "eigen" && (!istHex(neu.hintergrund_eigen) || luminanz(neu.hintergrund_eigen) < 0.6));
    window.clearTimeout(timer.current);
    offen.current = null;
    if (ungueltig) return;
    if (sofort) speichern.mutate(neu);
    else {
      offen.current = neu;
      timer.current = window.setTimeout(() => { offen.current = null; speichern.mutate(neu); }, 400);
    }
  };
  // Wer die Seite direkt nach einer Eingabe verlässt, verliert sie nicht: Ausstehendes wird sofort gespeichert
  useEffect(() => () => {
    window.clearTimeout(timer.current);
    if (offen.current) void api("auth/ich/", { method: "PATCH", body: { darstellung: offen.current } }).catch(() => undefined);
  }, []);
  zuruecksetzenRef.current = () => { aendern({ ...basis }); melden("Darstellung zurückgesetzt."); };
  const akzentName = d.akzent === "eigen" ? `Eigene Farbe ${d.akzent_eigen ?? ""}` : AKZENTE[d.akzent]?.[0] ?? "";
  return (
    <>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-4" data-testid="darstellung">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h2 className="lbl m-0">Darstellung{(ich.firmen?.length ?? 0) > 1 ? ` · ${ich.firmen?.find((f) => f.kuerzel === ich.firma)?.name ?? ""}` : ""}</h2>
          <span className="text-[0.8125rem] gedaempft">Warnfarben für Gewicht, Nickelallergie und Fehler bleiben überall gleich.</span>
        </div>
        <div className="grid grid-cols-4 gap-3" role="radiogroup" aria-label="Darstellung">
          {schemata(ich.firma).map((s) => (
            <button key={s.wert} type="button" role="radio" aria-checked={d.schema === s.wert} aria-label={`Darstellung ${s.titel}`}
              className={cx("card p-2.5 flex flex-col gap-2 text-left cursor-pointer border", d.schema === s.wert ? "border-akzent outline-2 outline-akzent" : "hover:bg-fein")}
              onClick={() => aendern({ schema: s.wert })}>
              <Mini farben={s.farben} />
              <span className="text-sm font-medium">{s.titel}</span>
              <span className="text-xs gedaempft">{s.text}</span>
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={d.auto_dunkel} onChange={(e) => aendern({ auto_dunkel: e.target.checked })} />
          Automatisch „Dunkel“, wenn Windows auf dunkel steht
        </label>
        {d.schema === "individuell" ? (
          <div className="flex flex-col gap-3 border-t border-rand pt-3.5">
            <div className="grid grid-cols-[6.875rem_minmax(0,1fr)] items-center gap-3">
              <span className="text-sm font-medium">Akzentfarbe</span>
              <div className="flex items-center gap-2 flex-wrap" role="group" aria-label="Akzentfarbe">
                {Object.entries(AKZENTE).map(([k, [n, hex]]) => (
                  <button key={k} type="button" aria-label={`Akzentfarbe ${n}`} title={n} aria-pressed={d.akzent === k}
                    className={cx("w-8 h-8 rounded-full border-2 cursor-pointer p-0", d.akzent === k ? "border-tinte" : "border-transparent")}
                    style={{ background: hex }} onClick={() => aendern({ akzent: k })} />
                ))}
                <label className="flex items-center gap-1.5 text-[0.8125rem] cursor-pointer" title="Eigene Farbe">
                  <input type="color" aria-label="Eigene Akzentfarbe" value={istHex(d.akzent_eigen) ? d.akzent_eigen : "#0A6A86"}
                    onChange={(e) => aendern({ akzent: "eigen", akzent_eigen: e.target.value.toUpperCase() }, false)} className="w-8 h-8 p-0 border-0 bg-transparent" />
                  Eigene …
                </label>
                <span className="text-[0.8125rem] gedaempft">{akzentName}{akzentFalsch ? " (nicht lesbar)" : ""}</span>
              </div>
              <span className="text-sm font-medium">Hintergrund</span>
              <div className="grid grid-cols-7 gap-2" role="group" aria-label="Hintergrund">
                {Object.entries(HINTERGRUENDE).map(([k, [n, hex]]) => (
                  <button key={k} type="button" aria-label={`Hintergrund ${n}`} aria-pressed={d.hintergrund === k}
                    className={cx("flex flex-col items-center gap-1 bg-transparent border-0 cursor-pointer text-xs p-0")} onClick={() => aendern({ hintergrund: k })}>
                    <span className={cx("w-full h-8 rounded-md border-2", d.hintergrund === k ? "border-tinte" : "border-rand")} style={{ background: hex }} />{n}
                  </button>
                ))}
                <label className="flex flex-col items-center gap-1 text-xs cursor-pointer">
                  <input type="color" aria-label="Eigene Hintergrundfarbe" value={istHex(d.hintergrund_eigen) ? d.hintergrund_eigen : "#F3F1EC"}
                    onChange={(e) => aendern({ hintergrund: "eigen", hintergrund_eigen: e.target.value.toUpperCase() }, false)} className="w-full h-8 p-0 border-0 bg-transparent" />
                  Eigene
                </label>
              </div>
            </div>
            {akzentFalsch ? <Meldung art="warn">Auf dieser Farbe ist weder weiße noch dunkle Schrift gut lesbar. Bitte eine hellere oder dunklere wählen.</Meldung> : null}
            {grundFalsch ? <Meldung art="warn">Diese Farbe ist zu dunkel, Schrift wäre schlecht lesbar. Bitte eine hellere wählen oder „Dunkel“ nehmen.</Meldung> : null}
            <div className="flex items-center gap-3 p-3 rounded-lg bg-grund border border-rand text-sm">
              <span className="gedaempft">Vorschau</span>
              <span className="nav aktiv">Patienten</span>
              <span>Weber, Anna</span>
              <span className="btn pri klein">Kontakt erfassen</span>
            </div>
          </div>
        ) : null}
        {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
      </Karte>
      <Karte className="px-5 py-[1.125rem] grid grid-cols-2 gap-4">
        <div className="col-span-2 flex flex-col gap-2">
          <span className="lbl">Dichte</span>
          <Segmente label="Dichte" wert={d.dichte} onWahl={(w) => aendern({ dichte: w })} className="self-start"
            werte={[{ wert: "grosszuegig", text: "Großzügig" }, { wert: "normal", text: "Normal" }, { wert: "kompakt", text: "Kompakt" }, { wert: "sehrkompakt", text: "Sehr kompakt" }]} />
          <span className="text-[0.8125rem] gedaempft">Zeilen je Bildschirm in der Patientenliste: <span className="num">{ZEILEN[d.dichte]}</span></span>
        </div>
        <div className="col-span-2 flex flex-col gap-2">
          <span className="lbl">Schriftgröße</span>
          <Segmente label="Schriftgröße" wert={d.schriftgroesse} onWahl={(w) => aendern({ schriftgroesse: w })} className="self-start"
            werte={[{ wert: "klein", text: "Klein" }, { wert: "normal", text: "Normal" }, { wert: "gross", text: "Groß" }, { wert: "sehrgross", text: "Sehr groß" }]} />
        </div>
        <div className="flex flex-col gap-2">
          <span className="lbl">Schriftstärke</span>
          <Segmente label="Schriftstärke" wert={d.schriftstaerke} onWahl={(w) => aendern({ schriftstaerke: w })} className="self-start"
            werte={[{ wert: "normal", text: "Normal" }, { wert: "kraeftig", text: "Kräftig" }]} />
          <span className="text-[0.8125rem] gedaempft">Kräftig macht dünne Schrift auf hellen Bildschirmen besser lesbar.</span>
        </div>
        <div className="flex flex-col gap-2 justify-end">
          <span className="text-[0.8125rem] gedaempft">Vorschau</span>
          <span className="card px-3 py-2 text-sm">Weber, Anna · <span className="num">54,6 kg</span> · Nr. <span className="num">0231</span></span>
        </div>
      </Karte>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-4" data-testid="aktenansicht">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h2 className="lbl m-0">Patientenakte</h2>
          <span className="text-[0.8125rem] gedaempft">Aufbau der Akte – gilt für dich an jedem PC; am Telefon immer mit Kopf oben.</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3" role="radiogroup" aria-label="Aufbau der Patientenakte">
          {AKTENANSICHTEN.map((a) => (
            <button key={a.wert} type="button" role="radio" aria-checked={d.aktenansicht === a.wert} aria-label={`Aktenansicht ${a.titel}`}
              className={cx("card p-2.5 flex flex-col gap-2 text-left cursor-pointer border", d.aktenansicht === a.wert ? "border-akzent outline-2 outline-akzent" : "hover:bg-fein")}
              onClick={() => aendern({ aktenansicht: a.wert })}>
              <AktenSkizze art={a.wert} />
              <span className="text-sm font-medium">{a.titel}</span>
              <span className="text-xs gedaempft">{a.text}</span>
            </button>
          ))}
        </div>
        {d.aktenansicht === "kopfzeile" ? (
          <div className="flex flex-col gap-2">
            <span className="lbl">Höhe des Kopfs</span>
            <Segmente label="Höhe des Aktenkopfs" wert={d.aktenkopf} onWahl={(w) => aendern({ aktenkopf: w })} className="self-start"
              werte={KOPFSTUFEN.map((s) => ({ wert: s.wert, text: s.text }))} />
            <span className="text-[0.8125rem] gedaempft">Auch direkt in der Akte: den Griff unter dem Kopf nach oben oder unten ziehen.</span>
          </div>
        ) : null}
        {d.aktenansicht === "seitenleiste" ? (
          <div className="flex flex-col gap-2">
            <span className="lbl">Breite der Seitenleiste</span>
            <Segmente label="Breite der Seitenleiste" wert={String(d.aktenleiste_breite)} onWahl={(w) => aendern({ aktenleiste_breite: Number(w) })}
              className="self-start" werte={AKTENLEISTE.punkte.map((px) => ({ wert: String(px), text: `${px} px` }))} />
            <span className="text-[0.8125rem] gedaempft">Auch direkt in der Akte: den Rand der Seitenleiste ziehen (rastet ein, Doppelklick: {AKTENLEISTE.standard} px). Unter 1280 px Fensterbreite stehen Leiste und Inhalt untereinander.</span>
          </div>
        ) : null}
        {d.aktenansicht === "karteikarte" ? (
          <span className="text-[0.8125rem] gedaempft">Die Akte öffnet mit der Karteikarte. In der Kürzelzeile öffnet <span className="num font-semibold">K Text</span> einen
            neuen Kontakt, <span className="num font-semibold">G 61,2</span> das Gewicht, <span className="num font-semibold">T</span> einen Termin
            und <span className="num font-semibold">P</span> einen neuen Plan – gespeichert wird erst im Formular.</span>
        ) : null}
      </Karte>
    </>
  );
}

function Zeile({ titel, unter, rechts }: { titel: ReactNode; unter?: ReactNode; rechts?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5 border-b border-rand last:border-b-0 flex-wrap">
      <span className="flex flex-col gap-0.5 text-sm min-w-0"><span className="font-medium flex items-center gap-2 flex-wrap">{titel}</span>{unter ? <span className="text-[0.8125rem] gedaempft">{unter}</span> : null}</span>
      {rechts}
    </div>
  );
}

function KennwortDialog({ offen, onOffen }: { offen: boolean; onOffen: (o: boolean) => void }) {
  const [alt, setAlt] = useState("");
  const [neu, setNeu] = useState("");
  const [wdh, setWdh] = useState("");
  const [fehler, setFehler] = useState("");
  const { setStatus } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  useEffect(() => { if (offen) { setAlt(""); setNeu(""); setWdh(""); setFehler(""); } }, [offen]);
  const aendern = useMutation({
    mutationFn: () => {
      if (neu !== wdh) throw new ApiFehler(400, "Die beiden neuen Passwörter stimmen nicht überein.", null, {});
      return api<Status>("auth/kennwort/", { body: { alt, neu } });
    },
    onSuccess: (s) => {
      setStatus(s);
      void qc.invalidateQueries({ queryKey: ["konto"] });
      melden("Passwort geändert. Andere Anmeldungen wurden beendet.");
      onOffen(false);
    },
    onError: (e) => setFehler(e instanceof ApiFehler ? [e.message, e.felder.details].filter(Boolean).join(" ") : String(e)),
  });
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Passwort ändern" breite={480}
      beschreibung="Mindestens 12 Zeichen. Nach dem Ändern werden alle anderen Anmeldungen beendet."
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf><Knopf variante="pri" laedt={aendern.isPending} onClick={() => aendern.mutate()}>Passwort ändern</Knopf></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); aendern.mutate(); }}>
        <Feld label="Bisheriges Passwort">{(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={alt} onChange={(e) => setAlt(e.target.value)} />}</Feld>
        <Feld label="Neues Passwort">{(p) => <Eingabe {...p} type="password" autoComplete="new-password" value={neu} onChange={(e) => setNeu(e.target.value)} />}</Feld>
        <Feld label="Neues Passwort wiederholen">{(p) => <Eingabe {...p} type="password" autoComplete="new-password" value={wdh} onChange={(e) => setWdh(e.target.value)} />}</Feld>
        {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

/** Zwei-Faktor-Anmeldung ausschalten (nur solange sie freiwillig ist): mit Passwort und einem gültigen Code */
function AusschaltenDialog({ offen, onOffen }: { offen: boolean; onOffen: (o: boolean) => void }) {
  const [kennwort, setKennwort] = useState("");
  const zf = useZweiterFaktor();
  const { setIch } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const aus = useMutation({
    mutationFn: () => api<Ich>("auth/2fa/ausschalten/", { body: { kennwort, ...zf.body } }),
    onSuccess: (ich) => {
      setIch(ich);
      void qc.invalidateQueries({ queryKey: ["konto"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden("Zwei-Faktor-Anmeldung ausgeschaltet.");
      onOffen(false);
    },
  });
  useEffect(() => { if (offen) { setKennwort(""); zf.zuruecksetzen(); aus.reset(); } }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const f = aus.error instanceof ApiFehler ? aus.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Zwei-Faktor-Anmeldung ausschalten" breite={520}
      beschreibung="Authenticator, Passkeys und Notfall-Codes werden gelöscht. Zum Anmelden genügen danach Benutzername und Passwort."
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={aus.isPending} disabled={!kennwort || !zf.bereit} onClick={() => aus.mutate()}>Ausschalten</Knopf></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (kennwort && zf.bereit) aus.mutate(); }}>
        <Meldung art="warn">Ohne zweiten Faktor schützt nur noch das Passwort dein Konto – und damit die Patientendaten, die du sehen darfst.</Meldung>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
          <Feld label="Dein Passwort" fehler={f.kennwort}>{(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}</Feld>
          {zf.feld(f.code)}
        </div>
        {aus.error && !Object.keys(f).length ? <Meldung art="fehler">{aus.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

/** Eigenen Passkey entfernen: mit Passwort und zweitem Faktor (Code oder ein Passkey) */
function PasskeyEntfernenDialog({ passkey, onZu }: { passkey: PasskeyEintrag | null; onZu: () => void }) {
  const [kennwort, setKennwort] = useState("");
  const zf = useZweiterFaktor();
  const { setIch } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const weg = useMutation({
    mutationFn: () => api<Ich>(`auth/passkeys/${passkey!.id}/entfernen/`, { body: { kennwort, ...zf.body } }),
    onSuccess: (ich) => {
      setIch(ich);
      void qc.invalidateQueries({ queryKey: ["konto"] });
      melden(`Passkey „${passkey?.name}“ entfernt.`);
      onZu();
    },
  });
  useEffect(() => { if (passkey) { setKennwort(""); zf.zuruecksetzen(); weg.reset(); } }, [passkey]); // eslint-disable-line react-hooks/exhaustive-deps
  const f = weg.error instanceof ApiFehler ? weg.error.felder : {};
  return (
    <Dialog offen={!!passkey} onOffen={(o) => { if (!o) onZu(); }} titel={`Passkey „${passkey?.name ?? ""}“ entfernen`} breite={520}
      beschreibung="Mit diesem Passkey kannst du dich danach nicht mehr anmelden. Der Eintrag im Passwortmanager bzw. auf dem Gerät bleibt; dort kannst du ihn selbst löschen."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={weg.isPending} disabled={!kennwort || !zf.bereit} onClick={() => weg.mutate()}>Entfernen</Knopf></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (kennwort && zf.bereit) weg.mutate(); }}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
          <Feld label="Dein Passwort" fehler={f.kennwort}>{(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}</Feld>
          {zf.feld(f.code)}
        </div>
        {weg.error && !Object.keys(f).length ? <Meldung art="fehler">{weg.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

function PasskeyUmbenennen({ passkey }: { passkey: PasskeyEintrag }) {
  const [offen, setOffen] = useState(false);
  const [name, setName] = useState(passkey.name);
  const qc = useQueryClient();
  const speichern = useMutation({
    mutationFn: () => api(`auth/passkeys/${passkey.id}/`, { method: "PATCH", body: { name: name.trim() } }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["konto"] }); setOffen(false); },
  });
  return <>
    <Knopf klein variante="geist" icon="stift" aria-label={`${passkey.name} umbenennen`} onClick={() => { setName(passkey.name); setOffen(true); }} />
    <Dialog offen={offen} onOffen={setOffen} titel="Passkey umbenennen" breite={440}
      fuss={<><Knopf onClick={() => setOffen(false)}>Abbrechen</Knopf><Knopf variante="pri" laedt={speichern.isPending} disabled={!name.trim()} onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) speichern.mutate(); }}>
        <Feld label="Name">{(p) => <Eingabe {...p} value={name} maxLength={64} onChange={(e) => setName(e.target.value)} autoFocus />}</Feld>
      </form>
    </Dialog>
  </>;
}

function SicherheitKarte() {
  const [dialog, setDialog] = useState<"" | "kennwort" | "geraet" | "codes" | "aus" | "passkey">("");
  const [entfernen, setEntfernen] = useState<PasskeyEintrag | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);
  const { setStatus } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const s = useQuery({ queryKey: ["konto", "sicherheit"], queryFn: () => api<Sicherheit>("auth/sicherheit/") });
  const neueCodes = useMutation({
    mutationFn: () => api<{ notfallcodes: string[] }>("auth/notfallcodes/", { method: "POST" }),
    onSuccess: (r) => {
      setCodes(r.notfallcodes);
      void qc.invalidateQueries({ queryKey: ["konto"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] }); // Hinweis „Nur noch n Notfall-Codes“ (S08) verschwindet
    },
  });
  // „Neue Codes erzeugen“ im Hinweis der Startseite führt hierher
  const location = useLocation();
  useEffect(() => {
    // … ebenso „2FA einrichten“ (Startseite, Administration › System: /konto#zwei-faktor)
    if ((location.state as { sicherheit?: number } | null)?.sicherheit || location.hash === "#zwei-faktor") {
      document.querySelector('[data-testid="sicherheit"]')?.scrollIntoView({ block: "start" });
    }
  }, [location.state, location.hash, s.data]);
  const d = s.data;
  const passkeys = d?.passkeys ?? [];
  const zweiterFaktor = !!d && (d.authenticator_aktiv || passkeys.length > 0);
  return (
    <Karte className="px-5 py-[1.125rem] flex flex-col gap-1" data-testid="sicherheit" id="zwei-faktor">
      <h2 className="lbl m-0 mb-1">Anmeldung und Sicherheit</h2>
      {s.isLoading || !d ? <Laden /> : <>
        <Zeile titel="Passwort" unter={d.kennwort_geaendert_am ? `zuletzt geändert ${datum(d.kennwort_geaendert_am)}` : "noch nie geändert"}
          rechts={<Knopf klein onClick={() => setDialog("kennwort")}>Ändern</Knopf>} />
        <Zeile titel={<>Authenticator-App {d.authenticator_aktiv ? <Chip art="ok"><Icon name="haken" />aktiv</Chip>
            : <Chip art={d.zweiter_faktor_pflicht && !zweiterFaktor ? "warn" : undefined}>nicht eingerichtet</Chip>}</>}
          unter={d.authenticator_aktiv ? (d.authenticator_eingerichtet_am ? `eingerichtet ${datum(d.authenticator_eingerichtet_am)}` : undefined)
            : d.zweiter_faktor_pflicht && !zweiterFaktor ? "zweiter Faktor für dein Konto Pflicht" : "Code vom Telefon als zweiter Faktor"}
          rechts={<span className="flex gap-1.5">
            <Knopf klein variante={d.authenticator_aktiv || passkeys.length ? "sec" : "pri"} onClick={() => setDialog("geraet")}>{d.authenticator_aktiv ? "Neues Gerät" : "Einrichten"}</Knopf>
          </span>} />
        <div className="py-2.5 border-b border-rand flex flex-col gap-2" data-testid="passkeys">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <span className="flex flex-col gap-0.5 text-sm min-w-0">
              <span className="font-medium flex items-center gap-2 flex-wrap">Passkeys {passkeys.length ? <Chip art="ok"><Icon name="haken" />{passkeys.length}</Chip> : <Chip>keiner</Chip>}</span>
              <span className="text-[0.8125rem] gedaempft">Fingerabdruck, Gesicht oder PIN statt Code – am PC und am Telefon</span>
            </span>
            <Knopf klein icon="plus" variante={zweiterFaktor ? "sec" : "pri"} onClick={() => setDialog("passkey")}>Passkey hinzufügen</Knopf>
          </div>
          {passkeys.map((p) => (
            <div key={p.id} className="flex items-center justify-between gap-2 pl-3 border-l-2 border-rand text-sm" data-testid="passkey-eintrag">
              <span className="flex flex-col min-w-0">
                <span className="font-medium truncate">{p.name}{p.synchronisiert ? <span className="gedaempft font-normal"> · synchronisiert</span> : null}</span>
                <span className="text-[0.8125rem] gedaempft">angelegt {datum(p.angelegt_am)}{p.zuletzt_am ? ` · zuletzt ${zeitpunkt(p.zuletzt_am)}` : " · noch nicht verwendet"}</span>
              </span>
              <span className="flex gap-1 shrink-0">
                <PasskeyUmbenennen passkey={p} />
                <Knopf klein variante="geist" icon="x" aria-label={`${p.name} entfernen`} onClick={() => setEntfernen(p)} />
              </span>
            </div>
          ))}
        </div>
        {zweiterFaktor && !d.zweiter_faktor_pflicht ? (
          <Zeile titel="Zwei-Faktor-Anmeldung" unter="freiwillig – ausschalten löscht App, Passkeys und Notfall-Codes"
            rechts={<Knopf klein variante="geist" onClick={() => setDialog("aus")}>Ausschalten</Knopf>} />
        ) : null}
        {zweiterFaktor ? (
          <Zeile titel="Notfall-Codes" unter={`${d.notfallcodes_uebrig} von ${d.notfallcodes_gesamt} übrig, für verlorenes Handy`}
            rechts={<Knopf klein onClick={() => setDialog("codes")}>Neu erzeugen</Knopf>} />
        ) : null}
      </>}
      <AusschaltenDialog offen={dialog === "aus"} onOffen={(o) => setDialog(o ? "aus" : "")} />
      <PasskeyEntfernenDialog passkey={entfernen} onZu={() => setEntfernen(null)} />
      <Dialog offen={dialog === "passkey"} onOffen={(o) => { setDialog(o ? "passkey" : ""); if (!o) setCodes(null); }} titel="Passkey hinzufügen" breite={520}>
        {codes ? (
          <NotfallcodesAnzeige codes={codes} weiterText="Fertig" onWeiter={() => { setCodes(null); setDialog(""); }} />
        ) : dialog === "passkey" ? (
          <PasskeyEinrichten onAbbrechen={() => setDialog("")} onFertig={(st) => {
            const { notfallcodes, ...rest } = st;
            setStatus(rest);
            void qc.invalidateQueries({ queryKey: ["konto"] });
            void qc.invalidateQueries({ queryKey: ["startseite"] });
            melden(`Passkey „${st.passkey_neu?.name ?? ""}“ eingerichtet.`);
            if (notfallcodes?.length) setCodes(notfallcodes); else setDialog("");
          }} />
        ) : null}
      </Dialog>
      <KennwortDialog offen={dialog === "kennwort"} onOffen={(o) => setDialog(o ? "kennwort" : "")} />
      <Dialog offen={dialog === "geraet"} onOffen={(o) => { setDialog(o ? "geraet" : ""); if (!o) setCodes(null); }} titel={d?.authenticator_aktiv || codes ? "Neues Gerät einrichten" : "Zwei-Faktor-Anmeldung einrichten"} breite={560}
        beschreibung={d?.authenticator_aktiv ? "Das bisherige Gerät gilt nicht mehr, sobald das neue bestätigt ist. Danach gibt es neue Notfall-Codes."
          : "Ab dann fragt EPM beim Anmelden zusätzlich nach dem Code aus der Authenticator-App. Danach gibt es Notfall-Codes für ein verlorenes Telefon."}>
        {codes ? (
          <NotfallcodesAnzeige codes={codes} weiterText="Fertig" onWeiter={() => { setCodes(null); setDialog(""); }} />
        ) : dialog === "geraet" ? (
          <AuthenticatorEinrichten onAbbrechen={() => setDialog("")} onFertig={(st) => {
            setCodes(st.notfallcodes ?? []);
            const { notfallcodes: _n, ...rest } = st;
            setStatus(rest);
            void qc.invalidateQueries({ queryKey: ["konto"] });
            void qc.invalidateQueries({ queryKey: ["startseite"] });
            melden(d?.authenticator_aktiv ? "Neues Gerät eingerichtet." : "Zwei-Faktor-Anmeldung eingerichtet.");
          }} />
        ) : null}
      </Dialog>
      <Dialog offen={dialog === "codes"} onOffen={(o) => { setDialog(o ? "codes" : ""); if (!o) setCodes(null); }} titel="Notfall-Codes neu erzeugen" breite={520}
        beschreibung="Die bisherigen Codes werden dabei ungültig."
        fuss={codes ? undefined : <><Knopf onClick={() => setDialog("")}>Abbrechen</Knopf><Knopf variante="pri" laedt={neueCodes.isPending} onClick={() => neueCodes.mutate()}>Neu erzeugen</Knopf></>}>
        {codes ? <NotfallcodesAnzeige codes={codes} weiterText="Fertig" onWeiter={() => { setCodes(null); setDialog(""); }} /> : null}
      </Dialog>
    </Karte>
  );
}

function SitzungenKarte() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const sitzungen = useQuery({ queryKey: ["konto", "sitzungen"], queryFn: () => api<Sitzung[]>("sitzungen/") });
  const beenden = useMutation({
    mutationFn: (id: number) => api(`sitzungen/${id}/`, { method: "DELETE" }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["konto", "sitzungen"] }); melden("Anmeldung beendet."); },
  });
  return (
    <Karte className="px-5 py-[1.125rem] flex flex-col gap-1" data-testid="sitzungen">
      <h2 className="lbl m-0 mb-1">Angemeldet</h2>
      {sitzungen.isLoading ? <Laden /> : (sitzungen.data ?? []).map((s) => (
        <Zeile key={s.id} titel={<>{s.diese ? "Dieser PC" : "Anderes Gerät"} · {s.browser || "Browser"}</>}
          unter={s.diese ? `angemeldet ${zeitpunkt(s.angemeldet_am)}${s.ip ? ` · ${s.ip}` : ""}` : `zuletzt ${zeitpunkt(s.zuletzt_am)}${s.ip ? ` · ${s.ip}` : ""}`}
          rechts={s.diese ? <Chip art="akzent">jetzt</Chip> : <Knopf klein laedt={beenden.isPending && beenden.variables === s.id} onClick={() => beenden.mutate(s.id)}>Abmelden</Knopf>} />
      ))}
    </Karte>
  );
}

/**
 * Mein Konto (seit 09.10.2026 ohne Darstellung, Wunsch: „Design und Mein Konto voneinander trennen und als separate
 * Menüpunkte anbieten“): Profil, Anmeldung und Sicherheit, angemeldete Geräte.
 */
export function Konto() {
  const ich = useIch();
  return (
    <Seite pfad={[{ text: "Mein Konto" }]}>
      <Seitenkopf titel="Mein Konto" />
      <div className="stapel grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
        <div className="stapel flex flex-col gap-5 min-w-0">
          <Karte className="px-5 py-[1.125rem] flex flex-col gap-3" data-testid="profil">
            <h2 className="lbl m-0">Profil</h2>
            <div className="grid grid-cols-[6.875rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
              <span className="gedaempft">Name</span><span>{[ich.titel, ich.vorname, ich.nachname].filter(Boolean).join(" ")}</span>
              <span className="gedaempft">Funktion</span><span>{ich.funktion || "—"}</span>
              <span className="gedaempft">Kürzel</span><span className="num">{ich.kuerzel || "—"}</span>
              <span className="gedaempft">Benutzer</span><span className="num">{ich.benutzername}</span>
              <span className="gedaempft">Rolle</span><span><Chip art={ich.rolle === "keine" ? undefined : "akzent"}>{ROLLEN[ich.rolle]}</Chip>{ich.ist_test ? <Chip art="warn" className="ml-2">Testzugang</Chip> : null}</span>
            </div>
            <span className="text-[0.8125rem] gedaempft">Name, Titel, Kürzel und Rolle ändert die Administration unter „Benutzer“.</span>
          </Karte>
          <SitzungenKarte />
        </div>
        <div className="stapel flex flex-col gap-5 min-w-0">
          <SicherheitKarte />
        </div>
      </div>
    </Seite>
  );
}

/**
 * Design (eigener Menüpunkt seit 09.10.2026): Farben, Dichte, Schrift, Aufbau der Patientenakte – gespeichert je
 * Person, an jedem PC gleich; dazu „Startseite anpassen“.
 */
export function Design() {
  const ich = useIch();
  const zuruecksetzen = useRef<(() => void) | null>(null);
  return (
    <Seite pfad={[{ text: "Design" }]}>
      <Seitenkopf titel="Design"
        rechts={<Knopf onClick={() => zuruecksetzen.current?.()}>Auf Standard zurücksetzen</Knopf>} />
      <div className="stapel flex flex-col gap-5 min-w-0 max-w-[68.75rem]" data-testid="design">
        {/* je Firma eigene Farben: beim Umschalten die Einstellungen der anderen Firma laden */}
        <DarstellungKarten key={ich.firma ?? ""} zuruecksetzenRef={zuruecksetzen} />
        <Link to="/" state={{ anpassen: Date.now() }} className="card px-5 py-4 flex items-center justify-between no-underline text-tinte hover:bg-fein">
          <span className="font-medium">Startseite anpassen</span><span aria-hidden="true">→</span>
        </Link>
      </div>
    </Seite>
  );
}
