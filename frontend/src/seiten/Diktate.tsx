/**
 * Diktate (Wunsch 23.10.2026), seit 27.10.2026 aufgebaut wie „Scans“:
 *   links  die Liste: „Ohne Zuordnung“ (hier aufgenommen, noch keinem Patienten zugeordnet) und „Fürs Sekretariat“
 *          (abgegebene Diktate, deren Text noch nicht im Bericht steht – älteste zuerst)
 *   rechts „Neues Diktat“ oder das gewählte Diktat: nachhören, Abschrift lesen, einem Patienten zuordnen
 * Aufnehmen geht ohne Patient; beim Zuordnen entsteht ein Bericht-Entwurf (oder es hängt sich an einen vorhandenen).
 * Nicht zugeordnete Diktate werden nach 7 Tagen gelöscht.
 */
import { useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAuswahl } from "@/lib/daten";
import { datum, heuteIso, uhrzeit } from "@/lib/format";
import { useMobil } from "@/lib/stufen";
import type { Bericht, Diktat, PatientZeile } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Feld, Fehleranzeige, Karte, Knopf, KartenKopf, Laden, Leer, Meldung, Seitenkopf, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { Abschrift, DiktatAufnahme, dauerText, statusArt } from "@/components/Diktat";
import { PatientWahl } from "@/components/PatientWahl";

const AUFBEWAHREN_TAGE = 7;

function laufend(d: Diktat) {
  return d.status === "wartet" || d.status === "laeuft";
}

function StatusChip({ d }: { d: Diktat }) {
  return (
    <Chip art={statusArt(d)}>
      {d.status === "wartet" && d.wann === "nachts" ? "wartet auf die Nacht" : d.status === "fertig" && d.patient ? "zum Übernehmen" : d.status_name}
    </Chip>
  );
}

/** Berichtsart und Titel – beim Aufnehmen mit Patient und beim Zuordnen gleich */
function BerichtFelder({ art, onArt, titel, onTitel, gesperrt }: {
  art: string; onArt: (v: string) => void; titel: string; onTitel: (v: string) => void; gesperrt?: boolean;
}) {
  const arten = useAuswahl("berichtart");
  return (
    <>
      <Feld label="Berichtsart">
        {(p) => (
          <Auswahl {...p} value={art} disabled={gesperrt} onChange={(e) => onArt(e.target.value)}>
            <option value="">— ohne Angabe —</option>
            {(arten.data ?? []).map((a) => <option key={a.id} value={a.id}>{a.wert}</option>)}
          </Auswahl>
        )}
      </Feld>
      <Feld label="Titel" hinweis="Leer: nach der Berichtsart">
        {(p) => <Eingabe {...p} value={titel} maxLength={200} disabled={gesperrt} onChange={(e) => onTitel(e.target.value)}
          placeholder="z. B. Verlaufsbericht" />}
      </Feld>
    </>
  );
}

