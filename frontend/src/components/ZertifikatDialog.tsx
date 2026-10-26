/**
 * Zertifikat (PKCS#12, .p12/.pfx) einer unterschriftsberechtigten Person hinterlegen – aus der Verwaltung „Fälle und
 * Abrechnung“ und beim Signieren in der Akte (die Person selbst). Das Kennwort prüft der Server nur, gespeichert wird es
 * nicht: Es wird bei jeder Signatur neu eingegeben.
 */
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import type { Unterzeichner } from "@/lib/typen";
import { Eingabe, Feld, Fehleranzeige, Knopf, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";

export function ZertifikatDialog({ person, offen, onOffen }: {
  person: Unterzeichner | null; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [datei, setDatei] = useState<File | null>(null);
  const [kennwort, setKennwort] = useState("");
  const hochladen = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("datei", datei!);
      form.append("kennwort", kennwort);
      return api<Unterzeichner>(`unterzeichner/${person!.id}/zertifikat/`, { form });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["faelle-stamm"] });
      melden("Zertifikat hinterlegt.");
      onOffen(false);
    },
  });
  const { reset } = hochladen;
  useEffect(() => {
    if (offen) { reset(); setDatei(null); setKennwort(""); }
  }, [offen, reset]);
  const f: Feldfehler = hochladen.error instanceof ApiFehler ? hochladen.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Zertifikat hinterlegen" beschreibung={person?.name}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" icon="hochladen" laedt={hochladen.isPending} disabled={!datei}
          onClick={() => hochladen.mutate()} data-testid="zertifikat-speichern">Hochladen</Knopf>
      </>}>
      <div className="flex flex-col gap-3" data-testid="zertifikat-dialog">
        <Feld label="Zertifikatsdatei (.p12 oder .pfx)" fehler={f.datei} pflicht>
          {(p) => <input {...p} type="file" accept=".p12,.pfx,application/x-pkcs12" className="text-sm"
            onChange={(e) => setDatei(e.target.files?.[0] ?? null)} />}
        </Feld>
        <Feld label="Kennwort der Datei" fehler={f.kennwort}>
          {(p) => <Eingabe {...p} type="password" autoComplete="off" value={kennwort} onChange={(e) => setKennwort(e.target.value)} />}
        </Feld>
        <Meldung art="info">Das Kennwort wird nur geprüft und nicht gespeichert. Beim Signieren wird es jedes Mal neu eingegeben.</Meldung>
        {hochladen.error && !Object.keys(f).length ? <Fehleranzeige fehler={hochladen.error} /> : null}
      </div>
    </Dialog>
  );
}
