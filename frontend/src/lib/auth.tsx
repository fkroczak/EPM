/** Anmeldestatus und eigener Benutzer; wendet die Darstellung der Person an. */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ABGEMELDET, api } from "./api";
import { darstellungAnwenden } from "./darstellung";
import type { Ich, Recht, Status } from "./typen";

type AuthWert = {
  status: Status | null;
  ich: Ich | null;
  laedt: boolean;
  setStatus: (s: Status) => void;
  setIch: (ich: Ich) => void;
  neuLaden: () => Promise<void>;
  abmelden: () => Promise<void>;
  darf: (recht: Recht) => boolean;
};

const AuthKontext = createContext<AuthWert | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatusRoh] = useState<Status | null>(null);
  const [laedt, setLaedt] = useState(true);
  const queryClient = useQueryClient();

  const setStatus = useCallback((s: Status) => {
    setStatusRoh(s);
    darstellungAnwenden(s.schritt === "fertig" ? s.benutzer?.darstellung : null);
  }, []);

  const neuLaden = useCallback(async () => {
    try {
      setStatus(await api<Status>("auth/status/", { ohneAbmeldeSignal: true }));
    } catch {
      setStatusRoh({ schritt: "anmelden" });
    } finally {
      setLaedt(false);
    }
  }, [setStatus]);

  useEffect(() => {
    void neuLaden();
    const abgemeldet = () => {
      queryClient.clear();
      void neuLaden();
    };
    window.addEventListener(ABGEMELDET, abgemeldet);
    return () => window.removeEventListener(ABGEMELDET, abgemeldet);
  }, [neuLaden, queryClient]);

  const abmelden = useCallback(async () => {
    try {
      await api("auth/abmelden/", { method: "POST", ohneAbmeldeSignal: true });
    } finally {
      queryClient.clear();
      await neuLaden();
    }
  }, [neuLaden, queryClient]);

  const ich = status?.schritt === "fertig" ? status.benutzer ?? null : null;
  const setIch = useCallback((neu: Ich) => {
    setStatusRoh((s) => (s ? { ...s, benutzer: neu } : s));
    darstellungAnwenden(neu.darstellung);
  }, []);
  const darf = useCallback((recht: Recht) => !!ich?.rechte.includes(recht), [ich]);

  return (
    <AuthKontext.Provider value={{ status, ich, laedt, setStatus, setIch, neuLaden, abmelden, darf }}>
      {children}
    </AuthKontext.Provider>
  );
}

export function useAuth(): AuthWert {
  const wert = useContext(AuthKontext);
  if (!wert) throw new Error("AuthProvider fehlt");
  return wert;
}

/** Eigener Benutzer (nur innerhalb der angemeldeten Anwendung verwenden) */
export function useIch(): Ich {
  const { ich } = useAuth();
  if (!ich) throw new Error("Nicht angemeldet");
  return ich;
}
