/**
 * Stammzertifikat der eigenen CA zum Herunterladen für jedes Gerät (Wunsch 11.10.2026: „Zertifikat exportierbar“).
 * Öffentlich und ohne Schlüssel – Nginx liefert es unter /epm-ca.crt, für iPhone/iPad zusätzlich als Profil
 * /epm-ca.mobileconfig (schreibt epm-zertifikat). Fehlt das Profil (ältere Server), baut der Browser es aus dem
 * Zertifikat. Ohne eigene CA auf dem Server (selbst signiert) erscheint nichts.
 */
import { useQuery } from "@tanstack/react-query";
import { Icon } from "@/components/ui/icon";
import { cx } from "@/components/ui/basis";

const CRT = "/epm-ca.crt";
const PROFIL = "/epm-ca.mobileconfig";

/** PEM des Stammzertifikats oder null (nicht eingerichtet; die Entwicklung liefert dann die Startseite aus) */
function usePem() {
  return useQuery({
    queryKey: ["stammzertifikat"],
    queryFn: async () => {
      const a = await fetch(CRT, { credentials: "same-origin" });
      const text = a.ok ? await a.text() : "";
      return text.includes("-----BEGIN CERTIFICATE-----") ? text : null;
    },
    staleTime: 60 * 60_000,
    retry: false,
  });
}

type Geraet = "ios" | "android" | "mac" | "windows";

function geraet(): Geraet {
  const ua = navigator.userAgent;
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "ios";
  if (/Android/.test(ua)) return "android";
  if (/Macintosh/.test(ua)) return "mac";
  return "windows"; // Windows und Linux: die .crt-Datei
}

function profilAusPem(pem: string): string {
  const der = pem.replace(/-----(BEGIN|END) CERTIFICATE-----/g, "").replace(/\s+/g, "");
  const u = () => crypto.randomUUID().toUpperCase();
  const [a, b] = [u(), u()];
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>PayloadContent</key><array><dict>
<key>PayloadCertificateFileName</key><string>epm-ca.crt</string>
<key>PayloadContent</key><data>${der}</data>
<key>PayloadDisplayName</key><string>EPM Stammzertifikat</string>
<key>PayloadIdentifier</key><string>epm.stammzertifikat.${b}</string>
<key>PayloadType</key><string>com.apple.security.root</string>
<key>PayloadUUID</key><string>${b}</string>
<key>PayloadVersion</key><integer>1</integer>
</dict></array>
<key>PayloadDisplayName</key><string>EPM Stammzertifikat</string>
<key>PayloadIdentifier</key><string>epm.profil.${a}</string>
<key>PayloadType</key><string>Configuration</string>
<key>PayloadUUID</key><string>${a}</string>
<key>PayloadVersion</key><integer>1</integer>
</dict></plist>`;
}

async function profilLaden(pem: string) {
  try {
    const a = await fetch(PROFIL, { credentials: "same-origin" });
    if (a.ok && (await a.clone().text()).includes("<plist")) {
      window.location.href = PROFIL; // iOS bietet die Installation nur beim direkten Aufruf an
      return;
    }
  } catch { /* weiter mit dem Profil aus dem Browser */ }
  const url = URL.createObjectURL(new Blob([profilAusPem(pem)], { type: "application/x-apple-aspen-config" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: "EPM-Stammzertifikat.mobileconfig" });
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

const ANLEITUNG: Record<Geraet, { titel: string; schritte: string }> = {
  windows: { titel: "Windows", schritte: "Datei öffnen › Zertifikat installieren › Lokaler Computer › „Alle Zertifikate in folgendem Speicher speichern“ › Vertrauenswürdige Stammzertifizierungsstellen › Fertig stellen. Danach den Browser neu starten." },
  mac: { titel: "Mac", schritte: "Datei öffnen (Schlüsselbundverwaltung) › Zertifikat „EPM …“ doppelklicken › Vertrauen › „Immer vertrauen“." },
  ios: { titel: "iPhone und iPad", schritte: "„Profil für iPhone/iPad“ antippen und erlauben › Einstellungen › Profil geladen › Installieren. Danach: Einstellungen › Allgemein › Info › Zertifikatsvertrauenseinstellungen › „EPM Stammzertifikat“ einschalten." },
  android: { titel: "Android", schritte: "Datei laden › Einstellungen › Sicherheit › Verschlüsselung und Anmeldedaten › Zertifikat installieren › CA-Zertifikat › Datei wählen." },
};

/** Download-Knöpfe und Anleitung; ``kompakt`` für die Anmeldeseite (nur die Knöpfe für dieses Gerät) */
export function Stammzertifikat({ kompakt, titel, className }: { kompakt?: boolean; titel?: string; className?: string }) {
  const pem = usePem();
  if (!pem.data) return null;
  const g = geraet();
  const reihenfolge = (["windows", "mac", "ios", "android"] as const).slice().sort((x, y) => Number(y === g) - Number(x === g));
  const knoepfe = (
    <div className="flex gap-2 flex-wrap">
      <a className={cx("btn", g !== "ios" ? "pri" : "sec")} href={CRT} download="epm-ca.crt" data-testid="stammzertifikat-crt">
        <Icon name="herunterladen" />Stammzertifikat (.crt)</a>
      <button type="button" className={cx("btn", g === "ios" ? "pri" : "sec")} onClick={() => void profilLaden(pem.data!)} data-testid="stammzertifikat-profil">
        <Icon name="herunterladen" />Profil für iPhone/iPad</button>
    </div>
  );
  if (kompakt) return <div className={cx("flex flex-col gap-2", className)} data-testid="stammzertifikat">{knoepfe}</div>;
  return (
    <div className={cx("flex flex-col gap-3 text-sm", className)} data-testid="stammzertifikat">
      {titel ? <h2 className="lbl m-0">{titel}</h2> : null}
      <p className="m-0">Einmal je Gerät installieren: Danach meldet der Browser keine Warnung mehr, und die Anmeldung per Passkey
        (Fingerabdruck, Gesicht, PIN) ist möglich. Das Zertifikat ist öffentlich und enthält keinen Schlüssel.</p>
      {knoepfe}
      <ul className="m-0 pl-5 flex flex-col gap-1.5">
        {reihenfolge.map((k) => (
          <li key={k} className={k === g ? "font-medium" : undefined}>
            <span className="font-medium">{ANLEITUNG[k].titel}{k === g ? " (dieses Gerät)" : ""}:</span>{" "}
            <span className={k === g ? "font-normal" : "gedaempft"}>{ANLEITUNG[k].schritte}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
