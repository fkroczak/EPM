/**
 * Administration › System › Zugang (Wunsch 11.10.2026): SSH nur auf Zeit (1, 4 oder 8 Stunden, danach schließt der Server
 * es selbst), erlaubte Netze für EPM (HTTPS) und SSH, Netzfilter für EPM, Firewall-Regeln (nur lesend) und von Fail2ban
 * gesperrte Adressen. Alles als Auftrag an den Systemagenten, mit der Bestätigung, die das Backend verlangt.
 */
import { useState } from "react";
import { Auswahl, Chip, Eingabe, Feld, Karte, KartenKopf, Knopf, Leer, Meldung } from "@/components/ui/basis";
import { zeitpunkt } from "@/lib/format";
import { AuftragDialog } from "./SystemWartung";
import type { Uebersicht } from "./System";

type Netz = { netz: string; bezeichnung: string; seit?: string | null; von?: string };
type Regel = { ziel: string; port: string; proto: string; aktion: string; von: string; schnittstelle: string; v6: boolean;
  kommentar: string };
export type ZugangStand = {
  gespeichert?: boolean; fehler?: string;
  ssh?: { zustand: "offen" | "dauerhaft" | "geschlossen"; bis: string | null; seit?: string | null; von?: string; port: number;
    dienst_aktiv: boolean; regeln: number; abweichung?: boolean };
  stunden?: number[]; max?: number;
  netze?: { https: Netz[]; ssh: Netz[] };
  https_filter?: { an: boolean; aktiv: boolean; moeglich: boolean };
  ereignisse?: { id: string; zeit: string; ok: boolean; bis?: string; text: string }[];
  firewall?: { verfuegbar: boolean; aktiv: boolean; standard: Record<string, string>; regeln: Regel[]; hinweis?: string };
  fail2ban?: { verfuegbar: boolean; jails: { name: string; gesperrt: string[]; anzahl: number; gesamt?: number; fehlversuche?: number }[];
    hinweis?: string };
};
type Dienst = "https" | "ssh";
const DIENST_NAME: Record<Dienst, string> = { https: "EPM (HTTPS)", ssh: "SSH" };

/** Liegt die IPv4-Adresse im Netz (CIDR)? IPv6 wird hier nicht ausgewertet (EPM läuft nur über IPv4). */
export function imNetz(ip: string | null | undefined, netz: string): boolean {
  const zahl = (a: string) => {
    const t = a.split(".");
    if (t.length !== 4 || t.some((x) => !/^\d{1,3}$/.test(x) || Number(x) > 255)) return null;
    return t.reduce((n, x) => n * 256 + Number(x), 0);
  };
  if (!ip) return false;
  const [adresse, laenge = "32"] = netz.split("/");
  const a = zahl(ip.replace(/^::ffff:/i, "")), b = zahl(adresse), l = Number(laenge);
  if (a == null || b == null || !(l >= 0 && l <= 32)) return false;
  const maske = l === 0 ? 0 : 2 ** 32 - 2 ** (32 - l);
  return Math.floor(a / 2 ** (32 - l)) * 2 ** (32 - l) === (b & maske) >>> 0;
}

function Zeile({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[minmax(7.5rem,36%)_1fr] gap-3 py-1 text-sm border-b border-rand last:border-b-0">
      <dt className="gedaempft">{label}</dt>
      <dd className="m-0 min-w-0 break-words">{children}</dd>
    </div>
  );
}

