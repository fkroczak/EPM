/**
 * Entwurf 1 · Anmeldung mit 2FA. Dazu die Schritte der ersten Anmeldung:
 * eigenes Passwort festlegen → Authenticator einrichten → Notfall-Codes notieren.
 */
import { useEffect, useRef, useState } from "react";
import type { CSSProperties, FormEvent, ReactNode } from "react";
import { ApiFehler, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PasskeyVorrat, geraetename, passkeyBenutzen, passkeyErstellen, passkeyHindernis } from "@/lib/passkey";
import type { Status } from "@/lib/typen";
import { Eingabe, Feld, Knopf, Meldung, Segmente } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { EpmMarke, EpmSymbol } from "@/components/layout/EpmMarke";
import { Stammzertifikat } from "@/components/Stammzertifikat";

/** Neutrale Anmeldeseite (Wunsch 11.10.2026): EPM wird von DSKM und Regeneration Clinic genutzt – vor der Anmeldung
 *  steht deshalb keine Firma im Vordergrund, sondern das System. Ruhige Fläche in Schiefer-Petrol, Pulslinie, Leitsatz;
 *  unten die Einrichtungen, die EPM gemeinsam nutzen. Logo und Farben der Firma erscheinen nach der Anmeldung. */
function Rahmen({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const firmen = status?.organisation?.firmen ?? [];
  return (
    // neutraler Akzent (Schiefer-Petrol) statt der Farben einer Firma
    <div className="min-h-screen flex bg-flaeche" style={{ "--akzent": "#24353D", "--akzent-hover": "#1B262D",
      "--akzent-text": "#2A4F57", "--akzent-weich": "#E3ECEB", "--ladebalken": "#5E9C93" } as CSSProperties}>
      <div aria-hidden="true" className="relative grow overflow-hidden hidden md:flex"
        style={{ background: "linear-gradient(160deg, #1B262D 0%, #22333B 55%, #2A3F47 100%)" }}>
        <svg viewBox="0 0 880 960" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 h-full w-full">
          <defs>
            <pattern id="punkte" width="28" height="28" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1.2" fill="#9CC9C1" fillOpacity=".10" />
            </pattern>
            <linearGradient id="puls" x1="0" x2="1">
              <stop offset="0" stopColor="#9CC9C1" stopOpacity="0" />
              <stop offset=".35" stopColor="#9CC9C1" stopOpacity=".55" />
              <stop offset="1" stopColor="#9CC9C1" stopOpacity=".15" />
            </linearGradient>
          </defs>
          <rect width="880" height="960" fill="url(#punkte)" />
          <circle cx="740" cy="160" r="260" fill="#9CC9C1" fillOpacity=".04" />
          <circle cx="740" cy="160" r="170" fill="none" stroke="#9CC9C1" strokeOpacity=".12" strokeWidth="1.5" />
        </svg>
        {/* Pulslinie im unteren Drittel, unabhängig vom Seitenverhältnis unter dem Leitsatz */}
        <svg viewBox="0 0 880 200" preserveAspectRatio="none" className="absolute inset-x-0 bottom-[16%] h-[9rem] w-full">
          <path d="M0 110 H300 l22 -40 l30 110 l34 -150 l28 104 l16 -24 H880" fill="none" stroke="url(#puls)"
            strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="relative flex flex-col justify-between px-[4.5rem] py-16 w-full">
          <div className="flex items-center gap-3">
            <EpmSymbol groesse={36} hell />
            <span className="font-mono text-xs font-medium uppercase tracking-[.14em]" style={{ color: "#9CC9C1" }}>
              EPM · Elektronisches Patientenmanagement
            </span>
          </div>
          <div className="flex flex-col gap-[1.125rem] max-w-[35rem]">
            <span className="font-serif italic text-[3.25rem] leading-[1.1] tracking-[-.01em]" style={{ color: "#F1F5F4" }}>
              Salus aegroti<br />suprema lex
            </span>
            <span className="w-14 h-[0.1875rem] rounded-sm" style={{ background: "#9CC9C1" }} />
            <span className="text-lg leading-normal" style={{ color: "#C9D6D3" }}>Das Wohl des Kranken ist oberstes Gesetz.</span>
          </div>
          {firmen.length ? (
            <div className="flex flex-col gap-2 text-[0.8125rem] leading-normal" style={{ color: "#A9BCB8" }}>
              <span className="font-mono text-[0.6875rem] uppercase tracking-[.12em]" style={{ color: "#7F9894" }}>Gemeinsam genutzt von</span>
              <span>{firmen.map((f) => f.name).join(" · ")}</span>
            </div>
          ) : <span />}
        </div>
      </div>
      <main className="w-full md:w-[33.75rem] shrink-0 px-4 sm:px-6 md:px-[4.5rem] py-8 sm:py-16 flex flex-col justify-center gap-6 sm:gap-8 bg-flaeche">
        <EpmMarke />
        {children}
        <div className="flex items-start gap-2 text-[0.8125rem] leading-normal gedaempft">
          <Icon name="schloss" groesse={14} className="mt-[0.1875rem] shrink-0" />
          <span>Nur im VPN erreichbar. Nach 30 Minuten ohne Aktivität wirst du abgemeldet.</span>
        </div>
        {/* Stammzertifikat schon vor der Anmeldung (Gerät einrichten, 11.10.2026); ohne eigene CA leer */}
        <details className="text-[0.8125rem] gedaempft [&:not(:has([data-testid=stammzertifikat]))]:hidden" data-testid="anmeldung-zertifikat">
          <summary className="cursor-pointer">Dieses Gerät einrichten (Stammzertifikat)</summary>
          <Stammzertifikat kompakt className="mt-2" />
        </details>
        {firmen.length ? <span className="md:hidden text-xs gedaempft">Gemeinsam genutzt von {firmen.map((f) => f.kurzname).join(" · ")}</span> : null}
      </main>
    </div>
  );
}

function fehlertext(e: unknown) {
  if (e instanceof ApiFehler) {
    const details = (e.daten as { details?: string[] } | null)?.details;
    return details?.length ? `${e.message} ${details.join(" ")}` : e.message;
  }
  return "Keine Verbindung zum Server. Bitte später erneut versuchen.";
}

/** Lösungsweg zur Fehlermeldung (Bedienung für Pflegekräfte, 10.10.2026): was als Nächstes zu tun ist */
const WEITER_ANMELDEN = "Bitte Schreibweise prüfen – Groß- und Kleinschreibung zählt (Feststelltaste?). Nach fünf "
  + "Fehlversuchen wird das Konto gesperrt; entsperren kann die Administration.";
const WEITER_CODE = "Der Code wechselt alle 30 Sekunden – bitte den gerade angezeigten eingeben. Ohne Telefon geht ein Notfall-Code.";

function Formular({ titel, text, onSubmit, children }: { titel: string; text?: ReactNode;
  onSubmit: (e: FormEvent) => void; children: ReactNode }) {
  return (
    <form className="flex flex-col gap-4" onSubmit={onSubmit} noValidate>
      <h1 className="m-0 text-[1.375rem] font-semibold">{titel}</h1>
      {text ? <p className="m-0 text-sm leading-normal text-text2">{text}</p> : null}
      {children}
    </form>
  );
}

function SchrittAnmelden() {
  const { setStatus } = useAuth();
  const [name, setName] = useState("");
  const [kennwort, setKennwort] = useState("");
  const [fehler, setFehler] = useState("");
  const [laedt, setLaedt] = useState(false);
  const [gross, setGross] = useState(false);
  const absenden = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !kennwort) {
      setFehler("Bitte Benutzername und Passwort eingeben.");
      return;
    }
    setLaedt(true);
    setFehler("");
    try {
      setStatus(await api<Status>("auth/anmelden/", { body: { benutzername: name.trim(), kennwort }, ohneAbmeldeSignal: true }));
    } catch (err) {
      setFehler(err instanceof ApiFehler && err.status === 401 ? `${fehlertext(err)} ${WEITER_ANMELDEN}` : fehlertext(err));
      setKennwort("");
    } finally {
      setLaedt(false);
    }
  };
  return (
    <Formular titel="Anmelden" onSubmit={absenden}>
      <Feld label="Benutzername">
        {(p) => <Eingabe {...p} autoComplete="username" value={name} onChange={(e) => setName(e.target.value)} autoFocus />}
      </Feld>
      <Feld label="Passwort">
        {(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort}
          onChange={(e) => setKennwort(e.target.value)}
          onKeyUp={(e) => setGross(e.getModifierState?.("CapsLock") ?? false)}
          onBlur={() => setGross(false)} />}
      </Feld>
      {gross ? <span className="text-[0.8125rem] text-warn flex items-center gap-1.5 -mt-2" role="status" data-testid="feststelltaste">
        <Icon name="warnung" groesse={14} />Die Feststelltaste ist an – das Passwort wird in Großbuchstaben getippt.</span> : null}
      {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
      <Knopf type="submit" variante="pri" className="w-full" laedt={laedt}>Weiter</Knopf>
    </Formular>
  );
}

