/**
 * Schreiben mit E-Mail (Vorlagen von Alice Hessel, 09.10.2026; F172–F174).
 *
 * Aus einer Dokumentvorlage entsteht die PDF (ansehen, herunterladen, in der Akte ablegen) und eine fertige E-Mail:
 * Empfänger, Betreff und Text kommen aus der Vorlage und lassen sich hier anpassen; „E-Mail vorbereiten“ lädt eine
 * .eml-Datei mit der PDF und den gewählten Anlagen im Anhang. Outlook öffnet sie als Entwurf zum Absenden
 * (ein mailto:-Link kann keine Anhänge mitgeben).
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ApiFehler, api, apiDatei } from "@/lib/api";
import type { Mailtext } from "@/lib/typen";
import { Eingabe, Fehleranzeige, Feld, Knopf, Laden, Meldung, Textfeld } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { PdfDialog } from "@/components/PdfDialog";
import { anlageOeffnen, useAnlagen } from "@/seiten/admin/Anlagen";

function speichern(daten: Uint8Array, typ: string, dateiname: string) {
  const url = URL.createObjectURL(new Blob([daten as BlobPart], { type: typ }));
  const a = document.createElement("a");
  a.href = url;
  a.download = dateiname;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function dateinameAus(kopf: Headers, ersatz: string) {
  const m = /filename\*=UTF-8''([^;]+)/.exec(kopf.get("Content-Disposition") ?? "");
  return m ? decodeURIComponent(m[1]) : ersatz;
}

export function SchreibenDialog({ offen, onOffen, titel, pfad, koerper, bereit = true, optionen, ablegen, onAbgelegt,
  ohneEmpfaenger = "In der Akte ist keine E-Mail-Adresse hinterlegt – im Entwurf eintragen." }: {
  offen: boolean;
  onOffen: (o: boolean) => void;
  titel: string;
  /** POST-Endpunkt, z. B. ``patienten/12/schreiben/`` */
  pfad: string;
  /** Angaben zum Schreiben (Art, Termin, Zeitraum …); ändern sie sich, werden Betreff und Text neu geholt */
  koerper: Record<string, unknown>;
  /** false, solange Pflichtangaben fehlen (z. B. kein Termin gewählt) */
  bereit?: boolean;
  /** Eingaben oberhalb der E-Mail (Auswahl des Schreibens, Termin …) */
  optionen?: ReactNode;
  /** „In der Akte ablegen“ anbieten (nur aus der Akte, offene Akten) */
  ablegen?: boolean;
  onAbgelegt?: () => void;
  /** Hinweis, wenn die Vorlage keinen Empfänger vorgibt */
  ohneEmpfaenger?: string;
}) {
  const melden = useHinweis();
  const anlagen = useAnlagen();
  const schluessel = JSON.stringify(koerper);
  const mail = useQuery({
    queryKey: ["schreiben-mail", pfad, schluessel],
    queryFn: () => api<Mailtext>(pfad, { body: { ...koerper, ausgabe: "email" } }),
    enabled: offen && bereit,
    staleTime: 0,
    gcTime: 0,
  });
  // eigene Änderungen an Empfänger, Betreff und Text – gelten, bis sich das Schreiben ändert
  const [eigen, setEigen] = useState<{ schluessel: string; an?: string; betreff?: string; text?: string }>({ schluessel });
  const geaendert = eigen.schluessel === schluessel ? eigen : { schluessel };
  const setze = (x: Partial<Mailtext>) => setEigen({ ...geaendert, ...x, schluessel });
  const an = geaendert.an ?? mail.data?.an ?? "";
  const betreff = geaendert.betreff ?? mail.data?.betreff ?? "";
  const text = geaendert.text ?? mail.data?.text ?? "";
  const [gewaehlt, setGewaehlt] = useState<number[]>([]);
  const [ablage, setAblage] = useState(false);
  const [pdfOffen, setPdfOffen] = useState(false);

  const eml = useMutation({
    mutationFn: () => apiDatei(pfad, { body: { ...koerper, ausgabe: "eml", an, betreff, text, anlagen: gewaehlt,
      ablegen: !!ablegen && ablage } }),
    onSuccess: ({ daten, kopf }) => {
      speichern(daten, "message/rfc822", dateinameAus(kopf, "Schreiben.eml"));
      if (kopf.get("X-EPM-Dokument")) onAbgelegt?.();
      melden(kopf.get("X-EPM-Dokument") ? "E-Mail vorbereitet, PDF in der Akte abgelegt." : "E-Mail vorbereitet – Datei öffnen und absenden.");
    },
  });
  const pdf = useMutation({
    mutationFn: () => apiDatei(pfad, { body: { ...koerper, ausgabe: "pdf", ablegen: !!ablegen && ablage } }),
    onSuccess: ({ daten, kopf }) => {
      speichern(daten, "application/pdf", dateinameAus(kopf, "Schreiben.pdf"));
      if (kopf.get("X-EPM-Dokument")) { onAbgelegt?.(); melden("PDF heruntergeladen und in der Akte abgelegt."); }
    },
  });
  const kopieren = async () => {
    try {
      await navigator.clipboard.writeText(text);
      melden("Text der E-Mail kopiert.");
    } catch {
      melden("Kopieren ist hier nicht möglich – bitte den Text markieren und kopieren.");
    }
  };
  const fehler = eml.error ?? pdf.error;
  const f = fehler instanceof ApiFehler ? fehler.felder : {};

  return (
    <>
      <Dialog offen={offen} onOffen={onOffen} titel={titel} breite={820}
        beschreibung="PDF zum Drucken oder Faxen – oder eine fertige E-Mail mit der PDF im Anhang, die Outlook als Entwurf öffnet."
        fuss={<>
          <Knopf onClick={() => onOffen(false)}>Schließen</Knopf>
          <Knopf icon="dokument" disabled={!bereit} onClick={() => setPdfOffen(true)}>PDF ansehen</Knopf>
          <Knopf icon="herunterladen" disabled={!bereit} laedt={pdf.isPending} onClick={() => pdf.mutate()}>PDF herunterladen</Knopf>
          <Knopf variante="pri" icon="mail" disabled={!bereit || !mail.data} laedt={eml.isPending} onClick={() => eml.mutate()}>
            E-Mail vorbereiten</Knopf>
        </>}>
        <div className="flex flex-col gap-3.5" data-testid="schreiben-dialog">
          {optionen}
          {!bereit ? null : mail.isLoading ? <Laden text="Text wird vorbereitet …" /> : <Fehleranzeige fehler={mail.error} />}
          {bereit && mail.data ? <>
            <div className="grid gap-3 sm:grid-cols-[1fr_1.4fr]">
              <Feld label="An" fehler={f.an} hinweis={!an ? ohneEmpfaenger : undefined}>
                {(p) => <Eingabe {...p} type="email" value={an} maxLength={300} onChange={(e) => setze({ an: e.target.value })} />}
              </Feld>
              <Feld label="Betreff" fehler={f.betreff}>
                {(p) => <Eingabe {...p} value={betreff} maxLength={200} onChange={(e) => setze({ betreff: e.target.value })} />}
              </Feld>
            </div>
            <Feld label="Text" fehler={f.text}>
              {(p) => <Textfeld {...p} rows={9} value={text} onChange={(e) => setze({ text: e.target.value })} className="font-[inherit] leading-snug" />}
            </Feld>
            <div className="flex items-center gap-3 flex-wrap text-[0.8125rem]">
              <span className="gedaempft">Anhang: {mail.data.dateiname}</span>
              <Knopf klein onClick={() => void kopieren()}>Text kopieren</Knopf>
              {geaendert.text !== undefined || geaendert.betreff !== undefined
                ? <Knopf klein onClick={() => setEigen({ schluessel })}>Text aus der Vorlage</Knopf> : null}
            </div>
            {anlagen.data?.length ? (
              <fieldset className="flex flex-col gap-1.5 border border-rand rounded-lg px-3 py-2">
                <legend className="lbl px-1">Weitere Anlagen</legend>
                {anlagen.data.map((a) => (
                  <div key={a.id} className="flex items-center gap-2 text-[0.8438rem]">
                    <label className="flex items-center gap-2 cursor-pointer min-w-0">
                      <input type="checkbox" checked={gewaehlt.includes(a.id)}
                        onChange={(e) => setGewaehlt(e.target.checked ? [...gewaehlt, a.id] : gewaehlt.filter((x) => x !== a.id))} />
                      <span className="truncate">{a.name}</span>
                    </label>
                    <button type="button" className="text-xs gedaempft underline" onClick={() => void anlageOeffnen(a)}>ansehen</button>
                  </div>
                ))}
              </fieldset>
            ) : null}
            {f.anlagen ? <Meldung art="fehler">{f.anlagen}</Meldung> : null}
          </> : null}
          {ablegen ? (
            <label className="flex items-center gap-2 text-[0.8438rem]">
              <input type="checkbox" checked={ablage} onChange={(e) => setAblage(e.target.checked)} />
              PDF beim Herunterladen bzw. Vorbereiten der E-Mail als Dokument „Schreiben“ in der Akte ablegen
            </label>
          ) : null}
          {fehler && !Object.keys(f).length ? <Fehleranzeige fehler={fehler} /> : null}
        </div>
      </Dialog>
      <PdfDialog offen={pdfOffen} onOffen={setPdfOffen} titel={titel} pfad={pfad} body={{ ...koerper, ausgabe: "pdf" }}
        dateiname={mail.data?.dateiname ?? "Schreiben.pdf"} />
    </>
  );
}
