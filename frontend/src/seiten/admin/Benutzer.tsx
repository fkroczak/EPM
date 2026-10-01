/** Entwurf 17 · Benutzer: anlegen, ändern, sperren, Einmal-Kennwort, 2FA zurücksetzen; Rechte je Gruppe einstellbar. */
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, alle, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import { relativ, zeitpunkt } from "@/lib/format";
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
};
type Formular = { titel: string; first_name: string; last_name: string; kuerzel: string; funktion: string; username: string; rolle: string };
const TITEL = ["", "Dr.", "Dr. med.", "Prof. Dr.", "Prof. Dr. med.", "Dipl.-Oec. troph."];
const LEER: Formular = { titel: "", first_name: "", last_name: "", kuerzel: "", funktion: "", username: "", rolle: "mitarbeiter" };

function anzeige(f: Formular) {
  const name = [f.titel, f.first_name ? `${f.first_name.trim()[0]}.` : "", f.last_name].filter(Boolean).join(" ");
  return name.trim() || "wird aus Titel, Vorname und Nachname gebildet";
}

function zustand(b: BenutzerTyp): { text: string; art: "ok" | "fehler" | "warn" | "neutral" } {
  if (b.nur_historisch) return { text: "ohne Login", art: "neutral" };
  if (b.gesperrt_am || !b.is_active) return { text: "gesperrt", art: "fehler" };
  if (b.muss_kennwort_aendern || !b.zweiter_faktor) return { text: "Einrichtung offen", art: "warn" };
  return { text: "aktiv", art: "ok" };
}

