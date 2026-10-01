/** Dialog und Menü auf Base UI (zugänglich: Fokusfalle, Escape, Rollen). */
import { Dialog as BaseDialog } from "@base-ui/react/dialog";
import { Menu as BaseMenu } from "@base-ui/react/menu";
import type { ReactNode } from "react";
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
          className="card fixed left-1/2 top-[12vh] z-50 -translate-x-1/2 max-h-[80vh] overflow-auto p-6 flex flex-col gap-4"
          style={{ width: `min(${breite}px, calc(100vw - 32px))` }}
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
          {fuss ? <div className="flex justify-end gap-2 flex-wrap">{fuss}</div> : null}
        </BaseDialog.Popup>
      </BaseDialog.Portal>
    </BaseDialog.Root>
  );
}

export type MenuEintrag = { text: ReactNode; onClick: () => void; gefaehrlich?: boolean; aus?: boolean; hinweis?: string };

export function Menue({ label, eintraege, ausloeser }: { label: string; eintraege: MenuEintrag[]; ausloeser?: ReactNode }) {
  return (
    <BaseMenu.Root>
      <BaseMenu.Trigger className="btn sec icon" aria-label={label}>
        {ausloeser ?? <Icon name="mehr" />}
      </BaseMenu.Trigger>
      <BaseMenu.Portal>
        <BaseMenu.Positioner side="bottom" align="end" sideOffset={6} className="z-50">
          <BaseMenu.Popup className="card min-w-[220px] p-1 flex flex-col outline-none">
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
