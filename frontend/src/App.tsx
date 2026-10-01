import { createBrowserRouter, Link, RouterProvider } from "react-router";
import { useAuth } from "./lib/auth";
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

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { index: true, element: <Start /> },
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
