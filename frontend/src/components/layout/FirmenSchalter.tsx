/**
 * Umschalter zwischen den Firmen unter dem Logo (Anforderung 11.10.2026: EPM für DSKM und Regeneration Clinic).
 * Sichtbar, wenn die Person in mehr als einer Firma Zugang hat. Die Wahl gilt für die Sitzung; danach zeigt das EPM nur
 * die Akten dieser Firma, neue Einträge vermerken sie, Rechte und Logo richten sich nach ihr.
 */
import { useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import type { Status } from "@/lib/typen";
import { Segmente, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";

export function useFirmaWechseln() {
  const { setStatus } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const melden = useHinweis();
  const [laeuft, setLaeuft] = useState(false);
  return {
    laeuft,
    wechseln: async (kuerzel: string) => {
      if (laeuft) return;
      setLaeuft(true);
      try {
        const s = await api<Status>("auth/firma/", { body: { firma: kuerzel } });
        // eine geöffnete Akte, ein Plan oder Scan gehört evtl. nur zur bisherigen Firma: zurück zur Liste
        const teile = pathname.split("/").filter(Boolean);
        const i = teile.findIndex((t) => /^\d+$/.test(t));
        if (i >= 0) navigate(`/${teile.slice(0, i).join("/")}`);
        queryClient.removeQueries();
        setStatus(s);
        const name = s.benutzer?.firmen?.find((f) => f.kuerzel === kuerzel)?.name ?? kuerzel;
        melden(`Du arbeitest jetzt für ${name}.`);
      } catch (e) {
        melden(e instanceof Error ? e.message : "Firma konnte nicht gewechselt werden.", "fehler");
      } finally {
        setLaeuft(false);
      }
    },
  };
}

/** ``schmal``: Leiste nur mit Symbolen – ein Knopf mit dem Kürzel, der zur nächsten Firma wechselt */
export function FirmenSchalter({ schmal, className }: { schmal?: boolean; className?: string }) {
  const ich = useIch();
  const { wechseln, laeuft } = useFirmaWechseln();
  const firmen = ich.firmen ?? [];
  if (firmen.length < 2) return null;
  const aktiv = firmen.find((f) => f.kuerzel === ich.firma) ?? firmen[0];
  if (schmal) {
    const naechste = firmen[(firmen.indexOf(aktiv) + 1) % firmen.length];
    return (
      <button type="button" className={cx("firma-kurz", className)} disabled={laeuft} data-testid="firma-kurz"
        title={`Firma: ${aktiv.name} – wechseln zu ${naechste.name}`} aria-label={`Firma ${aktiv.name}, wechseln zu ${naechste.name}`}
        onClick={() => void wechseln(naechste.kuerzel)}>
        {aktiv.kurzname}
      </button>
    );
  }
  return (
    <Segmente label="Firma" className={cx("firmen-schalter", className)} wert={aktiv.kuerzel}
      werte={firmen.map((f) => ({ wert: f.kuerzel, text: <span title={f.name}>{f.kurzname}</span> }))}
      onWahl={(k) => { if (k !== aktiv.kuerzel) void wechseln(k); }} />
  );
}
