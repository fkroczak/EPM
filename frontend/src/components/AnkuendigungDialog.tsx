/** Patientenankündigung für die Sprechstunden (F173): alle Praxistermine eines Zeitraums als PDF (Fax) oder E-Mail. */
import { useState } from "react";
import { useAuswahl } from "@/lib/daten";
import { Auswahl, Eingabe, Feld } from "@/components/ui/basis";
import { SchreibenDialog } from "@/components/SchreibenDialog";

export function AnkuendigungDialog({ offen, onOffen, von: vonVorgabe, bis: bisVorgabe }: {
  offen: boolean; onOffen: (o: boolean) => void; von: string; bis: string;
}) {
  const orte = useAuswahl("terminort");
  const [von, setVon] = useState<string | null>(null);
  const [bis, setBis] = useState<string | null>(null);
  const [ort, setOrt] = useState<string | null>(null);
  const vorschlag = orte.data?.find((o) => /holtmeier/i.test(o.wert)) ?? orte.data?.[0];
  const ortId = ort ?? (vorschlag ? String(vorschlag.id) : "");
  const a = von ?? vonVorgabe;
  const b = bis ?? bisVorgabe;
  const datumOk = /^\d{4}-\d{2}-\d{2}$/.test(a) && /^\d{4}-\d{2}-\d{2}$/.test(b) && a <= b;
  return (
    <SchreibenDialog offen={offen} onOffen={(o) => { if (!o) { setVon(null); setBis(null); } onOffen(o); }}
      titel="Patientenankündigung Sprechstunde" pfad="kalender/ankuendigung/" bereit={datumOk}
      ohneEmpfaenger="E-Mail-Adresse der Praxis eintragen – oder hier leer lassen und im Entwurf ergänzen."
      koerper={{ von: a, bis: b, ort: ortId ? Number(ortId) : null }}
      optionen={<>
        <div className="grid gap-3 sm:grid-cols-[10rem_10rem_1fr]">
          <Feld label="von">{(p) => <Eingabe {...p} type="date" value={a} onChange={(e) => setVon(e.target.value)} />}</Feld>
          <Feld label="bis">{(p) => <Eingabe {...p} type="date" value={b} onChange={(e) => setBis(e.target.value)} />}</Feld>
          <Feld label="Terminort der Sprechstunde" hinweis="Termine an anderen Orten (z. B. Telefon) stehen mit Ort und Telefonnummer als Hinweis in der Liste">
            {(p) => (
              <Auswahl {...p} value={ortId} onChange={(e) => setOrt(e.target.value)}>
                <option value="">– alle –</option>
                {(orte.data ?? []).map((o) => <option key={o.id} value={o.id}>{o.wert}</option>)}
              </Auswahl>
            )}
          </Feld>
        </div>
        <span className="text-[0.8125rem] gedaempft">Angekündigt werden alle Praxistermine im Zeitraum (ohne Testpatienten). Hinweise wie
          „1 h, Neuaufnahme“ oder „+ Labor“ im Termin unter „bei/Ort“ eintragen – sie erscheinen hinter dem Namen.</span>
      </>} />
  );
}
