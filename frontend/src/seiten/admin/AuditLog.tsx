/** Entwurf 20 · Audit-Log: Anmeldungen, Benutzer, Vorlagen, Exporte, Abschlüsse – nur lesen, nicht änderbar. */
import { useState } from "react";
import { PdfDialog } from "@/components/PdfDialog";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { abfrage, alle, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { datum, heuteIso, uhrzeit, zahl, zeitpunkt } from "@/lib/format";
import type { Benutzer, Systemereignis } from "@/lib/typen";
import { Auswahl, Chip, Fehleranzeige, Karte, Knopf, Laden, Leer, Seitenkopf, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { Seite } from "@/components/layout/Shell";

const GRUPPEN: { wert: string; text: string }[] = [
  { wert: "anmeldung", text: "Anmeldung" }, { wert: "fehlversuch", text: "Fehlversuch" }, { wert: "benutzer", text: "Benutzer" },
  { wert: "vorlage", text: "Vorlage" }, { wert: "backup", text: "Backup" }, { wert: "export", text: "Export" },
  { wert: "abschluss", text: "Abschluss" }, { wert: "infusionsplan", text: "Infusionsplan" },
];
const ZEITRAEUME: Record<string, { text: string; tage: number | null }> = {
  "7": { text: "Letzte 7 Tage", tage: 7 }, "30": { text: "Letzte 30 Tage", tage: 30 }, jahr: { text: "Dieses Jahr", tage: null }, alles: { text: "Alles", tage: null },
};

function vonDatum(z: string): string | undefined {
  if (z === "alles") return undefined;
  if (z === "jahr") return `${heuteIso().slice(0, 4)}-01-01`;
  const d = new Date();
  d.setDate(d.getDate() - (ZEITRAEUME[z].tage ?? 0));
  return d.toLocaleDateString("sv-SE", { timeZone: "Europe/Berlin" });
}

type Gesperrt = { id: number; benutzername: string; anzeigename: string; gesperrt_am: string; sperrgrund: string; fehlversuche: number };

export function AuditLog() {
  const { darf } = useAuth();
  const [zeitraum, setZeitraum] = useState("7");
  const [person, setPerson] = useState("");
  const [gruppen, setGruppen] = useState<string[]>([]);
  const [anzahl, setAnzahl] = useState(100);
  const werte = { von: vonDatum(zeitraum), benutzer: person || undefined, gruppe: gruppen.join(",") || undefined, seitengroesse: anzahl };
  const liste = useQuery({
    queryKey: ["protokoll", werte],
    queryFn: () => api<ApiSeite<Systemereignis>>(`protokoll/${abfrage(werte)}`),
    placeholderData: (vorher: ApiSeite<Systemereignis> | undefined) => vorher,
  });
  const benutzer = useQuery({ queryKey: ["benutzer"], queryFn: () => alle<Benutzer>("benutzer/?ordering=last_name"), enabled: darf("benutzer_verwalten") });
  const gesperrt = useQuery({ queryKey: ["benutzer", "hinweise"], queryFn: () => api<Gesperrt[]>("benutzer/hinweise/"), enabled: darf("benutzer_verwalten") });
  const daten = liste.data;
  const [pdf, setPdf] = useState(false);
  return (
    <Seite pfad={[{ text: "Administration" }, { text: "Audit-Log" }]}>
      <Seitenkopf titel="Audit-Log" unter="Alles, was nicht zu einer einzelnen Akte gehört: Anmeldungen, Benutzer, Vorlagen, Backups, Exporte."
        rechts={<Knopf icon="dokument" onClick={() => setPdf(true)}>Zeitraum als PDF</Knopf>} />
      <PdfDialog offen={pdf} onOffen={setPdf} titel="Audit-Log als PDF" dateiname="Audit-Log.pdf"
        pfad={`protokoll/pdf/${abfrage({ ...werte, seitengroesse: undefined })}`} />
      <div className="flex items-center gap-2.5 flex-wrap">
        <Auswahl aria-label="Zeitraum" className="w-[180px]" value={zeitraum} onChange={(e) => setZeitraum(e.target.value)}>
          {Object.entries(ZEITRAEUME).map(([k, v]) => <option key={k} value={k}>{v.text}</option>)}
        </Auswahl>
        {darf("benutzer_verwalten") ? (
          <Auswahl aria-label="Person" className="w-[220px]" value={person} onChange={(e) => setPerson(e.target.value)}>
            <option value="">Alle Personen</option>
            {(benutzer.data ?? []).map((b) => <option key={b.id} value={b.id}>{b.anzeigename} ({b.username})</option>)}
          </Auswahl>
        ) : null}
        <span className="w-px h-6 bg-rand" aria-hidden="true" />
        {GRUPPEN.map((g) => (
          <button key={g.wert} type="button" aria-pressed={gruppen.includes(g.wert)}
            className={cx("chip h-[30px] cursor-pointer border", gruppen.includes(g.wert) ? "akzent border-akzent" : "border-rand bg-flaeche text-text2")}
            onClick={() => setGruppen(gruppen.includes(g.wert) ? gruppen.filter((x) => x !== g.wert) : [...gruppen, g.wert])}>{g.text}</button>
        ))}
      </div>
      {(gesperrt.data ?? []).map((g) => (
        <div key={g.id} className="meldung warn flex gap-2.5 items-start text-sm" data-testid="sperrhinweis">
          <Icon name="warnung" />
          <span><strong>Hinweis:</strong> {g.anzeigename} ({g.benutzername}) ist seit {zeitpunkt(g.gesperrt_am)} gesperrt{g.sperrgrund ? ` – ${g.sperrgrund}` : ""}.{" "}
            <Link to={`/admin/benutzer?id=${g.id}`}>Zum Benutzer</Link></span>
        </div>
      ))}
      <Karte className="overflow-hidden">
        {liste.isLoading ? <Laden /> : (
          <table className="tabelle" data-testid="auditlog" aria-busy={liste.isFetching || undefined}>
            <thead><tr><th className="th w-[150px]">Zeitpunkt</th><th className="th">Person</th><th className="th">Art</th><th className="th">Details</th><th className="th">Gerät / Adresse</th></tr></thead>
            <tbody>
              {(daten?.results ?? []).map((e) => (
                <tr key={e.id}>
                  <td className="td num whitespace-nowrap">{datum(e.zeitpunkt)} {uhrzeit(e.zeitpunkt)}</td>
                  <td className="td">{e.person}</td>
                  <td className="td"><Chip art={e.gruppe === "fehlversuch" ? "fehler" : e.gruppe === "benutzer" ? "akzent" : undefined} title={e.art_name}>{e.gruppe_name || e.art_name}</Chip></td>
                  <td className="td text-sm">{e.beschreibung}</td>
                  <td className="td text-[0.8125rem] gedaempft">{[e.geraet, e.ip].filter(Boolean).join(" · ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {daten && !daten.count ? <Leer>Keine Einträge für diese Auswahl.</Leer> : null}
        {daten?.next ? <div className="px-4 py-3 border-t border-rand flex items-center gap-3"><Knopf klein onClick={() => setAnzahl(anzahl + 100)}>Weitere laden</Knopf><span className="text-xs gedaempft">{zahl(daten.results.length)} von {zahl(daten.count)}</span></div> : null}
        <Fehleranzeige fehler={liste.error} />
      </Karte>
      <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
        <Icon name="schloss" />
        <span>Das Audit-Log wird automatisch geschrieben und kann von niemandem geändert oder gelöscht werden, auch nicht vom Admin.
          Änderungen an Patientendaten stehen im Reiter „Verlauf“ der jeweiligen Akte.</span>
      </div>
    </Seite>
  );
}
