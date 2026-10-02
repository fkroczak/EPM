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
    "fehlversuch": ("Fehlversuch", [A.ANMELDUNG_FEHLGESCHLAGEN, A.ZWEITER_FAKTOR_FEHLGESCHLAGEN, A.ANMELDUNG_GESPERRT,
                                    A.DOKUMENT_LOESCHEN_ABGELEHNT, A.AKTE_LOESCHEN_ABGELEHNT]),
    "benutzer": ("Benutzer", [A.BENUTZER_ANGELEGT, A.BENUTZER_GEAENDERT, A.BENUTZER_GESPERRT, A.EINMAL_KENNWORT,
                              A.ZWEITER_FAKTOR_ZURUECKGESETZT, A.TESTDATEN, A.RECHTE_GEAENDERT]),
    "vorlage": ("Vorlage", [A.VORLAGE, A.STAMMDATEN]),
    "backup": ("Backup", [A.BACKUP]),
    "export": ("Export", [A.EXPORT]),
    "abschluss": ("Abschluss", [A.AKTE_ABGESCHLOSSEN, A.AKTE_GEOEFFNET]),
    # ohne eigenen Filterknopf im Entwurf, erscheint unter „alle“
    "infusionsplan": ("Infusionsplan", [A.PLAN_FREIGEGEBEN]),
    "dokument": ("Dokument", [A.DOKUMENT_UMGEHAENGT, A.DOKUMENT_GELOESCHT, A.DOKUMENT_LOESCHUNG_NACHGEHOLT]),
    # Administration › System: Aufträge an den Server, Wartung des EPM, Hinweise an alle Benutzer
    "system": ("System", [A.SYSTEM]),
    "datenschutz": ("Datenschutz", [A.DATENSCHUTZ, A.AKTE_EINGESCHRAENKT, A.AKTE_EINSCHRAENKUNG_AUFGEHOBEN,
                                    A.AKTE_EINSICHT, A.AKTE_GELOESCHT, A.PROTOKOLL_BEREINIGT]),
}
GRUPPE_JE_ART = {art: schluessel for schluessel, (_, arten) in GRUPPEN.items() for art in arten}


def gruppe(art: str) -> str:
    return GRUPPE_JE_ART.get(art, "")


def gruppe_name(art: str) -> str:
    return GRUPPEN[GRUPPE_JE_ART[art]][0] if art in GRUPPE_JE_ART else ""


def _dokument(e) -> str:
    """„Dokument „Titel““ – nach dem endgültigen Löschen (Art. 17 DSGVO) nur noch Nummer, Typ und Prüfsumme."""
    from patienten.loeschung import PLATZHALTER

    d = e.details or {}
    titel = d.get("titel")
    if titel and titel != PLATZHALTER:
        return f"Dokument „{titel}“"
    nummer = e.objekt.removeprefix("Dokument ").strip()
    teile = [t for t in (d.get("typ"), f"SHA-256 {d['sha256'][:8]}…" if d.get("sha256") else "") if t]
    return f"Dokument Nr. {nummer}" + (f" ({', '.join(teile)})" if teile else "")


