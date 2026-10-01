/**
 * Gemeinsame Ärzteliste (Festlegung 01.10.2026): Praxis mit Kontaktdaten einmal pflegen, beim Patienten mit Rolle
 * zuordnen (Hausarzt, Facharzt …). Eine geänderte Telefonnummer gilt so in jeder Akte. Nie löschen, nur deaktivieren.
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
import { Anzeige, Chip, Eingabe, Feld, Fehleranzeige, Karte, Knopf, Laden, Leer, Meldung, Seitenkopf, Segmente, Textfeld, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";

type Filter = "aktiv" | "inaktiv" | "alle";
const FELDER = ["name", "praxis", "fachrichtung", "strasse", "plz", "ort", "telefon", "fax", "email", "notiz"] as const;
type Formular = Record<(typeof FELDER)[number], string>;
const LEER: Formular = { name: "", praxis: "", fachrichtung: "", strasse: "", plz: "", ort: "", telefon: "", fax: "", email: "", notiz: "" };

function formularVon(a: Arzt | undefined): Formular {
  if (!a) return { ...LEER };
  return Object.fromEntries(FELDER.map((k) => [k, a[k] ?? ""])) as Formular;
}

function ZugeordnetePatienten({ arzt }: { arzt: Arzt }) {
  const patienten = useQuery({
    queryKey: ["aerzte", arzt.id, "patienten"],
    queryFn: () => api<PatientZeile[]>(`aerzte/${arzt.id}/patienten/`),
  });
  return (
    <div className="flex flex-col gap-2.5 border-t border-rand pt-3.5">
      <h3 className="lbl m-0">Patienten in Betreuung</h3>
      {patienten.isLoading ? <Laden /> : (patienten.data ?? []).length ? (
        <ul className="m-0 p-0 list-none flex flex-col" data-testid="arzt-patienten">
          {patienten.data!.map((p) => (
            <li key={p.id} className="py-1.5 border-b border-rand last:border-b-0 text-sm flex gap-3">
              <span className="num gedaempft">{nummer(p.nummer)}</span>
              <Link to={`/patienten/${p.id}`}>{p.nachname}, {p.vorname}</Link>
              {p.ist_test ? <Chip art="warn">Testpatient</Chip> : null}
            </li>
          ))}
        </ul>
      ) : <span className="text-sm gedaempft">Keinem Patienten in Betreuung zugeordnet.</span>}
    </div>
  );
}

export function Aerzte() {
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("aktiv");
  const [suche, setSuche] = useState("");
  const liste = useAerzteListe();
  const { darf } = useAuth();
  const pflegen = darf("versorger_pflegen");
  const neu = params.get("neu") === "1";
  const alle = liste.data ?? [];
  const wort = suche.trim().toLowerCase();
  const sichtbar = alle
    .filter((a) => filter === "alle" || (filter === "aktiv") === a.aktiv)
    .filter((a) => !wort || [a.name, a.praxis, a.fachrichtung, a.ort].some((t) => t.toLowerCase().includes(wort)));
  const gewaehltId = Number(params.get("id")) || sichtbar[0]?.id;
  const cur = neu ? undefined : alle.find((a) => a.id === gewaehltId);
  const [f, setF] = useState<Formular>({ ...LEER });
  const qc = useQueryClient();
  const melden = useHinweis();

  // Formular nur beim Wechsel neu füllen (ein Neuladen im Hintergrund verwirft keine Eingaben)
  // (nicht beim ersten Laden der Liste: sonst ging eine schon begonnene Eingabe bei „Neu“ verloren)
  useEffect(() => setF(formularVon(cur)), [cur?.id, neu]); // eslint-disable-line react-hooks/exhaustive-deps

  const waehlen = (id: number) => setParams(new URLSearchParams({ id: String(id) }), { replace: true });
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
      if (!cur) waehlen(a.id);
    },
  });
  const aktivSetzen = useMutation({
    mutationFn: (aktiv: boolean) => api<Arzt>(`aerzte/${cur!.id}/`, { method: "PATCH", body: { aktiv } }),
    onSuccess: (a) => {
      neuLaden();
      melden(a.aktiv ? "Arzt wieder aktiv." : "Arzt deaktiviert.");
      setFilter(a.aktiv ? "aktiv" : "inaktiv");
    },
  });
  const fehler: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const geaendert = FELDER.some((k) => f[k] !== formularVon(cur)[k]);

  const feld = (k: (typeof FELDER)[number], label: string, extra?: { num?: boolean; span?: boolean; typ?: string; hinweis?: string }) => !pflegen ? (
    <Anzeige label={label} className={extra?.span ? "col-span-2" : undefined}>{f[k]}</Anzeige>
  ) : (
    <Feld label={label} className={extra?.span ? "col-span-2" : undefined} fehler={fehler[k]} pflicht={k === "name"} hinweis={extra?.hinweis}>
      {(p) => <Eingabe {...p} className={extra?.num ? "num" : undefined} type={extra?.typ} value={f[k]}
        onChange={(e) => setF({ ...f, [k]: e.target.value })} />}
    </Feld>
  );

  return (
    <Seite pfad={[{ text: "Ärzte" }]}>
      <Seitenkopf titel="Ärzte" unter="Hausärzte, Fachärzte und Kliniken mit Kontaktdaten – einmal gepflegt, in jeder Akte zugeordnet"
        rechts={<>
          <Segmente label="Filter" wert={filter} onWahl={setFilter}
            werte={[{ wert: "aktiv", text: "Aktiv" }, { wert: "inaktiv", text: "Inaktiv" }, { wert: "alle", text: "Alle" }]} />
          {pflegen ? <Knopf variante="pri" icon="plus" onClick={() => setParams(new URLSearchParams({ neu: "1" }), { replace: true })}>Neuer Arzt</Knopf> : null}
        </>} />
      <Fehleranzeige fehler={liste.error} />
      <label className="relative w-[280px] block">
        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
        <input className="inp pl-[34px]" type="search" aria-label="Ärzte filtern" placeholder="Name, Praxis, Fachrichtung, Ort"
          value={suche} onChange={(e) => setSuche(e.target.value)} />
      </label>
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-5 items-start">
        <Karte className="overflow-hidden">
          {liste.isLoading ? <Laden /> : (
            <table className="tabelle" data-testid="aerzteliste">
              <thead><tr><th className="th">Name</th><th className="th">Fachrichtung</th><th className="th">Telefon</th><th className="th text-right">Patienten</th></tr></thead>
              <tbody>
                {sichtbar.map((a) => (
                  <tr key={a.id} className={cx("cursor-pointer", !neu && a.id === gewaehltId && "gewaehlt")} onClick={() => waehlen(a.id)}>
                    <td className="td">
                      <button type="button" className="bg-transparent border-0 p-0 font-medium text-akzent-text cursor-pointer text-left"
                        aria-current={!neu && a.id === gewaehltId ? "true" : undefined} onClick={(e) => { e.stopPropagation(); waehlen(a.id); }}>
                        {a.name}
                      </button>
                      {!a.aktiv ? <Chip className="ml-2">inaktiv</Chip> : null}
                      <br /><span className="text-[0.8125rem] gedaempft">{[a.praxis, a.ort].filter(Boolean).join(" · ") || "—"}</span>
                    </td>
                    <td className="td text-text2">{a.fachrichtung || "—"}</td>
                    <td className="td num">{a.telefon || "—"}</td>
                    <td className="td num text-right">{zahl(a.patienten_anzahl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {liste.data && !sichtbar.length ? (
            <Leer>{wort ? "Kein Treffer." : filter === "inaktiv" ? "Keine deaktivierten Ärzte." : "Noch keine Ärzte angelegt."}</Leer>
          ) : null}
        </Karte>

        {cur || neu ? (
          <Karte className="px-5 py-[18px] flex flex-col gap-3.5 min-w-0" data-testid="arzt-detail">
            <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); if (pflegen) speichern.mutate(); }}>
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="m-0 text-lg font-semibold">{cur ? cur.name : "Neuer Arzt"}</h2>
                {cur ? <span className="text-[0.8125rem] gedaempft"><span className="num">{zahl(cur.patienten_anzahl)}</span> Patienten in Betreuung</span> : null}
              </div>
              <div className="grid grid-cols-2 gap-3">
                {feld("name", "Name", { span: true, hinweis: "mit Titel, z. B. „Dr. med. Anna Hausmann“" })}
                {feld("praxis", "Praxis / Klinik")}
                {feld("fachrichtung", "Fachrichtung")}
                {feld("strasse", "Straße")}
                <div className="grid grid-cols-[90px_1fr] gap-3">
                  {feld("plz", "PLZ", { num: true })}
                  {feld("ort", "Ort")}
                </div>
                {feld("telefon", "Telefon", { num: true })}
                {feld("fax", "Fax", { num: true })}
                {feld("email", "E-Mail", { span: true, typ: "email" })}
                {pflegen ? (
                  <Feld label="Notiz" className="col-span-2" fehler={fehler.notiz}>
                    {(p) => <Textfeld {...p} rows={2} value={f.notiz} onChange={(e) => setF({ ...f, notiz: e.target.value })} />}
                  </Feld>
                ) : <Anzeige label="Notiz" className="col-span-2" mehrzeilig>{f.notiz}</Anzeige>}
              </div>
              {speichern.error && !Object.keys(fehler).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
              {pflegen ? (
                <div className="flex justify-end gap-2 flex-wrap">
                  {cur && cur.aktiv ? <Knopf className="mr-auto" laedt={aktivSetzen.isPending} onClick={() => aktivSetzen.mutate(false)}>Deaktivieren</Knopf> : null}
                  {cur && !cur.aktiv ? <Knopf className="mr-auto" laedt={aktivSetzen.isPending} onClick={() => aktivSetzen.mutate(true)}>Wieder aktivieren</Knopf> : null}
                  {neu ? <Knopf onClick={() => setParams(new URLSearchParams(), { replace: true })}>Abbrechen</Knopf> : null}
                  <Knopf type="submit" variante="pri" laedt={speichern.isPending} disabled={!!cur && !geaendert}>{cur ? "Speichern" : "Arzt anlegen"}</Knopf>
                </div>
              ) : null}
            </form>
            {cur ? <ZugeordnetePatienten arzt={cur} /> : null}
            <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
              <Icon name="info" />
              <span>Ärzte werden nie gelöscht, nur deaktiviert. Ein deaktivierter Arzt ist bei neuen Zuordnungen nicht mehr
                wählbar, bleibt aber in allen Akten sichtbar.</span>
            </div>
            <span className="text-xs gedaempft">Änderungen werden mit Person und Zeitpunkt protokolliert.</span>
          </Karte>
        ) : null}
      </div>
    </Seite>
  );
}
