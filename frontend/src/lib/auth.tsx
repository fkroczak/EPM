/** Anmeldestatus und eigener Benutzer; wendet die Darstellung der Person an. */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ABGEMELDET, RECHTE_GEAENDERT, STATUS_PRUEFEN, api } from "./api";
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
  /** Recht für diesen Patienten: Admins schreiben Patientendaten nur bei Testpatienten */
  darfBei: (recht: Recht, patient: { ist_test: boolean }) => boolean;
};

/** Rechte, die Patientendaten verändern (siehe backend/accounts/rechte.py) */
const PATIENTENDATEN: Recht[] = ["eintraege_erfassen", "akten_bearbeiten", "plaene_anlegen", "plaene_freigeben", "akten_abschliessen"];

const AuthKontext = createContext<AuthWert | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatusRoh] = useState<Status | null>(null);
  const [laedt, setLaedt] = useState(true);
  const rechteRef = useRef<unknown>(null);
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
    // 401/403 ohne eindeutige Meldung: abmelden, wenn die Sitzung nicht mehr gilt; sonst Rechte aktualisieren
    const pruefen = async (): Promise<Status | null> => {
      try {
        const s = await api<Status>("auth/status/", { ohneAbmeldeSignal: true });
        if (s.schritt !== "fertig") queryClient.clear();
        setStatus(s);
        return s;
      } catch {
        return null; /* Netzwerkfehler: Zustand beibehalten */
      }
    };
    // Rechte geändert (Administration): neu laden; nur wenn sie sich wirklich geändert haben, alle Daten neu holen
    // (sonst könnte eine abgelehnte Anfrage eine Schleife aus Neuladen und Ablehnung auslösen)
    let laeuft = false;
    const rechteNeu = async () => {
      if (laeuft) return;
      laeuft = true;
      try {
        const vorher = JSON.stringify(rechteRef.current);
        const s = await pruefen();
        const b = s?.schritt === "fertig" ? s.benutzer : null;
        if (b && JSON.stringify([b.rechte, b.schreibt_nur_testpatienten, b.ist_test]) !== vorher) void queryClient.invalidateQueries();
      } finally {
        laeuft = false;
      }
    };
    window.addEventListener(ABGEMELDET, abgemeldet);
    const statusPruefen = () => void pruefen();
    window.addEventListener(STATUS_PRUEFEN, statusPruefen);
    window.addEventListener(RECHTE_GEAENDERT, rechteNeu);
    return () => {
      window.removeEventListener(ABGEMELDET, abgemeldet);
      window.removeEventListener(STATUS_PRUEFEN, statusPruefen);
      window.removeEventListener(RECHTE_GEAENDERT, rechteNeu);
    };
  }, [neuLaden, queryClient, setStatus]);

  const abmelden = useCallback(async () => {
    try {
      await api("auth/abmelden/", { method: "POST", ohneAbmeldeSignal: true });
    } finally {
      queryClient.clear();
      await neuLaden();
    }
  }, [neuLaden, queryClient]);

  const ich = status?.schritt === "fertig" ? status.benutzer ?? null : null;
  rechteRef.current = ich ? [ich.rechte, ich.schreibt_nur_testpatienten, ich.ist_test] : null;
  const setIch = useCallback((neu: Ich) => {
    setStatusRoh((s) => (s ? { ...s, benutzer: neu } : s));
    darstellungAnwenden(neu.darstellung);
  }, []);
  const darf = useCallback((recht: Recht) => !!ich?.rechte.includes(recht), [ich]);
  const darfBei = useCallback((recht: Recht, patient: { ist_test: boolean }) =>
    darf(recht) && (patient.ist_test || !ich?.schreibt_nur_testpatienten || !PATIENTENDATEN.includes(recht)), [darf, ich]);

  return (
    <AuthKontext.Provider value={{ status, ich, laedt, setStatus, setIch, neuLaden, abmelden, darf, darfBei }}>
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
