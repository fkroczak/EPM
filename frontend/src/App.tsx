import { createBrowserRouter, Link, RouterProvider } from "react-router";
import type { ReactNode } from "react";
import { useAuth } from "./lib/auth";
import type { Recht } from "./lib/typen";
import { Laden, Meldung } from "./components/ui/basis";
import { Seite, Shell } from "./components/layout/Shell";
import { Anmeldung } from "./seiten/Anmeldung";
import { Akte } from "./seiten/akte/Akte";
import { Dokumente } from "./seiten/akte/Dokumente";
import { Kontakte } from "./seiten/akte/Kontakte";
import { PlanEditor } from "./seiten/akte/PlanEditor";
import { Plaene } from "./seiten/akte/Plaene";
import { Therapie } from "./seiten/akte/Therapie";
import { Uebersicht } from "./seiten/akte/Uebersicht";
import { Verlauf } from "./seiten/akte/Verlauf";
import { AuditLog } from "./seiten/admin/AuditLog";
import { Benutzer } from "./seiten/admin/Benutzer";
import { Vorlagen } from "./seiten/admin/Vorlagen";
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

/** Seite nur mit dem passenden Recht (die API prüft zusätzlich jede Anfrage) */
function MitRecht({ recht, titel, children }: { recht: Recht; titel: string; children: ReactNode }) {
  const { darf } = useAuth();
  if (darf(recht)) return <>{children}</>;
  return (
    <Seite pfad={[{ text: titel }]}>
      <Meldung art="warn">Für „{titel}“ fehlt das Recht. Die Rechte der Gruppen legt die Administration unter „Benutzer“ fest.</Meldung>
    </Seite>
  );
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
          { path: "verlauf", element: <Verlauf /> },
        ],
      },
      { path: "versorger", element: <Versorger /> },
      { path: "aerzte", element: <Aerzte /> },
      { path: "konto", element: <Konto /> },
      { path: "admin/benutzer", element: <MitRecht recht="benutzer_verwalten" titel="Benutzer"><Benutzer /></MitRecht> },
      { path: "admin/vorlagen", element: <MitRecht recht="vorlagen_pflegen" titel="Vorlagen"><Vorlagen /></MitRecht> },
      { path: "admin/audit-log", element: <MitRecht recht="audit_lesen" titel="Audit-Log"><AuditLog /></MitRecht> },
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
