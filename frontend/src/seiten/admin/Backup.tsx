/**
 * Entwurf 11 · Administration › Backup (F61–F64, Recht „Sicherungen verwalten“, Standard: nur Admin).
 *
 * Sicherungen (täglich 02:00, „Jetzt sichern“), Verschlüsselung mit einem Passwort, das hier festgelegt wird
 * (Festlegung 02.10.2026: symmetrisch, GnuPG/AES-256; das Passwort liegt nur auf dem Server und gehört ausgedruckt in
 * den Tresor), Übertragung in einen WebDAV-Ordner (Nextcloud) im Zeitfenster, Wiederherstellen mit Admin-Passwort und
 * 2FA. Alles läuft als Auftrag über den Systemagenten auf dem Server; Passwörter stehen nie in der Datenbank.
 */
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import type { Feldfehler } from "@/lib/api";
import { dateigroesse, relativ, uhrzeit, zeitpunkt } from "@/lib/format";
import { Seite } from "@/components/layout/Shell";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Feld, Karte, KartenKopf, Knopf, Laden, Leer, Meldung, Seitenkopf,
  Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { PdfDialog } from "@/components/PdfDialog";

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
  hersteller?: string; gesetzt_am?: string | null; gesetzt_von?: string };
type Uebertragung = { letzter_versuch?: string | null; letzter_erfolg?: string | null; letzter_fehler?: string; laeuft?: boolean;
  offen?: number; im_zeitfenster?: boolean; naechstes_fenster?: string | null; rclone?: boolean };
type Aktion = { name: string; bestaetigung: "keine" | "einfach" | "2fa"; beschreibung: string; sichern?: boolean;
  warnen?: boolean; hinweis?: string };
type Auftrag = { id: number; kennung: string; ziel: "server" | "epm"; aktion: string; name: string;
  status: "wartet" | "laeuft" | "erledigt" | "fehler" | "abgebrochen"; status_name: string; offen: boolean;
  parameter: { minuten?: number; stempel?: string; url?: string }; angefordert_von_name: string | null; angefordert_am: string;
  begonnen_am: string | null; beendet_am: string | null; ergebnis: string; ausgabe: string; rueckgabe: number | null;
  probelauf: boolean };
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

/** Admin-Passwort und Code (Authenticator oder Notfall-Code) – für Aktionen mit Bestätigung „2fa“ */
function Bestaetigung({ kennwort, code, onKennwort, onCode, fehler }: { kennwort: string; code: string;
  onKennwort: (s: string) => void; onCode: (s: string) => void; fehler: Feldfehler }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <Feld label="Ihr Passwort" fehler={fehler.kennwort} pflicht>
        {(p) => <Eingabe {...p} type="password" autoComplete="current-password" value={kennwort} onChange={(e) => onKennwort(e.target.value)} />}
      </Feld>
      <Feld label="Code aus der Authenticator-App" hinweis="oder ein Notfall-Code" fehler={fehler.code} pflicht>
        {(p) => <Eingabe {...p} inputMode="text" autoComplete="one-time-code" value={code} onChange={(e) => onCode(e.target.value)} />}
      </Feld>
    </div>
  );
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
  const [code, setCode] = useState("");
  const [kennung, setKennung] = useState<string | null>(null);
  const [blatt, setBlatt] = useState(false);
  useEffect(() => {
    if (!offen) { setPasswort(""); setPasswort2(""); setZeigen(false); setKennwort(""); setCode(""); setKennung(null); setBlatt(false); }
  }, [offen]);
  const los = useAuftrag("backup/passwort/", (a) => setKennung(a.kennung));
  const auftrag = kennung ? daten.auftraege.find((a) => a.kennung === kennung) : undefined;
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const { min, max } = daten.passwort;
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
            <Knopf variante="dng" laedt={los.isPending} disabled={!passwort || !passwort2 || !kennwort || !code}
              onClick={() => los.mutate({ passwort, passwort2, kennwort, code })}>Bestätigen und festlegen</Knopf>
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
          <form className="flex flex-col gap-3.5" onSubmit={(e) => { e.preventDefault(); los.mutate({ passwort, passwort2, kennwort, code }); }}>
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
            <Bestaetigung kennwort={kennwort} code={code} onKennwort={setKennwort} onCode={setCode} fehler={f} />
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
  const [w, setW] = useState({ url: "", benutzer: "", ziel_kennwort: "", ordner: "EPM-Sicherungen", von: "02:00", bis: "05:00" });
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  useEffect(() => {
    if (offen) {
      setW({ url: ziel.url ?? "", benutzer: ziel.benutzer ?? "", ziel_kennwort: "", ordner: ziel.eingerichtet ? ziel.ordner ?? "" : "EPM-Sicherungen",
        von: ziel.von ?? "02:00", bis: ziel.bis ?? "05:00" });
      setKennwort(""); setCode("");
    }
  }, [offen, ziel]);
  const los = useAuftrag("backup/ziel/", (a) => { melden(`${a.name}: Auftrag an den Server übergeben.`); onZu(); });
  useEffect(() => { if (offen) los.reset(); }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const setze = (k: keyof typeof w) => (e: { target: { value: string } }) => setW({ ...w, [k]: e.target.value });
  const absenden = () => los.mutate({ ...w, kennwort, code });
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) onZu(); }} breite={640}
      titel={ziel.eingerichtet ? "Übertragungsziel ändern" : "Übertragungsziel festlegen"}
      beschreibung="WebDAV-Ordner, in den der Server die verschlüsselten Sicherungen kopiert (z. B. Nextcloud; von dort auf die NAS gespiegelt)."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={los.isPending} disabled={!w.url || !w.benutzer || !kennwort || !code} onClick={absenden}>Bestätigen und speichern</Knopf></>}>
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
        <Meldung art="info">Übertragen werden nur verschlüsselte Sicherungen, und nur im Zeitfenster (von = bis: ganztägig). Im Ziel wird nie
          etwas gelöscht. Der Server erreicht das Internet nur über den Proxy der OPNsense – die Adresse muss dort freigegeben sein.</Meldung>
        <Bestaetigung kennwort={kennwort} code={code} onKennwort={setKennwort} onCode={setCode} fehler={f} />
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}

