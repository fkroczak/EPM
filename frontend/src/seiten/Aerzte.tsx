/**
 * Gemeinsame Ärzteliste (Festlegung 01.10.2026): Praxis mit Kontaktdaten einmal pflegen, beim Patienten mit Rolle
 * zuordnen (Hausarzt, Facharzt …). Eine geänderte Telefonnummer gilt so in jeder Akte. Nie löschen, nur deaktivieren.
 * Aufbau seit 08.10.2026 wie Versorger: Liste links, Arzt rechts zum Lesen, „Bearbeiten“ öffnet das Formular.
 */
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAerzteListe } from "@/lib/daten";
import { nummer, zahl } from "@/lib/format";
import type { Arzt, PatientZeile } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Eingabe, Feld, Fehleranzeige, Karte, Knopf, Laden, Meldung, Seitenkopf, Textfeld, cx } from "@/components/ui/basis";
import { Menue } from "@/components/ui/dialog";
import { Bestaetigen } from "@/components/Bestaetigen";
import { DetailKopf, Infoblock, ListenSpalte } from "@/components/StammListe";
import type { Filter } from "@/components/StammListe";
import { useMobil } from "@/lib/stufen";
import { useHinweis } from "@/components/ui/hinweise";

const FELDER = ["name", "praxis", "fachrichtung", "strasse", "plz", "ort", "telefon", "fax", "email", "notiz"] as const;
// Längen wie in der Datenbank: Eingabe endet dort, statt erst beim Speichern zu scheitern (Prüfung 11.10.2026)
const MAX_LAENGE: Record<string, number> = { name: 150, praxis: 150, fachrichtung: 100, strasse: 150, plz: 10, ort: 100, telefon: 50, fax: 50, email: 254 };
type Formular = Record<(typeof FELDER)[number], string>;
const LEER: Formular = { name: "", praxis: "", fachrichtung: "", strasse: "", plz: "", ort: "", telefon: "", fax: "", email: "", notiz: "" };

function formularVon(a: Arzt | undefined): Formular {
  if (!a) return { ...LEER };
  return Object.fromEntries(FELDER.map((k) => [k, a[k] ?? ""])) as Formular;
}

function ZugeordnetePatienten({ arzt }: { arzt: Arzt }) {
  const [alle, setAlle] = useState(false);
  const patienten = useQuery({
    queryKey: ["aerzte", arzt.id, "patienten"],
    queryFn: () => api<PatientZeile[]>(`aerzte/${arzt.id}/patienten/`),
  });
  useEffect(() => setAlle(false), [arzt.id]);
  const liste = patienten.data ?? [];
  const zeigen = alle ? liste : liste.slice(0, 12);
  return (
    <div className="flex flex-col gap-2 px-4 sm:px-5 py-3.5">
      <h3 className="m-0 text-[0.9375rem] font-semibold">Patienten in Betreuung <span className="num gedaempft font-normal">{zahl(liste.length || arzt.patienten_anzahl)}</span></h3>
      {patienten.isLoading ? <Laden /> : liste.length ? (
        // dreispaltig und eng: viele Patienten passen ohne Scrollen (Wunsch 08.10.2026)
        <ul className="m-0 p-0 list-none grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-3 gap-x-6" data-testid="arzt-patienten">
          {zeigen.map((p) => (
            <li key={p.id} className="py-1.5 border-b border-rand text-sm flex items-center gap-2.5 min-w-0">
              <span className="num gedaempft">{nummer(p.nummer)}</span>
              <Link to={`/patienten/${p.id}`} className="truncate">{p.nachname}, {p.vorname}</Link>
              {p.nickelallergie === "ja" ? <Chip art="fehler">Nickel</Chip> : null}
              {p.ist_test ? <Chip art="warn">Testpatient</Chip> : null}
            </li>
          ))}
          {!alle && liste.length > zeigen.length ? (
            <li className="py-1.5 text-sm"><button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer"
              onClick={() => setAlle(true)}>… {zahl(liste.length - zeigen.length)} weitere</button></li>
          ) : null}
        </ul>
      ) : <span className="text-sm gedaempft">Keinem Patienten in Betreuung zugeordnet.</span>}
    </div>
  );
}

const SPALTEN: Record<number, string> = { 1: "col-span-1", 2: "col-span-2", 3: "col-span-3", 4: "col-span-4", 6: "col-span-6" };