/** Zweiter Schritt der Anmeldung: Passkey (Festlegung 08.10.2026) oder Code aus der App bzw. Notfall-Code. */
function SchrittCode() {
  const { status, setStatus, abmelden } = useAuth();
  const faktoren = status?.faktoren ?? { authenticator: true, passkey: false };
  const hindernis = passkeyHindernis(status?.passkey);
  const passkeyGeht = faktoren.passkey && !hindernis;
  const [art, setArt] = useState<"passkey" | "code">(passkeyGeht ? "passkey" : "code");
  const [code, setCode] = useState("");
  const [fehler, setFehler] = useState("");
  const [laedt, setLaedt] = useState(false);
  const vorrat = useRef(new PasskeyVorrat("anmelden"));
  useEffect(() => { if (art === "passkey") vorrat.current.vorbereiten(); }, [art]);
  const beiFehler = async (err: unknown) => {
    const text = err instanceof ApiFehler || !(err instanceof Error) ? fehlertext(err) : err.message;
    setFehler(err instanceof ApiFehler && err.status === 401 && art === "code" && text.startsWith("Code") ? `${text} ${WEITER_CODE}` : text);
    if (err instanceof ApiFehler && err.status === 403) await abmelden();
  };
  const absenden = async (e: FormEvent) => {
    e.preventDefault();
    if (art === "passkey") return void mitPasskey();
    setLaedt(true);
    setFehler("");
    try {
      setStatus(await api<Status>("auth/2fa/", { body: { code }, ohneAbmeldeSignal: true }));
    } catch (err) {
      setCode("");
      await beiFehler(err);
    } finally {
      setLaedt(false);
    }
  };
  const mitPasskey = async () => {
    setLaedt(true);
    setFehler("");
    try {
      const antwort = await passkeyBenutzen(await vorrat.current.holen());
      setStatus(await api<Status>("auth/passkey/", { body: { antwort }, ohneAbmeldeSignal: true }));
    } catch (err) {
      vorrat.current.vorbereiten();
      await beiFehler(err);
    } finally {
      setLaedt(false);
    }
  };
  const codeText = faktoren.authenticator
    ? "Gib den 6-stelligen Code aus deiner Authenticator-App ein. Ohne Handy: einen deiner Notfall-Codes."
    : "Gib einen deiner Notfall-Codes ein.";
  return (
    <Formular titel={art === "passkey" ? "Mit Passkey anmelden" : "Bestätigungscode"}
      text={art === "passkey" ? "Bestätige die Anmeldung mit Fingerabdruck, Gesicht oder PIN deines Geräts." : codeText}
      onSubmit={absenden}>
      {passkeyGeht ? (
        <Segmente label="Zweiter Faktor" wert={art} onWahl={(a) => { setArt(a); setFehler(""); }}
          werte={[{ wert: "passkey", text: "Passkey" }, { wert: "code", text: faktoren.authenticator ? "Code" : "Notfall-Code" }]} />
      ) : null}
      {art === "passkey" ? (
        <Knopf type="submit" variante="pri" icon="passkey" className="w-full h-[3.25rem]" laedt={laedt} autoFocus
          data-testid="passkey-anmelden">Mit Passkey anmelden</Knopf>
      ) : <>
        <Feld label="Code">
          {(p) => <Eingabe {...p} className="num text-[1.375rem] tracking-[.3em] h-[3.25rem] text-center" inputMode="text"
            autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} autoFocus />}
        </Feld>
      </>}
      {faktoren.passkey && hindernis ? <Meldung art="info">{hindernis}</Meldung> : null}
      {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
      {art === "code" ? <Knopf type="submit" variante="pri" className="w-full" laedt={laedt} disabled={!code.trim()}>Anmelden</Knopf> : null}
      <Knopf variante="sec" className="w-full" onClick={() => void abmelden()}>Zurück</Knopf>
    </Formular>
  );
}

