"""KI (Experimentell) – Festlegung 14.10.2026, Plan: docs/KI-ERWEITERUNG-PLAN-2026-10-14.md.

Der KI-Dienst (Container ``ki-worker``, ``manage.py epm_ki``) liest die Dokumente der Akten **nur lesend**, erkennt
Text (vorhandene Texterkennung + lokales Vision-Modell Qwen3.5), bestimmt den Dokumenttyp und strukturiert Metadaten,
Laborwerte, Infusionspläne und Freitext. Alles landet hier – getrennt von der Akte – in der Prüf-Queue.

Getrennte Ebenen (Auftrag 8): **Original** (``patienten.Dokument``, wird nie verändert) · **KI-Rohdaten**
(``KiRohergebnis``, unveränderlich) · **Vorschlag und Korrektur** (``KiFeld`` mit ``KiKorrektur``, versioniert) ·
**übernommene Akteninhalte** (bestehende Tabellen der Akte, Nachweis in ``KiUebernahme``).

In die Akte schreibt ausschließlich ein angemeldeter Mitarbeiter mit Recht (``ki/uebernahme.py``); der KI-Dienst hat
dafür nicht einmal die Datenbankrechte (Rolle ``epm_ki``, ``ki/dbrolle.py``).
"""
import datetime as dt
import os

from django.conf import settings
from django.db import models
from django.utils import timezone


def _env_int(name, standard):
    try:
        return int(os.environ.get(name, standard))
    except ValueError:
        return standard


def _env_zeit(name, standard):
    try:
        return dt.time.fromisoformat(os.environ.get(name, standard))
    except ValueError:
        return dt.time.fromisoformat(standard)


