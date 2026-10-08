/** Gemeinsames für den Menüpunkt „Scans“ (F160 ff.): Adressen, Bezeichnungen, Text. */
import type { ScanErgebnis, ScanSeite, ScanWort, ScanZeile } from "@/lib/typen";

/** Wörter mit geringerer Sicherheit werden markiert (wie im Backend: scans/ocr/fusion.py, UNSICHER) */
export const UNSICHER = 0.8;

export const ARTEN: Record<string, string> = { labor: "Laborbefund", bia: "BIA-Messung", arztbrief: "Arztbrief" };

export const STATUS: Record<ScanZeile["status"], string> = {
  wartet: "wartet", laeuft: "wird erkannt", fertig: "erkannt", fehler: "Fehler",
};

export function bildUrl(scanId: number, seite: ScanSeite, art: "bild" | "roh" | "klein" = "bild"): string {
  // „v“ wechselt mit jeder neuen Aufbereitung: der Browser holt dann das neue Bild
  return `/api/scans/${scanId}/seiten/${seite.id}/bild/?art=${art}&v=${encodeURIComponent(seite.erkannt_am ?? String(seite.id))}`;
}

export function hatErgebnis(e: ScanSeite["ergebnis"]): e is ScanErgebnis {
  return !!e && Array.isArray((e as ScanErgebnis).reihen);
}

export function woerter(e: ScanSeite["ergebnis"]): ScanWort[] {
  if (!hatErgebnis(e)) return [];
  return e.reihen.flatMap((r) => r.flatMap((s) => s.w));
}

/** Text einer Seite: Stücke einer Reihe mit Tabulator getrennt (lässt sich so auch in eine Tabelle einfügen) */
export function seitenText(e: ScanSeite["ergebnis"]): string {
  if (!hatErgebnis(e)) return "";
  return e.reihen.map((r) => r.map((s) => s.w.map((w) => w[0]).join(" ")).join("\t")).join("\n");
}

export function prozent(wert: number | null | undefined): string {
  return wert == null ? "—" : `${Math.round(wert * 100)} %`;
}

/** „in 3 Tagen“, „morgen“, „heute“ */
export function bisDatum(iso: string): string {
  const ziel = new Date(iso);
  const tage = Math.round((new Date(ziel.getFullYear(), ziel.getMonth(), ziel.getDate()).getTime()
    - new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()).getTime()) / 86_400_000);
  if (tage <= 0) return "heute";
  if (tage === 1) return "morgen";
  return `in ${tage} Tagen`;
}

export async function inZwischenablage(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // ohne sicheren Kontext (z. B. Aufruf über die IP ohne vertrautes Zertifikat): über ein Textfeld kopieren
    const feld = document.createElement("textarea");
    feld.value = text;
    feld.style.position = "fixed";
    feld.style.opacity = "0";
    document.body.appendChild(feld);
    feld.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { ok = false; }
    feld.remove();
    return ok;
  }
}

export function dateiname(name: string): string {
  return name.replace(/\.[^.]+$/, "");
}
