/**
 * Vorlagen › Auswahllisten: Präparate für die Infusionspläne und die übrigen Auswahllisten (Katheter, Terminorte …).
 * Reihenfolge per Ziehen, Pfeiltasten am Griff oder ▲ ▼ (Tablet); ausblenden statt löschen. Je Liste steht, wo sie in
 * EPM zur Auswahl kommt (Vorlagen-Portal einfacher, F180).
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { zahl } from "@/lib/format";
import type { Auswahlwert, Praeparat } from "@/lib/typen";
import { Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { Erklaerung } from "@/components/ui/erklaerung";
import { useHinweis } from "@/components/ui/hinweise";
import { useSortierbar, verschiebe } from "@/components/ui/sortierbar";

export type Liste = { schluessel: string; titel: string; art: "praeparat" | "auswahl"; wo: string };
const IM_PLAN = "Im Infusionsplan zur Auswahl";
export const LISTEN: Liste[] = [
  { schluessel: "aminosaeuren", titel: "Aminosäuren", art: "praeparat", wo: `${IM_PLAN} bei „Aminosäuren“.` },
  { schluessel: "lipide", titel: "Lipide", art: "praeparat", wo: `${IM_PLAN} bei „Lipide“.` },
  { schluessel: "basisloesung", titel: "Basislösungen", art: "praeparat", wo: `${IM_PLAN} beim Zusatzvolumen (Basislösung).` },
  { schluessel: "glucose", titel: "Glucose", art: "praeparat", wo: `${IM_PLAN} bei „Glucose“.` },
  { schluessel: "albumin", titel: "Albumin", art: "praeparat", wo: `${IM_PLAN} bei „Humanalbumin“.` },
  { schluessel: "spurenelemente", titel: "Spurenelemente", art: "praeparat", wo: `${IM_PLAN} bei „Spurenelemente“.` },
  { schluessel: "vitamine", titel: "Vitamine", art: "praeparat", wo: `${IM_PLAN} bei „Vitamine“.` },
  { schluessel: "katheterschutz", titel: "Katheterblock", art: "praeparat", wo: `${IM_PLAN} beim Katheterblock.` },
  { schluessel: "elektrolyte", titel: "Elektrolytzusätze", art: "praeparat", wo: `${IM_PLAN} bei den Elektrolyten.` },
  { schluessel: "medikament", titel: "Medikamente", art: "praeparat", wo: `${IM_PLAN} unter den weiteren Bestandteilen.` },
  { schluessel: "sonstiges", titel: "Sonstige Bestandteile", art: "praeparat", wo: `${IM_PLAN} unter den weiteren Bestandteilen.` },
  { schluessel: "katheter", titel: "Katheter", art: "auswahl", wo: "Akte › Stammdaten (Katheter) und Akte › Katheter (Typ); steht auf dem Patientendatenblatt." },
  { schluessel: "terminort", titel: "Terminorte", art: "auswahl", wo: "Beim Anlegen eines Termins (Ort) und im Kalender bei der Ankündigung." },
  { schluessel: "dokumenttyp", titel: "Dokumenttypen", art: "auswahl", wo: "Beim Hochladen eines Dokuments in die Akte (Art des Dokuments)." },
  { schluessel: "kontaktart", titel: "Kontaktarten", art: "auswahl", wo: "Beim Erfassen eines Kontakts (Telefon, E-Mail, Besuch …)." },
  { schluessel: "beziehung", titel: "Beziehungen (Bezugspersonen)", art: "auswahl", wo: "Akte › Kontaktdaten › Bezugspersonen (Ehefrau, Sohn …)." },
  { schluessel: "berichtart", titel: "Berichtsarten", art: "auswahl", wo: "Akte › Berichte › „Neuer Bericht“ (Art des Berichts)." },
  // Katheter-Historie (F192, 15.10.2026)
  { schluessel: "katheter_entfernung", titel: "Katheter: Entfernungsgründe", art: "auswahl",
    wo: "Akte › Katheter › „Entfernen“ bzw. „Entfernt am“ (Grund der Entfernung)." },
  { schluessel: "katheter_komplikation", titel: "Katheter: Komplikationen", art: "auswahl",
    wo: "Akte › Katheter › „Komplikation“ (Art). Werte mit „Infektion“ im Namen zählen für die Kennzahl „Infektionen je 1000 Kathetertage“." },
];

const anzeige = (e: Praeparat | Auswahlwert) => ("name" in e ? e.anzeige : e.wert);

function EintragDialog({ liste, eintrag, onZu }: { liste: Liste; eintrag: Praeparat | Auswahlwert | null | "neu"; onZu: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [name, setName] = useState("");
  const [konz, setKonz] = useState("");
  const [einheit, setEinheit] = useState("ml");
  const [hinweis, setHinweis] = useState("");
  useEffect(() => {
    if (eintrag && eintrag !== "neu") {
      if ("kategorie" in eintrag) {
        setName(eintrag.name); setKonz(eintrag.konzentration); setEinheit(eintrag.einheit); setHinweis(eintrag.hinweis ?? "");
      } else setName(eintrag.wert);
    } else { setName(""); setKonz(""); setEinheit("ml"); setHinweis(""); }
  }, [eintrag]);
  const speichern = useMutation({
    mutationFn: () => {
      const neu = eintrag === "neu";
      if (liste.art === "praeparat") {
        const daten = { name, konzentration: konz, einheit, hinweis, ...(neu ? { kategorie: liste.schluessel } : {}) };
        return neu ? api("praeparate/", { body: daten }) : api(`praeparate/${(eintrag as Praeparat).id}/`, { method: "PATCH", body: daten });
      }
      return neu ? api("auswahlwerte/", { body: { liste: liste.schluessel, wert: name } })
        : api(`auswahlwerte/${(eintrag as Auswahlwert).id}/`, { method: "PATCH", body: { wert: name } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [liste.art === "praeparat" ? "praeparate" : "auswahlwerte"] });
      melden(eintrag === "neu" ? `„${name}“ gespeichert – steht ab sofort zur Auswahl.` : "Gespeichert.");
      onZu();
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={!!eintrag} onOffen={(o) => { if (!o) onZu(); }} titel={`${liste.titel}: ${eintrag === "neu" ? "neuer Eintrag" : "bearbeiten"}`} breite={520}
      beschreibung="Änderungen gelten für neue Einträge und Pläne; bestehende Pläne behalten ihre Werte."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf><Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf></>}>
      <form className="grid grid-cols-3 gap-3" onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        <Feld label={liste.art === "praeparat" ? "Name" : "Wert"} className="col-span-3" fehler={f.name ?? f.wert ?? f.non_field_errors}>
          {(p) => <Eingabe {...p} value={name} onChange={(e) => setName(e.target.value)} autoFocus />}
        </Feld>
        {liste.art === "praeparat" ? <>
          <Feld label="Konzentration" hinweis="z. B. 13,4 %" className="col-span-2" fehler={f.konzentration}>{(p) => <Eingabe {...p} value={konz} onChange={(e) => setKonz(e.target.value)} />}</Feld>
          <Feld label="Einheit" fehler={f.einheit}>{(p) => <Eingabe {...p} value={einheit} onChange={(e) => setEinheit(e.target.value)} />}</Feld>
          {/* Hinweis zum Praeparat (F111), z. B. reines Taurolidin 2 % oder baugleich zu Cernevit */}
          <Feld label="Hinweis" className="col-span-3" hinweis="erscheint bei der Auswahl und auf der Plan-PDF" fehler={f.hinweis}>
            {(p) => <Eingabe {...p} maxLength={200} value={hinweis} onChange={(e) => setHinweis(e.target.value)} />}
          </Feld>
        </> : null}
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler" className="col-span-3">{speichern.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

