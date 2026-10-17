"""Datenbank-Rolle ``epm_ki`` für den KI-Dienst: technische Schreibsperre für die Akte (Auftrag 3 und 8).

Der KI-Dienst meldet sich mit dieser Rolle an. Sie darf alles **lesen** außer Anmeldedaten (Sitzungen, zweiter
Faktor), aber nur in die Tabellen der KI (``ki_*``; Nachweise nur anfügen) und in das Audit-Log (nur anfügen)
**schreiben**. Selbst ein Fehler im Dienst kann so nichts in die Patientenakte schreiben – das geht ausschließlich
über das Backend, im Namen eines angemeldeten Mitarbeiters.

Eingerichtet bzw. nachgezogen wird die Rolle vom Backend nach jeder Migration (``entrypoint.sh`` →
``manage.py epm_ki_dbrolle``), damit neue KI-Tabellen sofort erfasst sind.
"""
from django.db import connection
from psycopg import sql

ROLLE = "epm_ki"
SCHREIBEN_PRAEFIX = "ki_"
# Nachweise (unveränderlich, nur anfügen) – auch der KI-Dienst darf sie weder ändern noch löschen
NUR_ANFUEGEN = ["audit_systemereignis", "ki_kirohergebnis", "ki_kikorrektur", "ki_kiuebernahme"]
# Modell-Registry: Der Dienst trägt nur das Ergebnis eines Evaluationslaufs ein (ki/evaluation.py) – aktivieren,
# sperren und registrieren bleibt dem Backend
NUR_SPALTEN = {"ki_kimodellversion": ["evaluation"]}
# Anmeldedaten braucht der Dienst nicht: Sitzungen, zweiter Faktor (TOTP-/Notfallcodes, Passkeys)
NICHT_LESEN = ["django_session", "accounts_sitzung", "accounts_passkey"]
NICHT_LESEN_PRAEFIX = "otp_"


def _tabellen(cursor) -> list[str]:
    cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()")
    return sorted(r[0] for r in cursor.fetchall())


def einrichten(passwort: str | None = None, rolle: str = ROLLE) -> dict:
    """Rolle anlegen bzw. Rechte nachziehen; → Zusammenfassung. Ohne Passwort: Rolle ohne Anmeldung (Tests)."""
    with connection.cursor() as c:
        c.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [rolle])
        vorhanden = c.fetchone() is not None
        ident = sql.Identifier(rolle)
        if not vorhanden:
            c.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT").format(ident))
        if passwort:
            c.execute(sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(ident, sql.Literal(passwort)))
        c.execute("SELECT current_database(), current_schema()")
        db, schema = c.fetchone()
        c.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(db), ident))
        c.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), ident))
        tabellen = _tabellen(c)
        schreiben = [t for t in tabellen if t.startswith(SCHREIBEN_PRAEFIX) and t not in NUR_ANFUEGEN
                     and t not in NUR_SPALTEN]
        for t in tabellen:
            ti = sql.Identifier(t)
            c.execute(sql.SQL("REVOKE ALL ON TABLE {} FROM {}").format(ti, ident))
            if t in NICHT_LESEN or t.startswith(NICHT_LESEN_PRAEFIX):
                continue
            c.execute(sql.SQL("GRANT SELECT ON TABLE {} TO {}").format(ti, ident))
            if t in schreiben:
                c.execute(sql.SQL("GRANT INSERT, UPDATE, DELETE ON TABLE {} TO {}").format(ti, ident))
            elif t in NUR_ANFUEGEN:
                c.execute(sql.SQL("GRANT INSERT ON TABLE {} TO {}").format(ti, ident))
            elif t in NUR_SPALTEN:
                spalten = sql.SQL(", ").join(map(sql.Identifier, NUR_SPALTEN[t]))
                c.execute(sql.SQL("GRANT UPDATE ({}) ON TABLE {} TO {}").format(spalten, ti, ident))
        c.execute("SELECT sequencename FROM pg_sequences WHERE schemaname = current_schema()")
        for (seq,) in c.fetchall():
            si = sql.Identifier(seq)
            c.execute(sql.SQL("REVOKE ALL ON SEQUENCE {} FROM {}").format(si, ident))
            if seq.startswith(SCHREIBEN_PRAEFIX) or any(seq.startswith(t) for t in NUR_ANFUEGEN):
                c.execute(sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO {}").format(si, ident))
    return {"rolle": rolle, "neu": not vorhanden, "schreiben": schreiben, "nur_anfuegen": NUR_ANFUEGEN,
            "lesen": len(tabellen)}
