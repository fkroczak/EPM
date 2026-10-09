"""
Wartung des EPM, direkt im Backend (Administration › System). Jede Aufgabe liefert eine Kurzfassung und Einzelheiten;
die Ansicht legt dazu einen Systemauftrag (Ziel „EPM“) und einen Eintrag im Audit-Log an.
"""
import hashlib
import os
import platform
import django
from django.conf import settings
from django.db import connection
from django.utils import timezone

AUFGABEN = {
    "sitzungen_bereinigen": {
        "name": "Abgelaufene Sitzungen bereinigen", "bestaetigung": "keine",
        "beschreibung": "Abgelaufene Anmeldungen aus der Datenbank entfernen (angemeldete Benutzer bleiben angemeldet).",
    },
    "datenbank_optimieren": {
        "name": "Datenbank optimieren", "bestaetigung": "einfach",
        "beschreibung": "VACUUM und ANALYZE: Speicher freigeben und Statistiken für schnelle Abfragen erneuern.",
    },
    "dokumente_pruefen": {
        "name": "Dokumente prüfen", "bestaetigung": "keine",
        "beschreibung": "Jede Datei vorhanden und gleich groß? Mit Prüfsummen: Inhalt unverändert (dauert länger).",
    },
    "schutz_pruefen": {
        "name": "Unveränderlichkeit prüfen", "bestaetigung": "keine",
        "beschreibung": "Schutz-Trigger für Verlauf, Audit-Log, Kontakte und freigegebene Pläne prüfen und fehlende "
                        "wieder setzen.",
    },
    "konfiguration_pruefen": {
        "name": "Konfiguration prüfen", "bestaetigung": "keine",
        "beschreibung": "Sicherheitsprüfung von Django für den Betrieb (Einstellungen, Cookies, HTTPS).",
    },
    "alle_abmelden": {
        "name": "Alle anderen Benutzer abmelden", "bestaetigung": "einfach",
        "beschreibung": "Beendet alle Anmeldungen außer der eigenen, z. B. vor Wartungsarbeiten.",
    },
}

# Hinweise der Django-Sicherheitsprüfung, die im EPM bewusst anders gelöst sind
BEKANNTE_HINWEISE = {
    "security.W004": "HSTS setzt Nginx (Strict-Transport-Security in nginx/epm.conf).",
    "security.W008": "Nginx nimmt nur HTTPS an; eine Umleitung in Django ist nicht nötig.",
}


# ------------------------------------------------------------------ Überblick
def datenbank_info():
    with connection.cursor() as c:
        c.execute("SHOW server_version")
        version = c.fetchone()[0]
        c.execute("SELECT pg_database_size(current_database())")
        groesse = c.fetchone()[0]
        c.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
        verbindungen = c.fetchone()[0]
        c.execute(
            """
            SELECT relname, pg_total_relation_size(relid), n_live_tup, n_dead_tup,
                   greatest(last_vacuum, last_autovacuum), greatest(last_analyze, last_autoanalyze)
            FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 8
            """
        )
        tabellen = [{"name": r[0], "groesse": r[1], "zeilen": r[2], "tot": r[3], "vacuum_am": r[4], "analyze_am": r[5]}
                    for r in c.fetchall()]
        c.execute("SELECT max(greatest(last_vacuum, last_autovacuum)), sum(n_dead_tup) FROM pg_stat_user_tables")
        letzte_wartung, tote = c.fetchone()
    return {"version": version, "groesse": groesse, "verbindungen": verbindungen, "tabellen": tabellen,
            "letzte_wartung": letzte_wartung, "tote_zeilen": tote or 0}


def migrationen_offen() -> int:
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    return len(executor.migration_plan(executor.loader.graph.leaf_nodes()))


