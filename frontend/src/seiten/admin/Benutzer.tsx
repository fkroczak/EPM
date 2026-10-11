/** Entwurf 17 · Benutzer: anlegen, ändern, sperren, Einmal-Passwort, 2FA zurücksetzen; Rechte je Gruppe einstellbar.
 *  Fehlerliste 02.10.2026, Punkt 6: Konten „ohne Login“ setzen und wieder einbinden (Login geben), Rolle „Keine
 *  Berechtigung“, Testbenutzer-Schalter für Betrachter, Mitarbeiter (auch erweitert) und Mediziner, Zwei-Faktor-Anmeldung freiwillig
 *  oder Pflicht (Karte „Anmeldung“). */
import { useEffect, useState } from "react";
import { PdfDialog } from "@/components/PdfDialog";
import { useLocation, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, STATUS_PRUEFEN, alle, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import { relativ, zeitpunkt } from "@/lib/format";
import { detailZeigen } from "@/lib/stufen";
import { ROLLEN } from "@/lib/typen";
import type { Benutzer as BenutzerTyp } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, Seitenkopf, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";

type Rechte = {
  rechte: { code: string; name: string; beschreibung: string }[];
  rollen: { code: string; name: string }[];
  matrix: Record<string, Record<string, boolean>>;
  fest: [string, string][];
  standard: Record<string, string[]>;
  /** Rollen, die diese Rechte nur bei Testpatienten ausüben (Admin) */
  nur_testpatienten: { rollen: string[]; rechte: string[] };
  /** Rechte, die nur bestimmte Rollen haben können (endgültig löschen: Mediziner und Admin) */
  nur_rollen: Record<string, string[]>;
  /** Rollen ohne jedes Recht (Konten ohne Login) – stehen nicht in der Tabelle */
  ohne_rechte?: string[];
};
type Formular = { titel: string; first_name: string; last_name: string; kuerzel: string; funktion: string; username: string; rolle: string;
  ist_test: boolean; ohne_login: boolean;
  /** Rollen in weiteren Firmen (11.10.2026); die der DSKM ist ``rolle`` */
  firmenrollen: Record<string, string> };
type Anmeldung = { zweiter_faktor: "freiwillig" | "admins" | "alle"; auswahl: { wert: string; name: string }[]; geaendert_am: string | null;
  ohne_zweiten_faktor: { id: number; anzeigename: string; rolle: string }[] };
const TESTBENUTZER_ROLLEN = ["betrachter", "mitarbeiter", "mitarbeiter_plus", "mediziner"];
const TITEL = ["", "Dr.", "Dr. med.", "Prof. Dr.", "Prof. Dr. med.", "Dipl.-Oec. troph."];
const LEER: Formular = { titel: "", first_name: "", last_name: "", kuerzel: "", funktion: "", username: "", rolle: "mitarbeiter", ist_test: false,
  ohne_login: false, firmenrollen: {} };

function anzeige(f: Formular) {
  const name = [f.titel, f.first_name ? `${f.first_name.trim()[0]}.` : "", f.last_name].filter(Boolean).join(" ");
  return name.trim() || "wird aus Titel, Vorname und Nachname gebildet";
}

function zustand(b: BenutzerTyp): { text: string; art: "ok" | "fehler" | "warn" | "neutral" } {
  if (b.nur_historisch) return { text: "ohne Login", art: "neutral" };
  if (b.ausgeblendet_am) return { text: "ausgeblendet", art: "neutral" };
  if (b.gesperrt_am || !b.is_active) return { text: "gesperrt", art: "fehler" };
  // die Zwei-Faktor-Anmeldung zählt nur zur Einrichtung, wenn sie für diese Person Pflicht ist
  if (b.muss_kennwort_aendern || (b.zweiter_faktor_pflicht && !b.zweiter_faktor)) return { text: "Einrichtung offen", art: "warn" };
  return { text: "aktiv", art: "ok" };
}

function Kennwortanzeige({ id, kennwort, gueltig, name, benutzername }: { id: number; kennwort: string; gueltig: string | null; name: string; benutzername: string }) {
  const [blatt, setBlatt] = useState(false);
  return (
    <div className="meldung info flex flex-col gap-2" data-testid="einmal-kennwort">
      <span className="text-[0.8125rem] font-medium">Einmal-Passwort</span>
      <span className="num text-xl font-semibold tracking-[.08em]">{kennwort}</span>
      <span className="text-[0.8125rem] leading-normal">
        {gueltig ? `Gültig bis ${zeitpunkt(gueltig)}. ` : ""}Persönlich übergeben. Beim ersten Login legt {name} ein eigenes Passwort fest
        (und richtet die Authenticator-App ein, wenn die Zwei-Faktor-Anmeldung Pflicht ist). Das Passwort wird nur jetzt angezeigt.
      </span>
      <div><Knopf klein icon="dokument" onClick={() => setBlatt(true)}>Zugangsblatt drucken</Knopf></div>
      <PdfDialog offen={blatt} onOffen={setBlatt} titel={`Zugangsblatt für ${name}`} pfad={`benutzer/${id}/zugangsblatt/`}
        body={{ kennwort }} dateiname={`Zugang-${benutzername}.pdf`} />
    </div>
  );
}

function RechteMatrix() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const daten = useQuery({ queryKey: ["rechte"], queryFn: () => api<Rechte>("rechte/") });
  const [m, setM] = useState<Record<string, Record<string, boolean>> | null>(null);
  useEffect(() => { if (daten.data) setM(structuredClone(daten.data.matrix)); }, [daten.data]);
  const speichern = useMutation({
    mutationFn: () => api<Rechte>("rechte/", { method: "PUT", body: { matrix: m } }),
    onSuccess: (r) => { qc.setQueryData(["rechte"], r); melden("Rechte gespeichert. Sie gelten ab sofort."); void qc.invalidateQueries({ queryKey: ["rechte"] }); },
  });
  if (!daten.data || !m) return <Karte className="px-5 py-4"><Laden /></Karte>;
  const d = daten.data;
  const fest = new Set(d.fest.map(([r, c]) => `${r}.${c}`));
  // „Keine Berechtigung“ hat nie Rechte und ist nicht einstellbar – keine Spalte
  const rollen = d.rollen.filter((r) => !(d.ohne_rechte ?? []).includes(r.code) && m[r.code] && d.matrix[r.code]);
  const geaendert = rollen.reduce((n, r) => n + d.rechte.filter((x) => m[r.code][x.code] !== d.matrix[r.code][x.code]).length, 0);
  const standard = () => setM({ ...m, ...Object.fromEntries(rollen.map((r) => [r.code, Object.fromEntries(d.rechte.map((x) => [x.code, (d.standard[r.code] ?? []).includes(x.code) || fest.has(`${r.code}.${x.code}`)]))])) });
  return (
    <Karte className="px-5 py-[1.125rem] flex flex-col gap-3 overflow-x-auto" data-testid="rechte">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <h2 className="lbl m-0">Was die Rollen dürfen</h2>
          <span className="text-[0.8125rem] gedaempft leading-normal max-w-[70ch]">Je Gruppe einstellbar. Mediziner sind dem Admin gleichgestellt, außer bei Benutzern,
            dem Wiederöffnen abgeschlossener Akten, Sicherungen, Testdaten und der Systemverwaltung. Admins dürfen alles, Patientendaten schreiben sie aber nur
            bei Testpatienten – ausgenommen: Akten abschließen, Dokumente einem anderen Patienten zuordnen und endgültig löschen, das geht auch bei echten Akten.
            Die Rolle „Keine Berechtigung“ (Konten ohne Login) hat nie Rechte und steht deshalb nicht in der Tabelle. Die Systemverwaltung (Server und EPM) hat standardmäßig nur der Admin; für eine Urlaubsvertretung kann sie hier einer Gruppe freigeschaltet werden. Testbenutzer erhalten nie Rechte über
            Testpatienten hinaus.</span>
        </div>
        <div className="flex gap-2">
          <Knopf klein onClick={standard}>Standard</Knopf>
          <Knopf klein variante="pri" disabled={!geaendert} laedt={speichern.isPending} onClick={() => speichern.mutate()}>
            Speichern{geaendert ? ` (${geaendert})` : ""}
          </Knopf>
        </div>
      </div>
      <table className="tabelle">
        <thead><tr><th className="th"><span className="sr-only">Recht</span></th>{rollen.map((r) => <th key={r.code} className="th text-center">{r.name}</th>)}</tr></thead>
        <tbody>
          {d.rechte.map((x) => (
            <tr key={x.code}>
              <td className="td"><span className="text-sm">{x.name}</span>{x.beschreibung ? <><br /><span className="text-xs gedaempft">{x.beschreibung}</span></> : null}</td>
              {rollen.map((r) => {
                const istFest = fest.has(`${r.code}.${x.code}`);
                const vorbehalten = !!d.nur_rollen[x.code] && !d.nur_rollen[x.code].includes(r.code);
                const nurTest = d.nur_testpatienten.rollen.includes(r.code) && d.nur_testpatienten.rechte.includes(x.code);
                const anders = m[r.code][x.code] !== d.matrix[r.code][x.code];
                return (
                  <td key={r.code} className={cx("td text-center", anders && "bg-warn-bg")}>
                    <input type="checkbox" aria-label={`${r.name}: ${x.name}`} checked={m[r.code][x.code]} disabled={istFest || vorbehalten}
                      title={istFest ? "festes Recht, damit sich die Administration nicht aussperrt"
                        : vorbehalten ? `nur ${d.nur_rollen[x.code].map((c) => d.rollen.find((y) => y.code === c)?.name ?? c).join(", ")}` : undefined}
                      onChange={(e) => setM({ ...m, [r.code]: { ...m[r.code], [x.code]: e.target.checked } })} />
                    {nurTest ? <span className="block text-[0.6875rem] gedaempft leading-tight">nur Testpatienten</span> : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <Fehleranzeige fehler={speichern.error} />
      <span className="text-xs gedaempft">Jede Änderung steht mit Person und Zeitpunkt im Audit-Log.</span>
    </Karte>
  );
}

/** Anmeldung: Zwei-Faktor-Anmeldung freiwillig, Pflicht für Admins oder Pflicht für alle (Fehlerliste 02.10.2026, 6.5) */
function AnmeldungKarte({ onBenutzer }: { onBenutzer: (id: number) => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const daten = useQuery({ queryKey: ["benutzer", "anmeldung"], queryFn: () => api<Anmeldung>("benutzer/anmeldung/") });
  const [wert, setWert] = useState<string | null>(null);
  useEffect(() => { if (daten.data) setWert(daten.data.zweiter_faktor); }, [daten.data]);
  const speichern = useMutation({
    mutationFn: () => api<Anmeldung>("benutzer/anmeldung/", { method: "PUT", body: { zweiter_faktor: wert } }),
    onSuccess: (r) => {
      qc.setQueryData(["benutzer", "anmeldung"], r);
      void qc.invalidateQueries({ queryKey: ["benutzer"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      window.dispatchEvent(new Event(STATUS_PRUEFEN));
      melden("Anmeldung gespeichert. Die Regel gilt ab sofort.");
    },
  });
  const d = daten.data;
  if (!d || wert == null) return <Karte className="px-5 py-4" id="anmeldung">{daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />}</Karte>;
  const TEXT: Record<string, string> = {
    freiwillig: "Jede Person entscheidet selbst unter „Mein Konto“. Anmelden geht mit Benutzername und Passwort.",
    admins: "Admins müssen einen zweiten Faktor einrichten (Authenticator-App oder Passkey), alle anderen entscheiden selbst.",
    alle: "Alle müssen einen zweiten Faktor einrichten (Authenticator-App oder Passkey), bevor sie mit EPM arbeiten können.",
  };
  const betroffen = d.ohne_zweiten_faktor.filter((u) => wert === "alle" || (wert === "admins" && u.rolle === "admin"));
  return (
    <Karte className="px-5 py-[1.125rem] flex flex-col gap-3" id="anmeldung" data-testid="anmeldung">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <h2 className="lbl m-0">Anmeldung: Zwei-Faktor-Anmeldung (2FA)</h2>
          <span className="text-[0.8125rem] gedaempft leading-normal max-w-[70ch]">Zweiter Faktor ist der Code aus einer Authenticator-App oder ein Passkey (Fingerabdruck, Gesicht, PIN).
            Wer ihn eingerichtet hat, wird beim Anmelden immer danach gefragt – auch wenn er freiwillig ist.</span>
        </div>
        <Knopf klein variante="pri" disabled={wert === d.zweiter_faktor} laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf>
      </div>
      <div className="flex flex-col gap-1.5" role="radiogroup" aria-label="Zwei-Faktor-Anmeldung">
        {d.auswahl.map((a) => (
          <label key={a.wert} className="flex items-start gap-2.5 text-sm cursor-pointer">
            <input type="radio" name="zweiter-faktor" className="mt-1" checked={wert === a.wert} onChange={() => setWert(a.wert)} />
            <span><span className="font-medium">{a.name}</span><br /><span className="text-[0.8125rem] gedaempft">{TEXT[a.wert] ?? ""}</span></span>
          </label>
        ))}
      </div>
      {wert !== d.zweiter_faktor && betroffen.length ? (
        <Meldung art="warn">{betroffen.length === 1 ? "1 Person muss" : `${betroffen.length} Personen müssen`} dann zuerst die Authenticator-App einrichten
          (mit der nächsten Seite, die sie öffnen): {betroffen.map((u) => u.anzeigename).join(", ")}.</Meldung>
      ) : null}
      {d.ohne_zweiten_faktor.length ? (
        <span className="text-[0.8125rem]" data-testid="ohne-2fa">Ohne 2FA ({d.ohne_zweiten_faktor.length}):{" "}
          {d.ohne_zweiten_faktor.map((u, i) => (
            <span key={u.id}>{i ? ", " : ""}<button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer underline"
              onClick={() => onBenutzer(u.id)}>{u.anzeigename}</button></span>
          ))}
          <span className="gedaempft"> · Einrichten kann jede Person nur selbst unter „Mein Konto“.</span></span>
      ) : <span className="text-[0.8125rem] gedaempft">Alle aktiven Konten haben die Zwei-Faktor-Anmeldung eingerichtet.</span>}
      <Fehleranzeige fehler={speichern.error} />
      <span className="text-xs gedaempft">Bestätigungen (endgültig löschen, Wiederherstellen, Updates, Sicherung, Import) verlangen immer Passwort und
        Code – dafür muss die Person die Zwei-Faktor-Anmeldung eingerichtet haben, auch wenn sie freiwillig ist. Jede Änderung steht im Audit-Log.</span>
    </Karte>
  );
}

type Kennwort = { id: number; kennwort: string; gueltig: string | null };

/** Rolle in der Liste; bei mehreren Firmen je Firma mit Kürzel („DSKM Mitarbeiter“, „RG Mediziner“) */
function RollenChips({ b }: { b: BenutzerTyp }) {
  const alle = useIch().alle_firmen ?? [];
  if (alle.length < 2) return <Chip art={b.rolle === "keine" ? undefined : "akzent"}>{ROLLEN[b.rolle as keyof typeof ROLLEN] ?? b.rolle}</Chip>;
  const rollen = alle.map((x) => ({ firma: x, rolle: x.kuerzel === "dskm" ? b.rolle : b.firmenrollen?.[x.kuerzel] ?? "keine" }))
    .filter((r) => r.rolle !== "keine");
  if (!rollen.length) return <Chip>{ROLLEN.keine}</Chip>;
  return (
    <span className="inline-flex flex-col items-start gap-1">
      {rollen.map((r) => (
        <Chip key={r.firma.kuerzel} art="akzent" title={r.firma.name}>
          <span className="font-mono text-[0.625rem] opacity-75">{r.firma.kurzname}</span> {ROLLEN[r.rolle as keyof typeof ROLLEN] ?? r.rolle}
        </Chip>
      ))}
    </span>
  );
}

function Detail({ benutzer, neu, onGewaehlt, kennwortAnzeige, setKennwortAnzeige }: {
  benutzer: BenutzerTyp | null; neu: boolean; onGewaehlt: (id: number | null) => void;
  kennwortAnzeige: Kennwort | null; setKennwortAnzeige: (k: Kennwort | null) => void;
}) {
  const ich = useIch();
  const { darf } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  // Rolle je Firma (Anforderung 11.10.2026): DSKM wie bisher „Rolle“, weitere Firmen darunter
  const alleFirmen = ich.alle_firmen ?? [];
  const weitereFirmen = alleFirmen.filter((x) => x.kuerzel !== "dskm");
  const start = (): Formular => benutzer ? {
    titel: benutzer.titel, first_name: benutzer.first_name, last_name: benutzer.last_name, kuerzel: benutzer.kuerzel ?? "",
    funktion: benutzer.funktion, username: benutzer.username, rolle: benutzer.rolle, ist_test: benutzer.ist_test, ohne_login: false,
    firmenrollen: Object.fromEntries(Object.entries(benutzer.firmenrollen ?? {}).filter(([k]) => k !== "dskm")),
  } : { ...LEER };
  const [f, setF] = useState<Formular>(start);
  const kennwort = kennwortAnzeige && benutzer && kennwortAnzeige.id === benutzer.id ? kennwortAnzeige : null;
  const [frage, setFrage] = useState<"" | "kennwort" | "2fa" | "sperren" | "testdaten" | "ohnelogin" | "ausblenden">("");
  const [loginRolle, setLoginRolle] = useState<string | null>(null);
  useEffect(() => { setF(start()); }, [benutzer?.id, neu]); // eslint-disable-line react-hooks/exhaustive-deps
  const neuLaden = () => void qc.invalidateQueries({ queryKey: ["benutzer"] });
  const speichern = useMutation({
    mutationFn: () => {
      // „ohne Login“ gibt es nur beim Anlegen; ein Konto ohne Login hat keine Rolle und keinen Testzugang
      const { ohne_login, firmenrollen, ...rest } = f;
      // Rollen in weiteren Firmen nur, wenn es sie gibt und das Konto ein Login hat
      const felder = weitereFirmen.length && !ohne_login && !benutzer?.nur_historisch ? { ...rest, firmenrollen } : rest;
      const body = neu ? (ohne_login ? { ...felder, rolle: "keine", ist_test: false, ohne_login: true } : felder)
        : benutzer!.nur_historisch ? { ...felder, rolle: undefined, ist_test: undefined } : felder;
      return neu
        ? api<BenutzerTyp & { einmal_kennwort?: string }>("benutzer/", { body })
        : api<BenutzerTyp & { einmal_kennwort?: string }>(`benutzer/${benutzer!.id}/`, { method: "PATCH", body });
    },
    onSuccess: (b) => {
      neuLaden();
      if (neu) {
        if (b.einmal_kennwort) setKennwortAnzeige({ id: b.id, kennwort: b.einmal_kennwort, gueltig: b.einmal_kennwort_gueltig_bis });
        onGewaehlt(b.id);
        melden(b.nur_historisch ? "Benutzer ohne Login angelegt." : "Benutzer angelegt.");
      } else melden("Benutzer gespeichert.");
    },
  });
  // Konto ohne Login wieder einbinden: Rolle wählen, Einmal-Passwort für das Zugangsblatt
  const loginGeben = useMutation({
    mutationFn: () => api<BenutzerTyp & { einmal_kennwort: string }>(`benutzer/${benutzer!.id}/login-geben/`, { body: { rolle: loginRolle } }),
    onSuccess: (b) => {
      neuLaden();
      setLoginRolle(null);
      setKennwortAnzeige({ id: b.id, kennwort: b.einmal_kennwort, gueltig: b.einmal_kennwort_gueltig_bis });
      setF((v) => ({ ...v, rolle: b.rolle }));
      melden(`${b.anzeigename} hat wieder einen Login.`);
    },
  });
  const aktion = useMutation({
    mutationFn: (art: "kennwort" | "2fa" | "sperren" | "entsperren" | "testdaten" | "ohnelogin" | "ausblenden" | "einblenden") => {
      if (art === "testdaten") return api<Record<string, number>>("testdaten/zuruecksetzen/", { method: "POST" });
      const pfad = { kennwort: "einmal-kennwort", "2fa": "2fa-zuruecksetzen", sperren: "sperren", entsperren: "entsperren", ohnelogin: "ohne-login",
        ausblenden: "ausblenden", einblenden: "einblenden" }[art];
      return api<Record<string, unknown>>(`benutzer/${benutzer!.id}/${pfad}/`, { method: "POST" });
    },
    onSuccess: (r, art) => {
      neuLaden();
      setFrage("");
      if (art === "kennwort" || art === "2fa") setKennwortAnzeige({ id: benutzer!.id, kennwort: String(r.einmal_kennwort), gueltig: String(r.gueltig_bis ?? "") || null });
      if (art === "testdaten") void qc.invalidateQueries({});
      if (art === "ohnelogin") { setKennwortAnzeige(null); setF((v) => ({ ...v, rolle: "keine", ist_test: false })); }
      melden({ kennwort: "Neues Einmal-Passwort erzeugt.", "2fa": "2FA zurückgesetzt, neues Einmal-Passwort erzeugt.", sperren: "Benutzer gesperrt.",
        ohnelogin: "Konto ist jetzt ohne Login und ohne Rechte.",
        ausblenden: "Testbenutzer ausgeblendet.", einblenden: "Testbenutzer wieder eingeblendet.",
        entsperren: "Benutzer entsperrt.", testdaten: `Testdaten zurückgesetzt (${r.geloescht ?? 0} gelöscht, ${r.angelegt ?? 0} angelegt).` }[art]);
    },
  });
  const fehler: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const set = (k: keyof Formular) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const z = benutzer ? zustand(benutzer) : null;
  const name = benutzer ? benutzer.anzeigename : "die Person";
  const fragen = {
    kennwort: ["Einmal-Passwort erzeugen", "Das bisherige Passwort gilt danach nicht mehr, alle Anmeldungen der Person werden beendet."],
    "2fa": ["2FA zurücksetzen", "Authenticator, Passkeys und Notfall-Codes werden gelöscht. Mit dem neuen Einmal-Passwort richtet die Person den zweiten Faktor neu ein."],
    sperren: ["Benutzer sperren", "Die Person kann sich nicht mehr anmelden, alle Sitzungen werden beendet. Einträge bleiben zugeordnet."],
    testdaten: ["Testdaten zurücksetzen", "Alle Testpatienten (Nr. ab 9001) werden gelöscht und die Musterdaten neu angelegt. Echte Patienten bleiben unberührt."],
    ausblenden: ["Testbenutzer ausblenden", "Das Konto wird gesperrt, alle Anmeldungen werden beendet, und es erscheint in keiner Liste mehr (in der Benutzerverwaltung nur mit „Ausgeblendete zeigen“). Es wird nicht gelöscht; Einträge bleiben zugeordnet. Mit „Einblenden“ ist es wieder da."],
    ohnelogin: ["Auf „ohne Login“ setzen", "Die Person kann sich nicht mehr anmelden und hat keine Rechte mehr (Rolle „Keine Berechtigung“). Passwort, Authenticator, Passkeys und Notfall-Codes werden gelöscht, alle Sitzungen beendet. Ihre Einträge bleiben ihr zugeordnet. Mit „Login geben“ lässt sie sich später wieder einbinden."],
  } as const;
  const historisch = !!benutzer?.nur_historisch;
  const ohneLogin = neu ? f.ohne_login : historisch;
  const testMoeglich = !ohneLogin && TESTBENUTZER_ROLLEN.includes(f.rolle) && benutzer?.id !== ich.id;
  return (
    <Karte className="px-5 py-[1.125rem] flex flex-col gap-4 min-w-0 scroll-mt-20" data-testid="benutzer-detail">
      <div className="flex items-center gap-2.5 flex-wrap">
        <h2 className="m-0 text-lg font-semibold">{neu ? "Neuer Benutzer" : name}</h2>
        {z ? <Chip art={z.art}>{z.art === "ok" ? <Icon name="haken" /> : z.art === "fehler" ? <Icon name="schloss" /> : null}{z.text}</Chip> : null}
      </div>
      {benutzer?.gesperrt_am ? <Meldung art="fehler">Gesperrt am {zeitpunkt(benutzer.gesperrt_am)}{benutzer.sperrgrund ? ` · ${benutzer.sperrgrund}` : ""}.</Meldung> : null}
      {historisch ? (
        <Meldung><span data-testid="ohne-login-hinweis">Ohne Login: nur als Name, damit Einträge dieser Person zugeordnet bleiben (z. B. aus dem Altsystem
          übernommen oder frühere Mitarbeiter). Kann sich nicht anmelden und hat keine Rechte. Mit „Login geben“ wird daraus wieder ein Konto zum Arbeiten.</span></Meldung>
      ) : null}
      {kennwort ? <Kennwortanzeige id={kennwort.id} kennwort={kennwort.kennwort} gueltig={kennwort.gueltig} name={name} benutzername={benutzer?.username ?? ""} /> : null}
      {benutzer?.ausgeblendet_am ? (
        <Meldung><span className="flex items-center justify-between gap-3 flex-wrap" data-testid="ausgeblendet-hinweis">
          <span>Ausgeblendet am {zeitpunkt(benutzer.ausgeblendet_am)}: gesperrt und in keiner Liste sichtbar.</span>
          <Knopf klein laedt={aktion.isPending && aktion.variables === "einblenden"} onClick={() => aktion.mutate("einblenden")}>Einblenden</Knopf></span></Meldung>
      ) : null}
      {benutzer?.ist_test && !benutzer.ausgeblendet_am ? (
        <div className="meldung warn flex flex-col gap-2 text-[0.8125rem]">
          <span><strong>Testbenutzer:</strong> sieht und bearbeitet ausschließlich Testpatienten, nie echte Patientendaten. Oben erscheint dauerhaft ein
            Hinweis „Testzugang“. Für Schulungen und zum Durchklicken nach jedem Update.</span>
          <div className="flex gap-2 flex-wrap">
            {darf("testdaten_zuruecksetzen") ? <Knopf klein onClick={() => setFrage("testdaten")}>Testdaten auf Ausgangsstand zurücksetzen</Knopf> : null}
            {benutzer.id !== ich.id ? <Knopf klein onClick={() => setFrage("ausblenden")}>Testbenutzer ausblenden</Knopf> : null}
          </div>
        </div>
      ) : null}
      <form className="grid grid-cols-4 gap-3" onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        <Feld label="Titel" fehler={fehler.titel}>
          {(p) => <Auswahl {...p} value={f.titel} onChange={set("titel")}>{TITEL.concat(TITEL.includes(f.titel) ? [] : [f.titel]).map((t) => <option key={t} value={t}>{t || "—"}</option>)}</Auswahl>}
        </Feld>
        <Feld label="Vorname" fehler={fehler.first_name}>{(p) => <Eingabe {...p} value={f.first_name} onChange={set("first_name")} />}</Feld>
        <Feld label="Nachname" fehler={fehler.last_name}>{(p) => <Eingabe {...p} value={f.last_name} onChange={set("last_name")} />}</Feld>
        <Feld label="Kürzel" hinweis="erscheint an Einträgen" fehler={fehler.kuerzel}>{(p) => <Eingabe {...p} className="num" maxLength={4} value={f.kuerzel} onChange={set("kuerzel")} />}</Feld>
        <Feld label="Funktion" className="col-span-2" fehler={fehler.funktion}>{(p) => <Eingabe {...p} placeholder="z. B. Ärztin, Ernährungsberaterin" value={f.funktion} onChange={set("funktion")} />}</Feld>
        <Feld label="Benutzername" hinweis="zum Anmelden" fehler={fehler.username}>{(p) => <Eingabe {...p} className="num" autoComplete="off" value={f.username} onChange={set("username")} />}</Feld>
        <Feld label={weitereFirmen.length ? `Rolle ${alleFirmen.find((x) => x.kuerzel === "dskm")?.kurzname ?? "DSKM"}` : "Rolle"} fehler={fehler.rolle}
          hinweis={ohneLogin ? "ohne Login: keine Rechte" : undefined}>
          {(p) => <Auswahl {...p} value={ohneLogin ? "keine" : f.rolle} disabled={ohneLogin} data-testid="rolle-dskm"
            onChange={(e) => setF({ ...f, rolle: e.target.value, ist_test: TESTBENUTZER_ROLLEN.includes(e.target.value) ? f.ist_test : false })}>
            {Object.entries(ROLLEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Auswahl>}
        </Feld>
        {weitereFirmen.map((firma) => (
          <Feld key={firma.kuerzel} label={`Rolle ${firma.kurzname}`} fehler={fehler.firmenrollen}
            hinweis={ohneLogin ? undefined : `bei ${firma.name}; „Keine Berechtigung“ = kein Zugang`}>
            {(p) => <Auswahl {...p} value={ohneLogin ? "keine" : f.firmenrollen[firma.kuerzel] ?? "keine"} disabled={ohneLogin}
              data-testid={`rolle-${firma.kuerzel}`}
              onChange={(e) => setF({ ...f, firmenrollen: { ...f.firmenrollen, [firma.kuerzel]: e.target.value } })}>
              {Object.entries(ROLLEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Auswahl>}
          </Feld>
        ))}
        <div className="col-span-4 flex flex-col gap-1.5">
          {neu ? (
            <label className="flex items-start gap-2 text-sm cursor-pointer">
              <input type="checkbox" className="mt-1" checked={f.ohne_login} onChange={(e) => setF({ ...f, ohne_login: e.target.checked })} />
              <span>Ohne Login anlegen<br /><span className="text-[0.8125rem] gedaempft">Nur als Name für Einträge (z. B. frühere Mitarbeiter): kein Passwort,
                keine Rechte. Ein Login lässt sich später geben.</span></span>
            </label>
          ) : null}
          <label className={cx("flex items-start gap-2 text-sm", testMoeglich ? "cursor-pointer" : "opacity-60")}>
            <input type="checkbox" className="mt-1" checked={f.ist_test && !ohneLogin} disabled={!testMoeglich && !f.ist_test}
              onChange={(e) => setF({ ...f, ist_test: e.target.checked })} />
            <span>Testbenutzer<br /><span className="text-[0.8125rem] gedaempft">Sieht und bearbeitet ausschließlich Testpatienten – für Schulungen und zum
              Ausprobieren. Möglich für Betrachter, Mitarbeiter, Mitarbeiter (erweitert) und Mediziner{benutzer?.id === ich.id ? "; nicht für das eigene Konto" : ""}.</span>
              {fehler.ist_test ? <><br /><span className="fehlertext" role="alert">{fehler.ist_test}</span></> : null}</span>
          </label>
        </div>
        <span className="col-span-4 text-[0.8125rem] gedaempft">Anzeige in der Akte: <span className="text-tinte font-medium">{anzeige(f)}</span></span>
        {speichern.error && !Object.keys(fehler).length ? <Meldung art="fehler" className="col-span-4">{speichern.error.message}</Meldung> : null}
        {neu ? (
          f.ohne_login ? <Meldung className="col-span-4">Das Konto bekommt kein Passwort und keine Rechte. Es dient nur dazu, Einträge einer Person zuzuordnen.</Meldung>
            : <Meldung className="col-span-4">Nach dem Anlegen erzeugt EPM ein Einmal-Passwort. Du gibst es der Person persönlich oder als ausgedrucktes Zugangsblatt.
              Beim ersten Login legt sie ein eigenes Passwort fest; die Authenticator-App richtet sie ein, wenn die Zwei-Faktor-Anmeldung Pflicht ist –
              sonst freiwillig unter „Mein Konto“.</Meldung>
        ) : null}
        <div className="col-span-4 flex gap-2 flex-wrap items-center">
          {!neu && benutzer && !benutzer.nur_historisch && !benutzer.ausgeblendet_am ? <>
            <Knopf onClick={() => setFrage("kennwort")}>Einmal-Passwort erzeugen</Knopf>
            <Knopf onClick={() => setFrage("2fa")} disabled={!benutzer.zweiter_faktor}>2FA zurücksetzen</Knopf>
            {benutzer.gesperrt_am || !benutzer.is_active
              ? <Knopf icon="schloss" laedt={aktion.isPending && aktion.variables === "entsperren"} onClick={() => aktion.mutate("entsperren")}>Entsperren</Knopf>
              : <Knopf icon="schloss" disabled={benutzer.id === ich.id} title={benutzer.id === ich.id ? "Das eigene Konto kann nicht gesperrt werden." : undefined}
                  onClick={() => setFrage("sperren")}>Sperren</Knopf>}
            <Knopf disabled={benutzer.id === ich.id} title={benutzer.id === ich.id ? "Das eigene Konto kann nicht auf „ohne Login“ gesetzt werden." : undefined}
              onClick={() => setFrage("ohnelogin")}>Auf „ohne Login“ setzen</Knopf>
          </> : null}
          {!neu && historisch ? <Knopf icon="schloss" onClick={() => setLoginRolle("mitarbeiter")}>Login geben</Knopf> : null}
          {neu ? <Knopf className="ml-auto" onClick={() => onGewaehlt(null)}>Abbrechen</Knopf> : null}
          <Knopf type="submit" variante="pri" className={neu ? "" : "ml-auto"} laedt={speichern.isPending}>{neu ? (f.ohne_login ? "Ohne Login anlegen" : "Anlegen und Einmal-Passwort erzeugen") : "Speichern"}</Knopf>
        </div>
      </form>
      <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
        <Icon name="info" />
        <span>EPM verschickt keine E-Mails, der Server braucht dafür keinen Zugang nach außen. Zugangsdaten übergibst du persönlich. Jede Änderung an Benutzern steht im Audit-Log.</span>
      </div>
      <Dialog offen={!!frage} onOffen={(o) => { if (!o) setFrage(""); }} titel={frage ? fragen[frage][0] : ""} breite={480}
        beschreibung={frage ? fragen[frage][1] : undefined}
        fuss={<><Knopf onClick={() => setFrage("")}>Abbrechen</Knopf>
          <Knopf variante={frage === "sperren" || frage === "testdaten" || frage === "ohnelogin" || frage === "ausblenden" ? "dng" : "pri"} laedt={aktion.isPending} onClick={() => frage && aktion.mutate(frage)}>{frage ? fragen[frage][0] : ""}</Knopf></>}>
        <Fehleranzeige fehler={aktion.error} />
      </Dialog>
      <Dialog offen={loginRolle != null} onOffen={(o) => { if (!o) { setLoginRolle(null); loginGeben.reset(); } }} titel="Login geben" breite={480}
        beschreibung={`${name} wird wieder ein Konto zum Arbeiten: Rolle wählen, EPM erzeugt ein Einmal-Passwort für das Zugangsblatt.`}
        fuss={<><Knopf onClick={() => setLoginRolle(null)}>Abbrechen</Knopf>
          <Knopf variante="pri" laedt={loginGeben.isPending} onClick={() => loginGeben.mutate()}>Login geben</Knopf></>}>
        <div className="flex flex-col gap-3">
          <Feld label="Rolle">
            {(p) => <Auswahl {...p} value={loginRolle ?? "mitarbeiter"} onChange={(e) => setLoginRolle(e.target.value)}>
              {Object.entries(ROLLEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Auswahl>}
          </Feld>
          <span className="text-[0.8125rem] gedaempft">Alle bisherigen Einträge der Person bleiben ihr zugeordnet. Mit „Keine Berechtigung“ kann sie sich
            anmelden, sieht aber keine Patientendaten.</span>
          <Fehleranzeige fehler={loginGeben.error} />
        </div>
      </Dialog>
    </Karte>
  );
}

export function Benutzer() {
  const [params] = useSearchParams();
  const [gewaehlt, setGewaehlt] = useState<number | null>(Number(params.get("id")) || null);
  const [neu, setNeu] = useState(params.get("neu") === "1"); // „Benutzer anlegen“ auf der Startseite der Administration
  const [kennwort, setKennwort] = useState<Kennwort | null>(null);
  // ausgeblendete Testbenutzer nur auf Wunsch (Festlegung 03.10.2026)
  const [mitAusgeblendeten, setMitAusgeblendeten] = useState(false);
  const liste = useQuery({
    queryKey: ["benutzer", { ausgeblendete: mitAusgeblendeten }],
    queryFn: () => alle<BenutzerTyp>(`benutzer/?ordering=last_name${mitAusgeblendeten ? "&ausgeblendete=1" : ""}`),
  });
  const benutzer = liste.data ?? [];
  const qc = useQueryClient();
  const melden = useHinweis();
  const [alleAusblenden, setAlleAusblenden] = useState(false);
  const ich = useIch();
  const sichtbareTester = benutzer.filter((b) => b.ist_test && !b.ausgeblendet_am && b.id !== ich.id);
  const ausblenden = useMutation({
    mutationFn: () => api<{ ausgeblendet: number }>("benutzer/testbenutzer-ausblenden/", { method: "POST" }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ["benutzer"] });
      setAlleAusblenden(false);
      melden(`${r.ausgeblendet} Testbenutzer ausgeblendet.`);
    },
  });
  const { hash } = useLocation();
  useEffect(() => {
    if (hash === "#anmeldung" && liste.data) document.getElementById("anmeldung")?.scrollIntoView({ block: "start" });
  }, [hash, liste.data]);
  const aktiv = neu ? null : benutzer.find((b) => b.id === gewaehlt) ?? benutzer[0] ?? null;
  // unter 1280 px steht das Formular unter der Liste: nach dem Antippen dorthin scrollen (Fehlermeldung 11.10.2026:
  // „am Telefon muss ich ganz nach unten scrollen“)
  const waehlen = (id: number) => { setNeu(false); setGewaehlt(id); detailZeigen("benutzer-detail"); };
  return (
    <Seite pfad={[{ text: "Administration" }, { text: "Benutzer" }]}>
      <Seitenkopf titel="Benutzer" unter="Wer darf was im EPM. Benutzer werden nie gelöscht, nur gesperrt, damit ihre Einträge zuordenbar bleiben."
        rechts={<>
          <label className="flex items-center gap-1.5 text-sm cursor-pointer">
            <input type="checkbox" checked={mitAusgeblendeten} onChange={(e) => setMitAusgeblendeten(e.target.checked)} />Ausgeblendete zeigen
          </label>
          {sichtbareTester.length ? <Knopf onClick={() => { ausblenden.reset(); setAlleAusblenden(true); }}>Alle Testbenutzer ausblenden</Knopf> : null}
          <Knopf variante="pri" icon="plus" onClick={() => { setNeu(true); detailZeigen("benutzer-detail"); }}>Benutzer anlegen</Knopf></>} />
      <Dialog offen={alleAusblenden} onOffen={setAlleAusblenden} titel="Alle Testbenutzer ausblenden" breite={520}
        beschreibung="Alle Konten mit Testzugang werden gesperrt, ihre Anmeldungen beendet, und sie erscheinen in keiner Liste mehr. Nichts wird gelöscht; einzeln wieder einblendbar."
        fuss={<><Knopf onClick={() => setAlleAusblenden(false)}>Abbrechen</Knopf>
          <Knopf variante="dng" laedt={ausblenden.isPending} onClick={() => ausblenden.mutate()}>{sichtbareTester.length} ausblenden</Knopf></>}>
        <div className="flex flex-col gap-2 text-sm">
          <span>{sichtbareTester.map((b) => b.anzeigename).join(", ")}</span>
          <Fehleranzeige fehler={ausblenden.error} />
        </div>
      </Dialog>
      {/* unter 1280 px: Liste, dann das gewählte Konto, dann Anmeldung und Rechte (vorher stand das Formular ganz unten) */}
      <div className="stapel grid grid-cols-1 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] gap-5 items-start">
        <div className="stapel flex flex-col gap-5 min-w-0 max-xl:contents">
          <Karte className="overflow-x-auto max-xl:order-1">
            {liste.isLoading ? <Laden /> : (
              <table className="tabelle" data-testid="benutzerliste">
                <thead><tr><th className="th w-12"><span className="sr-only">Kürzel</span></th><th className="th">Name</th><th className="th">Rolle</th><th className="th">Anmeldung</th><th className="th">Status</th></tr></thead>
                <tbody>
                  {benutzer.map((b) => {
                    const z = zustand(b);
                    return (
                      <tr key={b.id} className={cx("cursor-pointer", aktiv?.id === b.id && "gewaehlt")} onClick={() => waehlen(b.id)}>
                        <td className="td"><span className="w-8 h-8 rounded-full bg-akzent-weich text-akzent-text inline-flex items-center justify-center text-xs font-semibold">{b.kuerzel || "—"}</span></td>
                        <td className="td">
                          <button type="button" className="bg-transparent border-0 p-0 font-medium text-akzent-text cursor-pointer text-left"
                            onClick={(e) => { e.stopPropagation(); waehlen(b.id); }}>{b.anzeigename}</button>
                          <br /><span className="text-[0.8125rem] gedaempft">{b.funktion ? `${b.funktion} · ` : ""}<span className="num">{b.username}</span></span>
                        </td>
                        <td className="td"><RollenChips b={b} />{b.ist_test ? <><br /><Chip art="warn" className="mt-1">Testbenutzer</Chip></> : null}</td>
                        <td className="td text-[0.8125rem]">{b.last_login ? relativ(b.last_login, true) : "noch nie"}<br /><span className="gedaempft">2FA: {b.nur_historisch ? "—" : b.zweiter_faktor ? "aktiv" : b.zweiter_faktor_pflicht ? "nicht eingerichtet (Pflicht)" : "nicht eingerichtet"}</span></td>
                        <td className="td"><Chip art={z.art}>{z.text}</Chip></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
            <Fehleranzeige fehler={liste.error} />
          </Karte>
          <div className="stapel flex flex-col gap-5 min-w-0 max-xl:order-3">
            <AnmeldungKarte onBenutzer={waehlen} />
            <RechteMatrix />
          </div>
        </div>
        {aktiv || neu ? <div className="min-w-0 max-xl:order-2">
          <Detail benutzer={aktiv} neu={neu} onGewaehlt={(id) => { setNeu(false); setGewaehlt(id); }}
            kennwortAnzeige={kennwort} setKennwortAnzeige={setKennwort} />
        </div> : null}
      </div>
    </Seite>
  );
}
