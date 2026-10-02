/** Entwurf 14 · Mein Konto (Varianten 22/23): Darstellung, Profil, Anmeldung und Sicherheit, Sitzungen. */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import { AKZENTE, HINTERGRUENDE, STANDARD_DARSTELLUNG, aufAkzent, darstellungAnwenden, istHex, luminanz } from "@/lib/darstellung";
import type { Darstellung } from "@/lib/darstellung";
import { datum, zeitpunkt } from "@/lib/format";
import { ROLLEN } from "@/lib/typen";
import type { Ich, Status } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Eingabe, Feld, Karte, Knopf, Laden, Meldung, Seitenkopf, Segmente, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { AuthenticatorEinrichten, NotfallcodesAnzeige } from "./Anmeldung";

type Sicherheit = { kennwort_geaendert_am: string | null; authenticator_aktiv: boolean; authenticator_eingerichtet_am: string | null;
  notfallcodes_uebrig: number; notfallcodes_gesamt: number; zweiter_faktor_pflicht?: boolean };
type Sitzung = { id: number; browser: string; ip: string | null; angemeldet_am: string; zuletzt_am: string; diese: boolean };

const SCHEMATA: { wert: Darstellung["schema"]; titel: string; text: string; farben: [string, string, string] }[] = [
  { wert: "standard", titel: "Standard", text: "Stiftungsfarben, abgestimmt", farben: ["#F3F4F6", "#FFFFFF", "#251F53"] },
  { wert: "individuell", titel: "Individuell", text: "Akzent und Hintergrund selbst wählen", farben: ["#EAF0F2", "#FFFFFF", "#0A6A86"] },
  { wert: "kontrast", titel: "Hoher Kontrast", text: "kräftige Kanten und Schrift", farben: ["#FFFFFF", "#FFFFFF", "#000000"] },
  { wert: "dunkel", titel: "Dunkel", text: "abends, blendet weniger", farben: ["#15131F", "#1F1C2C", "#B9B2F0"] },
];
const ZEILEN: Record<Darstellung["dichte"], string> = { grosszuegig: "ca. 11", normal: "ca. 14", kompakt: "ca. 19", sehrkompakt: "ca. 25" };

