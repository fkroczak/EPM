/** Entwurf 12 · Neuer Patient: Grunddaten, Doppelungsprüfung, Gewicht bei Aufnahme als erste Messung. */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAerzteListe, useAuswahl, useVersorgerListe } from "@/lib/daten";
import { datum, eingabeDatum, eingabeZahl, heuteIso, nummer } from "@/lib/format";
import { GESCHLECHTER, VERSICHERUNGSARTEN } from "@/lib/typen";
import type { Patient, PatientZeile } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Feld, Karte, Knopf, KnopfLink, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { NeuerArztDialog, NeuerVersorgerDialog } from "@/components/SchnellAnlegen";

type Formular = {
  nachname: string; vorname: string; geschlecht: string; geburtsdatum: string; groesse: string; gewicht: string;
  gemessen_am: string; strasse: string; plz: string; ort: string; telefon: string; telefon2: string; email: string;
  versicherungsart: string; krankenkasse: string; versichertennummer: string;
  versorger: string; ansprechpartner: string; katheter: string; nickelallergie: string; hausarzt: string;
  ueberweisung_durch: string; diagnose: string;
};

const LEER: Formular = {
  nachname: "", vorname: "", geschlecht: "", geburtsdatum: "", groesse: "", gewicht: "", gemessen_am: "",
  strasse: "", plz: "", ort: "", telefon: "", telefon2: "", email: "",
  versicherungsart: "", krankenkasse: "", versichertennummer: "", versorger: "", ansprechpartner: "", katheter: "",
  nickelallergie: "unbekannt", hausarzt: "", ueberweisung_durch: "", diagnose: "",
};

/** Wert der Auswahl „kein“ (bewusst keiner) bei Versorger und Katheter */
const KEIN = "kein";

/** Klartext der Diagnose als einfaches HTML für das Rich-Text-Feld der Akte */
function alsHtml(text: string): string {
  const esc = (t: string) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return text.trim() ? text.trim().split(/\n{2,}/).map((a) => `<p>${esc(a).replace(/\n/g, "<br>")}</p>`).join("") : "";
}

function Einheit({ children, einheit }: { children: ReactNode; einheit: string }) {
  return (
    <span className="relative block">
      {children}
      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[0.8125rem] gedaempft pointer-events-none">{einheit}</span>
    </span>
  );
}

function Abschnitt({ titel, children }: { titel: string; children: ReactNode }) {
  return (
    <Karte className="px-5 py-[18px] flex flex-col gap-3.5">
      <h2 className="lbl m-0">{titel}</h2>
      {/* Formulare in Stufen (S16): 2 breite Felder je Zeile, ab 1920 px 3, ab 2560 px 4 */}
      <div className="grid grid-cols-2 md:grid-cols-4 fhd:grid-cols-6 qhd:grid-cols-8 gap-x-3 md:gap-x-4 gap-y-3.5 items-start">{children}</div>
    </Karte>
  );
}

