/** Eine vom Server erzeugte PDF anzeigen (pdf.js) und herunterladen – für Akte, Verlauf, Audit-Log, Zugangsblatt. */
import { useQuery } from "@tanstack/react-query";
import { apiDatei } from "@/lib/api";
import { Fehleranzeige, Knopf, Laden } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { PdfLeser } from "@/components/PdfAnsicht";

export function PdfDialog({ offen, onOffen, titel, pfad, dateiname, body }: {
  offen: boolean; onOffen: (o: boolean) => void; titel: string; pfad: string; dateiname: string; body?: unknown;
}) {
  const datei = useQuery({
    queryKey: ["pdf", pfad, body ?? null],
    queryFn: () => apiDatei(pfad, body !== undefined ? { method: "POST", body } : {}),
    enabled: offen,
    staleTime: 0,
    gcTime: 0,
  });
  const herunterladen = () => {
    if (!datei.data) return;
    const url = URL.createObjectURL(new Blob([datei.data.daten as BlobPart], { type: "application/pdf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = dateiname;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={titel} breite={1100}
      beschreibung={<Knopf klein icon="herunterladen" disabled={!datei.data} onClick={herunterladen}>Herunterladen</Knopf>}>
      <div className="flex flex-col gap-3" data-testid="pdf-dialog">
        {datei.isFetching ? <Laden text="PDF wird erzeugt …" /> : null}
        <Fehleranzeige fehler={datei.error} />
        {datei.data && !datei.isFetching ? (
          <PdfLeser url={`${pfad}-${datei.dataUpdatedAt}`} laden={() => Promise.resolve(datei.data.daten)} className="h-[64vh]" />
        ) : null}
      </div>
    </Dialog>
  );
}