function SchrittKennwort() {
  const { setStatus, abmelden } = useAuth();
  const [neu, setNeu] = useState("");
  const [wdh, setWdh] = useState("");
  const [fehler, setFehler] = useState("");
  const [laedt, setLaedt] = useState(false);
  const absenden = async (e: FormEvent) => {
    e.preventDefault();
    if (neu.length < 12) return setFehler("Das Passwort braucht mindestens 12 Zeichen.");
    if (neu !== wdh) return setFehler("Die beiden Eingaben stimmen nicht überein.");
    setLaedt(true);
    setFehler("");
    try {
      setStatus(await api<Status>("auth/kennwort/", { body: { neu }, ohneAbmeldeSignal: true }));
    } catch (err) {
      setFehler(fehlertext(err));
    } finally {
      setLaedt(false);
    }
  };
  return (
    <Formular titel="Eigenes Passwort festlegen"
      text="Das Einmal-Passwort gilt nur für die erste Anmeldung. Wähle jetzt ein eigenes Passwort mit mindestens 12 Zeichen."
      onSubmit={absenden}>
      <Feld label="Neues Passwort" hinweis="Mindestens 12 Zeichen, nicht nur Ziffern, nicht ähnlich zum Benutzernamen.">
        {(p) => <Eingabe {...p} type="password" autoComplete="new-password" value={neu} onChange={(e) => setNeu(e.target.value)} autoFocus />}
      </Feld>
      <Feld label="Passwort wiederholen">
        {(p) => <Eingabe {...p} type="password" autoComplete="new-password" value={wdh} onChange={(e) => setWdh(e.target.value)} />}
      </Feld>
      {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
      <Knopf type="submit" variante="pri" className="w-full" laedt={laedt}>Passwort speichern</Knopf>
      <Knopf variante="sec" className="w-full" onClick={() => void abmelden()}>Abbrechen</Knopf>
    </Formular>
  );
}

export function AuthenticatorEinrichten({ onFertig, onAbbrechen }: {
  onFertig: (s: Status) => void; onAbbrechen?: () => void;
}) {
  const [qr, setQr] = useState<{ otpauth_url: string; qr_svg: string } | null>(null);
  const [code, setCode] = useState("");
  const [fehler, setFehler] = useState("");
  const [laedt, setLaedt] = useState(false);
  const gestartet = useRef(false);
  useEffect(() => {
    if (gestartet.current) return;
    gestartet.current = true;
    api<{ otpauth_url: string; qr_svg: string }>("auth/2fa/einrichten/", { method: "POST", ohneAbmeldeSignal: true })
      .then(setQr)
      .catch((e) => setFehler(fehlertext(e)));
  }, []);
  const schluessel = qr ? new URL(qr.otpauth_url).searchParams.get("secret") ?? "" : "";
  const absenden = async (e: FormEvent) => {
    e.preventDefault();
    setLaedt(true);
    setFehler("");
    try {
      onFertig(await api<Status>("auth/2fa/bestaetigen/", { body: { code }, ohneAbmeldeSignal: true }));
    } catch (err) {
      setFehler(fehlertext(err));
      setCode("");
    } finally {
      setLaedt(false);
    }
  };
  return (
    <Formular titel="Authenticator-App einrichten"
      text="Scanne den Code mit einer Authenticator-App (z. B. Microsoft oder Google Authenticator) und gib danach die angezeigte 6-stellige Zahl ein."
      onSubmit={absenden}>
      {qr ? (
        <div className="flex gap-4 items-center flex-wrap">
          <div className="w-44 h-44 bg-white p-2 rounded-lg border border-rand [&_svg]:w-full [&_svg]:h-full"
            role="img" aria-label="QR-Code für die Authenticator-App" dangerouslySetInnerHTML={{ __html: qr.qr_svg }} />
          <div className="flex flex-col gap-1 text-[0.8125rem] min-w-0">
            <span className="gedaempft">Ohne Kamera: Schlüssel von Hand eingeben</span>
            <code className="num break-all text-sm" data-testid="otp-schluessel">{schluessel}</code>
          </div>
        </div>
      ) : !fehler ? <span className="text-sm gedaempft">QR-Code wird erzeugt …</span> : null}
      <Feld label="Code aus der App">
        {(p) => <Eingabe {...p} className="num text-[1.375rem] tracking-[.3em] h-[3.25rem] text-center" inputMode="numeric"
          autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
      </Feld>
      {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
      <Knopf type="submit" variante="pri" className="w-full" laedt={laedt} disabled={!qr || code.trim().length < 6}>
        Bestätigen
      </Knopf>
      {onAbbrechen ? <Knopf variante="sec" className="w-full" onClick={onAbbrechen}>Abbrechen</Knopf> : null}
    </Formular>
  );
}

/** Passkey anlegen – bei der ersten Anmeldung (statt der App) und unter Mein Konto (Festlegung 08.10.2026). */
export function PasskeyEinrichten({ onFertig, onAbbrechen }: { onFertig: (s: Status) => void; onAbbrechen?: () => void }) {
  const { status } = useAuth();
  const hindernis = passkeyHindernis(status?.passkey);
  const [name, setName] = useState(() => geraetename());
  const [fehler, setFehler] = useState("");
  const [laedt, setLaedt] = useState(false);
  const vorrat = useRef(new PasskeyVorrat("registrieren"));
  useEffect(() => { if (!hindernis) vorrat.current.vorbereiten(); }, [hindernis]);
  const absenden = async (e: FormEvent) => {
    e.preventDefault();
    setLaedt(true);
    setFehler("");
    try {
      const antwort = await passkeyErstellen(await vorrat.current.holen());
      onFertig(await api<Status>("auth/passkey/registrieren/", { body: { antwort, name: name.trim() }, ohneAbmeldeSignal: true }));
    } catch (err) {
      vorrat.current.vorbereiten();
      setFehler(err instanceof ApiFehler || !(err instanceof Error) ? fehlertext(err) : err.message);
    } finally {
      setLaedt(false);
    }
  };
  return (
    <Formular titel="Passkey einrichten"
      text="Der Passkey liegt sicher auf diesem Gerät (oder im Passwortmanager) und wird mit Fingerabdruck, Gesicht oder PIN freigegeben – statt eines Codes aus der App. Am besten gleich auf PC und Telefon einrichten."
      onSubmit={absenden}>
      {hindernis ? <Meldung art="warn">{hindernis}</Meldung> : <>
        <Feld label="Name des Passkeys" hinweis="z. B. „iPhone“ oder „Büro-PC“ – damit du ihn später wiedererkennst">
          {(p) => <Eingabe {...p} value={name} maxLength={64} onChange={(e) => setName(e.target.value)} />}
        </Feld>
        {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
        <Knopf type="submit" variante="pri" icon="passkey" className="w-full" laedt={laedt} disabled={!name.trim()}
          data-testid="passkey-anlegen">Passkey anlegen</Knopf>
      </>}
      {onAbbrechen ? <Knopf variante="sec" className="w-full" onClick={onAbbrechen}>Abbrechen</Knopf> : null}
    </Formular>
  );
}

/** Erste Anmeldung mit Pflicht zum zweiten Faktor: Passkey oder Authenticator-App */
function ZweitenFaktorEinrichten({ onFertig, onAbbrechen }: { onFertig: (s: Status) => void; onAbbrechen: () => void }) {
  const { status } = useAuth();
  const [art, setArt] = useState<"passkey" | "app">(passkeyHindernis(status?.passkey) ? "app" : "passkey");
  return (
    <div className="flex flex-col gap-4">
      <Segmente label="Zweiter Faktor" wert={art} onWahl={setArt}
        werte={[{ wert: "passkey", text: "Passkey" }, { wert: "app", text: "Authenticator-App" }]} />
      {art === "passkey" ? <PasskeyEinrichten onFertig={onFertig} onAbbrechen={onAbbrechen} />
        : <AuthenticatorEinrichten onFertig={onFertig} onAbbrechen={onAbbrechen} />}
    </div>
  );
}

export function NotfallcodesAnzeige({ codes, onWeiter, weiterText = "Codes notiert – weiter" }: {
  codes: string[]; onWeiter: () => void; weiterText?: string;
}) {
  return (
    <div className="flex flex-col gap-4">
      <h1 className="m-0 text-[1.375rem] font-semibold">Notfall-Codes</h1>
      <p className="m-0 text-sm leading-normal text-text2">
        Jeder Code gilt einmal, falls das Handy verloren geht. Die Codes werden nur jetzt angezeigt:
        ausdrucken oder notieren und sicher aufbewahren.
      </p>
      <ol className="grid grid-cols-1 min-[23.75rem]:grid-cols-2 gap-x-6 gap-y-1 m-0 pl-6 num text-[0.9375rem]" data-testid="notfallcodes">
        {codes.map((c) => <li key={c}>{c}</li>)}
      </ol>
      <div className="flex gap-2">
        <Knopf variante="sec" onClick={() => window.print()}>Drucken</Knopf>
        <Knopf variante="pri" className="grow" onClick={onWeiter}>{weiterText}</Knopf>
      </div>
    </div>
  );
}

export function Anmeldung() {
  const { status, setStatus, abmelden } = useAuth();
  const [codes, setCodes] = useState<{ codes: string[]; status: Status } | null>(null);
  let inhalt: ReactNode;
  if (codes) {
    inhalt = <NotfallcodesAnzeige codes={codes.codes} onWeiter={() => { setStatus(codes.status); setCodes(null); }} />;
  } else if (status?.schritt === "kennwort_aendern") {
    inhalt = <SchrittKennwort />;
  } else if (status?.schritt === "2fa_einrichten") {
    inhalt = (
      <ZweitenFaktorEinrichten
        onFertig={(s) => (s.notfallcodes?.length ? setCodes({ codes: s.notfallcodes, status: s }) : setStatus(s))}
        onAbbrechen={() => void abmelden()}
      />
    );
  } else if (status?.schritt === "2fa") {
    inhalt = <SchrittCode />;
  } else {
    inhalt = <SchrittAnmelden />;
  }
  return <Rahmen>{inhalt}</Rahmen>;
}
