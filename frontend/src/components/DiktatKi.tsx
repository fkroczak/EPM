/**
 * Diktat → gegliederter Bericht mit der lokalen KI (14.11.2026).
 *
 * „Mit KI gliedern“ legt eine eigene KI-Unterhaltung mit der Vorlage „Diktat als Brief gliedern“ an
 * (``POST ki/chats/diktat/``); der KI-Dienst schreibt den Entwurf wie jede Chat-Antwort (Vorrang, auch tagsüber).
 * Die Seite fragt alle 2 Sekunden nach und zeigt den Text schon beim Schreiben. Danach: Zahlen/Daten, die nicht im
 * Diktat stehen, und Zahlen/Daten des Diktats, die im Entwurf fehlen, sind markiert. In den Bericht kommt der
 * Entwurf erst mit „Entwurf in den Text übernehmen“ – wie die Abschrift selbst.
 */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Chip, Fehleranzeige, Knopf, Ladekreis, Meldung } from "@/components/ui/basis";

type Nachricht = { id: number; rolle: "nutzer" | "ki"; text: string; status: "wartet" | "laeuft" | "fertig" | "fehler";
  schritt: string; fehler: string; dauer_s: number | null;
  pruefung: { neue_werte?: string[]; fehlende_werte?: string[]; offene_stellen?: number } };
type Chat = { id: number; nachrichten: Nachricht[] };

function escape(t: string) {
  return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Antwort der KI („## Überschrift“, „- Punkt“, Absätze) → HTML für den Editor des Berichts */
export function entwurfAlsHtml(text: string): string {
  const aus: string[] = [];
  let absatz: string[] = [];
  let liste: string[] = [];
  const absatzEnde = () => { if (absatz.length) aus.push(`<p>${absatz.map(escape).join("<br>")}</p>`); absatz = []; };
  const listeEnde = () => { if (liste.length) aus.push(`<ul>${liste.map((x) => `<li>${escape(x)}</li>`).join("")}</ul>`); liste = []; };
  for (const roh of text.replace(/\r/g, "").split("\n")) {
    const z = roh.trim();
    const titel = /^#{1,6}\s+(.*)$/.exec(z);
    const punkt = /^[-•*]\s+(.*)$/.exec(z);
    if (!z) { absatzEnde(); listeEnde(); }
    else if (titel) { absatzEnde(); listeEnde(); aus.push(`<h3>${escape(titel[1].replace(/\*\*/g, ""))}</h3>`); }
    else if (punkt) { absatzEnde(); liste.push(punkt[1]); }
    else { listeEnde(); absatz.push(z.replace(/\*\*/g, "")); }
  }
  absatzEnde();
  listeEnde();
  return aus.join("");
}

export function DiktatKi({ diktatId, onUebernehmen, uebernimmt }: {
  diktatId: number;
  onUebernehmen: (html: string) => void;
  uebernimmt?: boolean;
}) {
  const [chatId, setChatId] = useState<number | null>(null);
  const starten = useMutation({
    mutationFn: () => api<Chat>("ki/chats/diktat/", { body: { diktat: diktatId } }),
    onSuccess: (c) => setChatId(c.id),
  });
  const chat = useQuery({
    queryKey: ["ki", "chats", chatId],
    queryFn: () => api<Chat>(`ki/chats/${chatId}/`, { hintergrund: true }),
    enabled: chatId !== null,
    refetchInterval: (q) => {
      const n = q.state.data?.nachrichten.at(-1);
      return !n || n.status === "wartet" || n.status === "laeuft" ? 2000 : false;
    },
  });
  const n = chat.data?.nachrichten.filter((x) => x.rolle === "ki").at(-1);

  if (chatId === null) {
    return (
      <div className="flex flex-col gap-1">
        <Knopf klein icon="stern" laedt={starten.isPending} onClick={() => starten.mutate()} data-testid="diktat-ki-gliedern"
          title="Die lokale KI macht aus der Abschrift einen gegliederten Entwurf (Überschriften, ohne Diktieranweisungen)">
          Mit KI gliedern
        </Knopf>
        <Fehleranzeige fehler={starten.error} />
      </div>
    );
  }
  const laeuft = !n || n.status === "wartet" || n.status === "laeuft";
  const neu = n?.pruefung?.neue_werte ?? [];
  const fehlt = n?.pruefung?.fehlende_werte ?? [];
  return (
    <div className="rounded-lg border border-rand bg-grund px-3 py-2.5 flex flex-col gap-2" data-testid="diktat-ki">
      <span className="text-[0.8125rem] font-medium">Entwurf der KI</span>
      {n?.status === "fehler" ? <Meldung art="fehler">Keine Antwort: {n.fehler}</Meldung> : (
        <div className="text-sm whitespace-pre-wrap" data-testid="diktat-ki-text">
          {n?.text}
          {laeuft ? <span className="inline-flex items-center gap-2 gedaempft ml-1.5 align-middle"><Ladekreis groesse={12} />
            {!n?.text ? (n?.status === "wartet" ? "wartet auf den KI-Dienst …" : `${n?.schritt || "KI schreibt"} …`) : null}</span> : null}
        </div>
      )}
      {n?.status === "fertig" ? (
        <>
          <div className="flex items-center gap-2 flex-wrap text-[0.75rem]">
            <Chip art="warn">KI-Vorschlag – bitte gegen die Abschrift prüfen</Chip>
            {neu.length ? <Chip art="fehler" title="Diese Zahlen oder Daten stehen nicht in der Abschrift (oder wurden dort als Wort diktiert)">
              Nicht im Diktat: {neu.join(", ")}</Chip> : null}
            {fehlt.length ? <Chip art="fehler" title="Diese Zahlen oder Daten aus der Abschrift fehlen im Entwurf">
              Fehlt im Entwurf: {fehlt.join(", ")}</Chip> : null}
            {n.pruefung?.offene_stellen ? <Chip art="warn">{n.pruefung.offene_stellen} offene Stelle(n) [?]</Chip> : null}
          </div>
          <div className="flex gap-2 flex-wrap">
            <Knopf klein variante="pri" icon="plus" laedt={uebernimmt} onClick={() => onUebernehmen(entwurfAlsHtml(n.text))}
              data-testid="diktat-ki-uebernehmen">Entwurf in den Text übernehmen</Knopf>
            <Knopf klein variante="geist" onClick={() => { setChatId(null); starten.reset(); }}>Verwerfen</Knopf>
          </div>
        </>
      ) : null}
      {n?.status === "fehler" ? <Knopf klein variante="geist" onClick={() => { setChatId(null); starten.reset(); }}>Schließen</Knopf> : null}
    </div>
  );
}
