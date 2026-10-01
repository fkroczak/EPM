"""
Gruppen und lesbare Beschreibungen der Systemereignisse (Entwurf 20 · Audit-Log).

Die Beschreibung wird beim Lesen aus Art und Details gebildet; gespeichert wird nur,
was tatsächlich passiert ist. So bleiben auch ältere Einträge lesbar.
"""
from .models import SystemEreignis

A = SystemEreignis.Art

# Filterknöpfe im Entwurf: Anmeldung · Fehlversuch · Benutzer · Vorlage · Backup · Export · Abschluss
GRUPPEN = {
    "anmeldung": ("Anmeldung", [A.ANMELDUNG, A.ABMELDUNG, A.KENNWORT_GEAENDERT, A.ZWEITER_FAKTOR_EINGERICHTET]),
    "fehlversuch": ("Fehlversuch", [A.ANMELDUNG_FEHLGESCHLAGEN, A.ZWEITER_FAKTOR_FEHLGESCHLAGEN, A.ANMELDUNG_GESPERRT]),
    "benutzer": ("Benutzer", [A.BENUTZER_ANGELEGT, A.BENUTZER_GEAENDERT, A.BENUTZER_GESPERRT, A.EINMAL_KENNWORT,
                              A.ZWEITER_FAKTOR_ZURUECKGESETZT, A.TESTDATEN, A.RECHTE_GEAENDERT]),
    "vorlage": ("Vorlage", [A.VORLAGE, A.STAMMDATEN]),
    "backup": ("Backup", [A.BACKUP]),
    "export": ("Export", [A.EXPORT]),
    "abschluss": ("Abschluss", [A.AKTE_ABGESCHLOSSEN, A.AKTE_GEOEFFNET]),
    # ohne eigenen Filterknopf im Entwurf, erscheint unter „alle“
    "infusionsplan": ("Infusionsplan", [A.PLAN_FREIGEGEBEN]),
}
GRUPPE_JE_ART = {art: schluessel for schluessel, (_, arten) in GRUPPEN.items() for art in arten}


def gruppe(art: str) -> str:
    return GRUPPE_JE_ART.get(art, "")


def gruppe_name(art: str) -> str:
    return GRUPPEN[GRUPPE_JE_ART[art]][0] if art in GRUPPE_JE_ART else ""


def _akte(e) -> str:
    d = e.details or {}
    try:
        nummer = f"Nr. {int(e.objekt):04d}"
    except (TypeError, ValueError):
        nummer = e.objekt
    return f"Akte {d['name']} ({nummer})" if d.get("name") else f"Akte {nummer}"


def _wert(w) -> str:
    if w is True:
        return "ein"
    if w is False:
        return "aus"
    return "–" if w in (None, "") else str(w)


def _aenderungen(d) -> str:
    teile = []
    for feld, werte in (d.get("aenderungen") or {}).items():
        name = (d.get("bezeichnungen") or {}).get(feld, feld)
        if isinstance(werte, (list, tuple)) and len(werte) in (2, 3):
            einheit = f" {werte[2]}" if len(werte) == 3 and werte[2] else ""
            teile.append(f"„{name}“ von {_wert(werte[0])} auf {_wert(werte[1])}{einheit} geändert")
        else:
            teile.append(f"„{name}“ geändert")
    return "; ".join(teile)


