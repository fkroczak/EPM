/**
 * KI (Experimentell) › Chat (12.11.2026): Texte mit der lokalen KI medizinisch formulieren, prüfen, kürzen … – mit den
 * Promptvorlagen aus Administration › Vorlagen › KI-Prompts. Jede Person sieht nur ihre eigenen Unterhaltungen.
 * Die Antwort schreibt der KI-Dienst (Warteschlange); die Seite fragt alle 3 Sekunden nach, solange sie wartet.
 * Dokumente (12.11.2026): hochladen oder aus einer Akte wählen, ohne Seitengrenze – der KI-Dienst erkennt den Text
 * und liest lange Unterlagen Teil für Teil.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiFehler, abfrage, alle, api } from "@/lib/api";
import { datum, nummer, zeitpunkt } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import type { KiStand } from "@/lib/ki";
import type { Dokument, PatientZeile } from "@/lib/typen";
import { Auswahl, Chip, Fehleranzeige, Karte, Knopf, Ladekreis, Leer, Meldung, Textfeld, cx } from "@/components/ui/basis";
import { Dialog } from "@/components/ui/dialog";
import { useHinweis } from "@/components/ui/hinweise";
import { Icon } from "@/components/ui/icon";
import { PatientWahl } from "@/components/PatientWahl";

export type KiPromptvorlage = { id: number; name: string; beschreibung: string; anweisung: string; temperatur: string;
  aktiv: boolean; reihenfolge: number; mitgeliefert: boolean; geaendert_am: string; geaendert_von_name: string | null };
type Anhang = { id: number; herkunft: "upload" | "akte"; name: string; groesse: number; seiten: number; seiten_fertig: number;
  status: "wartet" | "fertig" | "fehler"; fehler: string; dokument: number | null; patient: number | null; patient_nummer: number | null };
type Nachricht = { id: number; rolle: "nutzer" | "ki"; text: string; status: "wartet" | "laeuft" | "fertig" | "fehler";
  schritt: string; anhaenge: Anhang[]; vorlage_name: string; pruefung: { neue_werte?: string[]; offene_stellen?: number; ok?: boolean }; fehler: string;
  modell: string; dauer_s: number | null; erstellt_am: string };
type ChatKurz = { id: number; titel: string; vorlage: number | null; vorlage_name: string | null; aktualisiert_am: string; wartet: boolean };
type ChatVoll = ChatKurz & { nachrichten: Nachricht[]; aufbewahrung_tage: number };
/** Dokument aus einer Akte, zum Anhängen gewählt */
type AktenDok = { id: number; titel: string; patient: string };
const MAX_ZEICHEN = 100000;
const LESBAR = ["application/pdf", "image/jpeg", "image/png", "image/tiff", "image/webp", "image/bmp", "image/heic", "image/heif"];
const DATEITYPEN = ".pdf,.jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp,.heic,.heif,application/pdf,image/*";

