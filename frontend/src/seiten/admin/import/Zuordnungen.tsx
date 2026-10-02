/**
 * Administration › Import › Zuordnungen: Was das Werkzeug aus dem Dump erkannt hat – und wo die Administration
 * korrigiert. Jede Änderung wird sofort gespeichert; „Vorschlag“ nimmt eine Entscheidung zurück. Die Zuordnungen
 * bleiben unabhängig vom Dump erhalten und gelten für den frischen Dump zum Go-live weiter.
 */
import { useEffect, useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { datum, zahl } from "@/lib/format";
import { ROLLEN } from "@/lib/typen";
import { Auswahl, Chip, Eingabe, Karte, KartenKopf, Knopf, Leer, Meldung, Segmente, cx } from "@/components/ui/basis";
import { Icon } from "@/components/ui/icon";
import type { Aenderung, Auffaelligkeit, Benutzerzeile, Bestand, BenutzerWahl, Entscheidungsart, GeloeschtWahl, KatheterWahl,
  Offen, PraeparatWahl, Praeparatfeld, Praeparatzeile, VersorgerWahl, Zuordnung, Zuordnungsstand } from "./typen";

type Speichern = (a: Aenderung) => void;
type Teil = Offen["bereich"];

/** Texteingabe, die erst beim Verlassen des Felds (oder mit Enter) speichert */
function Texteingabe({ wert, onFertig, ...rest }: { wert: string; onFertig: (text: string) => void }
  & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const [text, setText] = useState(wert);
  useEffect(() => { setText(wert); }, [wert]);
  return (
    <Eingabe {...rest} value={text} onChange={(e) => setText(e.target.value)}
      onBlur={() => { if (text.trim() !== wert) onFertig(text.trim()); }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
  );
}

function Zustand({ offen, entschieden }: { offen: boolean; entschieden: boolean }) {
  if (offen) return <Chip art="warn"><Icon name="warnung" />offen</Chip>;
  return entschieden ? <Chip art="akzent">zugeordnet</Chip> : <Chip art="ok">erkannt</Chip>;
}

function Zurueck({ zeigen, onClick, name }: { zeigen: boolean; onClick: () => void; name: string }) {
  if (!zeigen) return null;
  return <Knopf klein variante="geist" onClick={onClick} aria-label={`Vorschlag für ${name}`} title="Entscheidung zurücknehmen – es gilt wieder der Vorschlag">Vorschlag</Knopf>;
}

function Fehlertext({ text }: { text: string }) {
  return text ? <span className="text-[0.8125rem] text-fehler" role="alert">{text}</span> : null;
}

// ---------------------------------------------------------------- Tabellen und Spalten
function Spalten({ stand, speichern, laeuft }: { stand: Zuordnungsstand; speichern: Speichern; laeuft: boolean }) {
  const q = stand.quelle;
  const ignorierteTabellen = q.uebrig.filter((u) => u.art === "ignoriert").map((u) => u.tabelle);
  return (
    <div className="flex flex-col gap-5">
      {q.tabellen.map((t) => {
        const ignoriert = t.rest.filter((r) => r.art === "ignoriert").map((r) => r.spalte);
        return (
          <Karte key={t.name} className="px-5 py-4 flex flex-col gap-3" data-testid={`quelle-${t.name}`}>
            <KartenKopf titel={`${t.titel} → ${t.ziel}`}
              unter={t.tabelle ? `${zahl(t.zeilen)} Zeilen in der Tabelle „${t.tabelle}“` : t.art === "ohne" ? "bewusst nicht vorhanden" : "im Dump nicht gefunden"}
              rechts={
                <Auswahl aria-label={`Tabelle im Dump für ${t.titel}`} className="w-[240px]"
                  value={t.art === "ohne" ? "__ohne" : t.tabelle ?? ""}
                  onChange={(e) => speichern({ bereich: "tabellen", aenderungen: { [t.name]: e.target.value === "__ohne" ? "" : e.target.value || null } })}>
                  {t.tabelle ? null : <option value="">— bitte zuordnen —</option>}
                  {q.im_dump.map((n) => <option key={n} value={n}>{n}</option>)}
                  <option value="__ohne">im Dump nicht vorhanden</option>
                </Auswahl>} />
            {t.tabelle ? (
              <table className="tabelle">
                <thead><tr><th className="th">Angabe im EPM</th><th className="th w-[260px]">Spalte im Dump</th><th className="th w-[130px]" /><th className="th">Hinweis</th></tr></thead>
                <tbody>
                  {t.felder.map((f) => (
                    <tr key={f.name}>
                      <td className="td">{f.titel}{f.pflicht ? <span aria-hidden="true"> *</span> : null}</td>
                      <td className="td">
                        <Auswahl aria-label={`Spalte für ${t.titel}: ${f.titel}`} value={f.spalte ?? ""}
                          aria-invalid={f.pflicht && !f.spalte ? true : undefined}
                          onChange={(e) => speichern({ bereich: "spalten", aenderungen: { [t.name]: { [f.name]: e.target.value } } })}>
                          <option value="">— keine —</option>
                          {t.spalten.map((s) => <option key={s} value={s}>{s}</option>)}
                        </Auswahl>
                      </td>
                      <td className="td whitespace-nowrap">
                        {f.art === "fehlt" ? <Chip art={f.pflicht ? "fehler" : "neutral"}>{f.pflicht ? "fehlt" : "nicht im Dump"}</Chip>
                          : f.art === "ohne" ? <Chip>bewusst leer</Chip>
                          : <Zustand offen={false} entschieden={f.art === "gewaehlt"} />}
                        <Zurueck zeigen={f.art === "gewaehlt" || f.art === "ohne"} name={`${t.titel}: ${f.titel}`}
                          onClick={() => speichern({ bereich: "spalten", aenderungen: { [t.name]: { [f.name]: null } } })} />
                      </td>
                      <td className="td text-[0.8125rem] gedaempft">{f.hinweis}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
            {t.rest.length ? (
              <div className="flex flex-col gap-1.5">
                <span className="lbl">Weitere Spalten der Tabelle</span>
                {t.rest.map((r) => (
                  <div key={r.spalte} className="flex items-center gap-2.5 text-sm flex-wrap" data-testid={`rest-${t.name}-${r.spalte}`}>
                    <span className="num">{r.spalte}</span>
                    {r.art === "offen" ? <Chip art="warn"><Icon name="warnung" />nicht zugeordnet</Chip> : <Chip>wird nicht übernommen</Chip>}
                    <span className="text-[0.8125rem] gedaempft">{r.grund}</span>
                    {r.art === "offen" ? <Knopf klein disabled={laeuft} onClick={() => speichern({ bereich: "spalten_ignoriert", aenderungen: { [t.name]: [...ignoriert, r.spalte] } })}
                      aria-label={`Spalte ${r.spalte} nicht übernehmen`}>Nicht übernehmen</Knopf> : null}
                    {r.art === "ignoriert" ? <Knopf klein variante="geist" disabled={laeuft} onClick={() => speichern({ bereich: "spalten_ignoriert",
                      aenderungen: { [t.name]: ignoriert.filter((s) => s !== r.spalte) } })}>Zurücknehmen</Knopf> : null}
                  </div>
                ))}
              </div>
            ) : null}
          </Karte>
        );
      })}
      {q.uebrig.length ? (
        <Karte className="px-5 py-4 flex flex-col gap-2" data-testid="quelle-uebrig">
          <KartenKopf titel="Weitere Tabellen im Dump" unter="Tabellen, die das Werkzeug keiner Angabe im EPM zuordnen kann." />
          {q.uebrig.map((u) => (
            <div key={u.tabelle} className="flex items-center gap-2.5 text-sm flex-wrap">
              <span className="num">{u.tabelle}</span><span className="gedaempft">{zahl(u.zeilen)} Zeilen</span>
              {u.art === "offen" ? <Chip art="warn"><Icon name="warnung" />nicht zugeordnet</Chip> : <Chip>wird nicht übernommen</Chip>}
              {u.art === "offen"
                ? <Knopf klein disabled={laeuft} onClick={() => speichern({ bereich: "tabellen_ignoriert", aenderungen: [...ignorierteTabellen, u.tabelle] })}>Nicht übernehmen</Knopf>
                : <Knopf klein variante="geist" disabled={laeuft} onClick={() => speichern({ bereich: "tabellen_ignoriert",
                  aenderungen: ignorierteTabellen.filter((n) => n !== u.tabelle) })}>Zurücknehmen</Knopf>}
            </div>
          ))}
        </Karte>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- Benutzer
const BENUTZERART: Record<BenutzerWahl["art"], string> = {
  benutzer: "vorhandener Benutzer", konto: "neues Konto", historisch: "historischer Benutzer (ohne Login)", ohne: "ohne Bearbeiter übernehmen",
};

function BenutzerTeil({ stand, bestand, rollen, speichern }: { stand: Zuordnungsstand; bestand: Bestand; rollen: string[]; speichern: Speichern }) {
  const personen = bestand.benutzer.filter((b) => !b.ist_test);
  const setze = (b: Benutzerzeile, wahl: Partial<BenutzerWahl> | null) => speichern({ bereich: "benutzer", aenderungen: { [b.schluessel]: wahl } });
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="zuordnung-benutzer">
      <KartenKopf titel="Benutzer und Bearbeiter"
        unter="Namen aus der Benutzertabelle und aus „bearbeitet von“. Konten entstehen ohne Kennwort – danach unter Benutzer ein Einmal-Kennwort erzeugen. Historische Benutzer können sich nie anmelden; sie stehen nur als Bearbeiter an alten Einträgen." />
      {stand.benutzer.length === 0 ? <Leer>Im Dump kommen keine Benutzer vor.</Leer> : (
        <table className="tabelle">
          <thead><tr><th className="th">Im Altsystem</th><th className="th w-[90px]">Einträge</th><th className="th w-[250px]">Im EPM</th><th className="th">Angaben</th><th className="th w-[150px]" /></tr></thead>
          <tbody>
            {stand.benutzer.map((b) => {
              const w = b.wirksam;
              return (
                <tr key={b.schluessel} data-testid={`benutzer-${b.schluessel}`}>
                  <td className="td align-top">
                    <span className="num font-medium">{b.name}</span><br />
                    <span className="text-xs gedaempft">{b.im_altsystem_konto ? `Konto im Altsystem${b.rechte ? ` · Rechte ${b.rechte}` : ""}` : "nur als Bearbeiter genannt"}</span>
                  </td>
                  <td className="td align-top num" title={Object.entries(b.anzahl).map(([t, n]) => `${t}: ${n}`).join(", ")}>{zahl(b.eintraege)}</td>
                  <td className="td align-top">
                    <Auswahl aria-label={`Zuordnung für ${b.name}`} value={w.art}
                      onChange={(e) => {
                        const art = e.target.value as BenutzerWahl["art"];
                        setze(b, art === "benutzer" ? { art, id: b.aehnlich[0] ?? 0 } : { art });
                      }}>
                      {(Object.keys(BENUTZERART) as BenutzerWahl["art"][]).map((a) => <option key={a} value={a}>{BENUTZERART[a]}</option>)}
                    </Auswahl>
                  </td>
                  <td className="td align-top">
                    <div className="flex flex-col gap-1.5">
                      {w.art === "benutzer" ? (
                        <Auswahl aria-label={`Benutzer im EPM für ${b.name}`} value={personen.some((p) => p.id === w.id) ? w.id : 0}
                          onChange={(e) => setze(b, { art: "benutzer", id: Number(e.target.value) })}>
                          <option value={0}>— bitte wählen —</option>
                          {personen.map((p) => <option key={p.id} value={p.id}>{p.anzeigename} ({p.username}){p.nur_historisch ? " · ohne Login" : ""}</option>)}
                        </Auswahl>
                      ) : null}
                      {w.art === "konto" || w.art === "historisch" ? (
                        <div className="grid grid-cols-[1.3fr_0.8fr_1fr_1fr] gap-1.5">
                          <Texteingabe aria-label={`Benutzername für ${b.name}`} placeholder="Benutzername" wert={w.benutzername} onFertig={(t) => setze(b, { ...w, benutzername: t })} />
                          <Texteingabe aria-label={`Titel für ${b.name}`} placeholder="Titel" wert={w.titel} onFertig={(t) => setze(b, { ...w, titel: t })} />
                          <Texteingabe aria-label={`Vorname für ${b.name}`} placeholder="Vorname" wert={w.vorname} onFertig={(t) => setze(b, { ...w, vorname: t })} />
                          <Texteingabe aria-label={`Nachname für ${b.name}`} placeholder="Nachname" wert={w.nachname} onFertig={(t) => setze(b, { ...w, nachname: t })} />
                        </div>
                      ) : null}
                      {w.art === "konto" ? (
                        <Auswahl aria-label={`Rolle für ${b.name}`} value={w.rolle} className="w-[200px]" onChange={(e) => setze(b, { ...w, rolle: e.target.value })}>
                          {rollen.includes(w.rolle) ? null : <option value="">— Rolle wählen —</option>}
                          {rollen.map((r) => <option key={r} value={r}>{ROLLEN[r] ?? r}</option>)}
                        </Auswahl>
                      ) : null}
                      <Fehlertext text={b.fehler} />
                    </div>
                  </td>
                  <td className="td align-top whitespace-nowrap">
                    <Zustand offen={!!b.fehler} entschieden={!!b.entscheidung} />
                    <Zurueck zeigen={!!b.entscheidung} name={b.name} onClick={() => setze(b, null)} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Karte>
  );
}

// ---------------------------------------------------------------- Versorger
const VERSORGERART: Record<VersorgerWahl["art"], string> = {
  neu: "neu anlegen", vorhanden: "vorhandener Versorger", kein: "bedeutet „kein Versorger“", leer: "nicht übernehmen (leer)",
};

function VersorgerTeil({ stand, bestand, speichern }: { stand: Zuordnungsstand; bestand: Bestand; speichern: Speichern }) {
  const setze = (schluessel: string, wahl: VersorgerWahl | null) => speichern({ bereich: "versorger", aenderungen: { [schluessel]: wahl } });
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="zuordnung-versorger">
      <KartenKopf titel="Versorger"
        unter="Im Altsystem ist jede Zeile eine Firma mit einer Person. Im EPM wird daraus ein Versorger mit Ansprechpartnern: gleiche Firma = ein Versorger." />
      {stand.versorger.length === 0 ? <Leer>Im Dump kommen keine Versorger vor.</Leer> : (
        <table className="tabelle">
          <thead><tr><th className="th w-[50px]">Nr.</th><th className="th">Im Altsystem</th><th className="th w-[90px]">Patienten</th><th className="th w-[230px]">Im EPM</th><th className="th">Versorger · Ansprechpartner</th><th className="th w-[150px]" /></tr></thead>
          <tbody>
            {stand.versorger.map((v) => {
              const w = v.wirksam;
              const ansprech = v.firma ? v.name : "";
              return (
                <tr key={v.schluessel} data-testid={`versorger-${v.schluessel}`}>
                  <td className="td align-top num">{v.schluessel}</td>
                  <td className="td align-top">
                    <span className="font-medium">{v.firma || v.name || "—"}</span>{v.firma && v.name ? <span> · {v.name}</span> : null}<br />
                    <span className="text-xs gedaempft">{[v.tel, v.email].filter(Boolean).join(" · ") || "ohne Telefon und E-Mail"}</span>
                  </td>
                  <td className="td align-top num">{zahl(v.patienten)}</td>
                  <td className="td align-top">
                    <Auswahl aria-label={`Zuordnung für Versorger ${v.schluessel}`} value={w.art}
                      onChange={(e) => {
                        const art = e.target.value as VersorgerWahl["art"];
                        setze(v.schluessel, art === "neu" ? { art, versorger: v.firma || v.name, ansprechpartner: ansprech }
                          : art === "vorhanden" ? { art, id: 0, ansprechpartner: ansprech } : { art });
                      }}>
                      {(Object.keys(VERSORGERART) as VersorgerWahl["art"][]).map((a) => <option key={a} value={a}>{VERSORGERART[a]}</option>)}
                    </Auswahl>
                  </td>
                  <td className="td align-top">
                    <div className="flex flex-col gap-1.5">
                      {w.art === "neu" || w.art === "vorhanden" ? (
                        <div className="grid grid-cols-2 gap-1.5">
                          {w.art === "neu" ? (
                            <Texteingabe aria-label={`Name des Versorgers ${v.schluessel}`} placeholder="Name des Versorgers" wert={w.versorger}
                              onFertig={(t) => setze(v.schluessel, { ...w, versorger: t })} />
                          ) : (
                            <Auswahl aria-label={`Versorger im EPM für ${v.schluessel}`} value={bestand.versorger.some((x) => x.id === w.id) ? w.id : 0}
                              onChange={(e) => setze(v.schluessel, { ...w, id: Number(e.target.value) })}>
                              <option value={0}>— bitte wählen —</option>
                              {bestand.versorger.map((x) => <option key={x.id} value={x.id}>{x.name}{x.aktiv ? "" : " (deaktiviert)"}</option>)}
                            </Auswahl>
                          )}
                          <Texteingabe aria-label={`Ansprechpartner für Versorger ${v.schluessel}`} placeholder="Ansprechpartner (leer = keiner)" wert={w.ansprechpartner}
                            onFertig={(t) => setze(v.schluessel, { ...w, ansprechpartner: t })} />
                        </div>
                      ) : null}
                      <Fehlertext text={v.fehler} />
                    </div>
                  </td>
                  <td className="td align-top whitespace-nowrap">
                    <Zustand offen={!!v.fehler} entschieden={!!v.entscheidung} />
                    <Zurueck zeigen={!!v.entscheidung} name={`Versorger ${v.schluessel}`} onClick={() => setze(v.schluessel, null)} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </Karte>
  );
}

// ---------------------------------------------------------------- Werte: Katheter, Nickelallergie, Geschlecht
const FESTE_WERTE: Record<"nickel" | "geschlecht", { titel: string; unter: string; werte: [string, string][] }> = {
  nickel: { titel: "Nickelallergie", unter: "Ohne Angabe gilt „unbekannt“ – die Akte zeigt dazu einen Hinweis.",
    werte: [["ja", "ja"], ["nein", "nein"], ["unbekannt", "unbekannt"]] },
  geschlecht: { titel: "Geschlecht", unter: "", werte: [["w", "weiblich"], ["m", "männlich"], ["d", "divers"], ["", "unbekannt"]] },
};

function WerteTeil({ stand, bestand, speichern }: { stand: Zuordnungsstand; bestand: Bestand; speichern: Speichern }) {
  const katheter = (schluessel: string, wahl: KatheterWahl | null) => speichern({ bereich: "werte", aenderungen: { katheter: { [schluessel]: wahl } } });
  return (
    <div className="flex flex-col gap-5">
      <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="zuordnung-katheter">
        <KartenKopf titel="Katheter" unter="Die Werte des Altsystems werden Einträge der Auswahlliste „Katheter“ (Vorlagen › Auswahllisten)." />
        <table className="tabelle">
          <thead><tr><th className="th">Im Altsystem</th><th className="th w-[90px]">Patienten</th><th className="th w-[300px]">Im EPM</th><th className="th" /><th className="th w-[150px]" /></tr></thead>
          <tbody>
            {stand.werte.katheter.map((k) => {
              const w = k.wirksam;
              const wert = w.art === "wert" ? `w:${w.id}` : w.art;
              return (
                <tr key={k.schluessel} data-testid={`katheter-${k.schluessel || "leer"}`}>
                  <td className="td">{k.text || <span className="gedaempft">(ohne Angabe)</span>}</td>
                  <td className="td num">{zahl(k.anzahl)}</td>
                  <td className="td">
                    <Auswahl aria-label={`Katheter im EPM für ${k.text || "ohne Angabe"}`} value={wert}
                      onChange={(e) => {
                        const v = e.target.value;
                        katheter(k.schluessel, v.startsWith("w:") ? { art: "wert", id: Number(v.slice(2)) }
                          : v === "neu" ? { art: "neu", wert: k.text } : { art: v as "kein" | "leer" });
                      }}>
                      {bestand.katheter.map((x) => <option key={x.id} value={`w:${x.id}`}>{x.wert}{x.aktiv ? "" : " (ausgeblendet)"}</option>)}
                      <option value="neu">neuer Eintrag der Auswahlliste</option>
                      <option value="kein">kein Katheter</option>
                      <option value="leer">nicht erfasst (leer)</option>
                    </Auswahl>
                  </td>
                  <td className="td">
                    {w.art === "neu" ? <Texteingabe aria-label={`Bezeichnung für ${k.text}`} wert={w.wert} onFertig={(t) => katheter(k.schluessel, { art: "neu", wert: t })} /> : null}
                    <Fehlertext text={k.fehler} />
                  </td>
                  <td className="td whitespace-nowrap">
                    <Zustand offen={!!k.fehler} entschieden={!!k.entscheidung} />
                    <Zurueck zeigen={!!k.entscheidung} name={`Katheter ${k.text}`} onClick={() => katheter(k.schluessel, null)} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Karte>
      {(["nickel", "geschlecht"] as const).map((feld) => (
        <Karte key={feld} className="px-5 py-4 flex flex-col gap-3" data-testid={`zuordnung-${feld}`}>
          <KartenKopf titel={FESTE_WERTE[feld].titel} unter={FESTE_WERTE[feld].unter} />
          <table className="tabelle">
            <thead><tr><th className="th">Im Altsystem</th><th className="th w-[90px]">Patienten</th><th className="th w-[300px]">Im EPM</th><th className="th w-[150px]" /></tr></thead>
            <tbody>
              {stand.werte[feld].map((z) => (
                <tr key={z.schluessel} data-testid={`${feld}-${z.schluessel || "leer"}`}>
                  <td className="td">{z.text || <span className="gedaempft">(ohne Angabe)</span>}</td>
                  <td className="td num">{zahl(z.anzahl)}</td>
                  <td className="td">
                    <Auswahl aria-label={`${FESTE_WERTE[feld].titel} im EPM für ${z.text || "ohne Angabe"}`} value={z.wirksam === null ? "__offen" : z.wirksam}
                      aria-invalid={z.wirksam === null ? true : undefined}
                      onChange={(e) => speichern({ bereich: "werte", aenderungen: { [feld]: { [z.schluessel]: e.target.value } } })}>
                      {z.wirksam === null ? <option value="__offen" disabled>— bitte zuordnen —</option> : null}
                      {FESTE_WERTE[feld].werte.map(([w, name]) => <option key={w} value={w}>{name}</option>)}
                    </Auswahl>
                  </td>
                  <td className="td whitespace-nowrap">
                    <Zustand offen={z.wirksam === null} entschieden={z.entscheidung !== null} />
                    <Zurueck zeigen={z.entscheidung !== null} name={`${FESTE_WERTE[feld].titel} ${z.text}`}
                      onClick={() => speichern({ bereich: "werte", aenderungen: { [feld]: { [z.schluessel]: null } } })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Karte>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Präparate
function praeparatName(p: Bestand["praeparate"][number]) {
  return `${p.name} ${p.konzentration}`.trim() + (p.aktiv ? "" : " (ausgeblendet)");
}

function PraeparatZeile({ feld, f, z, bestand, kategorien, speichern }: { feld: string; f: Praeparatfeld; z: Praeparatzeile; bestand: Bestand;
  kategorien: Record<string, string>; speichern: Speichern }) {
  const setze = (wahl: PraeparatWahl | null) => speichern({ bereich: "praeparate", aenderungen: { [feld]: { [z.schluessel]: wahl } } });
  const kandidaten = bestand.praeparate.filter((p) => f.kategorien.includes(p.kategorie));
  const aehnlich = kandidaten.filter((p) => z.aehnlich.includes(p.id));
  const w = z.wirksam;
  const wert = !w ? "" : w.art === "praeparat" ? `p:${w.id}` : w.art;
  const mitKategorie = f.kategorien.length > 1;
  const eintrag = (p: Bestand["praeparate"][number]) => (
    <option key={p.id} value={`p:${p.id}`}>{praeparatName(p)}{mitKategorie ? ` · ${kategorien[p.kategorie] ?? p.kategorie}` : ""}</option>);
  return (
    <tr data-testid={`praeparat-${feld}-${z.schluessel}`}>
      <td className="td align-top font-medium">{z.text}</td>
      <td className="td align-top num">{zahl(z.anzahl)}</td>
      <td className="td align-top">
        <Auswahl aria-label={`Zuordnung für ${f.titel}: ${z.text}`} value={wert} aria-invalid={!w ? true : undefined}
          onChange={(e) => {
            const v = e.target.value;
            if (v.startsWith("p:")) setze({ art: "praeparat", id: Number(v.slice(2)) });
            else if (v === "neu") setze({ art: "neu", ...z.neu_vorschlag, ...(mitKategorie ? { kategorie: "medikament" } : {}) });
            else if (v === "bemerkung" || v === "leer") setze({ art: v });
          }}>
          {!w ? <option value="" disabled>— bitte zuordnen —</option> : null}
          {aehnlich.length ? <optgroup label="Ähnlich geschrieben">{aehnlich.map(eintrag)}</optgroup> : null}
          <optgroup label="Präparate im EPM">{kandidaten.filter((p) => !z.aehnlich.includes(p.id)).map(eintrag)}</optgroup>
          <optgroup label="Sonst">
            <option value="neu">neues Präparat anlegen</option>
            <option value="bemerkung">als Text in die Bemerkung des Plans</option>
            <option value="leer">nicht übernehmen</option>
          </optgroup>
        </Auswahl>
      </td>
      <td className="td align-top">
        <div className="flex flex-col gap-1.5">
          {w?.art === "neu" ? (
            <div className={cx("grid gap-1.5", mitKategorie ? "grid-cols-[1.4fr_0.8fr_1fr]" : "grid-cols-[1.4fr_0.8fr]")}>
              <Texteingabe aria-label={`Name des neuen Präparats für ${z.text}`} placeholder="Name" wert={w.name} onFertig={(t) => setze({ ...w, name: t })} />
              <Texteingabe aria-label={`Konzentration für ${z.text}`} placeholder="Konzentration" wert={w.konzentration} onFertig={(t) => setze({ ...w, konzentration: t })} />
              {mitKategorie ? (
                <Auswahl aria-label={`Kategorie für ${z.text}`} value={w.kategorie ?? ""} onChange={(e) => setze({ ...w, kategorie: e.target.value })}>
                  {f.kategorien.map((k) => <option key={k} value={k}>{kategorien[k] ?? k}</option>)}
                </Auswahl>
              ) : null}
            </div>
          ) : null}
          <Fehlertext text={w ? z.fehler : ""} />
        </div>
      </td>
      <td className="td align-top whitespace-nowrap">
        <Zustand offen={!!z.fehler} entschieden={!!z.entscheidung} />
        <Zurueck zeigen={!!z.entscheidung} name={`${f.titel} ${z.text}`} onClick={() => setze(null)} />
      </td>
    </tr>
  );
}

function PraeparateTeil({ stand, bestand, kategorien, speichern }: { stand: Zuordnungsstand; bestand: Bestand; kategorien: Record<string, string>;
  speichern: Speichern }) {
  const felder = Object.entries(stand.praeparate).filter(([, f]) => f.zeilen.length);
  if (!felder.length) return <Karte className="px-5 py-4"><Leer>In den Infusionsplänen des Dumps stehen keine Präparate.</Leer></Karte>;
  return (
    <div className="flex flex-col gap-5">
      <Meldung art="info">Vorgeschlagen wird nur, was genau zu einem Präparat im EPM passt (Groß-/Kleinschreibung, Leerzeichen und „20%“ / „20 %“ sind egal).
        Schreibvarianten bitte dem richtigen Präparat zuordnen – so entsteht je Präparat nur ein Eintrag.</Meldung>
      {felder.map(([feld, f]) => (
        <Karte key={feld} className="px-5 py-4 flex flex-col gap-3" data-testid={`zuordnung-praeparate-${feld}`}>
          <KartenKopf titel={f.titel} unter={feld === "medikamente"
            ? "Ein Präparat der Kategorie „Katheterschutz“ wird der Katheterschutz des Plans; alles andere steht unter „Weitere Bestandteile“ – mit dem Wortlaut des Altsystems."
            : feld === "vitamine" ? "„A | B“ im Altsystem = mehrere Vitamine am Plan." : undefined} />
          <table className="tabelle">
            <thead><tr><th className="th">Im Altsystem</th><th className="th w-[70px]">Pläne</th><th className="th w-[320px]">Im EPM</th><th className="th" /><th className="th w-[150px]" /></tr></thead>
            <tbody>{f.zeilen.map((z) => <PraeparatZeile key={z.schluessel} feld={feld} f={f} z={z} bestand={bestand} kategorien={kategorien} speichern={speichern} />)}</tbody>
          </table>
        </Karte>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- Im Altsystem gelöschte Patienten
function GeloeschteTeil({ stand, anlaesse, speichern }: { stand: Zuordnungsstand; anlaesse: Record<string, string>; speichern: Speichern }) {
  const [alle, setAlle] = useState("");
  const setze = (schluessel: string, wahl: GeloeschtWahl | null) => speichern({ bereich: "geloeschte", aenderungen: { [schluessel]: wahl } });
  if (!stand.geloeschte.length) return <Karte className="px-5 py-4"><Leer>Im Dump ist kein Patient als gelöscht markiert.</Leer></Karte>;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="zuordnung-geloeschte">
      <KartenKopf titel={`Im Altsystem gelöschte Patienten (${stand.geloeschte.length})`}
        unter="Standard: nicht übernehmen – mit allen ihren Gewichten, Kontakten und Plänen. Oder als abgeschlossene Akte übernehmen: Dann läuft die Aufbewahrungsfrist ab dem Abschlussdatum." />
      <div className="flex items-end gap-2 flex-wrap">
        <Auswahl aria-label="Anlass für alle" className="w-[240px]" value={alle} onChange={(e) => setAlle(e.target.value)}>
          <option value="">Anlass für alle wählen …</option>
          {Object.entries(anlaesse).map(([k, name]) => <option key={k} value={k}>{name}</option>)}
        </Auswahl>
        <Knopf disabled={!alle} onClick={() => speichern({ bereich: "geloeschte",
          aenderungen: Object.fromEntries(stand.geloeschte.map((g) => [g.schluessel, { art: "abgeschlossen", anlass: alle, am: g.wirksam.art === "abgeschlossen" ? g.wirksam.am : null }])) })}>
          Alle als abgeschlossene Akten übernehmen</Knopf>
        <Knopf variante="geist" onClick={() => speichern({ bereich: "geloeschte", aenderungen: Object.fromEntries(stand.geloeschte.map((g) => [g.schluessel, null])) })}>
          Alle nicht übernehmen</Knopf>
      </div>
      <table className="tabelle">
        <thead><tr><th className="th w-[60px]">Nr.</th><th className="th">Name</th><th className="th">geboren</th><th className="th">gelöscht am</th><th className="th">Einträge</th>
          <th className="th w-[250px]">Entscheidung</th><th className="th">Anlass · Abschlussdatum</th></tr></thead>
        <tbody>
          {stand.geloeschte.map((g) => {
            const w = g.wirksam;
            return (
              <tr key={g.schluessel} data-testid={`geloescht-${g.schluessel}`}>
                <td className="td align-top num">{g.schluessel}</td>
                <td className="td align-top">{g.name}</td>
                <td className="td align-top num">{g.geburtsdatum ? datum(g.geburtsdatum) : "—"}</td>
                <td className="td align-top num">{datum(g.geloescht_am)}</td>
                <td className="td align-top text-[0.8125rem]">{g.gewichte} Gewichte · {g.kontakte} Kontakte · {g.plaene} Pläne</td>
                <td className="td align-top">
                  <Auswahl aria-label={`Entscheidung für Patient ${g.schluessel}`} value={w.art}
                    onChange={(e) => setze(g.schluessel, e.target.value === "abgeschlossen" ? { art: "abgeschlossen", anlass: null, am: null } : null)}>
                    <option value="nicht">nicht übernehmen</option>
                    <option value="abgeschlossen">als abgeschlossene Akte übernehmen</option>
                  </Auswahl>
                </td>
                <td className="td align-top">
                  {w.art === "abgeschlossen" ? (
                    <div className="flex flex-col gap-1.5">
                      <div className="grid grid-cols-[1.3fr_1fr] gap-1.5">
                        <Auswahl aria-label={`Anlass für Patient ${g.schluessel}`} value={w.anlass ?? ""} aria-invalid={!w.anlass ? true : undefined}
                          onChange={(e) => setze(g.schluessel, { ...w, anlass: e.target.value })}>
                          {w.anlass && anlaesse[w.anlass] ? null : <option value="">— Anlass wählen —</option>}
                          {Object.entries(anlaesse).map(([k, name]) => <option key={k} value={k}>{name}</option>)}
                        </Auswahl>
                        <Eingabe type="date" aria-label={`Abschlussdatum für Patient ${g.schluessel}`} value={w.am ?? ""}
                          onChange={(e) => { if (e.target.value) setze(g.schluessel, { ...w, am: e.target.value }); }} />
                      </div>
                      <Fehlertext text={g.fehler} />
                    </div>
                  ) : <span className="text-[0.8125rem] gedaempft">bleibt im Altsystem</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Karte>
  );
}

// ---------------------------------------------------------------- Auffälligkeiten
const ENTSCHEIDUNG: Record<Entscheidungsart, string> = {
  wert: "Wert eintragen", leer: "leer lassen", unveraendert: "unverändert übernehmen", auslassen: "nicht übernehmen",
};

function AuffaelligZeile({ a, speichern }: { a: Auffaelligkeit; speichern: Speichern }) {
  const [art, setArt] = useState<string>(a.entscheidung?.art ?? "");
  useEffect(() => { setArt(a.entscheidung?.art ?? ""); }, [a.entscheidung?.art]);
  const setze = (wahl: { art: Entscheidungsart; wert?: string } | null) => speichern({ bereich: "korrekturen", aenderungen: { [a.schluessel]: wahl } });
  const was = `${a.tabelle_titel} ${a.id}: ${a.feld_titel}`;
  return (
    <tr data-testid={`auffaellig-${a.schluessel}`}>
      <td className="td align-top text-[0.8125rem] whitespace-nowrap">{a.tabelle_titel} <span className="num">{a.id}</span>
        {a.patient != null && a.tabelle !== "patienten" ? <><br /><span className="gedaempft">Patient {a.patient}</span></> : null}</td>
      <td className="td align-top">{a.feld_titel}</td>
      <td className="td align-top text-sm">{a.text}{a.wert !== null && a.art !== "korrigiert" ? <><br /><span className="text-xs gedaempft">im Dump: <span className="num">{a.wert || "(leer)"}</span></span></> : null}</td>
      <td className="td align-top">
        <div className="flex flex-col gap-1.5">
          <Auswahl aria-label={`Entscheidung für ${was}`} value={art} aria-invalid={a.blockiert ? true : undefined}
            onChange={(e) => {
              const v = e.target.value;
              setArt(v);
              if (v === "") setze(null);
              else if (v !== "wert") setze({ art: v as Entscheidungsart });
            }}>
            <option value="">{a.standard === "offen" ? "— bitte entscheiden —" : `Standard: ${ENTSCHEIDUNG[a.standard]}`}</option>
            {a.moeglich.map((m) => <option key={m} value={m}>{ENTSCHEIDUNG[m]}</option>)}
          </Auswahl>
          {art === "wert" ? (
            a.eingabe === "datum" ? (
              <Eingabe type="date" aria-label={`Wert für ${was}`} defaultValue={/^\d{4}-\d{2}-\d{2}$/.test(a.entscheidung?.wert ?? "") ? a.entscheidung?.wert : ""}
                onBlur={(e) => { if (e.target.value && e.target.value !== a.entscheidung?.wert) setze({ art: "wert", wert: e.target.value }); }} />
            ) : (
              <Texteingabe aria-label={`Wert für ${was}`} placeholder={a.eingabe === "zahl" ? "Zahl" : "Text"} wert={a.entscheidung?.wert ?? ""}
                onFertig={(t) => { if (t) setze({ art: "wert", wert: t }); }} />
            )
          ) : null}
        </div>
      </td>
      <td className="td align-top whitespace-nowrap">
        {a.blockiert ? <Chip art="warn"><Icon name="warnung" />offen</Chip> : a.entscheidung ? <Chip art="akzent">entschieden</Chip> : <Chip>Standard</Chip>}
      </td>
    </tr>
  );
}

function AuffaelligkeitenTeil({ stand, speichern }: { stand: Zuordnungsstand; speichern: Speichern }) {
  const [anzahl, setAnzahl] = useState(200);
  const liste = stand.auffaelligkeiten;
  if (!liste.length) return <Karte className="px-5 py-4"><Leer>Keine Auffälligkeiten.</Leer></Karte>;
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="zuordnung-auffaelligkeiten">
      <KartenKopf titel={`Auffälligkeiten (${liste.length})`}
        unter="Einzelne Werte, die fehlen, nicht lesbar oder unplausibel sind. Ohne Entscheidung gilt der Standard; was als „offen“ markiert ist, muss entschieden werden. Eine Korrektur gilt nur, solange im Dump derselbe Wert steht." />
      <table className="tabelle">
        <thead><tr><th className="th w-[130px]">Zeile</th><th className="th w-[170px]">Angabe</th><th className="th">Befund</th><th className="th w-[320px]">Entscheidung</th><th className="th w-[110px]" /></tr></thead>
        <tbody>{liste.slice(0, anzahl).map((a) => <AuffaelligZeile key={a.schluessel} a={a} speichern={speichern} />)}</tbody>
      </table>
      {liste.length > anzahl ? <div><Knopf klein onClick={() => setAnzahl(anzahl + 200)}>Weitere anzeigen ({liste.length - anzahl})</Knopf></div> : null}
    </Karte>
  );
}

// ---------------------------------------------------------------- Rahmen
const TEILE: { wert: Teil; text: string }[] = [
  { wert: "spalten", text: "Tabellen und Spalten" }, { wert: "benutzer", text: "Benutzer" }, { wert: "versorger", text: "Versorger" },
  { wert: "werte", text: "Katheter und Werte" }, { wert: "praeparate", text: "Präparate" }, { wert: "geloeschte", text: "Gelöschte Patienten" },
  { wert: "auffaelligkeiten", text: "Auffälligkeiten" },
];

export function Zuordnungen({ daten, speichern, laeuft, fehler }: { daten: Zuordnung; speichern: Speichern; laeuft: boolean; fehler: ReactNode }) {
  const [teil, setTeil] = useState<Teil>("spalten");
  const stand = daten.stand, bestand = daten.bestand;
  if (!stand || !bestand) return null;
  const offen = (t: Teil) => stand.offen.filter((o) => o.bereich === t).length;
  const auswahl = daten.auswahl ?? { rollen: [], anlaesse: {}, kategorien: {} };
  return (
    <div className="flex flex-col gap-5" aria-busy={laeuft || undefined}>
      {stand.offen.length ? (
        <div className="meldung warn flex flex-col gap-1.5" data-testid="offene-punkte">
          <span className="font-medium flex items-center gap-2"><Icon name="warnung" />{stand.offen.length} offene Punkte – erst danach sind Probelauf und Import möglich</span>
          <ul className="m-0 pl-5 text-[0.8125rem]">
            {stand.offen.slice(0, 12).map((o, i) => <li key={i}>{o.text}</li>)}
            {stand.offen.length > 12 ? <li>… und {stand.offen.length - 12} weitere</li> : null}
          </ul>
        </div>
      ) : (
        <div className="meldung ok flex items-center gap-2" data-testid="offene-punkte"><Icon name="haken" />Alle Zuordnungen sind vollständig. Weiter mit „Probelauf und Import“.</div>
      )}
      {fehler}
      <Segmente label="Bereich der Zuordnungen" wert={teil} onWahl={setTeil}
        werte={TEILE.map((t) => ({ wert: t.wert, text: offen(t.wert) ? `${t.text} (${offen(t.wert)})` : t.text }))} className="self-start flex-wrap" />
      {teil === "spalten" ? <Spalten stand={stand} speichern={speichern} laeuft={laeuft} /> : null}
      {teil === "benutzer" ? <BenutzerTeil stand={stand} bestand={bestand} rollen={auswahl.rollen} speichern={speichern} /> : null}
      {teil === "versorger" ? <VersorgerTeil stand={stand} bestand={bestand} speichern={speichern} /> : null}
      {teil === "werte" ? <WerteTeil stand={stand} bestand={bestand} speichern={speichern} /> : null}
      {teil === "praeparate" ? <PraeparateTeil stand={stand} bestand={bestand} kategorien={auswahl.kategorien} speichern={speichern} /> : null}
      {teil === "geloeschte" ? <GeloeschteTeil stand={stand} anlaesse={auswahl.anlaesse} speichern={speichern} /> : null}
      {teil === "auffaelligkeiten" ? <AuffaelligkeitenTeil stand={stand} speichern={speichern} /> : null}
    </div>
  );
}
