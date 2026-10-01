/** Entwurf 2 · Start (Varianten 16 über die Darstellung). */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth, useIch, useOhneRechtSchliessen } from "@/lib/auth";
import { datum, kg, langesDatum, prozent, relativ, terminZeit, uhrzeit } from "@/lib/format";
import { TERMINARTEN } from "@/lib/typen";
import type { Ich, Karte, Termin } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Fehleranzeige, Karte as KarteBox, Knopf, Laden, Leer, Segmente, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { useSortierbar } from "@/components/ui/sortierbar";
import { TerminDialog } from "@/components/TerminDialog";

type PlanEintrag = { id: number; patient: number; name: string; gueltig_ab: string; status: string; erstellt_am: string;
  erstellt_von: string | null; freigegeben_am: string | null };

type Startdaten = {
  termine: { ueberfaellig: Termin[]; heute: Termin[]; naechste_7_tage: Termin[] };
  gewichtswarnungen: { patient: number; name: string; nummer: number; gewicht: { kg: number; am: string } | null; prozent: number }[];
  gewicht_schwelle: { prozent: number; monate: number };
  infusionsplaene: { entwuerfe: PlanEintrag[]; aelter_als_grenze: PlanEintrag[]; grenze_monate: number };
  pruefen: { altdokumente: number; nickelallergie_unbekannt: number; kein_versorger: number; kein_kontakt: number; kontakt_monate: number };
  zuletzt_eingetragen: { bereich: string; bezeichnung: string; objekt_id: number; patient: number; name: string | null;
    zeitpunkt: string; person: string | null }[];
  zahlen: { in_betreuung: number; mit_offenem_termin: number };
};

const KARTEN: { id: Karte["id"]; titel: string }[] = [
  { id: "termine", titel: "Termine und Wiedervorlagen" },
  { id: "gewicht", titel: "Auffällige Gewichte" },
  { id: "plaene", titel: "Infusionspläne" },
  { id: "pruefen", titel: "Nach und nach prüfen" },
  { id: "aktiv", titel: "Zuletzt eingetragen" },
];

function kartenVon(ich: Ich): Karte[] {
  const gespeichert = ich.startseite?.karten ?? [];
  const ids = new Set(gespeichert.map((k) => k.id));
  return [...gespeichert.filter((k) => KARTEN.some((x) => x.id === k.id)),
    ...KARTEN.filter((k) => !ids.has(k.id)).map((k) => ({ id: k.id, sichtbar: true }))];
}

function terminChip(t: Termin) {
  if (t.art === "wiedervorlage") return <Chip art="warn">{TERMINARTEN[t.art]}</Chip>;
  if (t.art === "praxistermin") return <Chip art="akzent">{t.ort_name || t.bei || TERMINARTEN[t.art]}</Chip>;
  return <Chip>{TERMINARTEN[t.art]}</Chip>;
}

function Liste({ children }: { children: ReactNode }) {
  return <div className="flex flex-col">{children}</div>;
}

function Zeile({ links, rechts, unter, zu }: { links: ReactNode; rechts?: ReactNode; unter?: ReactNode; zu: string }) {
  return (
    <div className="flex justify-between items-center gap-3 py-[9px] border-b border-rand last:border-b-0">
      <span className="flex flex-col gap-px min-w-0">
        <Link to={zu} className="font-medium no-underline">{links}</Link>
        {unter ? <span className="text-[0.78125rem] gedaempft">{unter}</span> : null}
      </span>
      {rechts}
    </div>
  );
}

