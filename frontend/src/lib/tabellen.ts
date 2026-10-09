/**
 * Tabellen am Telefon (Wunsch 09.10.2026: „keine Felder ragen raus oder werden abgeschnitten“): Unter 768 px stehen die
 * Zellen einer Zeile als Raster untereinander (index.css, „.tabelle“ im Abschnitt Telefon) statt breiter als der
 * Bildschirm zu werden. Damit jede Zelle weiß, wozu sie gehört, schreibt diese Funktion die Spaltenüberschrift als
 * ``data-label`` an die Zelle; die erste beschriftete Zelle einer Zeile wird zum Titel der Zeile (``data-titel``).
 * Tabellen mit ``tabelle-fest`` bleiben Tabellen (sie scrollen in ihrer Karte).
 */
const TELEFON = "(max-width: 47.99em)"; // wie index.css (47.99rem): bezogen auf die Schriftgröße des Browsers

/** Überschrift je Spalte; bei mehrzeiligem Kopf die unterste Zelle, die die Spalte abdeckt (rowSpan und colSpan) */
function ueberschriften(tabelle: HTMLTableElement): string[] {
  const kopf = tabelle.tHead?.rows;
  if (!kopf || !kopf.length) return [];
  const namen: string[] = [];
  const belegt: number[] = []; // je Spalte: bis zu welcher Zeile (ausschließlich) eine Zelle von oben hineinragt
  Array.from(kopf).forEach((zeile, z) => {
    let spalte = 0;
    for (const th of Array.from(zeile.cells)) {
      while ((belegt[spalte] ?? 0) > z) spalte++;
      const text = (th.getAttribute("aria-label") ?? th.textContent ?? "").replace(/\s+/g, " ").trim();
      for (let i = 0; i < th.colSpan; i++, spalte++) {
        namen[spalte] = text;
        belegt[spalte] = z + Math.max(1, th.rowSpan);
      }
    }
  });
  return namen;
}

function setzen(el: HTMLElement, name: string, wert: string | null) {
  if (el.getAttribute(name) === wert) return;
  if (wert === null) el.removeAttribute(name); else el.setAttribute(name, wert);
}

function beschriften() {
  for (const tabelle of Array.from(document.querySelectorAll<HTMLTableElement>("table.tabelle:not(.tabelle-fest)"))) {
    const namen = ueberschriften(tabelle);
    for (const koerper of Array.from(tabelle.tBodies)) {
      for (const zeile of Array.from(koerper.rows)) {
        let spalte = 0;
        let titel = false;
        for (const zelle of Array.from(zeile.cells)) {
          const name = zelle.colSpan === 1 ? namen[spalte] || null : null;
          setzen(zelle, "data-label", name);
          setzen(zelle, "data-titel", name && !titel ? "" : null);
          if (name) titel = true;
          spalte += zelle.colSpan;
        }
      }
    }
  }
}

/** Einmal beim Start: beschriftet alle Tabellen und danach jede, die React neu zeichnet (nur am Telefon). */
export function tabellenFuerTelefon() {
  if (typeof window === "undefined" || !window.matchMedia || typeof MutationObserver === "undefined") return;
  const telefon = window.matchMedia(TELEFON);
  let geplant = false;
  const planen = () => {
    if (geplant || !telefon.matches) return;
    geplant = true;
    window.requestAnimationFrame(() => { geplant = false; beschriften(); });
  };
  new MutationObserver(planen).observe(document.body, { childList: true, characterData: true, subtree: true });
  telefon.addEventListener("change", planen);
  planen();
}
