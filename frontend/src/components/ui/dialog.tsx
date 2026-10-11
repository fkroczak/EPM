/** Dialog und Menü auf Base UI (zugänglich: Fokusfalle, Escape, Rollen). */
import { Dialog as BaseDialog } from "@base-ui/react/dialog";
import { Menu as BaseMenu } from "@base-ui/react/menu";
import type { ReactNode } from "react";
import { rem } from "@/lib/masse";
import { cx } from "./basis";
import { Icon } from "./icon";

export function Dialog({ offen, onOffen, titel, beschreibung, children, fuss, breite = 520 }: {
  offen: boolean;
  onOffen: (offen: boolean) => void;
  titel: ReactNode;
  beschreibung?: ReactNode;
  children?: ReactNode;
  fuss?: ReactNode;
  breite?: number;
}) {
  return (
    <BaseDialog.Root open={offen} onOpenChange={(o) => onOffen(o)}>
      <BaseDialog.Portal>
        <BaseDialog.Backdrop className="fixed inset-0 z-40 bg-black/35" />
        <BaseDialog.Popup
          className="card dialog-popup fixed left-1/2 top-3 sm:top-[12vh] z-50 -translate-x-1/2 max-h-[calc(100dvh-1.5rem-env(safe-area-inset-bottom))] sm:max-h-[80vh] overflow-auto p-4 sm:p-6 flex flex-col gap-4"
          style={{ width: `min(${rem(breite)}, calc(100vw - 1.25rem))` }}
          onKeyDown={(e) => {
            // Strg Enter (Mac: ⌘ Enter) speichert: löst den Hauptknopf unten rechts aus (Tastenkürzel, 08.10.2026)
            if (e.key !== "Enter" || !(e.ctrlKey || e.metaKey) || e.defaultPrevented) return;
            // nur für diesen Dialog, nicht für einen darin verschachtelten (der hat seinen eigenen Hauptknopf)
            if (!e.currentTarget.contains(e.target as Node)) return;
            const knoepfe = e.currentTarget.querySelectorAll<HTMLButtonElement>(".dialog-fuss .btn.pri:not(:disabled)");
            const knopf = knoepfe[knoepfe.length - 1];
            if (!knopf) return;
            e.preventDefault();
            e.stopPropagation();
            knopf.click();
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-col gap-1">
              <BaseDialog.Title className="m-0 text-lg font-semibold">{titel}</BaseDialog.Title>
              {beschreibung ? (
                <BaseDialog.Description className="m-0 text-sm gedaempft">{beschreibung}</BaseDialog.Description>
              ) : null}
            </div>
            <BaseDialog.Close className="btn geist icon" aria-label="Schließen">
              <Icon name="x" />
            </BaseDialog.Close>
          </div>
          {children}
          {fuss ? <div className="dialog-fuss flex justify-end gap-2 flex-wrap">{fuss}</div> : null}
        </BaseDialog.Popup>
      </BaseDialog.Portal>
    </BaseDialog.Root>
  );
}

export type MenuEintrag = { text: ReactNode; onClick: () => void; gefaehrlich?: boolean; aus?: boolean; hinweis?: string };

/** Menü hinter „⋯“; der Name erscheint zusätzlich als Tooltip (Bedienung für Pflegekräfte, 10.10.2026). */
export function Menue({ label, eintraege, ausloeser }: { label: string; eintraege: MenuEintrag[]; ausloeser?: ReactNode }) {
  return (
    <BaseMenu.Root>
      {/* mit eigenem Auslöser (Text) ein normaler kleiner Knopf, sonst „⋯“ */}
      <BaseMenu.Trigger className={ausloeser ? "btn sec klein" : "btn sec icon"} aria-label={ausloeser ? undefined : label} title={label}>
        {ausloeser ?? <Icon name="mehr" />}
      </BaseMenu.Trigger>
      <BaseMenu.Portal>
        <BaseMenu.Positioner side="bottom" align="end" sideOffset={6} className="z-50">
          <BaseMenu.Popup className="card min-w-[13.75rem] p-1 flex flex-col outline-none">
            {eintraege.map((e, i) => (
              <BaseMenu.Item
                key={i}
                disabled={e.aus}
                onClick={e.onClick}
                className={cx(
                  "flex flex-col items-start gap-0.5 rounded-md px-3 py-2 text-sm cursor-pointer outline-none",
                  "data-[highlighted]:bg-fein data-[disabled]:opacity-50 data-[disabled]:cursor-not-allowed",
                  e.gefaehrlich && "text-fehler",
                )}
              >
                <span>{e.text}</span>
                {e.hinweis ? <span className="text-xs gedaempft">{e.hinweis}</span> : null}
              </BaseMenu.Item>
            ))}
          </BaseMenu.Popup>
        </BaseMenu.Positioner>
      </BaseMenu.Portal>
    </BaseMenu.Root>
  );
}