def epm_info():
    from accounts import zweifaktor
    from accounts.models import Rolle, User
    from patienten.models import Dokument, Patient

    konten = User.objects.filter(nur_historisch=False, ausgeblendet_am__isnull=True)  # ausgeblendete Testbenutzer nicht
    mit_2fa = zweifaktor.nutzer_mit_zweitem_faktor()  # Authenticator oder Passkey
    ohne_2fa = list(konten.filter(is_active=True).exclude(id__in=mit_2fa).order_by("last_name", "first_name"))
    einmal = list(konten.filter(is_active=True, muss_kennwort_aendern=True).order_by("last_name", "first_name"))
    dokumente = Dokument.objects.all()
    try:
        s = os.statvfs(settings.EPM_DOKUMENTE)
        platz = {"gesamt": s.f_blocks * s.f_frsize, "frei": s.f_bavail * s.f_frsize}
    except OSError:
        platz = None
    return {
        "version": settings.EPM_VERSION or "unbekannt",
        "python": platform.python_version(),
        "django": django.get_version(),
        "zeitzone": settings.TIME_ZONE,
        "datenbank": datenbank_info(),
        "migrationen_offen": migrationen_offen(),
        "schutz": schutz_stand(),
        "patienten": {
            "in_betreuung": Patient.objects.filter(abgeschlossen_am__isnull=True, ist_test=False).count(),
            "abgeschlossen": Patient.objects.filter(abgeschlossen_am__isnull=False, ist_test=False).count(),
            "testpatienten": Patient.objects.filter(ist_test=True).count(),
        },
        "dokumente": {
            "anzahl": dokumente.count(),
            "groesse": sum(dokumente.values_list("groesse", flat=True)),
            "ungeprueft": dokumente.filter(typ_geprueft=False, ausgeblendet=False).count(),
            "platz": platz,
        },
        "konten": {
            "aktiv": konten.filter(is_active=True).count(),
            "gesperrt": konten.filter(gesperrt_am__isnull=False).count(),
            "ohne_2fa": len(ohne_2fa),
            # wer das ist – für den direkten Weg zur Einrichtung (Fehlerliste 02.10.2026, Punkt 4.2)
            "ohne_2fa_konten": [{"id": u.id, "anzeigename": u.anzeigename, "benutzername": u.username} for u in ohne_2fa],
            "zweiter_faktor": zweifaktor.regel(),
            "einmal_kennwort_offen": len(einmal),
            "einmal_kennwort_konten": [{"id": u.id, "anzeigename": u.anzeigename, "benutzername": u.username}
                                       for u in einmal],
            "gesperrt_konten": [{"id": u.id, "anzeigename": u.anzeigename, "benutzername": u.username}
                                for u in konten.filter(gesperrt_am__isnull=False).order_by("last_name", "first_name")],
            "admins": konten.filter(is_active=True, rolle=Rolle.ADMIN).count(),
        },
        "texterkennung": texterkennung_info(),
    }


def texterkennung_info():
    """Scans und OCR-Dienst (F167): Verfahren im Image, Lebenszeichen des Dienstes, Warteschlange, Speicher."""
    from scans import dienst

    try:
        verfahren = dienst.verfahren()
    except Exception as e:  # noqa: BLE001 – Systemseite soll trotzdem laden
        verfahren = {"fehler": str(e)[:200]}
    return {"verfahren": verfahren, "dienst": dienst.dienst_stand(), "scans": dienst.stand()}


def angemeldete_sitzungen():
    """Alle gültigen Anmeldungen (alle Benutzer), neueste Aktivität zuerst."""
    from django.contrib.sessions.models import Session

    from accounts.models import Sitzung

    gueltig = Session.objects.filter(expire_date__gt=timezone.now()).values("session_key")
    return (Sitzung.objects.filter(sitzungsschluessel__in=gueltig).select_related("benutzer")
            .order_by("-zuletzt_am"))


# ------------------------------------------------------------------ Aufgaben
def sitzungen_bereinigen(request, **_):
    from django.contrib.sessions.models import Session

    from accounts.models import Sitzung

    abgelaufen, _d = Session.objects.filter(expire_date__lte=timezone.now()).delete()
    gueltig = Session.objects.values("session_key")
    verwaist, _d = Sitzung.objects.exclude(sitzungsschluessel__in=gueltig).delete()
    return 0, f"{abgelaufen} abgelaufene Sitzungen und {verwaist} Geräteeinträge entfernt.", ""


