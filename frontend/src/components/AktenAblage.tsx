/**
 * Dokumente direkt in die Akte legen (Vorschlag „Erfassen“, 08.10.2026): „Dokument hochladen“ im Aktenkopf und
 * Dateien irgendwo auf die geöffnete Akte ziehen. Die Seite bleibt, wo sie ist; jede Datei wird einzeln hochgeladen
 * und grün/rot quittiert. Im Reiter Dokumente übernimmt dessen eigene Ablage (dort mit Fortschrittsliste).
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Dokument } from "@/lib/typen";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";

export const DATEITYPEN = ".pdf,.jpg,.jpeg,.png,.txt,application/pdf,image/jpeg,image/png,text/plain";

function hatDateien(e: DragEvent) {
  return !!e.dataTransfer && Array.from(e.dataTransfer.types).includes("Files");
}

/** patientId = null: Ablage aus (abgeschlossene Akte, ohne Recht) */
export function useAktenAblage(patientId: number | null): { waehlen: () => void; ablage: ReactNode } {
  const eingabe = useRef<HTMLInputElement>(null);
  const [ziehen, setZiehen] = useState(false);
  const zaehler = useRef(0);
  const qc = useQueryClient();
  const melden = useHinweis();

  const hochladen = async (dateien: FileList | File[]) => {
    if (!patientId) return;
    for (const datei of Array.from(dateien)) {
      const form = new FormData();
      form.append("patient", String(patientId));
      form.append("datei", datei);
      form.append("titel", datei.name.replace(/\.[^.]+$/, ""));
      try {
        await api<Dokument>("dokumente/", { form });
        melden(`Dokument „${datei.name}“ in die Akte gelegt.`);
      } catch (e) {
        melden(`${datei.name}: ${e instanceof ApiFehler ? (e.felder.datei || e.message) : String(e)}`, "fehler");
      }
    }
    void qc.invalidateQueries({ queryKey: ["patient", patientId] });
  };
  const hochladenRef = useRef(hochladen);
  hochladenRef.current = hochladen;

  useEffect(() => {
    if (!patientId) return;
    const rein = (e: DragEvent) => { if (!hatDateien(e)) return; zaehler.current += 1; setZiehen(true); };
    const ueber = (e: DragEvent) => { if (hatDateien(e)) e.preventDefault(); };
    const raus = (e: DragEvent) => {
      if (!hatDateien(e)) return;
      zaehler.current = Math.max(0, zaehler.current - 1);
      if (!zaehler.current) setZiehen(false);
    };
    const ab = (e: DragEvent) => {
      zaehler.current = 0;
      setZiehen(false);
      // schon von einer eigenen Ablage verarbeitet (Reiter Dokumente)? Dann hier nichts mehr tun
      if (!hatDateien(e) || e.defaultPrevented) return;
      e.preventDefault();
      if (e.dataTransfer?.files.length) void hochladenRef.current(e.dataTransfer.files);
    };
    document.addEventListener("dragenter", rein);
    document.addEventListener("dragover", ueber);
    document.addEventListener("dragleave", raus);
    document.addEventListener("drop", ab);
    return () => {
      document.removeEventListener("dragenter", rein);
      document.removeEventListener("dragover", ueber);
      document.removeEventListener("dragleave", raus);
      document.removeEventListener("drop", ab);
      zaehler.current = 0;
      setZiehen(false);
    };
  }, [patientId]);

  const ablage = patientId ? (
    <>
      <input ref={eingabe} type="file" multiple hidden aria-label="Dokument in die Akte legen" accept={DATEITYPEN}
        data-testid="akten-datei" onChange={(e) => { if (e.target.files?.length) void hochladen(e.target.files); e.target.value = ""; }} />
      {ziehen ? (
        <div className="akten-ablage nicht-drucken" data-testid="akten-ablage" aria-hidden="true">
          <div className="akten-ablage-kasten"><Icon name="hochladen" groesse={28} />Datei loslassen, um sie in die Akte zu legen
            <span className="gedaempft text-[0.8125rem]">PDF, JPG, PNG, TXT · max. 50 MB</span></div>
        </div>
      ) : null}
    </>
  ) : null;
  return { waehlen: () => eingabe.current?.click(), ablage };
}
