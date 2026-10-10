/**
 * Entwurf 11 · Administration › Backup (F61–F64, Recht „Sicherungen verwalten“, Standard: nur Admin).
 *
 * Sicherungen (täglich 02:00, „Jetzt sichern“), Verschlüsselung mit einem Passwort, das hier festgelegt wird
 * (Festlegung 02.10.2026: symmetrisch, GnuPG/AES-256; das Passwort liegt nur auf dem Server und gehört ausgedruckt in
 * den Tresor), Übertragung in einen WebDAV-Ordner (Nextcloud) im Zeitfenster, Wiederherstellen mit Admin-Passwort und
 * 2FA. Alles läuft als Auftrag über den Systemagenten auf dem Server; Passwörter stehen nie in der Datenbank.
 *
 * Fehlerliste 02.10.2026, Punkt 5: Sicherung herunterladen (der Server legt sie für 2 Stunden als eine Datei bereit),
 * Aufbewahrung 7/14/30 Tage wählbar, heruntergeladene Sicherung wieder hochladen (in Stücken, mit Fortschritt) – z. B.
 * Altdaten auf der Migrationsmaschine importieren, dort sichern, hier hochladen und wiederherstellen.
 * Bestätigungen: Passwort, dazu der Code nur, wenn die Person eine Zwei-Faktor-Anmeldung eingerichtet hat (6.5).
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { AuftragFortschritt, LaufendeAuftraege } from "@/components/AuftragFortschritt";
import { useHintergrundarbeit } from "@/lib/laden";
import type { Feldfehler } from "@/lib/api";
import { useIch } from "@/lib/auth";
import { dateigroesse, relativ, uhrzeit, zeitpunkt } from "@/lib/format";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Seitenkopf,
  Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { PdfDialog } from "@/components/PdfDialog";
import { useZweiterFaktor } from "@/components/ZweiterFaktor";
import type { ZweiterFaktorWert } from "@/components/ZweiterFaktor";
import { ZweiFaktorFehlt } from "@/components/ZweiFaktorFehlt";

// ---------------------------------------------------------------- Typen (GET /api/backup/)
type Sicherung = {
  stempel: string; zeitpunkt: string | null; art: string; art_name: string; ausgeloest_von: string;
  verschluesselt: boolean; verfahren: string; passwort_nr: number | null; groesse: number; dateien: string[];
  dokumente: boolean; loeschliste: boolean; pruefsummen: boolean; epm_version: string; uebertragen_am: string | null;
  uebertragen: boolean; wiederherstellbar: boolean; nicht_wiederherstellbar_weil: string;
};
type Version = { nr: number; gesetzt_am: string | null; gesetzt_von: string; entfernt_am: string | null; sicherungen: number };
type Kurz = { zustand: "ok" | "warnung" | "fehler" | "unbekannt"; letzte_am: string | null; verschluesselt: boolean | null;
  titel: string; hinweise: string[] };
type Ziel = { eingerichtet: boolean; url?: string; benutzer?: string; ordner?: string; von?: string; bis?: string;
  hersteller?: string; gesetzt_am?: string | null; gesetzt_von?: string;
  /** Tage, die Sicherungen im Ziel bleiben; 0 = nie löschen (Festlegung 03.10.2026, Standard 30) */
  aufbewahrung_tage?: number };
/** Aufbewahrung im Übertragungsziel (wie im Systemagenten) */
const ZIEL_AUFBEWAHRUNG = [0, 14, 30, 60, 90, 180, 365];
const zielAufbewahrung = (t: number | undefined) => (t === 0 ? "nie löschen" : `${t ?? 30} Tage`);
type Uebertragung = { letzter_versuch?: string | null; letzter_erfolg?: string | null; letzter_fehler?: string; laeuft?: boolean;
  offen?: number; im_zeitfenster?: boolean; naechstes_fenster?: string | null; rclone?: boolean;
  im_ziel_entfernt?: { am: string; anzahl: number } | null };
type Aktion = { name: string; bestaetigung: "keine" | "einfach" | "2fa"; beschreibung: string; sichern?: boolean;
  warnen?: boolean; hinweis?: string };
type Auftrag = { id: number; kennung: string; ziel: "server" | "epm"; aktion: string; name: string;
  status: "wartet" | "laeuft" | "erledigt" | "fehler" | "abgebrochen"; status_name: string; offen: boolean;
  parameter: { minuten?: number; stempel?: string; url?: string; tage?: number; datei?: string; upload?: string }; angefordert_von_name: string | null; angefordert_am: string;
  begonnen_am: string | null; beendet_am: string | null; ergebnis: string; ausgabe: string; rueckgabe: number | null;
  probelauf: boolean };
type Bereit = { stempel: string; groesse: number | null; bis: string | null };
type Upload = { upload: string; name: string; groesse: number; erhalten: number; vollstaendig: boolean; von: string; begonnen_am: string | null };
export type Daten = {
  agent: { verzeichnis: boolean; erreichbar: boolean };
  status: { vorhanden: boolean; aktuell: boolean; zeit: string | null; alter_s: number | null };
  probelauf: boolean;
  kurz: Kurz;
  letzte: Sicherung | null;
  sicherungen: Sicherung[];
  verschluesselung: { eingerichtet: boolean; aktuell: number | null; verfahren: string; versionen: Version[] };
  ziel: Ziel;
  uebertragung: Uebertragung;
  speicher: { sicherungen: number | null; gesamt: number | null; frei: number | null; belegt: number | null };
  aufbewahrung_tage: number | null;
  aufbewahrung_auswahl?: number[];
  /** Ordner zum Herunter- und Hochladen auf dem Server vorhanden */
  austausch?: boolean;
  bereitgestellt?: Bereit[];
  uploads?: Upload[];
  upload?: { teil: number; max: number };
  naechste_sicherung: string | null;
  nachts_fehlgeschlagen: boolean;
  gpg: boolean | null;
  auftraege: Auftrag[];
  aktionen: Record<string, Aktion>;
  minuten: number[];
  angemeldet: string[];
  passwort: { min: number; max: number };
};