def datenbank_optimieren(request, **_):
    from django.db import connections

    vorher = datenbank_info()
    zeilen = []
    # VACUUM geht nicht innerhalb einer Transaktion (jede Anfrage läuft in einer): eigene Verbindung im Autocommit.
    # Wartet höchstens 10 s auf Sperren, damit die Anfrage nie hängen bleibt.
    eigene = connections.create_connection("default")
    try:
        eigene.ensure_connection()
        eigene.set_autocommit(True)
        with eigene.cursor() as c:
            c.execute("SET lock_timeout = '10s'")
            c.execute("VACUUM (ANALYZE)")
        zeilen.append("VACUUM (ANALYZE) ausgeführt.")
    except Exception as e:  # noqa: BLE001 – dann wenigstens die Statistiken erneuern
        zeilen.append(f"VACUUM nicht möglich ({e}); nur ANALYZE ausgeführt.")
        with connection.cursor() as c:
            c.execute("ANALYZE")
    finally:
        eigene.close()
    nachher = datenbank_info()
    frei = max(0, vorher["groesse"] - nachher["groesse"])
    zeilen.append(f"Größe vorher {vorher['groesse']} Bytes, nachher {nachher['groesse']} Bytes.")
    zeilen.append(f"Nicht mehr benötigte Zeilen vorher: {vorher['tote_zeilen']}, nachher: {nachher['tote_zeilen']}.")
    kurz = "Datenbank optimiert" + (f", {frei // 1024} KB frei geworden." if frei >= 1024 else ".")
    return 0, kurz, "\n".join(zeilen)


def _sha256(pfad):
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for teil in iter(lambda: f.read(1 << 20), b""):
            h.update(teil)
    return h.hexdigest()


def dokumente_pruefen(request, pruefsummen=False, **_):
    """Dateien der Akte, gespeicherte Plan-PDFs und Logos gegen die Datenbank; zusätzlich Dateien ohne Eintrag."""
    from infusionen.models import Infusionsplan
    from patienten.models import Dokument
    from stammdaten.models import Logo

    basis = settings.EPM_DOKUMENTE
    probleme, bekannt = [], set()
    gepruft = 0
    # ohne Titel: die Ausgabe sieht die Administration, die eingeschränkte Akten nur mit Nummer sehen darf (Art. 18 DSGVO)
    eintraege = [(d.datei, d.groesse, d.sha256, f"Dokument {d.id} (Patient {d.patient.nummer})")
                 for d in Dokument.objects.select_related("patient")]
    eintraege += [(p.pdf_datei, None, p.pdf_sha256, f"Infusionsplan {p.id} (Patient {p.patient.nummer})")
                  for p in Infusionsplan.objects.exclude(pdf_datei="").exclude(pdf_datei__isnull=True)
                  .select_related("patient")]
    eintraege += [(lg.datei, None, None, "Logo") for lg in Logo.objects.all()]
    for datei, groesse, pruefsumme, was in eintraege:
        bekannt.add(datei)
        pfad = basis / datei
        gepruft += 1
        if not pfad.is_file():
            probleme.append(f"fehlt: {was} – {datei}")
            continue
        if groesse is not None and pfad.stat().st_size != groesse:
            probleme.append(f"Größe weicht ab: {was} – {datei}")
            continue
        if pruefsummen and pruefsumme and _sha256(pfad) != pruefsumme:
            probleme.append(f"Prüfsumme weicht ab (Datei verändert): {was} – {datei}")
    ohne_eintrag = []
    if basis.is_dir():
        for wurzel, _ordner, dateien in os.walk(basis):
            for name in dateien:
                relativ = os.path.relpath(os.path.join(wurzel, name), basis)
                if relativ not in bekannt and not name.startswith("."):
                    ohne_eintrag.append(relativ)
    zeilen = [f"{gepruft} Dateien geprüft" + (" mit Prüfsummen." if pruefsummen else " (vorhanden, Größe).")]
    zeilen += probleme[:200]
    if ohne_eintrag:
        zeilen.append(f"{len(ohne_eintrag)} Dateien ohne Eintrag in der Datenbank (werden nicht gelöscht):")
        zeilen += [f"  {x}" for x in sorted(ohne_eintrag)[:100]]
    if probleme:
        return 1, f"{len(probleme)} von {gepruft} Dateien auffällig – Einzelheiten ansehen.", "\n".join(zeilen)
    kurz = f"Alle {gepruft} Dateien in Ordnung" + (" (Prüfsummen stimmen)" if pruefsummen else "")
    if ohne_eintrag:
        kurz += f"; {len(ohne_eintrag)} Dateien ohne Eintrag"
    return 0, kurz + ".", "\n".join(zeilen)