export function KiChat() {
  const qc = useQueryClient();
  const melden = useHinweis();
  const { darf } = useAuth();
  const [aktiv, setAktiv] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [vorlage, setVorlage] = useState<string>("");
  const [dateien, setDateien] = useState<File[]>([]);
  const [aktenDoks, setAktenDoks] = useState<AktenDok[]>([]);
  const [akteOffen, setAkteOffen] = useState(false);
  const dateiRef = useRef<HTMLInputElement>(null);
  const anhaenge = dateien.length + aktenDoks.length;
  const verlaufRef = useRef<HTMLDivElement>(null);
  const stand = useQuery({ queryKey: ["ki", "stand"], queryFn: () => api<KiStand>("ki/stand/", { hintergrund: true }), refetchInterval: 30_000 });
  const vorlagen = useQuery({ queryKey: ["ki", "vorlagen"], queryFn: () => api<KiPromptvorlage[]>("ki/vorlagen/") });
  const liste = useQuery({ queryKey: ["ki", "chats"], queryFn: () => api<ChatKurz[]>("ki/chats/") });
  const chat = useQuery({
    queryKey: ["ki", "chat", aktiv], enabled: aktiv !== null,
    queryFn: () => api<ChatVoll>(`ki/chats/${aktiv}/`, { hintergrund: true }),
    // schreibt die KI gerade: alle 1,5 s (Text erscheint Stück für Stück), wartet sie: alle 3 s
    refetchInterval: (q) => (q.state.data?.nachrichten.some((n) => n.status === "laeuft") ? 1500
      : q.state.data?.nachrichten.some((n) => n.status === "wartet") ? 3000 : false),
  });
  // Standardvorlage: die erste („Medizinisch formulieren“); bei einem bestehenden Chat dessen Vorlage
  useEffect(() => {
    if (!vorlage && vorlagen.data?.length) setVorlage(String(vorlagen.data[0].id));
  }, [vorlagen.data, vorlage]);
  useEffect(() => { if (chat.data?.vorlage) setVorlage(String(chat.data.vorlage)); }, [chat.data?.id]);
  const anzahl = chat.data?.nachrichten.length ?? 0;
  const wartet = !!chat.data?.nachrichten.some((n) => n.status === "wartet" || n.status === "laeuft");
  // nur im Verlauf nach unten scrollen – die Seite und das Eingabefeld bleiben stehen
  const laenge = chat.data?.nachrichten.at(-1)?.text.length ?? 0;
  useEffect(() => { const v = verlaufRef.current; if (v) v.scrollTop = v.scrollHeight; }, [anzahl, wartet, aktiv, laenge]);
  useEffect(() => { if (!wartet) void qc.invalidateQueries({ queryKey: ["ki", "chats"] }); }, [wartet, qc]);

  const senden = useMutation({
    mutationFn: async () => {
      let id = aktiv;
      if (id === null) id = (await api<ChatVoll>("ki/chats/", { body: { vorlage: vorlage || null } })).id;
      if (!anhaenge) return api<ChatVoll>(`ki/chats/${id}/nachricht/`, { body: { text, vorlage: vorlage || null } });
      const form = new FormData();
      form.append("text", text);
      form.append("vorlage", vorlage);
      dateien.forEach((d) => form.append("dateien", d));
      aktenDoks.forEach((d) => form.append("dokumente", String(d.id)));
      return api<ChatVoll>(`ki/chats/${id}/nachricht/`, { form });
    },
    onSuccess: (c) => {
      setText(""); setDateien([]); setAktenDoks([]); setAktiv(c.id);
      qc.setQueryData(["ki", "chat", c.id], c);
      void qc.invalidateQueries({ queryKey: ["ki", "chats"] });
    },
  });
  const loeschen = useMutation({
    mutationFn: (id: number) => api(`ki/chats/${id}/`, { method: "DELETE" }),
    onSuccess: () => { setAktiv(null); void qc.invalidateQueries({ queryKey: ["ki", "chats"] }); melden("Chat gelöscht."); },
  });
  const gewaehlt = vorlagen.data?.find((v) => String(v.id) === vorlage);
  const fehler = senden.error instanceof ApiFehler
    ? senden.error.felder.text || senden.error.felder.dateien || senden.error.felder.dokumente || senden.error.message
    : senden.error ? String(senden.error) : "";
  const darfSchreiben = darf("ki_berichte");
  const sendbar = (!!text.trim() || anhaenge > 0) && !wartet && darfSchreiben;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[16rem_minmax(0,1fr)] gap-4 items-start" data-testid="ki-chat">
      <Karte className="flex flex-col gap-2 p-3 lg:max-h-[calc(100dvh-19rem)] overflow-y-auto">
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

      <Karte className="flex flex-col gap-3 p-4 min-w-0 h-[calc(100dvh-19rem)] min-h-[26rem]">
        <Meldung art="info" className="text-[0.8125rem] shrink-0">
          Lokale KI, offline auf dem Server. Sie arbeitet nur mit dem, was Sie eingeben oder anhängen – <strong>jede Antwort vor der Verwendung prüfen</strong>.
          Zahlen oder Daten, die weder in Ihrem Text noch in den Dokumenten stehen, werden markiert. Lange Dokumente liest sie Teil für Teil – das dauert.
          {chat.data ? ` Chats werden nach ${chat.data.aufbewahrung_tage} Tagen ohne Änderung gelöscht.` : ""}
        </Meldung>
        <div ref={verlaufRef} className="flex flex-col gap-3 flex-1 min-h-0 overflow-y-auto pr-1" aria-live="polite" data-testid="ki-chat-verlauf">
          {aktiv === null ? <Leer>Text unten eingeben oder Dokumente anhängen, Vorlage wählen und senden.</Leer> : null}
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
          <Textfeld aria-label="Nachricht an die KI" rows={4} value={text} maxLength={MAX_ZEICHEN} disabled={!darfSchreiben}
            placeholder="z. B. Stichpunkte: Pat. seit 3 Tagen Fieber 38,5, Katheter gerötet, Abstrich abgenommen – oder ein Dokument anhängen und fragen: „Welche Laborwerte sind auffällig?“"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && sendbar) senden.mutate(); }} />
          {anhaenge ? (
            <ul className="m-0 p-0 list-none flex flex-wrap gap-1.5" aria-label="Anhänge" data-testid="ki-chat-anhaenge-neu">
              {dateien.map((d, i) => (
                <li key={`d${i}`}><AnhangChip name={d.name} zusatz={groesse(d.size)} onWeg={() => setDateien(dateien.filter((_, j) => j !== i))} /></li>))}
              {aktenDoks.map((d) => (
                <li key={`a${d.id}`}><AnhangChip name={d.titel} zusatz={d.patient} onWeg={() => setAktenDoks(aktenDoks.filter((x) => x.id !== d.id))} /></li>))}
            </ul>
          ) : null}
          <div className="flex items-center gap-3 flex-wrap">
            <Knopf variante="pri" icon="sprechblase" laedt={senden.isPending} disabled={!sendbar}
              onClick={() => senden.mutate()}>Senden</Knopf>
            <input ref={dateiRef} type="file" multiple accept={DATEITYPEN} className="hidden" data-testid="ki-chat-datei"
              onChange={(e) => { setDateien([...dateien, ...Array.from(e.target.files ?? [])]); e.target.value = ""; }} />
            <Knopf klein icon="hochladen" disabled={!darfSchreiben || wartet} onClick={() => dateiRef.current?.click()}>Datei anhängen</Knopf>
            <Knopf klein icon="dokument" disabled={!darfSchreiben || wartet} onClick={() => setAkteOffen(true)}>Aus Akte</Knopf>
            <span className="text-xs gedaempft">Strg + Enter · {text.length.toLocaleString("de-DE")} / {MAX_ZEICHEN.toLocaleString("de-DE")} Zeichen</span>
            {aktiv !== null ? <Knopf klein variante="geist" className="ml-auto" laedt={loeschen.isPending}
              onClick={() => { if (window.confirm("Diesen Chat löschen?")) loeschen.mutate(aktiv); }}>Chat löschen</Knopf> : null}
          </div>
          {!darfSchreiben ? <Meldung art="warn">Zum Chatten fehlt das Recht „KI (Experimentell): Berichtsentwurf anfordern“.</Meldung> : null}
          {fehler ? <Meldung art="fehler">{fehler}</Meldung> : null}
        </div>
      </Karte>
      <AktenWahl offen={akteOffen} onOffen={setAkteOffen} gewaehlt={aktenDoks}
        onWahl={(d) => setAktenDoks(aktenDoks.some((x) => x.id === d.id) ? aktenDoks.filter((x) => x.id !== d.id) : [...aktenDoks, d])} />
    </div>
  );
}