// ---------------------------------------------------------------- SSH
function SshKarte({ daten, z, offen }: { daten: Uebersicht; z: ZugangStand; offen: Set<string> }) {
  const [oeffnen, setOeffnen] = useState<number | null>(null);
  const [schliessen, setSchliessen] = useState(false);
  const s = z.ssh;
  const netze = z.netze?.ssh ?? [];
  const laeuft = offen.has("server:ssh_oeffnen") || offen.has("server:ssh_schliessen");
  const chip = !s ? null : s.zustand === "geschlossen" ? <Chip art="ok">geschlossen</Chip>
    : s.zustand === "offen" ? <Chip art="warn">offen bis {zeitpunkt(s.bis)}</Chip>
      : <Chip art="fehler">dauerhaft offen (Ersteinrichtung)</Chip>;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3 min-w-0" data-testid="ssh-karte">
      <KartenKopf titel="SSH" rechts={chip}
        unter="Im Betrieb ist SSH aus. Bei Bedarf hier für 1, 4 oder 8 Stunden öffnen; danach schließt der Server es von selbst." />
      {s?.zustand === "dauerhaft" ? (
        <Meldung art="warn">SSH ist seit der Einrichtung dauerhaft offen. Bitte jetzt schließen und danach nur noch auf Zeit öffnen.</Meldung>
      ) : null}
      {s?.abweichung ? <Meldung art="warn">Der SSH-Dienst läuft, obwohl SSH als geschlossen gilt (z. B. von Hand gestartet). „Jetzt
        schließen“ stellt den Zustand wieder her.</Meldung> : null}
      {s ? (
        <dl className="m-0">
          <Zeile label="Port">{s.port}</Zeile>
          <Zeile label="Dienst">{s.dienst_aktiv ? "läuft" : "aus"} · {s.regeln} Firewall-Regel(n) für SSH</Zeile>
          <Zeile label="Erlaubte Netze">{netze.length ? netze.map((n) => n.netz).join(", ") : <span className="text-warn">keine – SSH lässt sich nicht öffnen</span>}</Zeile>
          {s.seit ? <Zeile label="Zuletzt geändert">{zeitpunkt(s.seit)}{s.von ? ` · ${s.von}` : ""}</Zeile> : null}
        </dl>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {(z.stunden ?? [1, 4, 8]).map((h) => (
          <Knopf key={h} disabled={!daten.agent.verzeichnis || laeuft || !netze.length} laedt={offen.has("server:ssh_oeffnen") && h === oeffnen}
            onClick={() => setOeffnen(h)} data-testid={`ssh-oeffnen-${h}`}>Für {h} h öffnen</Knopf>
        ))}
        <Knopf variante="dng" disabled={!daten.agent.verzeichnis || laeuft || s?.zustand === "geschlossen" && !s.abweichung && !s.regeln}
          laedt={offen.has("server:ssh_schliessen")} onClick={() => setSchliessen(true)} data-testid="ssh-schliessen">Jetzt schließen</Knopf>
      </div>
      <span className="text-xs gedaempft">Notzugang ohne SSH: die Konsole der VM im Hypervisor. Bestehende SSH-Verbindungen laufen nach dem
        Schließen weiter, bis sie enden.</span>
      {z.ereignisse?.length ? (
        <ul className="m-0 pl-5 text-xs gedaempft" data-testid="ssh-ereignisse">
          {z.ereignisse.slice(-3).reverse().map((e) => <li key={e.id}>{zeitpunkt(e.zeit)}: {e.ok ? "" : "Fehler – "}{e.text}</li>)}
        </ul>
      ) : null}
      <AuftragDialog offen={oeffnen != null} titel={`SSH für ${oeffnen} Stunde${oeffnen === 1 ? "" : "n"} öffnen`} aktion={daten.verwaltung?.ssh_oeffnen}
        pfad="system/zugang/ssh/oeffnen/" body={{ stunden: oeffnen }} daten={daten} knopf="Bestätigen und öffnen" onZu={() => setOeffnen(null)}>
        <Meldung art="info">SSH ist danach {oeffnen} Stunde{oeffnen === 1 ? "" : "n"} lang aus diesen Netzen erreichbar: {netze.map((n) => `${n.netz} (${n.bezeichnung})`).join(", ")}.
          Dann schließt der Server es von selbst.</Meldung>
      </AuftragDialog>
      <AuftragDialog offen={schliessen} titel="SSH jetzt schließen" aktion={daten.verwaltung?.ssh_schliessen} pfad="system/zugang/ssh/schliessen/"
        daten={daten} knopf="Schließen" onZu={() => setSchliessen(false)}>
        <Meldung art="info">Der Server entfernt die Firewall-Regeln für SSH und stoppt den Dienst. Bestehende Verbindungen laufen weiter.</Meldung>
      </AuftragDialog>
    </Karte>
  );
}

// ---------------------------------------------------------------- Erlaubte Netze und Netzfilter
function NetzListe({ dienst, liste, eigeneIp, onEntfernen, sperre }: { dienst: Dienst; liste: Netz[]; eigeneIp: string | null;
  onEntfernen: (n: Netz) => void; sperre: boolean }) {
  return (
    <div className="flex flex-col gap-1 min-w-0" data-testid={`netze-${dienst}`}>
      <span className="text-sm font-semibold">{DIENST_NAME[dienst]}</span>
      {!liste.length ? <Leer>Kein Netz eingetragen.</Leer> : liste.map((n) => {
        const eigenes = dienst === "https" && imNetz(eigeneIp, n.netz);
        const nurHier = eigenes && !liste.some((x) => x !== n && imNetz(eigeneIp, x.netz));
        const letztes = dienst === "https" && liste.length === 1;
        const grund = letztes ? "Das letzte Netz für EPM bleibt." : nurHier ? "Über dieses Netz erreicht Ihr Gerät EPM." : "";
        return (
          <div key={n.netz} className="flex items-center gap-2 py-1.5 border-b border-rand last:border-b-0 flex-wrap">
            <div className="flex flex-col min-w-0 grow">
              <span className="num text-[0.8125rem] break-all">{n.netz}{eigenes ? <Chip art="akzent" className="ml-2">Ihr Gerät</Chip> : null}</span>
              <span className="text-xs gedaempft break-words">{n.bezeichnung}{grund ? ` · ${grund}` : ""}</span>
            </div>
            <Knopf klein variante="dng" disabled={sperre || !!grund} onClick={() => onEntfernen(n)}
              aria-label={`${n.netz} für ${DIENST_NAME[dienst]} entfernen`}>Entfernen</Knopf>
          </div>
        );
      })}
    </div>
  );
}

function NetzeKarte({ daten, z, offen }: { daten: Uebersicht; z: ZugangStand; offen: Set<string> }) {
  const [neu, setNeu] = useState(false);
  const [dienst, setDienst] = useState<Dienst>("https");
  const [netz, setNetz] = useState("");
  const [bezeichnung, setBezeichnung] = useState("");
  const [weg, setWeg] = useState<{ dienst: Dienst; netz: Netz } | null>(null);
  const [filter, setFilter] = useState<boolean | null>(null);
  const eigeneIp = daten.angemeldet.find((s) => s.eigene)?.ip ?? null;
  const f = z.https_filter;
  const sperre = !daten.agent.verzeichnis || offen.has("server:netz_hinzufuegen") || offen.has("server:netz_entfernen");
  const imErlaubten = (z.netze?.https ?? []).some((n) => imNetz(eigeneIp, n.netz));
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3 min-w-0" data-testid="netze-karte">
      <KartenKopf titel="Erlaubte Netze" unter={`Aus diesen Netzen sind EPM und SSH erreichbar (je bis zu ${z.max ?? 20}). Ihr Gerät: ${eigeneIp ?? "unbekannt"}.`}
        rechts={<Knopf klein icon="plus" disabled={sperre} onClick={() => { setDienst("https"); setNetz(""); setBezeichnung(""); setNeu(true); }}
          data-testid="netz-neu">Netz hinzufügen</Knopf>} />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {(["https", "ssh"] as Dienst[]).map((d) => (
          <NetzListe key={d} dienst={d} liste={z.netze?.[d] ?? []} eigeneIp={eigeneIp} sperre={sperre}
            onEntfernen={(n) => setWeg({ dienst: d, netz: n })} />
        ))}
      </div>
      <span className="text-xs gedaempft">Schutz vor dem Aussperren: Das letzte Netz für EPM und das Netz Ihres Geräts lassen sich nicht entfernen.
        SSH-Netze gelten, solange SSH offen ist.</span>
      <div className="flex flex-col gap-2 pt-2 border-t border-rand" data-testid="netzfilter">
        <span className="text-sm font-semibold flex items-center gap-2 flex-wrap">Netzfilter für EPM
          <Chip art={f?.an ? (f.aktiv ? "ok" : "warn") : undefined}>{f?.an ? (f.aktiv ? "an" : "an, wird gerade eingehängt") : "aus"}</Chip></span>
        <span className="text-xs gedaempft">Docker umgeht die Firewall des Servers. Erst mit dem Netzfilter ist EPM wirklich nur aus den
          erlaubten Netzen erreichbar.</span>
        {f && !f.moeglich ? <Meldung art="warn">Auf dem Server fehlt EPM_MGMT_IP in /etc/epm/epm.conf. Ohne sie gibt es keinen Netzfilter.</Meldung> : null}
        {f && !f.an && !imErlaubten ? <Meldung art="warn">Ihr Gerät ist in keinem erlaubten Netz für EPM. Bitte zuerst Ihr Netz eintragen.</Meldung> : null}
        <Knopf className="self-start" variante={f?.an ? "dng" : "sec"} disabled={!daten.agent.verzeichnis || !f || offen.has("server:https_filter") || (!f.an && (!f.moeglich || !imErlaubten))}
          laedt={offen.has("server:https_filter")} onClick={() => setFilter(!f?.an)} data-testid="netzfilter-schalten">
          {f?.an ? "Netzfilter ausschalten" : "Netzfilter einschalten"}</Knopf>
      </div>
      <AuftragDialog offen={neu} titel="Netz hinzufügen" aktion={daten.verwaltung?.netz_hinzufuegen} pfad="system/zugang/netze/"
        body={{ dienst, netz: netz.trim(), bezeichnung: bezeichnung.trim() }} daten={daten} knopf="Bestätigen und hinzufügen" onZu={() => setNeu(false)}>
        <Feld label="Für">
          {(p) => <Auswahl {...p} value={dienst} onChange={(e) => setDienst(e.target.value as Dienst)}>
            <option value="https">EPM (HTTPS)</option><option value="ssh">SSH</option></Auswahl>}
        </Feld>
        <Feld label="Netz oder Adresse" pflicht hinweis={dienst === "https" ? "IPv4, z. B. 192.168.20.0/24 oder 10.8.0.5. Höchstens /8."
          : "IPv4 oder IPv6, z. B. 10.8.0.0/24 oder fd00:1::/64. Höchstens /8 bzw. /32."}>
          {(p) => <Eingabe {...p} spellCheck={false} autoComplete="off" inputMode="text" placeholder="192.168.20.0/24" value={netz}
            onChange={(e) => setNetz(e.target.value)} />}
        </Feld>
        <Feld label="Bezeichnung" pflicht hinweis="z. B. Praxisnetz 2 oder VPN">
          {(p) => <Eingabe {...p} maxLength={40} value={bezeichnung} onChange={(e) => setBezeichnung(e.target.value)} />}
        </Feld>
      </AuftragDialog>
      <AuftragDialog offen={!!weg} titel="Netz entfernen" aktion={daten.verwaltung?.netz_entfernen} pfad="system/zugang/netze/entfernen/"
        body={weg ? { dienst: weg.dienst, netz: weg.netz.netz } : {}} daten={daten} knopf="Bestätigen und entfernen" onZu={() => setWeg(null)}>
        {weg ? <Meldung art="warn">{weg.netz.netz} ({weg.netz.bezeichnung}) ist danach für {DIENST_NAME[weg.dienst]} nicht mehr erlaubt.
          Geräte aus diesem Netz erreichen {weg.dienst === "https" ? "EPM" : "SSH"} dann nicht mehr.</Meldung> : null}
      </AuftragDialog>
      <AuftragDialog offen={filter != null} titel={filter ? "Netzfilter einschalten" : "Netzfilter ausschalten"} aktion={daten.verwaltung?.https_filter}
        pfad="system/zugang/filter/" body={{ an: filter }} daten={daten} knopf={filter ? "Bestätigen und einschalten" : "Bestätigen und ausschalten"}
        onZu={() => setFilter(null)}>
        <Meldung art={filter ? "warn" : "info"}>{filter
          ? `EPM ist danach nur noch aus diesen Netzen erreichbar: ${(z.netze?.https ?? []).map((n) => n.netz).join(", ")}. Geräte in anderen Netzen sehen EPM nicht mehr.`
          : "EPM ist danach aus jedem Netz erreichbar, das den Server erreicht."}</Meldung>
      </AuftragDialog>
    </Karte>
  );
}

