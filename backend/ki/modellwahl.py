"""Welches Modell der Container ``ki-modell`` lädt – Wechsel, Rollback, Probe und Tagesschlaf.

Der Container startet ``llama-server`` über ein kleines Startskript (``rollout/ki/ki-modell-start.sh``). Es liest
aus der gemeinsamen Ablage ``EPM_KI/modell/`` (dort nur lesend eingebunden):

- ``aktiv.env`` – das freigegebene Modell (schreibt das Backend beim Aktivieren bzw. Zurückschalten),
- ``probe.env`` – vorübergehend ein Kandidat für einen Evaluationslauf (schreibt der KI-Dienst, nachts),
- ``schlafen`` – tagsüber ohne Arbeit: llama-server beenden und den Speicher freigeben (schreibt der KI-Dienst).

Je eine ``.json`` daneben ist zum Nachlesen für Menschen. Ändert sich eine Datei, startet das Skript llama-server mit
dem richtigen Modell neu und prüft vorher die SHA-256 der Datei. Produktivmodelle werden nie überschrieben: jede Version ist eine eigene Datei, die vorherige bleibt als
„vorherige Version“ stehen und ist mit einem Klick (Passwort + zweiter Faktor) wieder aktiv.
"""
import json
import os

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import KiModellversion

M = KiModellversion.Status


def ordner():
    pfad = settings.EPM_KI / "modell"
    pfad.mkdir(mode=0o755, parents=True, exist_ok=True)
    return pfad


def kennung(mv: KiModellversion) -> str:
    """Alias, unter dem llama-server das Modell meldet – daran erkennt der Dienst, welches geladen ist."""
    return f"{mv.datei}#{mv.sha256[:12]}"


def _datei(ziel, text: str):
    tmp = ziel.with_name(ziel.name + ".neu")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, ziel)


def _schreiben(name: str, daten: dict | None):
    """``name.env`` (KEY=VALUE für das Startskript – es führt nichts davon aus) und ``name.json``."""
    env, js = ordner() / f"{name}.env", ordner() / f"{name}.json"
    if daten is None:
        env.unlink(missing_ok=True)
        js.unlink(missing_ok=True)
        return
    _datei(js, json.dumps(daten, ensure_ascii=False, indent=1))
    _datei(env, "".join(f"{k.upper()}={daten[k]}\n" for k in ("datei", "projektor", "sha256", "alias")))


def _beschreibung(mv: KiModellversion) -> dict:
    return {"id": mv.pk, "name": mv.name, "datei": mv.datei, "projektor": mv.projektor, "sha256": mv.sha256,
            "alias": kennung(mv), "geaendert": timezone.now().isoformat(timespec="seconds")}


def aktivieren(mv: KiModellversion, user) -> KiModellversion | None:
    """``mv`` wird aktiv, das bisher aktive „vorherige Version“; → bisher aktives Modell."""
    with transaction.atomic():
        bisher = KiModellversion.objects.select_for_update().filter(rolle=mv.rolle, status=M.AKTIV).first()
        # nur die zuletzt aktive bleibt „vorherige Version“; ältere gelten weiter als evaluiert
        KiModellversion.objects.filter(rolle=mv.rolle, status=M.VORHERIG).update(status=M.EVALUATION)
        if bisher is not None:
            bisher.status = M.VORHERIG
            bisher.save(update_fields=["status"])
        mv.status, mv.aktiviert_am, mv.aktiviert_von = M.AKTIV, timezone.now(), user
        mv.save(update_fields=["status", "aktiviert_am", "aktiviert_von"])
        if mv.rolle == KiModellversion.Rolle.VISION:
            transaction.on_commit(lambda: _schreiben("aktiv", _beschreibung(mv)))
    return bisher


def probe_setzen(mv: KiModellversion | None):
    _schreiben("probe", _beschreibung(mv) if mv is not None else None)


def schlafen(an: bool):
    marke = ordner() / "schlafen"
    if an:
        marke.touch()
    else:
        marke.unlink(missing_ok=True)


def schlaeft() -> bool:
    return (settings.EPM_KI / "modell" / "schlafen").exists()
