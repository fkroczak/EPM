/**
 * Reiter „Therapie“: Therapie, Empfehlung und Bemerkung als formatierte Texte mit Versionen.
 *
 * Seit der Aufteilung vom 07.10.2026 (F121) ein eigener Reiter; die Diagnosen stehen unter „Diagnosen“. Oben steht,
 * wann die Therapie zuletzt geändert wurde – damit beim Aufschlagen sofort sichtbar ist, wie alt sie ist.
 */
import { Link } from "react-router";
import { Icon } from "@/components/ui/icon";
import { RASTER_SPALTEN, useStufe } from "@/lib/stufen";
import { Bereich, Bereiche } from "@/components/ui/bereiche";
import { useAkte } from "./Akte";
import { TextKarte, ZuletztGeaendert } from "./TextKarte";

/** Im Raster mit einstellbarer Größe je Karte (Fehlerliste 02.10.2026, Punkt 2); die Therapie braucht Platz für
 *  lange Texte – Standard: doppelt so breit. */
export function Therapie() {
  const { patient } = useAkte();
  const stufe = useStufe();
  return (
    <div className="flex flex-col gap-3">
      <ZuletztGeaendert feld="therapie" />
      <Bereiche seite="akte_therapie" spalten={RASTER_SPALTEN[stufe]} testid="therapie-stufe">
        <Bereich id="therapie" titel="Therapie" standard={{ breite: 2 }}><TextKarte feld="therapie" immerOffen /></Bereich>
        <Bereich id="empfehlung" titel="Empfehlung"><TextKarte feld="empfehlung" /></Bereich>
        {/* seit 03.10.2026 sichtbar (Klärung U5) – u. a. Bemerkungen aus dem Altsystem */}
        <Bereich id="bemerkung" titel="Bemerkung"><TextKarte feld="bemerkung" /></Bereich>
        <Bereich id="hinweis" titel="Hinweis" menue={false}>
          <div className="meldung info flex gap-2.5 items-start text-[0.8125rem] leading-normal">
            <Icon name="info" />
            <span>Therapie, Empfehlung und Bemerkung sind änderbar. Jede Fassung bleibt mit Person, Datum und Uhrzeit im{" "}
              <Link to={`/patienten/${patient.id}/verlauf`}>Verlauf</Link> erhalten. Die Diagnosen stehen unter{" "}
              <Link to={`/patienten/${patient.id}/diagnosen`}>Diagnosen</Link>, die Kommunikation mit dem Patienten unter{" "}
              <Link to={`/patienten/${patient.id}/kontakte`}>Kontakte</Link>.</span>
          </div>
        </Bereich>
      </Bereiche>
    </div>
  );
}
