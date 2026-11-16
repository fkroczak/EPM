"""Testlauf für ``manage.py test --parallel``.

Viele Testmodule legen ihre Arbeitsordner beim Import an (``tempfile.mkdtemp`` auf Modulebene). Mit dem Linux-Standard
``fork`` teilten sich alle Testprozesse dieselben Ordner und störten sich gegenseitig (12.11.2026). Mit ``spawn``
importiert jeder Prozess die Module neu und bekommt eigene Ordner.

Passwort-Hashes (15.11.2026): Im Betrieb PBKDF2 mit über einer Million Runden (Django-Standard) – je Benutzer, den ein
Test anlegt, und je Anmeldung mehrere Zehntelsekunden. Die Tests prüfen die Anmeldelogik, nicht den Hash-Algorithmus;
daher hier ein schneller Hasher zuerst. Die Betriebs-Hasher bleiben als weitere Einträge gültig, und
``epm/test_sicherheit.py`` prüft, dass die Einstellungen des Betriebs PBKDF2 behalten.

Threads der Texterkennung (15.11.2026): Tesseract (OpenMP) und onnxruntime nehmen je Prozess EPM_OCR_THREADS (Standard
2). Laufen die Tests auf allen Kernen parallel, wären die Kerne doppelt belegt – OpenMP wartet dann aktiv und einzelne
Erkennungen dauerten statt 5 s bis zu 280 s. Im parallelen Lauf daher ein Thread je Testprozess (wie im Betrieb ein
Thread je Kern); die Diktate (whisper.cpp, ein einzelner langer Test) behalten zwei. Eine gesetzte Umgebung gilt weiter.

Aufteilen auf mehrere Rechner (15.11.2026): ``EPM_TESTTEIL=2/3`` führt nur den zweiten von drei Teilen aus. Geteilt
wird nach Testklassen (sie teilen sich ``setUpTestData``), gewichtet mit den gemessenen Laufzeiten aus
``epm/testzeiten.json`` (neue Klassen: geschätzt nach Anzahl der Tests). Jede Klasse landet in genau einem Teil; alle
Teile zusammen sind der vollständige Lauf. Innerhalb eines Teils kommen die längsten Klassen zuerst, damit am Ende
nicht ein Prozess allein an einer langen Klasse rechnet.
"""
import json
import multiprocessing
import os
import unittest
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.test.runner import DiscoverRunner, ParallelTestSuite

multiprocessing.set_start_method("spawn", force=True)

SCHNELLER_HASHER = "django.contrib.auth.hashers.MD5PasswordHasher"
TESTZEITEN = Path(__file__).with_name("testzeiten.json")
SEKUNDEN_JE_UNBEKANNTEM_TEST = 0.5


def klasse_von(test) -> str:
    return f"{type(test).__module__}.{type(test).__qualname__}"


def testzeiten() -> dict[str, float]:
    try:
        return json.loads(TESTZEITEN.read_text(encoding="utf-8"))["klassen"]
    except (OSError, ValueError, KeyError):
        return {}


def teil_lesen(wert: str | None) -> tuple[int, int] | None:
    """„2/3“ → (2, 3); leer → None (alles)."""
    if not wert:
        return None
    try:
        nr, anzahl = (int(x) for x in wert.split("/"))
    except ValueError:
        raise ValueError(f"EPM_TESTTEIL={wert!r}: erwartet z. B. 2/3") from None
    if not 1 <= nr <= anzahl:
        raise ValueError(f"EPM_TESTTEIL={wert!r}: Teil muss zwischen 1 und {anzahl} liegen")
    return nr, anzahl