function TermineKarte({ daten }: { daten: Startdaten }) {
  const { darf, darfBei } = useAuth();
  const [tab, setTab] = useState<"heute" | "woche" | "ueber">("heute");
  const [dialog, setDialog] = useState(false);
  const [erledigt, setErledigt] = useState<Record<number, Termin>>({});
  const [laeuft, setLaeuft] = useState<number[]>([]);
  const qc = useQueryClient();
  const melden = useHinweis();
  const abhaken = useMutation({
    mutationFn: (t: Termin) => api<Termin>(`termine/${t.id}/erledigt/`, { method: "POST" }),
    onMutate: (t) => setLaeuft((l) => [...l, t.id]), // Haken sofort zeigen, bei Fehler zurücknehmen
    onSettled: (_d, _e, t) => setLaeuft((l) => l.filter((x) => x !== t.id)),
    onSuccess: (t) => {
      setErledigt((e) => ({ ...e, [t.id]: t }));
      void qc.invalidateQueries({ queryKey: ["patient", t.patient] });
      melden(`Erledigt: ${t.patient_name}`);
    },
    onError: (e) => melden(e.message, "fehler"),
  });
  const offen = (l: Termin[]) => l.filter((t) => !erledigt[t.id]).length;
  const heute = daten.termine.heute, woche = daten.termine.naechste_7_tage, ueber = daten.termine.ueberfaellig;
  const zeilen = tab === "heute" ? heute : tab === "woche" ? woche : ueber;
  const schreiben = darf("eintraege_erfassen");
  useOhneRechtSchliessen(schreiben, () => setDialog(false));
  return (
    <KarteBox className="col-span-3 lg:col-span-2 px-5 py-[18px] flex flex-col gap-3 min-w-0" aria-labelledby="k-termine">
      <div className="flex justify-between items-center gap-3 flex-wrap">
        <h2 id="k-termine" className="lbl m-0">Termine und Wiedervorlagen</h2>
        <div className="flex items-center gap-2.5">
          <Segmente label="Zeitraum" wert={tab} onWahl={setTab} werte={[
            { wert: "heute", text: <>Heute <span className="num opacity-70">{offen(heute)}</span></> },
            { wert: "woche", text: <>Nächste 7 Tage <span className="num opacity-70">{offen(woche)}</span></> },
            { wert: "ueber", text: <>Überfällig <span className="num opacity-70">{offen(ueber)}</span></> },
          ]} />
          {schreiben ? <Knopf klein icon="plus" onClick={() => setDialog(true)}>Termin</Knopf> : null}
        </div>
      </div>
      <div className="flex flex-col" data-testid="terminliste">
        {zeilen.length === 0 ? <Leer>Keine offenen Termine.</Leer> : zeilen.map((t) => {
          const fertig = erledigt[t.id];
          return (
            <div key={t.id} className="grid grid-cols-[36px_150px_190px_minmax(0,1fr)] items-center gap-3 py-[11px] border-b border-rand last:border-b-0">
              {/* Abhaken nur mit Recht; ohne Recht kein (ausgegrautes) Kästchen */}
              {darfBei("eintraege_erfassen", { ist_test: t.patient_ist_test }) ? (
                <input type="checkbox" aria-label={`Erledigt: ${t.patient_name}, ${t.titel}`} className="!w-5 !h-5"
                  checked={!!fertig || laeuft.includes(t.id)}
                  disabled={!!fertig || laeuft.includes(t.id)}
                  onChange={() => abhaken.mutate(t)} />
              ) : <span aria-hidden="true" />}
              <span className="num text-[0.84375rem] text-text2">{terminZeit(t.faellig_am, t.uhrzeit)}</span>
              <span>{terminChip(t)}</span>
              <span className="flex flex-col gap-px min-w-0">
                {fertig ? (
                  <span className="gedaempft line-through">{t.patient_name} · {t.titel}</span>
                ) : (
                  <span><Link to={`/patienten/${t.patient}`} className="font-medium no-underline">{t.patient_name}</Link>{" "}
                    <span className="text-text2">· {t.titel}{t.notiz ? ` – ${t.notiz}` : ""}</span></span>
                )}
                <span className="text-[0.78125rem] gedaempft">
                  {fertig ? `erledigt ${uhrzeit(fertig.erledigt_am)} von ${fertig.erledigt_von_name ?? "—"}`
                    : `angelegt von ${t.angelegt_von_name ?? "—"}`}
                </span>
              </span>
            </div>
          );
        })}
      </div>
      <span className="text-[0.78125rem] gedaempft">
        Abhaken markiert als erledigt, mit Person und Uhrzeit. Termine lassen sich in der Akte, bei einem Kontakt oder hier anlegen.
      </span>
      {schreiben ? <TerminDialog offen={dialog} onOffen={setDialog} /> : null}
    </KarteBox>
  );
}

function GewichtKarte({ daten }: { daten: Startdaten }) {
  const s = daten.gewicht_schwelle;
  return (
    <KarteBox className="col-span-3 lg:col-span-1 px-5 py-[18px] flex flex-col gap-1.5 min-w-0" aria-labelledby="k-gewicht">
      <h2 id="k-gewicht" className="lbl m-0">Auffällige Gewichte</h2>
      <span className="text-[0.78125rem] gedaempft">Mehr als {String(s.prozent).replace(".", ",")} % Verlust in {s.monate} Monaten</span>
      <Liste>
        {daten.gewichtswarnungen.length === 0 ? <Leer>Keine auffälligen Gewichte.</Leer> : daten.gewichtswarnungen.map((w) => (
          <Zeile key={w.patient} zu={`/patienten/${w.patient}`} links={w.name}
            unter={w.gewicht ? `${kg(w.gewicht.kg)} · zuletzt ${datum(w.gewicht.am)}` : undefined}
            rechts={<Chip art="warn">{prozent(w.prozent)}</Chip>} />
        ))}
      </Liste>
    </KarteBox>
  );
}

