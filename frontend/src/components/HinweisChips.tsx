/**
 * Hinweise einer Akte als Chips – jeder mit „×“ zum Wegklicken (Wunsch 07.10.2026, F119).
 *
 * Beim Wegklicken wird entschieden, wie lange Ruhe sein soll: 3, 6 oder 12 Monate – danach erscheint der
 * Hinweis von allein wieder – oder „nicht mehr nötig“, dann bleibt er weg, bis jemand ihn zurückholt.
 * Festgehalten wird das mit Grund, Person und Zeitpunkt; es steht im Verlauf der Akte.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { RUHE_FRISTEN } from "@/lib/typen";
import type { HinweisArt, Hinweisruhe, Kontaktstufe } from "@/lib/typen";
import { datum, zeitpunkt } from "@/lib/format";
import { Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, Meldung, Segmente } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";

export type Hinweis = { art: HinweisArt; text: string; stufe?: Kontaktstufe };

type Wahl = "3" | "6" | "12" | "dauerhaft";

export function RuheDialog({ patientId, hinweis, offen, onOffen }: {
  patientId: number; hinweis: Hinweis | null; offen: boolean; onOffen: (o: boolean) => void;
}) {
  const [wahl, setWahl] = useState<Wahl>("3");
  const [grund, setGrund] = useState("");
  const qc = useQueryClient();
  const melden = useHinweis();
  const [gesetzt, setGesetzt] = useState<unknown>(undefined);
  if (offen && gesetzt !== hinweis) {
    setGesetzt(hinweis);
    setWahl("3");
    setGrund("");
  }
  const speichern = useMutation({
    mutationFn: () => api<Hinweisruhe>(`patienten/${patientId}/hinweis-ruhe/`, {
      body: wahl === "dauerhaft"
        ? { art: hinweis!.art, dauerhaft: true, grund }
        : { art: hinweis!.art, monate: Number(wahl), grund },
    }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["patient", patientId] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      void qc.invalidateQueries({ queryKey: ["hinweis-ruhe", patientId] });
      melden(wahl === "dauerhaft" ? "Hinweis ausgeblendet." : `Hinweis für ${wahl} Monate ausgeblendet.`);
      onOffen(false);
    },
  });
  return (
    <Dialog offen={offen} onOffen={onOffen} breite={520} titel="Hinweis ausblenden"
      beschreibung={hinweis?.text}
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} onClick={() => speichern.mutate()}>Ausblenden</Knopf>
      </>}>
      <Feld label="Wie lange soll Ruhe sein?">
        {() => (
          <Segmente label="Ruhe" wert={wahl} onWahl={setWahl} werte={[
            ...RUHE_FRISTEN.map((m) => ({ wert: String(m) as Wahl, text: `${m} Monate` })),
            { wert: "dauerhaft" as Wahl, text: "nicht mehr nötig" },
          ]} />
        )}
      </Feld>
      <Meldung art="info">
        {wahl === "dauerhaft"
          ? "Der Hinweis bleibt weg, bis ihn jemand in der Akte wieder einschaltet."
          : `Der Hinweis erscheint nach ${wahl} Monaten von allein wieder.`}
      </Meldung>
      <Feld label="Grund" hinweis="hilft später beim Nachvollziehen; steht im Verlauf der Akte">
        {(p) => <Eingabe {...p} value={grund} maxLength={300} onChange={(e) => setGrund(e.target.value)}
          placeholder="z. B. Labor ist beim Hausarzt angefordert" />}
      </Feld>
      <Fehleranzeige fehler={speichern.error} />
    </Dialog>
  );
}

/** Chips der Hinweise; mit ``patientId`` und Recht lässt sich jeder einzeln wegklicken. */
export function HinweisChips({ hinweise, patientId, ausblendbar }: {
  hinweise: Hinweis[]; patientId?: number; ausblendbar?: boolean;
}) {
  const [dialog, setDialog] = useState<Hinweis | null>(null);
  const kann = !!patientId && !!ausblendbar;
  return (
    <>
      {hinweise.map((h) => (
        <Chip key={h.art} art={h.stufe === "ueberfaellig" ? "fehler" : "warn"}>
          {h.text}
          {kann ? (
            <button type="button" className="ml-1 bg-transparent border-0 p-0 cursor-pointer opacity-70 hover:opacity-100"
              aria-label={`Hinweis „${h.text}“ ausblenden`} title="Ausblenden"
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDialog(h); }}>×</button>
          ) : null}
        </Chip>
      ))}
      {kann ? <RuheDialog patientId={patientId!} hinweis={dialog} offen={!!dialog}
        onOffen={(o) => { if (!o) setDialog(null); }} /> : null}
    </>
  );
}

/** Karte in der Akte: welche Hinweise gerade weggeklickt sind – und zurück damit. */
export function StummKarte({ patientId, aenderbar }: { patientId: number; aenderbar: boolean }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const liste = useQuery({
    queryKey: ["hinweis-ruhe", patientId],
    queryFn: () => api<Hinweisruhe[]>(`patienten/${patientId}/hinweis-ruhe/`),
  });
  const einschalten = useMutation({
    mutationFn: (r: Hinweisruhe) => api(`patienten/${patientId}/hinweis-ruhe/`, { body: { art: r.art, aufheben: true } }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["hinweis-ruhe", patientId] });
      void qc.invalidateQueries({ queryKey: ["patient", patientId] });
      void qc.invalidateQueries({ queryKey: ["patienten"] });
      void qc.invalidateQueries({ queryKey: ["startseite"] });
      melden("Hinweis wieder eingeschaltet.");
    },
    onError: (e) => melden(e.message, "fehler"),
  });
  const laufend = (liste.data ?? []).filter((r) => r.laeuft);
  if (!laufend.length) return null;
  return (
    <Karte className="px-[22px] py-[18px] flex flex-col gap-2" data-testid="stumme-hinweise">
      <KartenKopf titel="Ausgeblendete Hinweise" unter="Erscheinen nach Ablauf der Frist von allein wieder." />
      <ul className="m-0 p-0 list-none flex flex-col gap-1.5">
        {laufend.map((r) => (
          <li key={r.id} className="flex items-start justify-between gap-3 text-sm">
            <span className="min-w-0">
              {r.art_name}
              <span className="gedaempft"> · {r.bis ? `bis ${datum(r.bis)}` : "nicht mehr nötig"}</span>
              {r.grund ? <span className="block text-[0.75rem] gedaempft">{r.grund}</span> : null}
              <span className="block text-[0.75rem] gedaempft">
                {zeitpunkt(r.gesetzt_am)} · {r.gesetzt_von_name ?? "—"}
              </span>
            </span>
            {aenderbar ? (
              <Knopf klein laedt={einschalten.isPending} onClick={() => einschalten.mutate(r)}>Wieder einschalten</Knopf>
            ) : null}
          </li>
        ))}
      </ul>
    </Karte>
  );
}