function groesse(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toLocaleString("de-DE", { maximumFractionDigits: 1 })} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function AnhangChip({ name, zusatz, onWeg }: { name: string; zusatz?: string; onWeg?: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-rand bg-fein px-2 py-1 text-[0.8125rem] max-w-[22rem]">
      <Icon name="dokument" groesse={14} />
      <span className="truncate">{name}</span>
      {zusatz ? <span className="gedaempft whitespace-nowrap">{zusatz}</span> : null}
      {onWeg ? <button type="button" className="gedaempft hover:text-text" aria-label={`${name} entfernen`} onClick={onWeg}><Icon name="x" groesse={14} /></button> : null}
    </span>
  );
}

/** Dokumente aus einer Akte wählen: Patient suchen, dann Dokumente anhaken (mehrere, auch aus mehreren Akten). */
function AktenWahl({ offen, onOffen, gewaehlt, onWahl }: { offen: boolean; onOffen: (o: boolean) => void;
  gewaehlt: AktenDok[]; onWahl: (d: AktenDok) => void }) {
  const [patient, setPatient] = useState<PatientZeile | null>(null);
  const doks = useQuery({
    queryKey: ["dokumente", "ki-chat", patient?.id],
    queryFn: () => alle<Dokument>(`dokumente/${abfrage({ patient: patient!.id, ausgeblendet: "false" })}`),
    enabled: offen && !!patient,
  });
  const lesbar = (doks.data ?? []).filter((d) => LESBAR.includes(d.mime));
  const name = patient ? `${patient.nachname}, ${patient.vorname} (${nummer(patient.nummer)})` : "";
  return (
    <Dialog offen={offen} onOffen={onOffen} titel="Dokumente aus der Akte anhängen" breite={640}
      beschreibung="Die KI liest den Text der gewählten Dokumente (schon erkannter Text wird übernommen). Ihr Chat bleibt nur für Sie sichtbar; der Zugriff wird im Protokoll der Akte vermerkt."
      fuss={<Knopf variante="pri" onClick={() => onOffen(false)}>Fertig{gewaehlt.length ? ` (${gewaehlt.length} gewählt)` : ""}</Knopf>}>
      <div className="flex flex-col gap-3" data-testid="ki-chat-aktenwahl">
        <PatientWahl id="ki-chat-patient" wert={patient} onWahl={setPatient} />
        {patient && doks.isLoading ? <Ladekreis /> : null}
        {patient && doks.data && !lesbar.length ? <Leer>Keine lesbaren Dokumente (PDF oder Bild) in dieser Akte.</Leer> : null}
        {lesbar.length ? (
          <ul className="m-0 p-0 list-none flex flex-col gap-0.5 max-h-[22rem] overflow-y-auto">
            {lesbar.map((d) => {
              const an = gewaehlt.some((x) => x.id === d.id);
              return (
                <li key={d.id}>
                  <label className="flex items-center gap-2.5 rounded-md px-2 py-1.5 hover:bg-fein cursor-pointer text-sm">
                    <input type="checkbox" checked={an} onChange={() => onWahl({ id: d.id, titel: d.titel, patient: name })} />
                    <span className="min-w-0 grow truncate">{d.titel}</span>
                    <span className="gedaempft whitespace-nowrap">{d.typ_name ? `${d.typ_name} · ` : ""}{d.datum ? datum(d.datum) : ""}</span>
                  </label>
                </li>);
            })}
          </ul>
        ) : null}
      </div>
    </Dialog>
  );
}