function PlaeneKarte({ daten }: { daten: Startdaten }) {
  const p = daten.infusionsplaene;
  const leer = p.entwuerfe.length === 0 && p.aelter_als_grenze.length === 0;
  return (
    <KarteBox className="col-span-3 md:col-span-1 px-5 py-[18px] flex flex-col gap-1.5 min-w-0" aria-labelledby="k-plaene">
      <h2 id="k-plaene" className="lbl m-0">Infusionspläne</h2>
      <Liste>
        {leer ? <Leer>Keine offenen Entwürfe, keine alten Pläne.</Leer> : null}
        {p.entwuerfe.map((e) => (
          <Zeile key={e.id} zu={`/patienten/${e.patient}/plaene?plan=${e.id}`} links={e.name}
            unter={`seit ${relativ(e.erstellt_am, true)} · ${e.erstellt_von ?? "—"}`} rechts={<Chip>Entwurf</Chip>} />
        ))}
        {p.aelter_als_grenze.map((e) => (
          <Zeile key={e.id} zu={`/patienten/${e.patient}/plaene?plan=${e.id}`} links={e.name}
            unter={`freigegeben ${datum(e.freigegeben_am ?? e.gueltig_ab)}`}
            rechts={<Chip art="warn">älter als {p.grenze_monate} Monate</Chip>} />
        ))}
      </Liste>
    </KarteBox>
  );
}

function PruefenKarte({ daten }: { daten: Startdaten }) {
  const p = daten.pruefen;
  const eintraege: [string, number, string][] = [
    ["Altdokumente: Typ und Datum prüfen", p.altdokumente, "altdokumente"],
    ["Nickelallergie nicht erfasst", p.nickelallergie_unbekannt, "nickelallergie"],
    ["Versorger nicht erfasst", p.kein_versorger, "kein_versorger"],
    [`Kein Kontakt seit über ${p.kontakt_monate} Monaten`, p.kein_kontakt, "kein_kontakt"],
  ];
  return (
    <KarteBox className="col-span-3 md:col-span-1 px-5 py-[18px] flex flex-col gap-2.5 min-w-0" aria-labelledby="k-pruefen">
      <h2 id="k-pruefen" className="lbl m-0">Nach und nach prüfen</h2>
      <div className="flex flex-col gap-2.5 text-sm">
        {eintraege.map(([text, n, filter]) => (
          <Link key={filter} to={`/patienten?pruefen=${filter}`} className="flex justify-between no-underline text-tinte hover:text-akzent-text">
            <span>{text}</span><span className="num text-akzent-text" data-testid={`pruefen-${filter}`}>{n}</span>
          </Link>
        ))}
      </div>
    </KarteBox>
  );
}

function AktivKarte({ daten }: { daten: Startdaten }) {
  const wann = (z: string) => {
    const r = relativ(z);
    return r === "heute" ? uhrzeit(z) : r === "gestern" ? "gestern" : datum(z).slice(0, 6);
  };
  return (
    <KarteBox className="col-span-3 md:col-span-1 px-5 py-[18px] flex flex-col gap-1.5 min-w-0" aria-labelledby="k-aktiv">
      <h2 id="k-aktiv" className="lbl m-0">Zuletzt eingetragen</h2>
      <div className="flex flex-col text-[0.84375rem]">
        {daten.zuletzt_eingetragen.length === 0 ? <Leer>Noch nichts eingetragen.</Leer> : daten.zuletzt_eingetragen.map((z, i) => (
          <div key={`${z.bereich}-${z.objekt_id}-${i}`} className="py-[7px] border-b border-rand last:border-b-0">
            <span className="num gedaempft">{wann(z.zeitpunkt)}</span> {z.person ?? "—"} · {z.bezeichnung}{" "}
            <Link to={`/patienten/${z.patient}`}>{z.name?.split(",")[0] ?? "Akte"}</Link>
          </div>
        ))}
      </div>
    </KarteBox>
  );
}