export function Aerzte() {
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("aktiv");
  const [suche, setSuche] = useState("");
  const liste = useAerzteListe();
  const { darf } = useAuth();
  const mobil = useMobil();
  const pflegen = darf("versorger_pflegen");
  const neu = params.get("neu") === "1";
  const alle = liste.data ?? [];
  const wort = suche.trim().toLowerCase();
  const sichtbar = alle
    .filter((a) => filter === "alle" || (filter === "aktiv") === a.aktiv)
    .filter((a) => !wort || [a.name, a.praxis, a.fachrichtung, a.ort, a.telefon].some((t) => t.toLowerCase().includes(wort)));
  const gewaehltId = Number(params.get("id")) || (mobil ? null : sichtbar[0]?.id ?? null);
  const cur = neu ? undefined : alle.find((a) => a.id === gewaehltId);
  const [bearbeiten, setBearbeiten] = useState(false);
  const [frage, setFrage] = useState(false);
  const [f, setF] = useState<Formular>({ ...LEER });
  const qc = useQueryClient();
  const melden = useHinweis();

  // Formular beim Wechsel neu füllen und wieder zum Lesen umschalten
  useEffect(() => { setF(formularVon(cur)); setBearbeiten(false); }, [cur?.id, neu]); // eslint-disable-line react-hooks/exhaustive-deps

  const waehlen = (id: number) => setParams(new URLSearchParams({ id: String(id) }), { replace: !mobil });
  const zurListe = () => setParams(new URLSearchParams(), { replace: true });
  const neuLaden = () => {
    void qc.invalidateQueries({ queryKey: ["aerzte"] });
    void qc.invalidateQueries({ queryKey: ["patient"] });
  };
  const speichern = useMutation({
    mutationFn: () => cur
      ? api<Arzt>(`aerzte/${cur.id}/`, { method: "PATCH", body: f })
      : api<Arzt>("aerzte/", { body: f }),
    onSuccess: (a) => {
      neuLaden();
      melden(cur ? "Arzt gespeichert." : "Arzt angelegt.");
      setBearbeiten(false);
      if (!cur) waehlen(a.id);
    },
  });
  const aktivSetzen = useMutation({
    mutationFn: (aktiv: boolean) => api<Arzt>(`aerzte/${cur!.id}/`, { method: "PATCH", body: { aktiv } }),
    onSuccess: (a) => {
      neuLaden();
      melden(a.aktiv ? "Arzt wieder aktiv." : "Arzt deaktiviert.");
      setFrage(false);
      setFilter(a.aktiv ? "aktiv" : "inaktiv");
      waehlen(a.id); // der eben geänderte Eintrag bleibt gewählt
    },
  });
  const fehler: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const geaendert = FELDER.some((k) => f[k] !== formularVon(cur)[k]);
  const formular = neu || (bearbeiten && pflegen);

  // 6-spaltiges Raster (Wunsch 08.10.2026: auf einem 1080p-Bildschirm ohne Scrollen): Angabe ``spalten`` von 6
  const feld = (k: (typeof FELDER)[number], label: string, extra?: { num?: boolean; spalten?: number; typ?: string; platzhalter?: string }) => (
    <Feld label={label} className={SPALTEN[extra?.spalten ?? 3]} fehler={fehler[k]} pflicht={k === "name"}>
      {(p) => <Eingabe {...p} className={extra?.num ? "num" : undefined} type={extra?.typ} value={f[k]} placeholder={extra?.platzhalter} maxLength={MAX_LAENGE[k]}
        onChange={(e) => setF({ ...f, [k]: e.target.value })} />}
    </Feld>
  );
  const zeigeDetail = !!(cur || neu);

  return (
    <Seite pfad={[{ text: "Ärzte" }]}>
      <Seitenkopf titel="Ärzte"
        rechts={pflegen ? <Knopf variante="pri" icon="plus" onClick={() => setParams(new URLSearchParams({ neu: "1" }), { replace: !mobil })}>Neuer Arzt</Knopf> : null} />
      <Fehleranzeige fehler={liste.error} />
      <div className="stamm-raster">
        {liste.isLoading ? <Laden /> : (
          <ListenSpalte<Arzt> eintraege={sichtbar} alle={alle} gewaehlt={neu ? null : gewaehltId} onWahl={waehlen}
            suche={suche} onSuche={setSuche} sucheLabel="Ärzte filtern" platzhalter="Name, Praxis, Fachrichtung, Ort"
            filter={filter} onFilter={setFilter} testid="aerzteliste" versteckt={zeigeDetail}
            titel={(a) => a.name}
            unter={(a) => [a.fachrichtung, a.ort].filter(Boolean).join(" · ") || a.praxis || "—"}
            zahl={(a) => a.patienten_anzahl}
            leer={wort ? "Kein Treffer." : filter === "inaktiv" ? "Keine deaktivierten Ärzte." : "Noch keine Ärzte angelegt."}
            fuss={<><span className="num">{zahl(sichtbar.length)}</span> Ärzte · Zahl rechts = Patienten in Betreuung</>} />
        )}

        {zeigeDetail ? (
          <Karte className="min-w-0 flex flex-col" data-testid="arzt-detail">
            <DetailKopf titel={cur ? cur.name : "Neuer Arzt"} aktiv={cur?.aktiv} onListe={zurListe} patienten={cur?.patienten_anzahl}
              rechts={cur && pflegen && !formular ? <>
                <Knopf klein icon="stift" onClick={() => setBearbeiten(true)}>Bearbeiten</Knopf>
                <Menue label="Weitere Aktionen" eintraege={cur.aktiv
                  ? [{ text: "Deaktivieren …", gefaehrlich: true, onClick: () => { aktivSetzen.reset(); setFrage(true); } }]
                  : [{ text: "Wieder aktivieren", onClick: () => aktivSetzen.mutate(true) }]} />
              </> : undefined} />

            {formular ? (
              <form className="flex flex-col gap-3.5 px-4 sm:px-5 py-4 border-b border-rand" noValidate
                onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
                <div className="formular grid grid-cols-6">
                  {feld("name", "Name", { spalten: 6, platzhalter: "mit Titel, z. B. „Dr. med. Anna Hausmann“" })}
                  {feld("praxis", "Praxis / Klinik")}
                  {feld("fachrichtung", "Fachrichtung")}
                  {feld("strasse", "Straße")}
                  {feld("plz", "PLZ", { num: true, spalten: 1 })}
                  {feld("ort", "Ort", { spalten: 2 })}
                  {feld("telefon", "Telefon", { num: true, spalten: 2 })}
                  {feld("fax", "Fax", { num: true, spalten: 2 })}
                  {feld("email", "E-Mail", { spalten: 2, typ: "email" })}
                  <Feld label="Notiz" className="col-span-6" fehler={fehler.notiz}>
                    {(p) => <Textfeld {...p} rows={2} value={f.notiz} onChange={(e) => setF({ ...f, notiz: e.target.value })} />}
                  </Feld>
                </div>
                {speichern.error && !Object.keys(fehler).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
                <div className="flex justify-end gap-2 flex-wrap">
                  <Knopf onClick={() => { if (neu) zurListe(); else { setF(formularVon(cur)); setBearbeiten(false); speichern.reset(); } }}>Abbrechen</Knopf>
                  <Knopf type="submit" variante="pri" laedt={speichern.isPending} disabled={!!cur && !geaendert}>Speichern</Knopf>
                </div>
              </form>
            ) : cur ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-x-8 gap-y-4 px-4 sm:px-5 py-4 border-b border-rand">
                <Infoblock titel="Praxis" zeilen={[["Praxis / Klinik", cur.praxis], ["Fachrichtung", cur.fachrichtung],
                  ["Straße", cur.strasse], ["Ort", [cur.plz, cur.ort].filter(Boolean).join(" "), true]]} />
                <Infoblock titel="Erreichbarkeit" zeilen={[["Telefon", cur.telefon, true], ["Fax", cur.fax, true],
                  ["E-Mail", cur.email ? <a href={`mailto:${cur.email}`}>{cur.email}</a> : ""]]} />
                <Infoblock titel="Notiz">
                  <p className={cx("m-0 text-sm whitespace-pre-line break-words", !cur.notiz && "gedaempft")}>{cur.notiz || "—"}</p>
                </Infoblock>
              </div>
            ) : null}
            {cur ? <ZugeordnetePatienten arzt={cur} /> : null}
            {cur ? (
              <Bestaetigen offen={frage} onOffen={setFrage} titel="Arzt deaktivieren" knopf="Deaktivieren"
                text={<>{cur.name} ist bei neuen Zuordnungen nicht mehr wählbar, bleibt aber in allen Akten sichtbar und lässt sich wieder aktivieren.</>}
                laedt={aktivSetzen.isPending} fehler={aktivSetzen.error} onJa={() => aktivSetzen.mutate(false)} />
            ) : null}
          </Karte>
        ) : null}
      </div>
    </Seite>
  );
}
