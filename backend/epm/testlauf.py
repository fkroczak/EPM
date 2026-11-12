"""Testlauf für ``manage.py test --parallel``.

Viele Testmodule legen ihre Arbeitsordner beim Import an (``tempfile.mkdtemp`` auf Modulebene). Mit dem Linux-Standard
``fork`` teilten sich alle Testprozesse dieselben Ordner und störten sich gegenseitig (12.11.2026). Mit ``spawn``
importiert jeder Prozess die Module neu und bekommt eigene Ordner.
"""
import multiprocessing

from django.test.runner import DiscoverRunner

multiprocessing.set_start_method("spawn", force=True)


class Testlauf(DiscoverRunner):
    pass
