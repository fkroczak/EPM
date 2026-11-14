/**
 * Administration › KI › Priorisierung (14.11.2026): Reihenfolge der Arbeit im KI-Dienst und Prioritäten der Dokumente
 * (angefordert, Termin bald, neu, „Neu lesen“, Altbestand). Gespeichert in den KI-Einstellungen.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { zeitpunkt } from "@/lib/format";
import type { KiEinstellungen } from "@/lib/ki";
import { Chip, Eingabe, Feld, Fehleranzeige, Karte, KartenKopf, Knopf, Laden } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";

type Zahl = "prio_angefordert" | "prio_termin" | "termin_tage" | "prio_neu" | "neu_tage" | "prio_neu_lesen" | "prio_altbestand";

const PRIOS: { name: Zahl; text: string; hinweis: string; tage?: { name: Zahl; text: string; hinweis: string } }[] = [
  { name: "prio_angefordert", text: "Ausdrücklich angefordert", hinweis: "„jetzt verarbeiten“, „Erneut verarbeiten“ (0–100)" },
  { name: "prio_termin", text: "Patient hat bald einen Praxistermin", hinweis: "0–100",
    tage: { name: "termin_tage", text: "Termin in den nächsten (Tagen)", hinweis: "0–30, 0 = aus" } },
  { name: "prio_neu", text: "Neue Dokumente", hinweis: "0–100",
    tage: { name: "neu_tage", text: "hochgeladen in den letzten (Tagen)", hinweis: "1–90" } },
  { name: "prio_neu_lesen", text: "Neu lesen (Nachtaufgabe oder „Jetzt neu lesen“)", hinweis: "0–100" },
  { name: "prio_altbestand", text: "Altbestand", hinweis: "0–100" },
];

export function KiPriorisierung() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const q = useQuery({ queryKey: ["ki", "einstellungen"], queryFn: () => api<KiEinstellungen>("ki/einstellungen/") });
  const [werte, setWerte] = useState<Partial<KiEinstellungen>>({});
  useEffect(() => { if (q.data) setWerte(q.data); }, [q.data]);
  const speichern = useMutation({
    mutationFn: () => api<KiEinstellungen>("ki/einstellungen/", { method: "PUT", body: werte }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["ki"] }); melden("Gespeichert – gilt ab dem nächsten Durchlauf des KI-Dienstes."); },
  });
  if (!q.data) return q.isLoading ? <Laden /> : <Fehleranzeige fehler={q.error} />;
  const fehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const setz = (k: keyof KiEinstellungen, v: unknown) => setWerte({ ...werte, [k]: v });
  const zahlFeld = (name: Zahl, text: string, hinweis: string) => (
    <Feld key={name} label={text} hinweis={hinweis} fehler={fehler[name]}>
      {(p) => <Eingabe {...p} type="number" min={0} step="1" value={String(werte[name] ?? "")}
        onChange={(e) => setz(name, e.target.value === "" ? "" : Number(e.target.value))} />}
    </Feld>);
  // Dokumente: höchste Priorität zuerst (so wie der Dienst sie abholt)
  const reihe = PRIOS.map((p) => ({ text: p.text, wert: Number(werte[p.name] ?? 0) })).sort((a, b) => b.wert - a.wert);
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)] items-start">
      <Karte className="flex flex-col gap-4">
        <KartenKopf titel="Priorität der Dokumente" unter={q.data.geaendert_von_name
          ? `höhere Zahl = früher gelesen · zuletzt geändert ${zeitpunkt(q.data.geaendert_am)} von ${q.data.geaendert_von_name}`
          : "höhere Zahl = früher gelesen"} />
        <div className="flex flex-col gap-3">
          {PRIOS.map((p) => (
            <div key={p.name} className="grid gap-3 sm:grid-cols-2 border-b border-rand pb-3 last:border-0 last:pb-0">
              {zahlFeld(p.name, p.text, p.hinweis)}
              {p.tage ? zahlFeld(p.tage.name, p.tage.text, p.tage.hinweis) : null}
            </div>))}
        </div>
        <div className="flex flex-col gap-2 text-sm">
          <label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={!!werte.chat_vorrang}
            onChange={(e) => setz("chat_vorrang", e.target.checked)} />
            <span>Chat hat Vorrang: tagsüber hält ein wartender KI-Chat alle anderen Aufträge an</span></label>
          <label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={!!werte.zusammenfassung_tagsueber}
            onChange={(e) => setz("zusammenfassung_tagsueber", e.target.checked)} />
            <span>„Akte auf einen Blick“ auf Anforderung auch tagsüber erstellen (vorbereitete für Termine immer nur nachts)</span></label>
        </div>
        <div className="flex gap-2"><Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Speichern</Knopf></div>
        <Fehleranzeige fehler={speichern.error} />
      </Karte>
      <Karte className="flex flex-col gap-3" data-testid="ki-was-zuerst">
        <KartenKopf titel="Was zuerst?" unter="Reihenfolge, in der der KI-Dienst Arbeit abholt" />
        <ol className="m-0 pl-5 text-sm flex flex-col gap-1.5">
          <li><strong>KI-Chat</strong>{werte.chat_vorrang ? <span className="gedaempft"> – tagsüber hält ein wartender Chat alles andere an</span> : null}</li>
          <li><strong>Berichtsentwürfe</strong> <span className="gedaempft">(auf Anforderung)</span></li>
          <li><strong>Akte auf einen Blick</strong> <span className="gedaempft">– {werte.zusammenfassung_tagsueber
            ? "tagsüber nur angeforderte, für Termine vorbereitete nachts" : "nur nachts"}</span></li>
          <li><strong>Evaluation</strong> <span className="gedaempft">neuer Modelle (nachts)</span></li>
          <li><strong>Dokumente</strong> <span className="gedaempft">nach Priorität:</span>
            <ol className="m-0 mt-1 pl-5 flex flex-col gap-1">
              {reihe.map((r) => <li key={r.text}><Chip art={r.wert <= 0 ? "neutral" : undefined}>{r.wert}</Chip> {r.text}</li>)}
            </ol>
          </li>
        </ol>
        <p className="m-0 text-[0.75rem] gedaempft">
          Scans haben tagsüber Vorrang: Solange gescannt wird, wartet die KI. Tagsüber (parallele Aufträge tagsüber = 0) liest
          sie nur Angefordertes; alles andere folgt im Nachtfenster und innerhalb der Grenzen für CPU und Speicher.
          Bei Fehlern fällt die Priorität eines Dokuments auf 0 oder darunter.
        </p>
      </Karte>
    </div>
  );
}
