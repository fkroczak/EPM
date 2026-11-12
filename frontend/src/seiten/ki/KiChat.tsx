/**
 * KI (Experimentell) › Chat (12.11.2026): Texte mit der lokalen KI medizinisch formulieren, prüfen, kürzen … – mit den
 * Promptvorlagen aus Administration › Vorlagen › KI-Prompts. Jede Person sieht nur ihre eigenen Unterhaltungen.
 * Die Antwort schreibt der KI-Dienst (Warteschlange); die Seite fragt alle 3 Sekunden nach, solange sie wartet.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, api } from "@/lib/api";
import { zeitpunkt } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import type { KiStand } from "@/lib/ki";
import { Auswahl, Chip, Fehleranzeige, Karte, Knopf, Ladekreis, Leer, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { useHinweis } from "@/components/ui/hinweise";

export type KiPromptvorlage = { id: number; name: string; beschreibung: string; anweisung: string; temperatur: string;
  aktiv: boolean; reihenfolge: number; mitgeliefert: boolean; geaendert_am: string; geaendert_von_name: string | null };
type Nachricht = { id: number; rolle: "nutzer" | "ki"; text: string; status: "wartet" | "laeuft" | "fertig" | "fehler";
  vorlage_name: string; pruefung: { neue_werte?: string[]; offene_stellen?: number; ok?: boolean }; fehler: string;
  modell: string; dauer_s: number | null; erstellt_am: string };
type ChatKurz = { id: number; titel: string; vorlage: number | null; vorlage_name: string | null; aktualisiert_am: string; wartet: boolean };
type ChatVoll = ChatKurz & { nachrichten: Nachricht[]; aufbewahrung_tage: number };

export function KiChat() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const { darf } = useAuth();
  const [aktiv, setAktiv] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [vorlage, setVorlage] = useState<string>("");
  const verlaufRef = useRef<HTMLDivElement>(null);
  const stand = useQuery({ queryKey: ["ki", "stand"], queryFn: () => api<KiStand>("ki/stand/", { hintergrund: true }), refetchInterval: 30_000 });
  const vorlagen = useQuery({ queryKey: ["ki", "vorlagen"], queryFn: () => api<KiPromptvorlage[]>("ki/vorlagen/") });
  const liste = useQuery({ queryKey: ["ki", "chats"], queryFn: () => api<ChatKurz[]>("ki/chats/") });
  const chat = useQuery({
    queryKey: ["ki", "chat", aktiv], enabled: aktiv !== null,
    queryFn: () => api<ChatVoll>(`ki/chats/${aktiv}/`, { hintergrund: true }),
    refetchInterval: (q) => (q.state.data?.nachrichten.some((n) => n.status === "wartet" || n.status === "laeuft") ? 3000 : false),
  });
  // Standardvorlage: die erste („Medizinisch formulieren“); bei einem bestehenden Chat dessen Vorlage
  useEffect(() => {
    if (!vorlage && vorlagen.data?.length) setVorlage(String(vorlagen.data[0].id));
  }, [vorlagen.data, vorlage]);
  useEffect(() => { if (chat.data?.vorlage) setVorlage(String(chat.data.vorlage)); }, [chat.data?.id]);
  const anzahl = chat.data?.nachrichten.length ?? 0;
  const wartet = !!chat.data?.nachrichten.some((n) => n.status === "wartet" || n.status === "laeuft");
  // nur im Verlauf nach unten scrollen – die Seite und das Eingabefeld bleiben stehen
  useEffect(() => { const v = verlaufRef.current; if (v) v.scrollTop = v.scrollHeight; }, [anzahl, wartet, aktiv]);
  useEffect(() => { if (!wartet) void qc.invalidateQueries({ queryKey: ["ki", "chats"] }); }, [wartet, qc]);

  const senden = useMutation({
    mutationFn: async () => {
      let id = aktiv;
      if (id === null) id = (await api<ChatVoll>("ki/chats/", { body: { vorlage: vorlage || null } })).id;
      return api<ChatVoll>(`ki/chats/${id}/nachricht/`, { body: { text, vorlage: vorlage || null } });
    },
    onSuccess: (c) => {
      setText(""); setAktiv(c.id);
      qc.setQueryData(["ki", "chat", c.id], c);
      void qc.invalidateQueries({ queryKey: ["ki", "chats"] });
    },
  });
  const loeschen = useMutation({
    mutationFn: (id: number) => api(`ki/chats/${id}/`, { method: "DELETE" }),
    onSuccess: () => { setAktiv(null); void qc.invalidateQueries({ queryKey: ["ki", "chats"] }); melden("Chat gelöscht."); },
  });
  const gewaehlt = vorlagen.data?.find((v) => String(v.id) === vorlage);
  const fehler = senden.error instanceof ApiFehler ? senden.error.felder.text || senden.error.message : senden.error ? String(senden.error) : "";
  const darfSchreiben = darf("ki_berichte");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[16rem_minmax(0,1fr)] gap-4 items-start" data-testid="ki-chat">
      <Karte className="flex flex-col gap-2 p-3 lg:max-h-[calc(100dvh-14rem)] overflow-y-auto">
        <Knopf variante="pri" icon="plus" onClick={() => { setAktiv(null); setText(""); senden.reset(); }}>Neuer Chat</Knopf>
        <span className="text-xs gedaempft">Nur Sie sehen Ihre Chats.</span>
        <ul className="m-0 p-0 list-none flex flex-col gap-0.5" aria-label="Meine Chats">
          {(liste.data ?? []).map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => setAktiv(c.id)} aria-current={c.id === aktiv || undefined}
                className={cx("w-full text-left rounded-md px-2 py-1.5 hover:bg-fein flex flex-col", c.id === aktiv && "bg-akzent-weich")}>
                <span className="text-sm truncate">{c.titel || "Neuer Chat"}</span>
                <span className="text-[0.75rem] gedaempft">{zeitpunkt(c.aktualisiert_am)}{c.wartet ? " · wartet" : ""}</span>
              </button>
            </li>
          ))}
        </ul>
        {liste.data && !liste.data.length ? <span className="text-sm gedaempft">Noch keine Chats.</span> : null}
      </Karte>

      <Karte className="flex flex-col gap-3 p-4 min-w-0 h-[calc(100dvh-14rem)] min-h-[30rem]">
        <Meldung art="info" className="text-[0.8125rem] shrink-0">
          Lokale KI, offline auf dem Server. Sie formuliert nur, was Sie eingeben – <strong>jede Antwort vor der Verwendung prüfen</strong>.
          Zahlen oder Daten, die nicht in Ihrem Text stehen, werden markiert.
          {chat.data ? ` Chats werden nach ${chat.data.aufbewahrung_tage} Tagen ohne Änderung gelöscht.` : ""}
        </Meldung>
        <div ref={verlaufRef} className="flex flex-col gap-3 flex-1 min-h-0 overflow-y-auto pr-1" aria-live="polite" data-testid="ki-chat-verlauf">
          {aktiv === null ? <Leer>Text unten eingeben, Vorlage wählen und senden.</Leer> : null}
          {chat.data?.nachrichten.map((n) => <Blase key={n.id} n={n} />)}
          {wartet ? <WarteHinweis stand={stand.data} /> : null}
        </div>
        <Fehleranzeige fehler={chat.error} />
        <div className="flex flex-col gap-2 border-t border-rand pt-3 shrink-0">
          <div className="flex items-center gap-2.5 flex-wrap">
            <label htmlFor="ki-vorlage" className="text-sm font-medium">Vorlage</label>
            <Auswahl id="ki-vorlage" className="w-[18rem]" value={vorlage} onChange={(e) => setVorlage(e.target.value)}>
              {(vorlagen.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </Auswahl>
            {gewaehlt?.beschreibung ? <span className="text-[0.8125rem] gedaempft">{gewaehlt.beschreibung}</span> : null}
          </div>
          <Textfeld aria-label="Nachricht an die KI" rows={4} value={text} maxLength={8000} disabled={!darfSchreiben}
            placeholder="z. B. Stichpunkte: Pat. seit 3 Tagen Fieber 38,5, Katheter gerötet, Abstrich abgenommen"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && text.trim() && !wartet) senden.mutate(); }} />
          <div className="flex items-center gap-3 flex-wrap">
            <Knopf variante="pri" icon="sprechblase" laedt={senden.isPending} disabled={!text.trim() || wartet || !darfSchreiben}
              onClick={() => senden.mutate()}>Senden</Knopf>
            <span className="text-xs gedaempft">Strg + Enter · {text.length} / 8000 Zeichen</span>
            {aktiv !== null ? <Knopf klein variante="geist" className="ml-auto" laedt={loeschen.isPending}
              onClick={() => { if (window.confirm("Diesen Chat löschen?")) loeschen.mutate(aktiv); }}>Chat löschen</Knopf> : null}
          </div>
          {!darfSchreiben ? <Meldung art="warn">Zum Chatten fehlt das Recht „KI (Experimentell): Berichtsentwurf anfordern“.</Meldung> : null}
          {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
        </div>
      </Karte>
    </div>
  );
}

/** Warum es dauert: Modell schläft/lädt, Pause (Sicherung), Dienst aus. */
function WarteHinweis({ stand }: { stand?: KiStand }) {
  const d = stand?.dienst;
  const e = d?.entscheidung;
  const text = !d || !d.laeuft ? "Der KI-Dienst meldet sich gerade nicht – die Antwort kommt, sobald er wieder läuft."
    : e?.modus === "aus" ? "Die KI ist ausgeschaltet (Administration › KI) – es kommt keine Antwort."
    : d.modell.eingerichtet && !d.modell.bereit ? "Das KI-Modell wird gerade geladen (tagsüber schläft es, wenn eine Weile niemand die KI nutzt). Das dauert meist 1–2 Minuten."
    : e?.modus === "pause" ? `Pause${e.grund ? ` – ${e.grund}` : ""}. Die Antwort kommt danach.`
    : "";
  return text ? <span className="text-[0.8125rem] gedaempft self-start" data-testid="ki-chat-warten">{text} Nach 15 Minuten ohne Antwort wird abgebrochen.</span> : null;
}

