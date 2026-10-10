/**
 * Fachbegriff mit Erklärung beim Draufzeigen (Rückfrage beantwortet am 10.10.2026): gepunktet unterstrichen, die
 * Erklärung erscheint bei Maus-Hover, beim Tastaturfokus und beim Antippen (Telefon, Tablet); Escape oder ein Tipp
 * daneben schließt sie. Für Screenreader hängt die Erklärung per ``aria-describedby`` am Begriff.
 *
 *   <Begriff name="bia">BIA</Begriff>              Erklärung aus lib/begriffe.ts
 *   <Begriff erklaerung="…">Sondertext</Begriff>   eigene Erklärung
 *
 * Technik: Popover von Base UI (Positionierung, Escape, Klick daneben). Kein Tooltip von Base UI, weil der sich auf
 * Touchgeräten nicht antippen lässt. Nicht in Knöpfe oder Links setzen (Knopf im Knopf) – dort den Text daneben stellen.
 */
import { useId, useState } from "react";
import type { ReactNode } from "react";
import { Popover } from "@base-ui/react/popover";
import { BEGRIFFE } from "@/lib/begriffe";
import type { BegriffSchluessel } from "@/lib/begriffe";
import { cx } from "./basis";

export function Begriff({ name, erklaerung, children, className }: {
  name?: BegriffSchluessel; erklaerung?: string; children: ReactNode; className?: string;
}) {
  const id = useId();
  const [offen, setOffen] = useState(false);
  const text = erklaerung ?? (name ? BEGRIFFE[name] : "");
  if (!text) return <>{children}</>;
  return (
    <Popover.Root open={offen} onOpenChange={setOffen}>
      <Popover.Trigger openOnHover delay={250} closeDelay={100} aria-describedby={`${id}-erklaerung`}
        className={cx("begriff", className)} data-testid="begriff"
        // Tastaturfokus öffnet; Fokus durch Antippen/Klick nicht – sonst schlösse der Klick gleich danach wieder
        onFocus={(e) => { if (e.currentTarget.matches(":focus-visible")) setOffen(true); }} onBlur={() => setOffen(false)}>
        {children}
      </Popover.Trigger>
      {/* immer im DOM, nur für Hilfsmittel – die sichtbare Blase unten ist für sie ausgeblendet */}
      <span id={`${id}-erklaerung`} className="sr-only">{text}</span>
      <Popover.Portal>
        <Popover.Positioner side="top" sideOffset={6} collisionPadding={8} className="z-[60]">
          <Popover.Popup role="tooltip" aria-hidden="true" initialFocus={false} finalFocus={false}
            className="begriff-blase" data-testid="begriff-erklaerung">
            {text}
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}
