/**
 * Administration › Import › Zuordnungen: Was das Werkzeug aus dem Dump erkannt hat – und wo die Administration
 * korrigiert. Jede Änderung wird sofort gespeichert; „Vorschlag“ nimmt eine Entscheidung zurück. Die Zuordnungen
 * bleiben unabhängig vom Dump erhalten und gelten für den frischen Dump zum Go-live weiter.
 */
import { useEffect, useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { datum, zahl, zeitpunkt } from "@/lib/format";
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
    <div className="stapel flex flex-col gap-5">
      {q.tabellen.map((t) => {
        const ignoriert = t.rest.filter((r) => r.art === "ignoriert").map((r) => r.spalte);
        return (
          <Karte key={t.name} className="px-5 py-4 flex flex-col gap-3" data-testid={`quelle-${t.name}`}>
            <KartenKopf titel={`${t.titel} → ${t.ziel}`}
              unter={t.tabelle ? `${zahl(t.zeilen)} Zeilen in der Tabelle „${t.tabelle}“` : t.art === "ohne" ? "bewusst nicht vorhanden" : "im Dump nicht gefunden"}
              rechts={
                <Auswahl aria-label={`Tabelle im Dump für ${t.titel}`} className="w-[15rem]"
                  value={t.art === "ohne" ? "__ohne" : t.tabelle ?? ""}
                  onChange={(e) => speichern({ bereich: "tabellen", aenderungen: { [t.name]: e.target.value === "__ohne" ? "" : e.target.value || null } })}>
                  {t.tabelle ? null : <option value="">— bitte zuordnen —</option>}
                  {q.im_dump.map((n) => <option key={n} value={n}>{n}</option>)}
                  <option value="__ohne">im Dump nicht vorhanden</option>
                </Auswahl>} />
            {t.tabelle ? (
              <table className="tabelle">
                <thead><tr><th className="th">Angabe im EPM</th><th className="th w-[16.25rem]">Spalte im Dump</th><th className="th w-[8.125rem]" /><th className="th">Hinweis</th></tr></thead>
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
          <thead><tr><th className="th">Im Altsystem</th><th className="th w-[5.625rem]">Einträge</th><th className="th w-[15.625rem]">Im EPM</th><th className="th">Angaben</th><th className="th w-[9.375rem]" /></tr></thead>
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
                        <Auswahl aria-label={`Rolle für ${b.name}`} value={w.rolle} className="w-[12.5rem]" onChange={(e) => setze(b, { ...w, rolle: e.target.value })}>
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
          <thead><tr><th className="th w-[3.125rem]">Nr.</th><th className="th">Im Altsystem</th><th className="th w-[5.625rem]">Patienten</th><th className="th w-[14.375rem]">Im EPM</th><th className="th">Versorger · Ansprechpartner</th><th className="th w-[9.375rem]" /></tr></thead>
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
    <div className="stapel flex flex-col gap-5">
      <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="zuordnung-katheter">
        <KartenKopf titel="Katheter" unter="Die Werte des Altsystems werden Einträge der Auswahlliste „Katheter“ (Vorlagen › Auswahllisten)." />
        <table className="tabelle">
          <thead><tr><th className="th">Im Altsystem</th><th className="th w-[5.625rem]">Patienten</th><th className="th w-[18.75rem]">Im EPM</th><th className="th" /><th className="th w-[9.375rem]" /></tr></thead>
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
            <thead><tr><th className="th">Im Altsystem</th><th className="th w-[5.625rem]">Patienten</th><th className="th w-[18.75rem]">Im EPM</th><th className="th w-[9.375rem]" /></tr></thead>
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
    <div className="stapel flex flex-col gap-5">
      <Meldung art="info">Vorgeschlagen wird nur, was genau zu einem Präparat im EPM passt (Groß-/Kleinschreibung, Leerzeichen und „20%“ / „20 %“ sind egal).
        Schreibvarianten bitte dem richtigen Präparat zuordnen – so entsteht je Präparat nur ein Eintrag.</Meldung>
      {felder.map(([feld, f]) => (
        <Karte key={feld} className="px-5 py-4 flex flex-col gap-3" data-testid={`zuordnung-praeparate-${feld}`}>
          <KartenKopf titel={f.titel} unter={feld === "medikamente"
            ? "Ein Präparat der Kategorie „Katheterschutz“ wird der Katheterschutz des Plans; alles andere steht unter „Weitere Bestandteile“ – mit dem Wortlaut des Altsystems."
            : feld === "vitamine" ? "„A | B“ im Altsystem = mehrere Vitamine am Plan." : undefined} />
          <table className="tabelle">
            <thead><tr><th className="th">Im Altsystem</th><th className="th w-[4.375rem]">Pläne</th><th className="th w-[20rem]">Im EPM</th><th className="th" /><th className="th w-[9.375rem]" /></tr></thead>
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
        <Auswahl aria-label="Anlass für alle" className="w-[15rem]" value={alle} onChange={(e) => setAlle(e.target.value)}>
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
        <thead><tr><th className="th w-[3.75rem]">Nr.</th><th className="th">Name</th><th className="th">geboren</th><th className="th">gelöscht am</th><th className="th">Einträge</th>
          <th className="th w-[15.625rem]">Entscheidung</th><th className="th">Anlass · Abschlussdatum</th></tr></thead>
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
const ARTEN: Entscheidungsart[] = ["wert", "leer", "unveraendert", "auslassen"];
type Wahl = { art: Entscheidungsart; wert?: string };

/** Wahlmöglichkeiten, die für alle angegebenen Auffälligkeiten gelten */
function gemeinsam(liste: Auffaelligkeit[]): Entscheidungsart[] {
  return ARTEN.filter((m) => liste.length > 0 && liste.every((a) => a.moeglich.includes(m)));
}

/** Entscheidung mit Werteingabe – für eine Zeile, eine Gruppe oder die Auswahl */
function Entscheider({ label, wertLabel, moeglich, aktuell, leerText, eingabe, ungueltig, onWahl }: {
  label: string; wertLabel: string; moeglich: Entscheidungsart[]; aktuell: Wahl | null; leerText: string; eingabe: "text" | "zahl" | "datum";
  ungueltig?: boolean; onWahl: (w: Wahl | null) => void;
}) {
  const [art, setArt] = useState<string>(aktuell?.art ?? "");
  useEffect(() => { setArt(aktuell?.art ?? ""); }, [aktuell?.art]);
  return (
    <div className="flex flex-col gap-1.5">
      <Auswahl aria-label={label} value={art} aria-invalid={ungueltig ? true : undefined}
        onChange={(e) => {
          const v = e.target.value;
          setArt(v);
          if (v === "") onWahl(null);
          else if (v !== "wert") onWahl({ art: v as Entscheidungsart });
        }}>
        <option value="">{leerText}</option>
        {moeglich.map((m) => <option key={m} value={m}>{ENTSCHEIDUNG[m]}</option>)}
      </Auswahl>
      {art === "wert" ? (
        eingabe === "datum" ? (
          <Eingabe type="date" aria-label={wertLabel} defaultValue={/^\d{4}-\d{2}-\d{2}$/.test(aktuell?.wert ?? "") ? aktuell?.wert : ""}
            onBlur={(e) => { if (e.target.value && e.target.value !== aktuell?.wert) onWahl({ art: "wert", wert: e.target.value }); }} />
        ) : (
          <Texteingabe aria-label={wertLabel} placeholder={eingabe === "zahl" ? "Zahl" : "Text"} wert={aktuell?.wert ?? ""}
            onFertig={(t) => { if (t) onWahl({ art: "wert", wert: t }); }} />
        )
      ) : null}
    </div>
  );
}

function standardText(a: Auffaelligkeit) {
  if (a.regel && a.entscheidung?.regel) return `Regel: ${ENTSCHEIDUNG[a.regel.art]}${a.regel.wert ? ` „${a.regel.wert}“` : ""}`;
  return a.standard === "offen" ? "— bitte entscheiden —" : `Standard: ${ENTSCHEIDUNG[a.standard]}`;
}

function AuffaelligZeile({ a, speichern, gewaehlt, onWaehlen }: {
  a: Auffaelligkeit; speichern: Speichern; gewaehlt?: boolean; onWaehlen?: (an: boolean) => void;
}) {
  const was = `${a.tabelle_titel} ${a.id}: ${a.feld_titel}`;
  // Entscheidung zur einzelnen Zeile (eine Regel erscheint als Vorgabe, nicht als eigene Entscheidung)
  const eigene = a.entscheidung && !a.entscheidung.regel ? a.entscheidung : null;
  return (
    <tr data-testid={`auffaellig-${a.schluessel}`}>
      {onWaehlen ? (
        <td className="td align-top w-[2.25rem]">
          <input type="checkbox" aria-label={`${was} auswählen`} checked={!!gewaehlt} onChange={(e) => onWaehlen(e.target.checked)} />
        </td>
      ) : null}
      <td className="td align-top text-[0.8125rem] whitespace-nowrap">{a.tabelle_titel} <span className="num">{a.id}</span>
        {a.patient != null && a.tabelle !== "patienten" ? <><br /><span className="gedaempft">Patient {a.patient}</span></> : null}</td>
      <td className="td align-top">{a.feld_titel}</td>
      <td className="td align-top text-sm">{a.text}{a.wert !== null && a.art !== "korrigiert" ? <><br /><span className="text-xs gedaempft">im Dump: <span className="num">{a.wert || "(leer)"}</span></span></> : null}</td>
      <td className="td align-top">
        <Entscheider label={`Entscheidung für ${was}`} wertLabel={`Wert für ${was}`} moeglich={a.moeglich} aktuell={eigene} leerText={standardText(a)}
          eingabe={a.eingabe} ungueltig={a.blockiert}
          onWahl={(w) => speichern({ bereich: "korrekturen", aenderungen: { [a.schluessel]: w } })} />
      </td>
      <td className="td align-top whitespace-nowrap">
        {a.blockiert ? <Chip art="warn"><Icon name="warnung" />offen</Chip>
          : eigene ? <Chip art="akzent">entschieden</Chip>
          : a.entscheidung?.regel ? <Chip art="akzent">per Regel</Chip> : <Chip>Standard</Chip>}
      </td>
    </tr>
  );
}

type Gruppe = { schluessel: string; titel: string; wert: string; liste: Auffaelligkeit[]; regel: Auffaelligkeit["regel"] };

function gruppieren(liste: Auffaelligkeit[]): Gruppe[] {
  const je = new Map<string, Gruppe>();
  for (const a of liste) {
    let g = je.get(a.gruppe);
    if (!g) {
      g = { schluessel: a.gruppe, titel: `${a.tabelle_titel} · ${a.feld_titel}`, wert: a.roh ?? "", liste: [], regel: a.regel };
      je.set(a.gruppe, g);
    }
    g.liste.push(a);
  }
  // große Gruppen zuerst – dort spart eine Regel die meiste Arbeit; offene vor erledigten
  return [...je.values()].sort((x, y) =>
    Number(y.liste.some((a) => a.blockiert)) - Number(x.liste.some((a) => a.blockiert)) || y.liste.length - x.liste.length
    || x.titel.localeCompare(y.titel) || x.wert.localeCompare(y.wert, "de", { numeric: true }));
}

/** Wahlmöglichkeiten einer Regel: wie beim Speichern im Server (dienst._regeln_pruefen) */
function regelMoeglich(g: Gruppe): Entscheidungsart[] {
  const mitglieder = g.liste.filter((a) => a.art !== "korrigiert");
  if (g.regel && mitglieder.length && mitglieder.every((a) => a.art === "ausgelassen" && a.entscheidung?.regel)) return g.regel.moeglich;
  return gemeinsam(mitglieder);
}

function GruppenZeile({ g, speichern }: { g: Gruppe; speichern: Speichern }) {
  const [auf, setAuf] = useState(false);
  const moeglich = regelMoeglich(g);
  const offen = g.liste.filter((a) => a.blockiert).length;
  const einzeln = g.liste.filter((a) => a.entscheidung && !a.entscheidung.regel).length;
  const patienten = new Set(g.liste.map((a) => a.patient ?? (a.tabelle === "patienten" ? a.id : null)).filter((p) => p != null)).size;
  const muster = g.liste.find((a) => a.art !== "ausgelassen" && a.art !== "korrigiert") ?? g.liste[0];
  const befund = g.regel?.befund && muster.art === "ausgelassen" ? g.regel.befund : muster.text;
  const standard = muster.standard === "offen" ? "— bitte entscheiden —" : `einzeln (Standard: ${ENTSCHEIDUNG[muster.standard]})`;
  const label = `Regel für ${g.titel} „${g.wert || "(leer)"}“`;
  return (
    <>
      <tr data-testid={`gruppe-${g.schluessel}`}>
        <td className="td align-top text-[0.8125rem]">{g.titel}</td>
        <td className="td align-top num">{g.wert || <span className="gedaempft">(leer)</span>}</td>
        <td className="td align-top text-sm">{befund}
          <br /><span className="text-xs gedaempft">{zahl(g.liste.length)} {g.liste.length === 1 ? "Zeile" : "Zeilen"}{patienten > 1 ? ` bei ${zahl(patienten)} Patienten` : ""}
            {einzeln ? ` · ${zahl(einzeln)} einzeln entschieden (hat Vorrang)` : ""}</span>
        </td>
        <td className="td align-top">
          {moeglich.length ? (
            <Entscheider label={label} wertLabel={`Wert für alle: ${g.titel} „${g.wert || "(leer)"}“`} moeglich={moeglich} aktuell={g.regel} leerText={standard} eingabe={muster.eingabe}
              ungueltig={offen > 0} onWahl={(w) => speichern({ bereich: "regeln", aenderungen: { [g.schluessel]: w } })} />
          ) : <span className="text-[0.8125rem] gedaempft">nur einzeln entscheidbar</span>}
        </td>
        <td className="td align-top whitespace-nowrap">
          <div className="flex flex-col items-start gap-1.5">
            {offen ? <Chip art="warn"><Icon name="warnung" />{offen} offen</Chip> : g.regel ? <Chip art="akzent">Regel</Chip> : <Chip>Standard</Chip>}
            <Knopf klein variante="geist" aria-expanded={auf} onClick={() => setAuf(!auf)}>{auf ? "Zeilen ausblenden" : "Zeilen zeigen"}</Knopf>
          </div>
        </td>
      </tr>
      {auf ? (
        <tr><td className="td p-0" colSpan={5}>
          <div className="pl-6 pr-2 py-2 bg-grund">
            <table className="tabelle">
              <tbody>{g.liste.slice(0, 300).map((a) => <AuffaelligZeile key={a.schluessel} a={a} speichern={speichern} />)}</tbody>
            </table>
            {g.liste.length > 300 ? <p className="text-[0.8125rem] gedaempft m-0 mt-2">Es werden die ersten 300 Zeilen gezeigt; die Regel gilt für alle {zahl(g.liste.length)}.</p> : null}
          </div>
        </td></tr>
      ) : null}
    </>
  );
}

function Einzelliste({ liste, speichern }: { liste: Auffaelligkeit[]; speichern: Speichern }) {
  const [anzahl, setAnzahl] = useState(200);
  const [filter, setFilter] = useState("");
  const [auswahl, setAuswahl] = useState<Set<string>>(new Set());
  const [sammelArt, setSammelArt] = useState<string>("");
  const [sammelWert, setSammelWert] = useState("");
  const angaben = [...new Map(liste.map((a) => [`${a.tabelle}:${a.feld}`, `${a.tabelle_titel} · ${a.feld_titel}`])).entries()];
  const gefiltert = filter ? liste.filter((a) => `${a.tabelle}:${a.feld}` === filter) : liste;
  const sichtbar = gefiltert.slice(0, anzahl);
  const gewaehlt = liste.filter((a) => auswahl.has(a.schluessel));
  const moeglich = gemeinsam(gewaehlt);
  // Auswahl auf vorhandene Zeilen beschränken (nach dem Speichern kann sich die Liste ändern)
  useEffect(() => {
    const da = new Set(liste.map((a) => a.schluessel));
    setAuswahl((alt) => { const neu = new Set([...alt].filter((s) => da.has(s))); return neu.size === alt.size ? alt : neu; });
  }, [liste]);
  useEffect(() => { if (sammelArt && !moeglich.includes(sammelArt as Entscheidungsart)) setSammelArt(""); }, [moeglich.join(), sammelArt]);
  const waehle = (s: string, an: boolean) => setAuswahl((alt) => { const neu = new Set(alt); if (an) neu.add(s); else neu.delete(s); return neu; });
  const alleSichtbar = sichtbar.length > 0 && sichtbar.every((a) => auswahl.has(a.schluessel));
  const anwenden = (wahl: Wahl | null) => {
    speichern({ bereich: "korrekturen", aenderungen: Object.fromEntries(gewaehlt.map((a) => [a.schluessel, wahl])) });
    setAuswahl(new Set());
    setSammelArt("");
    setSammelWert("");
  };
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-end gap-2 flex-wrap">
        <Auswahl aria-label="Angabe filtern" className="w-[16.25rem]" value={filter} onChange={(e) => { setFilter(e.target.value); setAnzahl(200); }}>
          <option value="">Alle Angaben ({zahl(liste.length)})</option>
          {angaben.map(([k, t]) => <option key={k} value={k}>{t} ({zahl(liste.filter((a) => `${a.tabelle}:${a.feld}` === k).length)})</option>)}
        </Auswahl>
        <Knopf klein variante="geist" onClick={() => setAuswahl(new Set([...auswahl, ...gefiltert.map((a) => a.schluessel)]))}>
          Alle {zahl(gefiltert.length)} auswählen</Knopf>
        {auswahl.size ? <Knopf klein variante="geist" onClick={() => setAuswahl(new Set())}>Auswahl aufheben</Knopf> : null}
      </div>
      {auswahl.size ? (
        <div className="meldung info flex items-end gap-2 flex-wrap" data-testid="sammelentscheidung">
          <span className="font-medium self-center">{zahl(auswahl.size)} ausgewählt:</span>
          {moeglich.length ? (
            <>
              <Auswahl aria-label="Entscheidung für die Auswahl" className="w-[14.375rem]" value={sammelArt} onChange={(e) => setSammelArt(e.target.value)}>
                <option value="">— Entscheidung wählen —</option>
                {moeglich.map((m) => <option key={m} value={m}>{ENTSCHEIDUNG[m]}</option>)}
              </Auswahl>
              {sammelArt === "wert" ? <Eingabe aria-label="Wert für die Auswahl" className="w-[10rem]" value={sammelWert} onChange={(e) => setSammelWert(e.target.value)} /> : null}
              <Knopf klein disabled={!sammelArt || (sammelArt === "wert" && !sammelWert.trim())}
                onClick={() => anwenden(sammelArt === "wert" ? { art: "wert", wert: sammelWert.trim() } : { art: sammelArt as Entscheidungsart })}>
                Für {zahl(auswahl.size)} übernehmen</Knopf>
            </>
          ) : <span className="text-[0.8125rem]">Für diese Auswahl gibt es keine gemeinsame Entscheidung – bitte nach Angabe filtern.</span>}
          <Knopf klein variante="geist" onClick={() => anwenden(null)}>Entscheidungen der Auswahl zurücknehmen</Knopf>
        </div>
      ) : null}
      <table className="tabelle">
        <thead><tr>
          <th className="th w-[2.25rem]"><input type="checkbox" aria-label="Alle sichtbaren auswählen" checked={alleSichtbar}
            onChange={(e) => setAuswahl((alt) => { const neu = new Set(alt); sichtbar.forEach((a) => e.target.checked ? neu.add(a.schluessel) : neu.delete(a.schluessel)); return neu; })} /></th>
          <th className="th w-[8.125rem]">Zeile</th><th className="th w-[10.625rem]">Angabe</th><th className="th">Befund</th><th className="th w-[20rem]">Entscheidung</th><th className="th w-[6.875rem]" />
        </tr></thead>
        <tbody>{sichtbar.map((a) => <AuffaelligZeile key={a.schluessel} a={a} speichern={speichern}
          gewaehlt={auswahl.has(a.schluessel)} onWaehlen={(an) => waehle(a.schluessel, an)} />)}</tbody>
      </table>
      {gefiltert.length > anzahl ? <div><Knopf klein onClick={() => setAnzahl(anzahl + 200)}>Weitere anzeigen ({gefiltert.length - anzahl})</Knopf></div> : null}
    </div>
  );
}

const TAGE = [0, 1, 2, 3, 4, 5, 6, 7];

function GewichteZusammenfassen({ z, speichern }: { z: Zuordnungsstand["zusammengefasst"]; speichern: Speichern }) {
  const [auf, setAuf] = useState(false);
  return (
    <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="gewichte-zusammenfassen">
      <KartenKopf titel="Gewichte zusammenfassen"
        unter="Mehrere Gewichte eines Patienten kurz hintereinander sind im Altsystem meist Korrekturen derselben Messung. Alle Einträge, die höchstens so viele Tage (× 24 Stunden) nach dem ersten Eintrag einer Gruppe erfasst wurden, werden zu einem zusammengefasst; übernommen wird der zuletzt erfasste. Das gilt nach den Entscheidungen unten: Was „nicht übernommen“ wird, verdrängt keinen anderen Wert."
        rechts={
          <Auswahl aria-label="Gewichte zusammenfassen innerhalb von" className="w-[12.5rem]" value={String(z.tage)}
            onChange={(e) => speichern({ bereich: "einstellungen", aenderungen: { gewichte_tage: Number(e.target.value) } })}>
            {TAGE.map((t) => <option key={t} value={t}>{t === 0 ? "nicht zusammenfassen" : `innerhalb von ${t} ${t === 1 ? "Tag" : "Tagen"}`}</option>)}
          </Auswahl>} />
      {z.tage ? (
        <div className="flex items-center gap-3 flex-wrap text-sm">
          <span data-testid="zusammengefasst-zahl">{z.anzahl ? `${zahl(z.anzahl)} Gewichte bei ${zahl(z.patienten)} Patienten werden nicht übernommen, weil ein später erfasster Wert sie ersetzt.` : "Keine Gewichte liegen so dicht beieinander."}</span>
          {z.gruppen.length ? <Knopf klein variante="geist" aria-expanded={auf} onClick={() => setAuf(!auf)}>{auf ? "Liste ausblenden" : "Liste zeigen"}</Knopf> : null}
        </div>
      ) : <span className="text-sm gedaempft">Alle Gewichte werden einzeln übernommen.</span>}
      {auf && z.tage ? (
        <table className="tabelle">
          <thead><tr><th className="th w-[5.625rem]">Patient</th><th className="th">übernommen</th><th className="th">ersetzt (nicht übernommen)</th></tr></thead>
          <tbody>
            {z.gruppen.map((g) => (
              <tr key={g.behalten.id}>
                <td className="td align-top num">{g.patient}</td>
                <td className="td align-top num">{g.behalten.kg.replace(".", ",")} kg · {zeitpunkt(g.behalten.zeit)}</td>
                <td className="td align-top num text-[0.8125rem]">{g.verworfen.map((v) => `${v.kg.replace(".", ",")} kg · ${zeitpunkt(v.zeit)}`).join(" | ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {auf && z.gruppen.length < z.patienten ? <p className="text-[0.8125rem] gedaempft m-0">Es werden die ersten {zahl(z.gruppen.length)} Gruppen gezeigt; das Protokoll des Probelaufs nennt alle.</p> : null}
    </Karte>
  );
}

function AuffaelligkeitenTeil({ stand, speichern }: { stand: Zuordnungsstand; speichern: Speichern }) {
  const [ansicht, setAnsicht] = useState<"gruppen" | "einzeln">("gruppen");
  const liste = stand.auffaelligkeiten;
  const gruppen = gruppieren(liste);
  return (
    <div className="stapel flex flex-col gap-5">
      {stand.zusammengefasst ? <GewichteZusammenfassen z={stand.zusammengefasst} speichern={speichern} /> : null}
      {!liste.length ? <Karte className="px-5 py-4"><Leer>Keine Auffälligkeiten.</Leer></Karte> : (
        <Karte className="px-5 py-4 flex flex-col gap-3" data-testid="zuordnung-auffaelligkeiten">
          <KartenKopf titel={`Auffälligkeiten (${zahl(liste.length)} in ${zahl(gruppen.length)} Gruppen)`}
            unter="Einzelne Werte, die fehlen, nicht lesbar oder unplausibel sind. Ohne Entscheidung gilt der Standard; was als „offen“ markiert ist, muss entschieden werden. Gleiche Meldungen mit demselben Wert sind zu Gruppen zusammengefasst: Eine Regel gilt für alle Zeilen mit diesem Wert – auch im frischen Dump zum Go-live. Eine Entscheidung zu einer einzelnen Zeile hat Vorrang und gilt nur, solange im Dump derselbe Wert steht."
            rechts={<Segmente label="Ansicht der Auffälligkeiten" wert={ansicht} onWahl={setAnsicht}
              werte={[{ wert: "gruppen", text: "Gruppiert" }, { wert: "einzeln", text: "Einzeln mit Auswahl" }]} />} />
          {ansicht === "gruppen" ? (
            <table className="tabelle">
              <thead><tr><th className="th w-[10.625rem]">Angabe</th><th className="th w-[6.875rem]">Wert im Dump</th><th className="th">Befund</th>
                <th className="th w-[20rem]">Für alle mit diesem Wert</th><th className="th w-[9.375rem]" /></tr></thead>
              <tbody>{gruppen.map((g) => <GruppenZeile key={g.schluessel} g={g} speichern={speichern} />)}</tbody>
            </table>
          ) : <Einzelliste liste={liste} speichern={speichern} />}
        </Karte>
      )}
    </div>
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
    <div className="stapel flex flex-col gap-5" aria-busy={laeuft || undefined}>
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
