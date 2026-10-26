import { createBrowserRouter, Link, Navigate, RouterProvider } from "react-router";
import type { ReactNode } from "react";
import { useAuth } from "./lib/auth";
import type { Recht } from "./lib/typen";
import { Laden } from "./components/ui/basis";
import { Seite, Shell } from "./components/layout/Shell";
import { Anmeldung } from "./seiten/Anmeldung";
import { Start } from "./seiten/Start";

function NichtGefunden() {
  return (
    <Seite pfad={[{ text: "Nicht gefunden" }]}>
      <h1 className="m-0 text-[1.625rem] font-semibold">Seite nicht gefunden</h1>
      <p className="m-0 text-sm">Diese Adresse gibt es im EPM nicht. <Link to="/">Zur Startseite</Link></p>
    </Seite>
  );
}

/** Seite nur mit dem passenden Recht (die API prüft zusätzlich jede Anfrage). Ohne Recht gibt es die Seite für
 *  diese Person nicht: weiter zur Startseite, ohne Hinweis auf Rechte (Festlegung 01.10.2026). */
function MitRecht({ recht, children }: { recht: Recht | Recht[]; titel?: string; children: ReactNode }) {
  const { darf } = useAuth();
  if ((Array.isArray(recht) ? recht : [recht]).some(darf)) return <>{children}</>;
  return <Navigate to="/" replace />;
}

/** Jede Seite als eigene Datei, geladen beim ersten Aufruf (Lighthouse 09.10.2026: vorher ein Paket mit 1,7 MB für
 *  alle Seiten, auch für die Anmeldung). Der Router wartet auf die Datei und zeigt solange die bisherige Seite. */
function seite(laden: () => Promise<ReactNode>) {
  return { lazy: async () => ({ element: await laden() }) };
}

