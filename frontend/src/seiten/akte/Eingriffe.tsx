/**
 * Reiter „Eingriffe“ der Regeneration Clinic (Wunsch 21.11.2026): durchgeführte Therapie oder Operation mit OPS- und
 * ICD-Code.
 *
 * Ablauf beantragt → genehmigt → durchgeführt (oder abgelehnt). Sobald ein Eingriff genehmigt oder als durchgeführt
 * eingetragen ist, steht seine Diagnose in der Diagnoseliste der Akte – eine schon vorhandene Diagnose mit demselben
 * ICD-Code wird verknüpft, nicht doppelt angelegt. Aufbau wie alle Reiter (F122): links die Einträge, rechts der
 * gewählte. Nichts wird gelöscht; „Entfernen“ nimmt einen falschen Eintrag heraus, er bleibt im Verlauf.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, alle, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { useAuswahl, useDiagnoseliste, useOpsliste } from "@/lib/daten";
import { datum, eingabeDatum } from "@/lib/format";
import { EINGRIFF_STATUS } from "@/lib/typen";
import type { Dokument, Eingriff } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Feld, Knopf, KnopfLink, Meldung } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { FirmaMarke } from "@/components/FirmenWahl";
import { Bestaetigen } from "@/components/Bestaetigen";
import { useAkte } from "./Akte";
import { Abschnitt, Aktenseite, Detail, Eintrag, Eintragsliste, Wertetabelle, useWahl } from "./Aktenseite";

const OPS_LISTE = "opsliste-eingriff";
const DIAGNOSE_LISTE = "diagnoseliste-eingriff";

/** Status als Marke: genehmigt und durchgeführt grün, abgelehnt rot, beantragt neutral */
function StatusChip({ e }: { e: Eingriff }) {
  const art = !e.aktiv ? "neutral" : e.status === "abgelehnt" ? "fehler" : e.status === "beantragt" ? "warn" : "ok";
  return <Chip art={art}>{e.aktiv ? e.status_name : "entfernt"}</Chip>;
}

