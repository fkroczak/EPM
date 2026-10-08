/** Entwurf 13 · Versorger mit Ansprechpartnern. Nie löschen, nur deaktivieren; Patienten vorher neu zuordnen. */
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
import { Anzeige, Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, Knopf, Laden, Leer, Meldung, Seitenkopf, Segmente, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";

type Filter = "aktiv" | "inaktiv" | "alle";
const VERSORGER_FELDER = ["name", "strasse", "plz", "ort", "telefon", "fax", "email", "notiz"] as const;
type VersorgerFormular = Record<(typeof VERSORGER_FELDER)[number], string>;
const LEER_V: VersorgerFormular = { name: "", strasse: "", plz: "", ort: "", telefon: "", fax: "", email: "", notiz: "" };
const AP_FELDER = ["name", "zustaendigkeit", "telefon", "mobil", "email", "notiz"] as const;
type ApFormular = Record<(typeof AP_FELDER)[number], string>;
const LEER_AP: ApFormular = { name: "", zustaendigkeit: "", telefon: "", mobil: "", email: "", notiz: "" };

function personen(n: number) {
  return n === 0 ? "—" : n === 1 ? "1 Person" : `${n} Personen`;
}

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
        {ap && ap.aktiv ? <Knopf className="mr-auto" onClick={() => setModus("deaktivieren")}>Deaktivieren</Knopf> : null}
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

export function Versorger() {
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("aktiv");
  const liste = useVersorgerListe();
  const { darf } = useAuth();
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
  const gewaehltId = Number(params.get("id")) || sichtbar[0]?.id;
  const cur = neu ? undefined : alle.find((v) => v.id === gewaehltId);
  const [f, setF] = useState<VersorgerFormular>({ ...LEER_V });
  const [apDialog, setApDialog] = useState<{ offen: boolean; ap: Ansprechpartner | null }>({ offen: false, ap: null });
  const qc = useQueryClient();
  const melden = useHinweis();

  // Formular nur beim Wechsel des Versorgers neu füllen (ein Neuladen im Hintergrund verwirft keine Eingaben)
  // (nicht beim ersten Laden der Liste: sonst ging eine schon begonnene Eingabe bei „Neu“ verloren)
  useEffect(() => setF(formularVon(cur)), [cur?.id, neu]); // eslint-disable-line react-hooks/exhaustive-deps

  const waehlen = (id: number) => setParams(new URLSearchParams({ id: String(id) }), { replace: true });
  const speichern = useMutation({
    mutationFn: () => cur
      ? api<VersorgerTyp>(`versorger/${cur.id}/`, { method: "PATCH", body: f })
      : api<VersorgerTyp>("versorger/", { body: f }),
    onSuccess: (v) => {
      void qc.invalidateQueries({ queryKey: ["versorger"] });
      melden(cur ? "Versorger gespeichert." : "Versorger angelegt.");
      if (!cur) waehlen(v.id);
    },
  });
  const aktivSetzen = useMutation({
    mutationFn: (aktiv: boolean) => api<VersorgerTyp>(`versorger/${cur!.id}/`, { method: "PATCH", body: { aktiv } }),
    onSuccess: (v) => {
      void qc.invalidateQueries({ queryKey: ["versorger"] });
      melden(v.aktiv ? "Versorger wieder aktiv." : "Versorger deaktiviert.");
      setFilter(v.aktiv ? "aktiv" : "inaktiv");
    },
  });
  const fehler: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const geaendert = VERSORGER_FELDER.some((k) => f[k] !== formularVon(cur)[k]);

  // 6-spaltiges Raster (Wunsch 08.10.2026: auf einem 1080p-Bildschirm ohne Scrollen): Angabe ``spalten`` von 6
  const feld = (k: (typeof VERSORGER_FELDER)[number], label: string, extra?: { num?: boolean; spalten?: number; typ?: string }) => !pflegen ? (
    <Anzeige label={label} className={SPALTEN[extra?.spalten ?? 3]}>{f[k]}</Anzeige>
  ) : (
    <Feld label={label} className={SPALTEN[extra?.spalten ?? 3]} fehler={fehler[k]} pflicht={k === "name"}>
      {(p) => <Eingabe {...p} className={extra?.num ? "num" : undefined} type={extra?.typ} value={f[k]}
        onChange={(e) => setF({ ...f, [k]: e.target.value })} />}
    </Feld>
  );

  return (
    <Seite pfad={[{ text: "Versorger" }]}>
      <Seitenkopf titel="Versorger"
        rechts={<>
          <Segmente label="Filter" wert={filter} onWahl={setFilter}
            werte={[{ wert: "aktiv", text: "Aktiv" }, { wert: "inaktiv", text: "Inaktiv" }, { wert: "alle", text: "Alle" }]} />
          {pflegen ? <Knopf variante="pri" icon="plus" onClick={() => setParams(new URLSearchParams({ neu: "1" }), { replace: true })}>Neuer Versorger</Knopf> : null}
        </>} />
      <Fehleranzeige fehler={liste.error} />
      <label className="relative w-[280px] block">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
        <input className="inp pl-[34px]" type="search" aria-label="Versorger filtern" placeholder="Firma, Ort, Telefon, Ansprechpartner"
          value={suche} onChange={(e) => setSuche(e.target.value)} />
      </label>
      <div className="stapel grid grid-cols-1 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-5 items-start">
        <Karte className="overflow-hidden">
          {liste.isLoading ? <Laden /> : (
            <table className="tabelle" data-testid="versorgerliste">
              <thead><tr><th className="th">Firma</th><th className="th">Ansprechpartner</th><th className="th">Telefon</th><th className="th text-right">Patienten</th></tr></thead>
              <tbody>
                {sichtbar.map((v) => (
                  <tr key={v.id} className={cx("cursor-pointer", !neu && v.id === gewaehltId && "gewaehlt")} onClick={() => waehlen(v.id)}>
                    <td className="td">
                      <button type="button" className="bg-transparent border-0 p-0 font-medium text-akzent-text cursor-pointer text-left"
                        aria-current={!neu && v.id === gewaehltId ? "true" : undefined} onClick={(e) => { e.stopPropagation(); waehlen(v.id); }}>
                        {v.name}
                      </button>
                      {!v.aktiv ? <Chip className="ml-2">inaktiv</Chip> : null}
                      <br /><span className="text-[0.8125rem] gedaempft">{v.ort || "—"}</span>
                    </td>
                    <td className="td text-text2">{personen(v.ansprechpartner.filter((a) => a.aktiv).length)}</td>
                    <td className="td num">{v.telefon || "—"}</td>
                    <td className="td num text-right">{zahl(v.patienten_anzahl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {liste.data && !sichtbar.length ? <Leer>{woerter.length ? "Kein Versorger passt zur Suche." : filter === "inaktiv" ? "Keine deaktivierten Versorger." : "Noch keine Versorger angelegt."}</Leer> : null}
        </Karte>

        {cur || neu ? (
          <Karte className="px-5 py-[18px] flex flex-col gap-3.5 min-w-0" data-testid="versorger-detail">
            <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); if (pflegen) speichern.mutate(); }}>
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="m-0 text-lg font-semibold">{cur ? cur.name : "Neuer Versorger"}</h2>
                {cur ? <span className="text-[0.8125rem] gedaempft"><span className="num">{zahl(cur.patienten_anzahl)}</span> Patienten in Betreuung</span> : null}
              </div>
              <div className="formular grid grid-cols-6">
                {feld("name", "Firma", { spalten: 6 })}
                {feld("strasse", "Straße")}
                {feld("plz", "PLZ", { num: true, spalten: 1 })}
                {feld("ort", "Ort", { spalten: 2 })}
                {feld("telefon", "Telefon Zentrale", { num: true, spalten: 2 })}
                {feld("fax", "Fax", { num: true, spalten: 2 })}
                {feld("email", "E-Mail", { spalten: 2, typ: "email" })}
                {pflegen ? (
                  <Feld label="Notiz" className="col-span-6" fehler={fehler.notiz}>
                    {(p) => <Textfeld {...p} rows={2} value={f.notiz} onChange={(e) => setF({ ...f, notiz: e.target.value })} />}
                  </Feld>
                ) : <Anzeige label="Notiz" className="col-span-6" mehrzeilig>{f.notiz}</Anzeige>}
              </div>
              {speichern.error && !Object.keys(fehler).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
              {pflegen ? (
                <div className="flex justify-end gap-2 flex-wrap">
                  {cur && cur.aktiv ? <Knopf className="mr-auto" laedt={aktivSetzen.isPending} onClick={() => aktivSetzen.mutate(false)}>Deaktivieren</Knopf> : null}
                  {cur && !cur.aktiv ? <Knopf className="mr-auto" laedt={aktivSetzen.isPending} onClick={() => aktivSetzen.mutate(true)}>Wieder aktivieren</Knopf> : null}
                  {neu ? <Knopf onClick={() => setParams(new URLSearchParams(), { replace: true })}>Abbrechen</Knopf> : null}
                  <Knopf type="submit" variante="pri" laedt={speichern.isPending} disabled={!!cur && !geaendert}>{cur ? "Speichern" : "Versorger anlegen"}</Knopf>
                </div>
              ) : null}
            </form>

            {cur ? (
              <div className="flex flex-col gap-2.5 border-t border-rand pt-3.5">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="lbl m-0">Ansprechpartner</h3>
                  {pflegen ? <Knopf klein icon="plus" onClick={() => setApDialog({ offen: true, ap: null })}>Ansprechpartner</Knopf> : null}
                </div>
                <div className="flex flex-col" data-testid="ansprechpartner">
                  {cur.ansprechpartner.map((a) => (
                    <div key={a.id} className={cx("grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 py-1 border-b border-rand last:border-b-0", !a.aktiv && "opacity-60")}>
                      <span className="flex flex-col gap-px min-w-0">
                        {pflegen ? (
                          <button type="button" className="bg-transparent border-0 p-0 text-left font-medium text-akzent-text cursor-pointer"
                            onClick={() => setApDialog({ offen: true, ap: a })}>{a.name}</button>
                        ) : <span className="font-medium">{a.name}</span>}
                        <span className="text-[0.8125rem] gedaempft truncate">{a.zustaendigkeit}{!a.aktiv ? " · inaktiv" : ""}</span>
                      </span>
                      <span className="flex flex-col items-end text-[0.8125rem]">
                        <span className="num">{a.telefon}</span><span className="num gedaempft">{a.mobil}</span>
                      </span>
                      <Link to={`/patienten?versorger=${cur.id}&ansprechpartner=${a.id}`} className="text-[0.8125rem] no-underline whitespace-nowrap">
                        <span className="num">{zahl(a.patienten_anzahl)}</span> Patienten
                      </Link>
                    </div>
                  ))}
                  {!cur.ansprechpartner.length ? <span className="text-sm gedaempft py-2">Keine Ansprechpartner hinterlegt.</span> : null}
                </div>

              </div>
            ) : null}

            {/* Hinweise in einer kleinen Zeile statt drei Absätzen (Wunsch 08.10.2026: ohne Scrollen auf 1080p) */}
            <span className="text-xs gedaempft leading-snug">
              Jeder Patient ist einem Ansprechpartner zugeordnet; wird jemand deaktiviert, zeigt EPM seine Patienten zum Neuzuordnen an.
              Versorger werden nie gelöscht, nur deaktiviert – sie bleiben in allen Akten und Plänen erhalten.
              Änderungen werden mit Person und Zeitpunkt protokolliert.
            </span>
            {cur ? <AnsprechpartnerDialog versorger={cur} ap={apDialog.ap} offen={apDialog.offen} onOffen={(o) => setApDialog((d) => ({ ...d, offen: o }))} /> : null}
          </Karte>
        ) : null}
      </div>
    </Seite>
  );
}