// ---------------------------------------------------------------- Firewall-Regeln (nur lesend)
const STANDARD_TEXT: Record<string, string> = { deny: "sperren", allow: "erlauben", reject: "abweisen", disabled: "aus" };

function FirewallKarte({ z }: { z: ZugangStand }) {
  const fw = z.firewall;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3 min-w-0" data-testid="firewall-karte">
      <KartenKopf titel="Firewall-Regeln" unter="Stand der Firewall des Servers (ufw), nur zum Ansehen."
        rechts={fw?.verfuegbar ? <Chip art={fw.aktiv ? "ok" : "fehler"}>{fw.aktiv ? "aktiv" : "inaktiv"}</Chip> : null} />
      {!fw?.verfuegbar ? <span className="text-sm gedaempft">Nicht abrufbar{fw?.hinweis ? `: ${fw.hinweis}` : ""}.</span> : (
        <>
          <dl className="m-0">
            {Object.entries(fw.standard).map(([richtung, wert]) => <Zeile key={richtung} label={`Standard ${richtung}`}>{STANDARD_TEXT[wert] ?? wert}</Zeile>)}
          </dl>
          {!fw.regeln.length ? <Leer>Keine Regeln.</Leer> : (
            <>
              <table className="tabelle max-sm:hidden" data-testid="firewall-tabelle">
                <thead><tr><th className="th">Aktion</th><th className="th">Port</th><th className="th">Von</th><th className="th">Kommentar</th></tr></thead>
                <tbody>{fw.regeln.map((r, i) => (
                  <tr key={i}><td className="td text-[0.8125rem]">{r.aktion}</td>
                    <td className="td num text-[0.8125rem]">{r.ziel}{r.v6 ? " (IPv6)" : ""}{r.schnittstelle ? <span className="gedaempft"> · {r.schnittstelle}</span> : null}</td>
                    <td className="td num text-[0.8125rem] break-all">{r.von}</td><td className="td text-[0.8125rem] break-words">{r.kommentar}</td></tr>))}</tbody>
              </table>
              <ul className="m-0 p-0 list-none flex flex-col sm:hidden" data-testid="firewall-liste">
                {fw.regeln.map((r, i) => (
                  <li key={i} className="py-1.5 border-b border-rand last:border-b-0 text-sm min-w-0">
                    <span className="font-medium">{r.aktion}</span> <span className="num break-all">{r.ziel}{r.v6 ? " (IPv6)" : ""}</span>
                    <span className="block text-xs gedaempft break-all">von {r.von}{r.schnittstelle ? ` · ${r.schnittstelle}` : ""}{r.kommentar ? ` · ${r.kommentar}` : ""}</span>
                  </li>))}
              </ul>
            </>
          )}
        </>
      )}
    </Karte>
  );
}

