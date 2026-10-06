"""
Revisionssicherheit auf Datenbankebene.

Ein Trigger verhindert UPDATE und DELETE auf allen Historientabellen (simple-history)
und auf dem Systemprotokoll. Kontakte dürfen nur die Storno-Felder ändern.
Ausnahme nur im Wartungsmodus (SET LOCAL epm.wartung = 'on'), z. B. beim
Zurücksetzen der Testdaten, und beim Schwärzen eines endgültig gelöschten Dokuments
(Art. 17 DSGVO, `patienten.loeschung.schwaerze_dokument`): dann dürfen genau Titel,
Dateiname, Notiz und Datum dieses einen Dokuments durch „[entfernt]“ ersetzt werden.

Die Trigger werden nach jeder Migration neu gesetzt (post_migrate), damit auch
künftige Historientabellen automatisch geschützt sind.
"""
from contextlib import contextmanager

from django.db import connection, transaction

FUNKTIONEN_SQL = r"""
CREATE OR REPLACE FUNCTION epm_nur_anfuegen() RETURNS trigger AS $$
DECLARE
    -- Schwärzen nach Art. 17 DSGVO: 'dokument:<Nummer>:<SHA-256>' (SET LOCAL, nur in der Löschtransaktion)
    ziel text := coalesce(current_setting('epm.schwaerzen', true), '');
BEGIN
    IF coalesce(current_setting('epm.wartung', true), '') = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    -- Einzige Ausnahme: Titel, Dateiname, Notiz und Datum eines endgültig gelöschten Dokuments werden durch den
    -- Platzhalter ersetzt. Alles andere an der Zeile muss gleich bleiben; nur dieses eine Dokument (Nummer + Prüfsumme).
    IF TG_OP = 'UPDATE' AND ziel LIKE 'dokument:%:%' THEN
        IF TG_TABLE_NAME = 'patienten_historicaldokument' THEN
            IF OLD.id::text = split_part(ziel, ':', 2) AND OLD.sha256 = split_part(ziel, ':', 3)
               AND NEW.titel = '[entfernt]' AND NEW.originalname = '[entfernt]' AND NEW.notiz = ''
               AND NEW.datum IS NULL
               AND (to_jsonb(NEW) - 'titel' - 'originalname' - 'notiz' - 'datum')
                   = (to_jsonb(OLD) - 'titel' - 'originalname' - 'notiz' - 'datum') THEN
                RETURN NEW;
            END IF;
        ELSIF TG_TABLE_NAME = 'audit_systemereignis' THEN
            IF OLD.objekt = 'Dokument ' || split_part(ziel, ':', 2)
               AND OLD.art IN ('dokument_umgehaengt', 'dokument_geloescht', 'dokument_loeschen_abgelehnt')
               AND OLD.details ->> 'sha256' = split_part(ziel, ':', 3)
               AND NEW.details ->> 'titel' = '[entfernt]'
               AND (NEW.details - 'titel') = (OLD.details - 'titel')
               AND (to_jsonb(NEW) - 'details') = (to_jsonb(OLD) - 'details') THEN
                RETURN NEW;
            END IF;
        END IF;
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

BERICHT_SQL = r"""
CREATE OR REPLACE FUNCTION epm_bericht_schutz() RETURNS trigger AS $$
BEGIN
    IF coalesce(current_setting('epm.wartung', true), '') = 'on' THEN
        RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.status <> 'entwurf' THEN
            RAISE EXCEPTION 'EPM: freigegebene Berichte können nicht gelöscht werden'
                USING ERRCODE = 'insufficient_privilege';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.status = 'entwurf' THEN
        RETURN NEW;  -- Entwurf: frei bearbeitbar, auch die Freigabe selbst
    END IF;
    RAISE EXCEPTION 'EPM: freigegebene Berichte sind unveränderlich' USING ERRCODE = 'insufficient_privilege';
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
    "berichte_bericht": "epm_bericht_schutz",
}
# Zuordnungstabellen von Plänen: auch INSERT prüfen
ZUORDNUNG = {"infusionen_infusionsplan_vitamine": "epm_plan_zuordnung_schutz"}
NUR_ANFUEGEN_FEST = ["audit_systemereignis", "patienten_dokumentvorgang", "patienten_loeschprotokoll"]


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
        c.execute(BERICHT_SQL)
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
    """Erlaubt innerhalb des Blocks Änderungen an geschützten Tabellen. Sparsam verwenden!

    Am Ende des Blocks gilt wieder der Zustand von vorher – auch wenn der Block Teil einer größeren Transaktion
    ist (``SET LOCAL`` allein gälte bis zu deren Ende). Bei einem Fehler nimmt der Rücksprung die Einstellung zurück."""
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SELECT coalesce(current_setting('epm.wartung', true), '')")
            vorher = c.fetchone()[0] or "off"
            c.execute("SELECT set_config('epm.wartung', 'on', true)")
        yield
        with connection.cursor() as c:
            c.execute("SELECT set_config('epm.wartung', %s, true)", [vorher])