const router = createBrowserRouter([
  {
    element: <Shell />,
    // erste Seite wird noch geladen (sonst Warnung „No HydrateFallback element“ in der Konsole)
    hydrateFallbackElement: <Laden text="EPM wird geladen …" />,
    children: [
      { index: true, element: <Start /> },
      { path: "patienten", ...seite(() => import("./seiten/Patienten").then(({ Patienten }) => <Patienten />)) },
      { path: "patienten/neu", ...seite(() => import("./seiten/PatientNeu").then(({ PatientNeu }) => <PatientNeu />)) },
      {
        path: "patienten/:id",
        ...seite(() => import("./seiten/akte/Akte").then(({ Akte }) => <Akte />)),
        children: [
          { index: true, ...seite(() => import("./seiten/akte/Uebersicht").then(({ Uebersicht }) => <Uebersicht />)) },
          // Ansicht „Karteikarte“ (Wunsch 08.10.2026): alle Einträge chronologisch mit Kürzelzeile
          { path: "kartei", ...seite(() => import("./seiten/akte/Karteikarte").then(({ Karteikarte }) => <Karteikarte />)) },
          // eigene Reiter seit 07.10.2026 (F121); die alten Adressen leiten weiter
          { path: "diagnosen", ...seite(() => import("./seiten/akte/Diagnosen").then(({ Diagnosen }) => <Diagnosen />)) },
          // Medikamentenplan (Wunsch 11.10.2026)
          { path: "medikamente", ...seite(() => import("./seiten/akte/Medikamente").then(({ Medikamente }) => <Medikamente />)) },
          { path: "therapie", ...seite(() => import("./seiten/akte/Therapie").then(({ Therapie }) => <Therapie />)) },
          { path: "empfehlung", ...seite(() => import("./seiten/akte/Therapie").then(({ Empfehlung }) => <Empfehlung />)) },
          { path: "kontakte", ...seite(() => import("./seiten/akte/Kontakte").then(({ Kontakte }) => <Kontakte />)) },
          { path: "plaene", ...seite(() => import("./seiten/akte/Plaene").then(({ Plaene }) => <Plaene />)) },
          { path: "plaene/neu", ...seite(() => import("./seiten/akte/PlanEditor").then(({ PlanEditor }) => <PlanEditor />)) },
          { path: "plaene/:planId/bearbeiten", ...seite(() => import("./seiten/akte/PlanEditor").then(({ PlanEditor }) => <PlanEditor key="bearbeiten" />)) },
          { path: "labor", ...seite(() => import("./seiten/akte/Labor").then(({ Labor }) => <Labor />)) },
          { path: "bia", ...seite(() => import("./seiten/akte/Bia").then(({ Bia }) => <Bia />)) },
          { path: "befunde", element: <Navigate to="../labor" replace /> },
          { path: "berichte", ...seite(() => import("./seiten/akte/Berichte").then(({ Berichte }) => <Berichte />)) },
          { path: "korrespondenz", ...seite(() => import("./seiten/akte/Korrespondenz").then(({ Korrespondenz }) => <Korrespondenz />)) },
          { path: "dokumente", ...seite(() => import("./seiten/akte/Dokumente").then(({ Dokumente }) => <Dokumente />)) },
          { path: "datenschutz", ...seite(() => import("./seiten/akte/Datenschutz").then(({ AkteDatenschutz }) => <AkteDatenschutz />)) },
          { path: "verlauf", ...seite(() => import("./seiten/akte/Verlauf").then(({ Verlauf }) => <Verlauf />)) },
          // KI (Experimentell, 14.10.2026): Hinweise Labor ↔ Infusionsplan, Dokumente in der KI, Berichtsentwurf
          { path: "ki", ...seite(() => import("./seiten/akte/KiAkte").then(({ KiAkte }) => <MitRecht recht="ki_ansehen"><KiAkte /></MitRecht>)) },
        ],
      },
      { path: "kalender", ...seite(() => import("./seiten/Kalender").then(({ Kalender }) => <MitRecht recht="akten_lesen" titel="Kalender"><Kalender /></MitRecht>)) },
      { path: "infusionsplaene", ...seite(() => import("./seiten/Infusionsplaene").then(({ Infusionsplaene }) => <MitRecht recht="akten_lesen" titel="Infusionspläne"><Infusionsplaene /></MitRecht>)) },
      { path: "versorger", ...seite(() => import("./seiten/Versorger").then(({ Versorger }) => <Versorger />)) },
      { path: "aerzte", ...seite(() => import("./seiten/Aerzte").then(({ Aerzte }) => <Aerzte />)) },
      { path: "datenschutz", ...seite(() => import("./seiten/Datenschutz").then(({ Datenschutz }) => <MitRecht recht={["datenschutz_bearbeiten", "datenschutz_entscheiden"]}><Datenschutz /></MitRecht>)) },
      // Diktate fürs Sekretariat (23.10.2026)
      { path: "diktate", ...seite(() => import("./seiten/Diktate").then(({ Diktate }) => <MitRecht recht={["eintraege_erfassen", "diktieren"]} titel="Diktate"><Diktate /></MitRecht>)) },
      { path: "scans", ...seite(() => import("./seiten/scans/Scans").then(({ Scans }) => <MitRecht recht="scans_bearbeiten" titel="Scans"><Scans /></MitRecht>)) },
      // KI (Experimentell, 14.10.2026): Prüf-Queue, Prüfansicht, Qualität
      { path: "ki", ...seite(() => import("./seiten/ki/KiQueue").then(({ KiQueue }) => <MitRecht recht="ki_ansehen" titel="KI (Experimentell)"><KiQueue /></MitRecht>)) },
      { path: "ki/:id", ...seite(() => import("./seiten/ki/KiPruefung").then(({ KiPruefung }) => <MitRecht recht="ki_ansehen" titel="KI (Experimentell)"><KiPruefung /></MitRecht>)) },
      { path: "konto", ...seite(() => import("./seiten/Konto").then(({ Konto }) => <Konto />)) },
      { path: "design", ...seite(() => import("./seiten/Konto").then(({ Design }) => <Design />)) },
      { path: "hilfe", ...seite(() => import("./seiten/Hilfe").then(({ Hilfe }) => <Hilfe />)) },
      // Systemverwaltung: Zustand auf einen Blick und häufige Aufgaben (Wunsch 10.10.2026, F179)
      { path: "admin", ...seite(() => import("./seiten/admin/Verwaltung").then(({ Verwaltung }) => <MitRecht recht={["system_verwalten", "backup_verwalten"]} titel="Systemverwaltung"><Verwaltung /></MitRecht>)) },
      { path: "admin/backup", ...seite(() => import("./seiten/admin/Backup").then(({ Backup }) => <MitRecht recht="backup_verwalten" titel="Backup"><Backup /></MitRecht>)) },
      { path: "admin/benutzer", ...seite(() => import("./seiten/admin/Benutzer").then(({ Benutzer }) => <MitRecht recht="benutzer_verwalten" titel="Benutzer"><Benutzer /></MitRecht>)) },
      { path: "admin/vorlagen", ...seite(() => import("./seiten/admin/Vorlagen").then(({ Vorlagen }) => <MitRecht recht="vorlagen_pflegen" titel="Vorlagen"><Vorlagen /></MitRecht>)) },
      { path: "admin/vorlagen/dokumente", ...seite(() => import("./seiten/admin/Vorlagen").then(({ Vorlagen }) => <MitRecht recht="vorlagen_pflegen" titel="Dokumentvorlagen"><Vorlagen /></MitRecht>)) },
      { path: "admin/audit-log", ...seite(() => import("./seiten/admin/AuditLog").then(({ AuditLog }) => <MitRecht recht="audit_lesen" titel="Audit-Log"><AuditLog /></MitRecht>)) },
      { path: "admin/system", ...seite(() => import("./seiten/admin/System").then(({ System }) => <MitRecht recht="system_verwalten" titel="System"><System /></MitRecht>)) },
      { path: "admin/ki", ...seite(() => import("./seiten/admin/KiVerwaltung").then(({ KiVerwaltung }) => <MitRecht recht="ki_verwalten" titel="KI (Experimentell)"><KiVerwaltung /></MitRecht>)) },
      { path: "admin/import", ...seite(() => import("./seiten/admin/import/Import").then(({ Import }) => <MitRecht recht="altdaten_importieren" titel="Import"><Import /></MitRecht>)) },
      { path: "*", element: <NichtGefunden /> },
    ],
  },
]);

export function App() {
  const { status, laedt } = useAuth();
  if (laedt) return <Laden text="EPM wird geladen …" />;
  if (status?.schritt !== "fertig") return <Anmeldung />;
  return <RouterProvider router={router} />;
}