def _datum(wert: str) -> str:
    from datetime import datetime

    from django.utils import timezone

    try:
        zeit = datetime.fromisoformat(wert)
    except (TypeError, ValueError):
        return str(wert or "")
    if timezone.is_aware(zeit):
        zeit = timezone.localtime(zeit)
    return zeit.strftime("%d.%m.%Y %H:%M")


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
    if d.get("verborgen"):
        # Verarbeitung der Akte eingeschränkt, die lesende Person darf keine Einsicht nehmen (nur für die Anzeige)
        return f"{e.get_art_display()}: {e.objekt}"
    if d.get("entfernt"):
        # Die Akte ist endgültig gelöscht: Der Eintrag bleibt (wer, wann, was), Namen und Inhalte sind entfernt
        return f"{e.get_art_display()}: {e.objekt} – Angaben mit der Akte gelöscht"
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
        if d.get("grund") == "bestaetigung":
            return f"Falsches Passwort bei der Bestätigung: {d.get('was', 'Systemaktion')}"
        return "Falsches Passwort" + (f" ({d['versuch']}. Versuch)" if d.get("versuch") else "")
    if art == A.ZWEITER_FAKTOR_FEHLGESCHLAGEN:
        if d.get("schritt") == "einrichten":
            return "Falscher Code bei der Einrichtung des Authenticators"
        if d.get("schritt") == "bestaetigung":
            return f"Falscher 2FA-Code bei der Bestätigung: {d.get('was', 'Systemaktion')}"
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
        if d.get("quelle") == "altdaten":
            return f"Benutzer {e.objekt} bei der Übernahme der Altdaten angelegt ({rolle}), noch ohne Kennwort"
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
        if d.get("auf_anordnung"):
            return (f"Infusionsplan nach Freigabe durch {d.get('freigegeben_von', '')} am {d.get('freigegeben_am', '')} "
                    f"({d.get('weg', '')}) abgeschlossen ({e.objekt})")
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
        als = d.get("format", "PDF")
        return f"{d.get('was', 'Export')} als {als}: {e.objekt}" if e.objekt else f"{d.get('was', 'Export')} als {als}"
    if art == A.TESTDATEN:
        return f"Testdaten zurückgesetzt: {d.get('geloescht', 0)} Testpatienten gelöscht, {d.get('angelegt', 0)} neu angelegt"
    if art == A.DOKUMENT_UMGEHAENGT:
        return (f"{_dokument(e)} von {d.get('von', '')} zu {d.get('nach', '')} verschoben, "
                f"Grund: {d.get('grund', '')}")
    if art == A.DOKUMENT_GELOESCHT:
        return (f"{_dokument(e)} aus {d.get('akte', '')} endgültig gelöscht – Datei, Titel und Inhalt entfernt "
                f"(Art. 17 DSGVO), Grund: {d.get('grund', '')}")
    if art == A.DOKUMENT_LOESCHEN_ABGELEHNT:
        return f"Löschen von {_dokument(e)} abgelehnt: {d.get('fehler', '')}"
    if art == A.DOKUMENT_LOESCHUNG_NACHGEHOLT:
        return (f"{_dokument(e)} war durch eine Wiederherstellung zurückgekommen und wurde erneut gelöscht "
                f"(Löschung vom {_datum(d.get('geloescht_am', ''))})")
    if art == A.SYSTEM:
        return _system(e, d)
    if art == A.BACKUP:
        return _backup(e, d)
    if art == A.DATENSCHUTZ:
        return f"{e.objekt}: {d.get('aktion', '')}" + (f" – {d['hinweis']}" if d.get("hinweis") else "")
    if art == A.AKTE_EINGESCHRAENKT:
        return f"Verarbeitung eingeschränkt: {e.objekt}, Grund: {d.get('grund', '')}"
    if art == A.AKTE_EINSCHRAENKUNG_AUFGEHOBEN:
        return f"Einschränkung aufgehoben: {e.objekt}, Grund: {d.get('grund', '')}"
    if art == A.AKTE_EINSICHT:
        return f"Einsicht in eingeschränkte Akte: {e.objekt}, Grund: {d.get('grund', '')}"
    if art == A.AKTE_GELOESCHT:
        rechtsgrund = {"frist": "Aufbewahrungsfrist abgelaufen", "antrag": "Antrag der betroffenen Person"}.get(
            d.get("rechtsgrund"), d.get("rechtsgrund", ""))
        return f"{e.objekt} endgültig gelöscht ({rechtsgrund}), Grund: {d.get('grund', '')}"
    if art == A.AKTE_LOESCHEN_ABGELEHNT:
        return f"Löschen abgelehnt: {e.objekt} – {d.get('fehler', '')}"
    if art == A.PROTOKOLL_BEREINIGT:
        return (f"{d.get('anzahl', 0)} Einträge älter als {d.get('jahre', '?')} Jahre entfernt "
                f"(eingestellte Aufbewahrung des Audit-Logs)")
    return e.get_art_display() + (f" {e.objekt}" if e.objekt else "")


