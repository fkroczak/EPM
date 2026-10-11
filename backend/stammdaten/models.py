"""Stammdaten, die der Admin selbst pflegt: Auswahllisten, Versorger, Präparate, Einstellungen."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class Auswahlwert(models.Model):
    class Liste(models.TextChoices):
        KATHETER = "katheter", "Katheter"
        DOKUMENTTYP = "dokumenttyp", "Dokumenttyp"
        KONTAKTART = "kontaktart", "Kontaktart"
        TERMINORT = "terminort", "Terminort"
        BEZIEHUNG = "beziehung", "Beziehung (Bezugsperson)"
        # Wünsche aus der Praxis vom 06.10.2026: Berichte in der Akte (F115)
        BERICHTART = "berichtart", "Berichtsart"

    liste = models.CharField(max_length=30, choices=Liste.choices)
    wert = models.CharField(max_length=100)
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Auswahlwert"
        verbose_name_plural = "Auswahlwerte"
        ordering = ["liste", "reihenfolge", "wert"]
        constraints = [models.UniqueConstraint(fields=["liste", "wert"], name="auswahlwert_eindeutig")]

    def delete(self, *args, **kwargs):
        raise PermissionError("Auswahlwerte werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return self.wert


class Versorger(models.Model):
    """Homecare-Versorger. Wird nie gelöscht, nur deaktiviert."""

    name = models.CharField(max_length=150, unique=True)
    strasse = models.CharField("Straße", max_length=150, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField(max_length=100, blank=True)
    telefon = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    notiz = models.TextField(blank=True)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Versorger"
        verbose_name_plural = "Versorger"
        ordering = ["name"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Versorger werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return self.name


class Ansprechpartner(models.Model):
    """Person beim Versorger; betreut jeweils einen Teil der Patienten."""

    versorger = models.ForeignKey(Versorger, on_delete=models.PROTECT, related_name="ansprechpartner")
    name = models.CharField(max_length=150)
    zustaendigkeit = models.CharField("Zuständigkeit", max_length=150, blank=True,
                                      help_text="z. B. „Disposition · Patienten A–K“")
    telefon = models.CharField(max_length=50, blank=True)
    mobil = models.CharField(max_length=50, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    notiz = models.TextField(blank=True)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Ansprechpartner"
        verbose_name_plural = "Ansprechpartner"
        ordering = ["versorger__name", "name"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Ansprechpartner werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return f"{self.name} ({self.versorger})"


class Arzt(models.Model):
    """Arzt bzw. Praxis (gemeinsame Liste, Festlegung 01.10.2026). Wird einmal gepflegt und beim Patienten
    mit Rolle zugeordnet (Hausarzt, Facharzt …); eine geänderte Telefonnummer gilt so für alle Patienten.
    Wird nie gelöscht, nur deaktiviert."""

    name = models.CharField("Name", max_length=150, help_text="z. B. „Dr. med. Anna Hausmann“")
    praxis = models.CharField("Praxis / Klinik", max_length=150, blank=True)
    fachrichtung = models.CharField(max_length=100, blank=True, help_text="z. B. Allgemeinmedizin, Gastroenterologie")
    strasse = models.CharField("Straße", max_length=150, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField(max_length=100, blank=True)
    telefon = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    notiz = models.TextField(blank=True)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Arzt"
        verbose_name_plural = "Ärzte"
        ordering = ["name", "ort"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Ärzte werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return f"{self.name} ({self.ort})" if self.ort else self.name


class Praeparat(models.Model):
    class Kategorie(models.TextChoices):
        BASISLOESUNG = "basisloesung", "Basislösung"
        GLUCOSE = "glucose", "Glucose"
        AMINOSAEUREN = "aminosaeuren", "Aminosäuren"
        LIPIDE = "lipide", "Lipide"
        ALBUMIN = "albumin", "Albumin"
        ELEKTROLYTE = "elektrolyte", "Elektrolyte"
        VITAMINE = "vitamine", "Vitamine"
        SPURENELEMENTE = "spurenelemente", "Spurenelemente"
        KATHETERSCHUTZ = "katheterschutz", "Katheterschutz"
        MEDIKAMENT = "medikament", "Medikament"
        SONSTIGES = "sonstiges", "Sonstiges"

    kategorie = models.CharField(max_length=30, choices=Kategorie.choices)
    name = models.CharField(max_length=150)
    konzentration = models.CharField(max_length=60, blank=True, help_text="z. B. 50 %, 10 %, 20 %")
    einheit = models.CharField(max_length=10, default="ml", help_text="Standard-Einheit der Menge")
    # Kurzer Hinweis zum Präparat (Wunsch 06.10.2026, F111): erscheint bei der Auswahl und auf der Plan-PDF,
    # z. B. „baugleich zu Cernevit, günstiger (Regressgefahr)“ oder „reines Taurolidin 2 %“.
    hinweis = models.CharField(max_length=200, blank=True, help_text="z. B. „reines Taurolidin 2 %“")
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    aktiv = models.BooleanField(default=True, help_text="Ausgeblendete Präparate erscheinen nicht bei neuen Plänen")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Präparat"
        verbose_name_plural = "Präparate"
        ordering = ["kategorie", "reihenfolge", "name", "konzentration"]
        constraints = [
            models.UniqueConstraint(fields=["kategorie", "name", "konzentration"], name="praeparat_eindeutig")
        ]

    def delete(self, *args, **kwargs):
        raise PermissionError("Präparate werden nicht gelöscht, nur deaktiviert.")

    def __str__(self):
        return f"{self.name} {self.konzentration}".strip()


class Laborparameter(models.Model):
    """Katalog der Laborwerte (Wunsch 06.10.2026, F112): Gruppe, Name, Einheit, Referenzbereich.

    Die Erfassungsmaske eines Laborbefunds zeigt die aktiven Parameter nach Gruppen; eingetragen wird nur der
    gemessene Wert, die Einheit steht schon da und bleibt je Wert überschreibbar. Gepflegt unter
    Vorlagen › Laborparameter (Recht „Vorlagen pflegen“). Wird nie gelöscht, nur deaktiviert – sonst verlören
    bereits erfasste Befunde ihren Bezug."""

    class Gruppe(models.TextChoices):
        TRANSAMINASEN = "transaminasen", "Transaminasen"
        NIERE = "niere", "Nierenwerte"
        EISEN = "eisen", "Eisenhaushalt"
        EIWEISS_FETT = "eiweiss_fett", "Eiweiß- und Fettstoffwechsel"
        ELEKTROLYTE = "elektrolyte", "Elektrolyte"
        SPURENELEMENTE = "spurenelemente", "Spurenelemente"
        HAEMATOLOGIE = "haematologie", "Hämatologie"
        VITAMINE = "vitamine", "Vitamine"
        KNOCHEN = "knochen", "Knochenstoffwechsel"
        PANKREAS = "pankreas", "Pankreasenzyme"
        DIABETES = "diabetes", "Blutzucker / Diabetes"
        SCHILDDRUESE = "schilddruese", "Schilddrüse"
        TUMORMARKER = "tumormarker", "Tumormarker"
        GENETIK = "genetik", "Genetische Parameter"
        SONSTIGES = "sonstiges", "Weitere Parameter"

    gruppe = models.CharField(max_length=30, choices=Gruppe.choices)
    name = models.CharField(max_length=150)
    kurzname = models.CharField(max_length=60, blank=True, help_text="für enge Spalten, z. B. „GPT“")
    # Scans (F166): weitere Schreibweisen, unter denen Labore den Wert drucken („ALAT“, „Krea“) – kommagetrennt.
    # Die üblichen Schreibweisen kennt die Werterkennung schon (scans/ocr/auswertung.py, SYNONYME).
    suchbegriffe = models.CharField("Suchbegriffe für Scans", max_length=300, blank=True,
                                    help_text="weitere Schreibweisen auf Laborbefunden, durch Komma getrennt")
    einheit = models.CharField(max_length=30, blank=True, help_text="z. B. mg/dl, µg/l, U/l")
    # Referenzbereich: in der Mail nicht gewünscht, aber jedes Labor liefert ihn mit (U44). Bleibt leer, bis
    # Alice entschieden hat; erst dann markiert die Oberfläche abweichende Werte.
    referenz_von = models.DecimalField("Referenz von", max_digits=12, decimal_places=4, null=True, blank=True)
    referenz_bis = models.DecimalField("Referenz bis", max_digits=12, decimal_places=4, null=True, blank=True)
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    aktiv = models.BooleanField(default=True, help_text="Ausgeblendete Parameter erscheinen nicht in neuen Befunden")

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Laborparameter"
        verbose_name_plural = "Laborparameter"
        ordering = ["gruppe", "reihenfolge", "name"]
        constraints = [
            models.UniqueConstraint(fields=["gruppe", "name"], name="laborparameter_eindeutig"),
            models.CheckConstraint(
                name="laborparameter_referenz_reihenfolge",
                condition=models.Q(referenz_von__isnull=True) | models.Q(referenz_bis__isnull=True)
                | models.Q(referenz_von__lte=models.F("referenz_bis")),
            ),
        ]

    def delete(self, *args, **kwargs):
        raise PermissionError("Laborparameter werden nicht gelöscht, nur deaktiviert.")

    def clean(self):
        if (self.referenz_von is not None and self.referenz_bis is not None
                and self.referenz_von > self.referenz_bis):
            raise ValidationError({"referenz_bis": "„Referenz bis“ muss größer oder gleich „Referenz von“ sein."})

    def __str__(self):
        return f"{self.name} ({self.einheit})" if self.einheit else self.name


ICD_MUSTER = r"^[A-Z]\d{2}(\.\d{1,2})?[+*!]?$"


class Diagnosevorlage(models.Model):
    """Die Liste, die im Hintergrund mitläuft (Wunsch 06.10.2026, F117): Diagnose mit ICD-Code.

    Beim Eintragen einer Diagnose in der Akte wird daraus vorgeschlagen; eine neue Kombination aus Code und
    Bezeichnung wandert in den Katalog, damit die Liste von allein mitwächst (U53). Korrigiert und
    ausgeblendet wird sie unter Vorlagen › Diagnosen. Das Zusatzkennzeichen (G/V/Z/A) gehört zur einzelnen
    Diagnose in der Akte, nicht hierher – dieselbe Diagnose kann bei einem Patienten gesichert und bei einem
    anderen ein Verdacht sein."""

    icd_code = models.CharField("ICD-Code", max_length=10, db_index=True, help_text="z. B. K91.2")
    bezeichnung = models.CharField(max_length=200)
    aktiv = models.BooleanField(default=True)
    angelegt_am = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Diagnose (Liste)"
        verbose_name_plural = "Diagnosen (Liste)"
        ordering = ["bezeichnung", "icd_code"]
        constraints = [models.UniqueConstraint(fields=["icd_code", "bezeichnung"], name="diagnosevorlage_eindeutig")]

    def delete(self, *args, **kwargs):
        raise PermissionError("Diagnosen der Liste werden nicht gelöscht, nur deaktiviert.")

    def clean(self):
        import re

        self.icd_code = (self.icd_code or "").strip().upper()
        if not re.match(ICD_MUSTER, self.icd_code):
            raise ValidationError({"icd_code": "ICD-Code wie „K91.2“ angeben (Buchstabe, zwei Ziffern, "
                                               "bei Bedarf Punkt und ein bis zwei Stellen)."})
        if not (self.bezeichnung or "").strip():
            raise ValidationError({"bezeichnung": "Bitte die Bezeichnung angeben."})

    def __str__(self):
        return f"{self.bezeichnung} [{self.icd_code}]"


# Erklärungen, die bei jeder Akte in Betreuung vorliegen sollen (Schlüssel wie ``patienten.Erklaerung.Art``).
# Fehlt eine davon, steht die Akte unter „Nach und nach prüfen“ (Festlegung 02.10.2026).
ERKLAERUNGSARTEN = ["datenschutzinformation", "einwilligung", "schweigepflichtentbindung"]


def pflicht_erklaerungen_standard():
    return list(ERKLAERUNGSARTEN)


def kontaktstufen_fehler(bald, ueberfaellig) -> dict | None:
    """Kontakt fällig in zwei Stufen (S04): beide mindestens 1 Monat, „bald fällig“ vor „überfällig“."""
    if bald is None or bald < 1:
        return {"kontakt_bald_monate": "Bitte mindestens 1 Monat angeben."}
    if ueberfaellig is None or ueberfaellig <= bald:
        return {"kontakt_ueberfaellig_monate": "„Überfällig“ muss später liegen als „bald fällig“."}
    return None


def scans_fehler(frist, hoechst, verlaengerung, max_mb, max_anzahl) -> dict:
    """Regeln für die Aufbewahrung der Scans (F165): Frist 1–365 Tage, Höchstdauer nicht kürzer als die Frist,
    Verlängerung 1 Tag bis Höchstdauer, Obergrenzen in vernünftigen Grenzen."""
    fehler = {}
    if frist is not None and not 1 <= frist <= 365:
        fehler["scans_frist_tage"] = "Bitte 1 bis 365 Tage angeben."
    if hoechst is not None and not 1 <= hoechst <= 365:
        fehler["scans_hoechst_tage"] = "Bitte 1 bis 365 Tage angeben."
    elif frist is not None and hoechst is not None and hoechst < frist:
        fehler["scans_hoechst_tage"] = "Die Höchstdauer darf nicht kürzer sein als die Aufbewahrung."
    if verlaengerung is not None and (verlaengerung < 1 or (hoechst is not None and verlaengerung > hoechst)):
        fehler["scans_verlaengerung_tage"] = "Bitte mindestens 1 Tag und höchstens die Höchstdauer angeben."
    if max_mb is not None and not 100 <= max_mb <= 500_000:
        fehler["scans_max_mb"] = "Bitte 100 bis 500 000 MB angeben."
    if max_anzahl is not None and not 10 <= max_anzahl <= 10_000:
        fehler["scans_max_anzahl"] = "Bitte 10 bis 10 000 angeben."
    return fehler


def vorgabe_fehler(werte: dict) -> dict:
    """Mengen je kg der Praxisvorgabe: nicht negativ und unter einer großzügigen Obergrenze (Tippfehler abfangen)."""
    fehler = {}
    for feld, wert in werte.items():
        if wert is None:
            fehler[feld] = "Bitte einen Wert angeben (0 = nicht vorbelegen)."
            continue
        oben = Einstellungen.VORGABE_JE_KG[feld][1]
        if not Decimal(0) <= Decimal(wert) <= oben:
            fehler[feld] = f"Bitte 0 bis {str(oben).replace('.', ',')} je kg angeben."
    return fehler


class Firma(models.Model):
    """Firma, die EPM nutzt (Anforderung 11.10.2026): Deutsche Stiftung Krankheitsbedingte Mangelernährung (DSKM) und
    Regeneration Clinic (RG). Patienten gehören einer oder beiden Firmen (``patienten.PatientFirma``), Mitarbeiter haben
    je Firma eine Rolle (``accounts.Mitgliedschaft``). Oben links in der Seitenleiste wird zwischen den Firmen
    umgeschaltet; Liste, Startseite, Kalender, Statistiken zeigen dann nur die Patienten dieser Firma.

    Je Firma: Logo, Briefkopf (``absender``) und Dokumentvorlagen. Gemeinsam: Versorger, Ärzte, Präparate,
    Laborparameter, Auswahllisten und Grenzwerte."""

    DSKM = "dskm"
    RG = "rg"

    kuerzel = models.SlugField("Kürzel", max_length=10, unique=True)
    name = models.CharField("Name", max_length=200)
    kurzname = models.CharField("Kurzname", max_length=40, help_text="im Umschalter, z. B. „DSKM“")
    # Briefkopf: DSKM nutzt den in den Einstellungen gewählten Absender (Stiftung bzw. gUG), RG einen eigenen
    absender = models.CharField("Briefkopf", max_length=10, blank=True,
                                help_text="leer = Absender aus den Einstellungen (Stiftung bzw. gUG)")
    # Altdaten-Import (MS-Access-Dump) gilt nur für diese Firma (Anforderung 11.10.2026: nur DSKM)
    altdaten = models.BooleanField("Altdaten-Import", default=False)
    reihenfolge = models.PositiveSmallIntegerField(default=0)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Firma"
        verbose_name_plural = "Firmen"
        ordering = ["reihenfolge", "id"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Firmen werden nicht gelöscht.")

    def __str__(self):
        return self.kurzname

    @classmethod
    def dskm(cls):
        return cls.objects.get(kuerzel=cls.DSKM)


class Einstellungen(models.Model):
    """Genau ein Datensatz (pk=1): Absender, Warnschwellen, Plausibilitätsgrenzen, Fristen des Datenschutzes."""

    class Absender(models.TextChoices):
        STIFTUNG = "stiftung", "Stiftung"
        GUG = "gug", "gUG"
        # Briefkopf der Regeneration Clinic (Anforderung 11.10.2026, ``Firma.absender``)
        RG = "rg", "Regeneration Clinic"

    absender = models.CharField("Absender", max_length=10, choices=Absender.choices, default=Absender.STIFTUNG)

    # Warnungen
    gewicht_warnung_prozent = models.DecimalField("Warnung Gewichtsverlust", max_digits=4, decimal_places=1,
                                                  default=Decimal("5.0"))
    gewicht_warnung_monate = models.PositiveSmallIntegerField("Zeitraum Gewichtsverlust", default=3)
    plan_alter_warnung_monate = models.PositiveSmallIntegerField("Infusionsplan gilt als alt nach", default=12)
    # Befunde gelten nach einem Jahr als alt (Festlegung 07.10.2026, F120); je Art einstellbar
    labor_alter_warnung_monate = models.PositiveSmallIntegerField("Laborbefund gilt als alt nach", default=12)
    bia_alter_warnung_monate = models.PositiveSmallIntegerField("BIA-Messung gilt als alt nach", default=12)
    # Wiedereinbestellung in zwei Stufen (Festlegung 01.10.2026, S04): „bald fällig“ ab 4 Monaten (quartalsweise
    # Kontakte + 1 Monat), „überfällig“ ab 6 Monaten – beide einstellbar, „bald“ muss früher liegen als „überfällig“
    kontakt_bald_monate = models.PositiveSmallIntegerField("Kontakt bald fällig", default=4)
    kontakt_ueberfaellig_monate = models.PositiveSmallIntegerField("Kontakt überfällig", default=6)
    # Wiedervorlage beim Erfassen eines Kontakts (Wunsch 08.10.2026): standardmäßig in 14 Tagen, einstellbar;
    # im Dialog lässt sich das Datum je Kontakt weiterhin frei ändern
    wiedervorlage_tage = models.PositiveSmallIntegerField("Wiedervorlage nach", default=14)
    # Infoblatt an die Praxis (F177): Die Startseite erinnert ab „Vorlauf“ Tagen vor dem nächsten Zeitraum (nächste
    # Woche Mo–So oder nächster Monat), bis für diesen Zeitraum ein Infoblatt erstellt ist
    infoblatt_rhythmus = models.CharField("Infoblatt an die Praxis", max_length=10, default="woche",
                                          choices=[("woche", "wöchentlich"), ("monat", "monatlich"),
                                                   ("aus", "keine Erinnerung")])
    infoblatt_vorlauf_tage = models.PositiveSmallIntegerField("Erinnerung an das Infoblatt (Tage vorher)", default=3)
    # Automatisierungen für die Pflege (10.10.2026): „Kein Gewicht seit … Monaten“ (F186) und das Angebot
    # „Terminbestätigung schicken?“ nach dem Speichern eines Praxistermins (F185)
    gewicht_fehlt_monate = models.PositiveSmallIntegerField("Gewicht fehlt, wenn keine Messung seit", default=3)
    terminbestaetigung_anbieten = models.BooleanField("Terminbestätigung nach dem Speichern anbieten", default=True)

    # Plausibilitätsgrenzen (Eingaben außerhalb werden abgelehnt)
    gewicht_min_kg = models.DecimalField("Gewicht minimal", max_digits=5, decimal_places=1, default=Decimal("20.0"))
    gewicht_max_kg = models.DecimalField("Gewicht maximal", max_digits=5, decimal_places=1, default=Decimal("250.0"))
    groesse_min_cm = models.DecimalField("Größe minimal", max_digits=5, decimal_places=1, default=Decimal("100.0"))
    groesse_max_cm = models.DecimalField("Größe maximal", max_digits=5, decimal_places=1, default=Decimal("230.0"))
    kcal_max_tag = models.PositiveIntegerField("Energie maximal", default=5000)
    # Grenzen je Planwert (Entwurf 18 · Vorlagen › Grenzwerte). Die Standardwerte sind bewusst weit
    # gefasst und werden von der Administration festgelegt.
    kcal_min_tag = models.PositiveIntegerField("Energie minimal", default=0)
    glucose_min_g = models.DecimalField("Glucose minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    glucose_max_g = models.DecimalField("Glucose maximal", max_digits=6, decimal_places=1, default=Decimal("1000"))
    aminosaeuren_min_g = models.DecimalField("Aminosäuren minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    aminosaeuren_max_g = models.DecimalField("Aminosäuren maximal", max_digits=6, decimal_places=1, default=Decimal("300"))
    lipide_min_g = models.DecimalField("Lipide minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    lipide_max_g = models.DecimalField("Lipide maximal", max_digits=6, decimal_places=1, default=Decimal("200"))
    natrium_min_mmol = models.DecimalField("Natrium minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    natrium_max_mmol = models.DecimalField("Natrium maximal", max_digits=6, decimal_places=1, default=Decimal("500"))
    kalium_min_mmol = models.DecimalField("Kalium minimal", max_digits=6, decimal_places=1, default=Decimal("0"))
    kalium_max_mmol = models.DecimalField("Kalium maximal", max_digits=6, decimal_places=1, default=Decimal("300"))
    # Gesamtvolumen = Gewicht × 35 ml (Festlegung 01.10.2026); Standard deckt 20–250 kg ab
    volumen_min_ml = models.DecimalField("Gesamtvolumen minimal", max_digits=7, decimal_places=0, default=Decimal("0"))
    volumen_max_ml = models.DecimalField("Gesamtvolumen maximal", max_digits=7, decimal_places=0, default=Decimal("9000"))
    # „Mengen nach Praxisvorgabe“ im Plan-Editor (Entscheidung der Praxis 10.10.2026, F190): Mengen je kg des letzten
    # Gewichts, Startwerte wie im Altsystem (EPM_infuplan.php). Unter Vorlagen › Grenzwerte einstellbar.
    vorgabe_glucose_g_kg = models.DecimalField("Glucose je kg", max_digits=5, decimal_places=2, default=Decimal("3.5"))
    vorgabe_aminosaeuren_g_kg = models.DecimalField("Aminosäuren je kg", max_digits=5, decimal_places=2, default=Decimal("1.2"))
    vorgabe_lipide_g_kg = models.DecimalField("Lipide je kg", max_digits=5, decimal_places=2, default=Decimal("1"))
    vorgabe_natrium_mmol_kg = models.DecimalField("Natrium je kg", max_digits=5, decimal_places=2, default=Decimal("1.3"))
    vorgabe_kalium_mmol_kg = models.DecimalField("Kalium je kg", max_digits=5, decimal_places=2, default=Decimal("0.7"))
    vorgabe_phosphat_mmol_kg = models.DecimalField("Phosphat je kg", max_digits=5, decimal_places=2, default=Decimal("0.3"))
    vorgabe_calcium_mmol_kg = models.DecimalField("Calcium je kg", max_digits=5, decimal_places=2, default=Decimal("0.15"))
    vorgabe_magnesium_mmol_kg = models.DecimalField("Magnesium je kg", max_digits=5, decimal_places=2, default=Decimal("0.2"))
    # Gewicht vor der Freigabe eines Plans „bitte prüfen“, wenn älter (Entscheidung der Praxis 10.10.2026: 6 Monate)
    plan_gewicht_alter_monate = models.PositiveSmallIntegerField("Gewicht für den Plan gilt als alt nach", default=6)
    vorgabe_geaendert_am = models.DateTimeField("Praxisvorgabe je kg zuletzt geändert", null=True, blank=True, editable=False)

    # Datenschutz (Festlegung 02.10.2026)
    aufbewahrung_jahre = models.PositiveSmallIntegerField("Aufbewahrung nach Abschluss der Akte", default=10)
    abschluss_pruefen_monate = models.PositiveSmallIntegerField("Abschluss prüfen, wenn kein Kontakt seit", default=24)
    protokoll_aufbewahrung_jahre = models.PositiveSmallIntegerField(
        "Audit-Log aufbewahren", default=0, help_text="0 = unbegrenzt; sonst werden ältere Einträge täglich entfernt")
    pflicht_erklaerungen = models.JSONField("Erklärungen, die vorliegen sollen", default=pflicht_erklaerungen_standard,
                                            blank=True)
    # Vordrucke ohne Wasserzeichen „ENTWURF“, obwohl die mitgelieferte Startvorlage noch aktiv ist (Festlegung 03.10.2026:
    # Entwurfsmodus manuell abschaltbar, Vorlagen › Dokumentvorlagen). Liste der Arten; nur über eigenen Endpunkt.
    vordrucke_ohne_entwurf = models.JSONField("Vordrucke ohne Wasserzeichen „ENTWURF“", default=list, blank=True)
    # Scans und Texterkennung (Festlegung 08.10.2026, F165): Aufbewahrung nicht zugeordneter Scans, Verlängern je
    # Scan bis zur Höchstdauer (ab dem Hochladen), Obergrenzen für Speicher und Anzahl; Fachwörter für die Erkennung
    scans_frist_tage = models.PositiveSmallIntegerField("Scans aufbewahren (Tage)", default=7)
    scans_hoechst_tage = models.PositiveSmallIntegerField("Scans höchstens aufbewahren (Tage)", default=30)
    scans_verlaengerung_tage = models.PositiveSmallIntegerField("Scans verlängern um (Tage)", default=7)
    scans_max_mb = models.PositiveIntegerField("Speicher für Scans (MB)", default=2000)
    scans_max_anzahl = models.PositiveIntegerField("Scans höchstens (Anzahl)", default=300)
    ocr_fachwoerter = models.TextField("Fachwörter für die Texterkennung", blank=True,
                                       help_text="je Zeile ein Wort, z. B. Präparate und Diagnosen")
    # Musterdaten (Testbenutzer, Testpatienten ab Nr. 9001) bei jedem Update/Start anlegen? Nach „Datenbank leeren“
    # aus (Festlegung 03.10.2026); unter Administration › System umschaltbar.
    musterdaten_automatisch = models.BooleanField("Musterdaten automatisch anlegen", default=True)
    # Menüpunkt „Import“ nach der Übernahme ausblenden, wieder einblendbar (Festlegung 03.10.2026, U32)
    import_ausgeblendet = models.BooleanField("Import ausgeblendet", default=False)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Einstellungen"
        verbose_name_plural = "Einstellungen"

    GRENZPAARE = [
        ("gewicht_min_kg", "gewicht_max_kg"), ("groesse_min_cm", "groesse_max_cm"), ("kcal_min_tag", "kcal_max_tag"),
        ("glucose_min_g", "glucose_max_g"), ("aminosaeuren_min_g", "aminosaeuren_max_g"),
        ("lipide_min_g", "lipide_max_g"), ("natrium_min_mmol", "natrium_max_mmol"),
        ("kalium_min_mmol", "kalium_max_mmol"), ("volumen_min_ml", "volumen_max_ml"),
    ]

    # Feld der Praxisvorgabe je kg → Feld im Plan, Obergrenze je kg (Plausibilität, keine medizinische Vorgabe)
    VORGABE_JE_KG = {
        "vorgabe_glucose_g_kg": ("glucose_g", Decimal("10")), "vorgabe_aminosaeuren_g_kg": ("aminosaeuren_g", Decimal("5")),
        "vorgabe_lipide_g_kg": ("lipide_g", Decimal("5")), "vorgabe_natrium_mmol_kg": ("natrium_mmol", Decimal("10")),
        "vorgabe_kalium_mmol_kg": ("kalium_mmol", Decimal("10")), "vorgabe_phosphat_mmol_kg": ("phosphat_mmol", Decimal("5")),
        "vorgabe_calcium_mmol_kg": ("calcium_mmol", Decimal("5")), "vorgabe_magnesium_mmol_kg": ("magnesium_mmol", Decimal("5")),
    }

    def save(self, *args, **kwargs):
        self.pk = 1
        fehler = vorgabe_fehler({f: getattr(self, f) for f in self.VORGABE_JE_KG})
        if fehler:
            raise ValidationError(fehler)
        bisher = Einstellungen.objects.filter(pk=1).values(*self.VORGABE_JE_KG).first()
        if bisher and any(Decimal(bisher[f]) != Decimal(getattr(self, f)) for f in self.VORGABE_JE_KG):
            self.vorgabe_geaendert_am = timezone.now()
        for unten, oben in self.GRENZPAARE:
            if getattr(self, unten) >= getattr(self, oben):
                raise ValidationError({unten: "Untere Grenze muss kleiner als obere Grenze sein."})
        if not 1 <= self.aufbewahrung_jahre <= 100:
            raise ValidationError({"aufbewahrung_jahre": "Bitte 1 bis 100 Jahre angeben."})
        if self.abschluss_pruefen_monate < 1:
            raise ValidationError({"abschluss_pruefen_monate": "Bitte mindestens 1 Monat angeben."})
        for feld in ("plan_alter_warnung_monate", "labor_alter_warnung_monate", "bia_alter_warnung_monate",
                     "gewicht_fehlt_monate", "plan_gewicht_alter_monate"):
            if getattr(self, feld) < 1:
                raise ValidationError({feld: "Bitte mindestens 1 Monat angeben."})
        fehler = kontaktstufen_fehler(self.kontakt_bald_monate, self.kontakt_ueberfaellig_monate)
        if fehler:
            raise ValidationError(fehler)
        fehler = scans_fehler(self.scans_frist_tage, self.scans_hoechst_tage, self.scans_verlaengerung_tage,
                              self.scans_max_mb, self.scans_max_anzahl)
        if fehler:
            raise ValidationError(fehler)
        if (not isinstance(self.pflicht_erklaerungen, list)
                or any(a not in ERKLAERUNGSARTEN for a in self.pflicht_erklaerungen)
                or len(set(self.pflicht_erklaerungen)) != len(self.pflicht_erklaerungen)):
            raise ValidationError({"pflicht_erklaerungen": "Unbekannte Erklärung."})
        if not isinstance(self.vordrucke_ohne_entwurf, list) or any(a not in ERKLAERUNGSARTEN
                                                                    for a in self.vordrucke_ohne_entwurf):
            raise ValidationError({"vordrucke_ohne_entwurf": "Unbekannter Vordruck."})
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Einstellungen können nicht gelöscht werden.")

    @classmethod
    def aktuell(cls) -> "Einstellungen":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Einstellungen"


class Absenderangaben(models.Model):
    """Briefkopf je Absender (Entwurf 18 · Briefkopf und Logo). Welcher gilt, steht in Einstellungen.absender."""

    art = models.CharField(max_length=10, choices=Einstellungen.Absender.choices, unique=True)
    name = models.CharField("Name", max_length=200, blank=True)
    strasse = models.CharField("Straße", max_length=150, blank=True)
    plz = models.CharField("PLZ", max_length=10, blank=True)
    ort = models.CharField("Ort", max_length=100, blank=True)
    telefon = models.CharField("Telefon", max_length=50, blank=True)
    fax = models.CharField("Fax", max_length=50, blank=True)
    email = models.CharField("E-Mail", max_length=150, blank=True)
    internet = models.CharField("Internet", max_length=150, blank=True)
    fusszeile = models.CharField("Fußzeile", max_length=300, blank=True)

    history = HistoricalRecords()

    # Vorbelegung wie im Entwurf; die Administration pflegt die Angaben danach selbst
    VORBELEGUNG = {
        Einstellungen.Absender.STIFTUNG: {
            "name": "Deutsche Stiftung Krankheitsbedingte Mangelernährung", "strasse": "Waltrup 16",
            "plz": "48341", "ort": "Altenberge", "telefon": "0251 98 11 400", "fax": "0251 98 11 4019",
            "email": "kontakt@dsgme.org", "internet": "www.dsgme.org",
            "fusszeile": "rechtsfähige gemeinnützige und mildtätige Stiftung",
        },
        Einstellungen.Absender.GUG: {},
        Einstellungen.Absender.RG: {"name": "Regeneration Clinic"},
    }

    class Meta:
        verbose_name = "Absenderangaben"
        verbose_name_plural = "Absenderangaben"
        ordering = ["art"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Absenderangaben werden nicht gelöscht.")

    def __str__(self):
        return f"{self.get_art_display()}: {self.name}"

    @classmethod
    def aktuelle(cls, firma=None):
        """Briefkopf der Firma (ohne Angabe: der aktiven, 11.10.2026): RG eigener, DSKM wie in den Einstellungen."""
        from epm.firma import aktive_firma

        firma = firma or aktive_firma()
        art = (firma.absender if firma is not None and firma.absender else None) or Einstellungen.aktuell().absender
        return cls.alle()[art]

    @classmethod
    def alle(cls) -> dict:
        ergebnis = {}
        for art in Einstellungen.Absender.values:
            obj, _ = cls.objects.get_or_create(art=art, defaults=cls.VORBELEGUNG.get(art, {}))
            ergebnis[art] = obj
        return ergebnis


class Logo(models.Model):
    """Hochgeladenes Logo für Briefkopf und Seitenleiste. Das neueste gilt; ältere bleiben erhalten."""

    datei = models.CharField(max_length=255, unique=True, editable=False)
    mime = models.CharField(max_length=40, editable=False)
    sha256 = models.CharField(max_length=64, editable=False)
    breite = models.PositiveIntegerField(null=True, blank=True, editable=False)
    hoehe = models.PositiveIntegerField(null=True, blank=True, editable=False)
    hochgeladen_am = models.DateTimeField(auto_now_add=True)
    hochgeladen_von = models.ForeignKey("accounts.User", on_delete=models.PROTECT, null=True, related_name="+")
    # je Firma ein Logo (Anforderung 11.10.2026); leer = Logo der DSKM aus der Zeit vor den Firmen
    firma = models.ForeignKey(Firma, on_delete=models.PROTECT, null=True, blank=True, related_name="logos")

    class Meta:
        verbose_name = "Logo"
        verbose_name_plural = "Logos"
        ordering = ["-hochgeladen_am", "-id"]

    def delete(self, *args, **kwargs):
        raise PermissionError("Logos werden nicht gelöscht.")

    @classmethod
    def aktuell(cls, firma=None):
        """Neuestes Logo der Firma (ohne Angabe: der gerade aktiven); für die DSKM zählen auch Logos ohne Firma."""
        from epm.firma import aktive_firma

        firma = firma or aktive_firma()
        if firma is None:
            return cls.objects.first()
        qs = cls.objects.filter(firma=firma)
        if firma.kuerzel == Firma.DSKM:
            qs = cls.objects.filter(models.Q(firma=firma) | models.Q(firma__isnull=True))
        return qs.first()
