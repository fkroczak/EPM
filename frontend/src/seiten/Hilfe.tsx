/**
 * Hilfe (S15, Entwurf 2 „Hilfe“): Abschnitte nach den tatsächlichen Rechten der Person, mitgeliefert mit der EPM-Version,
 * darunter eigene Ergänzungen der Stiftung (mit Historie; bearbeiten mit „Vorlagen pflegen“). Das „?“ jeder Seite führt
 * mit ``?seite=<Pfad>`` hierher und öffnet den passenden Abschnitt.
 */
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { zeitpunkt } from "@/lib/format";
import { Seite } from "@/components/layout/Shell";
import { Chip, Fehleranzeige, Karte, Knopf, Laden, Leer, Seitenkopf, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Editor, Richtext, klartext } from "@/components/Editor";

type Ergaenzung = { text: string; geaendert_am: string | null; geaendert_von: string | null; versionen: number };
type Abschnitt = { id: string; titel: string; seiten: string[]; html: string; ergaenzung: Ergaenzung | null };
type Gruppe = { id: string; titel: string; abschnitte: Abschnitt[] };
type Antwort = { version: string | null; darf_ergaenzen: boolean; gruppen: Gruppe[] };
type Fassung = { version: number; zeitpunkt: string; person: string | null; text: string };

/** Abschnitt zur Adresse einer Seite: längstes passendes Muster gewinnt (":id" = Nummer) */
function abschnittFuer(gruppen: Gruppe[], pfad: string): string | null {
  let best: [number, string] | null = null;
  for (const g of gruppen) {
    for (const a of g.abschnitte) {
      for (const muster of a.seiten) {
        const re = new RegExp(`^${muster.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/:id/g, "\\d+")}/?$`);
        if (re.test(pfad) && (!best || muster.length > best[0])) best = [muster.length, a.id];
      }
    }
  }
  if (best) return best[1];
  // Unterseiten ohne eigenen Abschnitt: nächsthöhere Seite
  const oben = pfad.replace(/\/[^/]+\/?$/, "");
  return oben && oben !== pfad ? abschnittFuer(gruppen, oben) : null;
}

function HistorieDialog({ abschnitt, onZu }: { abschnitt: Abschnitt | null; onZu: () => void }) {
  const fassungen = useQuery({
    queryKey: ["hilfe", abschnitt?.id, "versionen"],
    queryFn: () => api<Fassung[]>(`hilfe/${abschnitt!.id}/ergaenzung/versionen/`),
    enabled: !!abschnitt,
  });
  return (
    <Dialog offen={!!abschnitt} onOffen={(o) => { if (!o) onZu(); }} titel={`Historie: ${abschnitt?.titel ?? ""}`} breite={680}
      beschreibung="Alle Fassungen der Ergänzung, neueste zuerst. Jede Änderung steht auch im Audit-Log.">
      {fassungen.isLoading ? <Laden /> : <Fehleranzeige fehler={fassungen.error} />}
      <ol className="m-0 p-0 list-none flex flex-col gap-3" data-testid="hilfe-historie">
        {(fassungen.data ?? []).map((f) => (
          <li key={f.version} className="border border-rand rounded-lg px-3.5 py-2.5 flex flex-col gap-1.5">
            <span className="text-[0.8125rem] gedaempft">Fassung {f.version} · {zeitpunkt(f.zeitpunkt)} · {f.person ?? "—"}</span>
            {f.text ? <Richtext html={f.text} className="text-sm" /> : <span className="text-sm gedaempft">(entfernt)</span>}
          </li>
        ))}
      </ol>
    </Dialog>
  );
}