def aufteilen(klassen: dict[str, int], anzahl: int, zeiten: dict[str, float]) -> list[list[str]]:
    """Klassen (Name → Anzahl Tests) auf ``anzahl`` Teile, längste zuerst in den jeweils leichtesten Teil.
    Ergebnis hängt nur von Namen, Anzahl und Zeiten ab – auf jedem Rechner gleich."""
    def gewicht(name):
        return zeiten.get(name, klassen[name] * SEKUNDEN_JE_UNBEKANNTEM_TEST)

    teile: list[list[str]] = [[] for _ in range(anzahl)]
    last = [0.0] * anzahl
    for name in sorted(klassen, key=lambda n: (-gewicht(n), n)):
        i = min(range(anzahl), key=lambda j: (last[j], j))
        teile[i].append(name)
        last[i] += gewicht(name)
    return teile


def schnelle_hashes():
    """Im Hauptprozess und in jedem mit ``spawn`` gestarteten Testprozess (dort läuft nur Djangos eigenes
    ``setup_test_environment``, nicht das des Testlaufs)."""
    from django.contrib.auth.hashers import get_hashers, get_hashers_by_algorithm

    if settings.PASSWORD_HASHERS[0] != SCHNELLER_HASHER:
        settings.PASSWORD_HASHERS = [SCHNELLER_HASHER, *settings.PASSWORD_HASHERS]
        get_hashers.cache_clear()
        get_hashers_by_algorithm.cache_clear()


def _testprozess_einrichten(*_):
    schnelle_hashes()


class ParallelerTestlauf(ParallelTestSuite):
    process_setup = _testprozess_einrichten   # Django übergibt process_setup.__func__ an jeden Testprozess


class Testlauf(DiscoverRunner):
    parallel_test_suite = ParallelerTestlauf

    def test_suite(self, tests=()):
        """Von ``build_suite`` mit allen gefundenen Tests aufgerufen: nur der eigene Teil, längste Klassen zuerst."""
        tests = list(tests)
        teil = teil_lesen(os.environ.get("EPM_TESTTEIL"))
        if teil is None and self._shuffler is not None:
            return unittest.TestSuite(tests)
        je_klasse: dict[str, list] = defaultdict(list)
        for t in tests:
            je_klasse[klasse_von(t)].append(t)
        zeiten = testzeiten()
        if teil is None:
            namen = list(je_klasse)
        else:
            nr, anzahl = teil
            # Ladefehler (Syntaxfehler, fehlendes Modul) immer im ersten Teil – nie stillschweigend weglassen
            fehler = [n for n in je_klasse if isinstance(je_klasse[n][0], unittest.loader._FailedTest)]
            normal = {n: len(je_klasse[n]) for n in je_klasse if n not in fehler}
            namen = aufteilen(normal, anzahl, zeiten)[nr - 1] + (fehler if nr == 1 else [])
            geschaetzt = sum(zeiten.get(n, normal.get(n, 0) * SEKUNDEN_JE_UNBEKANNTEM_TEST) for n in namen)
            self.log(f"Testteil {nr}/{anzahl}: {len(namen)} von {len(je_klasse)} Klassen, "
                     f"{sum(len(je_klasse[n]) for n in namen)} von {len(tests)} Tests, geschätzt {geschaetzt:.0f} s")
        if self._shuffler is None:
            # Djangos Reihenfolge der Arten bleibt (Ladefehler, TestCase, SimpleTestCase), darin die längsten zuerst
            arten = (unittest.loader._FailedTest, *self.reorder_by)

            def art(n):
                return next((i for i, a in enumerate(arten) if isinstance(je_klasse[n][0], a)), len(arten))

            namen = sorted(namen, key=lambda n: (art(n), -zeiten.get(n, 0.0)))  # stabil bei Gleichstand
        return unittest.TestSuite([t for n in namen for t in je_klasse[n]])

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        schnelle_hashes()
        if self.parallel > 1:  # vor dem Start der Testprozesse – sie erben die Umgebung
            os.environ.setdefault("EPM_DIKTAT_THREADS", os.environ.get("EPM_OCR_THREADS", "2"))
            os.environ.setdefault("EPM_OCR_THREADS", "1")