/** ``liste``: Schlüssel der gewählten Liste (aus der Adresse, z. B. von der Übersicht oder der Suche) */
export function ListenBereich({ liste, onListe }: { liste: string | null; onListe: (schluessel: string) => void }) {
  const gewaehlt = LISTEN.find((l) => l.schluessel === liste) ?? LISTEN[0];
  const [dialog, setDialog] = useState<Praeparat | Auswahlwert | null | "neu">(null);
  const [filter, setFilter] = useState("");
  const qc = useQueryClient();
  const melden = useHinweis();
  const praeparate = useQuery({ queryKey: ["praeparate", "alle"], queryFn: () => api<Praeparat[]>("praeparate/") });
  const auswahl = useQuery({ queryKey: ["auswahlwerte", "verwaltung"], queryFn: () => api<Auswahlwert[]>("auswahlwerte/") });
  const eintraege: (Praeparat | Auswahlwert)[] = gewaehlt.art === "praeparat"
    ? (praeparate.data ?? []).filter((p) => p.kategorie === gewaehlt.schluessel)
    : (auswahl.data ?? []).filter((a) => a.liste === gewaehlt.schluessel);
  const [reihe, setReihe] = useState<(Praeparat | Auswahlwert)[]>([]);
  const signatur = eintraege.map((e) => `${e.id}:${e.reihenfolge}:${e.aktiv}:${anzeige(e)}`).join("|");
  useEffect(() => setReihe(eintraege), [signatur, gewaehlt.schluessel]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => setFilter(""), [gewaehlt.schluessel]);
  const pfad = gewaehlt.art === "praeparat" ? "praeparate" : "auswahlwerte";
  const neuLaden = () => {
    void qc.invalidateQueries({ queryKey: ["praeparate"] });
    void qc.invalidateQueries({ queryKey: ["auswahlwerte"] });
  };
  const reihenfolge = useMutation({
    mutationFn: (ids: number[]) => api(`${pfad}/reihenfolge/`, { body: { ids } }),
    onSuccess: () => { neuLaden(); melden("Reihenfolge gespeichert."); },
  });
  const aktiv = useMutation({
    mutationFn: (e: Praeparat | Auswahlwert) => api(`${pfad}/${e.id}/`, { method: "PATCH", body: { aktiv: !e.aktiv } }),
    // Häkchen sofort umschalten; bei einem Fehler den gespeicherten Stand wieder anzeigen
    onMutate: (e) => setReihe((r) => r.map((x) => (x.id === e.id ? { ...x, aktiv: !e.aktiv } : x))),
    onSuccess: (_d, e) => melden(e.aktiv ? `„${anzeige(e)}“ ausgeblendet – wird bei neuen Eingaben nicht mehr angeboten.` : `„${anzeige(e)}“ wird wieder angeboten.`),
    onError: (_f, e) => setReihe((r) => r.map((x) => (x.id === e.id ? { ...x, aktiv: e.aktiv } : x))),
    onSettled: () => neuLaden(),
  });
  const ordnen = (neu: (Praeparat | Auswahlwert)[]) => { setReihe(neu); reihenfolge.mutate(neu.map((e) => e.id)); };
  const sort = useSortierbar(reihe, ordnen);
  const anzahl = (l: Liste) => l.art === "praeparat" ? (praeparate.data ?? []).filter((p) => p.kategorie === l.schluessel).length
    : (auswahl.data ?? []).filter((a) => a.liste === l.schluessel).length;
  const suche = filter.trim().toLocaleLowerCase("de");
  // beim Suchen ohne Ziehen und ▲ ▼: die Reihenfolge bezieht sich immer auf die ganze Liste
  const sichtbar = reihe.map((e, i) => ({ e, i })).filter(({ e }) => !suche || anzeige(e).toLocaleLowerCase("de").includes(suche));
  const navKnopf = (l: Liste) => (
    <button key={l.schluessel} type="button" aria-current={gewaehlt.schluessel === l.schluessel ? "true" : undefined}
      className={cx("flex items-center justify-between px-3 py-2 rounded-md border-0 cursor-pointer text-sm text-left", gewaehlt.schluessel === l.schluessel ? "bg-akzent-weich text-akzent-text font-medium" : "bg-transparent hover:bg-fein")}
      onClick={() => onListe(l.schluessel)}>
      <span>{l.titel}</span><span className="num text-xs gedaempft">{anzahl(l)}</span>
    </button>
  );
  const pfeil = "w-7 h-7 p-0 border border-rand rounded-md bg-flaeche text-[0.75rem] leading-none cursor-pointer gedaempft hover:text-tinte disabled:opacity-30 disabled:cursor-default";
  return (
    <div className="stapel grid grid-cols-1 xl:grid-cols-[16.25rem_minmax(0,1fr)] gap-5 items-start">
      <nav aria-label="Listen" className="card p-1.5 flex flex-col">
        <span className="lbl px-3 pt-2 pb-1">Präparate für Infusionspläne</span>
        {LISTEN.filter((l) => l.art === "praeparat").map(navKnopf)}
        <span className="lbl px-3 pt-3 pb-1 border-t border-rand mt-1.5">Weitere Auswahllisten</span>
        {LISTEN.filter((l) => l.art === "auswahl").map(navKnopf)}
      </nav>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3" data-testid="liste">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex flex-col gap-1 min-w-0">
            <h2 className="lbl m-0">{gewaehlt.titel} · {gewaehlt.art === "praeparat" ? "Präparate" : "Auswahlwerte"}</h2>
            <span className="text-[0.8125rem] gedaempft" data-testid="liste-wo"><strong className="font-medium text-text2">Wo benutzt:</strong> {gewaehlt.wo}</span>
          </div>
          <Knopf klein icon="plus" onClick={() => setDialog("neu")}>{gewaehlt.art === "praeparat" ? "Neues Präparat" : "Neuer Wert"}</Knopf>
        </div>
        {reihe.length > 8 ? (
          <Eingabe type="search" aria-label="In dieser Liste suchen" placeholder="In dieser Liste suchen …" value={filter}
            onChange={(e) => setFilter(e.target.value)} className="max-w-[20rem]" />
        ) : null}
        {praeparate.isLoading || auswahl.isLoading ? <Laden /> : (
          <table className="tabelle">
            <thead><tr><th className="th w-10" /><th className="th">Name</th>{gewaehlt.art === "praeparat" ? <><th className="th">Konzentration</th><th className="th text-right">in Plänen</th></> : null}<th className="th">Auswahl</th><th className="th w-[4.5rem]"><span className="sr-only">Reihenfolge</span></th></tr></thead>
            <tbody>
              {sichtbar.map(({ e, i }) => (
                <tr key={e.id} {...(suche ? {} : sort.zeile(i))} className={cx(sort.ueber === i && "outline-2 outline-akzent", sort.zieht === i && "opacity-50", !e.aktiv && "opacity-70")}>
                  <td className="td"><button type="button" disabled={!!suche} className="border-0 bg-transparent cursor-grab gedaempft p-0 tracking-[-2px] disabled:opacity-30" {...sort.griff(i, anzeige(e), "vorlagen")}>⋮⋮</button></td>
                  <td className="td">
                    <button type="button" className="bg-transparent border-0 p-0 cursor-pointer text-left text-akzent-text font-medium" onClick={() => setDialog(e)}>
                      {anzeige(e)}
                    </button>
                  </td>
                  {"name" in e ? <><td className="td num">{e.konzentration || "—"}</td><td className="td num text-right">{zahl(e.in_plaenen)}</td></> : null}
                  <td className="td">
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input type="checkbox" checked={e.aktiv} aria-label={`${anzeige(e)} in der Auswahl`} onChange={() => aktiv.mutate(e)} />
                      {e.aktiv ? "wird angeboten" : "ausgeblendet"}
                    </label>
                  </td>
                  <td className="td">
                    {/* ▲ ▼ für Tablet und Telefon, wo Ziehen schwer geht */}
                    <span className="flex gap-1">
                      <button type="button" className={pfeil} aria-label={`${anzeige(e)} nach oben`} disabled={!!suche || i === 0}
                        onClick={() => ordnen(verschiebe(reihe, i, i - 1))}>▲</button>
                      <button type="button" className={pfeil} aria-label={`${anzeige(e)} nach unten`} disabled={!!suche || i === reihe.length - 1}
                        onClick={() => ordnen(verschiebe(reihe, i, i + 1))}>▼</button>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {suche && !sichtbar.length ? <span className="text-sm gedaempft">Kein Eintrag enthält „{filter}“.</span> : null}
        <Fehleranzeige fehler={reihenfolge.error ?? aktiv.error} />
        <div className="text-[0.8125rem] gedaempft leading-normal flex items-start gap-2">
          <span>Reihenfolge mit ▲ ▼, per Ziehen am Griff ⋮⋮ oder mit den Pfeiltasten – so erscheint die Liste auch bei der Auswahl.
            Nicht mehr benötigte Einträge <strong className="font-medium text-text2">ausblenden</strong> statt löschen.</span>
          <Erklaerung titel="Ausblenden statt löschen">
            Ein ausgeblendeter Eintrag wird bei neuen Plänen, Terminen und Akten nicht mehr angeboten. Wo er schon steht, bleibt er
            unverändert stehen – auch auf alten PDFs. Gelöscht wird nichts; das Häkchen lässt sich jederzeit wieder setzen.
          </Erklaerung>
        </div>
      </Karte>
      <EintragDialog liste={gewaehlt} eintrag={dialog} onZu={() => setDialog(null)} />
    </div>
  );
}
