/** Vorlagen › Anlagen für E-Mails (F174): PDFs, die an die E-Mails der Schreiben angehängt werden können. */
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api, apiDatei } from "@/lib/api";
import { datum } from "@/lib/format";
import type { Anlage } from "@/lib/typen";
import { Chip, Eingabe, Fehleranzeige, Feld, Karte, Knopf, Laden, Meldung } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";

function groesse(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function useAnlagen(alle = false) {
  return useQuery({ queryKey: ["anlagen", alle], queryFn: () => api<Anlage[]>(`anlagen/${alle ? "?alle=1" : ""}`) });
}

export async function anlageOeffnen(a: Pick<Anlage, "id">) {
  const { daten } = await apiDatei(`anlagen/${a.id}/datei/`);
  const url = URL.createObjectURL(new Blob([daten as BlobPart], { type: "application/pdf" }));
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function AnlagenBereich() {
  const liste = useAnlagen(true);
  const qc = useQueryClient();
  const melden = useHinweis();
  const [name, setName] = useState("");
  const [beschreibung, setBeschreibung] = useState("");
  const [datei, setDatei] = useState<File | null>(null);
  const eingabe = useRef<HTMLInputElement>(null);
  const neu = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("name", name.trim());
      form.append("beschreibung", beschreibung.trim());
      if (datei) form.append("datei", datei);
      return api<Anlage>("anlagen/", { form });
    },
    onSuccess: () => {
      setName(""); setBeschreibung(""); setDatei(null);
      void qc.invalidateQueries({ queryKey: ["anlagen"] });
      melden("Anlage gespeichert.");
    },
  });
  const aendern = useMutation({
    mutationFn: ({ a, aktiv }: { a: Anlage; aktiv: boolean }) => api<Anlage>(`anlagen/${a.id}/`, { method: "PATCH", body: { aktiv } }),
    onSuccess: (a) => { void qc.invalidateQueries({ queryKey: ["anlagen"] }); melden(a.aktiv ? "Anlage wieder aktiv." : "Anlage deaktiviert."); },
  });
  const f = neu.error instanceof ApiFehler ? neu.error.felder : {};
  return (
    <div className="stapel grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-5 items-start">
      <Karte className="px-5 py-[18px] flex flex-col gap-3" data-testid="anlagen">
        <h2 className="lbl m-0">Anlagen</h2>
        <span className="text-[13px] gedaempft">Diese PDFs lassen sich beim Schreiben aus der Akte und bei der Patientenankündigung an die
          E-Mail hängen (z. B. Leitfaden Zottentraining, Handlungsempfehlung Locklösungen). Deaktivierte Anlagen stehen dort nicht mehr zur Wahl.</span>
        {liste.isLoading ? <Laden /> : null}
        <Fehleranzeige fehler={liste.error} />
        <ul className="flex flex-col divide-y divide-rand m-0 p-0 list-none">
          {(liste.data ?? []).map((a) => (
            <li key={a.id} className="py-2.5 flex items-center gap-3 flex-wrap">
              <div className="flex flex-col min-w-0 flex-1">
                <span className="font-medium">{a.name} {a.aktiv ? null : <Chip>deaktiviert</Chip>}</span>
                <span className="text-xs gedaempft">{[a.beschreibung, a.dateiname, groesse(a.groesse),
                  a.mitgeliefert ? "mitgeliefert" : `${datum(a.hochgeladen_am)}${a.hochgeladen_von ? ` · ${a.hochgeladen_von}` : ""}`]
                  .filter(Boolean).join(" · ")}</span>
              </div>
              <Knopf klein icon="dokument" onClick={() => void anlageOeffnen(a)}>Öffnen</Knopf>
              <Knopf klein laedt={aendern.isPending && aendern.variables?.a.id === a.id}
                onClick={() => aendern.mutate({ a, aktiv: !a.aktiv })}>{a.aktiv ? "Deaktivieren" : "Wieder aktivieren"}</Knopf>
            </li>
          ))}
        </ul>
      </Karte>
      <Karte className="px-5 py-[18px] flex flex-col gap-3">
        <h2 className="lbl m-0">Neue Anlage</h2>
        <Feld label="Name" fehler={f.name} pflicht>
          {(p) => <Eingabe {...p} value={name} maxLength={150} onChange={(e) => setName(e.target.value)} placeholder="z. B. Merkblatt Katheterpflege" />}
        </Feld>
        <Feld label="Beschreibung" fehler={f.beschreibung}>
          {(p) => <Eingabe {...p} value={beschreibung} maxLength={300} onChange={(e) => setBeschreibung(e.target.value)} />}
        </Feld>
        <div className="flex items-center gap-3 flex-wrap">
          <Knopf icon="hochladen" onClick={() => eingabe.current?.click()}>PDF wählen</Knopf>
          <span className="text-[13px] gedaempft truncate">{datei ? datei.name : "höchstens 20 MB"}</span>
          <input ref={eingabe} type="file" hidden aria-label="PDF-Datei der Anlage" accept=".pdf,application/pdf"
            onChange={(e) => { setDatei(e.target.files?.[0] ?? null); e.target.value = ""; }} />
        </div>
        {f.datei ? <Meldung art="fehler">{f.datei}</Meldung> : null}
        <Knopf variante="pri" laedt={neu.isPending} disabled={!name.trim() || !datei} onClick={() => neu.mutate()}>Anlage speichern</Knopf>
      </Karte>
    </div>
  );
}
