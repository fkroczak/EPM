/**
 * Maße in rem (Festlegung 09.10.2026): Die ganze Oberfläche wächst mit der Schriftgröße – mit der eingestellten unter
 * Mein Konto › Darstellung und mit der des Browsers bzw. Telefons. Größen im Code bleiben als px-Werte beim
 * Grundwert 16 px geschrieben (wie im Entwurf) und werden hier umgerechnet.
 */
export function rem(px: number): string {
  return `${+(px / 16).toFixed(4)}rem`;
}

/** Media-Query-Grenze in em (wie die rem-Grenzen in index.css: bezogen auf die Schriftgröße des Browsers) */
export function em(px: number): string {
  return `${+(px / 16).toFixed(4)}em`;
}
