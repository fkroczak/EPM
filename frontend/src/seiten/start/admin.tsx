/**
 * Kacheln der Administration auf der Startseite (S12–S14, Entwurf 2 „Startseite Admin“). Sie erscheinen nur mit dem
 * passenden Recht und nutzen dieselben Endpunkte wie die Seiten Backup, System, Benutzer und Audit-Log; Update und
 * Neustart öffnen denselben Bestätigungsdialog wie Administration › System (Passwort + 2FA, vorher Sicherung,
 * Warnung an die angemeldeten Benutzer).
 */
import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { dateigroesse, relativ, zahl, zeitpunkt } from "@/lib/format";
import { ROLLEN } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Fehleranzeige, Knopf, Laden, Leer, Meldung, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { AusfuehrenDialog, anteil, dauer, stufe } from "@/seiten/admin/System";
import type { Sitzung, Uebersicht, Wahl } from "@/seiten/admin/System";
import { Rueckfrage, systemdZeit } from "@/seiten/admin/Backup";
import type { Daten as BackupDaten } from "@/seiten/admin/Backup";
import { KachelFuss, KachelInhalt, KachelKopf } from "./kacheln";

export type Konto = { id: number; benutzername: string; anzeigename: string; rolle: string;
  probleme: ("gesperrt" | "einmal_kennwort" | "einmal_kennwort_abgelaufen" | "ohne_2fa" | "notfallcodes")[];
  gesperrt_am: string | null; sperrgrund: string; fehlversuche: number; einmal_kennwort_gueltig_bis: string | null;
  notfallcodes_uebrig: number; notfallcodes_gesamt: number };

export function useSystem(aktiv: boolean) {
  return useQuery({ queryKey: ["system", "uebersicht"], queryFn: () => api<Uebersicht>("system/uebersicht/"), refetchInterval: 60_000,
    enabled: aktiv });
}

export function useKonten(aktiv: boolean) {
  return useQuery({ queryKey: ["benutzer", "konten"], queryFn: () => api<Konto[]>("benutzer/konten/"), enabled: aktiv, refetchInterval: 60_000 });
}

function Messung({ label, prozent, text }: { label: string; prozent: number | null; text: ReactNode }) {
  const s = stufe(prozent);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-[0.8125rem] text-text2"><span>{label}</span><span className="num">{text}</span></div>
      <div role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={prozent ?? undefined}
        className="h-1.5 rounded-full bg-fein overflow-hidden">
        <div className={cx("h-full rounded-full", s === "ok" ? "bg-akzent" : s === "warn" ? "bg-warn" : "bg-fehler")}
          style={{ width: `${Math.min(100, Math.max(2, prozent ?? 0))}%` }} />
      </div>
    </div>
  );
}

function Feld3({ titel, wert, unter }: { titel: string; wert: ReactNode; unter?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 px-3.5 py-3 border border-fein rounded-[10px] min-w-0">
      <span className="text-[0.8125rem] gedaempft">{titel}</span>
      <span className="text-lg font-semibold leading-tight">{wert}</span>
      {unter}
    </div>
  );
}