class Unveraenderlich(models.Model):
    """Nur anfügen: Rohdaten, Korrekturen und Übernahmen bleiben, wie sie entstanden sind."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise PermissionError(f"{self._meta.verbose_name} ist unveränderlich.")
        super().save(*args, **kwargs)


class Dokumenttyp(models.TextChoices):
    LABOR = "labor", "Laborbefund"
    ARZTBERICHT = "arztbericht", "Arztbericht"
    ENTLASSBERICHT = "entlassbericht", "Entlassbericht"
    VERLAUF = "verlauf", "Verlaufsdokumentation"
    INFUSIONSPLAN = "infusionsplan", "Infusionsplan"
    MEDIKATIONSPLAN = "medikationsplan", "Medikationsplan"
    PFLEGEBERICHT = "pflegebericht", "Pflegebericht"
    SONSTIGES = "sonstiges", "Sonstiges"


def diktat_nacht_env() -> tuple[int, int]:
    """Nachtfenster der Diktate aus ``EPM_DIKTAT_NACHT`` („21-7“) – Startwert der Einstellung und Rückfall."""
    try:
        ab, bis = (int(x) for x in os.environ.get("EPM_DIKTAT_NACHT", "21-7").split("-"))
    except ValueError:
        return 21, 7
    return (ab, bis) if 0 <= ab <= 23 and 0 <= bis <= 23 else (21, 7)


class KiEinstellung(models.Model):
    """Einstellungen des KI-Dienstes (Administration › KI). Vorgaben kommen aus Umgebungsvariablen (``KI_*``), die
    Oberfläche überschreibt sie; ``KI_WORKER_MAX`` bleibt eine harte Obergrenze für die Zahl paralleler Aufträge."""

    aktiv = models.BooleanField(default=True, help_text="Hauptschalter: aus = der KI-Dienst nimmt nichts Neues an")
    nacht_beginn = models.TimeField(default=dt.time(21, 0))
    nacht_ende = models.TimeField(default=dt.time(7, 0))
    zeitzone = models.CharField(max_length=50, default="Europe/Berlin")
    worker_nacht = models.PositiveSmallIntegerField(default=1, help_text="parallele Aufträge im Nachtfenster")
    worker_tag = models.PositiveSmallIntegerField(
        default=0, help_text="parallele Aufträge tagsüber; 0 = nur ausdrücklich angeforderte (dann einer)")
    max_cpu_prozent = models.PositiveSmallIntegerField(default=80)
    min_ram_frei_mb = models.PositiveIntegerField(default=1536)
    max_last_je_kern = models.FloatField(default=1.5)
    pause_bei_sicherung = models.BooleanField(default=True)
    altbestand_lesen = models.BooleanField(default=True, help_text="vorhandene Dokumente der Akten nach und nach lesen")
    max_seiten = models.PositiveSmallIntegerField(default=30, help_text="Seiten je Dokument (große PDFs)")
    bild_max_px = models.PositiveSmallIntegerField(default=1600, help_text="längste Bildseite für das Vision-Modell")
    ocr_schwelle = models.FloatField(default=0.85, help_text="darunter liest das Vision-Modell die Seite selbst")
    feld_unsicher = models.FloatField(default=0.7, help_text="Felder darunter gelten als unsicher")
    verknuepfung_stunden = models.PositiveSmallIntegerField(default=48)
    beispiele_max = models.PositiveSmallIntegerField(
        default=12, help_text="frühere Korrekturen als Beispiele im Prompt (ki/beispiele.py); 0 = aus")
    aufbewahrung_tage = models.PositiveSmallIntegerField(default=14, help_text="Zwischendateien danach löschen")
    # Priorisierung (14.11.2026, Administration › KI › Priorisierung): höher = früher. „Angefordert“ heißt
    # ``prioritaet >= prio_angefordert`` – deshalb liegen alle anderen Stufen darunter (Prüfung in der API); so nimmt
    # der Tagesbetrieb mit ``worker_tag = 0`` weiterhin nur ausdrücklich angeforderte Dokumente
    prio_angefordert = models.PositiveSmallIntegerField(default=10,
                                                        help_text="„jetzt verarbeiten“, „Erneut verarbeiten“")
    prio_termin = models.PositiveSmallIntegerField(default=8, help_text="Akte mit Praxistermin in den nächsten Tagen")
    termin_tage = models.PositiveSmallIntegerField(default=3, help_text="Vorlauf für den Termin-Vorrang; 0 = aus")
    prio_neu = models.PositiveSmallIntegerField(default=5, help_text="neu hochgeladene Dokumente")
    neu_tage = models.PositiveSmallIntegerField(default=7, help_text="so lange gilt ein Dokument als neu")
    prio_neu_lesen = models.PositiveSmallIntegerField(default=3,
                                                      help_text="„Neu lesen“ (Nachtaufgabe, Administration)")
    prio_altbestand = models.PositiveSmallIntegerField(default=0)
    chat_vorrang = models.BooleanField(
        default=True, help_text="tagsüber hält ein wartender Chat alle anderen Aufträge an")
    zusammenfassung_tagsueber = models.BooleanField(
        default=True, help_text="„Akte auf einen Blick“ auf Anforderung auch tagsüber erstellen")
    zusammenfassung_ohne_termin_tage = models.PositiveSmallIntegerField(
        default=90, help_text="Zeitraum der Zusammenfassung ohne früheren Termin und ohne Kontakt")
    # bisher nur Umgebungsvariablen (EPM_DIKTAT_NACHT, EPM_KI_CHAT_TAGE) – die bleiben Startwert bzw. Rückfall, solange
    # es keine Einstellungszeile gibt
    diktat_nacht_beginn = models.PositiveSmallIntegerField(default=21, help_text="Diktate „heute Nacht“ ab (Stunde)")
    diktat_nacht_ende = models.PositiveSmallIntegerField(default=7, help_text="… bis (Stunde)")
    chat_tage = models.PositiveSmallIntegerField(default=30, help_text="KI-Chats ohne Änderung danach löschen")
    # Training (optional, Entscheidung 14.10.2026): nur nachts/am Wochenende, nur ohne angemeldete Benutzer und erst,
    # wenn die Rechtsgrundlagen-Prüfung dokumentiert ist
    training_erlaubt = models.BooleanField(default=False)
    training_nur_wochenende = models.BooleanField(default=True)
    rechtsgrundlage = models.TextField(blank=True)
    rechtsgrundlage_geprueft_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                                     blank=True, related_name="+")
    rechtsgrundlage_geprueft_am = models.DateTimeField(null=True, blank=True)
    geaendert_am = models.DateTimeField(auto_now=True)
    geaendert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")

    class Meta:
        verbose_name = "KI-Einstellung"
        verbose_name_plural = "KI-Einstellungen"

    def __str__(self):
        return "KI-Einstellungen"

    @classmethod
    def laden(cls) -> "KiEinstellung":
        obj = cls.objects.filter(pk=1).first()
        if obj is None:
            obj = cls(pk=1, nacht_beginn=_env_zeit("KI_NACHT_BEGINN", "21:00"),
                      nacht_ende=_env_zeit("KI_NACHT_ENDE", "07:00"),
                      zeitzone=os.environ.get("KI_ZEITZONE", "Europe/Berlin"),
                      worker_nacht=_env_int("KI_WORKER_NACHT", 1), worker_tag=_env_int("KI_WORKER_TAG", 0),
                      max_cpu_prozent=_env_int("KI_MAX_CPU_PROZENT", 80),
                      min_ram_frei_mb=_env_int("KI_MIN_RAM_FREI_MB", 1536),
                      chat_tage=max(1, _env_int("EPM_KI_CHAT_TAGE", 30)))
            obj.diktat_nacht_beginn, obj.diktat_nacht_ende = diktat_nacht_env()
            obj.save()
        return obj

    @staticmethod
    def worker_max() -> int:
        return max(1, _env_int("KI_WORKER_MAX", 4))


class KiModellversion(models.Model):
    """Modell-Registry: Produktivmodelle werden nie überschrieben. Neue Version → Evaluation → Freigabe durch einen
    Admin (Passwort + zweiter Faktor) → aktiv; die bisherige bleibt als „vorherig“ für das Zurückschalten."""

    class Rolle(models.TextChoices):
        VISION = "vision", "Vision/OCR und Text"
        TEXT = "text", "nur Text"
        EMBEDDING = "embedding", "Suche (Embedding)"

    class Status(models.TextChoices):
        EINGESPIELT = "eingespielt", "eingespielt"
        EVALUATION = "evaluation", "in Evaluation"
        AKTIV = "aktiv", "aktiv"
        VORHERIG = "vorherig", "vorherige Version"
        GESPERRT = "gesperrt", "gesperrt"

    name = models.CharField(max_length=150, help_text="z. B. „Qwen3.5-4B Q4_K_M“")
    rolle = models.CharField(max_length=10, choices=Rolle.choices, default=Rolle.VISION)
    datei = models.CharField(max_length=255, help_text="GGUF-Datei im Modellordner")
    projektor = models.CharField(max_length=255, blank=True, help_text="Vision-Projektor (mmproj)")
    sha256 = models.CharField(max_length=64)
    groesse = models.PositiveBigIntegerField(default=0)
    quantisierung = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.EINGESPIELT)
    evaluation = models.JSONField(default=dict, blank=True)
    notiz = models.TextField(blank=True)
    eingespielt_am = models.DateTimeField(auto_now_add=True)
    aktiviert_am = models.DateTimeField(null=True, blank=True)
    aktiviert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")

    class Meta:
        verbose_name = "KI-Modellversion"
        verbose_name_plural = "KI-Modellversionen"
        ordering = ["-eingespielt_am", "-id"]
        constraints = [models.UniqueConstraint(fields=["rolle"], condition=models.Q(status="aktiv"),
                                               name="ki_ein_aktives_modell_je_rolle")]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @classmethod
    def aktiv(cls, rolle: str = "vision") -> "KiModellversion | None":
        return cls.objects.filter(rolle=rolle, status=cls.Status.AKTIV).first()


class KiVorgang(models.Model):
    """Ein Dokument der Akte in der KI-Verarbeitung (Statuswerte aus dem Auftrag, Abschnitt 5)."""

    class Status(models.TextChoices):
        NEU = "neu", "Neu"
        IN_VERARBEITUNG = "in_verarbeitung", "In Verarbeitung"
        OCR_FERTIG = "ocr_fertig", "OCR abgeschlossen"
        ANALYSE_FERTIG = "analyse_fertig", "Analyse abgeschlossen"
        ZUR_PRUEFUNG = "zur_pruefung", "Zur Prüfung vorgelegt"
        TEILWEISE = "teilweise", "Teilweise freigegeben"
        UEBERNOMMEN = "uebernommen", "Freigegeben und übernommen"
        ABGELEHNT = "abgelehnt", "Abgelehnt"
        FEHLER = "fehler", "Fehler"
        NACHVERARBEITUNG = "nachverarbeitung", "Zur Nachverarbeitung markiert"

    WARTEND = (Status.NEU, Status.NACHVERARBEITUNG)
    IN_ARBEIT = (Status.IN_VERARBEITUNG, Status.OCR_FERTIG, Status.ANALYSE_FERTIG)
    PRUEFBAR = (Status.ZUR_PRUEFUNG, Status.TEILWEISE)

    # Geht das Dokument (Art. 17 DSGVO, endgültig gelöscht), gehen die KI-Daten mit
    dokument = models.ForeignKey("patienten.Dokument", on_delete=models.CASCADE, related_name="ki_vorgaenge")
    patient = models.ForeignKey("patienten.Patient", on_delete=models.CASCADE, related_name="ki_vorgaenge")
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    sha256 = models.CharField(max_length=64, help_text="Prüfsumme des Dokuments zum Zeitpunkt der Verarbeitung")
    ist_test = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEU, db_index=True)
    prioritaet = models.SmallIntegerField(default=0, help_text="höher = früher; angefordert = 10")
    angefordert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="+")
    angefordert_am = models.DateTimeField(null=True, blank=True)
    schritt = models.CharField(max_length=120, blank=True)
    fortschritt = models.PositiveSmallIntegerField(default=0)
    versuche = models.PositiveSmallIntegerField(default=0)
    fehler = models.TextField(blank=True)
    begonnen_am = models.DateTimeField(null=True, blank=True)
    lebenszeichen = models.DateTimeField(null=True, blank=True)
    fertig_am = models.DateTimeField(null=True, blank=True)
    dauer_s = models.FloatField(null=True, blank=True)

    # Ergebnis auf Dokumentebene (Vorschläge; maßgeblich sind die Felder)
    dokumenttyp = models.CharField(max_length=20, choices=Dokumenttyp.choices, blank=True)
    typ_konfidenz = models.FloatField(null=True, blank=True)
    metadaten = models.JSONField(default=dict, blank=True)
    seiten = models.PositiveSmallIntegerField(default=0)
    ocr_text = models.TextField(blank=True)
    ocr_konfidenz = models.FloatField(null=True, blank=True)
    zusammenfassung = models.TextField(blank=True)
    verfahren = models.JSONField(default=list, blank=True)
    modellversion = models.ForeignKey(KiModellversion, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    prompt_version = models.CharField(max_length=20, blank=True)

    erstellt_am = models.DateTimeField(auto_now_add=True, db_index=True)
    geprueft_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    geprueft_am = models.DateTimeField(null=True, blank=True)
    ablehnungsgrund = models.TextField(blank=True)

    class Meta:
        verbose_name = "KI-Vorgang"
        verbose_name_plural = "KI-Vorgänge"
        ordering = ["-erstellt_am", "-id"]
        constraints = [models.UniqueConstraint(fields=["dokument", "sha256"], name="ki_vorgang_je_fassung")]
        indexes = [models.Index(fields=["status", "prioritaet"], name="ki_vorgang_queue"),
                   models.Index(fields=["patient", "status"], name="ki_vorgang_patient")]

    def __str__(self):
        return f"KI-Vorgang Nr. {self.pk}"


class KiSeite(models.Model):
    """Erkennung einer Seite: Text der klassischen Erkennung (Stufe 1) und – wenn sie unsicher war – des
    Vision-Modells (Stufe 2)."""

    vorgang = models.ForeignKey(KiVorgang, on_delete=models.CASCADE, related_name="seiten_liste")
    nr = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True)
    konfidenz = models.FloatField(null=True, blank=True)
    verfahren = models.JSONField(default=list, blank=True)
    vision_text = models.TextField(blank=True)
    vision_fertig = models.BooleanField(default=False, help_text="Stufe 2 erledigt (auch: nicht nötig)")
    # Ergebnis der klassischen Erkennung (Reihen mit Wörtern, wie in „Scans“) für die regelbasierte Gegenprüfung
    ergebnis = models.JSONField(default=dict, blank=True)
    breite = models.PositiveIntegerField(default=0)
    hoehe = models.PositiveIntegerField(default=0)
    dauer_s = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "KI-Seite"
        verbose_name_plural = "KI-Seiten"
        ordering = ["vorgang", "nr"]
        constraints = [models.UniqueConstraint(fields=["vorgang", "nr"], name="ki_seite_einmal")]


class KiRohergebnis(Unveraenderlich):
    """Antwort des Modells, wie sie kam (nur anfügen) – mit Modell, Version und Prompt-Fassung (Audit, Auftrag 8)."""

    vorgang = models.ForeignKey(KiVorgang, on_delete=models.CASCADE, null=True, blank=True, related_name="roh")
    art = models.CharField(max_length=20)  # transkription | extraktion | bericht | evaluation
    seite = models.PositiveSmallIntegerField(null=True, blank=True)
    modellversion = models.ForeignKey(KiModellversion, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    modell = models.CharField(max_length=150, blank=True)
    prompt_version = models.CharField(max_length=20, blank=True)
    parameter = models.JSONField(default=dict, blank=True)
    antwort = models.TextField(blank=True)
    dauer_s = models.FloatField(null=True, blank=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "KI-Rohergebnis"
        verbose_name_plural = "KI-Rohergebnisse"
        ordering = ["erstellt_am", "id"]


class KiFeld(models.Model):
    """Ein erkannter Wert zur Prüfung: Metadatum, Laborwert, Position eines Infusionsplans, Medikament, Diagnose
    oder Textabschnitt. ``wert`` ist der Vorschlag der KI (bleibt erhalten), ``korrigiert`` die Fassung des
    Mitarbeiters; jede Änderung steht zusätzlich versioniert in ``KiKorrektur``."""

    class Gruppe(models.TextChoices):
        META = "meta", "Metadaten"
        LABOR = "labor", "Laborwert"
        INFUSION = "infusion", "Infusionsplan"
        MEDIKATION = "medikation", "Medikation"
        DIAGNOSE = "diagnose", "Diagnose"
        TEXT = "text", "Text"

    class Status(models.TextChoices):
        OFFEN = "offen", "offen"
        FREIGEGEBEN = "freigegeben", "freigegeben"
        VERWORFEN = "verworfen", "verworfen"
        UEBERNOMMEN = "uebernommen", "übernommen"

    class Entscheidung(models.TextChoices):
        KEINE = "", "—"
        NEU = "neu", "Neu anlegen"
        ERGAENZEN = "ergaenzen", "Bestehenden Eintrag ergänzen"
        ERSETZEN = "ersetzen", "Bestehenden Eintrag ersetzen"
        VERWERFEN = "verwerfen", "Verwerfen"

    vorgang = models.ForeignKey(KiVorgang, on_delete=models.CASCADE, related_name="felder")
    gruppe = models.CharField(max_length=12, choices=Gruppe.choices)
    schluessel = models.CharField(max_length=40, help_text="z. B. dokumentdatum, laborwert, position, abschnitt")
    nr = models.PositiveSmallIntegerField(default=0)
    wert = models.JSONField(default=dict)
    korrigiert = models.JSONField(null=True, blank=True)
    konfidenz = models.FloatField(null=True, blank=True)
    quelle = models.CharField(max_length=20, blank=True, help_text="vision | regeln | vision+regeln | ocr")
    belege = models.JSONField(default=dict, blank=True, help_text="Seite, Zeile, Hinweise der Prüfung")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OFFEN)
    entscheidung = models.CharField(max_length=10, choices=Entscheidung.choices, blank=True, default="")
    ziel = models.JSONField(default=dict, blank=True, help_text="nach der Übernahme: Modell und ID des Akteneintrags")
    geaendert_am = models.DateTimeField(auto_now=True)
    geaendert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")

    class Meta:
        verbose_name = "KI-Feld"
        verbose_name_plural = "KI-Felder"
        ordering = ["vorgang", "gruppe", "nr", "id"]

    def __str__(self):
        return f"{self.get_gruppe_display()} {self.schluessel} ({self.vorgang_id})"

    @property
    def endwert(self) -> dict:
        return self.korrigiert if self.korrigiert is not None else self.wert


class KiKorrektur(Unveraenderlich):
    """Versionierte Korrektur eines Felds (Grundlage für Qualitäts-Dashboard und Evaluationsdaten)."""

    class Fehlerart(models.TextChoices):
        LESEFEHLER = "lesefehler", "Zeichen falsch gelesen (OCR)"
        ZUORDNUNG = "zuordnung", "falscher Parameter / falsche Zuordnung"
        EINHEIT = "einheit", "Einheit falsch"
        DATUM = "datum", "Datum/Uhrzeit falsch"
        TYP = "typ", "Dokumenttyp falsch"
        FEHLT = "fehlt", "Wert fehlte"
        UEBERFLUESSIG = "ueberfluessig", "kein Wert (gehört nicht dazu)"
        SONSTIGES = "sonstiges", "sonstiges"

    feld = models.ForeignKey(KiFeld, on_delete=models.CASCADE, related_name="korrekturen")
    version = models.PositiveSmallIntegerField()
    alt = models.JSONField(null=True, blank=True)
    neu = models.JSONField(null=True, blank=True)
    fehlerart = models.CharField(max_length=15, choices=Fehlerart.choices, default=Fehlerart.SONSTIGES)
    kommentar = models.CharField(max_length=300, blank=True)
    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    zeitpunkt = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "KI-Korrektur"
        verbose_name_plural = "KI-Korrekturen"
        ordering = ["feld", "version"]
        constraints = [models.UniqueConstraint(fields=["feld", "version"], name="ki_korrektur_version")]


class KiUebernahme(Unveraenderlich):
    """Nachweis einer Übernahme in die Akte: wer, wann, welche Felder, mit welchen Entscheidungen, wohin."""

    vorgang = models.ForeignKey(KiVorgang, on_delete=models.CASCADE, related_name="uebernahmen")
    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    zeitpunkt = models.DateTimeField(auto_now_add=True)
    felder = models.JSONField(default=list)
    ziele = models.JSONField(default=list, help_text="[{modell, id, aktion}]")
    entscheidungen = models.JSONField(default=dict)

    class Meta:
        verbose_name = "KI-Übernahme"
        verbose_name_plural = "KI-Übernahmen"
        ordering = ["-zeitpunkt", "-id"]


class KiHinweis(models.Model):
    """Historischer Zusammenhang zwischen Laborwert und Infusionsplan – ausschließlich eine Entscheidungshilfe,
    keine medizinische Bewertung (Auftrag 4). Entsteht regelbasiert (``ki/verknuepfung.py``)."""

    class Art(models.TextChoices):
        SUBSTITUTION = "substitution", "auffälliger Wert, anschließend Maßnahme dokumentiert"
        NORMALISIERT = "normalisiert", "Wert nach Maßnahme im Referenzbereich"
        WEITERHIN = "weiterhin", "Wert nach Maßnahme weiterhin auffällig"
        KEINE_MASSNAHME = "keine_massnahme", "auffälliger Wert ohne nachfolgende Maßnahme im Zeitraum"

    class Stufe(models.TextChoices):
        GESICHERT = "gesichert", "gesicherter Zusammenhang"
        WAHRSCHEINLICH = "wahrscheinlich", "wahrscheinlicher Zusammenhang"

    class Status(models.TextChoices):
        NEU = "neu", "neu"
        GESEHEN = "gesehen", "gesehen"
        AUSGEBLENDET = "ausgeblendet", "ausgeblendet"

    patient = models.ForeignKey("patienten.Patient", on_delete=models.CASCADE, related_name="ki_hinweise")
    art = models.CharField(max_length=20, choices=Art.choices)
    stufe = models.CharField(max_length=15, choices=Stufe.choices)
    parameter = models.CharField(max_length=60)
    text = models.CharField(max_length=500)
    zeitpunkt = models.DateTimeField(help_text="Zeitpunkt des auslösenden Laborwerts (ohne Uhrzeit: 00:00)")
    belege = models.JSONField(default=dict)
    schluessel = models.CharField(max_length=200, help_text="verhindert doppelte Hinweise")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NEU)
    erstellt_am = models.DateTimeField(auto_now_add=True)
    aktualisiert_am = models.DateTimeField(auto_now=True)
    geaendert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")

    class Meta:
        verbose_name = "KI-Hinweis"
        verbose_name_plural = "KI-Hinweise"
        ordering = ["-zeitpunkt", "-id"]
        constraints = [models.UniqueConstraint(fields=["patient", "schluessel"], name="ki_hinweis_einmal")]


class KiBerichtsauftrag(models.Model):
    """Berichtsentwurf – nur auf ausdrückliche Anforderung (Auftrag 6), nur aus freigegebenen Akteninhalten."""

    class Art(models.TextChoices):
        LABOR = "labor", "Laborzusammenfassung"
        INFUSION = "infusion", "Medikations-/Infusionsübersicht"
        VERLAUF = "verlauf", "Verlaufsbericht"

    class Status(models.TextChoices):
        WARTET = "wartet", "wartet"
        LAEUFT = "laeuft", "wird erstellt"
        FERTIG = "fertig", "Entwurf fertig"
        FEHLER = "fehler", "Fehler"
        GESPEICHERT = "gespeichert", "als Bericht-Entwurf gespeichert"
        VERWORFEN = "verworfen", "verworfen"

    patient = models.ForeignKey("patienten.Patient", on_delete=models.CASCADE, related_name="ki_berichte")
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    art = models.CharField(max_length=10, choices=Art.choices)
    von = models.DateField(null=True, blank=True)
    bis = models.DateField(null=True, blank=True)
    dokumenttypen = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WARTET, db_index=True)
    angefordert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    angefordert_am = models.DateTimeField(auto_now_add=True)
    lebenszeichen = models.DateTimeField(null=True, blank=True)
    fakten = models.JSONField(default=list, blank=True, help_text="Grundlage mit Quellen [{nr, text, quelle}]")
    entwurf = models.TextField(blank=True)
    pruefung = models.JSONField(default=dict, blank=True, help_text="Markierungen der Gegenprüfung")
    fehler = models.TextField(blank=True)
    modellversion = models.ForeignKey(KiModellversion, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    fertig_am = models.DateTimeField(null=True, blank=True)
    bericht = models.ForeignKey("berichte.Bericht", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")

    class Meta:
        verbose_name = "KI-Berichtsentwurf"
        verbose_name_plural = "KI-Berichtsentwürfe"
        ordering = ["-angefordert_am", "-id"]


class KiEvaluationsfall(models.Model):
    """Pseudonymisiertes Beispiel aus einer Korrektur: Erwartung (vom Mitarbeiter bestätigt) zum Vergleich von
    Modellversionen. Für Training nur nach ausdrücklicher Freigabe (``training_freigegeben``)."""

    # pseudonymisiert ist nicht anonym: wird das Dokument endgültig gelöscht (Art. 17 DSGVO), geht der Fall mit
    vorgang = models.ForeignKey(KiVorgang, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    dokumenttyp = models.CharField(max_length=20, choices=Dokumenttyp.choices, blank=True)
    eingabe_text = models.TextField(help_text="pseudonymisierter OCR-Text")
    erwartet = models.JSONField(default=dict, help_text="bestätigte Felder, pseudonymisiert")
    pseudonymisiert_am = models.DateTimeField(default=timezone.now)
    training_freigegeben = models.BooleanField(default=False)
    freigegeben_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="+")
    freigegeben_am = models.DateTimeField(null=True, blank=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "KI-Evaluationsfall"
        verbose_name_plural = "KI-Evaluationsfälle"
        ordering = ["-erstellt_am", "-id"]


class KiEvaluationslauf(models.Model):
    modellversion = models.ForeignKey(KiModellversion, on_delete=models.CASCADE, related_name="laeufe")
    gestartet_am = models.DateTimeField(auto_now_add=True)
    fertig_am = models.DateTimeField(null=True, blank=True)
    faelle = models.PositiveIntegerField(default=0)
    ergebnis = models.JSONField(default=dict, blank=True)
    fehler = models.TextField(blank=True)

    class Meta:
        verbose_name = "KI-Evaluationslauf"
        verbose_name_plural = "KI-Evaluationsläufe"
        ordering = ["-gestartet_am", "-id"]


class KiPromptvorlage(models.Model):
    """Vorgefertigte Anweisung für den KI-Chat (Administration › Vorlagen › KI-Prompts, Recht „Vorlagen pflegen“).

    Die Anweisung kommt **hinter** den festen Rahmen aus ``ki/chat.py`` (nichts erfinden, keine Diagnose …): eine
    Vorlage kann die Aufgabe genauer beschreiben, den Rahmen aber nicht aufheben. Feste Anweisung + niedrige
    Temperatur = gleichbleibende Ergebnisse."""

    name = models.CharField(max_length=100, unique=True)
    beschreibung = models.CharField(max_length=300, blank=True, help_text="Wofür? – steht im Chat unter der Auswahl")
    anweisung = models.TextField(help_text="Aufgabe an die KI (Systemanweisung, Teil 2)")
    temperatur = models.DecimalField(max_digits=3, decimal_places=2, default=0.1,
                                     help_text="0 = immer gleich formuliert, 1 = freier")
    aktiv = models.BooleanField(default=True)
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    mitgeliefert = models.BooleanField(default=False)
    geaendert_am = models.DateTimeField(auto_now=True)
    geaendert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="+")

    class Meta:
        verbose_name = "KI-Promptvorlage"
        verbose_name_plural = "KI-Promptvorlagen"
        ordering = ["reihenfolge", "name"]

    def __str__(self):
        return self.name


class KiChat(models.Model):
    """Unterhaltung mit der KI – **nur für die Person sichtbar, die sie begonnen hat** (auch nicht für Admins)."""

    benutzer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ki_chats")
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    titel = models.CharField(max_length=200, blank=True)
    vorlage = models.ForeignKey(KiPromptvorlage, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    aktualisiert_am = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = "KI-Chat"
        verbose_name_plural = "KI-Chats"
        ordering = ["-aktualisiert_am", "-id"]


class KiChatNachricht(models.Model):
    class Rolle(models.TextChoices):
        NUTZER = "nutzer", "Sie"
        KI = "ki", "KI"

    class Status(models.TextChoices):
        WARTET = "wartet", "wartet auf den KI-Dienst"
        LAEUFT = "laeuft", "wird geschrieben"
        FERTIG = "fertig", "fertig"
        FEHLER = "fehler", "Fehler"

    chat = models.ForeignKey(KiChat, on_delete=models.CASCADE, related_name="nachrichten")
    rolle = models.CharField(max_length=6, choices=Rolle.choices)
    text = models.TextField(blank=True)
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.FERTIG, db_index=True)
    vorlage_name = models.CharField(max_length=100, blank=True)
    anweisung = models.TextField(blank=True, help_text="Anweisung der Vorlage zum Zeitpunkt der Anfrage")
    temperatur = models.DecimalField(max_digits=3, decimal_places=2, default=0.1)
    pruefung = models.JSONField(default=dict, blank=True, help_text="Markierungen der Gegenprüfung")
    fehler = models.TextField(blank=True)
    modell = models.CharField(max_length=200, blank=True)
    dauer_s = models.FloatField(null=True, blank=True)
    versuche = models.PositiveSmallIntegerField(default=0)
    erstellt_am = models.DateTimeField(auto_now_add=True)
    lebenszeichen = models.DateTimeField(null=True, blank=True)
    fertig_am = models.DateTimeField(null=True, blank=True)
    schritt = models.CharField(max_length=160, blank=True, help_text="was der KI-Dienst gerade tut (Dokument lesen …)")

    class Meta:
        verbose_name = "KI-Chatnachricht"
        verbose_name_plural = "KI-Chatnachrichten"
        ordering = ["erstellt_am", "id"]


class KiChatAnhang(models.Model):
    """Dokument zu einer Chatnachricht (12.11.2026): hochgeladen oder aus einer Akte gewählt, ohne Seitengrenze.

    Der KI-Dienst erkennt den Text und legt ihn in ``text`` ab; eine hochgeladene Datei (``datei``) wird danach
    gelöscht. Der Anhang geht mit dem Chat (Aufbewahrung wie der Chat), mit dem Dokument der Akte (Löschung nach
    Art. 17 DSGVO) und mit der Akte."""

    class Herkunft(models.TextChoices):
        UPLOAD = "upload", "Hochgeladen"
        AKTE = "akte", "Aus der Akte"

    class Status(models.TextChoices):
        WARTET = "wartet", "Text wird erkannt"
        FERTIG = "fertig", "fertig"
        FEHLER = "fehler", "Fehler"

    nachricht = models.ForeignKey(KiChatNachricht, on_delete=models.CASCADE, related_name="anhaenge")
    herkunft = models.CharField(max_length=6, choices=Herkunft.choices)
    dokument = models.ForeignKey("patienten.Dokument", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    patient = models.ForeignKey("patienten.Patient", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    name = models.CharField(max_length=255)
    mime = models.CharField(max_length=100, blank=True)
    groesse = models.PositiveBigIntegerField(default=0)
    datei = models.BinaryField(null=True, blank=True, help_text="hochgeladene Datei, bis der Text erkannt ist")
    seiten = models.PositiveIntegerField(default=0)
    seiten_fertig = models.PositiveIntegerField(default=0)
    text = models.TextField(blank=True)
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.WARTET)
    fehler = models.TextField(blank=True)
    erstellt_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "KI-Chat-Anhang"
        verbose_name_plural = "KI-Chat-Anhänge"
        ordering = ["id"]


def _alle_wochentage():
    return list(range(7))


class KiAufgabe(models.Model):
    """Nachtaufgabe (Zeitplan, 14.11.2026, Administration › KI › Nachtaufgaben). Eine Aufgabe **reiht nur Arbeit
    ein** – abgearbeitet wird nach Modus, Grenzen und Nachtfenster wie alles andere (``ki/aufgaben.py``)."""

    class Art(models.TextChoices):
        ZUSAMMENFASSUNG_TERMINE = "zusammenfassung_termine", "Akte auf einen Blick für die nächsten Termine"
        NEU_LESEN = "neu_lesen", "Dokumente mit dem aktiven Modell neu lesen"
        DOKUMENTE_VORMERKEN = "dokumente_vormerken", "Dokumente in die Queue legen"

    name = models.CharField(max_length=100)
    art = models.CharField(max_length=30, choices=Art.choices)
    aktiv = models.BooleanField(default=True)
    wochentage = models.JSONField(default=_alle_wochentage, help_text="0 = Montag … 6 = Sonntag")
    uhrzeit = models.TimeField(default=dt.time(3, 0), help_text="Ortszeit (Zeitzone der KI-Einstellungen)")
    parameter = models.JSONField(default=dict, blank=True)
    letzter_lauf = models.DateTimeField(null=True, blank=True)
    letztes_ergebnis = models.CharField(max_length=500, blank=True)
    jetzt_angefordert = models.BooleanField(default=False, help_text="läuft beim nächsten Durchlauf des KI-Dienstes")
    geaendert_am = models.DateTimeField(auto_now=True)
    geaendert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")

    class Meta:
        verbose_name = "KI-Nachtaufgabe"
        verbose_name_plural = "KI-Nachtaufgaben"
        ordering = ["uhrzeit", "id"]

    def __str__(self):
        return f"KI-Aufgabe {self.pk}"


class KiZusammenfassung(models.Model):
    """„Akte auf einen Blick“ (14.11.2026): was seit dem letzten Praxistermin in der Akte passiert ist – Fakten aus der
    Akte (Code), formuliert vom lokalen Modell, gegengeprüft wie der Berichtsentwurf (``ki/zusammenfassung.py``).
    Nur Anzeige in der Übersicht der Akte, nie selbst Teil der Akte; geht mit dem Patienten (CASCADE)."""

    class Grund(models.TextChoices):
        TERMIN = "termin", "nachts für einen Termin vorbereitet"
        ANGEFORDERT = "angefordert", "auf Anforderung"

    class Status(models.TextChoices):
        WARTET = "wartet", "wartet"
        LAEUFT = "laeuft", "wird erstellt"
        FERTIG = "fertig", "fertig"
        FEHLER = "fehler", "Fehler"

    class VonGrund(models.TextChoices):
        TERMIN = "termin", "seit dem letzten Termin"
        KONTAKT = "kontakt", "seit dem letzten Kontakt"
        STANDARD = "standard", "fester Zeitraum (ohne Termin und Kontakt)"

    OFFEN = (Status.WARTET, Status.LAEUFT)

    patient = models.ForeignKey("patienten.Patient", on_delete=models.CASCADE, related_name="ki_zusammenfassungen")
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    grund = models.CharField(max_length=12, choices=Grund.choices)
    termin = models.ForeignKey("patienten.Termin", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    von = models.DateField(null=True, blank=True)
    bis = models.DateField(null=True, blank=True)
    von_grund = models.CharField(max_length=10, choices=VonGrund.choices, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.WARTET, db_index=True)
    fakten = models.JSONField(default=list, blank=True, help_text="[{nr, text, quelle, datum, link}]")
    entwurf = models.TextField(blank=True)
    pruefung = models.JSONField(default=dict, blank=True, help_text="Markierungen der Gegenprüfung")
    fehler = models.TextField(blank=True)
    modellversion = models.ForeignKey(KiModellversion, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    prompt_version = models.CharField(max_length=20, blank=True)
    angefordert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="+")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    fertig_am = models.DateTimeField(null=True, blank=True)
    lebenszeichen = models.DateTimeField(null=True, blank=True)
    dauer_s = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "KI-Zusammenfassung (Akte auf einen Blick)"
        verbose_name_plural = "KI-Zusammenfassungen (Akte auf einen Blick)"
        ordering = ["-erstellt_am", "-id"]
        indexes = [models.Index(fields=["patient", "status"], name="ki_zusammenfassung_patient")]

    def __str__(self):
        return f"Akte auf einen Blick {self.pk}"
