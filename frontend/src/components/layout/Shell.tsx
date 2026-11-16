/** Seitenleiste und Kopfzeile wie im Entwurf (256 px Leiste, 60 px Kopf mit Pfad und Suche). Am Telefon (unter 768 px,
 *  Festlegung 08.10.2026) statt der Seitenleiste eine Leiste unten (Start, Patienten, Notiz, Pläne, Menü) und das
 *  vollständige Menü als Schublade. */
import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Dialog as BaseDialog } from "@base-ui/react/dialog";
import { Menu as BaseMenu } from "@base-ui/react/menu";
import { RECHTE_GEAENDERT, abfrage, api } from "@/lib/api";
import type { Seite as ApiSeite } from "@/lib/api";
import { useKiZurPruefung } from "@/lib/ki";
import { useFreigabenOffen } from "@/lib/freigaben";
import { useAuth, useIch } from "@/lib/auth";
import { datum, initialen, nummer, zeitpunkt } from "@/lib/format";
import { ROLLEN } from "@/lib/typen";
import type { Patient, PatientZeile } from "@/lib/typen";
import { KontaktDialog } from "@/components/Schnellerfassung";
import type { Vorgabe } from "@/components/Schnellerfassung";
import { useMobil } from "@/lib/stufen";
import { Ladebalken } from "@/components/ui/Ladebalken";
import { Chip, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import { FirmenSchalter } from "./FirmenSchalter";
import { Logo } from "./logo";
import { useDiktatStand } from "@/lib/diktate";

/** In der Schublade am Telefon stehen die Texte immer neben den Symbolen */
const Voll = createContext(false);
const TEXT = "sr-only hd:not-sr-only";

function NavText({ children }: { children: ReactNode }) {
  return <span className={useContext(Voll) ? undefined : TEXT}>{children}</span>;
}

function NavEintrag({ zu, icon, text, ende, zahl, testid }: { zu: string; icon: string; text: string; ende?: boolean;
  /** Zähler (z. B. offene Scans): neben dem Text, in der schmalen Leiste als Punkt am Symbol */
  zahl?: number; testid?: string }) {
  // schmale Leiste (nur Symbole): jeder Eintrag gleich groß und das Symbol mittig (Wunsch 08.10.2026)
  const voll = useContext(Voll);
  const titel = zahl ? `${text} (${zahl})` : text;
  return (
    <NavLink to={zu} end={ende} title={titel} className={({ isActive }) => cx("nav", !voll && "nav-symbol", isActive && "aktiv", "relative")}
      data-testid={testid}>
      <Icon name={icon} groesse={18} />
      <NavText>{text}</NavText>
      {zahl ? <>
        <span className={cx("nav-zahl num", voll ? "ml-auto" : "max-hd:hidden ml-auto")} aria-label={`${zahl} offen`}>{zahl}</span>
        {voll ? null : <span className="nav-punkt hd:hidden" aria-hidden="true" />}
      </> : null}
    </NavLink>
  );
}

/** Zahl der Scans, die auf Zuordnung warten oder gerade erkannt werden (Navigation, einmal je Minute) */
function useScansOffen(): number {
  const { darf } = useAuth();
  const stand = useQuery({
    queryKey: ["scans", "stand"],
    queryFn: () => api<{ offen: number; laufend: number }>("scans/stand/", { hintergrund: true }),
    enabled: darf("scans_bearbeiten"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  return stand.data ? stand.data.offen + stand.data.laufend : 0;
}

/** Angemeldete Person unten in der Seitenleiste: Kürzel im Kreis, Name und Rolle */
function Person({ v }: { v: boolean }) {
  const ich = useIch();
  return (
    <span className={cx("flex items-center gap-2.5 min-w-0", v ? "justify-start" : "justify-center hd:justify-start")}>
      <span aria-hidden="true" className="w-[2.125rem] h-[2.125rem] shrink-0 rounded-full bg-akzent-weich text-akzent-text flex items-center justify-center font-semibold text-[0.8125rem]">
        {ich.kuerzel || initialen(ich.anzeigename)}
      </span>
      <span className={cx("flex-col min-w-0 text-left", v ? "flex" : "sr-only hd:not-sr-only hd:flex")}>
        <span className="text-sm font-medium truncate text-tinte" data-testid={v ? undefined : "angemeldet-als"}>{ich.anzeigename}</span>
        <span className="text-xs gedaempft">{ROLLEN[ich.rolle]}{ich.ist_test ? " · Testzugang" : ""}</span>
      </span>
    </span>
  );
}

const ADMIN_OFFEN = "epm.navigation.administration";

function Seitenleiste({ schublade }: { schublade?: boolean }) {
  const ich = useIch();
  const { abmelden, darf } = useAuth();
  const scansOffen = useScansOffen();
  const diktateOffen = useDiktatStand().data?.offen ?? 0;
  const kiZurPruefung = useKiZurPruefung();
  const freigabenOffen = useFreigabenOffen();
  const navigate = useNavigate();
  const admin = [
    // Übersicht mit Ampel und häufigen Aufgaben (Wunsch 10.10.2026)
    darf("system_verwalten") || darf("backup_verwalten") ? <NavEintrag key="sv" zu="/admin" icon="aktivitaet" text="Systemverwaltung" ende /> : null,
    darf("backup_verwalten") ? <NavEintrag key="b" zu="/admin/backup" icon="backup" text="Backup" /> : null,
    darf("benutzer_verwalten") ? <NavEintrag key="u" zu="/admin/benutzer" icon="benutzer" text="Benutzer" /> : null,
    darf("vorlagen_pflegen") ? <NavEintrag key="v" zu="/admin/vorlagen" icon="vorlagen" text="Vorlagen" /> : null,
    // Fälle und Abrechnung (26.10.2026): nur Regeneration Clinic
    darf("vorlagen_pflegen") && ich.firma === "rg" ? <NavEintrag key="fa" zu="/admin/abrechnung" icon="buch" text="Fälle und Abrechnung" /> : null,
    darf("audit_lesen") ? <NavEintrag key="a" zu="/admin/audit-log" icon="uhr" text="Audit-Log" /> : null,
    darf("system_verwalten") ? <NavEintrag key="s" zu="/admin/system" icon="server" text="System" /> : null,
    darf("ki_verwalten") ? <NavEintrag key="k" zu="/admin/ki" icon="stern" text="KI" /> : null,
    // nach der Übernahme unter System ausblendbar (U32); die Seite bleibt über System erreichbar
    darf("altdaten_importieren") && !ich.import_ausgeblendet ? <NavEintrag key="i" zu="/admin/import" icon="hochladen" text="Import" /> : null,
  ].filter(Boolean);
  const v = !!schublade;
  const firma = ich.firmen?.find((f) => f.kuerzel === ich.firma);
  // Administration aufgeklappt: gemerkt je Browser; auf einer Seite der Administration immer offen
  const { pathname } = useLocation();
  const [adminGemerkt, setAdminGemerkt] = useState(() => {
    try { return window.localStorage.getItem(ADMIN_OFFEN) === "1"; } catch { return false; }
  });
  const adminOffen = adminGemerkt || pathname.startsWith("/admin");
  const adminUmschalten = (offen: boolean) => {
    setAdminGemerkt(offen);
    try { window.localStorage.setItem(ADMIN_OFFEN, offen ? "1" : "0"); } catch { /* ohne Speicher: nur für diese Sitzung */ }
  };
  return (
    <Voll.Provider value={v}>
    <aside data-leiste className={cx("shrink-0 bg-leiste border-r border-rand flex flex-col py-4 gap-5 nicht-drucken overflow-y-auto",
      v ? "w-full h-full px-3" : "w-16 hd:w-56 px-2 hd:px-2.5 sticky top-0 h-screen max-md:hidden")}
      style={{ borderRightWidth: "var(--randbreite)" }} data-testid={v ? "schublade" : "seitenleiste"}
      aria-label="Seitenleiste">
      <div className={cx(v ? "flex" : "hidden hd:flex", "flex-col gap-2")}>
        {/* Logo, Name und Umschalter mittig (Wunsch 11.10.2026); RGC direkt auf der salbeigrünen Leiste, DSKM auf weißem Feld */}
        <Logo className={cx("w-full max-w-[12.75rem] h-[4rem] px-1.5 py-1 rounded-lg self-center", ich.firma !== "rg" && "bg-white")}
          style={{ objectPosition: "center" }} firma={firma?.kuerzel} name={firma?.name} />
        <span className="px-1 text-center font-mono text-[0.6875rem] font-medium tracking-[.07em] uppercase gedaempft">
          EPM · Patientenmanagement
        </span>
        {/* Umschalter zwischen den Firmen direkt unter dem Logo (Anforderung 11.10.2026) */}
        <FirmenSchalter className="max-w-[12.75rem] self-center" />
      </div>
      {v ? null : <span className="hd:hidden self-center font-mono text-xs font-semibold tracking-[.07em] text-akzent-text" title="EPM · Patientenmanagement">EPM</span>}
      {v ? null : <FirmenSchalter schmal className="hd:hidden" />}
      <nav aria-label="Hauptnavigation" className="flex flex-col gap-0.5">
        <NavEintrag zu="/" icon="start" text="Start" ende />
        {darf("akten_lesen") ? <NavEintrag zu="/patienten" icon="patienten" text="Patienten" /> : null}
        {darf("akten_lesen") ? <NavEintrag zu="/kalender" icon="kalender" text="Kalender" /> : null}
        {/* Freigaben (16.11.2026): alles, was freigegeben werden muss, an einer Stelle */}
        {darf("datenpflege_freigeben") || darf("plaene_freigeben") || darf("ki_ansehen")
          ? <NavEintrag zu="/freigaben" icon="haken" text="Freigaben" zahl={freigabenOffen} testid="nav-freigaben" /> : null}
        {darf("akten_lesen") ? <NavEintrag zu="/infusionsplaene" icon="tropfen" text="Infusionspläne" /> : null}
        {/* Rolle „Keine Berechtigung“: keine gemeinsamen Listen */}
        {ich.rolle !== "keine" ? <NavEintrag zu="/versorger" icon="versorger" text="Versorger" /> : null}
        {ich.rolle !== "keine" ? <NavEintrag zu="/aerzte" icon="arzt" text="Ärzte" /> : null}
        {darf("datenschutz_bearbeiten") || darf("datenschutz_entscheiden") ? <NavEintrag zu="/datenschutz" icon="schloss" text="Datenschutz" /> : null}
        {/* eigener Menüpunkt direkt nach Datenschutz (Festlegung 08.10.2026, F160 ff.) */}
        {darf("scans_bearbeiten") ? <NavEintrag zu="/scans" icon="scan" text="Scans" zahl={scansOffen} testid="nav-scans" /> : null}
        {/* Diktate (23.10.2026): fürs Sekretariat, sobald etwas abgegeben ist; wer diktiert, sieht den Punkt immer und nimmt dort auf */}
        {darf("diktieren") || (darf("eintraege_erfassen") && diktateOffen > 0)
          ? <NavEintrag zu="/diktate" icon="mikrofon" text="Diktate" zahl={diktateOffen} testid="nav-diktate" /> : null}
        {/* KI (Experimentell, 14.10.2026): Prüf-Queue mit Zahl der Dokumente zur Prüfung */}
        {darf("ki_ansehen") ? <NavEintrag zu="/ki" icon="stern" text="KI (Experimentell)" zahl={kiZurPruefung} testid="nav-ki" /> : null}
      </nav>
      {admin.length ? (
        <nav aria-label="Administration" className="flex flex-col gap-0.5">
          {/* Wer viele Verwaltungsseiten hat (Praxismanagement), sieht sie als eine Gruppe zum Aufklappen – die
              tägliche Arbeit steht oben ohne Ablenkung (Wunsch 10.10.2026, F181). Bis zu zwei Punkte (Vorlagen,
              Audit-Log) bleiben offen; in der Schublade am Telefon und auf Seiten der Administration ist sie offen. */}
          {!v && admin.length > 2 ? (
            <button type="button" className={cx("nav nav-symbol hd:!justify-start border-0 bg-transparent cursor-pointer w-full", adminOffen && "text-tinte")}
              aria-expanded={adminOffen} title={adminOffen ? "Administration einklappen" : `Administration (${admin.length} Seiten)`}
              onClick={() => adminUmschalten(!adminOffen)} data-testid="nav-administration">
              <Icon name="zahnrad" groesse={18} />
              <span className="sr-only hd:not-sr-only">Administration</span>
              <span className="hidden hd:inline-flex ml-auto gedaempft" aria-hidden="true"><Icon name={adminOffen ? "hoch" : "runter"} groesse={14} /></span>
            </button>
          ) : <>
            <div className={cx("px-2 h-8 items-center text-xs font-medium gedaempft", v ? "flex" : "hidden hd:flex")}>Administration</div>
            {v ? null : <div className="hd:hidden border-t border-rand my-1" aria-hidden="true" />}
          </>}
          {v || admin.length <= 2 || adminOffen ? <div className={cx("flex flex-col gap-0.5", !v && admin.length > 2 && "hd:pl-2")}>{admin}</div> : null}
        </nav>
      ) : null}
      {/* Unten links nur die angemeldete Person (Wunsch 08.10.2026); Hilfe, Design, Mein Konto und Abmelden per Klick als Menü (Design seit 09.10.2026 eigener Punkt).
          In der Schublade am Telefon bleiben die Einträge offen sichtbar. */}
      <div className={cx("mt-auto flex flex-col gap-2.5 border-t border-rand pt-3.5", v ? "px-1.5" : "hd:px-1.5")}>
        {v ? <>
          <Person v />
          <NavLink to="/hilfe" title="Hilfe" className={({ isActive }) => cx("nav", isActive && "aktiv")}>
            <Icon name="hilfe" /> <NavText>Hilfe</NavText>
          </NavLink>
          <NavLink to="/design" title="Design" className={({ isActive }) => cx("nav", isActive && "aktiv")}>
            <Icon name="design" /> <NavText>Design</NavText>
          </NavLink>
          <NavLink to="/konto" title="Mein Konto" className={({ isActive }) => cx("nav", isActive && "aktiv")}>
            <Icon name="konto" /> <NavText>Mein Konto</NavText>
          </NavLink>
          <button type="button" title="Abmelden" className="nav border-0 bg-transparent cursor-pointer text-left" onClick={() => void abmelden()}>
            <Icon name="abmelden" /> <NavText>Abmelden</NavText>
          </button>
        </> : (
          <BaseMenu.Root>
            <BaseMenu.Trigger className="benutzerknopf" title={`${ich.anzeigename} – Hilfe, Design, Mein Konto, Abmelden`}
              data-testid="benutzermenue">
              <Person v={false} />
              <span className="hidden hd:inline-flex ml-auto gedaempft" aria-hidden="true"><Icon name="hoch" groesse={14} /></span>
            </BaseMenu.Trigger>
            <BaseMenu.Portal>
              {/* so breit wie der Knopf, bündig darüber; Einträge wie im Hauptmenü (Wunsch 08.10.2026) */}
              <BaseMenu.Positioner side="top" align="start" sideOffset={4} className="z-50">
                <BaseMenu.Popup className="card benutzermenue-liste p-1 flex flex-col gap-0.5 outline-none" data-testid="benutzermenue-liste">
                  {[
                    { text: "Hilfe", icon: "hilfe", tun: () => navigate("/hilfe") },
                    { text: "Design", icon: "design", tun: () => navigate("/design") },
                    { text: "Mein Konto", icon: "konto", tun: () => navigate("/konto") },
                    { text: "Abmelden", icon: "abmelden", tun: () => void abmelden() },
                  ].map((e) => (
                    <BaseMenu.Item key={e.text} onClick={e.tun} className="nav cursor-pointer outline-none data-[highlighted]:bg-fein data-[highlighted]:text-tinte">
                      <Icon name={e.icon} groesse={18} />{e.text}
                    </BaseMenu.Item>
                  ))}
                </BaseMenu.Popup>
              </BaseMenu.Positioner>
            </BaseMenu.Portal>
          </BaseMenu.Root>
        )}
      </div>
    </aside>
    </Voll.Provider>
  );
}

/** Telefon: Leiste unten mit den häufigsten Wegen; „Notiz“ öffnet die Schnellerfassung (in einer Akte für diese). */
function MobilLeiste() {
  const { darf } = useAuth();
  const { pathname } = useLocation();
  const qc = useQueryClient();
  const [menue, setMenue] = useState(false);
  const [notiz, setNotiz] = useState<{ vorgabe: Vorgabe | null } | null>(null);
  useEffect(() => setMenue(false), [pathname]);
  const notizOeffnen = () => {
    const id = Number(pathname.match(/^\/patienten\/(\d+)/)?.[1] ?? 0);
    const p = id ? qc.getQueryData<Patient>(["patient", id]) : undefined;
    setNotiz({ vorgabe: p && !p.ist_abgeschlossen ? { id: p.id, name: `${p.nachname}, ${p.vorname}`, ist_test: p.ist_test } : null });
  };
  const eintrag = (zu: string, icon: string, text: string, ende?: boolean) => (
    <NavLink to={zu} end={ende} className={({ isActive }) => cx("mobil-nav", isActive && "aktiv")}>
      <Icon name={icon} groesse={22} /><span>{text}</span>
    </NavLink>
  );
  return (
    <>
      <nav aria-label="Hauptnavigation (Telefon)" data-testid="mobil-leiste"
        data-leiste className="nicht-drucken fixed bottom-0 inset-x-0 z-30 bg-leiste border-t border-rand grid grid-cols-5 pb-[env(safe-area-inset-bottom)]">
        {eintrag("/", "start", "Start", true)}
        {darf("akten_lesen") ? eintrag("/patienten", "patienten", "Patienten") : <span />}
        {darf("eintraege_erfassen") ? (
          <button type="button" className="mobil-nav" onClick={notizOeffnen} data-testid="mobil-notiz">
            <span className="mobil-plus"><Icon name="plus" groesse={22} /></span><span>Notiz</span>
          </button>
        ) : <span />}
        {darf("akten_lesen") ? eintrag("/infusionsplaene?gruppe=entwuerfe", "tropfen", "Pläne") : <span />}
        <button type="button" className="mobil-nav" onClick={() => setMenue(true)} aria-haspopup="dialog" data-testid="mobil-menue">
          <Icon name="menue" groesse={22} /><span>Menü</span>
        </button>
      </nav>
      <BaseDialog.Root open={menue} onOpenChange={setMenue}>
        <BaseDialog.Portal>
          <BaseDialog.Backdrop className="fixed inset-0 z-40 bg-black/35" />
          {/* von rechts, auf der Seite des Knopfs „Menü“ (Daumen bleibt rechts, Wunsch 11.10.2026) */}
          <BaseDialog.Popup data-leiste data-testid="mobil-schublade" className="fixed inset-y-0 right-0 z-50 w-[min(20rem,86vw)] bg-leiste shadow-xl border-l border-rand pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
            <BaseDialog.Title className="sr-only">Menü</BaseDialog.Title>
            <BaseDialog.Close className="btn geist icon absolute right-2 top-[calc(env(safe-area-inset-top)+0.5rem)] z-10" aria-label="Menü schließen">
              <Icon name="x" />
            </BaseDialog.Close>
            <Seitenleiste schublade />
          </BaseDialog.Popup>
        </BaseDialog.Portal>
      </BaseDialog.Root>
      {notiz ? <KontaktDialog offen onOffen={(o) => { if (!o) setNotiz(null); }} vorgabe={notiz.vorgabe} /> : null}
    </>
  );
}

/** Patientensuche in der Kopfzeile (Strg K): Name, Nummer oder Geburtsdatum */
function Suche({ vollbreit, onFertig }: { vollbreit?: boolean; onFertig?: () => void } = {}) {
  // Auf der Patientenliste filtert dieses Feld direkt die Liste (?suche=…) – ein Suchfeld statt zwei
  // (Vorschlag „Weniger Wege“, 08.10.2026); überall sonst schlägt es Patienten zum Öffnen vor.
  const { pathname } = useLocation();
  const [params, setParams] = useSearchParams();
  const listenModus = pathname === "/patienten";
  const [text, setText] = useState(() => (listenModus ? params.get("suche") ?? "" : ""));
  const [offen, setOffen] = useState(false);
  const [markiert, setMarkiert] = useState(0);
  const feld = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { darf } = useAuth();
  const begriff = text.trim();
  const treffer = useQuery({
    queryKey: ["suche", begriff],
    queryFn: () => api<ApiSeite<PatientZeile>>(`patienten/${abfrage({ suche: begriff, seitengroesse: 8, ordering: "nachname" })}`),
    enabled: !listenModus && begriff.length >= 2 && darf("akten_lesen"),
  });
  // Liste: Adresse übernimmt den Text verzögert; geänderte Adresse (z. B. „Filter zurücksetzen“) übernimmt das Feld
  const inAdresse = listenModus ? params.get("suche") ?? "" : "";
  const zuletzt = useRef(inAdresse);
  useEffect(() => {
    if (!listenModus) { setText(""); return; }
    if (inAdresse !== zuletzt.current) { zuletzt.current = inAdresse; setText(inAdresse); }
  }, [listenModus, inAdresse]);
  useEffect(() => {
    if (!listenModus) return;
    const t = window.setTimeout(() => {
      const jetzt = new URLSearchParams(window.location.search);
      if ((jetzt.get("suche") ?? "") === begriff) return;
      if (begriff) jetzt.set("suche", begriff); else jetzt.delete("suche");
      jetzt.delete("seite");
      zuletzt.current = begriff;
      setParams(jetzt, { replace: true });
    }, 300);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [begriff, listenModus]);
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
    onFertig?.();
    navigate(`/patienten/${p.id}`);
  };
  return (
    <div className={cx("relative", vollbreit ? "w-full" : "w-[25rem] max-w-[45vw]")}>
      <span className="absolute left-3 top-1/2 -translate-y-1/2 gedaempft pointer-events-none"><Icon name="suche" groesse={18} /></span>
      <input
        ref={feld}
        className="inp pl-10 pr-16"
        type="search"
        role={listenModus ? undefined : "combobox"}
        aria-expanded={listenModus ? undefined : offen && begriff.length >= 2}
        aria-controls={listenModus ? undefined : "suche-ergebnisse"}
        aria-label={listenModus ? "Liste filtern" : "Suchen"}
        placeholder={listenModus ? "Liste filtern: Name, Nr. oder Geburtsdatum" : "Patient suchen: Name, Nr. oder Geburtsdatum"}
        value={text}
        onChange={(e) => { setText(e.target.value); setOffen(true); }}
        autoFocus={vollbreit}
        onFocus={() => setOffen(true)}
        onBlur={() => window.setTimeout(() => setOffen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setMarkiert((m) => Math.min(m + 1, liste.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setMarkiert((m) => Math.max(m - 1, 0)); }
          if (e.key === "Enter" && listenModus) { e.preventDefault(); onFertig?.(); }
          if (e.key === "Enter" && !listenModus && liste[markiert]) { e.preventDefault(); oeffnen(liste[markiert]); }
          if (e.key === "Escape") { setOffen(false); onFertig?.(); }
        }}
      />
      <span className="max-md:hidden absolute right-2.5 top-1/2 -translate-y-1/2 font-mono text-[0.6875rem] font-medium gedaempft border border-rand rounded-[0.3125rem] px-1.5 py-0.5 pointer-events-none">
        Strg K
      </span>
      {!listenModus && offen && begriff.length >= 2 ? (
        <ul id="suche-ergebnisse" role="listbox" className="card absolute left-0 right-0 top-[calc(100%+0.375rem)] z-50 m-0 p-1 list-none max-h-96 overflow-auto">
          {treffer.isLoading ? <li className="px-3 py-2 text-sm gedaempft">Suche …</li> : null}
          {!treffer.isLoading && liste.length === 0 ? <li className="px-3 py-2 text-sm gedaempft">Kein Patient gefunden.</li> : null}
          {liste.map((p, i) => (
            <li key={p.id} role="option" aria-selected={i === markiert}
              className={cx("px-3 py-2 rounded-md cursor-pointer flex items-center gap-3 text-sm", i === markiert && "bg-akzent-weich")}
              onMouseDown={(e) => { e.preventDefault(); oeffnen(p); }} onMouseEnter={() => setMarkiert(i)}>
              <span className="num gedaempft">{nummer(p.nummer)}</span>
              <span className="font-medium min-w-0 truncate">{p.nachname}, {p.vorname}</span>
              <span className="gedaempft max-[23.75rem]:hidden">{datum(p.geburtsdatum)}</span>
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
    queryFn: () => api<{ hinweis: Hinweis | null }>("system/hinweis/", { hintergrund: true }),
    refetchInterval: 60_000,
    refetchIntervalInBackground: true,
    staleTime: 30_000,
  });
  const h = daten.data?.hinweis;
  if (!h || weg === h.id) return null;
  const warnung = h.art === "warnung";
  // Warnungen (Wartung, Update, Neustart, Wiederherstellen) groß und unübersehbar (Fehlerliste 02.10.2026, 4.3)
  return (
    <div role="region" aria-label="Hinweis der Administration" data-testid="systemhinweis" data-art={h.art}
      className={cx("nicht-drucken systemhinweis", warnung && "warnung")}>
      <Icon name={warnung ? "warnung" : "info"} groesse={warnung ? 34 : 18} strokeWidth={warnung ? 2 : 1.8} className={cx("shrink-0", !warnung && "mt-0.5")} />
      <span className="grow leading-normal">
        <strong className={cx("font-semibold", warnung && "systemhinweis-titel")}>{warnung ? "Wartung – Hinweis der Administration" : "Hinweis der Administration: "}</strong>
        {h.text}
        {h.angelegt_von_name ? <span className="opacity-80"> – {h.angelegt_von_name}, {zeitpunkt(h.angelegt_am)}</span> : null}
      </span>
      <button type="button" className={cx("btn shrink-0", warnung ? "sec" : "geist klein")} onClick={() => { ausgeblendeterHinweis = h.id; setWeg(h.id); }}
        aria-label="Hinweis ausblenden">Ausblenden</button>
    </div>
  );
}

export type Pfadteil = { text: string; zu?: string };

/** Kopfzeile + Inhalt einer Seite. Der Inhalt nutzt die volle Fensterbreite (S16, Festlegung 01.10.2026); die Seiten
 *  teilen sich in Stufen auf (lib/stufen.ts). Das „?“ führt zum passenden Abschnitt der Hilfe (S15). */
export function Seite({ pfad, children, className, fuellen }: { pfad: Pfadteil[]; children: ReactNode; className?: string;
  /** Seite füllt das Fenster und scrollt nicht als Ganzes (Patientenakte, 10.10.2026): Kopf und Reiter bleiben stehen,
   *  gescrollt wird nur in Karten bzw. Spalten. Gilt ab 1280 × 600 px mit Maus (index.css, .seite-fuellt); darunter und
   *  auf Tablets scrollt die Seite. */
  fuellen?: boolean }) {
  const ich = useIch();
  const { pathname } = useLocation();
  const [suchen, setSuchen] = useState(false);
  const mobil = useMobil();
  useEffect(() => {
    document.title = `${pfad[pfad.length - 1]?.text ?? "Start"} · EPM`;
  }, [pfad]);
  useEffect(() => setSuchen(false), [pathname]);
  // Telefon: nur der letzte Teil des Pfads, davor ein Schritt zurück
  const zurueck = [...pfad].slice(0, -1).reverse().find((t) => t.zu);
  return (
    <div className={cx("grow min-w-0 flex flex-col min-h-screen", fuellen && "seite-fuellt")}>
      {mobil ? <header data-leiste className="sticky top-0 z-20 shrink-0 bg-leiste border-b border-rand nicht-drucken pt-[env(safe-area-inset-top)]"
        data-testid="mobil-kopf">
        <div className="h-14 flex items-center gap-1 px-2">
          {zurueck ? (
            <Link to={zurueck.zu!} className="btn icon geist shrink-0" aria-label={`Zurück: ${zurueck.text}`}><Icon name="zurueck" groesse={20} /></Link>
          ) : <span className="w-2 shrink-0" />}
          <span className="grow min-w-0 truncate font-semibold text-[0.9375rem]" aria-current="page">{pfad[pfad.length - 1]?.text}</span>
          {ich.ist_test ? <Chip art="warn">Test</Chip> : null}
          {(ich.firmen?.length ?? 0) > 1 ? <Chip data-testid="mobil-firma">{ich.firmen?.find((f) => f.kuerzel === ich.firma)?.kurzname}</Chip> : null}
          <button type="button" className="btn icon geist shrink-0" aria-label="Patient suchen" aria-expanded={suchen}
            onClick={() => setSuchen((s) => !s)} data-testid="mobil-suche"><Icon name={suchen ? "x" : "suche"} groesse={20} /></button>
          {pathname !== "/hilfe" ? (
            <Link to={`/hilfe?seite=${encodeURIComponent(pathname)}`} className="btn icon geist shrink-0" aria-label="Hilfe zu dieser Seite">
              <Icon name="hilfe" groesse={20} /></Link>
          ) : null}
        </div>
        {suchen ? <div className="px-3 pb-3"><Suche vollbreit onFertig={() => setSuchen(false)} /></div> : null}
      </header> : null}
      {mobil ? null : <header data-leiste className="h-[3.75rem] shrink-0 flex items-center justify-between gap-6 px-4 bg-leiste border-b border-rand nicht-drucken">
        <nav aria-label="Pfad" className="flex items-center gap-2.5 text-sm min-w-0">
          {pfad.map((t, i) => (
            <span key={i} className="flex items-center gap-2.5 min-w-0">
              {i > 0 ? <span className="gedaempft">/</span> : null}
              {t.zu && i < pfad.length - 1 ? <Link to={t.zu} className="no-underline text-text2 hover:text-tinte">{t.text}</Link>
                : <span className={cx(i === pfad.length - 1 && "font-semibold", "truncate")} aria-current={i === pfad.length - 1 ? "page" : undefined}>{t.text}</span>}
            </span>
          ))}
        </nav>
        <div className="flex items-center gap-2.5">
          <Suche />
          {pathname !== "/hilfe" ? (
            <Link to={`/hilfe?seite=${encodeURIComponent(pathname)}`} className="btn icon geist" aria-label="Hilfe zu dieser Seite"
              title="Hilfe zu dieser Seite" data-testid="hilfe-zur-seite"><Icon name="hilfe" groesse={20} /></Link>
          ) : null}
          {ich.ist_test ? <Chip art="warn" data-testid="testzugang">Testzugang</Chip> : null}
        </div>
      </header>}
      <Systemhinweis />
      <main className={cx("seite-inhalt grow min-h-0 min-w-0 w-full px-3 sm:px-4 schmal:px-8 py-4 md:py-7 flex flex-col gap-4 md:gap-5 max-md:pb-24", className)}>{children}</main>
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
  const mobil = useMobil();
  return (
    <div className="flex min-h-screen bg-grund">
      <Ladebalken />
      <Seitenleiste />
      <Outlet />
      {mobil ? <MobilLeiste /> : null}
    </div>
  );
}