function ErgaenzungKarte({ abschnitt, darf }: { abschnitt: Abschnitt; darf: boolean }) {
  const [bearbeiten, setBearbeiten] = useState(false);
  const [text, setText] = useState("");
  const [historie, setHistorie] = useState(false);
  const qc = useQueryClient();
  const melden = useHinweis();
  const e = abschnitt.ergaenzung;
  const speichern = useMutation({
    mutationFn: () => api<{ ergaenzung: Ergaenzung | null }>(`hilfe/${abschnitt.id}/ergaenzung/`, { method: "PUT", body: { text } }),
    onSuccess: (antwort) => {
      void qc.invalidateQueries({ queryKey: ["hilfe"] });
      melden(antwort.ergaenzung?.text ? "Ergänzung gespeichert." : "Ergänzung entfernt.");
      setBearbeiten(false);
    },
  });
  if (!e?.text && !darf && !e?.versionen) return null;
  return (
    <section aria-labelledby="h-ergaenzung" className="border border-akzent/30 rounded-xl px-4 py-3.5 flex flex-col gap-2 bg-grund"
      data-testid="hilfe-ergaenzung">
      <div className="flex justify-between items-center gap-2.5 flex-wrap">
        <h2 id="h-ergaenzung" className="m-0 text-[0.9375rem] font-semibold">Ergänzung der Stiftung</h2>
        <span className="flex gap-2 items-center">
          {e?.versionen ? <button type="button" className="bg-transparent border-0 p-0 text-[0.8125rem] text-akzent-text cursor-pointer"
            onClick={() => setHistorie(true)}>Historie ({e.versionen})</button> : null}
          {darf && !bearbeiten ? <Knopf klein icon="stift" onClick={() => { setText(e?.text ?? ""); setBearbeiten(true); }}>
            {e?.text ? "Bearbeiten" : "Ergänzen"}</Knopf> : null}
        </span>
      </div>
      {bearbeiten ? (
        <>
          <Editor wert={text} onAenderung={setText} label="Ergänzung der Stiftung" hoehe={140} autofokus
            platzhalter="z. B. interne Abläufe, Telefonnummern, Ansprechpartner" />
          <span className="text-xs gedaempft">Formatierung wird beim Speichern bereinigt. Leer speichern entfernt die Ergänzung; frühere Fassungen bleiben in der Historie.</span>
          <Fehleranzeige fehler={speichern.error} />
          <div className="flex gap-2">
            <Knopf klein variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf>
            <Knopf klein onClick={() => setBearbeiten(false)}>Abbrechen</Knopf>
          </div>
        </>
      ) : e?.text ? <Richtext html={e.text} className="text-[0.90625rem] leading-relaxed text-text2" />
        : <span className="text-sm gedaempft">Noch keine Ergänzung.</span>}
      {e?.text && e.geaendert_am ? <span className="text-xs gedaempft">{e.geaendert_von ?? "—"} · zuletzt geändert {zeitpunkt(e.geaendert_am)}
        {darf ? "" : " · bearbeiten mit dem Recht „Vorlagen pflegen“"}</span> : null}
      <HistorieDialog abschnitt={historie ? abschnitt : null} onZu={() => setHistorie(false)} />
    </section>
  );
}