function ZielEntfernenDialog({ offen, onZu }: { offen: boolean; onZu: () => void }) {
  const melden = useHinweis();
  const [kennwort, setKennwort] = useState("");
  const [code, setCode] = useState("");
  const los = useAuftrag("backup/ziel/entfernen/", (a) => { melden(`${a.name}: Auftrag an den Server übergeben.`); onZu(); });
  useEffect(() => { if (offen) { setKennwort(""); setCode(""); los.reset(); } }, [offen]); // eslint-disable-line react-hooks/exhaustive-deps
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  return (
    <Dialog offen={offen} onOffen={(o) => { if (!o) onZu(); }} titel="Übertragungsziel entfernen" breite={560}
      beschreibung="Adresse und Zugangsdaten werden vom Server gelöscht. Sicherungen liegen danach nur noch auf dem Server."
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={los.isPending} disabled={!kennwort || !code} onClick={() => los.mutate({ kennwort, code })}>Bestätigen und entfernen</Knopf></>}>
      <form className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); los.mutate({ kennwort, code }); }}>
        <Meldung art="warn">Bereits übertragene Sicherungen bleiben im Ziel.</Meldung>
        <Bestaetigung kennwort={kennwort} code={code} onKennwort={setKennwort} onCode={setCode} fehler={f} />
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
  const [code, setCode] = useState("");
  const los = useAuftrag(s ? `backup/${s.stempel}/wiederherstellen/` : "backup/", (a) => {
    melden(`${a.name}: Auftrag an den Server übergeben.`);
    onZu();
  });
  useEffect(() => { setMinuten(daten.angemeldet.length ? "5" : "0"); setText(""); setKennwort(""); setCode(""); los.reset(); }, [s]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!s) return null;
  const f: Feldfehler = los.error instanceof ApiFehler ? los.error.felder : {};
  const absenden = () => los.mutate({ minuten: Number(minuten), hinweis: text.trim() || undefined, kennwort, code });
  return (
    <Dialog offen onOffen={(o) => { if (!o) onZu(); }} titel="Sicherung wiederherstellen" breite={620}
      beschreibung={<>Stand vom <strong>{zeitpunkt(s.zeitpunkt)}</strong> · {s.art_name}{s.ausgeloest_von ? ` · ${s.ausgeloest_von}` : ""} ·
        {" "}{dateigroesse(s.groesse)} · {s.verschluesselt ? `verschlüsselt (Passwort Nr. ${s.passwort_nr ?? "?"})` : "unverschlüsselt"}</>}
      fuss={<><Knopf onClick={onZu}>Abbrechen</Knopf>
        <Knopf variante="dng" laedt={los.isPending} disabled={!kennwort || !code} onClick={absenden}>Bestätigen und wiederherstellen</Knopf></>}>
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
        <Bestaetigung kennwort={kennwort} code={code} onKennwort={setKennwort} onCode={setCode} fehler={f} />
        {f.minuten ? <Meldung art="fehler">{f.minuten}</Meldung> : null}
        {los.error && !Object.keys(f).length ? <Meldung art="fehler">{los.error.message}</Meldung> : null}
        <button type="submit" hidden />
      </form>
    </Dialog>
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

function SicherungenTabelle({ daten, onWiederherstellen }: { daten: Daten; onWiederherstellen: (s: Sicherung) => void }) {
  const ziel = daten.ziel.eingerichtet;
  const ue = daten.uebertragung;
  if (!daten.sicherungen.length) {
    return <Karte className="px-5 py-4"><Leer>{daten.status.vorhanden ? "Noch keine Sicherung auf dem Server." : "Der Server hat noch keinen Stand der Sicherungen gemeldet."}</Leer></Karte>;
  }
  return (
    <Karte className="overflow-hidden" data-testid="sicherungen">
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
              <td className="td text-right">
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
      <KartenKopf titel="Übertragung" unter="Kopie der verschlüsselten Sicherungen in einen WebDAV-Ordner (rclone, nur kopieren, nie löschen)"
        rechts={z.eingerichtet ? (u.letzter_fehler ? <Chip art="fehler">Fehler</Chip> : u.laeuft ? <Chip art="warn">läuft</Chip> : <Chip art="ok">eingerichtet</Chip>)
          : <Chip art="warn">kein Ziel</Chip>} />
      {z.eingerichtet ? (
        <dl className="m-0">
          <Wert label="Adresse"><span className="num text-[0.8125rem] break-all">{z.url}</span></Wert>
          <Wert label="Benutzer · Ordner">{z.benutzer} · {z.ordner ? `/${z.ordner}` : "/"}</Wert>
          <Wert label="Zeitfenster">{z.von === z.bis ? "ganztägig" : `${z.von}–${z.bis} Uhr`}{u.im_zeitfenster ? <span className="gedaempft"> · gerade offen</span>
            : u.naechstes_fenster ? <span className="gedaempft"> · nächstes {relativ(u.naechstes_fenster, true)}</span> : null}</Wert>
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
                  <td className="td"><AuftragStatus a={a} /></td>
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
type Offen = null | "jetzt" | "passwort" | "pruefen" | "ziel" | "ziel_entfernen" | "uebertragen";

export function Backup() {
  const qc = useQueryClient();
  const daten = useQuery({
    queryKey: ["backup"],
    queryFn: () => api<Daten>("backup/"),
    refetchInterval: (q) => ((q.state.data?.auftraege ?? []).some((a) => a.offen) ? 3000 : 30_000),
    retry: false,
  });
  const [offen, setOffen] = useState<Offen>(null);
  const [wahl, setWahl] = useState<Sicherung | null>(null);
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
        rechts={<Knopf variante="pri" icon="backup" laedt={laufend.has("sicherung")} disabled={laufend.has("sicherung") || !d.agent.verzeichnis}
          onClick={() => setOffen("jetzt")}>Jetzt sichern</Knopf>} />

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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="kennzahlen">
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
        </Kennzahl>
      </div>

      <SicherungenTabelle daten={d} onWiederherstellen={setWahl} />

      <div className="flex gap-2.5 px-4 py-3 rounded-lg bg-fehler-bg text-fehler text-sm leading-normal items-start" data-testid="warnung-wiederherstellen">
        <Icon name="warnung" groesse={18} />
        <span><strong>Wiederherstellen ersetzt den aktuellen Datenbestand.</strong> Vorher wird automatisch eine Sicherung des jetzigen Stands
          angelegt. Zum Bestätigen muss das Admin-Passwort und der 2FA-Code eingegeben werden.</span>
      </div>

      <div className="grid grid-cols-1 hd:grid-cols-2 gap-5 items-start">
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
    </Seite>
  );
}
