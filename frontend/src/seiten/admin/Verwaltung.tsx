/**
 * Administration › Systemverwaltung (Wunsch 10.10.2026, F179): eine Seite, auf der der Praxismanager auf einen Blick
 * sieht, ob alles in Ordnung ist (Ampel), und von der aus er die häufigen Aufgaben direkt erreicht – ohne SSH.
 * Die Ampeln nutzen dieselben Endpunkte wie System und Backup; jede führt zu dem Bereich, in dem man etwas tun kann.
 * Status nie nur über Farbe: jede Ampel hat Symbol und Text.
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { relativ, zahl } from "@/lib/format";
import { Seite } from "@/components/layout/Shell";
import { Fehleranzeige, Karte, KartenKopf, Knopf, KnopfLink, Laden, Meldung, Seitenkopf, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { Begriff } from "@/components/ui/Begriff";
import { AusfuehrenDialog, anteil } from "./System";
import type { Auftrag, Uebersicht, Wahl } from "./System";
import { Rueckfrage } from "./Backup";
import type { Daten as BackupDaten } from "./Backup";
import { AuslastungKarte } from "./auslastung";

type Stand = "ok" | "warn" | "fehler" | "unbekannt";
type Ampel = { id: string; titel: string; stand: Stand; wert: ReactNode; text: ReactNode; zu: string };

const SYMBOL: Record<Stand, string> = { ok: "haken", warn: "warnung", fehler: "warnung", unbekannt: "info" };
const STAND_TEXT: Record<Stand, string> = { ok: "in Ordnung", warn: "Hinweis", fehler: "Fehler", unbekannt: "unbekannt" };

function AmpelKachel({ a }: { a: Ampel }) {
  return (
    <Link to={a.zu} className={cx("card no-underline text-tinte px-4 py-3 flex flex-col gap-1 min-w-0 border-l-4 hover:border-akzent",
      a.stand === "ok" ? "border-l-[var(--ok)]" : a.stand === "warn" ? "border-l-[var(--warn)]" : a.stand === "fehler" ? "border-l-[var(--fehler)]"
        : "border-l-[var(--rand)]")} data-testid={`ampel-${a.id}`} data-stand={a.stand}>
      <span className="flex items-center justify-between gap-2 text-[0.8125rem] gedaempft">{a.titel}
        <span className={cx("flex items-center gap-1 text-xs", a.stand === "ok" ? "text-ok" : a.stand === "warn" ? "text-warn" : a.stand === "fehler"
          ? "text-fehler" : "gedaempft")}><Icon name={SYMBOL[a.stand]} groesse={12} />{STAND_TEXT[a.stand]}</span></span>
      <span className="text-base font-semibold leading-tight truncate">{a.wert}</span>
      <span className="text-xs gedaempft leading-snug">{a.text}</span>
    </Link>
  );
}

function schlimmer(a: Stand, b: Stand): Stand {
  const r: Stand[] = ["unbekannt", "ok", "warn", "fehler"];
  return r.indexOf(a) >= r.indexOf(b) ? a : b;
}

/** Ampeln aus den Daten von System und Backup (was fehlt, steht als „unbekannt“) */
export function ampeln(sys: Uebersicht | undefined, backup: BackupDaten | undefined, auftraege: Auftrag[]): Ampel[] {
  const liste: Ampel[] = [];
  const h = sys?.host && sys.host.aktuell ? sys.host : null;
  if (sys) {
    liste.push({ id: "agent", titel: "Systemagent", zu: "/admin/system", stand: sys.agent.erreichbar ? "ok" : sys.agent.verzeichnis ? "fehler" : "fehler",
      wert: sys.agent.erreichbar ? "meldet sich" : "meldet sich nicht",
      text: sys.agent.erreichbar ? `zuletzt gemessen ${relativ(sys.host?.zeit, true)}${h?.trocken ? " · Probelauf" : ""}` : "Aufträge an den Server warten, bis er wieder läuft" });
    const c = h?.container;
    const schlecht = (c?.liste ?? []).filter((x) => x.zustand !== "running" || (x.gesundheit && x.gesundheit !== "healthy"));
    liste.push({ id: "dienste", titel: "Dienste", zu: "/admin/system?reiter=wartung",
      stand: !c?.verfuegbar ? "unbekannt" : schlecht.length ? "fehler" : "ok",
      wert: !c?.verfuegbar ? "—" : schlecht.length ? `${schlecht.length} gestört` : `${c.liste.length} laufen`,
      text: schlecht.length ? schlecht.map((x) => `${x.dienst}: ${x.zustand}${x.gesundheit ? ` (${x.gesundheit})` : ""}`).join(", ") : "Container backend, web, ocr, db" });
    const platten = h?.platten?.length ? h.platten : sys.container.platten;
    const p = platten.find((x) => x.bezeichnung === "EPM-Daten") ?? platten[0];
    const belegt = p ? anteil(p.gesamt - p.frei, p.gesamt) : null;
    liste.push({ id: "platte", titel: "Speicherplatz", zu: "/admin/system?reiter=wartung",
      stand: belegt == null ? "unbekannt" : belegt >= 90 ? "fehler" : belegt >= 80 ? "warn" : "ok",
      wert: belegt == null ? "—" : `${belegt} % belegt`, text: p ? `${p.bezeichnung}: ${Math.round(p.frei / 1024 ** 3)} GB frei` : "" });
    const u = h?.updates;
    liste.push({ id: "updates", titel: "Ubuntu-Updates", zu: "/admin/system?reiter=wartung",
      stand: !u?.verfuegbar ? "unbekannt" : u.sicherheit || h?.neustart_noetig ? "warn" : "ok",
      wert: u?.verfuegbar ? `${zahl(u.anzahl ?? 0)} ausstehend` : "—",
      text: [u?.sicherheit ? `${u.sicherheit} Sicherheitsupdates` : "", h?.neustart_noetig ? "Neustart des Servers nötig" : "",
        u?.listen_am ? `Paketlisten ${relativ(u.listen_am, true)}` : ""].filter(Boolean).join(" · ") || "kommt vom Systemagenten" });
    const z = h?.zertifikat;
    liste.push({ id: "zertifikat", titel: "Zertifikat", zu: "/admin/system?reiter=zertifikat",
      stand: !z?.vorhanden || z.tage == null ? "unbekannt" : z.tage < 7 ? "fehler" : z.tage < 30 || z.selbst_signiert ? "warn" : "ok",
      wert: z?.tage != null ? (z.tage < 0 ? "abgelaufen" : `noch ${z.tage} Tage`) : "—",
      text: z?.vorhanden ? (z.selbst_signiert ? "selbst signiert – Browser warnen" : z.eigene_ca ? "eigene CA" : z.aussteller ?? "") : "kommt vom Systemagenten" });
    const t = sys.epm.texterkennung;
    liste.push({ id: "texterkennung", titel: "Texterkennung", zu: "/admin/system",
      stand: !t ? "unbekannt" : !t.dienst?.laeuft || t.verfahren?.fehler ? "fehler" : !t.verfahren?.paddle?.bereit || t.scans.fehler ? "warn" : "ok",
      wert: !t ? "—" : t.dienst?.laeuft ? "läuft" : "kein Lebenszeichen",
      text: !t ? "" : `${t.verfahren?.paddle?.bereit ? "Tesseract + PP-OCRv5" : "nur Tesseract"}${t.scans.fehler ? ` · ${t.scans.fehler} Scans mit Fehler` : ""}` });
    const uhr = h?.uhr;
    liste.push({ id: "uhr", titel: "Uhrzeit", zu: "/admin/system",
      stand: !uhr?.verfuegbar ? "unbekannt" : uhr.synchronisiert ? "ok" : "warn",
      wert: !uhr?.verfuegbar ? "—" : uhr.synchronisiert ? "synchron" : "nicht synchron",
      text: uhr?.verfuegbar ? `Zeitserver (NTP) ${uhr.ntp ? "an" : "aus"} · ${uhr.zeitzone}` : "kommt vom Systemagenten" });
  }
  if (backup) {
    const k = backup.kurz;
    liste.push({ id: "sicherung", titel: "Letzte Sicherung", zu: "/admin/backup",
      stand: k.zustand === "ok" ? "ok" : k.zustand === "warnung" ? "warn" : k.zustand === "fehler" ? "fehler" : "unbekannt",
      wert: backup.letzte ? relativ(backup.letzte.zeitpunkt, true) : "keine",
      text: k.zustand === "ok" ? `${backup.letzte?.verschluesselt ? "verschlüsselt" : "unverschlüsselt"} · ${backup.sicherungen.length} vorhanden` : k.titel });
    const z = backup.ziel, ue = backup.uebertragung;
    liste.push({ id: "uebertragung", titel: "Übertragung", zu: "/admin/backup?reiter=uebertragung",
      stand: !z.eingerichtet ? "warn" : ue.letzter_fehler ? "warn" : "ok",
      wert: !z.eingerichtet ? "kein Ziel" : ue.letzter_erfolg ? relativ(ue.letzter_erfolg, true) : "noch nie",
      text: !z.eingerichtet ? "Sicherungen liegen nur auf dem Server" : ue.letzter_fehler || `${ue.offen ?? 0} ausstehend · Zeitfenster ${z.von}–${z.bis}` });
  }
  const offen = auftraege.filter((a) => a.offen);
  const fehler = auftraege.filter((a) => a.status === "fehler" && Date.now() - Date.parse(a.angefordert_am) < 86400_000);
  if (sys) {
    liste.push({ id: "auftraege", titel: "Aufträge", zu: "/admin/system?reiter=verlauf",
      stand: fehler.length ? "warn" : "ok", wert: offen.length ? `${offen.length} laufen` : "keine offenen",
      text: fehler.length ? `${fehler.length} fehlgeschlagen in 24 h: ${fehler.slice(0, 2).map((a) => a.name).join(", ")}` : "keine Fehler in den letzten 24 Stunden" });
  }
  return liste;
}

