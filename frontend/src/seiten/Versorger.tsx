/**
 * Entwurf 13 · Versorger mit Ansprechpartnern. Nie löschen, nur deaktivieren; Patienten vorher neu zuordnen.
 * Aufbau seit 08.10.2026 nach dem Entwurf: Liste links, Versorger rechts zum Lesen, „Bearbeiten“ öffnet das Formular
 * (components/StammListe.tsx).
 */
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useVersorgerListe } from "@/lib/daten";
import { nummer, zahl } from "@/lib/format";
import type { Ansprechpartner, PatientZeile, Versorger as VersorgerTyp } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, Knopf, Laden, Meldung, Seitenkopf, Textfeld, cx } from "@/components/ui/basis";
import { Dialog, Menue } from "@/components/ui/dialog";
import { Bestaetigen } from "@/components/Bestaetigen";
import { DetailKopf, Infoblock, ListenSpalte } from "@/components/StammListe";
import type { Filter } from "@/components/StammListe";
import { useMobil } from "@/lib/stufen";
import { useHinweis } from "@/components/ui/hinweise";

const VERSORGER_FELDER = ["name", "strasse", "plz", "ort", "telefon", "fax", "email", "notiz"] as const;
type VersorgerFormular = Record<(typeof VERSORGER_FELDER)[number], string>;
const LEER_V: VersorgerFormular = { name: "", strasse: "", plz: "", ort: "", telefon: "", fax: "", email: "", notiz: "" };
const AP_FELDER = ["name", "zustaendigkeit", "telefon", "mobil", "email", "notiz"] as const;
type ApFormular = Record<(typeof AP_FELDER)[number], string>;
const LEER_AP: ApFormular = { name: "", zustaendigkeit: "", telefon: "", mobil: "", email: "", notiz: "" };

function formularVon(v: VersorgerTyp | undefined): VersorgerFormular {
  if (!v) return { ...LEER_V };
  return Object.fromEntries(VERSORGER_FELDER.map((k) => [k, v[k] ?? ""])) as VersorgerFormular;
}