// ---------------------------------------------------------------- Datensicherung
export function SicherungKachel() {
  const daten = useQuery({ queryKey: ["backup"], queryFn: () => api<BackupDaten>("backup/"), refetchInterval: 60_000, retry: false });
  const [frage, setFrage] = useState(false);
  const d = daten.data;
  const laeuft = !!d?.auftraege.some((a) => a.offen && a.aktion === "sicherung");
  return (
    <>
      <KachelKopf id="sicherung" titel="Datensicherung" rechts={d ? (
        <Knopf klein icon="backup" laedt={laeuft} disabled={laeuft || !d.agent.verzeichnis} onClick={() => setFrage(true)}>Jetzt sichern</Knopf>) : null} />
      <KachelInhalt className="flex flex-col gap-3">
        {!d ? (daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />) : (
          <>
            {d.kurz.zustand !== "ok" ? <Meldung art={d.kurz.zustand === "fehler" ? "fehler" : "warn"}>{d.kurz.titel}</Meldung> : null}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Feld3 titel="Letzte Sicherung" wert={d.letzte ? relativ(d.letzte.zeitpunkt, true) : "—"}
                unter={d.letzte ? <Chip art={d.letzte.verschluesselt ? "ok" : "warn"} className="self-start">
                  <Icon name="schloss" groesse={12} />{d.letzte.verschluesselt ? `verschlüsselt${d.letzte.passwort_nr ? ` · Nr. ${d.letzte.passwort_nr}` : ""}` : "unverschlüsselt"}</Chip> : null} />
              <Feld3 titel={d.ziel.hersteller === "nextcloud" ? "Übertragung Nextcloud" : "Übertragung"}
                wert={d.ziel.eingerichtet ? (d.uebertragung.letzter_erfolg ? relativ(d.uebertragung.letzter_erfolg, true) : "noch nie") : "—"}
                unter={!d.ziel.eingerichtet ? <span className="text-[0.78125rem] gedaempft">kein Ziel festgelegt</span>
                  : d.uebertragung.letzter_fehler ? <Chip art="fehler" className="self-start">Fehler</Chip>
                  : <Chip art="ok" className="self-start"><Icon name="haken" groesse={12} />übertragen</Chip>} />
              <Feld3 titel="Nächste Sicherung" wert={systemdZeit(d.naechste_sicherung) ?? "—"}
                unter={d.aufbewahrung_tage ? <span className="text-[0.78125rem] gedaempft">aufbewahrt {d.aufbewahrung_tage} Tage</span> : null} />
            </div>
            {d.speicher.gesamt ? (
              <Messung label="Speicher" prozent={anteil(d.speicher.belegt, d.speicher.gesamt)}
                text={`${dateigroesse(d.speicher.belegt ?? 0)} von ${dateigroesse(d.speicher.gesamt)}`} />
            ) : null}
            <span className="text-[0.78125rem] gedaempft">Sicherungen {dateigroesse(d.speicher.sicherungen ?? 0)} · {d.sicherungen.length} vorhanden
              {d.ziel.eingerichtet && d.ziel.von ? ` · Zeitfenster Übertragung ${d.ziel.von}–${d.ziel.bis}` : ""}</span>
          </>
        )}
      </KachelInhalt>
      <KachelFuss zu="/admin/backup">Zur Seite Backup</KachelFuss>
      {d ? (
        <Rueckfrage offen={frage} titel="Sicherung jetzt erstellen" knopf="Jetzt sichern" pfad="backup/jetzt/" onZu={() => setFrage(false)}
          text={<p className="m-0">Datenbank, Dokumente und Löschliste werden jetzt gesichert – wie die nächtliche Sicherung
            {d.verschluesselung.eingerichtet ? ", verschlüsselt mit dem Sicherungs-Passwort" : ", aber unverschlüsselt (kein Sicherungs-Passwort festgelegt)"}.
            EPM bleibt dabei erreichbar.</p>} />
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------- Server (S13)
export function ServerKachel() {
  const daten = useSystem(true);
  const d = daten.data;
  const h = d?.host && d.host.aktuell ? d.host : null;
  const sp = h?.speicher ?? d?.container.speicher;
  const platten = h?.platten?.length ? h.platten : d?.container.platten ?? [];
  const platte = platten.find((p) => p.bezeichnung === "EPM-Daten") ?? platten[0];
  const ram = anteil(sp && sp.gesamt != null && sp.verfuegbar != null ? sp.gesamt - sp.verfuegbar : null, sp?.gesamt);
  const cpu = h?.cpu?.prozent ?? null;
  return (
    <>
      <KachelKopf id="server" titel="Server" />
      <KachelInhalt className="flex flex-col gap-3" testid="kachel-server">
        {!d ? (daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />) : (
          <>
            <Messung label="CPU" prozent={cpu} text={cpu != null ? `${zahl(cpu, 0)} %` : "—"} />
            <Messung label="Arbeitsspeicher" prozent={ram} text={ram != null ? `${ram} %` : "—"} />
            <Messung label={`Platte ${platte?.bezeichnung ?? ""}`.trim()} prozent={platte ? anteil(platte.gesamt - platte.frei, platte.gesamt) : null}
              text={platte ? `${anteil(platte.gesamt - platte.frei, platte.gesamt)} %` : "—"} />
            <span className="text-[0.78125rem] gedaempft">läuft seit {dauer(h?.laufzeit_s ?? d.container.laufzeit_s)}
              {h ? ` · gemessen ${relativ(h.zeit, true)}` : " · ohne Systemagent nur Werte aus dem Container"}</span>
          </>
        )}
      </KachelInhalt>
      <KachelFuss zu="/admin/system">Zu Administration › System</KachelFuss>
    </>
  );
}

// ---------------------------------------------------------------- Ubuntu-Updates, Update und Neustart anstoßen (S13, S14)
export function UpdatesKachel() {
  const daten = useSystem(true);
  const auftraege = useQuery({ queryKey: ["system", "auftraege"], queryFn: () => api<{ aktion: string; offen: boolean }[]>("system/auftraege/"),
    refetchInterval: 30_000 });
  const [wahl, setWahl] = useState<Wahl | null>(null);
  const d = daten.data;
  const h = d?.host && d.host.aktuell ? d.host : null;
  const u = h?.updates;
  const offen = new Set((auftraege.data ?? []).filter((a) => a.offen).map((a) => a.aktion));
  const knopf = (code: string, text: string) => {
    const a = d?.aktionen.find((x) => x.code === code);
    if (!a) return null;
    return (
      <Knopf klein variante="dng" laedt={offen.has(code)} disabled={!a.erlaubt || !d!.agent.verzeichnis || offen.has(code)}
        onClick={() => setWahl({ art: "server", aktion: a })}>{offen.has(code) ? `${text} läuft` : text}</Knopf>
    );
  };
  return (
    <>
      <KachelKopf id="updates" titel="Ubuntu-Updates" />
      <KachelInhalt className="flex flex-col gap-2.5" testid="kachel-updates">
        {!d ? (daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />) : (
          <>
            <div className="flex items-baseline gap-2 flex-wrap">
              <span className="num text-[1.625rem] font-semibold">{u?.verfuegbar ? zahl(u.anzahl ?? 0) : "—"}</span>
              <span className="text-sm text-text2">ausstehend</span>
              {u?.sicherheit ? <Chip art="fehler">{u.sicherheit} Sicherheit</Chip> : null}
            </div>
            {h?.neustart_noetig ? <Chip art="warn" className="self-start"><Icon name="neustart" groesse={12} />Neustart nötig</Chip> : null}
            {!h ? <span className="text-[0.8125rem] gedaempft">Der Systemagent meldet sich gerade nicht – Updates werden erst angezeigt, wenn er wieder läuft.</span> : null}
            <span className="text-[0.78125rem] gedaempft leading-normal">Beides mit Passwort und 2FA; vorher automatische Sicherung, angemeldete Benutzer werden gewarnt.</span>
            <div className="flex gap-2 flex-wrap mt-auto">{knopf("updates_installieren", "Updates installieren")}{knopf("server_neustart", "Server neu starten")}</div>
          </>
        )}
      </KachelInhalt>
      {d ? <AusfuehrenDialog wahl={wahl} daten={d} onZu={() => setWahl(null)} /> : null}
    </>
  );
}

// ---------------------------------------------------------------- Konten (S12)
const KONTO_TEXT: Record<Konto["probleme"][number], [string, "fehler" | "warn" | undefined]> = {
  gesperrt: ["gesperrt", "fehler"], einmal_kennwort: ["Einmal-Kennwort offen", "warn"],
  einmal_kennwort_abgelaufen: ["Einmal-Kennwort abgelaufen", "warn"], ohne_2fa: ["ohne zweiten Faktor", "warn"],
  notfallcodes: ["Notfall-Codes knapp", undefined],
};

export function KontenKachel() {
  const konten = useKonten(true);
  const qc = useQueryClient();
  const melden = useHinweis();
  const entsperren = useMutation({
    mutationFn: (k: Konto) => api(`benutzer/${k.id}/entsperren/`, { method: "POST" }),
    onSuccess: (_d, k) => { void qc.invalidateQueries({ queryKey: ["benutzer"] }); melden(`${k.anzeigename} entsperrt.`); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const liste = konten.data ?? [];
  return (
    <>
      <KachelKopf id="konten" titel="Konten" />
      <KachelInhalt testid="kachel-konten">
        {konten.isLoading ? <Laden /> : <Fehleranzeige fehler={konten.error} />}
        {konten.data && liste.length === 0 ? <Leer>Alle Konten in Ordnung.</Leer> : null}
        {liste.map((k) => (
          <div key={k.id} className="flex justify-between items-center gap-3 py-2 border-b border-rand last:border-b-0">
            <span className="flex flex-col gap-1 min-w-0">
              <span className="flex gap-1 flex-wrap">{k.probleme.map((p) => <Chip key={p} art={KONTO_TEXT[p][1]}>{KONTO_TEXT[p][0]}</Chip>)}</span>
              <Link to={`/admin/benutzer?id=${k.id}`} className="font-medium no-underline truncate">{k.anzeigename}</Link>
              <span className="text-[0.78125rem] gedaempft">{ROLLEN[k.rolle] ?? k.rolle}{k.gesperrt_am ? ` · ${k.sperrgrund}` : ""}</span>
            </span>
            {k.probleme.includes("gesperrt") ? (
              <Knopf klein laedt={entsperren.isPending && entsperren.variables?.id === k.id} onClick={() => entsperren.mutate(k)}
                aria-label={`${k.anzeigename} entsperren`}>Entsperren</Knopf>
            ) : k.probleme.includes("notfallcodes") ? (
              <span className="num gedaempft text-[0.8125rem]">{k.notfallcodes_uebrig} von {k.notfallcodes_gesamt}</span>
            ) : null}
          </div>
        ))}
      </KachelInhalt>
      <KachelFuss zu="/admin/benutzer">Zu Benutzer</KachelFuss>
    </>
  );
}

// ---------------------------------------------------------------- Angemeldet (F89)
export function AngemeldetKachel() {
  const daten = useSystem(true);
  const qc = useQueryClient();
  const melden = useHinweis();
  const beenden = useMutation({
    mutationFn: (s: Sitzung) => api(`system/sitzungen/${s.id}/`, { method: "DELETE" }),
    onSuccess: (_d, s) => { void qc.invalidateQueries({ queryKey: ["system"] }); melden(`${s.name} abgemeldet.`); },
    onError: (e) => melden(e.message, "fehler"),
  });
  const liste = daten.data?.angemeldet ?? [];
  return (
    <>
      <KachelKopf id="angemeldet" titel={`Angemeldet${daten.data ? ` (${liste.length})` : ""}`} />
      <KachelInhalt testid="kachel-angemeldet">
        {!daten.data ? (daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />) : liste.map((s) => (
          <div key={s.id} className="flex justify-between items-center gap-3 py-2 border-b border-rand last:border-b-0">
            <span className="flex flex-col gap-px min-w-0">
              <span className="font-medium truncate">{s.eigene ? "Du" : s.name}</span>
              <span className="text-[0.78125rem] gedaempft truncate">{s.browser || "—"} · aktiv {relativ(s.zuletzt_am, true)}</span>
            </span>
            {s.eigene ? <Chip art="akzent">diese</Chip> : (
              <Knopf klein laedt={beenden.isPending && beenden.variables?.id === s.id} onClick={() => beenden.mutate(s)}
                aria-label={`${s.name} abmelden`}>Abmelden</Knopf>
            )}
          </div>
        ))}
      </KachelInhalt>
      <KachelFuss zu="/admin/system">Alle Anmeldungen</KachelFuss>
    </>
  );
}

// ---------------------------------------------------------------- Hinweis an alle (F89)
export function HinweisKachel() {
  const daten = useSystem(true);
  const qc = useQueryClient();
  const melden = useHinweis();
  const [text, setText] = useState("");
  const [minuten, setMinuten] = useState("60");
  const [art, setArt] = useState<"info" | "warnung">("info");
  const fertig = () => { void qc.invalidateQueries({ queryKey: ["system"] }); void qc.invalidateQueries({ queryKey: ["systemhinweis"] }); };
  const setzen = useMutation({
    mutationFn: () => api("system/hinweis/", { body: { text, art, minuten: minuten ? Number(minuten) : null } }),
    onSuccess: () => { fertig(); setText(""); melden("Hinweis an alle Benutzer gesetzt."); },
  });
  const beenden = useMutation({
    mutationFn: () => api("system/hinweis/", { method: "DELETE" }),
    onSuccess: () => { fertig(); melden("Hinweis beendet."); },
  });
  const h = daten.data?.hinweis;
  return (
    <>
      <KachelKopf id="hinweis" titel="Hinweis an alle" />
      <KachelInhalt className="flex flex-col gap-2.5" testid="kachel-hinweis">
        {h ? (
          <div className={cx("meldung flex flex-col gap-2", h.art === "warnung" ? "warn" : "info")}>
            <span>{h.text}<br /><span className="text-xs opacity-80">{h.gueltig_bis ? `bis ${zeitpunkt(h.gueltig_bis)}` : "bis er beendet wird"}</span></span>
            <Knopf klein className="self-start" laedt={beenden.isPending} onClick={() => beenden.mutate()}>Beenden</Knopf>
          </div>
        ) : <span className="text-[0.8125rem] gedaempft">Gerade ist kein Hinweis aktiv.</span>}
        <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); setzen.mutate(); }}>
          <Eingabe aria-label="Neuer Hinweis" maxLength={500} placeholder="z. B. Heute ab 18 Uhr Wartung" value={text} onChange={(e) => setText(e.target.value)} />
          <div className="flex gap-2 flex-wrap">
            <Auswahl aria-label="Anzeigen" className="w-auto" value={minuten} onChange={(e) => setMinuten(e.target.value)}>
              <option value="60">für 1 Stunde</option><option value="240">für 4 Stunden</option><option value="1440">für 1 Tag</option>
              <option value="">bis ich ihn beende</option>
            </Auswahl>
            <Auswahl aria-label="Art" className="w-auto" value={art} onChange={(e) => setArt(e.target.value as "info" | "warnung")}>
              <option value="info">Information</option><option value="warnung">Warnung</option>
            </Auswahl>
          </div>
          <Knopf type="submit" klein variante="pri" className="self-start" laedt={setzen.isPending} disabled={!text.trim()}>Hinweis setzen</Knopf>
        </form>
        <Fehleranzeige fehler={setzen.error ?? beenden.error} />
      </KachelInhalt>
    </>
  );
}

// ---------------------------------------------------------------- Zugriffe aus dem Audit-Log (S12)
type Zusammenfassung = { tage: number; von: string; zeilen: { schluessel: string; text: string; gruppe: string; anzahl: number }[] };

export function ZugriffeKachel() {
  const daten = useQuery({ queryKey: ["protokoll", "zusammenfassung"], queryFn: () => api<Zusammenfassung>("protokoll/zusammenfassung/?tage=7"),
    refetchInterval: 5 * 60_000 });
  return (
    <>
      <KachelKopf id="zugriffe" titel="Zugriffe · 7 Tage" />
      <KachelInhalt className="flex flex-col gap-2.5 text-sm" testid="kachel-zugriffe">
        {!daten.data ? (daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />) : daten.data.zeilen.map((z) => (
          <Link key={z.schluessel} to={`/admin/audit-log?gruppe=${z.gruppe}&tage=${daten.data!.tage}`}
            className="flex justify-between gap-3 no-underline text-tinte hover:text-akzent-text">
            <span>{z.text}</span><span className={cx("num", z.schluessel === "fehlversuche" && z.anzahl ? "text-fehler" : "text-akzent-text")}
              data-testid={`zugriffe-${z.schluessel}`}>{z.anzahl}</span>
          </Link>
        ))}
      </KachelInhalt>
      <KachelFuss zu="/admin/audit-log">Zum Audit-Log</KachelFuss>
    </>
  );
}

// ---------------------------------------------------------------- Testumgebung (S12)
type Testumgebung = { in_betreuung: number; abgeschlossen: number; zuletzt_am: string | null; zuletzt_von: string | null };

export function TestKachel() {
  const daten = useQuery({ queryKey: ["testdaten"], queryFn: () => api<Testumgebung>("testdaten/") });
  const [frage, setFrage] = useState(false);
  const qc = useQueryClient();
  const melden = useHinweis();
  const zuruecksetzen = useMutation({
    mutationFn: () => api<Record<string, number>>("testdaten/zuruecksetzen/", { method: "POST" }),
    onSuccess: () => {
      for (const k of [["testdaten"], ["startseite"], ["patienten"], ["meine-akten"]]) void qc.invalidateQueries({ queryKey: k });
      melden("Testdaten zurückgesetzt.");
      setFrage(false);
    },
  });
  const d = daten.data;
  return (
    <>
      <KachelKopf id="testumgebung" titel="Testumgebung" />
      <KachelInhalt className="flex flex-col gap-2.5" testid="kachel-testumgebung">
        {!d ? (daten.error ? <Fehleranzeige fehler={daten.error} /> : <Laden />) : (
          <>
            <div className="flex items-baseline gap-2"><span className="num text-2xl font-semibold">{d.in_betreuung + d.abgeschlossen}</span>
              <span className="text-sm text-text2">Testpatienten</span></div>
            <span className="text-[0.8125rem] gedaempft leading-normal">
              {d.zuletzt_am ? <>Zuletzt zurückgesetzt am <span className="num">{zeitpunkt(d.zuletzt_am)}</span>{d.zuletzt_von ? ` von ${d.zuletzt_von}` : ""}. </> : "Noch nie zurückgesetzt. "}
              Echte Akten bleiben dabei unverändert.</span>
            <Knopf klein className="self-start" onClick={() => setFrage(true)}>Testdaten zurücksetzen</Knopf>
          </>
        )}
      </KachelInhalt>
      <Dialog offen={frage} onOffen={setFrage} titel="Testdaten zurücksetzen"
        beschreibung="Alle Testpatienten (Nummern ab 9001) werden gelöscht und die Musterdaten neu angelegt. Echte Akten bleiben unverändert."
        fuss={<><Knopf onClick={() => setFrage(false)}>Abbrechen</Knopf>
          <Knopf variante="dng" laedt={zuruecksetzen.isPending} onClick={() => zuruecksetzen.mutate()}>Testdaten zurücksetzen</Knopf></>}>
        <Fehleranzeige fehler={zuruecksetzen.error} />
      </Dialog>
    </>
  );
}
