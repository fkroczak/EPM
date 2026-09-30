"""
Revisionssicherheit auf Datenbankebene.

Ein Trigger verhindert UPDATE und DELETE auf allen Historientabellen (simple-history)
und auf dem Systemprotokoll. Kontakte dürfen nur die Storno-Felder ändern.
Ausnahme nur im Wartungsmodus (SET LOCAL epm.wartung = 'on'), z. B. beim
Zurücksetzen der Testdaten.

Die Trigger werden nach jeder Migration neu gesetzt (post_migrate), damit auch
künftige Historientabellen automatisch geschützt sind.
"""
from contextlib import contextmanager

from django.db import connection, transaction

FUNKTIONEN_SQL = r"""
CREATE OR REPLACE FUNCTION epm_nur_anfuegen() RETURNS trigger AS $$
BEGIN
    IF coalesce(current_setting('epm.wartung', true), '') = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    RAISE EXCEPTION 'EPM: % auf % ist nicht erlaubt (Protokoll ist unveränderlich)', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION epm_kontakt_schutz() RETURNS trigger AS $$
BEGIN
    IF coalesce(current_setting('epm.wartung', true), '') = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'EPM: Kontakte können nicht gelöscht werden' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.patient_id IS DISTINCT FROM OLD.patient_id
       OR NEW.zeitpunkt IS DISTINCT FROM OLD.zeitpunkt
       OR NEW.art_id IS DISTINCT FROM OLD.art_id
       OR NEW.text IS DISTINCT FROM OLD.text
       OR NEW.erfasst_am IS DISTINCT FROM OLD.erfasst_am
       OR NEW.erfasst_von_id IS DISTINCT FROM OLD.erfasst_von_id
       OR OLD.storniert_am IS NOT NULL THEN
        RAISE EXCEPTION 'EPM: Kontakte sind unveränderlich (nur einmaliges Storno)'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION epm_plan_schutz() RETURNS trigger AS $$
BEGIN
    IF coalesce(current_setting('epm.wartung', true), '') = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'entwurf' THEN
            RAISE EXCEPTION 'EPM: freigegebene Infusionspläne können nicht gelöscht werden'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.status = 'entwurf' THEN
        RETURN NEW;  -- Entwurf: frei bearbeitbar, auch die Freigabe selbst
    END IF;
    -- freigegeben: nur aktuell -> abgeloest, sonst nichts
    IF OLD.status = 'aktuell' AND NEW.status = 'abgeloest'
       AND (to_jsonb(NEW) - 'status') = (to_jsonb(OLD) - 'status') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'EPM: freigegebene Infusionspläne sind unveränderlich' USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""

# Tabellen mit Sonderregeln (Name der Tabelle -> Funktion)
SONDERREGELN = {
    "patienten_kontakt": "epm_kontakt_schutz",
    "infusionen_infusionsplan": "epm_plan_schutz",
}
NUR_ANFUEGEN_FEST = ["audit_systemereignis"]


def _historientabellen(cursor):
    cursor.execute(
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname = current_schema() AND tablename LIKE '%%\\_historical%%'
        """
    )
    return [r[0] for r in cursor.fetchall()]


def installiere_trigger(using="default", **kwargs):
    from django.db import connections

    conn = connections[using]
    if conn.vendor != "postgresql":
        return
    with conn.cursor() as c:
        c.execute(FUNKTIONEN_SQL)
        vorhandene = set(conn.introspection.table_names(c))
        ziele = {t: "epm_nur_anfuegen" for t in _historientabellen(c) + NUR_ANFUEGEN_FEST}
        ziele.update(SONDERREGELN)
        for tabelle, funktion in ziele.items():
            if tabelle not in vorhandene:
                continue
            c.execute(
                f'CREATE OR REPLACE TRIGGER epm_schutz BEFORE UPDATE OR DELETE ON "{tabelle}" '
                f"FOR EACH ROW EXECUTE FUNCTION {funktion}()"
            )
            # Auch TRUNCATE verhindern
            if funktion == "epm_nur_anfuegen":
                c.execute(
                    f'CREATE OR REPLACE TRIGGER epm_schutz_truncate BEFORE TRUNCATE ON "{tabelle}" '
                    f"FOR EACH STATEMENT EXECUTE FUNCTION epm_nur_anfuegen()"
                )


@contextmanager
def wartungsmodus():
    """Erlaubt innerhalb der Transaktion Änderungen an geschützten Tabellen. Sparsam verwenden!"""
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET LOCAL epm.wartung = 'on'")
        yield