def schutz_stand():
    """Erwartete und vorhandene Schutz-Trigger (audit/schutz.py)."""
    from audit import schutz

    if connection.vendor != "postgresql":
        return {"erwartet": 0, "vorhanden": 0, "fehlend": []}
    with connection.cursor() as c:
        vorhandene_tabellen = set(connection.introspection.table_names(c))
        erwartet = {t: "epm_schutz" for t in schutz._historientabellen(c) + schutz.NUR_ANFUEGEN_FEST}
        erwartet.update({t: "epm_schutz" for t in schutz.SONDERREGELN})
        erwartet.update({t: "epm_schutz" for t in schutz.ZUORDNUNG})
        erwartet = {t: n for t, n in erwartet.items() if t in vorhandene_tabellen}
        c.execute(
            """
            SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
            WHERE t.tgname = 'epm_schutz' AND NOT t.tgisinternal AND t.tgenabled <> 'D'
            """
        )
        vorhanden = {r[0] for r in c.fetchall()}
    fehlend = sorted(set(erwartet) - vorhanden)
    return {"erwartet": len(erwartet), "vorhanden": len(set(erwartet) & vorhanden), "fehlend": fehlend}


def schutz_pruefen(request, **_):
    from audit.schutz import installiere_trigger

    vorher = schutz_stand()
    if vorher["fehlend"]:
        installiere_trigger()
    nachher = schutz_stand()
    zeilen = [f"Erwartet: {nachher['erwartet']} Tabellen, geschützt: {nachher['vorhanden']}."]
    if vorher["fehlend"]:
        zeilen.append("Fehlten und wurden neu gesetzt: " + ", ".join(vorher["fehlend"]))
    if nachher["fehlend"]:
        return 1, f"{len(nachher['fehlend'])} Tabellen ohne Schutz – Einzelheiten ansehen.", "\n".join(
            zeilen + ["Weiterhin ohne Schutz: " + ", ".join(nachher["fehlend"])])
    if vorher["fehlend"]:
        return 0, f"{len(vorher['fehlend'])} fehlende Schutz-Trigger wieder gesetzt.", "\n".join(zeilen)
    return 0, f"Alle {nachher['erwartet']} geschützten Tabellen in Ordnung.", "\n".join(zeilen)


def konfiguration_pruefen(request, **_):
    from django.core.checks import run_checks

    meldungen = run_checks(include_deployment_checks=True)
    offen, bekannt = [], []
    for m in meldungen:
        text = f"{m.id}: {m.msg}".replace("\n", " ")
        if m.id in BEKANNTE_HINWEISE:
            bekannt.append(f"{m.id}: bewusst so – {BEKANNTE_HINWEISE[m.id]}")
        else:
            offen.append(text)
    zeilen = offen + bekannt + [f"DEBUG: {'an' if settings.DEBUG else 'aus'}",
                                f"Sitzung läuft ab nach {settings.SESSION_COOKIE_AGE // 60} Minuten ohne Aktivität",
                                f"Erlaubte Adressen: {', '.join(settings.ALLOWED_HOSTS)}"]
    if settings.DEBUG:
        offen.append("DEBUG ist eingeschaltet")
    if offen:
        return 1, f"{len(offen)} Hinweise der Sicherheitsprüfung – Einzelheiten ansehen.", "\n".join(zeilen)
    return 0, "Keine offenen Hinweise" + (f" ({len(bekannt)} bewusst anders gelöst)." if bekannt else "."), \
        "\n".join(zeilen)


def alle_abmelden(request, **_):
    from accounts.models import Sitzung
    from accounts.sitzungen import sitzung_beenden

    eigene = request.session.session_key if getattr(request, "session", None) else None
    anzahl = 0
    for s in Sitzung.objects.exclude(sitzungsschluessel=eigene or ""):
        sitzung_beenden(s)
        anzahl += 1
    from django.contrib.sessions.models import Session

    # auch Sitzungen ohne Geräteeintrag (z. B. vor der Erfassung angemeldet), außer der eigenen
    rest, _d = Session.objects.exclude(session_key=eigene or "").delete()
    return 0, f"{max(anzahl, rest)} Anmeldungen beendet.", ""


AUSFUEHRUNG = {
    "sitzungen_bereinigen": sitzungen_bereinigen,
    "datenbank_optimieren": datenbank_optimieren,
    "dokumente_pruefen": dokumente_pruefen,
    "schutz_pruefen": schutz_pruefen,
    "konfiguration_pruefen": konfiguration_pruefen,
    "alle_abmelden": alle_abmelden,
}