/** Neues Diktat: gleich aufnehmen; Patient optional – ohne Patient landet es links unter „Ohne Zuordnung“ */
function NeuesDiktat({ onOhneZuordnung }: { onOhneZuordnung: (d: Diktat) => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const arten = useAuswahl("berichtart");
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const [art, setArt] = useState("");
  const [titel, setTitel] = useState("");
  const [aktiv, setAktiv] = useState(false);
  const [gesendet, setGesendet] = useState<Diktat | null>(null);
  // neue Aufnahme (anderer Patient, neuer Bericht): Aufnahme-Baustein neu aufsetzen
  const [runde, setRunde] = useState(0);

  // angelegter Entwurf: scheitert das Hochladen, nimmt der zweite Versuch denselben Bericht
  const angelegt = useRef<{ patient: number; bericht: number } | null>(null);
  const entwurf = async () => {
    if (angelegt.current?.patient === patient!.id) return angelegt.current.bericht;
    const name = titel.trim() || arten.data?.find((a) => String(a.id) === art)?.wert || `Diktat vom ${datum(heuteIso())}`;
    const neu = await api<Bericht>("berichte/", { body: { patient: patient!.id, titel: name, art: art ? Number(art) : null,
      datum: heuteIso(), empfaenger: "", inhalt: "" } });
    angelegt.current = { patient: patient!.id, bericht: neu.id };
    void qc.invalidateQueries({ queryKey: ["berichte", patient!.id] });
    return neu.id;
  };

  return (
    <Karte className="min-w-0 px-5 py-4 flex flex-col gap-3" data-testid="diktat-neu">
      <KartenKopf titel="Neues Diktat" unter="Gleich aufnehmen – den Patienten jetzt wählen oder danach zuordnen." />
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12.5rem_minmax(0,1fr)]">
        <Feld label="Patient" hinweis="optional – sonst danach zuordnen">
          {(p) => <PatientWahl id={p.id} wert={patient} onWahl={(x) => {
            if (aktiv && !window.confirm("Die Aufnahme ist noch nicht gesendet. Verwerfen?")) return;
            setPatient(x); setGesendet(null); setRunde((r) => r + 1);
          }} />}
        </Feld>
        <BerichtFelder art={art} onArt={setArt} titel={titel} onTitel={setTitel} gesperrt={aktiv || !patient} />
      </div>
      <DiktatAufnahme key={`${patient?.id ?? "ohne"}-${runde}`} patientId={patient?.id ?? null} vorHochladen={patient ? entwurf : undefined}
        onAktiv={setAktiv}
        onHochgeladen={(d) => {
          angelegt.current = null; setTitel(""); setRunde((r) => r + 1);
          void qc.invalidateQueries({ queryKey: ["diktate"] });
          if (!d.patient) {
            melden("Diktat gesendet – links unter „Ohne Zuordnung“. Dort einem Patienten zuordnen.");
            onOhneZuordnung(d);
            return;
          }
          setGesendet(d);
          melden(d.wann === "nachts" ? "Diktat gesendet – es wird heute Nacht abgeschrieben."
            : "Diktat gesendet – die Abschrift erscheint im Bericht, meist nach wenigen Minuten.");
        }} />
      {gesendet?.bericht ? (
        <Meldung art="ok">
          Gesendet: <Link to={`/patienten/${gesendet.patient}/berichte?bericht=${gesendet.bericht}`}>{gesendet.bericht_titel ?? "Bericht"}</Link>
          {" "}bei {gesendet.patient_name}. Ein weiteres Diktat wird ein neuer Bericht.
        </Meldung>
      ) : null}
    </Karte>
  );
}

