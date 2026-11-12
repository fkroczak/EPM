/** Vorlagen › KI-Prompts (12.11.2026): feste Anweisungen für den KI-Chat (KI (Experimentell) › Chat). Sie stehen hinter
 *  dem festen Sicherheitsrahmen (nichts erfinden, keine Diagnose …) und machen die Ergebnisse gleichbleibend. */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { datum } from "@/lib/format";
import { Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import type { KiPromptvorlage } from "@/seiten/ki/KiChat";

type Entwurf = { name: string; beschreibung: string; anweisung: string; temperatur: string; aktiv: boolean; reihenfolge: number };
const LEER: Entwurf = { name: "", beschreibung: "", anweisung: "", temperatur: "0.10", aktiv: true, reihenfolge: 100 };

export function KiPromptsBereich() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const liste = useQuery({ queryKey: ["ki", "vorlagen", "alle"], queryFn: () => api<KiPromptvorlage[]>("ki/vorlagen/?alle=1") });
  const [gewaehlt, setGewaehlt] = useState<number | "neu" | null>(null);
  const [e, setE] = useState<Entwurf>(LEER);
  const vorlage = typeof gewaehlt === "number" ? liste.data?.find((v) => v.id === gewaehlt) : undefined;
  useEffect(() => {
    if (gewaehlt === null && liste.data?.length) setGewaehlt(liste.data[0].id);
  }, [liste.data, gewaehlt]);
  useEffect(() => {
    if (gewaehlt === "neu") setE(LEER);
    else if (vorlage) setE({ name: vorlage.name, beschreibung: vorlage.beschreibung, anweisung: vorlage.anweisung,
      temperatur: vorlage.temperatur, aktiv: vorlage.aktiv, reihenfolge: vorlage.reihenfolge });
  }, [gewaehlt, vorlage?.geaendert_am]);
  const fertig = (text: string) => { void qc.invalidateQueries({ queryKey: ["ki", "vorlagen"] }); melden(text); };
  const speichern = useMutation({
    mutationFn: () => {
      const body = { ...e, temperatur: e.temperatur.replace(",", ".") };
      return gewaehlt === "neu" ? api<KiPromptvorlage>("ki/vorlagen/", { body })
        : api<KiPromptvorlage>(`ki/vorlagen/${gewaehlt}/`, { method: "PATCH", body });
    },
    onSuccess: (v) => { setGewaehlt(v.id); fertig("KI-Prompt gespeichert."); },
  });
  const loeschen = useMutation({
    mutationFn: (id: number) => api(`ki/vorlagen/${id}/`, { method: "DELETE" }),
    onSuccess: () => { setGewaehlt(null); fertig("KI-Prompt gelöscht."); },
  });
  const f = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  if (liste.isLoading) return <Laden />;
  return (
    <div className="stapel grid grid-cols-1 xl:grid-cols-[20rem_minmax(0,1fr)] gap-5 items-start" data-testid="ki-prompts">
      <Karte className="px-3 py-3 flex flex-col gap-2">
        <Knopf icon="plus" onClick={() => setGewaehlt("neu")}>Neuer KI-Prompt</Knopf>
        <ul className="m-0 p-0 list-none flex flex-col gap-0.5" aria-label="KI-Prompts">
          {(liste.data ?? []).map((v) => (
            <li key={v.id}>
              <button type="button" onClick={() => setGewaehlt(v.id)} aria-current={v.id === gewaehlt || undefined}
                className={cx("w-full text-left rounded-md px-2 py-1.5 hover:bg-fein text-sm", v.id === gewaehlt && "bg-akzent-weich")}>
                {v.name} {v.aktiv ? null : <Chip>ausgeblendet</Chip>}
              </button>
            </li>
          ))}
        </ul>
        <Fehleranzeige fehler={liste.error} />
      </Karte>
      <Karte className="px-5 py-[1.125rem] flex flex-col gap-3">
        <h2 className="lbl m-0">{gewaehlt === "neu" ? "Neuer KI-Prompt" : vorlage?.name ?? "KI-Prompt"}</h2>
        <span className="text-[0.8125rem] gedaempft">Steht im Chat unter „KI (Experimentell)“ zur Wahl. Vor jeder Anweisung gilt ein fester
          Rahmen: nichts erfinden, Zahlen und Daten exakt übernehmen, Unklares mit [?] markieren, keine eigenen Diagnosen oder Empfehlungen.
          Tipp für zuverlässige Ergebnisse: Aufgabe genau beschreiben, sagen, was gleich bleiben muss, und das Ausgabeformat festlegen.</span>
        <Feld label="Name" fehler={f.name} pflicht>
          {(p) => <Eingabe {...p} value={e.name} maxLength={100} onChange={(x) => setE({ ...e, name: x.target.value })} />}
        </Feld>
        <Feld label="Wofür? (kurz)" fehler={f.beschreibung}>
          {(p) => <Eingabe {...p} value={e.beschreibung} maxLength={300} onChange={(x) => setE({ ...e, beschreibung: x.target.value })} />}
        </Feld>
        <Feld label="Anweisung an die KI" fehler={f.anweisung} pflicht hinweis={`${e.anweisung.length} / 4000 Zeichen`}>
          {(p) => <Textfeld {...p} rows={9} value={e.anweisung} maxLength={4000} onChange={(x) => setE({ ...e, anweisung: x.target.value })} />}
        </Feld>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Feld label="Temperatur (0–1)" fehler={f.temperatur} hinweis="0,1 = gleichbleibend; höher = freier formuliert">
            {(p) => <Eingabe {...p} className="num" inputMode="decimal" value={e.temperatur} onChange={(x) => setE({ ...e, temperatur: x.target.value })} />}
          </Feld>
          <Feld label="Reihenfolge" fehler={f.reihenfolge}>
            {(p) => <Eingabe {...p} className="num" inputMode="numeric" value={String(e.reihenfolge)}
              onChange={(x) => setE({ ...e, reihenfolge: Number(x.target.value.replace(/\D/g, "")) || 0 })} />}
          </Feld>
          <label className="flex items-center gap-2 text-sm self-end pb-2">
            <input type="checkbox" checked={e.aktiv} onChange={(x) => setE({ ...e, aktiv: x.target.checked })} /> im Chat anbieten
          </label>
        </div>
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
        {loeschen.error ? <Meldung art="fehler">{loeschen.error instanceof ApiFehler ? Object.values(loeschen.error.felder)[0] || loeschen.error.message : String(loeschen.error)}</Meldung> : null}
        <div className="flex items-center gap-3 flex-wrap">
          <Knopf variante="pri" laedt={speichern.isPending} disabled={!e.name.trim() || !e.anweisung.trim()} onClick={() => speichern.mutate()}>Speichern</Knopf>
          {vorlage && !vorlage.mitgeliefert ? <Knopf variante="dng" laedt={loeschen.isPending}
            onClick={() => { if (window.confirm(`KI-Prompt „${vorlage.name}“ löschen?`)) loeschen.mutate(vorlage.id); }}>Löschen</Knopf> : null}
          {vorlage ? <span className="text-xs gedaempft">{vorlage.mitgeliefert ? "mitgeliefert · " : ""}geändert {datum(vorlage.geaendert_am)}
            {vorlage.geaendert_von_name ? ` von ${vorlage.geaendert_von_name}` : ""}</span> : null}
        </div>
      </Karte>
    </div>
  );
}
