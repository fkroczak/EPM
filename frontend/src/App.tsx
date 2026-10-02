import { createBrowserRouter, Link, Navigate, RouterProvider } from "react-router";
import type { ReactNode } from "react";
import { useAuth } from "./lib/auth";
import type { Recht } from "./lib/typen";
import { Laden } from "./components/ui/basis";
import { Seite, Shell } from "./components/layout/Shell";
import { Anmeldung } from "./seiten/Anmeldung";
import { Akte } from "./seiten/akte/Akte";
import { AkteDatenschutz } from "./seiten/akte/Datenschutz";
import { Dokumente } from "./seiten/akte/Dokumente";
import { Kontakte } from "./seiten/akte/Kontakte";
import { PlanEditor } from "./seiten/akte/PlanEditor";
import { Plaene } from "./seiten/akte/Plaene";
import { Therapie } from "./seiten/akte/Therapie";
import { Uebersicht } from "./seiten/akte/Uebersicht";
import { Verlauf } from "./seiten/akte/Verlauf";
import { AuditLog } from "./seiten/admin/AuditLog";
import { Backup } from "./seiten/admin/Backup";
import { System } from "./seiten/admin/System";
import { Import } from "./seiten/admin/import/Import";
import { Infusionsplaene } from "./seiten/Infusionsplaene";
import { Kalender } from "./seiten/Kalender";
import { Benutzer } from "./seiten/admin/Benutzer";
import { Datenschutz } from "./seiten/Datenschutz";
import { Vorlagen } from "./seiten/admin/Vorlagen";
import { Hilfe } from "./seiten/Hilfe";
import { Konto } from "./seiten/Konto";
import { PatientNeu } from "./seiten/PatientNeu";
import { Patienten } from "./seiten/Patienten";
import { Start } from "./seiten/Start";
import { Versorger } from "./seiten/Versorger";
import { Aerzte } from "./seiten/Aerzte";

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

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { index: true, element: <Start /> },
      { path: "patienten", element: <Patienten /> },
      { path: "patienten/neu", element: <PatientNeu /> },
      {
        path: "patienten/:id",
        element: <Akte />,
        children: [
          { index: true, element: <Uebersicht /> },
          { path: "therapie", element: <Therapie /> },
          { path: "kontakte", element: <Kontakte /> },
          { path: "plaene", element: <Plaene /> },
          { path: "plaene/neu", element: <PlanEditor /> },
          { path: "plaene/:planId/bearbeiten", element: <PlanEditor key="bearbeiten" /> },
          { path: "dokumente", element: <Dokumente /> },
          { path: "datenschutz", element: <AkteDatenschutz /> },
          { path: "verlauf", element: <Verlauf /> },
        ],
      },
      { path: "kalender", element: <MitRecht recht="akten_lesen" titel="Kalender"><Kalender /></MitRecht> },
      { path: "infusionsplaene", element: <MitRecht recht="akten_lesen" titel="Infusionspläne"><Infusionsplaene /></MitRecht> },
      { path: "versorger", element: <Versorger /> },
      { path: "aerzte", element: <Aerzte /> },
      { path: "datenschutz", element: <MitRecht recht={["datenschutz_bearbeiten", "datenschutz_entscheiden"]}><Datenschutz /></MitRecht> },
      { path: "konto", element: <Konto /> },
      { path: "hilfe", element: <Hilfe /> },
      { path: "admin/backup", element: <MitRecht recht="backup_verwalten" titel="Backup"><Backup /></MitRecht> },
      { path: "admin/benutzer", element: <MitRecht recht="benutzer_verwalten" titel="Benutzer"><Benutzer /></MitRecht> },
      { path: "admin/vorlagen", element: <MitRecht recht="vorlagen_pflegen" titel="Vorlagen"><Vorlagen /></MitRecht> },
      { path: "admin/vorlagen/dokumente", element: <MitRecht recht="vorlagen_pflegen" titel="Dokumentvorlagen"><Vorlagen /></MitRecht> },
      { path: "admin/audit-log", element: <MitRecht recht="audit_lesen" titel="Audit-Log"><AuditLog /></MitRecht> },
      { path: "admin/system", element: <MitRecht recht="system_verwalten" titel="System"><System /></MitRecht> },
      { path: "admin/import", element: <MitRecht recht="altdaten_importieren" titel="Import"><Import /></MitRecht> },
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