def _backup(e, d) -> str:
    """Administration › Backup: Aufträge wie unter System, dazu Passwort und Wiederherstellung (nie ein Passwort)."""
    ereignis = d.get("ereignis")
    if ereignis == "angefordert" and d.get("aktion") == "sicherung_ziel":
        teile = [f"Übertragungsziel festgelegt: {d.get('url', '')}"]
        if d.get("ordner"):
            teile.append(f"Ordner „{d['ordner']}“")
        if d.get("zeitfenster"):
            teile.append(f"Zeitfenster {d['zeitfenster']}")
        teile.append("neues Passwort für das Ziel" if d.get("zugang_neu") else "Passwort für das Ziel unverändert")
        return ", ".join(teile) + (", mit Passwort und 2FA bestätigt" if d.get("bestaetigt") else "")
    if ereignis == "angefordert" and d.get("aktion") == "wiederherstellen":
        zeit = _datum(d.get("sicherung_zeitpunkt", "")) or d.get("stempel", "")
        return (f"Wiederherstellen der Sicherung vom {zeit} angefordert"
                + (f", Beginn in {d['minuten']} Min." if d.get("minuten") else "")
                + (", mit Passwort und 2FA bestätigt" if d.get("bestaetigt") else ""))
    if ereignis == "wiederhergestellt":
        zeit = _datum(d.get("sicherung_zeitpunkt", "")) or d.get("stempel", "")
        text = f"Sicherung vom {zeit} wiederhergestellt, alle Anmeldungen beendet"
        if d.get("vorher_stempel"):
            text += f" – der Stand davor (auch dieses Audit-Log) ist in der Sicherung {d['vorher_stempel']}"
        return text
    if ereignis == "passwortblatt":
        return f"Passwortblatt für Sicherungs-Passwort Nr. {d.get('nr', '?')} gedruckt"
    if ereignis == "passwort_geprueft":
        return f"Sicherungs-Passwort geprüft: passt zu Nr. {d.get('nr', '?')}"
    if ereignis == "passwort_falsch":
        return "Sicherungs-Passwort geprüft: passt zu keinem hinterlegten Passwort"
    return _system(e, d)


def _system(e, d) -> str:
    name = d.get("name") or e.objekt or "Systemaktion"
    ereignis = d.get("ereignis")
    if ereignis == "angefordert":
        teile = [f"{name} angefordert"]
        if d.get("minuten"):
            teile.append(f"Beginn in {d['minuten']} Min.")
        if d.get("bestaetigt"):
            teile.append("mit Passwort und 2FA bestätigt")
        return ", ".join(teile)
    if ereignis == "abgeschlossen":
        zustand = {"erledigt": "erledigt", "fehler": "fehlgeschlagen"}.get(d.get("status"), d.get("status", ""))
        return f"{name} {zustand}" + (f": {d['ergebnis']}" if d.get("ergebnis") else "")
    if ereignis == "abgebrochen":
        return f"{name} zurückgezogen, bevor der Server ihn ausgeführt hat"
    if ereignis == "epm_aufgabe":
        return f"{name}" + (f": {d['ergebnis']}" if d.get("ergebnis") else "")
    if ereignis == "hinweis":
        return f"Hinweis an alle Benutzer: „{d.get('text', '')}“"
    if ereignis == "hinweis_beendet":
        return "Hinweis an alle Benutzer beendet"
    if ereignis == "sitzung_beendet":
        return f"Sitzung von {e.objekt} beendet ({d.get('browser') or 'Browser unbekannt'})"
    return name
