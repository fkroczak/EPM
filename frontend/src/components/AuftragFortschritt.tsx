/**
 * Fortschritt eines Auftrags auf dem Server (Wunsch 08.10.2026: „Fortschrittsbalken mit ungefährer Zeitangabe in
 * gleicher Farbe wie der Ladebalken beim Backup oder Update“).
 *
 * Der Systemagent meldet keinen Prozentstand, nur Beginn und Ende. Geschätzt wird deshalb aus der Dauer der letzten
 * erledigten Aufträge derselben Art (Median der letzten fünf), ohne solche aus festen Erfahrungswerten. Der Balken
 * füllt sich nach der verstrichenen Zeit bis höchstens 95 %; dauert es länger als üblich, sagt er das, statt stehen zu
 * bleiben. Wartet ein Auftrag mit verzögertem Beginn, läuft die Zeit bis zum Beginn herunter.
 */
import { useEffect, useState } from "react";
import { cx } from "@/components/ui/basis";

/** was ein Auftrag dafür mitbringen muss (System und Backup haben eigene, gleich aufgebaute Typen) */
export type AuftragZeit = {
  id: number; aktion: string; status: string; offen: boolean;
  angefordert_am: string; begonnen_am: string | null; beendet_am: string | null;
  parameter: { minuten?: number };
};

/** Erfahrungswerte in Sekunden, solange es noch keinen erledigten Auftrag derselben Art gibt */
const UEBLICH_S: Record<string, number> = {
  sicherung: 180, sicherung_uebertragen: 300, sicherung_einlesen: 240, sicherung_bereitstellen: 120,
  wiederherstellen: 600, epm_update: 900, updates_installieren: 600, updates_suchen: 60, server_neustart: 180,
  epm_neustart: 90, docker_aufraeumen: 120, pakete_aufraeumen: 120, datenbank_leeren: 180,
  // Wartung ohne SSH (10.10.2026)
  sicherung_loeschen: 15, dienst_neustart: 45, epm_zurueck: 300, epm_paket: 900, epm_paket_erstellen: 600, zertifikat_erneuern: 20,
  zertifikat_importieren: 20, ocr_modelle: 90, protokoll: 10,
};
const STANDARD_S = 120;

function sekunden(von: string, bis: string | number) {
  return ((typeof bis === "number" ? bis : Date.parse(bis)) - Date.parse(von)) / 1000;
}

/** übliche Dauer aus den letzten erledigten Aufträgen derselben Art (Median der letzten fünf) */
export function ueblicheDauer(aktion: string, liste: AuftragZeit[]): { s: number; geschaetzt: boolean } {
  const dauern = liste
    .filter((a) => a.aktion === aktion && a.status === "erledigt" && a.begonnen_am && a.beendet_am)
    .slice(0, 5)
    .map((a) => sekunden(a.begonnen_am!, a.beendet_am!))
    .filter((s) => s > 0)
    .sort((x, y) => x - y);
  if (!dauern.length) return { s: UEBLICH_S[aktion] ?? STANDARD_S, geschaetzt: true };
  return { s: Math.max(5, dauern[Math.floor(dauern.length / 2)]), geschaetzt: false };
}

export function ungefaehr(s: number): string {
  if (s < 50) return "unter 1 Min.";
  const min = Math.round(s / 60);
  if (min < 60) return `ca. ${min} Min.`;
  const h = Math.floor(min / 60), rest = min % 60;
  return `ca. ${h} h${rest ? ` ${rest} Min.` : ""}`;
}

function useJetzt(aktiv: boolean) {
  const [jetzt, setJetzt] = useState(() => Date.now());
  useEffect(() => {
    if (!aktiv) return;
    const t = window.setInterval(() => setJetzt(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [aktiv]);
  return jetzt;
}

export function AuftragFortschritt({ a, liste, className }: { a: AuftragZeit; liste: AuftragZeit[]; className?: string }) {
  const laeuft = a.status === "laeuft" && !!a.begonnen_am;
  const wartet = a.status === "wartet";
  const jetzt = useJetzt(a.offen);
  if (!a.offen || (!laeuft && !wartet)) return null;
  const ueblich = ueblicheDauer(a.aktion, liste);
  let anteil = 0, text = "", unbestimmt = false;
  if (laeuft) {
    const bisher = Math.max(0, sekunden(a.begonnen_am!, jetzt));
    anteil = Math.min(95, (bisher / ueblich.s) * 100);
    const rest = ueblich.s - bisher;
    text = rest > 0
      ? `${Math.round(anteil)} % · noch ${ungefaehr(rest)} (üblich ${ungefaehr(ueblich.s)}${ueblich.geschaetzt ? ", geschätzt" : ""})`
      : `dauert länger als üblich – bisher ${ungefaehr(bisher)}, üblich ${ungefaehr(ueblich.s)}`;
    if (rest <= 0) unbestimmt = true;
  } else {
    const beginn = Date.parse(a.angefordert_am) + (a.parameter.minuten ?? 0) * 60_000;
    const bis = (beginn - jetzt) / 1000;
    unbestimmt = true;
    text = bis > 5 ? `beginnt in ${ungefaehr(bis)} · Dauer dann ${ungefaehr(ueblich.s)}` : `wartet, bis der Server den Auftrag abholt · Dauer dann ${ungefaehr(ueblich.s)}`;
  }
  return (
    <div className={cx("flex flex-col gap-1 min-w-[11.25rem]", className)} data-testid="auftrag-fortschritt">
      <div className={cx("fortschritt", unbestimmt && "unbestimmt")} role="progressbar" aria-label="Fortschritt (geschätzt)"
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={unbestimmt ? undefined : Math.round(anteil)} aria-valuetext={text}>
        <div className="fortschritt-fuellung" style={unbestimmt ? undefined : { width: `${anteil}%` }} />
      </div>
      <span className="text-xs gedaempft">{text}</span>
    </div>
  );
}

/** Laufende und wartende Aufträge oben auf der Seite (System, Backup) – sichtbar, ohne zum Verlauf zu scrollen */
export function LaufendeAuftraege({ liste }: { liste: (AuftragZeit & { name: string })[] }) {
  const offen = liste.filter((a) => a.offen);
  if (!offen.length) return null;
  return (
    <section className="card px-5 py-3.5 flex flex-col gap-3" data-testid="laufende-auftraege" aria-label="Laufende Tätigkeiten">
      {offen.map((a) => (
        <div key={a.id} className="grid grid-cols-1 md:grid-cols-[minmax(10rem,16rem)_minmax(0,1fr)] gap-x-4 gap-y-1 items-center">
          <span className="text-sm font-medium">{a.name}</span>
          <AuftragFortschritt a={a} liste={liste} />
        </div>
      ))}
    </section>
  );
}
