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

VORLAGE_SQL = r"""
CREATE OR REPLACE FUNCTION epm_vorlage_schutz() RETURNS trigger AS $$
BEGIN
    IF coalesce(current_setting('epm.wartung', true), '') = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    IF OLD.status = 'entwurf' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    -- veröffentlicht: nur aktiv -> abgeloest, sonst nichts (jede gespeicherte PDF verweist auf ihre Version)
    IF TG_OP = 'UPDATE' AND OLD.status = 'aktiv' AND NEW.status = 'abgeloest'
       AND (to_jsonb(NEW) - 'status' - 'geaendert_am') = (to_jsonb(OLD) - 'status' - 'geaendert_am') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'EPM: veröffentlichte Dokumentvorlagen sind unveränderlich' USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""

VITAMINE_SQL = r"""
CREATE OR REPLACE FUNCTION epm_plan_zuordnung_schutz() RETURNS trigger AS $$
DECLARE
    plan_status text;
BEGIN
    IF coalesce(current_setting('epm.wartung', true), '') = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    SELECT status INTO plan_status FROM infusionen_infusionsplan
        WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.infusionsplan_id ELSE NEW.infusionsplan_id END;
    IF plan_status IS DISTINCT FROM 'entwurf' THEN
        RAISE EXCEPTION 'EPM: freigegebene Infusionspläne sind unveränderlich' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
END;
$$ LANGUAGE plpgsql;
"""

# Tabellen mit Sonderregeln (Name der Tabelle -> Funktion)
SONDERREGELN = {
    "patienten_kontakt": "epm_kontakt_schutz",
    "infusionen_infusionsplan": "epm_plan_schutz",
    "vorlagen_dokumentvorlage": "epm_vorlage_schutz",
}
# Zuordnungstabellen von Plänen: auch INSERT prüfen
ZUORDNUNG = {"infusionen_infusionsplan_vitamine": "epm_plan_zuordnung_schutz"}
NUR_ANFUEGEN_FEST = ["audit_systemereignis", "patienten_dokumentvorgang"]


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
        c.execute(VITAMINE_SQL)
        c.execute(VORLAGE_SQL)
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
            # Auch TRUNCATE verhindern (nur reine Protokolltabellen)
            if funktion == "epm_nur_anfuegen":
                c.execute(
                    f'CREATE OR REPLACE TRIGGER epm_schutz_truncate BEFORE TRUNCATE ON "{tabelle}" '
                    f"FOR EACH STATEMENT EXECUTE FUNCTION epm_nur_anfuegen()"
                )
        _zuordnung(c, vorhandene)


def _zuordnung(c, vorhandene):
    for tabelle, funktion in ZUORDNUNG.items():
        if tabelle in vorhandene:
            c.execute(
                f'CREATE OR REPLACE TRIGGER epm_schutz BEFORE INSERT OR UPDATE OR DELETE ON "{tabelle}" '
                f"FOR EACH ROW EXECUTE FUNCTION {funktion}()"
            )


@contextmanager
def wartungsmodus():
    """Erlaubt innerhalb der Transaktion Änderungen an geschützten Tabellen. Sparsam verwenden!"""
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET LOCAL epm.wartung = 'on'")
        yield
