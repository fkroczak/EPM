/**
 * Zweiter Faktor bei Bestätigungen (endgültig löschen, Wiederherstellen, Updates, Neustart, Import, Sicherung …):
 * Code aus der Authenticator-App (ggf. Notfall-Code) oder – Festlegung 08.10.2026 – ein Passkey.
 *
 *   const zf = useZweiterFaktor();
 *   …{zf.feld(f.code)}…
 *   api(…, { body: { kennwort, ...zf.body } })   // {code} oder {passkey}
 *   <Knopf disabled={!kennwort || !zf.bereit}>
 *
 * Mit Passkey: Tippen auf „Mit Passkey bestätigen“ fragt Fingerabdruck, Gesicht oder PIN ab; die Antwort gilt einmal
 * und wird mit dem Formular geschickt. Lehnt der Server den zweiten Faktor ab, muss neu bestätigt werden.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { PasskeyVorrat, passkeyBenutzen, passkeyHindernis } from "@/lib/passkey";
import type { PasskeyAntwort } from "@/lib/passkey";
import { Eingabe, Feld, Knopf, Meldung, Segmente } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";

type Art = "passkey" | "code";

export type ZweiterFaktorWert = {
  /** Code eingegeben bzw. Passkey bestätigt */
  bereit: boolean;
  /** Teil des Anfragekörpers: ``{code}`` oder ``{passkey}`` */
  body: { code: string } | { passkey: PasskeyAntwort };
  /** das Eingabefeld (Fehler des Servers zu „code“ übergeben) */
  feld: (fehler?: string) => ReactNode;
  zuruecksetzen: () => void;
};

export function useZweiterFaktor({ notfallcodes = true, label = "Code aus der Authenticator-App" }:
  { notfallcodes?: boolean; label?: string } = {}): ZweiterFaktorWert {
  const { ich, status } = useAuth();
  const hindernis = passkeyHindernis(status?.passkey);
  const passkeyGeht = !!ich?.passkey && !hindernis;
  const hatApp = ich?.authenticator ?? ich?.zweiter_faktor ?? false;
  const [art, setArt] = useState<Art>(passkeyGeht ? "passkey" : "code");
  const [code, setCode] = useState("");
  const [antwort, setAntwort] = useState<PasskeyAntwort | null>(null);
  useEffect(() => { if (art === "passkey" && !passkeyGeht) setArt("code"); }, [art, passkeyGeht]);
  const zuruecksetzen = () => { setCode(""); setAntwort(null); };
  return {
    bereit: art === "passkey" ? !!antwort : !!code.trim(),
    body: art === "passkey" && antwort ? { passkey: antwort } : { code: code.trim() },
    zuruecksetzen,
    feld: (fehler) => (
      <ZweiterFaktorFeld art={art} setArt={setArt} code={code} setCode={setCode} antwort={antwort} setAntwort={setAntwort}
        fehler={fehler} passkeyGeht={passkeyGeht} hatApp={hatApp} hatPasskey={!!ich?.passkey} hindernis={hindernis}
        notfallcodes={notfallcodes} label={label} />
    ),
  };
}

function ZweiterFaktorFeld({ art, setArt, code, setCode, antwort, setAntwort, fehler, passkeyGeht, hatApp, hatPasskey,
  hindernis, notfallcodes, label }: {
  art: Art; setArt: (a: Art) => void; code: string; setCode: (c: string) => void; antwort: PasskeyAntwort | null;
  setAntwort: (a: PasskeyAntwort | null) => void; fehler?: string; passkeyGeht: boolean; hatApp: boolean;
  hatPasskey: boolean; hindernis: string; notfallcodes: boolean; label: string;
}) {
  const vorrat = useRef(new PasskeyVorrat("bestaetigen"));
  const [laeuft, setLaeuft] = useState(false);
  const [problem, setProblem] = useState("");
  useEffect(() => { if (art === "passkey" && !antwort) vorrat.current.vorbereiten(); }, [art, antwort]);
  // abgelehnt: Die Antwort ist verbraucht, also neu bestätigen
  useEffect(() => { if (fehler) setAntwort(null); }, [fehler]); // eslint-disable-line react-hooks/exhaustive-deps

  const bestaetigen = async () => {
    setLaeuft(true);
    setProblem("");
    try {
      setAntwort(await passkeyBenutzen(await vorrat.current.holen()));
    } catch (e) {
      setProblem(e instanceof Error ? e.message : String(e));
    } finally {
      setLaeuft(false);
    }
  };

  return (
    <div className="flex flex-col gap-2 min-w-0" data-testid="zweiter-faktor">
      {passkeyGeht && (hatApp || notfallcodes) ? (
        <Segmente label="Zweiter Faktor" wert={art} onWahl={(a) => { setArt(a); setProblem(""); }}
          werte={[{ wert: "passkey", text: "Passkey" }, { wert: "code", text: hatApp ? "Code" : "Notfall-Code" }]} />
      ) : null}
      {art === "passkey" ? (
        <div className="feld">
          <span>Passkey</span>
          {antwort ? (
            <span className="flex items-center gap-2 min-h-10 text-sm" data-testid="passkey-bestaetigt">
              <Icon name="haken" className="text-ok" /> Passkey bestätigt
              <Knopf klein variante="geist" onClick={() => setAntwort(null)}>Erneut</Knopf>
            </span>
          ) : (
            <Knopf icon="passkey" laedt={laeuft} onClick={() => void bestaetigen()} className="w-full sm:w-auto"
              data-testid="passkey-bestaetigen">Mit Passkey bestätigen</Knopf>
          )}
          {fehler ? <span className="fehlertext" role="alert">{fehler}</span>
            : problem ? <span className="fehlertext" role="alert">{problem}</span>
              : <span className="hinweis">Fingerabdruck, Gesicht oder PIN am Gerät</span>}
        </div>
      ) : (
        <Feld label={hatApp ? label : "Notfall-Code"} hinweis={hatApp && notfallcodes ? "oder ein Notfall-Code" : undefined}
          fehler={fehler} pflicht>
          {(p) => <Eingabe {...p} inputMode="text" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
        </Feld>
      )}
      {hatPasskey && !passkeyGeht && hindernis ? <Meldung art="info" className="text-[0.8125rem]">{hindernis}</Meldung> : null}
    </div>
  );
}