/** Ein Diktat rechts: Stand, Abschrift zum Nachhören, zuordnen bzw. zum Bericht */
function DiktatDetail({ d, onListe, onWeg }: { d: Diktat; onListe: () => void; onWeg: () => void }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const { darf } = useAuth();
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const [art, setArt] = useState("");
  const [titel, setTitel] = useState("");
  const neu = () => void qc.invalidateQueries({ queryKey: ["diktate"] });
  const zuordnen = useMutation({
    mutationFn: () => {
      if (!patient) throw new ApiFehler(400, "", null, { patient: "Bitte den Patienten wählen." });
      return api<Diktat>(`diktate/${d.id}/zuordnen/`, { body: { patient: patient.id, art: art ? Number(art) : null, titel: titel.trim() } });
    },
    onSuccess: (z) => { neu(); melden(`Zugeordnet: „${z.bericht_titel ?? "Bericht"}“ bei ${z.patient_name}.`); },
  });
  const erneut = useMutation({ mutationFn: () => api<Diktat>(`diktate/${d.id}/erneut/`, { body: {} }), onSuccess: neu });
  const verwerfen = useMutation({
    mutationFn: () => api(`diktate/${d.id}/`, { method: "DELETE" }),
    onSuccess: () => { neu(); melden("Diktat verworfen."); onWeg(); },
  });
  const fehler = zuordnen.error instanceof ApiFehler ? zuordnen.error.felder : {};
  const bis = new Date(new Date(d.erstellt_am).getTime() + AUFBEWAHREN_TAGE * 86400000);

  return (
    <Karte className="min-w-0 px-5 py-4 flex flex-col gap-3" data-testid="diktat-detail">
      <div className="flex items-center gap-2 flex-wrap">
        <button type="button" className="btn sec klein md:hidden" onClick={onListe}><Icon name="zurueck" groesse={14} />Liste</button>
        <h2 className="m-0 text-lg font-semibold">Diktat vom {datum(d.erstellt_am)}, {uhrzeit(d.erstellt_am)} Uhr</h2>
        <StatusChip d={d} />
        {d.status === "fertig" && d.unsicher ? <Chip art="warn">{d.unsicher} unsicher</Chip> : null}
      </div>
      <span className="text-[0.8125rem] gedaempft">
        <span className="num">{dauerText(d.dauer_s)}</span> · {d.erstellt_von_name ?? "—"}
        {d.uebergabe === "sekretariat" ? " · ans Sekretariat" : ""}
        {!d.patient ? ` · ohne Zuordnung gelöscht am ${datum(bis.toISOString())}` : ""}
      </span>

      {laufend(d) ? <span className="text-sm gedaempft">{d.schritt || (d.wann === "nachts"
        ? "Wird heute Nacht abgeschrieben." : "Wartet auf die Abschrift – meist nach wenigen Minuten fertig.")}</span> : null}
      {d.status === "fehler" ? <Meldung art="fehler">{d.fehler}</Meldung> : null}
      {d.status === "fertig" ? <div className="rounded-lg border border-rand bg-grund p-3"><Abschrift diktat={d} /></div> : null}

      {d.patient ? (
        <Meldung art="info">
          <span className="flex items-center gap-3 flex-wrap">
            Bei <Link to={`/patienten/${d.patient}`}>{d.patient_name}</Link> im Bericht „{d.bericht_titel ?? "Bericht"}“.
            <Link to={`/patienten/${d.patient}/berichte?bericht=${d.bericht}`} className="font-medium">Bericht öffnen</Link>
          </span>
        </Meldung>
      ) : (
        <div className="flex flex-col gap-3 border-t border-rand pt-3" data-testid="diktat-zuordnen">
          <h3 className="lbl m-0">Einem Patienten zuordnen</h3>
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12.5rem_minmax(0,1fr)]">
            <Feld label="Patient" pflicht fehler={fehler.patient}>
              {(p) => <PatientWahl id={p.id} wert={patient} onWahl={(x) => { setPatient(x); zuordnen.reset(); }} fehler={!!fehler.patient} />}
            </Feld>
            <BerichtFelder art={art} onArt={setArt} titel={titel} onTitel={setTitel} />
          </div>
          <span className="text-[0.8125rem] gedaempft">Beim Zuordnen entsteht ein neuer Bericht-Entwurf in der Akte; die Abschrift
            übernehmen Sie dort mit „In den Text übernehmen“.</span>
          <div className="flex gap-2 flex-wrap">
            <Knopf variante="pri" icon="haken" laedt={zuordnen.isPending} onClick={() => zuordnen.mutate()}>Zuordnen</Knopf>
          </div>
          {zuordnen.error && !Object.keys(fehler).length ? <Fehleranzeige fehler={zuordnen.error} /> : null}
        </div>
      )}

      {darf("eintraege_erfassen") || !d.patient ? (
        <div className="flex gap-2 flex-wrap">
          {d.status === "fehler" && d.audio ? <Knopf klein icon="neustart" laedt={erneut.isPending} onClick={() => erneut.mutate()}>Erneut abschreiben</Knopf> : null}
          <Knopf klein variante="dng" laedt={verwerfen.isPending}
            onClick={() => { if (window.confirm("Diktat mit Aufnahme und Abschrift verwerfen?")) verwerfen.mutate(); }}>Verwerfen</Knopf>
        </div>
      ) : null}
      <Fehleranzeige fehler={erneut.error ?? verwerfen.error} />
    </Karte>
  );
}

function Eintrag({ d, aktiv, onWahl }: { d: Diktat; aktiv: boolean; onWahl: () => void }) {
  return (
    <div role="listitem" className="flex">
      <button type="button" aria-current={aktiv ? "true" : undefined} onClick={onWahl}
        className={cx("stamm-eintrag w-full text-left border-0 border-b border-rand bg-transparent cursor-pointer px-3 py-2.5 flex items-start gap-3", aktiv && "aktiv")}>
        <span className="w-9 h-9 rounded-full border border-rand shrink-0 flex items-center justify-center gedaempft"><Icon name="mikrofon" /></span>
        <span className="grow min-w-0 flex flex-col gap-1">
          <span className="font-medium text-sm truncate">{d.patient_name ?? `Diktat vom ${datum(d.erstellt_am)}`}</span>
          <span className="flex items-center gap-1.5 flex-wrap">
            <StatusChip d={d} />
            {d.status === "fertig" && d.unsicher ? <Chip art="warn">{d.unsicher} unsicher</Chip> : null}
          </span>
          <span className="text-xs gedaempft truncate">
            {d.patient ? `${d.bericht_titel ?? "Bericht"} · ` : ""}<span className="num">{datum(d.erstellt_am)} {uhrzeit(d.erstellt_am)}</span>
            {" · "}<span className="num">{dauerText(d.dauer_s)}</span>{d.erstellt_von_name ? ` · ${d.erstellt_von_name}` : ""}
          </span>
        </span>
      </button>
    </div>
  );
}

