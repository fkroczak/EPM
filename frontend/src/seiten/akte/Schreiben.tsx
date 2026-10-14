/** Schreiben aus der Akte (F172): Patientenaufnahme, Terminbestätigung, Reisebescheinigung und die eigenen Schreiben
 *  aus Vorlagen › Dokumentvorlagen (F176) – als PDF oder E-Mail. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { abfrage, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { terminZeit } from "@/lib/format";
import type { Korrespondenzschreiben, Patient, Termin } from "@/lib/typen";
import { TERMINARTEN } from "@/lib/typen";
import { Auswahl, Eingabe, Feld } from "@/components/ui/basis";
import { SchreibenDialog } from "@/components/SchreibenDialog";
import { useHinweis } from "@/components/ui/hinweise";

export type Schreiben = { art: string; name: string; beschreibung: string; termin: boolean; eigen: boolean; gruppe_name?: string };

/** Die Schreiben als Optionen einer Auswahl: feste zuerst, die eigenen nach Gruppe (auch im Reiter „Korrespondenz“) */
export function SchreibenOptionen({ liste }: { liste: Schreiben[] }) {
  const gruppen = [...new Set(liste.filter((s) => s.eigen).map((s) => s.gruppe_name ?? "Eigene Vorlagen"))];
  return <>
    {liste.filter((s) => !s.eigen).map((s) => <option key={s.art} value={s.art}>{s.name}</option>)}
    {/* eigene Vorlagen nach Gruppe (z. B. Anforderungen und Formulare der RGC, 13.10.2026) */}
    {gruppen.map((g) => (
      <optgroup key={g} label={g}>
        {liste.filter((s) => s.eigen && (s.gruppe_name ?? "Eigene Vorlagen") === g)
          .map((s) => <option key={s.art} value={s.art}>{s.name}</option>)}
      </optgroup>
    ))}
  </>;
}

export function SchreibenAusAkte({ patient, offen, onOffen }: { patient: Patient; offen: boolean; onOffen: (o: boolean) => void }) {
  const qc = useQueryClient();
  const schreiben = useQuery({ queryKey: ["schreiben"], queryFn: () => api<Schreiben[]>("schreiben/"), enabled: offen });
  const [art, setArt] = useState("patientenaufnahme");
  const gewaehlt = schreiben.data?.find((s) => s.art === art);
  const mitTermin = !!gewaehlt?.termin;
  const [termin, setTermin] = useState("");
  const [tage, setTage] = useState("");
  const [attest, setAttest] = useState(true);
  const termine = useQuery({
    queryKey: ["patient", patient.id, "termine", "schreiben"],
    queryFn: () => api<ApiSeite<Termin>>(`termine/${abfrage({ patient: patient.id, offen: "true", ausgeblendet: "false", seitengroesse: 50 })}`),
    enabled: offen && mitTermin,
  });
  // Vorschlag: der nächste Praxistermin
  const liste = termine.data?.results ?? [];
  const vorschlag = liste.find((t) => t.art === "praxistermin") ?? liste[0];
  const terminId = termin || (vorschlag ? String(vorschlag.id) : "");
  const tageZahl = /^\d{1,3}$/.test(tage) && Number(tage) > 0 ? Number(tage) : null;
  const koerper: Record<string, unknown> = { art };
  if (mitTermin) koerper.termin = terminId ? Number(terminId) : null;
  if (art === "reisebescheinigung") Object.assign(koerper, { attest, tage: tageZahl });
  const bereit = !!gewaehlt && (!mitTermin || !!terminId);
  const beschreibung = gewaehlt?.beschreibung || undefined;
  // „In der Akte ablegen“ (Korrespondenz, 14.10.2026): Entwurf mit Vorlage, Termin, Empfänger und Betreff
  const melden = useHinweis();
  const navigate = useNavigate();
  const entwurf = useMutation({
    mutationFn: ({ an, betreff }: { an: string; betreff: string }) => api<Korrespondenzschreiben>("korrespondenz/", {
      body: { patient: patient.id, vorlage: art, titel: betreff.trim() || (gewaehlt?.name ?? "Schreiben").split(" (")[0],
        empfaenger: an.trim(), termin: mitTermin && terminId ? Number(terminId) : null,
        optionen: art === "reisebescheinigung" ? { attest, ...(attest && tageZahl ? { tage: tageZahl } : {}) } : {} } }),
    onSuccess: (s) => {
      void qc.invalidateQueries({ queryKey: ["korrespondenz", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden("Als Entwurf in der Korrespondenz abgelegt.");
      onOffen(false);
      navigate(`/patienten/${patient.id}/korrespondenz?schreiben=${s.id}`);
    },
    onError: (e) => melden(e.message, "fehler"),
  });

  return (
    <SchreibenDialog offen={offen} onOffen={onOffen} titel="Schreiben und E-Mail" pfad={`patienten/${patient.id}/schreiben/`}
      koerper={koerper} bereit={bereit} ablegen={!patient.ist_abgeschlossen}
      entwurfAblegen={patient.ist_abgeschlossen ? undefined : { onAblegen: (w) => entwurf.mutate(w), laedt: entwurf.isPending }}
      onAbgelegt={() => {
        void qc.invalidateQueries({ queryKey: ["dokumente", patient.id] });
        void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      }}
      optionen={<>
        <Feld label="Schreiben" hinweis={beschreibung}>
          {(p) => (
            <Auswahl {...p} value={art} onChange={(e) => setArt(e.target.value)}>
              <SchreibenOptionen liste={schreiben.data ?? []} />
            </Auswahl>
          )}
        </Feld>
        {mitTermin ? (
          <Feld label="Termin" hinweis={termine.isSuccess && !liste.length ? "Keine offenen Termine – bitte zuerst einen Termin anlegen." : undefined}>
            {(p) => (
              <Auswahl {...p} value={terminId} onChange={(e) => setTermin(e.target.value)} disabled={!liste.length}>
                {liste.map((t) => (
                  <option key={t.id} value={t.id}>
                    {terminZeit(t.faellig_am, t.uhrzeit)} · {t.ort_name ?? TERMINARTEN[t.art]} · {t.titel}
                  </option>
                ))}
              </Auswahl>
            )}
          </Feld>
        ) : null}
        {art === "reisebescheinigung" ? (
          <div className="flex items-end gap-4 flex-wrap">
            <label className="flex items-center gap-2 text-[0.8438rem] pb-2">
              <input type="checkbox" checked={attest} onChange={(e) => setAttest(e.target.checked)} />
              Ärztliches Attest des ADAC anhängen (Name, Ort und Datum sind eingetragen)
            </label>
            {attest ? (
              <Feld label="Reisedauer in Tagen" hinweis="leer lassen, um sie von Hand einzutragen" className="w-[12.5rem]">
                {(p) => <Eingabe {...p} className="num" inputMode="numeric" value={tage} maxLength={3}
                  onChange={(e) => setTage(e.target.value.replace(/\D/g, ""))} />}
              </Feld>
            ) : null}
          </div>
        ) : null}
      </>} />
  );
}
