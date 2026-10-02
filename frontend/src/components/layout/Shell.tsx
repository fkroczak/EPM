/** Seitenleiste und Kopfzeile wie im Entwurf (256 px Leiste, 60 px Kopf mit Pfad und Suche). */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { RECHTE_GEAENDERT, abfrage, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { useAuth, useIch } from "@/lib/auth";
import { datum, initialen, nummer, zeitpunkt } from "@/lib/format";
import { ROLLEN } from "@/lib/typen";
import type { PatientZeile } from "@/lib/typen";
import { Chip, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { Logo } from "./logo";

function NavEintrag({ zu, icon, text, ende }: { zu: string; icon: string; text: string; ende?: boolean }) {
  return (
    <NavLink to={zu} end={ende} title={text} className={({ isActive }) => cx("nav", isActive && "aktiv")}>
      <Icon name={icon} groesse={18} />
      <span className="sr-only hd:not-sr-only">{text}</span>
    </NavLink>
  );
}

function Seitenleiste() {
  const ich = useIch();
  const { abmelden, darf } = useAuth();
  const admin = [
    darf("backup_verwalten") ? <NavEintrag key="b" zu="/admin/backup" icon="backup" text="Backup" /> : null,
    darf("benutzer_verwalten") ? <NavEintrag key="u" zu="/admin/benutzer" icon="benutzer" text="Benutzer" /> : null,
    darf("vorlagen_pflegen") ? <NavEintrag key="v" zu="/admin/vorlagen" icon="vorlagen" text="Vorlagen" /> : null,
    darf("audit_lesen") ? <NavEintrag key="a" zu="/admin/audit-log" icon="uhr" text="Audit-Log" /> : null,
    darf("system_verwalten") ? <NavEintrag key="s" zu="/admin/system" icon="server" text="System" /> : null,
  ].filter(Boolean);
  return (
    <aside className="w-16 hd:w-64 shrink-0 bg-flaeche border-r border-rand flex flex-col px-2 hd:px-3 py-4 gap-5 nicht-drucken sticky top-0 h-screen overflow-y-auto"
      style={{ borderRightWidth: "var(--randbreite)" }}>
      <div className="hidden hd:flex flex-col gap-2">
        <Logo className="w-[204px] h-[72px] px-1.5 py-1 rounded-lg bg-white" />
        <span className="px-1 font-mono text-[0.6875rem] font-medium tracking-[.07em] uppercase gedaempft">
          EPM · Patientenmanagement
        </span>
      </div>
      <span className="hd:hidden self-center font-mono text-xs font-semibold tracking-[.07em] text-akzent-text" title="EPM · Patientenmanagement">EPM</span>
      <nav aria-label="Hauptnavigation" className="flex flex-col gap-0.5">
        <NavEintrag zu="/" icon="start" text="Start" ende />
        <NavEintrag zu="/patienten" icon="patienten" text="Patienten" />
        {darf("akten_lesen") ? <NavEintrag zu="/kalender" icon="kalender" text="Kalender" /> : null}
        {darf("akten_lesen") ? <NavEintrag zu="/infusionsplaene" icon="tropfen" text="Infusionspläne" /> : null}
        <NavEintrag zu="/versorger" icon="versorger" text="Versorger" />
        <NavEintrag zu="/aerzte" icon="arzt" text="Ärzte" />
        {darf("datenschutz_bearbeiten") || darf("datenschutz_entscheiden") ? <NavEintrag zu="/datenschutz" icon="schloss" text="Datenschutz" /> : null}
      </nav>
      {admin.length ? (
        <nav aria-label="Administration" className="flex flex-col gap-0.5">
          <div className="px-2 h-8 hidden hd:flex items-center text-xs font-medium gedaempft">Administration</div>
          <div className="hd:hidden border-t border-rand my-1" aria-hidden="true" />
          {admin}
        </nav>
      ) : null}
      <div className="mt-auto flex flex-col gap-2.5 border-t border-rand pt-3.5 hd:px-1.5">
        <div className="flex items-center gap-2.5 justify-center hd:justify-start" title={ich.anzeigename}>
          <div className="w-[34px] h-[34px] rounded-full bg-akzent-weich text-akzent-text flex items-center justify-center font-semibold text-[0.8125rem]">
            {ich.kuerzel || initialen(ich.anzeigename)}
          </div>
          <div className="flex-col min-w-0 sr-only hd:not-sr-only hd:flex">
            <span className="text-sm font-medium truncate" data-testid="angemeldet-als">{ich.anzeigename}</span>
            <span className="text-xs gedaempft">{ROLLEN[ich.rolle]}{ich.ist_test ? " · Testzugang" : ""}</span>
          </div>
        </div>
        <NavLink to="/konto" title="Mein Konto" className={({ isActive }) => cx("nav", isActive && "aktiv")}>
          <Icon name="konto" /> <span className="sr-only hd:not-sr-only">Mein Konto</span>
        </NavLink>
        <button type="button" title="Abmelden" className="nav border-0 bg-transparent cursor-pointer text-left" onClick={() => void abmelden()}>
          <Icon name="abmelden" /> <span className="sr-only hd:not-sr-only">Abmelden</span>
        </button>
      </div>
    </aside>
  );
}

/** Patientensuche in der Kopfzeile (Strg K): Name, Nummer oder Geburtsdatum */
function Suche() {
  const [text, setText] = useState("");
  const [offen, setOffen] = useState(false);
  const [markiert, setMarkiert] = useState(0);
  const feld = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { darf } = useAuth();
  const begriff = text.trim();
  const treffer = useQuery({
    queryKey: ["suche", begriff],
    queryFn: () => api<ApiSeite<PatientZeile>>(`patienten/${abfrage({ suche: begriff, seitengroesse: 8, ordering: "nachname" })}`),
    enabled: begriff.length >= 2 && darf("akten_lesen"),
  });
  const liste = treffer.data?.results ?? [];
  useEffect(() => {
    const taste = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        feld.current?.focus();
        feld.current?.select();
      }
    };
    window.addEventListener("keydown", taste);
    return () => window.removeEventListener("keydown", taste);
  }, []);
  useEffect(() => setMarkiert(0), [begriff]);
  const oeffnen = (p: PatientZeile) => {
    setOffen(false);
    setText("");
    navigate(`/patienten/${p.id}`);
  };
  return (
    <div className="relative w-[400px] max-w-[45vw]">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" groesse={18} /></span>
      <input
        ref={feld}
        className="inp pl-10 pr-16"
        type="search"
        role="combobox"
        aria-expanded={offen && begriff.length >= 2}
        aria-controls="suche-ergebnisse"
        aria-label="Suchen"
        placeholder="Patient suchen: Name, Nr. oder Geburtsdatum"
        value={text}
        onChange={(e) => { setText(e.target.value); setOffen(true); }}
        onFocus={() => setOffen(true)}
        onBlur={() => window.setTimeout(() => setOffen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setMarkiert((m) => Math.min(m + 1, liste.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setMarkiert((m) => Math.max(m - 1, 0)); }
          if (e.key === "Enter" && liste[markiert]) { e.preventDefault(); oeffnen(liste[markiert]); }
          if (e.key === "Escape") setOffen(false);
        }}
      />
      <span className="absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-[0.6875rem] font-medium gedaempft border border-rand rounded-[5px] px-1.5 py-0.5 pointer-events-none">
        Strg K
      </span>
      {offen && begriff.length >= 2 ? (
        <ul id="suche-ergebnisse" role="listbox" className="card absolute left-0 right-0 top-[calc(100%+6px)] z-50 m-0 p-1 list-none max-h-96 overflow-auto">
          {treffer.isLoading ? <li className="px-3 py-2 text-sm gedaempft">Suche …</li> : null}
          {!treffer.isLoading && liste.length === 0 ? <li className="px-3 py-2 text-sm gedaempft">Kein Patient gefunden.</li> : null}
          {liste.map((p, i) => (
            <li key={p.id} role="option" aria-selected={i === markiert}
              className={cx("px-3 py-2 rounded-md cursor-pointer flex items-center gap-3 text-sm", i === markiert && "bg-akzent-weich")}
              onMouseDown={(e) => { e.preventDefault(); oeffnen(p); }} onMouseEnter={() => setMarkiert(i)}>
              <span className="num gedaempft">{nummer(p.nummer)}</span>
              <span className="font-medium">{p.nachname}, {p.vorname}</span>
              <span className="gedaempft">{datum(p.geburtsdatum)}</span>
              {p.ist_abgeschlossen ? <Chip>abgeschlossen</Chip> : null}
              {p.ist_test ? <Chip art="warn">Test</Chip> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

type Hinweis = { id: number; text: string; art: "info" | "warnung"; gueltig_bis: string | null; angelegt_am: string;
  angelegt_von_name: string | null };

/** Hinweis der Administration an alle Angemeldeten (z. B. vor Updates oder einem Neustart des Servers); jede Minute
 *  neu abgefragt. Eigene Rolle „region“, damit er Meldungen der Seite (status/alert) nicht überdeckt. */
let ausgeblendeterHinweis: number | null = null;

function Systemhinweis() {
  const [weg, setWeg] = useState<number | null>(ausgeblendeterHinweis);
  const daten = useQuery({
    queryKey: ["systemhinweis"],
    queryFn: () => api<{ hinweis: Hinweis | null }>("system/hinweis/"),
    refetchInterval: 60_000,
    refetchIntervalInBackground: true,
    staleTime: 30_000,
  });
  const h = daten.data?.hinweis;
  if (!h || weg === h.id) return null;
  return (
    <div role="region" aria-label="Hinweis der Administration" data-testid="systemhinweis"
      className={cx("nicht-drucken flex items-start gap-3 px-8 py-2.5 text-sm border-b",
        h.art === "warnung" ? "bg-warn-bg text-warn border-warn/30" : "bg-akzent-weich text-akzent-text border-rand")}>
      <Icon name={h.art === "warnung" ? "warnung" : "info"} groesse={18} className="shrink-0 mt-0.5" />
      <span className="grow leading-normal">
        <strong className="font-semibold">Hinweis der Administration: </strong>{h.text}
        {h.angelegt_von_name ? <span className="opacity-80"> – {h.angelegt_von_name}, {zeitpunkt(h.angelegt_am)}</span> : null}
      </span>
      <button type="button" className="btn geist klein shrink-0" onClick={() => { ausgeblendeterHinweis = h.id; setWeg(h.id); }}
        aria-label="Hinweis ausblenden">Ausblenden</button>
    </div>
  );
}

export type Pfadteil = { text: string; zu?: string };

/** Kopfzeile + Inhalt einer Seite */
export function Seite({ pfad, children, breit, className }: { pfad: Pfadteil[]; children: ReactNode; breit?: boolean;
  className?: string }) {
  const ich = useIch();
  useEffect(() => {
    document.title = `${pfad[pfad.length - 1]?.text ?? "Start"} · EPM`;
  }, [pfad]);
  return (
    <div className="grow min-w-0 flex flex-col min-h-screen">
      <header className="h-[60px] shrink-0 flex items-center justify-between gap-6 px-8 bg-flaeche border-b border-rand nicht-drucken">
        <nav aria-label="Pfad" className="flex items-center gap-2.5 text-sm min-w-0">
          {pfad.map((t, i) => (
            <span key={i} className="flex items-center gap-2.5 min-w-0">
              {i > 0 ? <span className="gedaempft">/</span> : null}
              {t.zu && i < pfad.length - 1 ? <Link to={t.zu} className="no-underline text-text2 hover:text-tinte">{t.text}</Link>
                : <span className={cx(i === pfad.length - 1 && "font-semibold", "truncate")} aria-current={i === pfad.length - 1 ? "page" : undefined}>{t.text}</span>}
            </span>
          ))}
        </nav>
        <div className="flex items-center gap-4">
          <Suche />
          {ich.ist_test ? <Chip art="warn" data-testid="testzugang">Testzugang</Chip> : null}
        </div>
      </header>
      <Systemhinweis />
      <main className={cx("grow min-h-0 px-8 py-7 flex flex-col gap-5", !breit && "max-w-[1440px]", className)}>{children}</main>
    </div>
  );
}

/**
 * Beim Seitenwechsel die eigenen Rechte prüfen: Seiten aus dem Zwischenspeicher laden ohne Anfrage, eine in der
 * Administration geänderte Berechtigung soll trotzdem mit dem nächsten Klick sichtbar werden (F71).
 */
function useRechteAktuell() {
  const { pathname } = useLocation();
  const erster = useRef(true);
  useEffect(() => {
    if (erster.current) {
      erster.current = false;
      return;
    }
    window.dispatchEvent(new Event(RECHTE_GEAENDERT));
  }, [pathname]);
}

export function Shell() {
  useRechteAktuell();
  return (
    <div className="flex min-h-screen bg-grund">
      <Seitenleiste />
      <Outlet />
    </div>
  );
}