export function Diktate() {
  const { darf } = useAuth();
  const mobil = useMobil();
  const [params, setParams] = useSearchParams();
  const gewaehltId = Number(params.get("diktat")) || null;
  const waehlen = (id: number | null) => setParams(id ? { diktat: String(id) } : {}, { replace: true });
  const takt = (q: { state: { data?: Diktat[] } }) => ((q.state.data ?? []).some(laufend) ? 5000 : 30_000);
  const eingang = useQuery({ queryKey: ["diktate", "eingang"], queryFn: () => api<Diktat[]>("diktate/eingang/"), refetchInterval: takt });
  const offen = useQuery({ queryKey: ["diktate", "offen"], queryFn: () => api<Diktat[]>("diktate/offen/"), refetchInterval: 30_000 });
  // gewähltes Diktat einzeln (auch nach dem Zuordnen, wenn es nicht mehr im Eingang steht)
  const gewaehlt = useQuery({
    queryKey: ["diktate", "eins", gewaehltId],
    queryFn: () => api<Diktat>(`diktate/${gewaehltId}/`),
    enabled: !!gewaehltId,
    refetchInterval: (q) => (q.state.data && laufend(q.state.data) ? 5000 : false),
  });
  const ohne = eingang.data ?? [];
  const sekretariat = offen.data ?? [];
  const zeigeDetail = !!gewaehltId;

  return (
    <Seite pfad={[{ text: "Diktate" }]}>
      <Seitenkopf titel="Diktate" unter={`Aufnehmen, danach einem Patienten zuordnen. Nicht zugeordnete Diktate werden nach ${AUFBEWAHREN_TAGE} Tagen gelöscht.`}
        rechts={darf("diktieren") && zeigeDetail ? <Knopf variante="pri" icon="mikrofon" onClick={() => waehlen(null)}>Neues Diktat</Knopf> : null} />
      <Fehleranzeige fehler={eingang.error ?? offen.error} />
      <div className="stamm-raster">
        <Karte className={cx("stamm-liste flex flex-col min-h-0 overflow-hidden", zeigeDetail && "max-md:hidden")}>
          <div className="grow min-h-0 overflow-y-auto overscroll-contain" data-testid="diktatliste">
            <h2 className="lbl m-0 px-3.5 pt-3 pb-1.5">Ohne Zuordnung <span className="num gedaempft font-normal">{ohne.length}</span></h2>
            {eingang.isPending ? <Laden /> : ohne.length ? (
              <div role="list" aria-label="Ohne Zuordnung" data-testid="diktate-eingang">
                {ohne.map((d) => <Eintrag key={d.id} d={d} aktiv={d.id === gewaehltId} onWahl={() => waehlen(d.id)} />)}
              </div>
            ) : <div className="px-3.5 pb-3"><Leer>Keine – hier aufgenommene Diktate ohne Patient erscheinen hier.</Leer></div>}
            <h2 className="lbl m-0 px-3.5 pt-3 pb-1.5 border-t border-rand">Fürs Sekretariat <span className="num gedaempft font-normal">{sekretariat.length}</span></h2>
            {offen.isPending ? <Laden /> : sekretariat.length ? (
              <div role="list" aria-label="Fürs Sekretariat" data-testid="diktate-offen">
                {sekretariat.map((d) => <Eintrag key={d.id} d={d} aktiv={d.id === gewaehltId} onWahl={() => waehlen(d.id)} />)}
              </div>
            ) : <div className="px-3.5 pb-3"><Leer>Keine offenen Diktate.</Leer></div>}
          </div>
          <div className="px-3.5 py-2 border-t border-rand text-xs gedaempft">
            Im Bericht: nachhören, „In den Text übernehmen“, korrigieren, speichern.
          </div>
        </Karte>

        {zeigeDetail ? (
          gewaehlt.isPending ? <Laden /> : gewaehlt.data ? (
            <DiktatDetail key={gewaehlt.data.id} d={gewaehlt.data} onListe={() => waehlen(null)} onWeg={() => waehlen(null)} />
          ) : (
            <Karte className="min-w-0 px-5 py-4 flex flex-col gap-3">
              <Meldung art="info">Dieses Diktat gibt es nicht mehr – es wurde verworfen oder ist abgelaufen.</Meldung>
              <Knopf className="self-start" onClick={() => waehlen(null)}>Zurück</Knopf>
            </Karte>
          )
        ) : darf("diktieren") ? <NeuesDiktat onOhneZuordnung={(d) => waehlen(d.id)} />
          : !mobil ? <Karte className="min-w-0 p-6 text-sm gedaempft">Links ein Diktat wählen.</Karte> : null}
      </div>
    </Seite>
  );
}