function Mini({ farben }: { farben: [string, string, string] }) {
  return (
    <span aria-hidden="true" className="block h-[64px] rounded-md border border-rand overflow-hidden" style={{ background: farben[0] }}>
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

function DarstellungKarten({ zuruecksetzenRef }: { zuruecksetzenRef: { current: (() => void) | null } }) {
  const ich = useIch();
  const { setIch } = useAuth();
  const melden = useHinweis();
  const [d, setD] = useState<Darstellung>({ ...STANDARD_DARSTELLUNG, ...ich.darstellung });
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
  zuruecksetzenRef.current = () => { aendern({ ...STANDARD_DARSTELLUNG }); melden("Darstellung zurückgesetzt."); };
  const akzentName = d.akzent === "eigen" ? `Eigene Farbe ${d.akzent_eigen ?? ""}` : AKZENTE[d.akzent]?.[0] ?? "";
  return (
    <>
      <Karte className="px-5 py-[18px] flex flex-col gap-4" data-testid="darstellung">
        <div className="flex items-baseline justify-between gap-3 flex-wrap">
          <h2 className="lbl m-0">Darstellung</h2>
          <span className="text-[0.8125rem] gedaempft">Warnfarben für Gewicht, Nickelallergie und Fehler bleiben überall gleich.</span>
        </div>
        <div className="grid grid-cols-4 gap-3" role="radiogroup" aria-label="Darstellung">
          {SCHEMATA.map((s) => (
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
            <div className="grid grid-cols-[110px_minmax(0,1fr)] items-center gap-3">
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
      <Karte className="px-5 py-[18px] grid grid-cols-2 gap-4">
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
    </>
  );
}

function Zeile({ titel, unter, rechts }: { titel: ReactNode; unter?: ReactNode; rechts?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5 border-b border-rand last:border-b-0">
      <span className="flex flex-col gap-0.5 text-sm"><span className="font-medium flex items-center gap-2">{titel}</span>{unter ? <span className="text-[0.8125rem] gedaempft">{unter}</span> : null}</span>
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
  const [code, setCode] = useState("");
  const { setIch } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const aus = useMutation({
    mutationFn: () => api<Ich>("auth/2fa/ausschalten/", { body: { kennwort, code } }),
    onSuccess: (ich) => {
      setIch(ich);
      void qc.invalidateQueries({ queryKey: ["konto"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden("Zwei-Faktor-Anmeldung ausgeschaltet.");
      onOffen(false);
    },
  });
  useEffect(() => { if (offen) { setKennwort(""); setCode(""); aus.reset(); } }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const f = aus.error instanceof ApiFehler ? aus.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Zwei-Faktor-Anmeldung ausschalten" breite={520}
      beschreibung="Authenticator und Notfall-Codes werden gelöscht. Zum Anmelden genügen danach Benutzername und Passwort."
      fuss={<><Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={aus.isPending} disabled={!kennwort || !code} onClick={() => aus.mutate()}>Ausschalten</Knopf></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (kennwort && code) aus.mutate(); }}>
        <Meldung art="warn">Ohne zweiten Faktor schützt nur noch das Passwort dein Konto – und damit die Patientendaten, die du sehen darfst.</Meldung>
        <div className="grid grid-cols-2 gap-3">
          <Feld label="Dein Passwort" fehler={f.kennwort}>{(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}</Feld>
          <Feld label="Code aus der Authenticator-App" hinweis="oder ein Notfall-Code" fehler={f.code}>
            {(p) => <Eingabe {...p} inputMode="text" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}</Feld>
        </div>
        {aus.error && !Object.keys(f).length ? <Meldung art="fehler">{aus.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

function SicherheitKarte() {
  const [dialog, setDialog] = useState<"" | "kennwort" | "geraet" | "codes" | "aus">("");
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
  return (
    <Karte className="px-5 py-[18px] flex flex-col gap-1" data-testid="sicherheit" id="zwei-faktor">
      <h2 className="lbl m-0 mb-1">Anmeldung und Sicherheit</h2>
      {s.isLoading || !d ? <Laden /> : <>
        <Zeile titel="Passwort" unter={d.kennwort_geaendert_am ? `zuletzt geändert ${datum(d.kennwort_geaendert_am)}` : "noch nie geändert"}
          rechts={<Knopf klein onClick={() => setDialog("kennwort")}>Ändern</Knopf>} />
        <Zeile titel={<>Zwei-Faktor-Anmeldung (Authenticator-App) {d.authenticator_aktiv ? <Chip art="ok"><Icon name="haken" />aktiv</Chip>
            : <Chip art={d.zweiter_faktor_pflicht ? "warn" : undefined}>nicht eingerichtet</Chip>}</>}
          unter={d.authenticator_aktiv ? (d.authenticator_eingerichtet_am ? `eingerichtet ${datum(d.authenticator_eingerichtet_am)}` : undefined)
            : d.zweiter_faktor_pflicht ? "für dein Konto Pflicht" : "freiwillig – schützt dein Konto zusätzlich mit einem Code vom Telefon"}
          rechts={<span className="flex gap-1.5">
            {d.authenticator_aktiv && !d.zweiter_faktor_pflicht ? <Knopf klein variante="geist" onClick={() => setDialog("aus")}>Ausschalten</Knopf> : null}
            <Knopf klein variante={d.authenticator_aktiv ? "sec" : "pri"} onClick={() => setDialog("geraet")}>{d.authenticator_aktiv ? "Neues Gerät" : "Einrichten"}</Knopf>
          </span>} />
        {d.authenticator_aktiv ? (
          <Zeile titel="Notfall-Codes" unter={`${d.notfallcodes_uebrig} von ${d.notfallcodes_gesamt} übrig, für verlorenes Handy`}
            rechts={<Knopf klein onClick={() => setDialog("codes")}>Neu erzeugen</Knopf>} />
        ) : null}
      </>}
      <AusschaltenDialog offen={dialog === "aus"} onOffen={(o) => setDialog(o ? "aus" : "")} />
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
    <Karte className="px-5 py-[18px] flex flex-col gap-1" data-testid="sitzungen">
      <h2 className="lbl m-0 mb-1">Angemeldet</h2>
      {sitzungen.isLoading ? <Laden /> : (sitzungen.data ?? []).map((s) => (
        <Zeile key={s.id} titel={<>{s.diese ? "Dieser PC" : "Anderes Gerät"} · {s.browser || "Browser"}</>}
          unter={s.diese ? `angemeldet ${zeitpunkt(s.angemeldet_am)}${s.ip ? ` · ${s.ip}` : ""}` : `zuletzt ${zeitpunkt(s.zuletzt_am)}${s.ip ? ` · ${s.ip}` : ""}`}
          rechts={s.diese ? <Chip art="akzent">jetzt</Chip> : <Knopf klein laedt={beenden.isPending && beenden.variables === s.id} onClick={() => beenden.mutate(s.id)}>Abmelden</Knopf>} />
      ))}
    </Karte>
  );
}

export function Konto() {
  const ich = useIch();
  const zuruecksetzen = useRef<(() => void) | null>(null);
  return (
    <Seite pfad={[{ text: "Mein Konto" }]}>
      <Seitenkopf titel="Mein Konto"
        unter={<span className="max-w-[80ch] inline-block leading-normal">Deine Einstellungen werden für dich gespeichert und gelten an jedem PC, an dem du dich anmeldest. Rolle und Rechte vergibt die Administration.</span>}
        rechts={<Knopf onClick={() => zuruecksetzen.current?.()}>Auf Standard zurücksetzen</Knopf>} />
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-5 items-start">
        <div className="flex flex-col gap-5 min-w-0"><DarstellungKarten zuruecksetzenRef={zuruecksetzen} /></div>
        <div className="flex flex-col gap-5 min-w-0">
          <Karte className="px-5 py-[18px] flex flex-col gap-3" data-testid="profil">
            <h2 className="lbl m-0">Profil</h2>
            <div className="grid grid-cols-[110px_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
              <span className="gedaempft">Name</span><span>{[ich.titel, ich.vorname, ich.nachname].filter(Boolean).join(" ")}</span>
              <span className="gedaempft">Funktion</span><span>{ich.funktion || "—"}</span>
              <span className="gedaempft">Kürzel</span><span className="num">{ich.kuerzel || "—"}</span>
              <span className="gedaempft">Benutzer</span><span className="num">{ich.benutzername}</span>
              <span className="gedaempft">Rolle</span><span><Chip art={ich.rolle === "keine" ? undefined : "akzent"}>{ROLLEN[ich.rolle]}</Chip>{ich.ist_test ? <Chip art="warn" className="ml-2">Testzugang</Chip> : null}</span>
            </div>
            <span className="text-[0.8125rem] gedaempft">Name, Titel, Kürzel und Rolle ändert die Administration unter „Benutzer“.</span>
          </Karte>
          <SicherheitKarte />
          <SitzungenKarte />
          <Link to="/" state={{ anpassen: Date.now() }} className="card px-5 py-4 flex items-center justify-between no-underline text-tinte hover:bg-fein">
            <span className="font-medium">Startseite anpassen</span><span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>
    </Seite>
  );
}
