/**
 * Welchen Firmen gehört eine Akte? (Anforderung 11.10.2026: DSKM und Regeneration Clinic teilen sich einen Teil der
 * Patienten.) Auswahl beim Anlegen und in der Akte. Eine zweite Firma nur mit erfasster Einwilligung zum Austausch:
 * liegt sie noch nicht vor, wird das Datum der unterschriebenen Einwilligung gleich mit erfasst.
 */
import { createContext, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useIch } from "@/lib/auth";
import { eingabeDatum } from "@/lib/format";
import type { Firma, Patient } from "@/lib/typen";
import { Chip, Eingabe, Feld, Knopf, Meldung, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";

/** Alle Firmen des EPM (leer bzw. eine: keine Auswahl nötig) */
export function useAlleFirmen(): Firma[] {
  return useIch().alle_firmen ?? [];
}

export function firmenText(kuerzel: string[] | undefined, alle: Firma[]): string {
  return (kuerzel ?? []).map((k) => alle.find((f) => f.kuerzel === k)?.kurzname ?? k).join(" · ");
}

/** Kästchen je Firma; ab zwei gewählten Firmen ohne vorliegende Einwilligung das Datum der Einwilligung */
export function FirmenWahl({ wert, onWert, einwilligung, onEinwilligung, einwilligungLiegtVor, fehler }: {
  wert: string[]; onWert: (w: string[]) => void;
  einwilligung: string; onEinwilligung: (t: string) => void;
  einwilligungLiegtVor?: boolean;
  fehler?: { firmen?: string; einwilligung_am?: string };
}) {
  const alle = useAlleFirmen();
  const brauchtEinwilligung = wert.length > 1 && !einwilligungLiegtVor;
  return (
    <div className="flex flex-col gap-3" data-testid="firmen-wahl">
      <fieldset className="border-0 p-0 m-0 flex flex-col gap-1.5">
        <legend className="text-sm font-medium mb-1.5">Betreut von</legend>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {alle.map((f) => {
            const an = wert.includes(f.kuerzel);
            return (
              <label key={f.kuerzel} className={cx("firma-wahl", an && "an")}>
                <input type="checkbox" checked={an} data-testid={`firma-${f.kuerzel}`}
                  onChange={(e) => onWert(e.target.checked ? alle.map((x) => x.kuerzel).filter((k) => k === f.kuerzel || wert.includes(k))
                    : wert.filter((k) => k !== f.kuerzel))} />
                <span className="flex flex-col leading-tight">
                  <span className="font-medium">{f.kurzname}</span>
                  <span className="text-xs gedaempft">{f.name}</span>
                </span>
              </label>
            );
          })}
        </div>
        {fehler?.firmen ? <span className="fehlertext" role="alert">{fehler.firmen}</span> : null}
      </fieldset>
      {brauchtEinwilligung ? (
        <Feld label="Einwilligung zum Austausch unterschrieben am" pflicht fehler={fehler?.einwilligung_am}
          hinweis="Beide Firmen sehen die gesamte Akte. Das geht nur mit der unterschriebenen Einwilligung (Vordruck unter Akte › Datenschutz).">
          {(p) => <div className="max-w-[10rem]"><Eingabe {...p} className="num" placeholder="TT.MM.JJJJ" inputMode="numeric" value={einwilligung}
            onChange={(e) => onEinwilligung(e.target.value)} data-testid="firmen-einwilligung" /></div>}
        </Feld>
      ) : wert.length > 1 ? <span className="text-[0.8125rem] gedaempft">Die Einwilligung zum Austausch liegt vor.</span> : null}
    </div>
  );
}

/** Daten für die API; ``null`` mit Fehlertext, wenn das Datum der Einwilligung fehlt oder ungültig ist */
export function firmenDaten(wert: string[], einwilligung: string, liegtVor?: boolean):
  { daten: { firmen: string[]; einwilligung_am?: string } } | { fehler: { firmen?: string; einwilligung_am?: string } } {
  if (!wert.length) return { fehler: { firmen: "Bitte mindestens eine Firma wählen." } };
  if (wert.length > 1 && !liegtVor) {
    const am = eingabeDatum(einwilligung);
    if (!am) return { fehler: { einwilligung_am: einwilligung.trim() ? "Bitte als TT.MM.JJJJ eingeben." : "Bitte das Datum der Einwilligung angeben." } };
    return { daten: { firmen: wert, einwilligung_am: am } };
  }
  return { daten: { firmen: wert } };
}

/** Chip „DSKM · RG“ im Kopf der Akte – mit Recht zum Bearbeiten öffnet er die Auswahl */
export function FirmenChip({ patient, onKlick }: { patient: Patient; onKlick?: () => void }) {
  const alle = useAlleFirmen();
  if (alle.length < 2 || !patient.firmen?.length) return null;
  const text = firmenText(patient.firmen, alle);
  const titel = patient.firmen.length > 1 ? "Gemeinsame Akte beider Firmen" : `Akte der ${alle.find((f) => f.kuerzel === patient.firmen![0])?.name ?? text}`;
  return onKlick ? (
    <button type="button" className="chip akzent border-0 cursor-pointer" title={`${titel} – Firmen ändern`} onClick={onKlick}
      data-testid="akte-firmen">{text}</button>
  ) : <Chip art="akzent" title={titel} data-testid="akte-firmen">{text}</Chip>;
}

export function FirmenDialog({ patient, offen, onOffen }: { patient: Patient; offen: boolean; onOffen: (o: boolean) => void }) {
  const ich = useIch();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const melden = useHinweis();
  const [wert, setWert] = useState<string[]>(patient.firmen ?? []);
  const [einwilligung, setEinwilligung] = useState("");
  const [lokal, setLokal] = useState<{ firmen?: string; einwilligung_am?: string }>({});
  useEffect(() => {
    if (offen) { setWert(patient.firmen ?? []); setEinwilligung(""); setLokal({}); }
  }, [offen, patient.firmen]);
  const speichern = useMutation({
    mutationFn: (daten: Record<string, unknown>) => api<Patient>(`patienten/${patient.id}/firmen/`, { body: daten }),
    onSuccess: (p) => {
      onOffen(false);
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden(`Betreut von: ${firmenText(p.firmen, ich.alle_firmen ?? [])}.`);
      // ohne die eigene Firma ist die Akte hier nicht mehr sichtbar
      if (ich.firma && !p.firmen?.includes(ich.firma)) navigate("/patienten");
    },
  });
  const server = speichern.error instanceof ApiFehler ? speichern.error.felder as { firmen?: string; einwilligung_am?: string } : {};
  const ohneEigene = !!ich.firma && wert.length > 0 && !wert.includes(ich.firma);
  const absenden = () => {
    const r = firmenDaten(wert, einwilligung, patient.firmen_einwilligung);
    if ("fehler" in r) { setLokal(r.fehler); return; }
    setLokal({});
    speichern.mutate(r.daten);
  };
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Betreuende Firmen" breite={520}
      beschreibung="Die Akte ist nur für die gewählten Firmen sichtbar. Einträge zeigen, in welcher Firma sie erfasst wurden."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={absenden} data-testid="firmen-speichern">Speichern</Knopf>
      </>}>
      <FirmenWahl wert={wert} onWert={setWert} einwilligung={einwilligung} onEinwilligung={setEinwilligung}
        einwilligungLiegtVor={patient.firmen_einwilligung} fehler={{ ...server, ...lokal }} />
      {ohneEigene ? <Meldung art="warn">Ohne die Firma, für die du gerade arbeitest, ist die Akte danach hier nicht mehr sichtbar.</Meldung> : null}
      {speichern.error && !Object.keys(server).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

/** Gemeinsame Akte beider Firmen? Setzt die Akte für ihre Reiter (FirmaMarke) */
export const AkteGeteilt = createContext(false);

/** Firma, in der ein Eintrag erfasst wurde (``firma_kurz`` vom Server). Sichtbar in gemeinsamen Akten und wenn der
 *  Eintrag aus einer anderen Firma stammt – in Akten nur einer Firma wäre er überall gleich und nur Ballast. */
export function FirmaMarke({ kurz, className }: { kurz?: string | null; className?: string }) {
  const ich = useIch();
  const geteilt = useContext(AkteGeteilt);
  if (!kurz) return null;
  const aktiv = ich.firmen?.find((f) => f.kuerzel === ich.firma)?.kurzname;
  if (!geteilt && kurz === aktiv) return null;
  const name = ich.alle_firmen?.find((f) => f.kurzname === kurz)?.name ?? kurz;
  return <span className={cx("firma-marke", className)} title={`erfasst bei ${name}`} data-testid="firma-marke">{kurz}</span>;
}