/** Ansprechpartner anlegen, bearbeiten, deaktivieren (mit Neuzuordnung der betreuten Patienten) */
function AnsprechpartnerDialog({ versorger, ap, offen, onOffen }: {
  versorger: VersorgerTyp; ap: Ansprechpartner | null; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const [f, setF] = useState<ApFormular>({ ...LEER_AP });
  const [ziel, setZiel] = useState("");
  const [modus, setModus] = useState<"bearbeiten" | "deaktivieren">("bearbeiten");
  const qc = useQueryClient();
  const melden = useHinweis();
  useEffect(() => {
    if (offen) {
      setF(ap ? (Object.fromEntries(AP_FELDER.map((k) => [k, ap[k] ?? ""])) as ApFormular) : { ...LEER_AP });
      setModus("bearbeiten");
      setZiel("");
    }
  }, [offen, ap]);
  const fertig = (text: string) => {
    void qc.invalidateQueries({ queryKey: ["versorger"] });
    void qc.invalidateQueries({ queryKey: ["patienten"] });
    melden(text);
    onOffen(false);
  };
  const speichern = useMutation({
    mutationFn: () => ap
      ? api<Ansprechpartner>(`ansprechpartner/${ap.id}/`, { method: "PATCH", body: f })
      : api<Ansprechpartner>("ansprechpartner/", { body: { ...f, versorger: versorger.id } }),
    onSuccess: () => fertig(ap ? "Ansprechpartner gespeichert." : "Ansprechpartner angelegt."),
  });
  const betreute = useQuery({
    queryKey: ["ansprechpartner", ap?.id, "patienten"],
    queryFn: () => api<PatientZeile[]>(`ansprechpartner/${ap!.id}/patienten/`),
    enabled: !!ap && offen && modus === "deaktivieren",
  });
  const deaktivieren = useMutation({
    mutationFn: async () => {
      if (ziel) await api(`ansprechpartner/${ap!.id}/neu-zuordnen/`, { body: { ziel: Number(ziel) } });
      return api(`ansprechpartner/${ap!.id}/`, { method: "PATCH", body: { aktiv: false } });
    },
    onSuccess: () => fertig("Ansprechpartner deaktiviert."),
  });
  const aktivieren = useMutation({
    mutationFn: () => api(`ansprechpartner/${ap!.id}/`, { method: "PATCH", body: { aktiv: true } }),
    onSuccess: () => fertig("Ansprechpartner wieder aktiv."),
  });
  const fehler: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const andere = versorger.ansprechpartner.filter((a) => a.aktiv && a.id !== ap?.id);
  const anzahl = betreute.data?.length ?? 0;

  if (ap && modus === "deaktivieren") {
    return (
      <Dialog offen={offen} onOffen={onOffen} titel={`${ap.name} deaktivieren`} breite={560}
        beschreibung="Ansprechpartner werden nie gelöscht. In bestehenden Akten bleibt der Name erhalten."
        fuss={<>
          <Knopf onClick={() => setModus("bearbeiten")}>Zurück</Knopf>
          <Knopf variante="dng" laedt={deaktivieren.isPending} disabled={betreute.isLoading || (anzahl > 0 && !ziel && andere.length > 0)}
            onClick={() => deaktivieren.mutate()}>
            {anzahl > 0 && ziel ? `${anzahl} Patienten neu zuordnen und deaktivieren` : "Deaktivieren"}
          </Knopf>
        </>}>
        {betreute.isLoading ? <Laden /> : anzahl === 0 ? (
          <Meldung>Keine Patienten in Betreuung zugeordnet.</Meldung>
        ) : (
          <div className="flex flex-col gap-3">
            <span className="text-sm">{anzahl} Patienten in Betreuung sind {ap.name} zugeordnet:</span>
            <ul className="m-0 p-0 list-none max-h-48 overflow-auto border border-rand rounded-lg" data-testid="neu-zuordnen-liste">
              {betreute.data!.map((p) => (
                <li key={p.id} className="px-3 py-1.5 text-sm border-b border-rand last:border-b-0 flex gap-3">
                  <span className="num gedaempft">{nummer(p.nummer)}</span> {p.nachname}, {p.vorname}
                </li>
              ))}
            </ul>
            {andere.length ? (
              <Feld label="Neu zuordnen an">
                {(p) => (
                  <Auswahl {...p} value={ziel} onChange={(e) => setZiel(e.target.value)}>
                    <option value="">— bitte wählen —</option>
                    {andere.map((a) => <option key={a.id} value={a.id}>{a.name}{a.zustaendigkeit ? ` (${a.zustaendigkeit})` : ""}</option>)}
                  </Auswahl>
                )}
              </Feld>
            ) : (
              <Meldung art="warn">Bei {versorger.name} gibt es keinen anderen aktiven Ansprechpartner. Die Patienten behalten die
                Zuordnung, bis ein neuer Ansprechpartner angelegt ist.</Meldung>
            )}
          </div>
        )}
        <Fehleranzeige fehler={deaktivieren.error} />
      </Dialog>
    );
  }

  return (
    <Dialog offen={offen} onOffen={onOffen} titel={ap ? ap.name : "Neuer Ansprechpartner"} beschreibung={versorger.name} breite={560}
      fuss={<>
        {ap && ap.aktiv ? <Knopf variante="dng" onClick={() => setModus("deaktivieren")}>Deaktivieren</Knopf> : null}
        {ap && !ap.aktiv ? <Knopf className="mr-auto" laedt={aktivieren.isPending} onClick={() => aktivieren.mutate()}>Wieder aktivieren</Knopf> : null}
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <form className="grid grid-cols-2 gap-3" onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        <Feld label="Name" pflicht fehler={fehler.name}>
          {(p) => <Eingabe {...p} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoFocus />}
        </Feld>
        <Feld label="Zuständigkeit" hinweis="z. B. „Patienten A–K“, „Kreis Warendorf“" fehler={fehler.zustaendigkeit}>
          {(p) => <Eingabe {...p} value={f.zustaendigkeit} onChange={(e) => setF({ ...f, zustaendigkeit: e.target.value })} />}
        </Feld>
        <Feld label="Telefon" fehler={fehler.telefon}>
          {(p) => <Eingabe {...p} className="num" value={f.telefon} onChange={(e) => setF({ ...f, telefon: e.target.value })} />}
        </Feld>
        <Feld label="Mobil" fehler={fehler.mobil}>
          {(p) => <Eingabe {...p} className="num" value={f.mobil} onChange={(e) => setF({ ...f, mobil: e.target.value })} />}
        </Feld>
        <Feld label="E-Mail" className="col-span-2" fehler={fehler.email}>
          {(p) => <Eingabe {...p} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />}
        </Feld>
        <Feld label="Notiz" className="col-span-2" fehler={fehler.notiz}>
          {(p) => <Textfeld {...p} rows={2} value={f.notiz} onChange={(e) => setF({ ...f, notiz: e.target.value })} />}
        </Feld>
        {speichern.error && !Object.keys(fehler).length ? <Meldung art="fehler" className="col-span-2">{speichern.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

const SPALTEN: Record<number, string> = { 1: "col-span-1", 2: "col-span-2", 3: "col-span-3", 4: "col-span-4", 6: "col-span-6" };
type Sortierung = "name" | "ansprechpartner";

/** Patienten in Betreuung: dreispaltig (Tablet zwei, Telefon eine), erst zwölf, dann alle */
function BetreutePatienten({ versorger }: { versorger: VersorgerTyp }) {
  const [sortierung, setSortierung] = useState<Sortierung>("name");
  const [alle, setAlle] = useState(false);
  const patienten = useQuery({
    queryKey: ["patienten", "versorger", versorger.id],
    queryFn: () => api<{ results: PatientZeile[]; count: number }>(`patienten/?versorger=${versorger.id}&status=in_betreuung&ordering=nachname&seitengroesse=500`),
  });
  useEffect(() => setAlle(false), [versorger.id]);
  const liste = [...(patienten.data?.results ?? [])].sort((a, b) => sortierung === "ansprechpartner"
    ? (a.ansprechpartner_name ?? "~").localeCompare(b.ansprechpartner_name ?? "~", "de") || a.nachname.localeCompare(b.nachname, "de")
    : a.nachname.localeCompare(b.nachname, "de") || a.vorname.localeCompare(b.vorname, "de"));
  const zeigen = alle ? liste : liste.slice(0, 12);
  return (
    <div className="flex flex-col gap-2 px-4 sm:px-5 py-3.5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="m-0 text-[0.9375rem] font-semibold">Patienten in Betreuung <span className="num gedaempft font-normal">{zahl(patienten.data?.count ?? versorger.patienten_anzahl)}</span></h3>
        {liste.length > 1 ? (
          <select aria-label="Sortierung der Patienten" className="bg-transparent border-0 text-[0.8125rem] gedaempft cursor-pointer"
            value={sortierung} onChange={(e) => setSortierung(e.target.value as Sortierung)}>
            <option value="name">nach Name</option>
            <option value="ansprechpartner">nach Ansprechpartner</option>
          </select>
        ) : null}
      </div>
      {patienten.isLoading ? <Laden /> : liste.length ? (
        <ul className="m-0 p-0 list-none grid grid-cols-1 sm:grid-cols-2 2xl:grid-cols-3 gap-x-6" data-testid="versorger-patienten">
          {zeigen.map((p) => (
            <li key={p.id} className="py-1.5 border-b border-rand text-sm flex items-center gap-2.5 min-w-0">
              <span className="num gedaempft">{nummer(p.nummer)}</span>
              <Link to={`/patienten/${p.id}`} className="truncate">{p.nachname}, {p.vorname}</Link>
              {p.nickelallergie === "ja" ? <Chip art="fehler">Nickel</Chip> : null}
              {p.ist_test ? <Chip art="warn">Test</Chip> : null}
              {sortierung === "ansprechpartner" && p.ansprechpartner_name ? <span className="ml-auto text-xs gedaempft truncate">{p.ansprechpartner_name}</span> : null}
            </li>
          ))}
          {!alle && liste.length > zeigen.length ? (
            <li className="py-1.5 text-sm"><button type="button" className="bg-transparent border-0 p-0 text-akzent-text cursor-pointer"
              onClick={() => setAlle(true)}>… {zahl(liste.length - zeigen.length)} weitere</button></li>
          ) : null}
        </ul>
      ) : <span className="text-sm gedaempft">Keine Patienten in Betreuung.</span>}
    </div>
  );
}

export function Versorger() {
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("aktiv");
  const liste = useVersorgerListe();
  const { darf } = useAuth();
  const mobil = useMobil();
  const pflegen = darf("versorger_pflegen");
  const neu = params.get("neu") === "1";
  const alle = liste.data ?? [];
  // Suche (Wunsch 08.10.2026): Firma, Ort, PLZ, Telefon, E-Mail und Ansprechpartner (Name, Telefon, Zuständigkeit)
  const [suche, setSuche] = useState("");
  const woerter = suche.toLowerCase().split(/\s+/).filter(Boolean);
  const trifft = (v: VersorgerTyp) => {
    if (!woerter.length) return true;
    const text = [v.name, v.ort, v.plz, v.strasse, v.telefon, v.email,
      ...v.ansprechpartner.flatMap((a) => [a.name, a.telefon, a.mobil, a.zustaendigkeit])].join(" ").toLowerCase();
    return woerter.every((w) => text.includes(w));
  };
  const sichtbar = alle.filter((v) => (filter === "alle" || (filter === "aktiv") === v.aktiv) && trifft(v));
  // Am Telefon erst die Liste, ein Eintrag erst nach Antippen; auf PC und Tablet ist der erste gewählt
  const gewaehltId = Number(params.get("id")) || (mobil ? null : sichtbar[0]?.id ?? null);
  const cur = neu ? undefined : alle.find((v) => v.id === gewaehltId);
  const [bearbeiten, setBearbeiten] = useState(false);
  const [f, setF] = useState<VersorgerFormular>({ ...LEER_V });
  const [apDialog, setApDialog] = useState<{ offen: boolean; ap: Ansprechpartner | null }>({ offen: false, ap: null });
  const [frage, setFrage] = useState(false);
  const qc = useQueryClient();
  const melden = useHinweis();

  // Formular beim Wechsel des Versorgers neu füllen und wieder zum Lesen umschalten
  useEffect(() => { setF(formularVon(cur)); setBearbeiten(false); }, [cur?.id, neu]); // eslint-disable-line react-hooks/exhaustive-deps

  const waehlen = (id: number) => setParams(new URLSearchParams({ id: String(id) }), { replace: !mobil });
  const zurListe = () => setParams(new URLSearchParams(), { replace: true });
  const speichern = useMutation({
    mutationFn: () => cur
      ? api<VersorgerTyp>(`versorger/${cur.id}/`, { method: "PATCH", body: f })
      : api<VersorgerTyp>("versorger/", { body: f }),
    onSuccess: (v) => {
      void qc.invalidateQueries({ queryKey: ["versorger"] });
      melden(cur ? "Versorger gespeichert." : "Versorger angelegt.");
      setBearbeiten(false);
      if (!cur) waehlen(v.id);
    },
  });
  const aktivSetzen = useMutation({
    mutationFn: (aktiv: boolean) => api<VersorgerTyp>(`versorger/${cur!.id}/`, { method: "PATCH", body: { aktiv } }),
    onSuccess: (v) => {
      void qc.invalidateQueries({ queryKey: ["versorger"] });
      melden(v.aktiv ? "Versorger wieder aktiv." : "Versorger deaktiviert.");
      setFrage(false);
      setFilter(v.aktiv ? "aktiv" : "inaktiv");
    },
  });
  const fehler: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const geaendert = VERSORGER_FELDER.some((k) => f[k] !== formularVon(cur)[k]);
  const formular = neu || (bearbeiten && pflegen);

  // 6-spaltiges Raster (Wunsch 08.10.2026: auf einem 1080p-Bildschirm ohne Scrollen): Angabe ``spalten`` von 6
  const feld = (k: (typeof VERSORGER_FELDER)[number], label: string, extra?: { num?: boolean; spalten?: number; typ?: string }) => (
    <Feld label={label} className={SPALTEN[extra?.spalten ?? 3]} fehler={fehler[k]} pflicht={k === "name"}>
      {(p) => <Eingabe {...p} className={extra?.num ? "num" : undefined} type={extra?.typ} value={f[k]}
        onChange={(e) => setF({ ...f, [k]: e.target.value })} />}
    </Feld>
  );
  const zeigeDetail = !!(cur || neu);

  return (
    <Seite pfad={[{ text: "Versorger" }]}>
      <Seitenkopf titel="Versorger"
        rechts={pflegen ? <Knopf variante="pri" icon="plus" onClick={() => setParams(new URLSearchParams({ neu: "1" }), { replace: !mobil })}>Neuer Versorger</Knopf> : null} />
      <Fehleranzeige fehler={liste.error} />
      <div className="stamm-raster">
        {liste.isLoading ? <Laden /> : (
          <ListenSpalte<VersorgerTyp> eintraege={sichtbar} alle={alle} gewaehlt={neu ? null : gewaehltId} onWahl={waehlen}
            suche={suche} onSuche={setSuche} sucheLabel="Versorger filtern" platzhalter="Firma, Ort, Telefon, Ansprechpartner"
            filter={filter} onFilter={setFilter} testid="versorgerliste" versteckt={zeigeDetail}
            titel={(v) => v.name}
            unter={(v) => {
              const n = v.ansprechpartner.filter((a) => a.aktiv).length;
              return [v.ort, n ? `${n} Ansprechpartner` : ""].filter(Boolean).join(" · ") || "—";
            }}
            zahl={(v) => v.patienten_anzahl}
            leer={woerter.length ? "Kein Versorger passt zur Suche." : filter === "inaktiv" ? "Keine deaktivierten Versorger." : "Noch keine Versorger angelegt."}
            fuss={<><span className="num">{zahl(sichtbar.length)}</span> Versorger · Zahl rechts = Patienten in Betreuung</>} />
        )}

        {zeigeDetail ? (
          <Karte className="min-w-0 flex flex-col" data-testid="versorger-detail">
            <DetailKopf titel={cur ? cur.name : "Neuer Versorger"} aktiv={cur?.aktiv} onListe={zurListe}
              patienten={cur?.patienten_anzahl} patientenLink={cur ? `/patienten?versorger=${cur.id}` : undefined}
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
                  {feld("name", "Firma", { spalten: 6 })}
                  {feld("strasse", "Straße")}
                  {feld("plz", "PLZ", { num: true, spalten: 1 })}
                  {feld("ort", "Ort", { spalten: 2 })}
                  {feld("telefon", "Telefon Zentrale", { num: true, spalten: 2 })}
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
                <Infoblock titel="Anschrift" zeilen={[["Straße", cur.strasse], ["Ort", [cur.plz, cur.ort].filter(Boolean).join(" "), true]]} />
                <Infoblock titel="Erreichbarkeit" zeilen={[["Zentrale", cur.telefon, true], ["Fax", cur.fax, true],
                  ["E-Mail", cur.email ? <a href={`mailto:${cur.email}`}>{cur.email}</a> : ""]]} />
                <Infoblock titel="Notiz">
                  <p className={cx("m-0 text-sm whitespace-pre-line break-words", !cur.notiz && "gedaempft")}>{cur.notiz || "—"}</p>
                </Infoblock>
              </div>
            ) : null}

            {cur ? (
              <div className="flex flex-col gap-2 px-4 sm:px-5 py-3.5 border-b border-rand">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="m-0 text-[0.9375rem] font-semibold">Ansprechpartner <span className="num gedaempft font-normal">{zahl(cur.ansprechpartner.filter((a) => a.aktiv).length)}</span></h3>
                  {pflegen ? <Knopf klein icon="plus" onClick={() => setApDialog({ offen: true, ap: null })}>Ansprechpartner</Knopf> : null}
                </div>
                {cur.ansprechpartner.length ? (
                  <table className="tabelle" data-testid="ansprechpartner">
                    <thead><tr><th className="th">Name</th><th className="th max-sm:hidden">Zuständigkeit</th><th className="th">Telefon</th>
                      <th className="th text-right">Patienten</th></tr></thead>
                    <tbody>
                      {cur.ansprechpartner.map((a) => (
                        <tr key={a.id} className={cx(!a.aktiv && "opacity-60")}>
                          <td className="td">
                            {pflegen ? (
                              <button type="button" className="bg-transparent border-0 p-0 text-left text-akzent-text cursor-pointer"
                                onClick={() => setApDialog({ offen: true, ap: a })}>{a.name}</button>
                            ) : a.name}
                            <span className="sm:hidden block text-xs gedaempft">{a.zustaendigkeit}{!a.aktiv ? " · inaktiv" : ""}</span>
                          </td>
                          <td className="td text-text2 max-sm:hidden">{a.zustaendigkeit}{!a.aktiv ? " · inaktiv" : ""}</td>
                          <td className="td num">{a.telefon || a.mobil || "—"}{a.telefon && a.mobil ? <span className="block gedaempft">{a.mobil}</span> : null}</td>
                          <td className="td num text-right">
                            <Link to={`/patienten?versorger=${cur.id}&ansprechpartner=${a.id}`} className="no-underline" aria-label={`${zahl(a.patienten_anzahl)} Patienten`}>
                              {zahl(a.patienten_anzahl)}</Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <span className="text-sm gedaempft">Keine Ansprechpartner hinterlegt.</span>}
              </div>
            ) : null}

            {cur ? <BetreutePatienten versorger={cur} /> : null}
            {cur ? <AnsprechpartnerDialog versorger={cur} ap={apDialog.ap} offen={apDialog.offen} onOffen={(o) => setApDialog((d) => ({ ...d, offen: o }))} /> : null}
            {cur ? (
              <Bestaetigen offen={frage} onOffen={setFrage} titel="Versorger deaktivieren" knopf="Deaktivieren"
                text={<>{cur.name} ist bei neuen Patienten nicht mehr wählbar. In bestehenden Akten und Plänen bleibt er erhalten; er lässt sich wieder aktivieren.</>}
                laedt={aktivSetzen.isPending} fehler={aktivSetzen.error} onJa={() => aktivSetzen.mutate(false)} />
            ) : null}
          </Karte>
        ) : null}
      </div>
    </Seite>
  );
}