function Anpassen({ karten, onAendern, onFertig }: { karten: Karte[]; onAendern: (k: Karte[]) => void; onFertig: () => void }) {
  const sort = useSortierbar(karten, onAendern);
  return (
    <KarteBox className="px-5 py-4 flex flex-col gap-3 !border-akzent" aria-labelledby="k-anpassen">
      <div className="flex justify-between items-center">
        <h2 id="k-anpassen" className="lbl m-0 text-akzent-text">Meine Startseite</h2>
        <Knopf klein variante="pri" onClick={onFertig}>Fertig</Knopf>
      </div>
      <ul className="grid grid-cols-2 md:grid-cols-5 gap-2.5 m-0 p-0 list-none">
        {karten.map((k, i) => {
          const titel = KARTEN.find((x) => x.id === k.id)?.titel ?? k.id;
          return (
            <li key={k.id} {...sort.zeile(i)}
              className={cx("flex items-center gap-2.5 px-3 py-2.5 border border-rand rounded-lg text-sm bg-flaeche",
                sort.ueber === i && "outline-2 outline-akzent", sort.zieht === i && "opacity-50")}>
              <button type="button" className="border-0 bg-transparent cursor-grab gedaempft p-0 tracking-[-2px]" {...sort.griff(i, titel, "startkarten")}>⋮⋮</button>
              <label className="flex items-center gap-2.5 cursor-pointer">
                <input type="checkbox" className="!w-[18px] !h-[18px]" checked={k.sichtbar}
                  onChange={() => onAendern(karten.map((x) => (x.id === k.id ? { ...x, sichtbar: !x.sichtbar } : x)))} />
                {titel}
              </label>
            </li>
          );
        })}
      </ul>
      <span className="text-[0.78125rem] gedaempft">
        Ein- und ausblenden per Haken, Reihenfolge per Ziehen. Gilt nur für dich; jede Person hat ihre eigene Startseite.
      </span>
    </KarteBox>
  );
}

export function Start() {
  const ich = useIch();
  const { setIch } = useAuth();
  const melden = useHinweis();
  const [bearbeiten, setBearbeiten] = useState(false);
  const location = useLocation();
  useEffect(() => {
    if ((location.state as { anpassen?: number } | null)?.anpassen) setBearbeiten(true); // „Startseite anpassen“ aus Mein Konto
  }, [location.state]);
  const daten = useQuery({ queryKey: ["startseite"], queryFn: () => api<Startdaten>("startseite/") });
  const karten = kartenVon(ich);
  const speichern = useMutation({
    mutationFn: (neu: Karte[]) => api<Ich>("auth/ich/", { method: "PATCH", body: { startseite: { karten: neu } } }),
    onMutate: (neu) => setIch({ ...ich, startseite: { karten: neu } }),
    onSuccess: (antwort) => setIch(antwort),
    onError: (e) => {
      melden(`Startseite nicht gespeichert: ${e.message}`, "fehler");
      setIch(ich);
    },
  });
  const d = daten.data;
  const inhalt: Record<Karte["id"], (d: Startdaten) => ReactNode> = {
    termine: (x) => <TermineKarte key="termine" daten={x} />,
    gewicht: (x) => <GewichtKarte key="gewicht" daten={x} />,
    plaene: (x) => <PlaeneKarte key="plaene" daten={x} />,
    pruefen: (x) => <PruefenKarte key="pruefen" daten={x} />,
    aktiv: (x) => <AktivKarte key="aktiv" daten={x} />,
  };
  return (
    <Seite pfad={[{ text: "Start" }]}>
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 text-[1.625rem] font-semibold">{langesDatum()}</h1>
          {d ? (
            <span className="text-sm gedaempft" data-testid="start-zahlen">
              <span className="num">{d.termine.heute.length}</span> offene Termine heute · <span className="num">{d.termine.ueberfaellig.length}</span> überfällig
            </span>
          ) : null}
        </div>
        <Knopf icon="stift" onClick={() => setBearbeiten((b) => !b)} aria-expanded={bearbeiten}>Startseite anpassen</Knopf>
      </div>
      {bearbeiten ? <Anpassen karten={karten} onAendern={(k) => speichern.mutate(k)} onFertig={() => setBearbeiten(false)} /> : null}
      {daten.isLoading ? <Laden /> : null}
      <Fehleranzeige fehler={daten.error} />
      {d ? (
        <div className="grid grid-cols-3 gap-5 items-start">
          {karten.filter((k) => k.sichtbar).map((k) => inhalt[k.id](d))}
        </div>
      ) : null}
    </Seite>
  );
}