// ---------------------------------------------------------------- Fail2ban
function Fail2banKarte({ daten, z, offen }: { daten: Uebersicht; z: ZugangStand; offen: Set<string> }) {
  const [wahl, setWahl] = useState<{ jail: string; ip: string } | null>(null);
  const f = z.fail2ban;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3 min-w-0" data-testid="fail2ban-karte">
      <KartenKopf titel="Gesperrte Adressen (Fail2ban)" unter="Fail2ban sperrt Adressen nach mehreren Fehlversuchen für eine Stunde." />
      {!f?.verfuegbar ? <span className="text-sm gedaempft">Nicht abrufbar{f?.hinweis ? `: ${f.hinweis}` : ""}.</span>
        : !f.jails.length ? <Leer>Keine Jails eingerichtet.</Leer> : f.jails.map((j) => (
          <div key={j.name} className="flex flex-col gap-1" data-testid={`jail-${j.name}`}>
            <span className="text-sm font-semibold">{j.name} <span className="font-normal gedaempft">· {j.anzahl} gesperrt
              {j.fehlversuche != null ? ` · ${j.fehlversuche} Fehlversuche` : ""}{j.gesamt != null ? ` · ${j.gesamt} Sperren insgesamt` : ""}</span></span>
            {!j.gesperrt.length ? <span className="text-xs gedaempft">Keine gesperrten Adressen.</span> : j.gesperrt.map((ip) => (
              <div key={ip} className="flex items-center justify-between gap-2 py-1 border-b border-rand last:border-b-0">
                <span className="num text-[0.8125rem] break-all">{ip}</span>
                <Knopf klein disabled={!daten.agent.verzeichnis || offen.has("server:fail2ban_entsperren")} onClick={() => setWahl({ jail: j.name, ip })}
                  aria-label={`${ip} entsperren`}>Entsperren</Knopf>
              </div>
            ))}
          </div>
        ))}
      <AuftragDialog offen={!!wahl} titel="Adresse entsperren" aktion={daten.verwaltung?.fail2ban_entsperren} pfad="system/zugang/entsperren/"
        body={wahl ?? {}} daten={daten} knopf="Entsperren" onZu={() => setWahl(null)}>
        {wahl ? <Meldung art="info">{wahl.ip} ist danach in „{wahl.jail}“ nicht mehr gesperrt. Neue Fehlversuche sperren sie wieder.</Meldung> : null}
      </AuftragDialog>
    </Karte>
  );
}

export function ZugangBereich({ daten, offen }: { daten: Uebersicht; offen: Set<string> }) {
  const h = daten.host && daten.host.aktuell ? daten.host : null;
  const z = h?.zugang;
  if (!z || !z.ssh) {
    return (
      <Meldung art="info">{z?.fehler ? `Der Stand des Zugangs ist nicht lesbar: ${z.fehler}`
        : "Der Stand von SSH, Firewall und Fail2ban kommt vom Systemagenten. Er meldet ihn nach dem nächsten EPM-Update."}</Meldung>
    );
  }
  return (
    <div className="stapel grid grid-cols-1 hd:grid-cols-2 gap-4 items-start" data-testid="zugang">
      <SshKarte daten={daten} z={z} offen={offen} />
      <NetzeKarte daten={daten} z={z} offen={offen} />
      <FirewallKarte z={z} />
      <Fail2banKarte daten={daten} z={z} offen={offen} />
    </div>
  );
}