function Aufgabe({ icon, titel, text, children }: { icon: string; titel: string; text: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-2.5 border-b border-rand last:border-b-0">
      <span className="w-8 h-8 shrink-0 rounded-lg bg-akzent-weich text-akzent-text flex items-center justify-center"><Icon name={icon} groesse={16} /></span>
      <div className="flex flex-col gap-0.5 min-w-0 grow">
        <span className="text-sm font-medium">{titel}</span>
        <span className="text-xs gedaempft">{text}</span>
      </div>
      <div className="flex gap-1.5 flex-wrap justify-end shrink-0">{children}</div>
    </div>
  );
}

export function Verwaltung() {
  const { darf } = useAuth();
  const system = darf("system_verwalten");
  const backupRecht = darf("backup_verwalten");
  const sys = useQuery({ queryKey: ["system", "uebersicht"], queryFn: () => api<Uebersicht>("system/uebersicht/"), refetchInterval: 60_000, enabled: system });
  const auftraege = useQuery({ queryKey: ["system", "auftraege"], queryFn: () => api<Auftrag[]>("system/auftraege/"), enabled: system,
    refetchInterval: (q) => ((q.state.data ?? []).some((a) => a.offen) ? 3000 : 30_000) });
  const backup = useQuery({ queryKey: ["backup"], queryFn: () => api<BackupDaten>("backup/"), refetchInterval: 60_000, enabled: backupRecht, retry: false });
  const [wahl, setWahl] = useState<Wahl | null>(null);
  const [sichern, setSichern] = useState(false);
  const liste = ampeln(sys.data, backup.data, auftraege.data ?? []);
  const gesamt = liste.reduce<Stand>((s, a) => (a.stand === "unbekannt" ? s : schlimmer(s, a.stand)), "ok");
  const d = sys.data;
  const aktion = (code: string) => d?.aktionen.find((a) => a.code === code);
  const offen = new Set((auftraege.data ?? []).filter((a) => a.offen).map((a) => a.aktion));
  const knopf = (code: string, text: string) => {
    const a = aktion(code);
    if (!a || !d) return null;
    return <Knopf klein variante={a.bestaetigung === "2fa" ? "dng" : "sec"} disabled={!a.erlaubt || !d.agent.verzeichnis || offen.has(code)}
      laedt={offen.has(code)} onClick={() => setWahl({ art: "server", aktion: a })}>{text}</Knopf>;
  };
  const laden = (system && !sys.data && !sys.error) || (backupRecht && !backup.data && !backup.error);
  const h = d?.host && d.host.aktuell ? d.host : null;
  return (
    <Seite pfad={[{ text: "Administration" }, { text: "Systemverwaltung" }]}>
      <Seitenkopf titel="Systemverwaltung" unter={<>Zustand von Server und EPM auf einen Blick – und die häufigen Aufgaben, ohne SSH. Ausgeführt vom <Begriff name="systemagent">Systemagenten</Begriff> auf dem Server.</>} />
      {system ? <Fehleranzeige fehler={sys.error} /> : null}
      {backupRecht ? <Fehleranzeige fehler={backup.error} /> : null}
      {laden ? <Laden /> : (
        <>
          {liste.length ? (
            <Meldung art={gesamt === "ok" ? "ok" : gesamt === "warn" ? "warn" : "fehler"}>
              <span data-testid="gesamtzustand">{gesamt === "ok" ? "Alles in Ordnung." : `${liste.filter((a) => a.stand === "fehler").length} Fehler, `
                + `${liste.filter((a) => a.stand === "warn").length} Hinweise – die markierten Kacheln führen direkt zur Abhilfe.`}</span>
            </Meldung>
          ) : null}
          <section aria-label="Zustand" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 fhd:grid-cols-4 gap-3" data-testid="ampeln">
            {liste.map((a) => <AmpelKachel key={a.id} a={a} />)}
          </section>
          <div className="stapel grid grid-cols-1 hd:grid-cols-2 gap-4 items-start">
            <Karte className="px-5 py-4 flex flex-col" data-testid="aufgaben">
              <KartenKopf titel="Häufige Aufgaben" unter="Gefährliches verlangt Passwort und zweiten Faktor; alles steht im Audit-Log." />
              {backupRecht ? (
                <Aufgabe icon="backup" titel="Sicherung" text="Jetzt sichern, Sicherungen herunterladen, löschen oder wiederherstellen.">
                  <Knopf klein onClick={() => setSichern(true)} disabled={!backup.data?.agent.verzeichnis}>Jetzt sichern</Knopf>
                  <KnopfLink klein to="/admin/backup">Sicherungen</KnopfLink>
                </Aufgabe>
              ) : null}
              {system ? (
                <>
                  <Aufgabe icon="neustart" titel="Updates" text={`Ubuntu: ${h?.updates?.verfuegbar ? `${h.updates.anzahl ?? 0} ausstehend` : "—"} · EPM: Version ${d?.epm.version ?? "—"}`}>
                    {knopf("updates_installieren", "Ubuntu-Updates")}{knopf("epm_update", "EPM aktualisieren")}
                  </Aufgabe>
                  <Aufgabe icon="server" titel="Server und Dienste" text="Server oder einzelne Dienste neu starten, aufräumen.">
                    {knopf("server_neustart", "Server neu starten")}
                    <KnopfLink klein to="/admin/system?reiter=wartung">Dienste</KnopfLink>
                  </Aufgabe>
                  <Aufgabe icon="hochladen" titel="Software" text="Version zurückschalten, Update-Paket oder OCR-Modelle hochladen.">
                    <KnopfLink klein to="/admin/system?reiter=software">Software</KnopfLink>
                  </Aufgabe>
                  <Aufgabe icon="schloss" titel="Zertifikat" text="Ablauf prüfen, erneuern, eigenes Zertifikat importieren, Stammzertifikat für Geräte.">
                    <KnopfLink klein to="/admin/system?reiter=zertifikat">Zertifikat</KnopfLink>
                  </Aufgabe>
                  <Aufgabe icon="dokument" titel="Protokolle" text="Container, Systemagent, Sicherung, Update – letzte Zeilen ansehen und herunterladen.">
                    <KnopfLink klein to="/admin/system?reiter=protokolle">Protokolle</KnopfLink>
                  </Aufgabe>
                  <Aufgabe icon="info" titel="Hinweis an alle" text="Vor Wartungsarbeiten alle Angemeldeten informieren.">
                    <KnopfLink klein to="/admin/system?reiter=anmeldungen">Hinweis setzen</KnopfLink>
                  </Aufgabe>
                </>
              ) : null}
              {darf("benutzer_verwalten") ? (
                <Aufgabe icon="benutzer" titel="Benutzer" text="Konten anlegen, entsperren, Einmal-Passwort, Rechte je Gruppe.">
                  <KnopfLink klein to="/admin/benutzer?neu=1">Benutzer anlegen</KnopfLink>
                  <KnopfLink klein to="/admin/benutzer">Benutzer</KnopfLink>
                </Aufgabe>
              ) : null}
              {darf("audit_lesen") ? (
                <Aufgabe icon="uhr" titel="Audit-Log" text="Wer hat wann was getan – auch jede Tätigkeit dieser Seite.">
                  <KnopfLink klein to="/admin/audit-log">Audit-Log</KnopfLink>
                </Aufgabe>
              ) : null}
            </Karte>
            {system ? <AuslastungKarte /> : null}
          </div>
        </>
      )}
      {d ? <AusfuehrenDialog wahl={wahl} daten={d} onZu={() => setWahl(null)} /> : null}
      {backup.data ? (
        <Rueckfrage offen={sichern} titel="Sicherung jetzt erstellen" knopf="Jetzt sichern" pfad="backup/jetzt/" onZu={() => setSichern(false)}
          text={<p className="m-0">Datenbank, Dokumente und Löschliste werden jetzt gesichert – wie die nächtliche Sicherung. EPM bleibt dabei erreichbar.</p>} />
      ) : null}
    </Seite>
  );
}
