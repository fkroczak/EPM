import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-serif/400-italic.css";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiFehler } from "./lib/api";
import { AuthProvider } from "./lib/auth";
import { HinweisProvider } from "./components/ui/hinweise";
import { App } from "./App";
import { tabellenFuerTelefon } from "./lib/tabellen";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 20_000,
      refetchOnWindowFocus: true,
      retry: (anzahl, fehler) => !(fehler instanceof ApiFehler && fehler.status < 500) && anzahl < 2,
    },
  },
});

tabellenFuerTelefon();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <HinweisProvider>
          <App />
        </HinweisProvider>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