function Kennwortanzeige({ kennwort, gueltig, name }: { kennwort: string; gueltig: string | null; name: string }) {
  return (
    <div className="meldung info flex flex-col gap-2" data-testid="einmal-kennwort">
      <span className="text-[0.8125rem] font-medium">Einmal-Kennwort</span>
      <span className="num text-xl font-semibold tracking-[.08em]">{kennwort}</span>
      <span className="text-[0.8125rem] leading-normal">
        {gueltig ? `Gültig bis ${zeitpunkt(gueltig)}. ` : ""}Persönlich übergeben. Beim ersten Login legt {name} ein eigenes Passwort fest und
        richtet die Authenticator-App ein. Das Kennwort wird nur jetzt angezeigt.
      </span>
      <div><Knopf klein icon="dokument" disabled title="folgt mit der PDF-Erzeugung (F55)">Zugangsblatt drucken</Knopf></div>
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
  const geaendert = d.rollen.reduce((n, r) => n + d.rechte.filter((x) => m[r.code][x.code] !== d.matrix[r.code][x.code]).length, 0);
  const standard = () => setM(Object.fromEntries(d.rollen.map((r) => [r.code, Object.fromEntries(d.rechte.map((x) => [x.code, d.standard[r.code].includes(x.code) || fest.has(`${r.code}.${x.code}`)]))])));
  return (
    <Karte className="px-5 py-[18px] flex flex-col gap-3" data-testid="rechte">
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-1">
          <h2 className="lbl m-0">Was die Rollen dürfen</h2>
          <span className="text-[0.8125rem] gedaempft leading-normal max-w-[70ch]">Je Gruppe einstellbar. Mediziner sind dem Admin gleichgestellt, außer bei Benutzern,
            dem Wiederöffnen abgeschlossener Akten, Sicherungen und Testdaten. Testbenutzer erhalten nie Rechte über Testpatienten hinaus.</span>
        </div>
        <div className="flex gap-2">
          <Knopf klein onClick={standard}>Standard</Knopf>
          <Knopf klein variante="pri" disabled={!geaendert} laedt={speichern.isPending} onClick={() => speichern.mutate()}>
            Speichern{geaendert ? ` (${geaendert})` : ""}
          </Knopf>
        </div>
      </div>
      <table className="tabelle">
        <thead><tr><th className="th" />{d.rollen.map((r) => <th key={r.code} className="th text-center">{r.name}</th>)}</tr></thead>
        <tbody>
          {d.rechte.map((x) => (
            <tr key={x.code}>
              <td className="td"><span className="text-sm">{x.name}</span>{x.beschreibung ? <><br /><span className="text-xs gedaempft">{x.beschreibung}</span></> : null}</td>
              {d.rollen.map((r) => {
                const istFest = fest.has(`${r.code}.${x.code}`);
                const anders = m[r.code][x.code] !== d.matrix[r.code][x.code];
                return (
                  <td key={r.code} className={cx("td text-center", anders && "bg-warn-bg")}>
                    <input type="checkbox" aria-label={`${r.name}: ${x.name}`} checked={m[r.code][x.code]} disabled={istFest}
                      title={istFest ? "festes Recht, damit sich die Administration nicht aussperrt" : undefined}
                      onChange={(e) => setM({ ...m, [r.code]: { ...m[r.code], [x.code]: e.target.checked } })} />
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

type Kennwort = { id: number; kennwort: string; gueltig: string | null };

function Detail({ benutzer, neu, onGewaehlt, kennwortAnzeige, setKennwortAnzeige }: {
  benutzer: BenutzerTyp | null; neu: boolean; onGewaehlt: (id: number | null) => void;
  kennwortAnzeige: Kennwort | null; setKennwortAnzeige: (k: Kennwort | null) => void;
}) {
  const ich = useIch();
  const { darf } = useAuth();
  const qc = useQueryClient();
  const melden = useHinweis();
  const start = (): Formular => benutzer ? {
    titel: benutzer.titel, first_name: benutzer.first_name, last_name: benutzer.last_name, kuerzel: benutzer.kuerzel ?? "",
    funktion: benutzer.funktion, username: benutzer.username, rolle: benutzer.rolle,
  } : { ...LEER };
  const [f, setF] = useState<Formular>(start);
  const kennwort = kennwortAnzeige && benutzer && kennwortAnzeige.id === benutzer.id ? kennwortAnzeige : null;
  const [frage, setFrage] = useState<"" | "kennwort" | "2fa" | "sperren" | "testdaten">("");
  useEffect(() => { setF(start()); }, [benutzer?.id, neu]); // eslint-disable-line react-hooks/exhaustive-deps
  const neuLaden = () => void qc.invalidateQueries({ queryKey: ["benutzer"] });
  const speichern = useMutation({
    mutationFn: () => neu
      ? api<BenutzerTyp & { einmal_kennwort?: string }>("benutzer/", { body: f })
      : api<BenutzerTyp & { einmal_kennwort?: string }>(`benutzer/${benutzer!.id}/`, { method: "PATCH", body: f }),
    onSuccess: (b) => {
      neuLaden();
      if (neu) {
        setKennwortAnzeige({ id: b.id, kennwort: b.einmal_kennwort ?? "", gueltig: b.einmal_kennwort_gueltig_bis });
        onGewaehlt(b.id);
        melden("Benutzer angelegt.");
      } else melden("Benutzer gespeichert.");
    },
  });
  const aktion = useMutation({
    mutationFn: (art: "kennwort" | "2fa" | "sperren" | "entsperren" | "testdaten") => {
      if (art === "testdaten") return api<Record<string, number>>("testdaten/zuruecksetzen/", { method: "POST" });
      const pfad = { kennwort: "einmal-kennwort", "2fa": "2fa-zuruecksetzen", sperren: "sperren", entsperren: "entsperren" }[art];
      return api<Record<string, unknown>>(`benutzer/${benutzer!.id}/${pfad}/`, { method: "POST" });
    },
    onSuccess: (r, art) => {
      neuLaden();
      setFrage("");
      if (art === "kennwort" || art === "2fa") setKennwortAnzeige({ id: benutzer!.id, kennwort: String(r.einmal_kennwort), gueltig: String(r.gueltig_bis ?? "") || null });
      if (art === "testdaten") void qc.invalidateQueries({});
      melden({ kennwort: "Neues Einmal-Kennwort erzeugt.", "2fa": "2FA zurückgesetzt, neues Einmal-Kennwort erzeugt.", sperren: "Benutzer gesperrt.",
        entsperren: "Benutzer entsperrt.", testdaten: `Testdaten zurückgesetzt (${r.geloescht ?? 0} gelöscht, ${r.angelegt ?? 0} angelegt).` }[art]);
    },
  });
  const fehler: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const set = (k: keyof Formular) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });
  const z = benutzer ? zustand(benutzer) : null;
  const name = benutzer ? benutzer.anzeigename : "die Person";
  const fragen = {
    kennwort: ["Einmal-Kennwort erzeugen", "Das bisherige Kennwort gilt danach nicht mehr, alle Anmeldungen der Person werden beendet."],
    "2fa": ["2FA zurücksetzen", "Authenticator und Notfall-Codes werden gelöscht. Mit dem neuen Einmal-Kennwort richtet die Person die App neu ein."],
    sperren: ["Benutzer sperren", "Die Person kann sich nicht mehr anmelden, alle Sitzungen werden beendet. Einträge bleiben zugeordnet."],
    testdaten: ["Testdaten zurücksetzen", "Alle Testpatienten (Nr. ab 9001) werden gelöscht und die Musterdaten neu angelegt. Echte Patienten bleiben unberührt."],
  } as const;
  return (
    <Karte className="px-5 py-[18px] flex flex-col gap-4 min-w-0" data-testid="benutzer-detail">
      <div className="flex items-center gap-2.5 flex-wrap">
        <h2 className="m-0 text-lg font-semibold">{neu ? "Neuer Benutzer" : name}</h2>
        {z ? <Chip art={z.art}>{z.art === "ok" ? <Icon name="haken" /> : z.art === "fehler" ? <Icon name="schloss" /> : null}{z.text}</Chip> : null}
      </div>
      {benutzer?.gesperrt_am ? <Meldung art="fehler">Gesperrt am {zeitpunkt(benutzer.gesperrt_am)}{benutzer.sperrgrund ? ` · ${benutzer.sperrgrund}` : ""}.</Meldung> : null}
      {benutzer?.nur_historisch ? <Meldung>Aus dem Altsystem übernommen, damit alte Einträge einer Person zugeordnet bleiben. Kann sich nicht anmelden.</Meldung> : null}
      {kennwort ? <Kennwortanzeige kennwort={kennwort.kennwort} gueltig={kennwort.gueltig} name={name} /> : null}
      {benutzer?.ist_test ? (
        <div className="meldung warn flex flex-col gap-2 text-[0.8125rem]">
          <span><strong>Testbenutzer:</strong> sieht und bearbeitet ausschließlich Testpatienten, nie echte Patientendaten. Oben erscheint dauerhaft ein
            Hinweis „Testzugang“. Für Schulungen und zum Durchklicken nach jedem Update.</span>
          {darf("testdaten_zuruecksetzen") ? <div><Knopf klein onClick={() => setFrage("testdaten")}>Testdaten auf Ausgangsstand zurücksetzen</Knopf></div> : null}
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
        <Feld label="Rolle" fehler={fehler.rolle}>
          {(p) => <Auswahl {...p} value={f.rolle} onChange={set("rolle")}>{Object.entries(ROLLEN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Auswahl>}
        </Feld>
        <span className="col-span-4 text-[0.8125rem] gedaempft">Anzeige in der Akte: <span className="text-tinte font-medium">{anzeige(f)}</span></span>
        {speichern.error && !Object.keys(fehler).length ? <Meldung art="fehler" className="col-span-4">{speichern.error.message}</Meldung> : null}
        {neu ? (
          <Meldung className="col-span-4">Nach dem Anlegen erzeugt EPM ein Einmal-Kennwort. Du gibst es der Person persönlich oder als ausgedrucktes Zugangsblatt.
            Beim ersten Login legt sie ein eigenes Passwort fest und richtet die Authenticator-App ein.</Meldung>
        ) : null}
        <div className="col-span-4 flex gap-2 flex-wrap items-center">
          {!neu && benutzer && !benutzer.nur_historisch ? <>
            <Knopf onClick={() => setFrage("kennwort")}>Einmal-Kennwort erzeugen</Knopf>
            <Knopf onClick={() => setFrage("2fa")} disabled={!benutzer.zweiter_faktor}>2FA zurücksetzen</Knopf>
            {benutzer.gesperrt_am || !benutzer.is_active
              ? <Knopf icon="schloss" laedt={aktion.isPending && aktion.variables === "entsperren"} onClick={() => aktion.mutate("entsperren")}>Entsperren</Knopf>
              : <Knopf icon="schloss" disabled={benutzer.id === ich.id} title={benutzer.id === ich.id ? "Das eigene Konto kann nicht gesperrt werden." : undefined}
                  onClick={() => setFrage("sperren")}>Sperren</Knopf>}
          </> : null}
          {neu ? <Knopf className="ml-auto" onClick={() => onGewaehlt(null)}>Abbrechen</Knopf> : null}
          <Knopf type="submit" variante="pri" className={neu ? "" : "ml-auto"} laedt={speichern.isPending}>{neu ? "Anlegen und Einmal-Kennwort erzeugen" : "Speichern"}</Knopf>
        </div>
      </form>
      <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
        <Icon name="info" />
        <span>EPM verschickt keine E-Mails, der Server braucht dafür keinen Zugang nach außen. Zugangsdaten übergibst du persönlich. Jede Änderung an Benutzern steht im Audit-Log.</span>
      </div>
      <Dialog offen={!!frage} onOffen={(o) => { if (!o) setFrage(""); }} titel={frage ? fragen[frage][0] : ""} breite={480}
        beschreibung={frage ? fragen[frage][1] : undefined}
        fuss={<><Knopf onClick={() => setFrage("")}>Abbrechen</Knopf>
          <Knopf variante={frage === "sperren" || frage === "testdaten" ? "dng" : "pri"} laedt={aktion.isPending} onClick={() => frage && aktion.mutate(frage)}>{frage ? fragen[frage][0] : ""}</Knopf></>}>
        <Fehleranzeige fehler={aktion.error} />
      </Dialog>
    </Karte>
  );
}

export function Benutzer() {
  const [params] = useSearchParams();
  const [gewaehlt, setGewaehlt] = useState<number | null>(Number(params.get("id")) || null);
  const [neu, setNeu] = useState(false);
  const [kennwort, setKennwort] = useState<Kennwort | null>(null);
  const liste = useQuery({ queryKey: ["benutzer"], queryFn: () => alle<BenutzerTyp>("benutzer/?ordering=last_name") });
  const benutzer = liste.data ?? [];
  const aktiv = neu ? null : benutzer.find((b) => b.id === gewaehlt) ?? benutzer[0] ?? null;
  return (
    <Seite pfad={[{ text: "Administration" }, { text: "Benutzer" }]}>
      <Seitenkopf titel="Benutzer" unter="Wer darf was im EPM. Benutzer werden nie gelöscht, nur gesperrt, damit ihre Einträge zuordenbar bleiben."
        rechts={<Knopf variante="pri" icon="plus" onClick={() => setNeu(true)}>Benutzer anlegen</Knopf>} />
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] gap-5 items-start">
        <div className="flex flex-col gap-5 min-w-0">
          <Karte className="overflow-hidden">
            {liste.isLoading ? <Laden /> : (
              <table className="tabelle" data-testid="benutzerliste">
                <thead><tr><th className="th w-12" /><th className="th">Name</th><th className="th">Rolle</th><th className="th">Anmeldung</th><th className="th">Status</th></tr></thead>
                <tbody>
                  {benutzer.map((b) => {
                    const z = zustand(b);
                    return (
                      <tr key={b.id} className={cx("cursor-pointer", aktiv?.id === b.id && "gewaehlt")} onClick={() => { setNeu(false); setGewaehlt(b.id); }}>
                        <td className="td"><span className="w-8 h-8 rounded-full bg-akzent-weich text-akzent-text inline-flex items-center justify-center text-xs font-semibold">{b.kuerzel || "—"}</span></td>
                        <td className="td">
                          <button type="button" className="bg-transparent border-0 p-0 font-medium text-akzent-text cursor-pointer text-left"
                            onClick={(e) => { e.stopPropagation(); setNeu(false); setGewaehlt(b.id); }}>{b.anzeigename}</button>
                          <br /><span className="text-[0.8125rem] gedaempft">{b.funktion ? `${b.funktion} · ` : ""}<span className="num">{b.username}</span></span>
                        </td>
                        <td className="td"><Chip art="akzent">{ROLLEN[b.rolle] ?? b.rolle}</Chip>{b.ist_test ? <><br /><Chip art="warn" className="mt-1">Testbenutzer</Chip></> : null}</td>
                        <td className="td text-[0.8125rem]">{b.last_login ? relativ(b.last_login, true) : "noch nie"}<br /><span className="gedaempft">2FA: {b.nur_historisch ? "—" : b.zweiter_faktor ? "aktiv" : "nicht eingerichtet"}</span></td>
                        <td className="td"><Chip art={z.art}>{z.text}</Chip></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
            <Fehleranzeige fehler={liste.error} />
          </Karte>
          <RechteMatrix />
        </div>
        {aktiv || neu ? <Detail benutzer={aktiv} neu={neu} onGewaehlt={(id) => { setNeu(false); setGewaehlt(id); }}
          kennwortAnzeige={kennwort} setKennwortAnzeige={setKennwort} /> : null}
      </div>
    </Seite>
  );
}
