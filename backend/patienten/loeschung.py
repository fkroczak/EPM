"""
Endgültiges Löschen eines Dokuments nach Art. 17 DSGVO (Festlegung 02.10.2026, U15).

Ein Dokument, das zu keinem Patienten der Stiftung gehört, wird überall entfernt, wo es Inhalt oder beschreibende
Angaben hinterlassen hat: Datei, Datensatz, Titel, Original-Dateiname, Notiz und Dokumentdatum – auch in der Historie
und im Audit-Log (Art. 5 Abs. 1 c, e; Art. 17 Abs. 1 d). Was bleibt, ist der Nachweis ohne Inhalt (Art. 5 Abs. 2,
Art. 33 Abs. 5; § 630f BGB: die Änderung der Akte bleibt mit Zeitpunkt erkennbar): dass in Akte X ein Dokument
Nummer N entfernt wurde, wann, von wem, mit welchem Grund, Dokumenttyp, Größe und SHA-256-Prüfsumme.

Sicherungen enthalten das Dokument bis zu ihrem Ablauf weiter. Damit eine Wiederherstellung es nicht zurückbringt,
steht jede Löschung zusätzlich in der Löschliste (eigener Ordner, weder in der Datenbank noch im Dokumentordner);
`epm_loeschungen_nachholen` läuft bei jedem Start des Backends und löscht und schwärzt erneut, was eine
Wiederherstellung zurückgebracht hat.
"""
import hashlib
import json
import os
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction

PLATZHALTER = "[entfernt]"
DOKUMENT_ARTEN = ["dokument_umgehaengt", "dokument_geloescht", "dokument_loeschen_abgelehnt", "dokument_text_erkannt"]


def schwaerze_dokument(dokument_id: int, sha256: str) -> dict:
    """Ersetzt Titel, Original-Dateinamen, Notiz und Datum des Dokuments in Historie und Audit-Log durch den
    Platzhalter. Die Schutz-Trigger lassen genau diese Änderung für genau dieses Dokument zu (audit/schutz.py).
    Mehrfach aufrufbar; gibt die Zahl der geänderten Zeilen zurück."""
    with transaction.atomic(), connection.cursor() as c:
        c.execute("SELECT set_config('epm.schwaerzen', %s, true)", [f"dokument:{int(dokument_id)}:{sha256}"])
        c.execute(
            """UPDATE patienten_historicaldokument
                  SET titel = %s, originalname = %s, notiz = '', datum = NULL
                WHERE id = %s AND sha256 = %s
                  AND (titel <> %s OR originalname <> %s OR notiz <> '' OR datum IS NOT NULL)""",
            [PLATZHALTER, PLATZHALTER, dokument_id, sha256, PLATZHALTER, PLATZHALTER],
        )
        historie = c.rowcount
        c.execute(
            """UPDATE audit_systemereignis
                  SET details = jsonb_set(details, '{titel}', to_jsonb(%s::text))
                WHERE objekt = %s AND art = ANY(%s) AND details ->> 'sha256' = %s
                  AND details ->> 'titel' IS NOT NULL AND details ->> 'titel' <> %s""",
            [PLATZHALTER, f"Dokument {int(dokument_id)}", DOKUMENT_ARTEN, sha256, PLATZHALTER],
        )
        protokoll = c.rowcount
        c.execute("SELECT set_config('epm.schwaerzen', '', true)")
    return {"historie": historie, "protokoll": protokoll}


def loeschliste() -> Path:
    return Path(settings.EPM_LOESCHLISTE)


def trage_ein(eintrag: dict) -> None:
    """Hängt eine Löschung an die Löschliste an (eine JSON-Zeile, sofort auf die Platte geschrieben).
    Dokument: nur Nummer, Prüfsumme, Pfad, Akte (Patienten-ID), Person (Benutzer-ID) und Zeitpunkt – kein Titel.
    Akte (``patienten.datenschutz``): Kennung, Patientennummer, Daten zu Anlage, Abschluss und Frist, Rechtsgrund,
    der eingetragene Grund (Freitext), Umfang in Zahlen, Person, Zeitpunkt – kein Name."""
    pfad = loeschliste()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    zeile = json.dumps(eintrag, ensure_ascii=False, sort_keys=True) + "\n"
    with open(pfad, "a", encoding="utf-8") as f:
        f.write(zeile)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.chmod(pfad, 0o600)
    except OSError:
        pass


def lies_liste() -> list[dict]:
    pfad = loeschliste()
    if not pfad.exists():
        return []
    eintraege = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        try:
            e = json.loads(zeile)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("dokument") and e.get("sha256"):
            eintraege.append(e)
    return eintraege


def unlesbare_zeilen() -> int:
    """Zeilen der Löschliste, die sich nicht lesen lassen (kein JSON-Objekt) – etwa nach einem abgebrochenen
    Schreibvorgang oder einer Bearbeitung von Hand. ``lies_liste`` und ``lies_akten`` überspringen sie; eine Löschung,
    die nur in einer solchen Zeile steht, würde nach einer Wiederherstellung nicht nachgeholt."""
    pfad = loeschliste()
    if not pfad.exists():
        return 0
    anzahl = 0
    for zeile in pfad.read_bytes().splitlines():
        if not zeile.strip():
            continue
        try:
            if not isinstance(json.loads(zeile.decode("utf-8")), dict):
                anzahl += 1
        except ValueError:   # auch UnicodeDecodeError
            anzahl += 1
    return anzahl


def _stand_pfad() -> Path:
    return loeschliste().with_name("nachholen.json")


def nachholen_stand() -> dict | None:
    """Ergebnis des letzten Laufs von ``epm_loeschungen_nachholen`` (``status`` ok | fehler, ``zeitpunkt``, ``text``).
    Liegt neben der Löschliste – außerhalb der Datenbank, damit es eine Wiederherstellung übersteht."""
    try:
        daten = json.loads(_stand_pfad().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return daten if isinstance(daten, dict) and daten.get("status") in ("ok", "fehler") else None


def nachholen_stand_schreiben(status: str, text: str, zeitpunkt: str) -> None:
    pfad = _stand_pfad()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_name(f".{pfad.name}.{os.getpid()}")
    tmp.write_text(json.dumps({"status": status, "text": text, "zeitpunkt": zeitpunkt}, ensure_ascii=False),
                   encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, pfad)


def datei_pruefsumme(pfad: Path) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for teil in iter(lambda: f.read(1024 * 1024), b""):
            h.update(teil)
    return h.hexdigest()
