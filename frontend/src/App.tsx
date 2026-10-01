import { createBrowserRouter, Link, RouterProvider } from "react-router";
import { useAuth } from "./lib/auth";
import { Laden } from "./components/ui/basis";
import { Seite, Shell } from "./components/layout/Shell";
import { Anmeldung } from "./seiten/Anmeldung";
import { Akte } from "./seiten/akte/Akte";
import { Kontakte } from "./seiten/akte/Kontakte";
import { PlanEditor } from "./seiten/akte/PlanEditor";
import { Plaene } from "./seiten/akte/Plaene";
import { Therapie } from "./seiten/akte/Therapie";
import { Uebersicht } from "./seiten/akte/Uebersicht";
import { PatientNeu } from "./seiten/PatientNeu";
import { Patienten } from "./seiten/Patienten";
import { Start } from "./seiten/Start";
import { Versorger } from "./seiten/Versorger";

function NichtGefunden() {
  return (
    <Seite pfad={[{ text: "Nicht gefunden" }]}>
      <h1 className="m-0 text-[1.625rem] font-semibold">Seite nicht gefunden</h1>
      <p className="m-0 text-sm">Diese Adresse gibt es im EPM nicht. <Link to="/">Zur Startseite</Link></p>
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
        ],
      },
      { path: "versorger", element: <Versorger /> },
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
