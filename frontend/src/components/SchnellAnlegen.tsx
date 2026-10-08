/**
 * Arzt oder Versorger anlegen, ohne die Seite zu verlassen (Vorschlag „Weniger Wege“, 08.10.2026): aus „Neuer Patient“
 * und „Arzt zuordnen“ öffnet „Neu anlegen“ diesen Dialog; nach dem Speichern ist der neue Eintrag gleich ausgewählt.
 * Was hier fehlt (Ansprechpartner, Notiz), wird wie gewohnt unter Versorger bzw. Ärzte ergänzt.
 */
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import type { Arzt, Versorger } from "@/lib/typen";
import { Eingabe, Feld, Knopf, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";

/** breite: Spalten im 8er-Raster ab Tablet (am Telefon eine Spalte) */
type FeldDef = { k: string; label: string; breite: 2 | 3 | 4 | 8; typ?: string; pflicht?: boolean; platzhalter?: string };

const ARZT: FeldDef[] = [
  { k: "name", label: "Name", breite: 4, pflicht: true, platzhalter: "z. B. Dr. med. Anna Hausmann" },
  { k: "fachrichtung", label: "Fachrichtung", breite: 4, platzhalter: "z. B. Allgemeinmedizin" },
  { k: "praxis", label: "Praxis / Klinik", breite: 8 },
  { k: "strasse", label: "Straße", breite: 3 }, { k: "plz", label: "PLZ", breite: 2 }, { k: "ort", label: "Ort", breite: 3 },
  { k: "telefon", label: "Telefon", breite: 2, typ: "tel" }, { k: "fax", label: "Fax", breite: 2, typ: "tel" },
  { k: "email", label: "E-Mail", breite: 4, typ: "email" },
];
const VERSORGER: FeldDef[] = [
  { k: "name", label: "Name", breite: 8, pflicht: true },
  { k: "strasse", label: "Straße", breite: 3 }, { k: "plz", label: "PLZ", breite: 2 }, { k: "ort", label: "Ort", breite: 3 },
  { k: "telefon", label: "Telefon", breite: 2, typ: "tel" }, { k: "fax", label: "Fax", breite: 2, typ: "tel" },
  { k: "email", label: "E-Mail", breite: 4, typ: "email" },
];
const BREITE: Record<FeldDef["breite"], string> = { 2: "sm:col-span-2", 3: "sm:col-span-3", 4: "sm:col-span-4", 8: "sm:col-span-8" };

function AnlegenDialog<T extends { id: number; name: string }>({ offen, onOffen, onAngelegt, titel, pfad, felder, schluessel, rest }: {
  offen: boolean; onOffen: (o: boolean) => void; onAngelegt: (neu: T) => void; titel: string; pfad: string; felder: FeldDef[];
  schluessel: string; rest: string;
}) {
  const leer = () => Object.fromEntries(felder.map((f) => [f.k, ""])) as Record<string, string>;
  const [w, setW] = useState(leer);
  const qc = useQueryClient();
  const melden = useHinweis();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (offen) setW(leer()); }, [offen]);
  const speichern = useMutation({
    mutationFn: () => {
      if (!w.name.trim()) throw new ApiFehler(400, "", null, { name: "Bitte einen Namen eingeben." });
      return api<T>(pfad, { body: Object.fromEntries(Object.entries(w).map(([k, v]) => [k, v.trim()])) });
    },
    onSuccess: (neu) => {
      void qc.invalidateQueries({ queryKey: [schluessel] });
      melden(`„${neu.name}“ angelegt und ausgewählt.`);
      onAngelegt(neu);
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={onOffen} titel={titel} breite={680}
      beschreibung={`${rest} ergänzen Sie danach unter ${schluessel === "aerzte" ? "Ärzte" : "Versorger"}.`}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" icon="haken" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Anlegen</Knopf>
      </>}>
      <form className="grid grid-cols-1 sm:grid-cols-8 gap-3" noValidate data-testid="schnell-anlegen"
        onSubmit={(e) => { e.preventDefault(); speichern.mutate(); }}>
        {felder.map((d) => (
          <Feld key={d.k} label={d.label} pflicht={d.pflicht} fehler={f[d.k]}
            className={BREITE[d.breite]}>
            {(p) => <Eingabe {...p} type={d.typ} placeholder={d.platzhalter} autoFocus={d.k === "name"} value={w[d.k]}
              onChange={(e) => setW({ ...w, [d.k]: e.target.value })} />}
          </Feld>
        ))}
        {speichern.error && !Object.keys(f).length ? <Meldung art="fehler" className="sm:col-span-8">{speichern.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

export function NeuerArztDialog(props: { offen: boolean; onOffen: (o: boolean) => void; onAngelegt: (neu: Arzt) => void }) {
  return <AnlegenDialog<Arzt> {...props} titel="Neuer Arzt" pfad="aerzte/" felder={ARZT} schluessel="aerzte" rest="Eine Notiz" />;
}

export function NeuerVersorgerDialog(props: { offen: boolean; onOffen: (o: boolean) => void; onAngelegt: (neu: Versorger) => void }) {
  return <AnlegenDialog<Versorger> {...props} titel="Neuer Versorger" pfad="versorger/" felder={VERSORGER} schluessel="versorger"
    rest="Ansprechpartner und Notiz" />;
}
