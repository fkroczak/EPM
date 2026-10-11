/**
 * Schalter „Technische Verwaltung“ (Wunsch 11.10.2026): Django-Admin (/verwaltung/) und die API-Ansicht im Browser sind
 * standardmäßig aus. Ein Admin schaltet sie für 1 oder 8 Stunden ein; danach sind sie von selbst wieder aus. Jede
 * Änderung steht im Audit-Log. Legt die Server-Konfiguration sie fest, gilt der Schalter nicht.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { zeitpunkt } from "@/lib/format";
import { Chip, Karte, KartenKopf, Knopf, Meldung } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";

type Stand = { an: boolean; bis: string | null; django_admin: boolean; api_ansicht: boolean;
  fest: { django_admin: boolean | null; api_ansicht: boolean | null } };

export function TechnikKarte() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const stand = useQuery({ queryKey: ["system", "technik"], queryFn: () => api<Stand>("system/technik/"), refetchInterval: 60_000 });
  const schalten = useMutation({
    mutationFn: (stunden: number) => api<Stand>("system/technik/", { method: "PUT", body: { stunden } }),
    onSuccess: (s) => {
      qc.setQueryData(["system", "technik"], s);
      melden(s.an ? `Technische Verwaltung an bis ${zeitpunkt(s.bis!)}.` : "Technische Verwaltung ausgeschaltet.");
    },
  });
  const s = stand.data;
  const fest = s && (s.fest.django_admin !== null || s.fest.api_ansicht !== null);
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="technik-karte">
      <KartenKopf titel="Technische Verwaltung" unter="Django-Admin und API-Ansicht im Browser – nur zur Fehlersuche. Danach schaltet EPM sie von selbst aus."
        rechts={s ? <Chip art={s.django_admin || s.api_ansicht ? "warn" : "ok"}>{s.django_admin || s.api_ansicht ? "an" : "aus"}</Chip> : null} />
      {s?.an && s.bis ? <span className="text-sm">An bis <strong>{zeitpunkt(s.bis)}</strong>.{" "}
        {s.django_admin ? <a href="/verwaltung/" target="_blank" rel="noopener">Django-Admin öffnen</a> : null}</span> : null}
      {fest ? <Meldung art="warn">Die Server-Konfiguration legt fest: Django-Admin {s!.django_admin ? "an" : "aus"}, API-Ansicht {s!.api_ansicht ? "an" : "aus"}
        (EPM_DJANGO_ADMIN / EPM_API_BROWSABLE in backend.env). Der Schalter wirkt dann nicht.</Meldung> : null}
      <div className="flex gap-2 flex-wrap">
        <Knopf laedt={schalten.isPending && schalten.variables === 1} onClick={() => schalten.mutate(1)} data-testid="technik-1h">Für 1 Stunde einschalten</Knopf>
        <Knopf laedt={schalten.isPending && schalten.variables === 8} onClick={() => schalten.mutate(8)}>Für 8 Stunden</Knopf>
        {s?.an ? <Knopf variante="pri" laedt={schalten.isPending && schalten.variables === 0} onClick={() => schalten.mutate(0)} data-testid="technik-aus">Jetzt ausschalten</Knopf> : null}
      </div>
    </Karte>
  );
}