export function Hilfe() {
  const [params, setParams] = useSearchParams();
  const [suche, setSuche] = useState("");
  const daten = useQuery({ queryKey: ["hilfe"], queryFn: () => api<Antwort>("hilfe/") });
  const d = daten.data;
  const alle = useMemo(() => (d?.gruppen ?? []).flatMap((g) => g.abschnitte.map((a) => ({ ...a, gruppe: g.titel }))), [d]);
  const gewaehlt = useMemo(() => {
    if (!d) return null;
    const id = params.get("abschnitt") ?? (params.get("seite") ? abschnittFuer(d.gruppen, params.get("seite")!) : null);
    return alle.find((a) => a.id === id) ?? alle[0] ?? null;
  }, [d, alle, params]);
  const begriff = suche.trim().toLowerCase();
  const treffer = begriff ? alle.filter((a) => `${a.titel} ${klartext(a.html)} ${a.ergaenzung ? klartext(a.ergaenzung.text) : ""}`
    .toLowerCase().includes(begriff)) : [];
  const waehle = (id: string) => { setParams(new URLSearchParams({ abschnitt: id }), { replace: true }); setSuche(""); };

  return (
    <Seite pfad={[{ text: "Hilfe" }]}>
      <Seitenkopf titel="Hilfe"
        unter={`Abschnitte passend zu deinen Rechten${d?.darf_ergaenzen ? " · Ergänzungen schreiben mit „Vorlagen pflegen“" : ""}`}
        rechts={
          <label className="relative w-[21.25rem] max-w-full block">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" groesse={18} /></span>
            <input className="inp pl-10" type="search" aria-label="In der Hilfe suchen" placeholder="In der Hilfe suchen" value={suche}
              onChange={(e) => setSuche(e.target.value)} />
          </label>
        } />
      {daten.isLoading ? <Laden /> : <Fehleranzeige fehler={daten.error} />}
      {d ? (
        <div className="stapel grid grid-cols-1 hd:grid-cols-[16.25rem_minmax(0,1fr)] fhd:grid-cols-[18.75rem_minmax(0,1fr)] gap-6 items-start">
          <nav aria-label="Inhalt der Hilfe" className="card p-2 flex flex-col gap-1 hd:sticky hd:top-4 hd:max-h-[calc(100vh-2rem)] hd:overflow-auto"
            data-testid="hilfe-inhalt">
            {begriff ? (
              <>
                <span className="text-xs font-semibold gedaempft px-2 pt-2 pb-0.5 uppercase tracking-[.04em]">Treffer ({treffer.length})</span>
                {treffer.length === 0 ? <span className="text-sm gedaempft px-2 py-1">Nichts gefunden.</span> : treffer.map((a) => (
                  <button key={a.id} type="button" className="nav text-left border-0 bg-transparent cursor-pointer h-auto py-1.5 flex-col items-start gap-0"
                    onClick={() => waehle(a.id)}><span className="text-[0.84375rem]">{a.titel}</span><span className="text-xs gedaempft">{a.gruppe}</span></button>
                ))}
              </>
            ) : d.gruppen.map((g) => (
              <div key={g.id} className="flex flex-col gap-0.5">
                <span className="text-xs font-semibold gedaempft px-2 pt-2 pb-0.5 uppercase tracking-[.04em]">{g.titel}</span>
                {g.abschnitte.map((a) => (
                  <button key={a.id} type="button" aria-current={gewaehlt?.id === a.id ? "page" : undefined}
                    className={cx("nav text-left border-0 bg-transparent cursor-pointer h-[1.875rem] text-[0.84375rem]", gewaehlt?.id === a.id && "aktiv")}
                    onClick={() => waehle(a.id)}>{a.titel}</button>
                ))}
              </div>
            ))}
          </nav>
          {gewaehlt ? (
            <Karte className="px-7 py-6 flex flex-col gap-3.5 max-w-[53.75rem]" data-testid="hilfe-abschnitt">
              <div className="flex justify-between items-center gap-3 flex-wrap">
                <span className="text-[0.8125rem] gedaempft">{gewaehlt.gruppe}</span>
                <Chip><Icon name="buch" groesse={12} />mitgeliefert · EPM {d.version ?? "Entwicklungsstand"}</Chip>
              </div>
              <h1 className="m-0 text-2xl font-semibold" data-testid="hilfe-titel">{gewaehlt.titel}</h1>
              <div className="richtext hilfe-text text-[0.9375rem] leading-relaxed" dangerouslySetInnerHTML={{ __html: gewaehlt.html }} />
              <ErgaenzungKarte key={gewaehlt.id} abschnitt={gewaehlt} darf={d.darf_ergaenzen} />
            </Karte>
          ) : <Leer>Keine Abschnitte.</Leer>}
        </div>
      ) : null}
    </Seite>
  );
}