export function PatientNeu() {
  const [f, setF] = useState<Formular>({ ...LEER, gemessen_am: datum(heuteIso()) });
  const [andere, setAndere] = useState<number[]>([]);
  // Arzt/Versorger anlegen, ohne die Seite zu verlassen (Vorschlag „Weniger Wege“, 08.10.2026)
  const [schnell, setSchnell] = useState<"" | "arzt" | "versorger">("");
  const [lokal, setLokal] = useState<Feldfehler>({});
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { darf } = useAuth();
  const setze = (feld: keyof Formular) => (e: { target: { value: string } }) => setF((alt) => ({ ...alt, [feld]: e.target.value }));

  // Testpatient (Fehlerliste 02.10.2026, 6.4): Mitarbeiter und Mediziner können beim Anlegen einen Testpatienten wählen –
  // z. B. um Infusionspläne auszuprobieren. Testbenutzer und Admins legen immer Testpatienten an (testpatient_fest).
  const [test, setTest] = useState(false);
  const naechste = useQuery({
    queryKey: ["patienten", "naechste-nummer", test],
    queryFn: () => api<{ nummer: number; testpatient: boolean; testpatient_fest?: boolean }>(`patienten/naechste-nummer/${test ? "?testpatient=1" : ""}`),
  });
  const versorger = useVersorgerListe();
  const katheter = useAuswahl("katheter");
  const aerzte = useAerzteListe();
  const gewaehlt = (versorger.data ?? []).find((v) => String(v.id) === f.versorger);

  // Doppelungsprüfung: gleiches Geburtsdatum und ähnlicher Name
  const geb = eingabeDatum(f.geburtsdatum);
  const [pruefung, setPruefung] = useState({ geb: "", nachname: "", vorname: "" });
  useEffect(() => {
    const t = window.setTimeout(() => setPruefung({ geb: geb ?? "", nachname: f.nachname.trim(), vorname: f.vorname.trim() }), 350);
    return () => window.clearTimeout(t);
  }, [geb, f.nachname, f.vorname]);
  const doppelte = useQuery({
    queryKey: ["patienten", "doppelte", pruefung],
    queryFn: () => api<PatientZeile[]>(`patienten/doppelte/${abfrage({ geburtsdatum: pruefung.geb, nachname: pruefung.nachname, vorname: pruefung.vorname })}`),
    enabled: !!pruefung.geb && (pruefung.nachname.length >= 2 || pruefung.vorname.length >= 2),
  });
  const aehnlich = (doppelte.data ?? []).filter((p) => !andere.includes(p.id));

  const anlegen = useMutation({
    mutationFn: (daten: Record<string, unknown>) => api<Patient>("patienten/", { body: daten }),
    onSuccess: (p) => {
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      navigate(`/patienten/${p.id}`);
    },
  });

  const absenden = () => {
    const fehler: Feldfehler = {};
    if (!f.nachname.trim()) fehler.nachname = "Bitte Nachnamen eingeben.";
    if (!f.vorname.trim()) fehler.vorname = "Bitte Vornamen eingeben.";
    if (!geb) fehler.geburtsdatum = f.geburtsdatum.trim() ? "Bitte als TT.MM.JJJJ eingeben." : "Bitte Geburtsdatum eingeben.";
    const groesse = eingabeZahl(f.groesse);
    if (groesse === "ungueltig") fehler.groesse_cm = "Bitte eine Zahl eingeben, z. B. 168.";
    const gewicht = eingabeZahl(f.gewicht);
    if (gewicht === "ungueltig") fehler.aufnahme_gewicht_kg = "Bitte eine Zahl eingeben, z. B. 54,6.";
    const gemessen = f.gemessen_am.trim() ? eingabeDatum(f.gemessen_am) : null;
    if (gewicht && f.gemessen_am.trim() && !gemessen) fehler.aufnahme_gemessen_am = "Bitte als TT.MM.JJJJ eingeben.";
    setLokal(fehler);
    if (Object.keys(fehler).length) return;
    anlegen.mutate({
      nachname: f.nachname.trim(),
      vorname: f.vorname.trim(),
      geschlecht: f.geschlecht,
      geburtsdatum: geb,
      groesse_cm: groesse,
      strasse: f.strasse.trim(),
      plz: f.plz.trim(),
      ort: f.ort.trim(),
      telefon: f.telefon.trim(),
      telefon2: f.telefon2.trim(),
      email: f.email.trim(),
      versicherungsart: f.versicherungsart,
      krankenkasse: f.krankenkasse.trim(),
      versichertennummer: f.versichertennummer.trim(),
      // „kein“ = bewusst keiner, leer = noch nicht erfasst (Festlegung 01.10.2026)
      versorger: f.versorger && f.versorger !== KEIN ? Number(f.versorger) : null,
      kein_versorger: f.versorger === KEIN,
      ansprechpartner: f.ansprechpartner && f.versorger !== KEIN ? Number(f.ansprechpartner) : null,
      katheter: f.katheter && f.katheter !== KEIN ? Number(f.katheter) : null,
      kein_katheter: f.katheter === KEIN,
      nickelallergie: f.nickelallergie,
      // Hausarzt aus der gemeinsamen Ärzteliste (wird als Zuordnung „Hausarzt“ gespeichert)
      ...(f.hausarzt ? { aufnahme_hausarzt: Number(f.hausarzt) } : {}),
      ueberweisung_durch: f.ueberweisung_durch.trim(),
      diagnose: alsHtml(f.diagnose),
      ...(gewicht ? { aufnahme_gewicht_kg: gewicht, aufnahme_gemessen_am: gemessen ?? heuteIso() } : {}),
      ...(test ? { testpatient: true } : {}),
    });
  };

  const server: Feldfehler = anlegen.error instanceof ApiFehler ? anlegen.error.felder : {};
  const e: Feldfehler = { ...server, ...lokal };
  const ohneFeld = anlegen.error && !Object.keys(server).length;

  // ohne Recht gibt es diese Seite nicht (Festlegung 01.10.2026: Nicht Erlaubtes wird nicht gezeigt)
  if (!darf("akten_bearbeiten")) return <Navigate to="/patienten" replace />;

  return (
    <Seite pfad={[{ text: "Patienten", zu: "/patienten" }, { text: "Neu" }]}>
      <form className="stapel flex flex-col gap-5" noValidate onSubmit={(ev) => { ev.preventDefault(); absenden(); }}>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div className="flex flex-col gap-1">
            <span className="text-sm gedaempft"><Link to="/patienten" className="no-underline">Patienten</Link> / Neu</span>
            <h1 className="m-0 text-[1.625rem] font-semibold">Neuer Patient</h1>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[0.84rem] gedaempft">
              Nr. <span className="num text-tinte font-semibold" data-testid="naechste-nummer">{naechste.data ? nummer(naechste.data.nummer) : "…"}</span> wird automatisch vergeben
            </span>
            {naechste.data?.testpatient_fest ? <Chip art="warn" title="Testbenutzer und Admins legen nur Testpatienten an">wird Testpatient</Chip>
              : !darf("testdaten_sehen") ? null : (
              <label className="flex items-center gap-1.5 text-sm cursor-pointer" title="Zum Ausprobieren, z. B. für Infusionspläne: eigene Nummern ab 9001, erscheint nicht in Auswertungen echter Patienten">
                <input type="checkbox" checked={test} onChange={(ev) => setTest(ev.target.checked)} />
                als Testpatient anlegen
              </label>
            )}
            {test && !naechste.data?.testpatient_fest ? <Chip art="warn">wird Testpatient</Chip> : null}
            <KnopfLink to="/patienten">Abbrechen</KnopfLink>
            <Knopf type="submit" variante="pri" laedt={anlegen.isPending}>Anlegen und Akte öffnen</Knopf>
          </div>
        </div>
        {ohneFeld ? <Meldung art="fehler">{anlegen.error?.message}</Meldung> : null}

        <div className="stapel grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_340px] gap-5 items-start">
          <div className="flex flex-col gap-4 min-w-0">
            <Abschnitt titel="Person">
              <Feld label="Nachname" pflicht className="col-span-2" fehler={e.nachname}>
                {(p) => <Eingabe {...p} value={f.nachname} onChange={setze("nachname")} autoComplete="off" maxLength={100} autoFocus />}
              </Feld>
              <Feld label="Vorname" pflicht fehler={e.vorname}>
                {(p) => <Eingabe {...p} value={f.vorname} onChange={setze("vorname")} autoComplete="off" maxLength={100} />}
              </Feld>
              <Feld label="Geschlecht" fehler={e.geschlecht}>
                {(p) => (
                  <Auswahl {...p} value={f.geschlecht} onChange={setze("geschlecht")}>
                    {["w", "m", "d", ""].map((k) => <option key={k} value={k}>{GESCHLECHTER[k]}</option>)}
                  </Auswahl>
                )}
              </Feld>
              <Feld label="Geburtsdatum" pflicht fehler={e.geburtsdatum}>
                {(p) => <Eingabe {...p} className="num" placeholder="TT.MM.JJJJ" value={f.geburtsdatum} onChange={setze("geburtsdatum")} inputMode="numeric" />}
              </Feld>
              <Feld label="Größe" fehler={e.groesse_cm}>
                {(p) => <Einheit einheit="cm"><Eingabe {...p} className="num pr-10" value={f.groesse} onChange={setze("groesse")} inputMode="decimal" /></Einheit>}
              </Feld>
              <Feld label="Gewicht bei Aufnahme" fehler={e.aufnahme_gewicht_kg}>
                {(p) => <Einheit einheit="kg"><Eingabe {...p} className="num pr-10" value={f.gewicht} onChange={setze("gewicht")} inputMode="decimal" /></Einheit>}
              </Feld>
              <Feld label="gemessen am" fehler={e.aufnahme_gemessen_am}>
                {(p) => <Eingabe {...p} className="num" placeholder="TT.MM.JJJJ" value={f.gemessen_am} onChange={setze("gemessen_am")} />}
              </Feld>
            </Abschnitt>

            <Abschnitt titel="Anschrift und Erreichbarkeit">
              <Feld label="Straße und Hausnummer" className="col-span-2" fehler={e.strasse}>
                {(p) => <Eingabe {...p} value={f.strasse} onChange={setze("strasse")} autoComplete="off" />}
              </Feld>
              <Feld label="PLZ" fehler={e.plz}>
                {(p) => <Eingabe {...p} className="num" value={f.plz} onChange={setze("plz")} inputMode="numeric" maxLength={10} />}
              </Feld>
              <Feld label="Ort" fehler={e.ort}>
                {(p) => <Eingabe {...p} value={f.ort} onChange={setze("ort")} autoComplete="off" />}
              </Feld>
              <Feld label="Telefon" className="col-span-2" fehler={e.telefon}>
                {(p) => <Eingabe {...p} className="num" type="tel" value={f.telefon} onChange={setze("telefon")} autoComplete="off" />}
              </Feld>
              <Feld label="Telefon 2" className="col-span-2" fehler={e.telefon2}>
                {(p) => <Eingabe {...p} className="num" type="tel" value={f.telefon2} onChange={setze("telefon2")} autoComplete="off" />}
              </Feld>
              <Feld label="E-Mail" className="col-span-2" fehler={e.email}>
                {(p) => <Eingabe {...p} type="email" value={f.email} onChange={setze("email")} autoComplete="off" />}
              </Feld>
              {/* Versichertendaten (F118) */}
              <Feld label="Versicherungsart" className="col-span-2" fehler={e.versicherungsart}>
                {(p) => (
                  <Auswahl {...p} value={f.versicherungsart} onChange={setze("versicherungsart")}>
                    {Object.entries(VERSICHERUNGSARTEN).map(([k, text]) => <option key={k} value={k}>{text}</option>)}
                  </Auswahl>
                )}
              </Feld>
              <Feld label="Versicherung" className="col-span-2" fehler={e.krankenkasse}>
                {(p) => <Eingabe {...p} value={f.krankenkasse} onChange={setze("krankenkasse")} autoComplete="off" maxLength={100} />}
              </Feld>
              <Feld label="Versichertennummer" className="col-span-2" fehler={e.versichertennummer}>
                {(p) => <Eingabe {...p} className="num" value={f.versichertennummer} onChange={setze("versichertennummer")} autoComplete="off" maxLength={50} />}
              </Feld>
            </Abschnitt>

            <Abschnitt titel="Betreuung">
              <div className="col-span-2 relative">
                {darf("versorger_pflegen") ? (
                  <button type="button" className="absolute right-0 top-0 text-[0.8125rem] bg-transparent border-0 p-0 text-akzent-text cursor-pointer hover:underline" aria-label="Neuen Versorger anlegen"
                    onClick={() => setSchnell("versorger")}>Neu anlegen</button>
                ) : null}
                <Feld label="Versorger" fehler={e.versorger}>
                  {(p) => (
                    <Auswahl {...p} value={f.versorger} onChange={(ev) => setF((alt) => ({ ...alt, versorger: ev.target.value, ansprechpartner: "" }))}>
                      <option value="">— nicht erfasst —</option>
                      <option value={KEIN}>kein Versorger</option>
                      {(versorger.data ?? []).filter((v) => v.aktiv).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                    </Auswahl>
                  )}
                </Feld>
              </div>
              <Feld label="Ansprechpartner beim Versorger" className="col-span-2" fehler={e.ansprechpartner}>
                {(p) => (
                  <Auswahl {...p} value={f.ansprechpartner} onChange={setze("ansprechpartner")} disabled={!gewaehlt}>
                    <option value="">— noch offen —</option>
                    {(gewaehlt?.ansprechpartner ?? []).filter((a) => a.aktiv).map((a) => (
                      <option key={a.id} value={a.id}>{a.name}{a.zustaendigkeit ? ` (${a.zustaendigkeit})` : ""}</option>
                    ))}
                  </Auswahl>
                )}
              </Feld>
              <Feld label="Katheter" className="col-span-2" fehler={e.katheter}>
                {(p) => (
                  <Auswahl {...p} value={f.katheter} onChange={setze("katheter")}>
                    <option value="">— nicht erfasst —</option>
                    <option value={KEIN}>kein Katheter</option>
                    {(katheter.data ?? []).map((k) => <option key={k.id} value={k.id}>{k.wert}</option>)}
                  </Auswahl>
                )}
              </Feld>
              <fieldset className="col-span-2 border-0 p-0 m-0 flex flex-col gap-2">
                <legend className="text-sm font-medium mb-2">Nickelallergie</legend>
                <div className="flex gap-5 h-9 items-center">
                  {["ja", "nein", "unbekannt"].map((w) => (
                    <label key={w} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input type="radio" name="nickelallergie" value={w} checked={f.nickelallergie === w} onChange={setze("nickelallergie")} /> {w}
                    </label>
                  ))}
                </div>
              </fieldset>
              <div className="col-span-2 relative">
                {darf("versorger_pflegen") ? (
                  <button type="button" className="absolute right-0 top-0 text-[0.8125rem] bg-transparent border-0 p-0 text-akzent-text cursor-pointer hover:underline" aria-label="Neuen Arzt anlegen"
                    onClick={() => setSchnell("arzt")}>Neu anlegen</button>
                ) : null}
                <Feld label="Hausarzt" fehler={e.aufnahme_hausarzt ?? e.hausarzt}
                  hinweis="aus der Ärzteliste; weitere Ärzte und Bezugspersonen danach in der Akte">
                  {(p) => (
                    <Auswahl {...p} value={f.hausarzt} onChange={setze("hausarzt")}>
                      <option value="">— nicht erfasst —</option>
                      {(aerzte.data ?? []).filter((a) => a.aktiv).map((a) => (
                        <option key={a.id} value={a.id}>{a.name}{a.ort ? ` (${a.ort})` : ""}</option>
                      ))}
                    </Auswahl>
                  )}
                </Feld>
              </div>
              <Feld label="Überweisung / Kontaktaufnahme durch" className="col-span-2" fehler={e.ueberweisung_durch}>
                {(p) => <Eingabe {...p} placeholder="z. B. Klinik, Praxis Dr. Holtmeier" value={f.ueberweisung_durch} onChange={setze("ueberweisung_durch")} />}
              </Feld>
            </Abschnitt>

            <Karte className="px-5 py-[18px] flex flex-col gap-3">
              <label htmlFor="neu-diagnose" className="lbl">Diagnose (optional, später in der Akte ergänzbar)</label>
              <Textfeld id="neu-diagnose" rows={3} placeholder="z. B. Kurzdarmsyndrom nach Dünndarmresektion …"
                value={f.diagnose} onChange={setze("diagnose")} aria-invalid={e.diagnose ? true : undefined} />
              {e.diagnose ? <span className="fehlertext" role="alert">{e.diagnose}</span> : null}
            </Karte>
          </div>

          <aside className="flex flex-col gap-4">
            {aehnlich.length ? (
              <Karte className="p-4 flex flex-col gap-3 border-warn" data-testid="doppelung">
                <div className="flex items-center gap-2 font-semibold text-warn"><Icon name="warnung" /> Ähnlicher Patient vorhanden</div>
                <span className="text-sm text-text2 leading-normal">Gleiches Geburtsdatum und ähnlicher Name. Ist das dieselbe Person?</span>
                {aehnlich.map((p) => (
                  <div key={p.id} className="flex flex-col gap-2 border border-rand rounded-lg p-3">
                    <Link to={`/patienten/${p.id}`} className="flex flex-col gap-0.5 no-underline">
                      <span className="font-medium">{p.nachname}, {p.vorname}</span>
                      <span className="num text-[0.8125rem] gedaempft">
                        Nr. {nummer(p.nummer)} · geb. {datum(p.geburtsdatum)}{p.ort ? ` · ${p.ort}` : ""}{p.ist_abgeschlossen ? " · abgeschlossen" : ""}
                      </span>
                    </Link>
                    <div className="flex gap-2 flex-wrap">
                      <KnopfLink to={`/patienten/${p.id}`} klein>Akte öffnen</KnopfLink>
                      <Knopf klein onClick={() => setAndere((a) => [...a, p.id])}>Nein, andere Person</Knopf>
                    </div>
                  </div>
                ))}
              </Karte>
            ) : null}
            <Karte className={cx("p-4 flex flex-col gap-2.5")}>
              <h2 className="lbl m-0">Danach in der Akte</h2>
              <span className="text-sm text-text2 leading-normal">
                Therapie, erster Infusionsplan, Dokumente und Termine legst du in der Akte an. Hier reichen die Grunddaten.
              </span>
              <span className="text-[0.8125rem] gedaempft"><span className="text-fehler">*</span> Pflichtfelder: Nachname, Vorname, Geburtsdatum</span>
            </Karte>
          </aside>
        </div>
      </form>
      {/* außerhalb des Formulars: sonst würde „Anlegen“ im Dialog auch den Patienten absenden */}
      <NeuerVersorgerDialog offen={schnell === "versorger"} onOffen={(o) => setSchnell(o ? "versorger" : "")}
        onAngelegt={(v) => setF((alt) => ({ ...alt, versorger: String(v.id), ansprechpartner: "" }))} />
      <NeuerArztDialog offen={schnell === "arzt"} onOffen={(o) => setSchnell(o ? "arzt" : "")}
        onAngelegt={(a) => setF((alt) => ({ ...alt, hausarzt: String(a.id) }))} />
    </Seite>
  );
}