def beschreibung(e) -> str:
    d = e.details or {}
    art = e.art
    if art == A.ANMELDUNG:
        return {
            "2fa": "Anmeldung mit 2FA",
            "notfallcode": f"Anmeldung mit Notfall-Code (noch {d.get('verbleibend', '?')} übrig)",
            "kennwort": "Kennwort richtig, zweiter Faktor ausstehend",
        }.get(d.get("schritt"), "Anmeldung")
    if art == A.ABMELDUNG:
        return "Abmeldung"
    if art == A.ANMELDUNG_FEHLGESCHLAGEN:
        if d.get("grund") == "einmal_kennwort_abgelaufen":
            return "Einmal-Kennwort abgelaufen"
        return "Falsches Passwort" + (f" ({d['versuch']}. Versuch)" if d.get("versuch") else "")
    if art == A.ZWEITER_FAKTOR_FEHLGESCHLAGEN:
        if d.get("schritt") == "einrichten":
            return "Falscher Code bei der Einrichtung des Authenticators"
        return "Falscher 2FA-Code" + (f" ({d['versuch']}. Versuch)" if d.get("versuch") else "")
    if art == A.ANMELDUNG_GESPERRT:
        if d.get("versuch_trotz_sperre"):
            return "Anmeldeversuch bei gesperrtem Konto"
        was = "falsche Passwörter" if d.get("letzter_fehler") == "kennwort" else "Fehlversuche"
        zeit = f" in {d['minuten']} Minuten" if d.get("minuten") else ""
        return f"{d.get('fehlversuche', '')} {was}{zeit}, Konto gesperrt".strip()
    if art == A.KENNWORT_GEAENDERT:
        return "Eigenes Kennwort bei der ersten Anmeldung gesetzt" if d.get("erstanmeldung") else "Kennwort geändert"
    if art == A.ZWEITER_FAKTOR_EINGERICHTET:
        if d.get("notfallcodes_neu"):
            return "Notfall-Codes neu erzeugt"
        return "Authenticator eingerichtet" + (" (Kommandozeile)" if d.get("quelle") == "Kommandozeile" else "")
    if art == A.BENUTZER_ANGELEGT:
        from accounts.models import Rolle

        rolle = dict(Rolle.choices).get(d.get("rolle"), d.get("rolle", ""))
        return f"Benutzer {e.objekt} angelegt ({rolle}), Einmal-Kennwort erzeugt"
    if art == A.BENUTZER_GEAENDERT:
        if d.get("entsperrt"):
            return f"Benutzer {e.objekt} entsperrt"
        felder = ", ".join(d.get("aenderungen") or {})
        return f"Benutzer {e.objekt} geändert" + (f": {felder}" if felder else "")
    if art == A.RECHTE_GEAENDERT:
        teile = [f"{t['rolle']} {'darf jetzt' if t['erlaubt'] else 'darf nicht mehr'} „{t['recht']}“"
                 for t in d.get("aenderungen", [])]
        return "Rechte geändert: " + "; ".join(teile) if teile else "Rechte geändert"
    if art == A.BENUTZER_GESPERRT:
        return f"Benutzer {e.objekt} gesperrt"
    if art == A.EINMAL_KENNWORT:
        return f"Neues Einmal-Kennwort für {e.objekt} erzeugt"
    if art == A.ZWEITER_FAKTOR_ZURUECKGESETZT:
        return f"2FA für {e.objekt} zurückgesetzt, Einmal-Kennwort erzeugt"
    if art == A.AKTE_ABGESCHLOSSEN:
        from patienten.models import Patient

        anlass = dict(Patient.Abschlussanlass.choices).get(d.get("anlass"), d.get("anlass", ""))
        return f"{_akte(e)} abgeschlossen, Anlass: {anlass}"
    if art == A.AKTE_GEOEFFNET:
        return f"{_akte(e)} wieder geöffnet, Grund: {d.get('grund', '')}"
    if art == A.PLAN_FREIGEGEBEN:
        return f"Infusionsplan freigegeben ({e.objekt})"
    if art == A.STAMMDATEN:
        if d.get("aenderungen"):
            if e.objekt == "Einstellungen":
                return f"Grenzwert {_aenderungen(d)}"
            return f"{e.objekt}: {_aenderungen(d)}"
        if d.get("aktion") == "Patienten neu zugeordnet":
            return f"{e.objekt}: {d.get('anzahl', 0)} Patienten an {d.get('ziel', '')} übergeben"
        return f"{e.objekt} {d.get('aktion', 'geändert')}"
    if art == A.VORLAGE:
        if d.get("aenderungen"):
            return f"{e.objekt}: {_aenderungen(d)}"
        return f"{e.objekt}: {d.get('aktion', 'geändert')}"
    if art == A.EXPORT:
        return f"{d.get('was', 'Export')} als PDF: {e.objekt}" if e.objekt else f"{d.get('was', 'Export')} als PDF"
    if art == A.TESTDATEN:
        return f"Testdaten zurückgesetzt: {d.get('geloescht', 0)} Testpatienten gelöscht, {d.get('angelegt', 0)} neu angelegt"
    return e.get_art_display() + (f" {e.objekt}" if e.objekt else "")
