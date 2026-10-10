/**
 * Vorlagen › Übersicht (F180, Wunsch 10.10.2026: „intuitiver für Praxismanager und Pflegekräfte“): Kacheln in
 * Alltagssprache – je Bereich „Wofür?“ und „Wo wird es benutzt?“ – und eine Suche über alle Vorlagen, Listen,
 * Präparate und Anlagen. Die Kacheln und Treffer sind Links (Adresse mit ?bereich=…), damit „Zurück“ funktioniert.
 */
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Auswahlwert, Praeparat } from "@/lib/typen";
import { Chip, Eingabe, Karte, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { LISTEN } from "@/seiten/admin/Auswahllisten";
import type { VorlagenUebersicht } from "@/seiten/admin/Dokumentvorlagen";

type Kachel = { titel: string; icon: string; ziel: string; bereich: string; wofuer: string; wo: string; stichwoerter: string };

export const DOKUMENTE_PFAD = "/admin/vorlagen/dokumente";
const zuBereich = (bereich: string, liste?: string) => `/admin/vorlagen?bereich=${bereich}${liste ? `&liste=${liste}` : ""}`;

const KACHELN: Kachel[] = [
  { titel: "Briefe, Formulare und E-Mail-Texte", icon: "mail", ziel: DOKUMENTE_PFAD, bereich: "Dokumentvorlagen",
    wofuer: "Text und Aussehen von Briefen, E-Mails und PDFs ändern – z. B. Terminbestätigung, Infusionsplan, Datenschutz-Vordrucke.",
    wo: "Akte › Schreiben und E-Mail, Infusionspläne, Kalender › Ankündigung",
    stichwoerter: "dokumentvorlagen brief schreiben email e-mail pdf text formular vordruck" },
  { titel: "Briefkopf und Logo", icon: "bild", ziel: zuBereich("briefkopf"), bereich: "Briefkopf und Logo",
    wofuer: "Logo, Anschrift, Telefon und Fußzeile, die oben und unten auf den PDFs stehen.",
    wo: "Auf jedem PDF: Infusionspläne, Briefe, Vordrucke",
    stichwoerter: "absender adresse anschrift telefon fax fußzeile logo briefkopf" },
  { titel: "Medikamente und Präparate", icon: "tropfen", ziel: zuBereich("listen", "aminosaeuren"), bereich: "Auswahllisten",
    wofuer: "Welche Präparate im Infusionsplan zur Auswahl stehen und in welcher Reihenfolge; nicht mehr benutzte ausblenden.",
    wo: "Akte › Infusionsplan erstellen und ändern",
    stichwoerter: "präparat medikament vitamine lipide glucose aminosäuren spurenelemente katheterblock" },
  { titel: "Auswahllisten", icon: "menue", ziel: zuBereich("listen", "katheter"), bereich: "Auswahllisten",
    wofuer: "Was in Feldern wie Katheter, Terminort, Dokumenttyp, Kontaktart oder Berichtsart zur Auswahl steht.",
    wo: "Akte, Termine, Kontakte, Dokumente, Berichte",
    stichwoerter: "auswahl liste katheter terminort ort dokumenttyp kontaktart beziehung berichtsart" },
  { titel: "Labor und Diagnosen", icon: "buch", ziel: zuBereich("kataloge"), bereich: "Labor und Diagnosen",
    wofuer: "Laborwerte mit Einheit und Referenzbereich sowie die Liste der Diagnosen mit ICD-Code.",
    wo: "Akte › Befunde und Diagnosen; Texterkennung von Laborbefunden",
    stichwoerter: "labor laborwert parameter referenz diagnose icd katalog" },
  { titel: "Grenzwerte und Fristen", icon: "warnung", ziel: zuBereich("grenzwerte"), bereich: "Grenzwerte",
    wofuer: "Ab wann EPM warnt (Gewichtsverlust, Kontakt fällig, alter Befund), Plausibilitätsgrenzen und Fristen für Datenschutz und Scans.",
    wo: "Startseite, Patientenliste, Kalender, Eingabe von Werten",
    stichwoerter: "grenzwert frist warnung gewicht kontakt fällig wiedervorlage datenschutz aufbewahrung scan plausibel kcal" },
  { titel: "Anlagen für E-Mails", icon: "dokument", ziel: zuBereich("anlagen"), bereich: "Anlagen für E-Mails",
    wofuer: "Merkblätter als PDF, die man beim Schreiben an die E-Mail hängen kann – z. B. Leitfaden Zottentraining.",
    wo: "Akte › Schreiben und E-Mail; Kalender › Ankündigung",
    stichwoerter: "anlage anhang merkblatt pdf leitfaden zottentraining" },
];

type Anlage = { id: number; name: string; beschreibung: string; aktiv: boolean };
type Treffer = { schluessel: string; titel: string; art: string; hinweis?: string; ziel: string };

const klein = (s: string) => s.toLocaleLowerCase("de");

export function VorlagenStart() {
  const [suche, setSuche] = useState("");
  const vorlagen = useQuery({ queryKey: ["vorlagen", "liste"], queryFn: () => api<VorlagenUebersicht[]>("vorlagen/") });
  const aktivSuche = suche.trim().length >= 2;
  // Listen, Präparate und Anlagen erst beim Suchen laden
  const praeparate = useQuery({ queryKey: ["praeparate", "alle"], queryFn: () => api<Praeparat[]>("praeparate/"), enabled: aktivSuche });
  const auswahl = useQuery({ queryKey: ["auswahlwerte", "verwaltung"], queryFn: () => api<Auswahlwert[]>("auswahlwerte/"), enabled: aktivSuche });
  const anlagen = useQuery({ queryKey: ["anlagen", "alle"], queryFn: () => api<Anlage[]>("anlagen/?alle=1"), enabled: aktivSuche });
  const offen = (vorlagen.data ?? []).filter((v) => v.entwurf);

  const treffer = useMemo<Treffer[]>(() => {
    if (!aktivSuche) return [];
    const s = klein(suche.trim());
    const passt = (...t: (string | undefined)[]) => t.some((x) => x && klein(x).includes(s));
    const listeTitel = (k: string) => LISTEN.find((l) => l.schluessel === k)?.titel ?? k;
    const liste: Treffer[] = [
      ...KACHELN.filter((k) => passt(k.titel, k.wofuer, k.stichwoerter, k.bereich))
        .map((k) => ({ schluessel: `k-${k.titel}`, titel: k.titel, art: "Bereich", hinweis: k.wofuer, ziel: k.ziel })),
      ...(vorlagen.data ?? []).filter((v) => passt(v.name, v.wofuer))
        .map((v) => ({ schluessel: `v-${v.art}`, titel: v.name, art: "Brief/Formular", hinweis: v.wofuer, ziel: `${DOKUMENTE_PFAD}?art=${v.art}` })),
      ...LISTEN.filter((l) => passt(l.titel, l.wo))
        .map((l) => ({ schluessel: `l-${l.schluessel}`, titel: l.titel, art: l.art === "praeparat" ? "Präparate" : "Auswahlliste", hinweis: l.wo, ziel: zuBereich("listen", l.schluessel) })),
      ...(praeparate.data ?? []).filter((p) => passt(p.anzeige, p.hinweis))
        .map((p) => ({ schluessel: `p-${p.id}`, titel: p.anzeige, art: "Präparat", hinweis: `in „${listeTitel(p.kategorie)}“${p.aktiv ? "" : " · ausgeblendet"}`, ziel: zuBereich("listen", p.kategorie) })),
      ...(auswahl.data ?? []).filter((a) => passt(a.wert))
        .map((a) => ({ schluessel: `a-${a.id}`, titel: a.wert, art: "Eintrag", hinweis: `in „${listeTitel(a.liste)}“${a.aktiv ? "" : " · ausgeblendet"}`, ziel: zuBereich("listen", a.liste) })),
      ...(anlagen.data ?? []).filter((a) => passt(a.name, a.beschreibung))
        .map((a) => ({ schluessel: `n-${a.id}`, titel: a.name, art: "Anlage", hinweis: a.beschreibung || undefined, ziel: zuBereich("anlagen") })),
    ];
    return liste.slice(0, 30);
  }, [aktivSuche, suche, vorlagen.data, praeparate.data, auswahl.data, anlagen.data]);

  return (
    <div className="stapel flex flex-col gap-5" data-testid="vorlagen-start">
      <Karte className="px-5 py-4 flex flex-col gap-2.5">
        <label htmlFor="vorlagen-suche" className="text-[0.9375rem] font-medium">Was möchten Sie ändern?</label>
        <div className="relative max-w-[36rem]">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" /></span>
          <Eingabe id="vorlagen-suche" type="search" className="pl-9 w-full" value={suche} onChange={(e) => setSuche(e.target.value)}
            placeholder="z. B. Terminbestätigung, Katheter, Logo, Cernevit …" autoComplete="off" />
        </div>
        {aktivSuche ? (
          treffer.length ? (
            <ul className="m-0 p-0 list-none flex flex-col divide-y divide-rand max-w-[48rem]" data-testid="vorlagen-treffer" aria-label="Treffer">
              {treffer.map((t) => (
                <li key={t.schluessel}>
                  <Link to={t.ziel} className="flex items-baseline gap-3 py-2 px-1 rounded-md no-underline text-tinte hover:bg-fein">
                    <span className="text-[0.75rem] gedaempft w-[6.5rem] shrink-0">{t.art}</span>
                    <span className="flex flex-col min-w-0">
                      <span className="font-medium text-akzent-text">{t.titel}</span>
                      {t.hinweis ? <span className="text-[0.8125rem] gedaempft">{t.hinweis}</span> : null}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : <span className="text-sm gedaempft">Nichts gefunden zu „{suche.trim()}“. Vielleicht unter einem der Bereiche unten?</span>
        ) : <span className="text-[0.8125rem] gedaempft">Sucht in allen Briefen und Formularen, Auswahllisten, Präparaten und Anlagen.</span>}
      </Karte>

      {offen.length ? (
        <div className="meldung warn" role="status" data-testid="vorlagen-offen">
          <span>Noch nicht freigegebene Änderungen an {offen.length === 1 ? "einer Vorlage" : `${offen.length} Vorlagen`}:{" "}
            {offen.map((v, i) => <span key={v.art}>{i ? ", " : ""}<Link to={`${DOKUMENTE_PFAD}?art=${v.art}`}>{v.name}</Link></span>)}.
            {" "}Bis zum Freigeben gilt in der Praxis die bisherige Fassung.</span>
        </div>
      ) : null}

      <ul className="m-0 p-0 list-none grid gap-4 grid-cols-1 md:grid-cols-2 2xl:grid-cols-3" aria-label="Bereiche">
        {KACHELN.map((k) => {
          const zahl = k.ziel === DOKUMENTE_PFAD ? vorlagen.data?.length : undefined;
          return (
            <li key={k.titel} className="flex">
              <Link to={k.ziel} data-testid="vorlagen-kachel"
                className={cx("card flex-1 flex flex-col gap-2 px-5 py-4 no-underline text-tinte border border-transparent",
                  "hover:border-akzent hover:shadow-md focus-visible:outline-2 focus-visible:outline-akzent")}>
                <span className="flex items-center gap-2.5">
                  <span className="w-8 h-8 rounded-lg bg-akzent-weich text-akzent-text inline-flex items-center justify-center shrink-0"><Icon name={k.icon} /></span>
                  <span className="text-[1rem] font-semibold leading-snug">{k.titel}</span>
                  {zahl ? <Chip className="ml-auto">{zahl} Vorlagen</Chip> : null}
                </span>
                <span className="text-sm leading-normal">{k.wofuer}</span>
                <span className="text-[0.8125rem] gedaempft leading-normal"><strong className="font-medium text-text2">Wo benutzt:</strong> {k.wo}</span>
                <span className="text-[0.75rem] gedaempft mt-auto pt-1">Oben im Menü: „{k.bereich}“</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
