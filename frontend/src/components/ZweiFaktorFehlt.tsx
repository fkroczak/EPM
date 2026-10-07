/**
 * Bestätigungen mit Passwort und Code (endgültig löschen, Wiederherstellen, Updates, Neustart, Sicherungs-Passwort,
 * Übertragungsziel, Import …) verlangen immer die Zwei-Faktor-Anmeldung (Festlegung 03.10.2026) – auch wenn die
 * Anmeldung selbst ohne sie erlaubt ist. Wer sie nicht eingerichtet hat, sieht diesen Hinweis; der Knopf zum
 * Bestätigen bleibt aus.
 */
import { Link } from "react-router";
import { useIch } from "@/lib/auth";
import { Meldung } from "@/components/ui/basis";

export function ZweiFaktorFehlt() {
  const ich = useIch();
  if (ich.zweiter_faktor) return null;
  return (
    <Meldung art="warn">
      <span data-testid="zweifaktor-fehlt">Für diese Bestätigung ist die Zwei-Faktor-Anmeldung nötig. Bitte zuerst unter{" "}
        <Link to="/konto#zwei-faktor">Mein Konto › Anmeldung und Sicherheit</Link> die Authenticator-App oder einen Passkey einrichten.</span>
    </Meldung>
  );
}