function Blase({ n }: { n: Nachricht }) {
  const melden = useHinweis();
  const nutzer = n.rolle === "nutzer";
  const neu = n.pruefung?.neue_werte ?? [];
  return (
    <div className={cx("flex flex-col gap-1 max-w-[52rem]", nutzer ? "self-end items-end" : "self-start")} data-testid={`ki-nachricht-${n.rolle}`}>
      <span className="text-[0.75rem] gedaempft">{nutzer ? "Sie" : `KI${n.vorlage_name ? ` · ${n.vorlage_name}` : ""}`}</span>
      <div className={cx("rounded-lg px-3 py-2 text-sm whitespace-pre-wrap", nutzer ? "bg-akzent-weich" : "bg-fein")}>
        {n.status === "wartet" || n.status === "laeuft"
          ? <span className="inline-flex items-center gap-2 gedaempft"><Ladekreis />{n.status === "wartet" ? "wartet auf den KI-Dienst …" : "KI schreibt …"}</span>
          : n.status === "fehler" ? <span className="fehlertext">Keine Antwort: {n.fehler}</span>
          : n.text}
      </div>
      {!nutzer && n.status === "fertig" ? (
        <div className="flex items-center gap-2 flex-wrap text-[0.75rem]">
          <Chip art="warn">KI-Vorschlag – bitte prüfen</Chip>
          {neu.length ? <Chip art="fehler" title="Diese Zahlen oder Daten stehen nicht in Ihrem Text">Nicht in Ihrer Eingabe: {neu.join(", ")}</Chip> : null}
          {n.pruefung?.offene_stellen ? <Chip art="warn">{n.pruefung.offene_stellen} offene Stelle(n) [?]</Chip> : null}
          {n.dauer_s ? <span className="gedaempft">{Math.round(n.dauer_s)} s</span> : null}
          <Knopf klein variante="geist" icon="kopieren" onClick={() => void navigator.clipboard.writeText(n.text).then(() => melden("In die Zwischenablage kopiert."))}>Kopieren</Knopf>
        </div>
      ) : null}
    </div>
  );
}