/** Warum es dauert: Modell schläft/lädt, Pause (Sicherung), Dienst aus. */
function WarteHinweis({ stand }: { stand?: KiStand }) {
  const d = stand?.dienst;
  const e = d?.entscheidung;
  const text = !d || !d.laeuft ? "Der KI-Dienst meldet sich gerade nicht – die Antwort kommt, sobald er wieder läuft."
    : e?.modus === "aus" ? "Die KI ist ausgeschaltet (Administration › KI) – es kommt keine Antwort."
    : d.modell.eingerichtet && !d.modell.bereit ? "Das KI-Modell wird gerade geladen (nach einem Neustart oder Modellwechsel). Das dauert meist 1–2 Minuten."
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
      {n.anhaenge?.length ? (
        <ul className="m-0 p-0 list-none flex flex-wrap gap-1.5 justify-end" aria-label="Anhänge">
          {n.anhaenge.map((a) => (
            <li key={a.id}><AnhangChip name={a.name} zusatz={[
              a.patient_nummer ? `Akte ${nummer(a.patient_nummer)}` : "",
              a.status === "fertig" ? (a.seiten ? `${a.seiten} S.` : "gelesen") : a.status === "fehler" ? "nicht lesbar" : a.seiten_fertig ? `${a.seiten_fertig} S. gelesen …` : "wartet",
            ].filter(Boolean).join(" · ")} /></li>))}
        </ul>
      ) : null}
      {nutzer && !n.text ? null : (
      <div className={cx("rounded-lg px-3 py-2 text-sm whitespace-pre-wrap", nutzer ? "bg-akzent-weich" : "bg-fein")}>
        {n.status === "laeuft" && n.text
          ? <>{n.text}<span className="inline-flex items-center gap-1.5 gedaempft ml-1.5 align-middle"><Ladekreis groesse={12} /></span></>
          : n.status === "wartet" || n.status === "laeuft"
          ? <span className="inline-flex items-center gap-2 gedaempft"><Ladekreis />{n.status === "wartet" ? "wartet auf den KI-Dienst …" : n.schritt ? `${n.schritt} …` : "KI schreibt …"}</span>
          : n.status === "fehler" ? <span className="fehlertext">Keine Antwort: {n.fehler}</span>
          : n.text}
      </div>)}
      {!nutzer && n.status === "fertig" ? (
        <div className="flex items-center gap-2 flex-wrap text-[0.75rem]">
          <Chip art="warn">KI-Vorschlag – bitte prüfen</Chip>
          {neu.length ? <Chip art="fehler" title="Diese Zahlen oder Daten stehen weder in Ihrem Text noch in den Dokumenten">Nicht in Ihrer Eingabe: {neu.join(", ")}</Chip> : null}
          {n.pruefung?.offene_stellen ? <Chip art="warn">{n.pruefung.offene_stellen} offene Stelle(n) [?]</Chip> : null}
          {n.dauer_s ? <span className="gedaempft">{Math.round(n.dauer_s)} s</span> : null}
          <Knopf klein variante="geist" icon="kopieren" onClick={() => void navigator.clipboard.writeText(n.text).then(() => melden("In die Zwischenablage kopiert."))}>Kopieren</Knopf>
        </div>
      ) : null}
    </div>
  );
}
