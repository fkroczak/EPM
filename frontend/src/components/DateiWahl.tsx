/** Datei auswählen wie sonst in EPM: Knopf „Datei wählen“, daneben der Name – statt des Eingabefelds des Browsers
 *  (das je nach Browser englisch beschriftet ist: „Choose File – No file chosen“). */
import { useRef } from "react";
import { Knopf } from "@/components/ui/basis";

export function DateiWahl({ id, datei, onDatei, accept, testid, label }: {
  id?: string; datei: File | null; onDatei: (f: File | null) => void; accept?: string; testid?: string; label: string;
}) {
  const eingabe = useRef<HTMLInputElement>(null);
  return (
    <div className="flex items-center gap-2.5 flex-wrap min-w-0">
      <Knopf klein icon="hochladen" onClick={() => eingabe.current?.click()}>{datei ? "Andere Datei" : "Datei wählen"}</Knopf>
      <span className="text-sm min-w-0 break-all">{datei ? datei.name : <span className="gedaempft">keine Datei gewählt</span>}</span>
      <input ref={eingabe} id={id} type="file" hidden aria-label={label} accept={accept} data-testid={testid}
        onChange={(e) => { onDatei(e.target.files?.[0] ?? null); e.target.value = ""; }} />
    </div>
  );
}
