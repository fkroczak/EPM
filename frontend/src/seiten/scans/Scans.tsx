/**
 * Menüpunkt „Scans“ (Festlegung 08.10.2026, F160 ff.): Posteingang für gescannte und fotografierte Dokumente.
 *
 * Hochladen (Knopf, Ziehen auf die Seite, am Telefon die Kamera) → Seiten werden automatisch aufbereitet und der
 * Text erkannt (OCR-Dienst, lokal) → einem Patienten zuordnen (mit Übernahme der Werte) oder den Text kopieren.
 * Nicht zugeordnete Scans werden nach der eingestellten Frist automatisch gelöscht. Aufbau wie Versorger und Ärzte:
 * links die Liste, rechts der gewählte Scan; am Telefon entweder Liste oder Scan.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateigroesse, zahl } from "@/lib/format";
import { useMobil } from "@/lib/stufen";
import type { Scan, ScanZeile, ScansStand } from "@/lib/typen";
import { Seite } from "@/components/layout/Shell";
import { Chip, Fehleranzeige, Karte, Knopf, Laden, Leer, Meldung, Seitenkopf, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import { useHinweis } from "@/components/ui/hinweise";
import { ARTEN, STATUS, bisDatum, dateiname } from "./hilfen";
import { ScanDetail } from "./ScanDetail";
import { Begriff } from "@/components/ui/Begriff";

const DATEITYPEN = ".pdf,.jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp,.heic,.heif,application/pdf,image/*";

function hatDateien(e: DragEvent) {
  return !!e.dataTransfer && Array.from(e.dataTransfer.types).includes("Files");
}

function StatusChip({ s }: { s: ScanZeile }) {
  if (s.status === "laeuft") return <Chip art="warn">wird erkannt {s.fortschritt} %</Chip>;
  if (s.status === "wartet") return <Chip art="warn">wartet</Chip>;
  if (s.status === "fehler") return <Chip art="fehler">Fehler</Chip>;
  return <Chip art="ok">{STATUS[s.status]}</Chip>;
}

export function Scans() {
  const [params, setParams] = useSearchParams();
  const mobil = useMobil();
  const qc = useQueryClient();
  const melden = useHinweis();
  const { darf } = useAuth();
  const [suche, setSuche] = useState("");
  const [ziehen, setZiehen] = useState(false);
  const [mehrere, setMehrere] = useState<File[] | null>(null);
  const [zuletzt, setZuletzt] = useState<{ patient: number; titel: string } | null>(null);
  const eingabe = useRef<HTMLInputElement>(null);
  const kamera = useRef<HTMLInputElement>(null);
  const zaehler = useRef(0);

  const stand = useQuery({ queryKey: ["scans", "stand"], queryFn: () => api<ScansStand>("scans/stand/"), refetchInterval: 60_000 });
  const liste = useQuery({
    queryKey: ["scans", "liste"],
    queryFn: () => api<ScanZeile[]>("scans/"),
    refetchInterval: (q) => (q.state.data?.some((s) => s.status === "wartet" || s.status === "laeuft") ? 2500 : 30_000),
  });
  const alle = liste.data ?? [];
  const wort = suche.trim().toLowerCase();
  const sichtbar = alle.filter((s) => !wort || [s.titel, s.originalname, s.hochgeladen_von_name ?? ""].some((t) => t.toLowerCase().includes(wort)));
  const gewaehltId = Number(params.get("id")) || (mobil ? null : sichtbar[0]?.id ?? null);
  const waehlen = (id: number | null) => setParams(id ? new URLSearchParams({ id: String(id) }) : new URLSearchParams(), { replace: !mobil });

  const hochladen = useMutation({
    mutationFn: async (gruppen: File[][]) => {
      const neu: Scan[] = [];
      for (const dateien of gruppen) {
        const form = new FormData();
        for (const d of dateien) form.append("dateien", d);
        if (dateien.length === 1) form.append("titel", dateiname(dateien[0].name));
        try {
          neu.push(await api<Scan>("scans/", { form }));
        } catch (e) {
          melden(`${dateien.map((d) => d.name).join(", ")}: ${e instanceof ApiFehler ? (e.felder.datei || e.message) : String(e)}`, "fehler");
        }
      }
      return neu;
    },
    onSuccess: (neu) => {
      void qc.invalidateQueries({ queryKey: ["scans"] });
      if (neu.length) {
        melden(neu.length === 1 ? `„${neu[0].titel}“ hochgeladen – der Text wird erkannt.` : `${neu.length} Scans hochgeladen – der Text wird erkannt.`);
        waehlen(neu[0].id);
      }
    },
  });

  const dateienGewaehlt = (liste_: FileList | File[]) => {
    const dateien = Array.from(liste_);
    if (!dateien.length) return;
    const bilder = dateien.filter((d) => d.type.startsWith("image/") || /\.(jpe?g|png|heic|heif|webp|tiff?|bmp)$/i.test(d.name));
    // mehrere Fotos: als ein Dokument mit mehreren Seiten oder als einzelne Scans? (Rückfrage)
    if (dateien.length > 1 && bilder.length === dateien.length) {
      setMehrere(dateien);
      return;
    }
    hochladen.mutate(dateien.map((d) => [d]));
  };
  const dateienRef = useRef(dateienGewaehlt);
  dateienRef.current = dateienGewaehlt;

  // Dateien irgendwo auf die Seite ziehen
  useEffect(() => {
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
      if (!hatDateien(e) || e.defaultPrevented) return;
      e.preventDefault();
      if (e.dataTransfer?.files.length) dateienRef.current(e.dataTransfer.files);
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
    };
  }, []);

  const st = stand.data;
  const naechster = (ohne: number) => sichtbar.find((s) => s.id !== ohne && s.status === "fertig")?.id ?? null;
  const zeigeDetail = gewaehltId !== null && alle.some((s) => s.id === gewaehltId);

  return (
    <Seite pfad={[{ text: "Scans" }]}>
      <Seitenkopf titel="Scans"
        unter={st ? `Nicht zugeordnete Scans werden nach ${st.frist_tage} Tagen gelöscht (verlängerbar bis ${st.hoechst_tage} Tage)` : undefined}
        rechts={<>
          {mobil ? <Knopf icon="kamera" onClick={() => kamera.current?.click()} data-testid="scan-foto">Foto</Knopf> : null}
          <Knopf variante="pri" icon="hochladen" laedt={hochladen.isPending} onClick={() => eingabe.current?.click()} data-testid="scan-hochladen">Hochladen</Knopf>
        </>} />
      <input ref={eingabe} type="file" multiple hidden accept={DATEITYPEN} data-testid="scan-datei" aria-label="Scan hochladen"
        onChange={(e) => { if (e.target.files?.length) dateienGewaehlt(e.target.files); e.target.value = ""; }} />
      <input ref={kamera} type="file" hidden accept="image/*" capture="environment" aria-label="Foto aufnehmen"
        onChange={(e) => { if (e.target.files?.length) hochladen.mutate([Array.from(e.target.files)]); e.target.value = ""; }} />

      {zuletzt ? (
        <Meldung art="ok">
          <span className="flex items-center gap-3 flex-wrap" data-testid="zuletzt-zugeordnet">
            „{zuletzt.titel}“ liegt jetzt in der Akte.
            <Link to={`/patienten/${zuletzt.patient}/dokumente`}>Akte öffnen</Link>
            <button type="button" className="btn geist klein ml-auto" onClick={() => setZuletzt(null)} aria-label="Hinweis schließen"><Icon name="x" /></button>
          </span>
        </Meldung>
      ) : null}
      {st && st.prozent >= 80 ? (
        <Meldung art="warn">Der Speicher für Scans ist zu {String(st.prozent).replace(".", ",")} % belegt ({dateigroesse(st.belegt)} von {dateigroesse(st.grenze)}).
          Bitte Scans zuordnen oder löschen – ab 100 % lassen sich keine neuen hochladen.</Meldung>
      ) : null}
      <Fehleranzeige fehler={liste.error} />

      <div className="stamm-raster">
        {liste.isLoading ? <Laden /> : (
          <Karte className={cx("stamm-liste flex flex-col min-h-0 overflow-hidden", zeigeDetail && "max-md:hidden")}>
            <div className="flex flex-col gap-2 p-2.5 border-b border-rand">
              <label className="relative block">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
                <input className="inp pl-[2.125rem]" type="search" aria-label="Scans filtern" placeholder="Titel, Datei, hochgeladen von"
                  value={suche} onChange={(e) => setSuche(e.target.value)} />
              </label>
            </div>
            <div className="grow min-h-0 overflow-y-auto overscroll-contain" role="list" aria-label="Scans" data-testid="scanliste">
              {sichtbar.map((s) => (
                <div role="listitem" key={s.id} className="flex">
                  <button type="button" aria-current={s.id === gewaehltId ? "true" : undefined} onClick={() => waehlen(s.id)}
                    className={cx("stamm-eintrag w-full text-left border-0 border-b border-rand bg-transparent cursor-pointer px-3 py-2.5 flex items-start gap-3",
                      s.id === gewaehltId && "aktiv")}>
                    {s.vorschau ? <img src={s.vorschau} alt="" className="w-11 h-14 object-cover object-top rounded border border-rand bg-white shrink-0" />
                      : <span className="w-11 h-14 rounded border border-dashed border-rand shrink-0 flex items-center justify-center gedaempft"><Icon name="scan" /></span>}
                    <span className="grow min-w-0 flex flex-col gap-1">
                      <span className="font-medium text-sm truncate">{s.titel}</span>
                      <span className="flex items-center gap-1.5 flex-wrap">
                        <StatusChip s={s} />
                        {s.arten.slice(0, 2).map((a) => <Chip key={a} art="akzent">{ARTEN[a] ?? a}</Chip>)}
                        {s.ist_test ? <Chip art="warn">Test</Chip> : null}
                        {s.quelle ? <Chip title={`Arbeitskopie von „${s.quelle.titel}“`}>aus der Akte</Chip> : null}
                      </span>
                      <span className="text-xs gedaempft truncate">
                        {zahl(s.seiten_anzahl)} S. · {s.hochgeladen_von_name ?? "—"} · <span className={cx(["heute", "morgen"].includes(bisDatum(s.laeuft_ab_am)) && "text-warn font-medium")}>
                          gelöscht {bisDatum(s.laeuft_ab_am)}</span>
                      </span>
                    </span>
                  </button>
                </div>
              ))}
              {!sichtbar.length ? (
                <div className="p-4 flex flex-col items-center gap-3 text-center">
                  <span className="gedaempft"><Icon name="scan" groesse={32} /></span>
                  <Leer>{wort ? "Kein Treffer." : "Keine Scans. Dateien hierher ziehen oder „Hochladen“ wählen."}</Leer>
                </div>
              ) : null}
            </div>
            <div className="px-3.5 py-2 border-t border-rand text-xs gedaempft flex flex-wrap gap-x-2" data-testid="scans-fuss">
              <span><span className="num">{zahl(alle.length)}</span> Scans</span>
              {st ? <span>· Speicher {String(st.prozent).replace(".", ",")} % belegt</span> : null}
              {st && st.laeuft_bald_ab ? <span className="text-warn">· {st.laeuft_bald_ab} werden in 24 Std. gelöscht</span> : null}
            </div>
          </Karte>
        )}

        {zeigeDetail ? (
          <ScanDetail id={gewaehltId!} alle={alle} onListe={() => waehlen(null)} onWeg={() => waehlen(naechster(gewaehltId!))}
            onZugeordnet={(patient, _dok, titel) => { setZuletzt({ patient, titel }); waehlen(naechster(gewaehltId!)); }} />
        ) : !liste.isLoading && !mobil ? (
          <Karte className="min-w-0 p-6 flex flex-col items-center gap-3 text-center" data-testid="scans-leer">
            <span className="gedaempft"><Icon name="hochladen" groesse={36} /></span>
            <p className="m-0 text-sm max-w-md">PDF, Fotos oder Scans hochladen: Die Seiten werden automatisch gerade gezogen und
              bereinigt, der Text wird erkannt. Danach einem Patienten zuordnen – Laborwerte, <Begriff name="bia">BIA</Begriff> und Diagnosen lassen sich dabei
              übernehmen – oder den Text kopieren.</p>
            {darf("scans_bearbeiten") ? <Knopf variante="pri" icon="hochladen" onClick={() => eingabe.current?.click()}>Hochladen</Knopf> : null}
            {st ? <span className="text-xs gedaempft">PDF, JPG, PNG, TIFF, WEBP, HEIC · bis {st.upload_max_mb} MB · bis {st.max_seiten} Seiten je Scan</span> : null}
          </Karte>
        ) : null}
      </div>

      {ziehen ? (
        <div className="akten-ablage nicht-drucken" aria-hidden="true">
          <div className="akten-ablage-kasten"><Icon name="hochladen" groesse={28} />Loslassen, um die Dateien als Scan hochzuladen
            <span className="gedaempft text-[0.8125rem]">PDF, JPG, PNG, TIFF, HEIC · mehrere Fotos werden auf Wunsch ein Dokument</span></div>
        </div>
      ) : null}

      <Dialog offen={!!mehrere} onOffen={(o) => { if (!o) setMehrere(null); }} titel={`${mehrere?.length ?? 0} Bilder hochladen`} breite={480}
        beschreibung="Sind das die Seiten eines Dokuments (z. B. ein mehrseitiger Arztbrief) oder einzelne Dokumente?"
        fuss={<>
          <Knopf onClick={() => { if (mehrere) hochladen.mutate(mehrere.map((d) => [d])); setMehrere(null); }} data-testid="einzeln">Einzelne Scans</Knopf>
          <Knopf variante="pri" onClick={() => { if (mehrere) hochladen.mutate([mehrere]); setMehrere(null); }} data-testid="ein-dokument">Ein Dokument mit {mehrere?.length} Seiten</Knopf>
        </>}>
        <ul className="m-0 pl-5 text-sm">{(mehrere ?? []).map((d) => <li key={d.name}>{d.name}</li>)}</ul>
      </Dialog>
    </Seite>
  );
}
