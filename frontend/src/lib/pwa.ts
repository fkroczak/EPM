/**
 * EPM als App (PWA, Festlegung 08.10.2026): Service Worker anmelden und die Installation anbieten.
 *
 * Der Service Worker (public/sw.js) speichert nur Programmdateien, nie Patientendaten. Er läuft nur in einem sicheren
 * Kontext mit gültigem Zertifikat – also über den Namen mit dem Zertifikat der eigenen CA, nicht über die IP-Adresse.
 */
import { useEffect, useState } from "react";

type InstallEreignis = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> };

let angebot: InstallEreignis | null = null;
const abonnenten = new Set<() => void>();
const melden = () => abonnenten.forEach((f) => f());

export function pwaStarten() {
  if (typeof window === "undefined") return;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();             // eigener Knopf unter Mein Konto statt der Leiste des Browsers
    angebot = e as InstallEreignis;
    melden();
  });
  window.addEventListener("appinstalled", () => { angebot = null; melden(); });
  if (import.meta.env.PROD && window.isSecureContext && "serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => undefined);   // z. B. Zertifikatsfehler
    });
  }
}

export function alsAppGeoeffnet(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export type Installation = {
  /** läuft gerade als installierte App */
  alsApp: boolean;
  /** der Browser bietet die Installation an (Chrome, Edge, Android) */
  kannInstallieren: boolean;
  /** iPhone/iPad: Installation nur über Teilen › Zum Home-Bildschirm */
  ios: boolean;
  installieren: () => Promise<boolean>;
};

export function useInstallation(): Installation {
  const [, neu] = useState(0);
  useEffect(() => {
    const f = () => neu((n) => n + 1);
    abonnenten.add(f);
    return () => { abonnenten.delete(f); };
  }, []);
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent)
    || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return {
    alsApp: alsAppGeoeffnet(),
    kannInstallieren: !!angebot,
    ios,
    installieren: async () => {
      if (!angebot) return false;
      const e = angebot;
      await e.prompt();
      const { outcome } = await e.userChoice;
      angebot = null;
      melden();
      return outcome === "accepted";
    },
  };
}