// ---------------------------------------------------------------- Hilfen
/** „Fri 2026-10-02 02:00:00 CEST“ (systemd) → „02.10.2026 02:00“ */
export function systemdZeit(text: string | null) {
  const m = text?.match(/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/);
  return m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}` : null;
}

/** Vorschlag für ein Sicherungs-Passwort: 20 Zeichen ohne verwechselbare (0/O, 1/l/I), in Fünfergruppen – gut
 *  abzuschreiben, etwa 115 Bit Zufall (crypto.getRandomValues, ohne Verzerrung durch Modulo). */
function passwortVorschlag() {
  const zeichen = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const grenze = 256 - (256 % zeichen.length);
  const aus: string[] = [];
  while (aus.length < 20) {
    const zufall = new Uint8Array(32);
    crypto.getRandomValues(zufall);
    for (const z of zufall) if (z < grenze && aus.length < 20) aus.push(zeichen[z % zeichen.length]);
  }
  return [0, 5, 10, 15].map((i) => aus.slice(i, i + 5).join("")).join("-");
}

function AuftragStatus({ a }: { a: Auftrag }) {
  const art = a.status === "erledigt" ? "ok" : a.status === "fehler" ? "fehler" : a.status === "abgebrochen" ? undefined : "warn";
  return <Chip art={art}>{a.status === "laeuft" || a.status === "wartet" ? <Icon name="sanduhr" groesse={12} /> : null}{a.status_name}</Chip>;
}

function Wert({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(120px,36%)_1fr] gap-3 py-1 text-sm border-b border-rand last:border-b-0">
      <dt className="gedaempft">{label}</dt>
      <dd className="m-0 min-w-0 break-words">{children}</dd>
    </div>
  );
}

/** Admin-Passwort und Code (Authenticator oder Notfall-Code) – für Aktionen mit Bestätigung „2fa“. Wer keine
 *  Zwei-Faktor-Anmeldung eingerichtet hat, kann nicht bestätigen und richtet sie zuerst ein (Festlegung 03.10.2026). */
function Bestaetigung({ kennwort, zf, onKennwort, fehler }: { kennwort: string; zf: ZweiterFaktorWert;
  onKennwort: (s: string) => void; fehler: Feldfehler }) {
  return (
    <>
      <ZweiFaktorFehlt />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-start">
        <Feld label="Ihr Passwort" fehler={fehler.kennwort} pflicht>
          {(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => onKennwort(e.target.value)} />}
        </Feld>
        {zf.feld(fehler.code)}
      </div>
    </>
  );
}

/** Ist die Bestätigung vollständig ausgefüllt? */
function useBestaetigt(kennwort: string, zf: ZweiterFaktorWert) {
  const ich = useIch();
  return ich.zweiter_faktor && !!kennwort && zf.bereit;
}

function useAuftrag(pfad: string, onFertig?: (a: Auftrag) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown> = {}) => api<Auftrag>(pfad, { method: "POST", body }),
    onSuccess: (a) => {
      void qc.invalidateQueries({ queryKey: ["backup"] });
      void qc.invalidateQueries({ queryKey: ["systemhinweis"] });
      onFertig?.(a);
    },
  });
}

// ---------------------------------------------------------------- Einfache Rückfrage (Jetzt sichern, Jetzt übertragen)
export function Rueckfrage({ offen, titel, text, knopf, pfad, onZu }: { offen: boolean; titel: string; text: ReactNode; knopf: string;
  pfad: string; onZu: () => void }) {
  const melden = useHinweis();
  const los = useAuftrag(pfad, (a) => { melden(`${a.name}: Auftrag an den Server übergeben.`); onZu(); });
  useEffect(() => { if (offen) los.reset(); }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) onZu(); }} titel={titel}
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf><Knopf variante="pri" laedt={los.isPending} onClick={() => los.mutate({})}>{knopf}</Knopf></>}>
      <div className="flex flex-col gap-3 text-sm">
        {text}
        <Fehleranzeige fehler={los.error} />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------- Sicherungs-Passwort festlegen
function PasswortDialog({ offen, daten, onZu }: { offen: boolean; daten: Daten; onZu: () => void }) {
  const [passwort, setPasswort] = useState("");
  const [passwort2, setPasswort2] = useState("");
  const [zeigen, setZeigen] = useState(false);
  const [kennwort, setKennwort] = useState("");
  const zf = useZweiterFaktor();
  const [kennung, setKennung] = useState<string | null>(null);
  const [blatt, setBlatt] = useState(false);
  useEffect(() => {
    if (!offen) { setPasswort(""); setPasswort2(""); setZeigen(false); setKennwort(""); zf.zuruecksetzen(); setKennung(null); setBlatt(false); }
  }, [offen]);
  const los = useAuftrag("backup/passwort/", (a) => setKennung(a.kennung));
  const auftrag = kennung ? daten.auftraege.find((a) => a.kennung === kennung) : undefined;
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const { min, max } = daten.passwort;
  const bestaetigt = useBestaetigt(kennwort, zf);
  const vorschlag = () => { const p = passwortVorschlag(); setPasswort(p); setPasswort2(p); setZeigen(true); };
  const fertig = auftrag?.status === "erledigt";
  return (
    <>
      <Dialog offen={offen && !blatt} onOffen={(o) => { if (!o) onZu(); }} breite={600}
        titel={daten.verschluesselung.eingerichtet ? "Neues Sicherungs-Passwort festlegen" : "Sicherungs-Passwort festlegen"}
        beschreibung="Damit werden ab der nächsten Sicherung Datenbank, Dokumente und Löschliste verschlüsselt (GnuPG, AES-256)."
        fuss={kennung ? (
          <>
            <Knopf onClick={onZu}>{auftrag && !auftrag.offen ? "Fertig" : "Ausblenden"}</Knopf>
            <Knopf variante="pri" icon="herunterladen" disabled={!fertig} onClick={() => setBlatt(true)}>Passwortblatt drucken</Knopf>
          </>
        ) : (
          <>
            <Knopf onClick={onZu}>Abbrechen</Knopf>
            <Knopf variante="dng" laedt={los.isPending} disabled={!passwort || !passwort2 || !bestaetigt}
              onClick={() => los.mutate({ passwort, passwort2, kennwort, ...zf.body })}>Bestätigen und festlegen</Knopf>
          </>
        )}>
        {kennung ? (
          <div className="flex flex-col gap-3" data-testid="passwort-ergebnis">
            {!auftrag || auftrag.offen ? (
              <Meldung art="info"><span className="flex items-center gap-2"><Icon name="sanduhr" groesse={14} />
                Der Server speichert das Passwort …</span></Meldung>
            ) : auftrag.status === "erledigt" ? (
              <Meldung art="ok">{auftrag.ergebnis}</Meldung>
            ) : <Meldung art="fehler">{auftrag.ergebnis || "Das Passwort wurde nicht gespeichert."}</Meldung>}
            {fertig ? (
              <p className="m-0 text-sm">Bitte jetzt das <strong>Passwortblatt drucken</strong> und im Tresor aufbewahren.
                Ohne dieses Passwort lassen sich die Sicherungen nicht mehr lesen; EPM zeigt es nach dem Schließen nicht mehr an.</p>
            ) : null}
          </div>
        ) : (
          <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); los.mutate({ passwort, passwort2, kennwort, ...zf.body }); }}>
            <Meldung art="info">Das Passwort liegt nur auf dem Server (nur für root lesbar), damit die nächtliche Sicherung ohne Eingabe
              läuft – und schützt die Kopien in der Nextcloud und auf der NAS. Ältere Sicherungen bleiben mit ihrem bisherigen Passwort lesbar.</Meldung>
            <div className="flex items-end gap-2">
              <Feld label="Neues Sicherungs-Passwort" className="grow" fehler={f.passwort} pflicht
                hinweis={`${min} bis ${max} Zeichen – am besten den Vorschlag nehmen`}>
                {(p) => <Eingabe {...p} type={zeigen ? "text" : "password"} autoComplete="new-password" spellCheck={false}
                  className="num" value={passwort} onChange={(e) => setPasswort(e.target.value)} />}
              </Feld>
              <Knopf onClick={vorschlag} className="mb-[22px]">Vorschlag erzeugen</Knopf>
            </div>
            <Feld label="Sicherungs-Passwort wiederholen" fehler={f.passwort2} pflicht>
              {(p) => <Eingabe {...p} type={zeigen ? "text" : "password"} autoComplete="new-password" spellCheck={false}
                className="num" value={passwort2} onChange={(e) => setPasswort2(e.target.value)} />}
            </Feld>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={zeigen} onChange={(e) => setZeigen(e.target.checked)} />Passwort anzeigen
            </label>
            <Bestaetigung kennwort={kennwort} zf={zf} onKennwort={setKennwort} fehler={f} />
            {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
            <button type="submit" hidden />
          </form>
        )}
      </Dialog>
      <PdfDialog offen={offen && blatt} onOffen={(o) => setBlatt(o)} titel="Passwortblatt" pfad="backup/passwortblatt/"
        body={{ passwort }} dateiname="EPM-Sicherungspasswort.pdf" />
    </>
  );
}

// ---------------------------------------------------------------- Passwort prüfen (z. B. das Blatt im Tresor)
function PruefenDialog({ offen, onZu }: { offen: boolean; onZu: () => void }) {
  const [passwort, setPasswort] = useState("");
  const [blatt, setBlatt] = useState(false);
  const pruefen = useMutation({
    mutationFn: () => api<{ stimmt: boolean; nr: number | null; aktuell: boolean }>("backup/passwort/pruefen/", { body: { passwort } }),
  });
  useEffect(() => { if (!offen) { setPasswort(""); setBlatt(false); pruefen.reset(); } }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const r = pruefen.data;
  return (
    <>
      <Dialog offen={offen && !blatt} onOffen={(o) => { if (!o) onZu(); }} titel="Sicherungs-Passwort prüfen"
        beschreibung="Passt ein Passwort (z. B. vom Blatt im Tresor) zu einem auf dem Server hinterlegten?"
        fuss={<>
          <Knopf onClick={onZu}>Fertig</Knopf>
          {r?.stimmt ? <Knopf icon="herunterladen" onClick={() => setBlatt(true)}>Passwortblatt drucken</Knopf> : null}
          <Knopf variante="pri" laedt={pruefen.isPending} disabled={!passwort} onClick={() => pruefen.mutate()}>Prüfen</Knopf>
        </>}>
        <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); pruefen.mutate(); }}>
          <Feld label="Sicherungs-Passwort">
            {(p) => <Eingabe {...p} type="password" autoComplete="off" className="num" value={passwort}
              onChange={(e) => { setPasswort(e.target.value); pruefen.reset(); }} />}
          </Feld>
          {r ? (r.stimmt
            ? <Meldung art="ok">Stimmt: Passwort Nr. {r.nr}{r.aktuell ? " (aktuell)" : " – nicht mehr das aktuelle, aber noch für ältere Sicherungen"}.</Meldung>
            : <Meldung art="fehler">Passt zu keinem hinterlegten Sicherungs-Passwort.</Meldung>) : null}
          <Fehleranzeige fehler={pruefen.error} />
          <button type="submit" hidden />
        </form>
      </Dialog>
      <PdfDialog offen={offen && blatt} onOffen={(o) => setBlatt(o)} titel="Passwortblatt" pfad="backup/passwortblatt/"
        body={{ passwort }} dateiname="EPM-Sicherungspasswort.pdf" />
    </>
  );
}

// ---------------------------------------------------------------- Übertragungsziel
function ZielDialog({ offen, ziel, onZu }: { offen: boolean; ziel: Ziel; onZu: () => void }) {
  const melden = useHinweis();
  const [w, setW] = useState({ url: "", benutzer: "", ziel_kennwort: "", ordner: "EPM-Sicherungen", von: "02:00", bis: "05:00",
    aufbewahrung_tage: "30" });
  const [kennwort, setKennwort] = useState("");
  const zf = useZweiterFaktor();
  useEffect(() => {
    if (offen) {
      setW({ url: ziel.url ?? "", benutzer: ziel.benutzer ?? "", ziel_kennwort: "", ordner: ziel.eingerichtet ? ziel.ordner ?? "" : "EPM-Sicherungen",
        von: ziel.von ?? "02:00", bis: ziel.bis ?? "05:00", aufbewahrung_tage: String(ziel.eingerichtet ? ziel.aufbewahrung_tage ?? 30 : 30) });
      setKennwort(""); zf.zuruecksetzen();
    }
  }, [offen, ziel]);
  const los = useAuftrag("backup/ziel/", (a) => { melden(`${a.name}: Auftrag an den Server übergeben.`); onZu(); });
  useEffect(() => { if (offen) los.reset(); }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const setze = (k: keyof typeof w) => (e: { target: { value: string } }) => setW({ ...w, [k]: e.target.value });
  const absenden = () => los.mutate({ ...w, aufbewahrung_tage: Number(w.aufbewahrung_tage), kennwort, ...zf.body });
  const bestaetigt = useBestaetigt(kennwort, zf);
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) onZu(); }} breite={640}
      titel={ziel.eingerichtet ? "Übertragungsziel ändern" : "Übertragungsziel festlegen"}
      beschreibung="WebDAV-Ordner, in den der Server die verschlüsselten Sicherungen kopiert (z. B. Nextcloud; von dort auf die NAS gespiegelt)."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={los.isPending} disabled={!w.url || !w.benutzer || !bestaetigt} onClick={absenden}>Bestätigen und speichern</Knopf></>}>
      <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); absenden(); }}>
        <Feld label="WebDAV-Adresse" fehler={f.url} pflicht hinweis="Nextcloud: https://cloud.beispiel.de/remote.php/dav/files/BENUTZER">
          {(p) => <Eingabe {...p} type="url" inputMode="url" spellCheck={false} value={w.url} onChange={setze("url")} placeholder="https://" />}
        </Feld>
        <div className="grid grid-cols-2 gap-3">
          <Feld label="Benutzer" fehler={f.benutzer} pflicht>
            {(p) => <Eingabe {...p} autoComplete="off" spellCheck={false} value={w.benutzer} onChange={setze("benutzer")} />}
          </Feld>
          <Feld label="Passwort für das Ziel" fehler={f.ziel_kennwort} pflicht={!ziel.eingerichtet}
            hinweis={ziel.eingerichtet ? "leer lassen = bisheriges bleibt" : "am besten ein App-Passwort der Nextcloud"}>
            {(p) => <Eingabe {...p} type="password" autoComplete="new-password" value={w.ziel_kennwort} onChange={setze("ziel_kennwort")} />}
          </Feld>
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)_130px_130px] gap-3">
          <Feld label="Ordner im Ziel" fehler={f.ordner} hinweis="wird angelegt, falls er fehlt">
            {(p) => <Eingabe {...p} spellCheck={false} value={w.ordner} onChange={setze("ordner")} />}
          </Feld>
          <Feld label="Zeitfenster von" fehler={f.von}>
            {(p) => <Eingabe {...p} type="time" value={w.von} onChange={setze("von")} />}
          </Feld>
          <Feld label="bis" fehler={f.bis}>
            {(p) => <Eingabe {...p} type="time" value={w.bis} onChange={setze("bis")} />}
          </Feld>
        </div>
        <Feld label="Aufbewahrung im Ziel" fehler={f.aufbewahrung_tage}
          hinweis="Nach jeder Übertragung entfernt der Server im Ordner ältere EPM-Sicherungen; die jüngste bleibt immer, andere Dateien werden nie angefasst.">
          {(p) => <Auswahl {...p} value={w.aufbewahrung_tage} onChange={setze("aufbewahrung_tage")}>
            {ZIEL_AUFBEWAHRUNG.map((t) => <option key={t} value={t}>{t === 0 ? "nie löschen" : `${t} Tage${t === 30 ? " (Standard)" : ""}`}</option>)}
          </Auswahl>}
        </Feld>
        <Meldung art="info">Übertragen werden nur verschlüsselte Sicherungen, und nur im Zeitfenster (von = bis: ganztägig). Der Server erreicht das Internet nur über den Proxy der OPNsense – die Adresse muss dort freigegeben sein.</Meldung>
        <Bestaetigung kennwort={kennwort} zf={zf} onKennwort={setKennwort} fehler={f} />
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

function ZielEntfernenDialog({ offen, onZu }: { offen: boolean; onZu: () => void }) {
  const melden = useHinweis();
  const [kennwort, setKennwort] = useState("");
  const zf = useZweiterFaktor();
  const los = useAuftrag("backup/ziel/entfernen/", (a) => { melden(`${a.name}: Auftrag an den Server übergeben.`); onZu(); });
  const bestaetigt = useBestaetigt(kennwort, zf);
  useEffect(() => { if (offen) { setKennwort(""); zf.zuruecksetzen(); los.reset(); } }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) onZu(); }} titel="Übertragungsziel entfernen" breite={560}
      beschreibung="Adresse und Zugangsdaten werden vom Server gelöscht. Sicherungen liegen danach nur noch auf dem Server."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={los.isPending} disabled={!bestaetigt} onClick={() => los.mutate({ kennwort, ...zf.body })}>Bestätigen und entfernen</Knopf></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); los.mutate({ kennwort, ...zf.body }); }}>
        <Meldung art="warn">Bereits übertragene Sicherungen bleiben im Ziel.</Meldung>
        <Bestaetigung kennwort={kennwort} zf={zf} onKennwort={setKennwort} fehler={f} />
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------- Wiederherstellen (F63)
function WiederherstellenDialog({ s, daten, onZu }: { s: Sicherung | null; daten: Daten; onZu: () => void }) {
  const melden = useHinweis();
  const [minuten, setMinuten] = useState("5");
  const [text, setText] = useState("");
  const [kennwort, setKennwort] = useState("");
  const zf = useZweiterFaktor();
  const los = useAuftrag(s ? `backup/${s.stempel}/wiederherstellen/` : "backup/", (a) => {
    melden(`${a.name}: Auftrag an den Server übergeben.`);
    onZu();
  });
  useEffect(() => { setMinuten(daten.angemeldet.length ? "5" : "0"); setText(""); setKennwort(""); zf.zuruecksetzen(); los.reset(); }, [s]); // eslint-disable-line react-hooks/exhaustive-deps
  const bestaetigt = useBestaetigt(kennwort, zf);
  if (!s) return null;
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const absenden = () => los.mutate({ minuten: Number(minuten), hinweis: text.trim() || undefined, kennwort, ...zf.body });
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel="Sicherung wiederherstellen" breite={620}
      beschreibung={<>Stand vom <strong>{zeitpunkt(s.zeitpunkt)}</strong> · {s.art_name}{s.ausgeloest_von ? ` · ${s.ausgeloest_von}` : ""} ·
        {" "}{dateigroesse(s.groesse)} · {s.verschluesselt ? `verschlüsselt (Passwort Nr. ${s.passwort_nr ?? "?"})` : "unverschlüsselt"}</>}
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={los.isPending} disabled={!bestaetigt} onClick={absenden}>Bestätigen und wiederherstellen</Knopf></>}>
      <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); absenden(); }}>
        <Meldung art="fehler"><strong>Datenbank und Dokumente werden durch diesen Stand ersetzt.</strong> Alles, was danach eingetragen
          wurde, ist danach nicht mehr in EPM – es steckt in der Sicherung, die der Server vorher automatisch anlegt. EPM ist dabei einige
          Minuten nicht erreichbar; alle Benutzer müssen sich danach neu anmelden. Die Löschliste bleibt: endgültig gelöschte Akten und
          Dokumente werden beim Start erneut gelöscht.</Meldung>
        {!daten.agent.erreichbar ? <Meldung art="warn">Der Systemagent auf dem Server meldet sich gerade nicht.</Meldung> : null}
        <Feld label="Beginn" hinweis={daten.angemeldet.length ? `Angemeldet: ${daten.angemeldet.join(", ")} – sie sehen den Hinweis oben auf jeder Seite.`
          : "Gerade ist niemand sonst angemeldet."}>
          {(p) => (
            <Auswahl {...p} value={minuten} onChange={(e) => setMinuten(e.target.value)}>
              {daten.minuten.map((m) => <option key={m} value={m}>{m === 0 ? "sofort" : `in ${m} Minuten`}</option>)}
            </Auswahl>
          )}
        </Feld>
        <Feld label="Hinweis an die Benutzer" hinweis="leer = Standardtext; Uhrzeit des Beginns wird angehängt" fehler={f.hinweis}>
          {(p) => <Textfeld {...p} rows={2} maxLength={400} value={text} onChange={(e) => setText(e.target.value)} />}
        </Feld>
        <Bestaetigung kennwort={kennwort} zf={zf} onKennwort={setKennwort} fehler={f} />
        {f.minuten ? <Meldung art="fehler">{f.minuten}</Meldung> : null}
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------- Herunterladen (5.1)
/** Die Sicherung als eine Datei: Der Server legt sie nach der Bestätigung für 2 Stunden bereit, dann lädt der Browser sie. */
function HerunterladenDialog({ s, daten, onZu }: { s: Sicherung | null; daten: Daten; onZu: () => void }) {
  const [kennwort, setKennwort] = useState("");
  const zf = useZweiterFaktor();
  const [kennung, setKennung] = useState<string | null>(null);
  const los = useAuftrag(s ? `backup/${s.stempel}/bereitstellen/` : "backup/", (a) => setKennung(a.kennung));
  useEffect(() => { setKennwort(""); zf.zuruecksetzen(); setKennung(null); los.reset(); }, [s?.stempel]); // eslint-disable-line react-hooks/exhaustive-deps
  const bestaetigt = useBestaetigt(kennwort, zf);
  if (!s) return null;
  const bereit = (daten.bereitgestellt ?? []).find((b) => b.stempel === s.stempel);
  const auftrag = kennung ? daten.auftraege.find((a) => a.kennung === kennung) : undefined;
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const laeuft = !!kennung && !bereit && (!auftrag || auftrag.offen || auftrag.status === "erledigt");
  const fehlgeschlagen = !!auftrag && !auftrag.offen && auftrag.status !== "erledigt";
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel="Sicherung herunterladen" breite={600}
      beschreibung={<>Stand vom <strong>{zeitpunkt(s.zeitpunkt)}</strong> · {s.art_name} · {dateigroesse(s.groesse)} ·
        {" "}{s.verschluesselt ? `verschlüsselt (Passwort Nr. ${s.passwort_nr ?? "?"})` : "unverschlüsselt"}</>}
      fuss={bereit ? (
        <><Knopf onClick={onZu}>Fertig</Knopf>
          <a className="btn pri" href={`/api/backup/${s.stempel}/datei/`} download data-testid="sicherung-datei"><Icon name="herunterladen" />Datei herunterladen</a></>
      ) : (
        <><Knopf onClick={onZu}>{kennung ? "Ausblenden" : "Abbrechen"}</Knopf>
          {!kennung || fehlgeschlagen ? <Knopf variante="pri" laedt={los.isPending} disabled={!bestaetigt || daten.austausch === false}
            onClick={() => { setKennung(null); los.mutate({ kennwort, ...zf.body }); }}>Bestätigen und bereitstellen</Knopf> : null}</>
      )}>
      <div className="flex flex-col gap-3.5" data-testid="herunterladen">
        {daten.austausch === false ? <Meldung art="fehler">Die Ordner für das Herunter- und Hochladen fehlen auf dem Server. Bitte dort einmal
          <code> sudo epm-update</code> ausführen.</Meldung> : null}
        {!s.verschluesselt ? (
          <Meldung art="fehler"><strong>Diese Sicherung ist nicht verschlüsselt.</strong> Die Datei enthält alle Patientendaten lesbar –
            nur auf einen verschlüsselten Datenträger laden und danach sicher löschen. Besser: erst ein Sicherungs-Passwort festlegen und neu sichern.</Meldung>
        ) : (
          <Meldung art="info">Die Datei bleibt verschlüsselt. Zum Lesen und Wiederherstellen braucht es das Sicherungs-Passwort
            Nr. {s.passwort_nr ?? "?"} (Passwortblatt im Tresor).</Meldung>
        )}
        {bereit ? (
          <Meldung art="ok"><span data-testid="sicherung-bereit">Die Datei liegt bereit{bereit.groesse ? ` (${dateigroesse(bereit.groesse)})` : ""}
            {bereit.bis ? ` – bis ${uhrzeit(bereit.bis)} Uhr` : ""}. Danach entfernt der Server sie wieder; jeder Abruf steht im Audit-Log.</span></Meldung>
        ) : laeuft ? (
          <Meldung art="info"><span className="flex items-center gap-2"><Icon name="sanduhr" groesse={14} />Der Server legt die Datei bereit …
            Bei großen Sicherungen dauert das einige Minuten.</span></Meldung>
        ) : (
          <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); if (bestaetigt) los.mutate({ kennwort, ...zf.body }); }}>
            {fehlgeschlagen ? <Meldung art="fehler">{auftrag?.ergebnis || "Die Datei konnte nicht bereitgestellt werden."}</Meldung> : null}
            <span className="text-sm">Der Server packt Datenbank, Dokumente und Löschliste dieser Sicherung in <strong>eine Datei</strong> und hält
              sie 2 Stunden zum Herunterladen bereit. Genau diese Datei lässt sich später wieder hochladen.</span>
            <Bestaetigung kennwort={kennwort} zf={zf} onKennwort={setKennwort} fehler={f} />
            {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
            <button type="submit" hidden />
          </form>
        )}
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------- Aufbewahrung (5.2)
function AufbewahrungDialog({ offen, daten, onZu }: { offen: boolean; daten: Daten; onZu: () => void }) {
  const melden = useHinweis();
  const auswahl = daten.aufbewahrung_auswahl ?? [7, 14, 30];
  const [tage, setTage] = useState(String(daten.aufbewahrung_tage ?? 14));
  const [kennwort, setKennwort] = useState("");
  const zf = useZweiterFaktor();
  const los = useAuftrag("backup/aufbewahrung/", (a) => { melden(`${a.name}: Auftrag an den Server übergeben.`); onZu(); });
  useEffect(() => { if (offen) { setTage(String(daten.aufbewahrung_tage ?? 14)); setKennwort(""); zf.zuruecksetzen(); los.reset(); } }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const bestaetigt = useBestaetigt(kennwort, zf);
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const absenden = () => los.mutate({ tage: Number(tage), kennwort, ...zf.body });
  const kuerzer = daten.aufbewahrung_tage != null && Number(tage) < daten.aufbewahrung_tage;
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) onZu(); }} titel="Aufbewahrung der Sicherungen" breite={560}
      beschreibung="Wie lange Sicherungen auf dem Server bleiben. Ältere entfernt die nächste Sicherung."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="pri" laedt={los.isPending} disabled={!bestaetigt || Number(tage) === daten.aufbewahrung_tage} onClick={absenden}>Bestätigen und speichern</Knopf></>}>
      <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); if (bestaetigt) absenden(); }}>
        <Feld label="Aufbewahren für" fehler={f.tage}>
          {(p) => (
            <Auswahl {...p} value={tage} onChange={(e) => setTage(e.target.value)}>
              {auswahl.map((t) => <option key={t} value={t}>{t} Tage{t === daten.aufbewahrung_tage ? " (aktuell)" : ""}</option>)}
            </Auswahl>
          )}
        </Feld>
        {kuerzer ? <Meldung art="warn">Mit der nächsten Sicherung entfernt der Server alle Sicherungen, die älter als {tage} Tage sind.
          Im Übertragungsziel gilt die dort eingestellte Aufbewahrung ({zielAufbewahrung(daten.ziel.aufbewahrung_tage)}).</Meldung>
          : <Meldung art="info">Mehr Tage brauchen mehr Speicher auf dem Server (aktuell {dateigroesse(daten.speicher.sicherungen ?? 0)} für
            {" "}{daten.sicherungen.length} Sicherungen, {daten.speicher.frei != null ? `${dateigroesse(daten.speicher.frei)} frei` : "freier Platz unbekannt"}).</Meldung>}
        <Bestaetigung kennwort={kennwort} zf={zf} onKennwort={setKennwort} fehler={f} />
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

// ---------------------------------------------------------------- Hochladen (5.3)
const warten = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Sicherung hochladen: die Datei, die „Herunterladen“ geliefert hat (auch von einem anderen EPM-Server, z. B. der
 * Migrationsmaschine). Übertragen wird in Stücken – eine unterbrochene Verbindung setzt an der Stelle fort, an der der
 * Server steht. Danach liest der Server die Datei ein (prüft Inhalt, Prüfsummen, Passwort); zurückgespielt wird erst mit
 * „Wiederherstellen“.
 */
function HochladenDialog({ offen, daten, onZu }: { offen: boolean; daten: Daten; onZu: () => void }) {
  const qc = useQueryClient();
  const eingabe = useRef<HTMLInputElement>(null);
  const abbruch = useRef(false);
  const [datei, setDatei] = useState<File | null>(null);
  const [passwort, setPasswort] = useState("");
  const [stand, setStand] = useState<{ phase: "wahl" | "laden" | "einlesen"; erhalten: number; upload?: string; kennung?: string }>({ phase: "wahl", erhalten: 0 });
  const [fehler, setFehler] = useState<string | null>(null);
  useEffect(() => {
    if (offen) { setDatei(null); setPasswort(""); setStand({ phase: "wahl", erhalten: 0 }); setFehler(null); abbruch.current = false; }
  }, [offen]);
  const teil = daten.upload?.teil ?? 4 * 1024 * 1024;
  const max = daten.upload?.max ?? 0;
  const auftrag = stand.kennung ? daten.auftraege.find((a) => a.kennung === stand.kennung) : undefined;
  const zuGross = !!datei && !!max && datei.size > max;
  const falsch = !!datei && !datei.name.toLowerCase().endsWith(".tar");

  const einlesen = async (upload: string) => {
    const a = await api<Auftrag>(`backup/hochladen/${upload}/einlesen/`, { body: passwort ? { passwort } : {} });
    setStand((s) => ({ ...s, phase: "einlesen", kennung: a.kennung }));
    void qc.invalidateQueries({ queryKey: ["backup"] });
  };
  const hochladen = async () => {
    if (!datei) return;
    setFehler(null);
    abbruch.current = false;
    let upload = stand.upload;
    let versatz = stand.erhalten;
    try {
      if (!upload) {
        const start = await api<{ upload: string; erhalten: number }>("backup/hochladen/", { body: { name: datei.name, groesse: datei.size } });
        upload = start.upload;
        versatz = start.erhalten;
      }
      setStand({ phase: "laden", erhalten: versatz, upload });
      let versuche = 0;
      while (versatz < datei.size) {
        if (abbruch.current) return;
        try {
          const r = await api<{ erhalten: number }>(`backup/hochladen/${upload}/?versatz=${versatz}`,
            { method: "PUT", roh: datei.slice(versatz, versatz + teil) });
          versatz = r.erhalten;
          versuche = 0;
        } catch (e) {
          // Der Server steht woanders (Stück kam an, Antwort ging verloren): dort fortsetzen
          const erhalten = e instanceof ApiFehler && e.status === 409 ? (e.daten as { erhalten?: number } | null)?.erhalten : undefined;
          if (typeof erhalten === "number") { versatz = erhalten; continue; }
          // Netz kurz weg: einige Male mit Pause wiederholen, dann aufgeben (Fortsetzen bleibt möglich)
          if ((e instanceof ApiFehler && e.status !== 0) || ++versuche > 5) throw e;
          await warten(1500 * versuche);
        }
        setStand({ phase: "laden", erhalten: versatz, upload });
      }
      await einlesen(upload);
    } catch (e) {
      setStand((s) => ({ ...s, erhalten: versatz, upload }));
      setFehler(e instanceof Error && e.message ? e.message : "Die Verbindung wurde unterbrochen.");
    }
  };
  const verwerfen = async () => {
    abbruch.current = true;
    if (stand.upload && stand.phase !== "einlesen") {
      try { await api(`backup/hochladen/${stand.upload}/`, { method: "DELETE" }); } catch { /* räumt der Server nach einem Tag selbst auf */ }
      void qc.invalidateQueries({ queryKey: ["backup"] });
    }
    onZu();
  };
  const verwerfenEingelesen = async () => {
    if (stand.upload) {
      try { await api(`backup/hochladen/${stand.upload}/`, { method: "DELETE" }); } catch { /* räumt der Server selbst auf */ }
      void qc.invalidateQueries({ queryKey: ["backup"] });
    }
    onZu();
  };
  const laeuft = stand.phase === "laden" && !fehler;
  const prozent = datei?.size ? Math.min(100, Math.round((100 * stand.erhalten) / datei.size)) : 0;
  const eingelesen = stand.phase === "einlesen" && auftrag && !auftrag.offen;
  // Rückgabe 3: Passwort fehlt oder passt nicht – die Datei bleibt auf dem Server, mit Passwort erneut einlesen
  const passwortFehlt = !!eingelesen && auftrag?.status !== "erledigt" && auftrag?.rueckgabe === 3;
  const nochmal = async () => {
    if (!stand.upload) return;
    setFehler(null);
    try { await einlesen(stand.upload); } catch (e) { setFehler(e instanceof Error ? e.message : String(e)); }
  };
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o && !laeuft) onZu(); }} titel="Sicherung hochladen" breite={620}
      beschreibung="Eine zuvor heruntergeladene Sicherung (epm-sicherung_….tar) auf diesen Server bringen – auch von einem anderen EPM-Server."
      fuss={stand.phase === "einlesen" ? (passwortFehlt ? (
        <><Knopf onClick={() => void verwerfenEingelesen()}>Datei verwerfen</Knopf>
          <Knopf variante="pri" disabled={!passwort} onClick={() => void nochmal()}>Mit Passwort einlesen</Knopf></>
      ) : (
        <Knopf variante={eingelesen ? "pri" : "sec"} onClick={onZu}>{eingelesen ? "Fertig" : "Ausblenden"}</Knopf>
      )) : (
        <><Knopf onClick={() => void verwerfen()}>{stand.upload ? "Abbrechen und verwerfen" : "Abbrechen"}</Knopf>
          <Knopf variante="pri" icon="hochladen" laedt={laeuft} disabled={!datei || zuGross || falsch || laeuft || daten.austausch === false}
            onClick={() => void hochladen()}>{stand.upload ? "Fortsetzen" : "Hochladen"}</Knopf></>
      )}>
      <div className="flex flex-col gap-3.5" data-testid="hochladen">
        {daten.austausch === false ? <Meldung art="fehler">Die Ordner für das Herunter- und Hochladen fehlen auf dem Server. Bitte dort einmal
          <code> sudo epm-update</code> ausführen.</Meldung> : null}
        {stand.phase === "wahl" || (stand.phase === "laden" && fehler) ? (
          <>
            <div className="feld">
              <span>Datei der Sicherung *</span>
              <div className="flex items-center gap-2.5 flex-wrap">
                <Knopf icon="hochladen" disabled={!!stand.upload} onClick={() => eingabe.current?.click()}>Datei auswählen</Knopf>
                <span className="text-sm">{datei ? <>{datei.name} <span className="gedaempft num">· {dateigroesse(datei.size)}</span></> : <span className="gedaempft">keine Datei gewählt</span>}</span>
                <input ref={eingabe} type="file" hidden aria-label="Datei der Sicherung" accept=".tar,application/x-tar"
                  onChange={(e) => { setDatei(e.target.files?.[0] ?? null); setFehler(null); }} />
              </div>
              {falsch ? <span className="fehlertext" role="alert">Bitte die Datei wählen, die „Herunterladen“ geliefert hat (epm-sicherung_….tar).</span>
                : zuGross ? <span className="fehlertext" role="alert">Die Datei ist größer als erlaubt ({dateigroesse(max)}).</span>
                : <span className="hinweis">Die Datei wird unverändert übertragen; eine verschlüsselte Sicherung bleibt verschlüsselt.</span>}
            </div>
            <Feld label="Passwort dieser Sicherung" hinweis="Nur nötig, wenn die Sicherung von einem anderen EPM-Server stammt oder mit einem Passwort verschlüsselt ist, das dieser Server nicht kennt. Der Server merkt es sich nur für diese Sicherung.">
              {(p) => <Eingabe {...p} type="password" autoComplete="off" spellCheck={false} className="num" value={passwort} onChange={(e) => setPasswort(e.target.value)} />}
            </Feld>
          </>
        ) : null}
        {stand.phase === "laden" ? (
          <div className="flex flex-col gap-1.5" data-testid="hochladen-fortschritt">
            <div className="flex justify-between text-sm"><span>{datei?.name}</span>
              <span className="num">{dateigroesse(stand.erhalten)} von {dateigroesse(datei?.size ?? 0)} · {prozent} %</span></div>
            <div className="h-2 rounded-full bg-fein overflow-hidden" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={prozent}
              aria-label="Fortschritt des Hochladens">
              <div className="h-full rounded-full bg-akzent transition-[width]" style={{ width: `${prozent}%` }} />
            </div>
            {laeuft ? <span className="text-xs gedaempft">Bitte dieses Fenster geöffnet lassen, bis die Datei übertragen ist.</span> : null}
          </div>
        ) : null}
        {stand.phase === "einlesen" ? (
          <div data-testid="hochladen-ergebnis">
            {!auftrag || auftrag.offen ? (
              <Meldung art="info"><span className="flex items-center gap-2"><Icon name="sanduhr" groesse={14} />Übertragen. Der Server prüft die
                Sicherung und nimmt sie in die Liste auf …</span></Meldung>
            ) : auftrag.status === "erledigt" ? (
              <Meldung art="ok">{auftrag.ergebnis || "Die Sicherung steht jetzt in der Liste."} Zurückgespielt wird sie erst mit „Wiederherstellen“.</Meldung>
            ) : <Meldung art="fehler">{auftrag.ergebnis || "Die Sicherung konnte nicht eingelesen werden."}</Meldung>}
            {passwortFehlt ? (
              <Feld label="Passwort dieser Sicherung" className="mt-3" hinweis="vom Passwortblatt des Servers, auf dem die Sicherung entstanden ist">
                {(p) => <Eingabe {...p} type="password" autoComplete="off" spellCheck={false} className="num" value={passwort} onChange={(e) => setPasswort(e.target.value)} />}
              </Feld>
            ) : null}
          </div>
        ) : null}
        {fehler ? <Meldung art="fehler"><span data-testid="hochladen-fehler">{fehler}{stand.upload ? " Mit „Fortsetzen“ geht es an derselben Stelle weiter." : ""}</span></Meldung> : null}
      </div>
    </Dialog>
  );
}

/** Hochgeladene Dateien, die noch nicht eingelesen sind (z. B. Fenster geschlossen, bevor der Server fertig war) */
function OffeneUploads({ daten, laufend }: { daten: Daten; laufend: Set<string> }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const fertig = () => void qc.invalidateQueries({ queryKey: ["backup"] });
  const [wahl, setWahl] = useState<Upload | null>(null);
  const [passwort, setPasswort] = useState("");
  const einlesen = useMutation({
    mutationFn: (u: Upload) => api<Auftrag>(`backup/hochladen/${u.upload}/einlesen/`, { body: passwort ? { passwort } : {} }),
    onSuccess: (a) => { fertig(); setWahl(null); setPasswort(""); melden(`${a.name}: Auftrag an den Server übergeben.`); },
  });
  const verwerfen = useMutation({
    mutationFn: (u: Upload) => api(`backup/hochladen/${u.upload}/`, { method: "DELETE" }),
    onSuccess: () => { fertig(); melden("Hochgeladene Datei verworfen."); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const liste = daten.uploads ?? [];
  if (!liste.length) return null;
  const liest = laufend.has("sicherung_einlesen");
  return (
    <Karte className="px-5 py-4 flex flex-col gap-2" data-testid="uploads">
      <KartenKopf titel="Hochgeladen, noch nicht eingelesen" unter="Der Server räumt liegen gebliebene Dateien nach einem Tag selbst auf." />
      {liste.map((u) => (
        <div key={u.upload} className="flex items-center justify-between gap-3 py-1.5 border-b border-rand last:border-b-0 text-sm flex-wrap">
          <span className="min-w-0 break-all">{u.name} <span className="gedaempft num">· {dateigroesse(u.erhalten)}{u.vollstaendig ? "" : ` von ${dateigroesse(u.groesse)}`}
            {u.von ? ` · ${u.von}` : ""}{u.begonnen_am ? ` · ${relativ(u.begonnen_am, true)}` : ""}</span>
            {u.vollstaendig ? null : <Chip art="warn" className="ml-2">unvollständig</Chip>}</span>
          <span className="flex gap-1.5">
            {u.vollstaendig ? <Knopf klein laedt={liest || (einlesen.isPending && einlesen.variables?.upload === u.upload)} disabled={liest}
              onClick={() => { einlesen.reset(); setPasswort(""); setWahl(u); }}>Einlesen</Knopf> : null}
            <Knopf klein variante="geist" disabled={liest} onClick={() => verwerfen.mutate(u)}>Verwerfen</Knopf>
          </span>
        </div>
      ))}
      <Dialog offen={!!wahl} onOffen={(o) => { if (!o) setWahl(null); }} titel="Hochgeladene Sicherung einlesen" breite={520}
        beschreibung={wahl ? `${wahl.name} · ${dateigroesse(wahl.erhalten)}` : undefined}
        fuss={<><Knopf onClick={() => setWahl(null)}>Abbrechen</Knopf>
          <Knopf variante="pri" laedt={einlesen.isPending} onClick={() => wahl && einlesen.mutate(wahl)}>Einlesen</Knopf></>}>
        <div className="flex flex-col gap-3">
          <Feld label="Passwort dieser Sicherung" hinweis="Nur nötig, wenn sie mit einem Passwort verschlüsselt ist, das dieser Server nicht kennt.">
            {(p) => <Eingabe {...p} type="password" autoComplete="off" spellCheck={false} className="num" value={passwort} onChange={(e) => setPasswort(e.target.value)} />}
          </Feld>
          <Fehleranzeige fehler={einlesen.error} />
        </div>
      </Dialog>
    </Karte>
  );
}

// ---------------------------------------------------------------- Teile der Seite
function Kennzahl({ titel, wert, children, testid }: { titel: string; wert: ReactNode; children?: ReactNode; testid?: string }) {
  return (
    <Karte className="px-[18px] py-4 flex flex-col gap-1.5 min-w-0" data-testid={testid}>
      <span className="lbl">{titel}</span>
      <span className="num text-xl font-medium">{wert}</span>
      {children}
    </Karte>
  );
}

function SicherungenTabelle({ daten, onWiederherstellen, onHerunterladen }: { daten: Daten; onWiederherstellen: (s: Sicherung) => void;
  onHerunterladen: (s: Sicherung) => void }) {
  const bereit = new Set((daten.bereitgestellt ?? []).map((b) => b.stempel));
  const ziel = daten.ziel.eingerichtet;
  const ue = daten.uebertragung;
  if (!daten.sicherungen.length) {
    return <Karte className="px-5 py-4"><Leer>{daten.status.vorhanden ? "Noch keine Sicherung auf dem Server." : "Der Server hat noch keinen Stand der Sicherungen gemeldet."}</Leer></Karte>;
  }
  return (
    <Karte className="overflow-x-auto" data-testid="sicherungen">
      <table className="tabelle">
        <thead><tr><th className="th">Zeitpunkt</th><th className="th">Art</th><th className="th text-right">Größe</th><th className="th">Schutz</th>
          <th className="th">{daten.ziel.hersteller === "nextcloud" ? "Nextcloud" : "Übertragung"}</th><th className="th" /></tr></thead>
        <tbody>
          {daten.sicherungen.map((s) => (
            <tr key={s.stempel} data-testid={`sicherung-${s.stempel}`}>
              <td className="td num">{zeitpunkt(s.zeitpunkt)}</td>
              <td className="td text-text2">{s.art_name}{s.ausgeloest_von ? ` · ${s.ausgeloest_von}` : ""}</td>
              <td className="td num text-right">{dateigroesse(s.groesse)}</td>
              <td className="td">{s.verschluesselt
                ? <Chip art="akzent" title={`Passwort Nr. ${s.passwort_nr ?? "?"}`}><Icon name="schloss" groesse={12} />verschlüsselt</Chip>
                : <Chip art="warn"><Icon name="warnung" groesse={12} />unverschlüsselt</Chip>}</td>
              <td className="td">{!ziel ? <span className="gedaempft">—</span>
                : s.uebertragen ? <Chip art="ok"><Icon name="haken" groesse={12} />übertragen {relativ(s.uebertragen_am, true).replace("heute, ", "")}</Chip>
                  : !s.verschluesselt || s.verfahren !== "gpg" ? <span className="text-xs gedaempft">wird nicht übertragen</span>
                    : ue.laeuft ? <Chip art="warn"><Icon name="sanduhr" groesse={12} />wird übertragen</Chip>
                      : <Chip art="warn"><Icon name="uhr" groesse={12} />wartet auf Zeitfenster</Chip>}</td>
              <td className="td text-right whitespace-nowrap">
                <Knopf klein icon="herunterladen" className="mr-1.5" onClick={() => onHerunterladen(s)}
                  aria-label={`Sicherung vom ${zeitpunkt(s.zeitpunkt)} herunterladen`}>{bereit.has(s.stempel) ? "Liegt bereit" : "Herunterladen"}</Knopf>
                <Knopf klein disabled={!s.wiederherstellbar} title={s.wiederherstellbar ? undefined : `nicht möglich: ${s.nicht_wiederherstellbar_weil}`}
                  onClick={() => onWiederherstellen(s)} aria-label={`Sicherung vom ${zeitpunkt(s.zeitpunkt)} wiederherstellen`}>Wiederherstellen</Knopf>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Karte>
  );
}

function Verschluesselung({ daten, onPasswort, onPruefen }: { daten: Daten; onPasswort: () => void; onPruefen: () => void }) {
  const v = daten.verschluesselung;
  const aktuell = v.versionen.find((x) => x.nr === v.aktuell);
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="verschluesselung">
      <KartenKopf titel="Verschlüsselung" unter={v.verfahren || "GnuPG (OpenPGP), AES-256, symmetrisch mit Passwort"}
        rechts={v.eingerichtet ? <Chip art="ok"><Icon name="schloss" groesse={12} />eingerichtet</Chip> : <Chip art="warn">nicht eingerichtet</Chip>} />
      {v.eingerichtet && aktuell ? (
        <p className="m-0 text-sm">Sicherungs-Passwort <strong>Nr. {aktuell.nr}</strong>, festgelegt {relativ(aktuell.gesetzt_am, true)}
          {aktuell.gesetzt_von ? ` von ${aktuell.gesetzt_von}` : ""}. Es liegt nur auf dem Server; der Ausdruck gehört in den Tresor.</p>
      ) : (
        <Meldung art="warn">Noch kein Sicherungs-Passwort – Sicherungen sind unverschlüsselt und werden nicht übertragen.</Meldung>
      )}
      {daten.gpg === false ? <Meldung art="fehler">GnuPG fehlt auf dem Server (<code>sudo apt install gnupg</code>) – ohne GnuPG wird nicht verschlüsselt.</Meldung> : null}
      {v.versionen.length ? (
        <table className="tabelle">
          <thead><tr><th className="th">Nr.</th><th className="th">festgelegt</th><th className="th">von</th><th className="th text-right">Sicherungen</th><th className="th" /></tr></thead>
          <tbody>{[...v.versionen].reverse().map((x) => (
            <tr key={x.nr}><td className="td num">{x.nr}</td><td className="td text-[0.8125rem]">{zeitpunkt(x.gesetzt_am)}</td>
              <td className="td text-[0.8125rem]">{x.gesetzt_von || "—"}</td><td className="td num text-right">{x.sicherungen}</td>
              <td className="td">{x.nr === v.aktuell ? <Chip art="akzent">aktuell</Chip> : x.entfernt_am ? <Chip>entfernt</Chip>
                : <Chip>für ältere Sicherungen</Chip>}</td></tr>))}</tbody>
        </table>
      ) : null}
      <div className="flex gap-2 flex-wrap">
        <Knopf variante={v.eingerichtet ? "sec" : "pri"} icon="schloss" onClick={onPasswort}>{v.eingerichtet ? "Neues Passwort festlegen" : "Passwort festlegen"}</Knopf>
        {v.eingerichtet ? <Knopf onClick={onPruefen}>Passwort prüfen</Knopf> : null}
      </div>
    </Karte>
  );
}

function UebertragungKarte({ daten, offen, onZiel, onEntfernen, onUebertragen }: { daten: Daten; offen: Set<string>;
  onZiel: () => void; onEntfernen: () => void; onUebertragen: () => void }) {
  const z = daten.ziel;
  const u = daten.uebertragung;
  const testen = useAuftrag("backup/ziel/testen/");
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="uebertragung">
      <KartenKopf titel="Übertragung" unter="Kopie der verschlüsselten Sicherungen in einen WebDAV-Ordner (rclone); ältere entfernt der Server dort nach der Aufbewahrung"
        rechts={z.eingerichtet ? (u.letzter_fehler ? <Chip art="fehler">Fehler</Chip> : u.laeuft ? <Chip art="warn">läuft</Chip> : <Chip art="ok">eingerichtet</Chip>)
          : <Chip art="warn">kein Ziel</Chip>} />
      {z.eingerichtet ? (
        <dl className="m-0">
          <Wert label="Adresse"><span className="num text-[0.8125rem] break-all">{z.url}</span></Wert>
          <Wert label="Benutzer · Ordner">{z.benutzer} · {z.ordner ? `/${z.ordner}` : "/"}</Wert>
          <Wert label="Zeitfenster">{z.von === z.bis ? "ganztägig" : `${z.von}–${z.bis} Uhr`}{u.im_zeitfenster ? <span className="gedaempft"> · gerade offen</span>
            : u.naechstes_fenster ? <span className="gedaempft"> · nächstes {relativ(u.naechstes_fenster, true)}</span> : null}</Wert>
          <Wert label="Aufbewahrung im Ziel"><span data-testid="ziel-aufbewahrung">{zielAufbewahrung(z.aufbewahrung_tage)}</span>
            {u.im_ziel_entfernt ? <span className="gedaempft"> · zuletzt {u.im_ziel_entfernt.anzahl} ältere entfernt, {relativ(u.im_ziel_entfernt.am, true)}</span> : null}</Wert>
          <Wert label="Zuletzt übertragen">{u.letzter_erfolg ? relativ(u.letzter_erfolg, true) : "noch nie"}
            {u.offen ? <span className="gedaempft"> · {u.offen} Sicherung{u.offen === 1 ? "" : "en"} ausstehend</span> : null}</Wert>
          {u.letzter_fehler ? <Wert label="Letzter Fehler"><span className="text-fehler">{u.letzter_fehler}</span>
            {u.letzter_versuch ? <span className="gedaempft"> ({relativ(u.letzter_versuch, true)})</span> : null}</Wert> : null}
          {z.gesetzt_von ? <Wert label="Festgelegt">{relativ(z.gesetzt_am, true)} von {z.gesetzt_von}</Wert> : null}
        </dl>
      ) : (
        <Meldung art="warn">Noch kein Übertragungsziel – Sicherungen liegen nur auf dem Server.</Meldung>
      )}
      {u.rclone === false ? <Meldung art="fehler">rclone fehlt auf dem Server (<code>sudo apt install rclone</code>).</Meldung> : null}
      <Fehleranzeige fehler={testen.error} />
      <div className="flex gap-2 flex-wrap">
        <Knopf variante={z.eingerichtet ? "sec" : "pri"} icon="stift" onClick={onZiel}>{z.eingerichtet ? "Ziel ändern" : "Ziel festlegen"}</Knopf>
        {z.eingerichtet ? (
          <>
            <Knopf laedt={testen.isPending || offen.has("sicherung_ziel_testen")} disabled={offen.has("sicherung_ziel_testen")}
              onClick={() => testen.mutate({})}>Verbindung testen</Knopf>
            <Knopf icon="hochladen" disabled={!daten.verschluesselung.eingerichtet || offen.has("sicherung_uebertragen")}
              laedt={offen.has("sicherung_uebertragen")} onClick={onUebertragen}>Jetzt übertragen</Knopf>
            <Knopf variante="geist" onClick={onEntfernen}>Ziel entfernen</Knopf>
          </>
        ) : null}
      </div>
    </Karte>
  );
}

function Taetigkeiten({ liste }: { liste: Auftrag[] }) {
  const qc = useQueryClient();
  const melden = useHinweis();
  const [auf, setAuf] = useState<number | null>(null);
  const zurueck = useMutation({
    mutationFn: (a: Auftrag) => api<Auftrag>(`backup/auftraege/${a.kennung}/abbrechen/`, { method: "POST" }),
    onSuccess: (a) => { void qc.invalidateQueries({ queryKey: ["backup"] }); void qc.invalidateQueries({ queryKey: ["systemhinweis"] }); melden(`${a.name} zurückgezogen.`); },
    onError: (e) => melden(e.message, "fehler"),
  });
  return (
    <Karte className="px-5 py-4 flex flex-col gap-2" data-testid="auftraege">
      <KartenKopf titel="Tätigkeiten" unter="Die letzten 20 – vollständig im Audit-Log (Gruppe „Backup“)." />
      {liste.length === 0 ? <Leer>Noch keine Tätigkeiten.</Leer> : (
        <table className="tabelle">
          <thead><tr><th className="th">Zeit</th><th className="th">Tätigkeit</th><th className="th">von</th><th className="th">Status</th><th className="th">Ergebnis</th><th className="th" /></tr></thead>
          <tbody>
            {liste.map((a) => (
              <Fragment key={a.id}>
                <tr data-testid="auftrag">
                  <td className="td text-[0.8125rem] whitespace-nowrap">{relativ(a.angefordert_am, true)}</td>
                  <td className="td"><span className="font-medium">{a.name}</span>
                    {a.parameter.stempel ? <span className="text-xs gedaempft"> · {a.parameter.stempel}</span> : null}
                    {a.parameter.minuten ? <span className="text-xs gedaempft"> · Beginn nach {a.parameter.minuten} Min.</span> : null}</td>
                  <td className="td text-[0.8125rem]">{a.angefordert_von_name ?? "—"}</td>
                  <td className="td"><AuftragStatus a={a} /><AuftragFortschritt a={a} liste={liste} className="mt-1.5" /></td>
                  <td className="td text-[0.8125rem] max-w-[420px]">{a.ergebnis || (a.status === "wartet" ? "wartet, bis der Server den Auftrag abholt" : "—")}</td>
                  <td className="td text-right whitespace-nowrap">
                    {a.status === "wartet" ? <Knopf klein laedt={zurueck.isPending} onClick={() => zurueck.mutate(a)}>Zurückziehen</Knopf> : null}
                    {a.ausgabe ? <Knopf klein variante="geist" onClick={() => setAuf(auf === a.id ? null : a.id)} aria-expanded={auf === a.id}>
                      {auf === a.id ? "Ausgabe zu" : "Ausgabe"}</Knopf> : null}
                  </td>
                </tr>
                {auf === a.id ? (
                  <tr><td colSpan={6} className="td">
                    <pre className="m-0 max-h-[360px] overflow-auto text-[0.75rem] leading-snug bg-grund rounded-lg p-3 whitespace-pre-wrap" data-testid="auftrag-ausgabe">{a.ausgabe}</pre>
                  </td></tr>
                ) : null}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </Karte>
  );
}

// ---------------------------------------------------------------- Seite
type Offen = null | "jetzt" | "passwort" | "pruefen" | "ziel" | "ziel_entfernen" | "uebertragen" | "aufbewahrung" | "hochladen";

export function Backup() {
  const qc = useQueryClient();
  const daten = useQuery({
    queryKey: ["backup"],
    queryFn: () => api<Daten>("backup/"),
    refetchInterval: (q) => ((q.state.data?.auftraege ?? []).some((a) => a.offen) ? 3000 : 30_000),
    retry: false,
  });
  // Solange ein Auftrag läuft (Sicherung, Übertragung, Wiederherstellung), bleibt der Ladebalken oben in Bewegung (F124)
  useHintergrundarbeit("backup-auftraege", (daten.data?.auftraege ?? []).some((a) => a.offen));
  const [offen, setOffen] = useState<Offen>(null);
  const [wahl, setWahl] = useState<Sicherung | null>(null);
  const [laden, setLaden] = useState<string | null>(null);
  const d = daten.data;
  const laufend = useMemo(() => new Set((d?.auftraege ?? []).filter((a) => a.offen).map((a) => a.aktion)), [d]);
  // Ist ein Auftrag fertig geworden, auch den Hinweis an alle Benutzer neu laden (Wiederherstellen setzt ihn)
  const vorher = useRef("");
  const jetzt = [...laufend].sort().join(",");
  useEffect(() => {
    if (vorher.current !== jetzt) void qc.invalidateQueries({ queryKey: ["systemhinweis"] });
    vorher.current = jetzt;
  }, [jetzt, qc]);

  if (!d) {
    return (
      <Seite pfad={[{ text: "Administration" }, { text: "Backup" }]}>
        <Seitenkopf titel="Backup und Wiederherstellung" />
        {daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />}
      </Seite>
    );
  }
  const sp = d.speicher;
  const belegtProzent = sp.belegt != null && sp.gesamt ? Math.round((100 * sp.belegt) / sp.gesamt) : null;
  const letzte = d.letzte;
  const z = d.ziel;
  const u = d.uebertragung;
  const naechste = systemdZeit(d.naechste_sicherung);
  const wiederherstellen = d.auftraege.find((a) => a.aktion === "wiederherstellen" && a.offen);

  return (
    <Seite pfad={[{ text: "Administration" }, { text: "Backup" }]}>
      <Seitenkopf titel="Backup und Wiederherstellung"
        unter={`Datenbank, Dokumente und Löschliste täglich um 02:00${d.aufbewahrung_tage ? `, ${d.aufbewahrung_tage} Tage auf dem Server` : ""}${
          d.verschluesselung.eingerichtet ? ", verschlüsselt" : ""}${z.eingerichtet ? ", Kopie im Übertragungsziel" : ""}.`}
        rechts={<>
          <Knopf icon="hochladen" disabled={!d.agent.verzeichnis} onClick={() => setOffen("hochladen")}>Sicherung hochladen</Knopf>
          <Knopf variante="pri" icon="backup" laedt={laufend.has("sicherung")} disabled={laufend.has("sicherung") || !d.agent.verzeichnis}
            onClick={() => setOffen("jetzt")}>Jetzt sichern</Knopf></>} />
      {/* laufende Tätigkeiten mit geschätztem Fortschritt (Wunsch 08.10.2026) */}
      <LaufendeAuftraege liste={d.auftraege} />

      {wiederherstellen ? (
        <Meldung art="warn"><span data-testid="wiederherstellen-laeuft"><strong>Wiederherstellen läuft</strong> ({wiederherstellen.parameter.stempel}):
          EPM ist gleich einige Minuten nicht erreichbar. Danach müssen sich alle neu anmelden.</span></Meldung>
      ) : null}
      {daten.error && wiederherstellen ? <Meldung art="info">EPM startet gerade mit der wiederhergestellten Sicherung …</Meldung> : <Fehleranzeige fehler={daten.error} />}
      {!d.agent.verzeichnis ? (
        <Meldung art="fehler">Das Auftragsverzeichnis fehlt. Sicherungen lassen sich erst steuern, wenn auf dem Server einmal
          <code> sudo epm-update</code> (bzw. <code>rollout/04-projekt.sh</code>) gelaufen ist.</Meldung>
      ) : !d.status.vorhanden || !d.status.aktuell ? (
        <Meldung art="warn"><span data-testid="agent-fehlt">Der Systemagent auf dem Server meldet keinen aktuellen Stand der Sicherungen
          {d.status.zeit ? ` (zuletzt ${relativ(d.status.zeit, true)})` : ""}. Aufträge warten, bis er wieder läuft
          (<code>systemctl status epm-systemstatus.timer epm-systemagent.path</code>).</span></Meldung>
      ) : null}
      {d.kurz.zustand !== "ok" && d.status.vorhanden ? (
        <Meldung art={d.kurz.zustand === "fehler" ? "fehler" : "warn"}>
          <span data-testid="backup-hinweise">{d.kurz.hinweise.map((h, i) => <Fragment key={h}>{i ? <br /> : null}{h}</Fragment>)}</span>
        </Meldung>
      ) : null}

      <div className="stapel grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="kennzahlen">
        <Kennzahl titel="Letzte Sicherung" testid="letzte-sicherung" wert={letzte ? relativ(letzte.zeitpunkt, true) : "—"}>
          {letzte ? (
            <span className="flex gap-1.5 flex-wrap items-center">
              <Chip art={d.kurz.zustand === "fehler" ? "fehler" : "ok"}>{d.kurz.zustand === "fehler" ? <Icon name="warnung" groesse={12} /> : <Icon name="haken" groesse={12} />}
                {d.nachts_fehlgeschlagen ? "nächtliche fehlgeschlagen" : d.kurz.zustand === "fehler" ? "zu alt" : "erfolgreich"}</Chip>
              <span className="text-[0.8125rem] gedaempft">{letzte.art_name} · {dateigroesse(letzte.groesse)}</span>
            </span>
          ) : <span className="text-[0.8125rem] gedaempft">noch keine Sicherung</span>}
          {naechste ? <span className="text-[0.8125rem] gedaempft">nächste: {naechste}</span> : null}
        </Kennzahl>
        <Kennzahl titel={z.hersteller === "nextcloud" ? "Übertragung Nextcloud" : "Übertragung"} testid="letzte-uebertragung"
          wert={z.eingerichtet ? (u.letzter_erfolg ? relativ(u.letzter_erfolg, true) : "noch nie") : "—"}>
          <span className="text-[0.8125rem] gedaempft">{!z.eingerichtet ? "kein Ziel festgelegt"
            : u.laeuft ? "läuft gerade" : z.von === z.bis ? "Zeitfenster ganztägig" : `Zeitfenster ${z.von}–${z.bis}${u.im_zeitfenster ? " (offen)" : ""}`}</span>
          {u.letzter_fehler ? <span className="text-[0.8125rem] text-fehler">{u.letzter_fehler}</span> : null}
        </Kennzahl>
        <Kennzahl titel="Speicher" testid="speicher" wert={sp.belegt != null && sp.gesamt ? `${dateigroesse(sp.belegt)} von ${dateigroesse(sp.gesamt)}` : "—"}>
          {belegtProzent != null ? (
            <div className="h-1.5 rounded-full bg-fein overflow-hidden" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={belegtProzent}
              aria-label={`Speicher belegt: ${belegtProzent} %`}>
              <div className={cx("h-full rounded-full", belegtProzent < 80 ? "bg-akzent" : belegtProzent < 90 ? "bg-warn" : "bg-fehler")}
                style={{ width: `${Math.max(2, belegtProzent)}%` }} />
            </div>
          ) : null}
          <span className="text-[0.8125rem] gedaempft">Sicherungen: {dateigroesse(sp.sicherungen ?? 0)} · {d.sicherungen.length} vorhanden</span>
          <span className="text-[0.8125rem] flex items-center gap-2 flex-wrap" data-testid="aufbewahrung">
            <span>Aufbewahrung: <strong className="num">{d.aufbewahrung_tage ?? "—"} Tage</strong></span>
            <Knopf klein disabled={!d.agent.verzeichnis || laufend.has("sicherung_aufbewahrung")} laedt={laufend.has("sicherung_aufbewahrung")}
              onClick={() => setOffen("aufbewahrung")}>Ändern</Knopf>
          </span>
        </Kennzahl>
      </div>

      <SicherungenTabelle daten={d} onWiederherstellen={setWahl} onHerunterladen={(s) => setLaden(s.stempel)} />
      <OffeneUploads daten={d} laufend={laufend} />

      <div className="flex gap-2.5 px-4 py-3 rounded-lg bg-fehler-bg text-fehler text-sm leading-normal items-start" data-testid="warnung-wiederherstellen">
        <Icon name="warnung" groesse={18} />
        <span><strong>Wiederherstellen ersetzt den aktuellen Datenbestand.</strong> Vorher wird automatisch eine Sicherung des jetzigen Stands
          angelegt. Zum Bestätigen müssen das eigene Passwort und der 2FA-Code eingegeben werden.</span>
      </div>

      <div className="stapel grid grid-cols-1 hd:grid-cols-2 gap-5 items-start">
        <Verschluesselung daten={d} onPasswort={() => setOffen("passwort")} onPruefen={() => setOffen("pruefen")} />
        <UebertragungKarte daten={d} offen={laufend} onZiel={() => setOffen("ziel")} onEntfernen={() => setOffen("ziel_entfernen")}
          onUebertragen={() => setOffen("uebertragen")} />
      </div>

      <Taetigkeiten liste={d.auftraege} />
      {d.probelauf ? <span className="text-xs gedaempft">Testumgebung: Der Systemagent läuft im Probelauf; Sicherung, Übertragung und Wiederherstellen sind echt.</span> : null}
      <span className="text-xs gedaempft">Stand vom Server {d.status.zeit ? `um ${uhrzeit(d.status.zeit)} Uhr` : "—"} · wird alle 30 Sekunden neu geladen.</span>

      <Rueckfrage offen={offen === "jetzt"} titel="Sicherung jetzt erstellen" knopf="Jetzt sichern" pfad="backup/jetzt/" onZu={() => setOffen(null)}
        text={<p className="m-0">Datenbank, Dokumente und Löschliste werden jetzt gesichert – wie die nächtliche Sicherung
          {d.verschluesselung.eingerichtet ? ", verschlüsselt mit dem Sicherungs-Passwort" : ", aber unverschlüsselt (kein Sicherungs-Passwort festgelegt)"}.
          EPM bleibt dabei erreichbar.</p>} />
      <Rueckfrage offen={offen === "uebertragen"} titel="Sicherungen jetzt übertragen" knopf="Jetzt übertragen" pfad="backup/uebertragen/"
        onZu={() => setOffen(null)}
        text={<p className="m-0">Alle noch nicht übertragenen verschlüsselten Sicherungen ({u.offen ?? 0}) werden jetzt zum Ziel kopiert – auch außerhalb
          des Zeitfensters. Das kann je nach Größe dauern und belastet die Leitung.</p>} />
      <PasswortDialog offen={offen === "passwort"} daten={d} onZu={() => setOffen(null)} />
      <PruefenDialog offen={offen === "pruefen"} onZu={() => setOffen(null)} />
      <ZielDialog offen={offen === "ziel"} ziel={z} onZu={() => setOffen(null)} />
      <ZielEntfernenDialog offen={offen === "ziel_entfernen"} onZu={() => setOffen(null)} />
      <WiederherstellenDialog s={wahl} daten={d} onZu={() => setWahl(null)} />
      <HerunterladenDialog s={d.sicherungen.find((x) => x.stempel === laden) ?? null} daten={d} onZu={() => setLaden(null)} />
      <AufbewahrungDialog offen={offen === "aufbewahrung"} daten={d} onZu={() => setOffen(null)} />
      <HochladenDialog offen={offen === "hochladen"} daten={d} onZu={() => setOffen(null)} />
    </Seite>
  );
}