function EingriffDialog({ eingriff, offen, onOffen, onGespeichert }: {
  eingriff: Eingriff | null; offen: boolean; onOffen: (o: boolean) => void; onGespeichert: (e: Eingriff) => void;
}) {
  const { patient } = useAkte();
  const ops = useOpsliste();
  const diagnosen = useDiagnoseliste();
  const typen = useAuswahl("dokumenttyp", false);
  const qc = useQueryClient();
  const melden = useHinweis();
  // Dokumente der Akte zum Verknüpfen (z. B. der OP-Bericht)
  const dokumente = useQuery({
    queryKey: ["patient", patient.id, "dokumente", false, ""],
    queryFn: () => alle<Dokument>(`dokumente/${abfrage({ patient: patient.id, ausgeblendet: "false" })}`),
    enabled: offen,
  });
  const [art, setArt] = useState(eingriff?.art ?? "operation");
  const [bezeichnung, setBezeichnung] = useState(eingriff?.bezeichnung ?? "");
  const [opsCodes, setOpsCodes] = useState(eingriff?.ops_codes ?? "");
  const [am, setAm] = useState(eingriff?.datum ? datum(eingriff.datum) : "");
  const [diagnose, setDiagnose] = useState(eingriff?.diagnose_bezeichnung ?? "");
  const [icd, setIcd] = useState(eingriff?.icd_code ?? "");
  // Festlegung 21.11.2026 (U77): immer „G – gesichert“
  const kennzeichen = "G";
  const [status, setStatus] = useState<Eingriff["status"]>(eingriff?.status ?? "beantragt");
  const [genehmigtAm, setGenehmigtAm] = useState(eingriff?.genehmigt_am ? datum(eingriff.genehmigt_am) : "");
  const [genehmigung, setGenehmigung] = useState(eingriff?.genehmigung ?? "");
  const [dokument, setDokument] = useState(eingriff?.dokument ? String(eingriff.dokument) : "");
  const [notiz, setNotiz] = useState(eingriff?.notiz ?? "");

  /** Aus der OPS-Liste gewählt: Bezeichnung und Code zusammen übernehmen */
  const ausOps = (text: string) => {
    setBezeichnung(text);
    const t = (ops.data ?? []).find((o) => o.bezeichnung === text);
    if (t && !opsCodes.trim()) setOpsCodes(t.ops_code);
  };
  const ausDiagnosen = (text: string) => {
    setDiagnose(text);
    const t = (diagnosen.data ?? []).find((d) => d.bezeichnung === text);
    if (t) setIcd(t.icd_code);
  };

  const speichern = useMutation({
    mutationFn: () => {
      const iso = (feld: string, wert: string) => {
        if (!wert.trim()) return null;
        const d = eingabeDatum(wert);
        if (!d) throw new ApiFehler(400, "", null, { [feld]: "Bitte als TT.MM.JJJJ eingeben." });
        return d;
      };
      const koerper = { patient: patient.id, art, bezeichnung: bezeichnung.trim(), ops_codes: opsCodes.trim(),
        datum: iso("datum", am), diagnose_bezeichnung: diagnose.trim(), icd_code: icd.trim().toUpperCase(),
        status, genehmigt_am: iso("genehmigt_am", genehmigtAm), genehmigung: genehmigung.trim(),
        dokument: dokument ? Number(dokument) : null, notiz: notiz.trim() };
      return eingriff
        ? api<Eingriff>(`eingriffe/${eingriff.id}/`, { method: "PATCH", body: koerper })
        : api<Eingriff>("eingriffe/", { body: koerper });
    },
    onSuccess: (e) => {
      void qc.invalidateQueries({ queryKey: ["eingriffe", patient.id] });
      void qc.invalidateQueries({ queryKey: ["diagnosen", patient.id] });
      void qc.invalidateQueries({ queryKey: ["opsliste"] });
      void qc.invalidateQueries({ queryKey: ["diagnoseliste"] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden(e.diagnose && !eingriff?.diagnose ? "Eingriff gespeichert, Diagnose in die Diagnoseliste übernommen."
        : eingriff ? "Eingriff geändert." : "Eingriff eingetragen.");
      onGespeichert(e);
      onOffen(false);
    },
  });
  const f: Feldfehler = speichern.error instanceof ApiFehler ? speichern.error.felder : {};
  const uebernahme = status === "genehmigt" || status === "durchgefuehrt";
  // OP-Berichte zuerst, dann die übrigen Dokumente
  const opTyp = (typen.data ?? []).find((t) => t.kennung === "op_bericht")?.id;
  const doks = [...(dokumente.data ?? [])].sort((a, b) => Number(b.typ === opTyp) - Number(a.typ === opTyp));

  return (
    <Dialog offen={offen} onOffen={onOffen} breite={680} titel={eingriff ? "Eingriff ändern" : "Neuer Eingriff"}
      beschreibung="Therapie oder Operation mit OPS-Code; die Diagnose wandert mit der Genehmigung in die Diagnoseliste."
      fuss={<>
        <Knopf onClick={() => onOffen(false)}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={speichern.isPending} disabled={!bezeichnung.trim() || !diagnose.trim() || !icd.trim()}
          onClick={() => speichern.mutate()}>Speichern</Knopf>
      </>}>
      <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
        <Feld label="Art" fehler={f.art} pflicht>
          {(p) => (
            <Auswahl {...p} value={art} onChange={(e) => setArt(e.target.value as Eingriff["art"])}>
              <option value="operation">Operation</option>
              <option value="therapie">Therapie</option>
            </Auswahl>
          )}
        </Feld>
        <Feld label={art === "operation" ? "Operation" : "Therapie"} fehler={f.bezeichnung} pflicht
          hinweis="Aus der Liste wählen oder neu eintragen – mit einem OPS-Code wandert sie in die Liste.">
          {(p) => <>
            <Eingabe {...p} list={OPS_LISTE} value={bezeichnung} maxLength={200} onChange={(e) => ausOps(e.target.value)}
              placeholder={art === "operation" ? "z. B. Dünndarmresektion" : "z. B. Teduglutid"} />
            <datalist id={OPS_LISTE}>
              {(ops.data ?? []).map((o) => <option key={o.id} value={o.bezeichnung}>{o.ops_code}</option>)}
            </datalist>
          </>}
        </Feld>
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
        <Feld label="OPS-Codes" fehler={f.ops_codes} hinweis="Mehrere mit Komma trennen, z. B. „5-455.01, 5-469.20“.">
          {(p) => <Eingabe {...p} className="num" value={opsCodes} maxLength={200} placeholder="5-455.01"
            onChange={(e) => setOpsCodes(e.target.value)} />}
        </Feld>
        <Feld label={status === "durchgefuehrt" ? "durchgeführt am" : "geplant am"} fehler={f.datum}>
          {(p) => <Eingabe {...p} className="num" value={am} placeholder="TT.MM.JJJJ" onChange={(e) => setAm(e.target.value)} />}
        </Feld>
      </div>
      <Feld label="Diagnose" fehler={f.diagnose_bezeichnung} pflicht>
        {(p) => <>
          <Eingabe {...p} list={DIAGNOSE_LISTE} value={diagnose} maxLength={200} onChange={(e) => ausDiagnosen(e.target.value)}
            placeholder="z. B. Kurzdarmsyndrom" />
          <datalist id={DIAGNOSE_LISTE}>
            {(diagnosen.data ?? []).map((d) => <option key={d.id} value={d.bezeichnung}>{d.icd_code}</option>)}
          </datalist>
        </>}
      </Feld>
      <Feld label="ICD-Code" fehler={f.icd_code} pflicht hinweis="Kommt als „G – gesichert“ in die Diagnoseliste.">
        {(p) => <Eingabe {...p} className="num w-[8.75rem]" value={icd} maxLength={10} placeholder="K91.2"
          onChange={(e) => setIcd(e.target.value.toUpperCase())} />}
      </Feld>
      <div className="grid gap-3 sm:grid-cols-[10rem_10rem_1fr]">
        <Feld label="Stand" fehler={f.status} pflicht>
          {(p) => (
            <Auswahl {...p} value={status} onChange={(e) => setStatus(e.target.value as Eingriff["status"])}>
              {Object.entries(EINGRIFF_STATUS).map(([k, text]) => <option key={k} value={k}>{text}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="genehmigt am" fehler={f.genehmigt_am}>
          {(p) => <Eingabe {...p} className="num" value={genehmigtAm} placeholder={uebernahme ? "heute" : "TT.MM.JJJJ"}
            onChange={(e) => setGenehmigtAm(e.target.value)} />}
        </Feld>
        <Feld label="Genehmigung" fehler={f.genehmigung} hinweis="Kostenträger, Aktenzeichen">
          {(p) => <Eingabe {...p} value={genehmigung} maxLength={200} onChange={(e) => setGenehmigung(e.target.value)} />}
        </Feld>
      </div>
      <Feld label="Dokument" fehler={f.dokument} hinweis="z. B. der OP-Bericht aus den Dokumenten der Akte">
        {(p) => (
          <Auswahl {...p} value={dokument} onChange={(e) => setDokument(e.target.value)}>
            <option value="">— keins —</option>
            {doks.map((d) => <option key={d.id} value={d.id}>{d.titel}{d.typ_name ? ` (${d.typ_name})` : ""}{d.datum ? ` · ${datum(d.datum)}` : ""}</option>)}
          </Auswahl>
        )}
      </Feld>
      <Feld label="Notiz" fehler={f.notiz}>
        {(p) => <Eingabe {...p} value={notiz} maxLength={300} onChange={(e) => setNotiz(e.target.value)} />}
      </Feld>
      <Meldung art="info">
        {eingriff?.diagnose ? <>Die Diagnose steht schon in der Diagnoseliste: <strong>{eingriff.diagnose_anzeige}</strong>.</>
          : uebernahme ? <>Beim Speichern kommt <strong>{diagnose.trim() || "die Diagnose"} [{(icd.trim() || "ICD").toUpperCase()}{kennzeichen}]</strong> in die Diagnoseliste.</>
          : <>Mit „genehmigt“ oder „durchgeführt“ kommt <strong>{diagnose.trim() || "die Diagnose"} [{(icd.trim() || "ICD").toUpperCase()}{kennzeichen}]</strong> in die Diagnoseliste.</>}
      </Meldung>
      {speichern.error && !Object.keys(f).length ? <Meldung art="fehler">{speichern.error.message}</Meldung> : null}
    </Dialog>
  );
}

function EingriffDetail({ e, bearbeiten, onAendern, onStatus, onAktiv }: {
  e: Eingriff; bearbeiten: boolean; onAendern: () => void; onStatus: (s: Eingriff["status"]) => void; onAktiv: () => void;
}) {
  const { patient } = useAkte();
  return (
    <Detail testid="eingriff-detail"
      titel={<>{e.bezeichnung} <StatusChip e={e} /></>}
      unter={<>{e.art_name}{e.datum ? <> · <span className="num">{datum(e.datum)}</span></> : null}{e.angelegt_von_name ? ` · eingetragen von ${e.angelegt_von_name}` : ""}</>}
      aktionen={bearbeiten ? <>
        {e.aktiv && e.status === "beantragt" ? <Knopf klein variante="pri" onClick={() => onStatus("genehmigt")}>Genehmigt</Knopf> : null}
        {e.aktiv && (e.status === "beantragt" || e.status === "genehmigt") ? <Knopf klein onClick={() => onStatus("durchgefuehrt")}>Durchgeführt</Knopf> : null}
        {e.aktiv ? <Knopf klein icon="stift" onClick={onAendern}>Bearbeiten</Knopf> : null}
        <Knopf klein variante="geist" onClick={onAktiv}>{e.aktiv ? "Entfernen" : "Wieder aufnehmen"}</Knopf>
      </> : undefined}>
      <Wertetabelle spalten={2} werte={[
        ["OPS", e.ops_codes || "—"],
        ["Diagnose (ICD)", `${e.icd_code} ${e.kennzeichen}`],
        ["genehmigt am", e.genehmigt_am ? datum(e.genehmigt_am) : "—"],
        ["Genehmigung", e.genehmigung || "—"],
      ]} />
      <Abschnitt titel="Diagnose">
        <div className="flex items-center gap-2 flex-wrap text-sm">
          <span>{e.diagnose_bezeichnung} [{e.icd_code}{e.kennzeichen}]</span>
          {e.diagnose ? <Chip art="ok">in der Diagnoseliste</Chip>
            : e.status === "abgelehnt" || !e.aktiv ? <Chip>nicht übernommen</Chip>
            : <Chip art="warn">kommt mit der Genehmigung in die Diagnoseliste</Chip>}
          {e.diagnose ? <KnopfLink klein variante="geist" to={`/patienten/${patient.id}/diagnosen?eintrag=${e.diagnose}`}>Zur Diagnose</KnopfLink> : null}
        </div>
      </Abschnitt>
      {e.dokument ? (
        <Abschnitt titel="Dokument">
          <KnopfLink klein variante="geist" icon="dokument" to={`/patienten/${patient.id}/dokumente?dokument=${e.dokument}`}>{e.dokument_titel}</KnopfLink>
        </Abschnitt>
      ) : null}
      {e.notiz ? <Abschnitt titel="Notiz"><p className="m-0 text-sm">{e.notiz}</p></Abschnitt> : null}
      <span className="text-[0.8125rem] gedaempft"><FirmaMarke kurz={e.firma_kurz} /></span>
    </Detail>
  );
}

export function Eingriffe() {
  const { patient, bearbeiten } = useAkte();
  const qc = useQueryClient();
  const melden = useHinweis();
  const [wahl, setWahl] = useWahl("eintrag");
  const [dialog, setDialog] = useState<{ offen: boolean; eingriff: Eingriff | null; nr: number }>({ offen: false, eingriff: null, nr: 0 });
  const oeffnen = (eingriff: Eingriff | null) => setDialog((d) => ({ offen: true, eingriff, nr: d.nr + 1 }));
  const [frage, setFrage] = useState<{ e: Eingriff; status?: Eingriff["status"] } | null>(null);
  const [entfernteAn, setEntfernte] = useState(false);

  const eingriffe = useQuery({
    queryKey: ["eingriffe", patient.id],
    queryFn: () => api<Eingriff[]>(`eingriffe/${abfrage({ patient: patient.id })}`),
  });
  const aendern = useMutation({
    mutationFn: ({ e, status }: { e: Eingriff; status?: Eingriff["status"] }) =>
      api<Eingriff>(`eingriffe/${e.id}/`, { method: "PATCH", body: status ? { status } : { aktiv: !e.aktiv } }),
    onSuccess: (e, { e: vorher }) => {
      void qc.invalidateQueries({ queryKey: ["eingriffe", patient.id] });
      void qc.invalidateQueries({ queryKey: ["diagnosen", patient.id] });
      void qc.invalidateQueries({ queryKey: ["patient", patient.id] });
      melden(e.diagnose && !vorher.diagnose ? `${e.status_name} – Diagnose in die Diagnoseliste übernommen.`
        : e.aktiv !== vorher.aktiv ? (e.aktiv ? "Eingriff wieder aufgenommen." : "Eingriff entfernt.") : `Als ${e.status_name} eingetragen.`);
      setFrage(null);
    },
  });

  const liste = eingriffe.data ?? [];
  const aktuelle = liste.filter((e) => e.aktiv);
  const entfernte = liste.filter((e) => !e.aktiv);
  const zeigeEntfernte = entfernteAn || entfernte.some((e) => String(e.id) === wahl);
  const sichtbar = zeigeEntfernte ? liste : aktuelle;
  const gewaehlt = sichtbar.find((e) => String(e.id) === wahl) ?? sichtbar[0];

  return (
    <>
      <Aktenseite
        testid="eingriffe"
        titel={aktuelle.length === 1 ? "Eingriff" : "Eingriffe"}
        anzahl={aktuelle.length}
        laedt={eingriffe.isPending}
        aktion={bearbeiten ? <Knopf variante="pri" icon="plus" onClick={() => oeffnen(null)}>Neuer Eingriff</Knopf> : undefined}
        liste={
          <Eintragsliste name="Eingriffe" leer={sichtbar.length ? undefined : "Noch kein Eingriff eingetragen."}>
            {sichtbar.map((e) => (
              <Eintrag key={e.id} aktiv={gewaehlt?.id === e.id} onWahl={() => setWahl(String(e.id))} warnung={e.aktiv && e.status === "beantragt"}
                datum={<>{e.datum ? datum(e.datum) : "ohne Datum"}<FirmaMarke kurz={e.firma_kurz} className="ml-1.5" /></>}
                merkmal={<StatusChip e={e} />}
                zeile={e.bezeichnung}
                unten={[e.ops_codes ? `OPS ${e.ops_codes}` : e.art_name, `${e.icd_code}${e.kennzeichen}`].join(" · ")} />
            ))}
          </Eintragsliste>
        }
        fuss={<>
          Ab „genehmigt“ steht die Diagnose in der Diagnoseliste.
          {entfernte.length ? <> <button type="button" className="bg-transparent border-0 p-0 underline cursor-pointer gedaempft"
            onClick={() => setEntfernte((x) => !x)}>{zeigeEntfernte ? "Entfernte ausblenden" : `${entfernte.length} entfernte anzeigen`}</button></> : null}
        </>}
        detail={gewaehlt ? <EingriffDetail e={gewaehlt} bearbeiten={bearbeiten} onAendern={() => oeffnen(gewaehlt)}
          onStatus={(status) => { aendern.reset(); setFrage({ e: gewaehlt, status }); }}
          onAktiv={() => { aendern.reset(); if (gewaehlt.aktiv) setFrage({ e: gewaehlt }); else aendern.mutate({ e: gewaehlt }); }} /> : null}
        leer="Links einen Eingriff wählen."
      />
      {bearbeiten ? <Bestaetigen offen={!!frage} onOffen={(o) => { if (!o) setFrage(null); }}
        titel={frage?.status ? `Als ${EINGRIFF_STATUS[frage.status]} eintragen` : "Eingriff entfernen"}
        knopf={frage?.status ? EINGRIFF_STATUS[frage.status].replace(/^./, (c) => c.toUpperCase()) : "Entfernen"}
        text={frage?.status
          ? <>„{frage.e.bezeichnung}“ wird als {EINGRIFF_STATUS[frage.status]} eingetragen (Datum heute).{frage.e.diagnose ? null
            : <> Die Diagnose <strong>{frage.e.diagnose_bezeichnung} [{frage.e.icd_code}{frage.e.kennzeichen}]</strong> kommt in die Diagnoseliste.</>}</>
          : <>„{frage?.e.bezeichnung}“ wird aus der Liste genommen und bleibt im Verlauf. Eine schon übernommene Diagnose bleibt stehen.</>}
        laedt={aendern.isPending} fehler={aendern.error} onJa={() => frage && aendern.mutate(frage)} /> : null}
      {bearbeiten ? <EingriffDialog key={dialog.nr} eingriff={dialog.eingriff} offen={dialog.offen}
        onOffen={(o) => setDialog((d) => ({ ...d, offen: o }))} onGespeichert={(e) => setWahl(String(e.id))} /> : null}
    </>
  );
}
