"""Behandlungsfälle und Dokumentenautomation der Regeneration Clinic (Anforderungsspezifikation vom 26.10.2026).

Grundprinzip: Ein Behandlungsfall ist die eine Datenquelle für alle Dokumente des Falls – Patientenerklärungen und
Aufklärungen (Vorlagen 01–12 der RGC), Zusatzbögen, OP-Bericht, Entlassungsbrief, Konsiliarbericht und Rechnung.
Welche Dokumente ein Fall braucht, bestimmt der Kostenträgertyp (Paketregel, ``Kostentraegertyp.paket``).

Lebenslauf eines Dokuments (``FallDokument``): **Entwurf** (noch keine PDF) → **erzeugt** (mindestens eine PDF) →
**final** (unterschrieben bzw. signiert). Solange es nicht final ist, bleibt der Inhalt änderbar: geändert werden die
Falldaten bzw. die Leistungspositionen der Rechnung, danach wird die PDF neu erzeugt. Jede Erzeugung ist eine neue,
unveränderliche ``DokumentVersion`` (PDF als Dokument der Akte, Prüfsumme, Datenstand) – die vorherige bleibt erhalten.
Erst mit elektronischer Signatur, hochgeladenem Scan der Papierunterschrift oder ausdrücklicher Finalisierung wird die
Fassung unveränderlich (Modell und Datenbank-Trigger, ``audit.schutz``). Eine finale Rechnung wird nur noch storniert
(Stornorechnung) und neu erzeugt.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from simple_history.models import HistoricalRecords

from patienten.models import AktenEintrag, Patient


class Sprache(models.TextChoices):
    DE = "de", "Deutsch"
    LV = "lv", "Lettisch"
    EN = "en", "Englisch"


class Fachbereich(models.TextChoices):
    KEINER = "", "—"
    ORTHOPAEDIE = "orthopaedie", "Orthopädie / Traumatologie"
    HNO = "hno", "HNO"
    ADIPOSITAS = "adipositas", "Adipositas und Stoffwechselerkrankungen"
    SONSTIGE = "sonstige", "anderer Fachbereich"


def runde(betrag) -> Decimal:
    return Decimal(betrag).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ====================================================================== Stammdaten (separat pflegbar)
class Kostentraegertyp(models.Model):
    """Art des Kostenträgers mit Paketregel: welche Dokumente ein Fall dieses Typs automatisch bekommt.

    ``paket``: Liste von Dokumentarten – ``op_bericht``, ``entlassbrief``, ``konsil``, ``rechnung`` oder der Schlüssel
    einer Vorlage der RGC (z. B. ``eigen-rgc-f02`` für die Patientenerklärung GKV). Der Zusatzbogen zur Aufklärung
    (Vorlage 07) kommt je Fachbereich des Falls dazu, wenn die Aufklärung im Paket ist."""

    kuerzel = models.SlugField("Kürzel", max_length=20, unique=True)
    name = models.CharField(max_length=120, unique=True)
    land = models.CharField("Land / Region", max_length=60, blank=True, help_text="z. B. Deutschland, Österreich, international")
    beschreibung = models.CharField(max_length=300, blank=True)
    paket = models.JSONField("Dokumentenpaket", default=list, blank=True)
    reihenfolge = models.PositiveSmallIntegerField(default=0)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Kostenträgertyp"
        verbose_name_plural = "Kostenträgertypen"
        ordering = ["reihenfolge", "name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        raise PermissionError("Kostenträgertypen werden nicht gelöscht, nur ausgeblendet.")

    def clean(self):
        from .pakete import pruefe_paket

        fehler = pruefe_paket(self.paket)
        if fehler:
            raise ValidationError({"paket": fehler})


class Kooperationspartner(models.Model):
    """Kooperationspartner eines Falls (z. B. Eibach, ARS, WC4, AIWA) – frei erweiterbar."""

    name = models.CharField(max_length=150, unique=True)
    kurzname = models.CharField(max_length=40, blank=True)
    anschrift = models.TextField(blank=True)
    kontakt = models.CharField(max_length=200, blank=True, help_text="Ansprechpartner, Telefon, E-Mail")
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Kooperationspartner"
        verbose_name_plural = "Kooperationspartner"
        ordering = ["name"]

    def __str__(self):
        return self.kurzname or self.name

    def delete(self, *args, **kwargs):
        raise PermissionError("Kooperationspartner werden nicht gelöscht, nur ausgeblendet.")


class Unterzeichner(models.Model):
    """Unterschriftsberechtigte Person (Dr. Markus Gottwald, Prof. Dr. Markus Masin – erweiterbar).

    Für die fortgeschrittene elektronische Signatur hinterlegt die Person ein eigenes Zertifikat (PKCS#12). Das Kennwort
    der Datei speichert EPM nicht: Es wird bei jeder Signatur eingegeben – so bleibt der Schlüssel unter der alleinigen
    Kontrolle der Person. Signieren darf nur das verknüpfte Benutzerkonto."""

    name = models.CharField("Name mit Titel", max_length=150, unique=True)
    funktion = models.CharField(max_length=150, blank=True, help_text="z. B. Chefarzt, Director")
    benutzer = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                    related_name="unterzeichner", verbose_name="Benutzerkonto")
    zertifikat = models.BinaryField("Zertifikat (PKCS#12)", null=True, blank=True, editable=False)
    zertifikat_info = models.CharField(max_length=300, blank=True, editable=False)
    zertifikat_bis = models.DateTimeField(null=True, blank=True, editable=False)
    reihenfolge = models.PositiveSmallIntegerField(default=0)
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords(excluded_fields=["zertifikat"])

    class Meta:
        verbose_name = "Unterschriftsberechtigte Person"
        verbose_name_plural = "Unterschriftsberechtigte"
        ordering = ["reihenfolge", "name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        raise PermissionError("Unterschriftsberechtigte werden nicht gelöscht, nur ausgeblendet.")

    @property
    def hat_zertifikat(self) -> bool:
        return bool(self.zertifikat)


class Leistung(models.Model):
    """Internationaler Leistungskatalog mit Preisen – Grundlage für Anlage K und Rechnung. Separat pflegbar; eine
    Preisänderung wirkt nur auf neue Positionen (die Position übernimmt Text und Preis beim Anlegen)."""

    code = models.CharField("Leistungsnummer", max_length=30, unique=True)
    bezeichnung = models.CharField("Bezeichnung (Deutsch)", max_length=300)
    bezeichnung_lv = models.CharField("Bezeichnung (Lettisch)", max_length=300, blank=True)
    bezeichnung_en = models.CharField("Bezeichnung (Englisch)", max_length=300, blank=True)
    gruppe = models.CharField(max_length=80, blank=True, help_text="z. B. Operation, Anästhesie, Unterbringung")
    einheit = models.CharField(max_length=30, default="Stück")
    preis = models.DecimalField("Preis (EUR)", max_digits=10, decimal_places=2)
    ust_satz = models.DecimalField("USt. %", max_digits=5, decimal_places=2, default=Decimal("0"),
                                   help_text="0 bei steuerfreien Heilbehandlungen")
    aktiv = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Leistung"
        verbose_name_plural = "Leistungskatalog"
        ordering = ["gruppe", "code"]

    def __str__(self):
        return f"{self.code} {self.bezeichnung}"

    def delete(self, *args, **kwargs):
        raise PermissionError("Leistungen werden nicht gelöscht, nur ausgeblendet.")

    def clean(self):
        fehler = {}
        if self.preis is not None and self.preis < 0:
            fehler["preis"] = "Der Preis darf nicht negativ sein."
        if self.ust_satz is not None and not 0 <= self.ust_satz <= 100:
            fehler["ust_satz"] = "Zwischen 0 und 100 %."
        if fehler:
            raise ValidationError(fehler)

    def text(self, sprache: str) -> str:
        return {"lv": self.bezeichnung_lv, "en": self.bezeichnung_en}.get(sprache) or self.bezeichnung


class Zaehler(models.Model):
    """Fortlaufende Nummern je Art und Jahr (Fälle, Rechnungen) – lückenlos unter Zeilensperre vergeben."""

    art = models.CharField(max_length=20)
    jahr = models.PositiveSmallIntegerField()
    wert = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["art", "jahr"], name="zaehler_je_art_jahr")]

    @classmethod
    def naechster(cls, art: str, jahr: int) -> int:
        with transaction.atomic():
            z, _ = cls.objects.select_for_update().get_or_create(art=art, jahr=jahr)
            z.wert += 1
            z.save(update_fields=["wert"])
            return z.wert


# ====================================================================== Behandlungsfall
class Behandlungsfall(AktenEintrag):
    class Status(models.TextChoices):
        OFFEN = "offen", "offen"
        ABGESCHLOSSEN = "abgeschlossen", "abgeschlossen"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="faelle")
    nummer = models.CharField("Fallnummer", max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OFFEN)
    titel = models.CharField(max_length=200, blank=True, help_text="z. B. „Knie-TEP rechts“")

    # Kostenträger
    kostentraegertyp = models.ForeignKey(Kostentraegertyp, on_delete=models.PROTECT, related_name="faelle",
                                         verbose_name="Kostenträgertyp")
    kostentraeger = models.CharField("Kostenträger", max_length=200, blank=True, help_text="z. B. AOK Bayern, ÖGK Wien")
    land = models.CharField("Land des Kostenträgers", max_length=80, blank=True)
    versichertennummer = models.CharField(max_length=50, blank=True)
    aktenzeichen = models.CharField("Aktenzeichen / Genehmigung", max_length=100, blank=True)
    kooperationspartner = models.ForeignKey(Kooperationspartner, on_delete=models.PROTECT, null=True, blank=True,
                                            related_name="faelle")
    rechnungsempfaenger = models.TextField("Rechnungsempfänger", blank=True,
                                           help_text="leer = Patient mit Anschrift aus der Akte")
    sprache = models.CharField(max_length=2, choices=Sprache.choices, default=Sprache.DE)
    fachbereich = models.CharField(max_length=20, choices=Fachbereich.choices, blank=True, default="")

    # Behandlung
    aufnahme = models.DateField("Aufnahme", null=True, blank=True)
    entlassung = models.DateField("Entlassung", null=True, blank=True)
    op_datum = models.DateField("OP-Datum", null=True, blank=True)
    eingriff = models.CharField(max_length=300, blank=True)
    diagnose = models.TextField(blank=True)
    behandelnder_arzt = models.ForeignKey(Unterzeichner, on_delete=models.PROTECT, null=True, blank=True,
                                          related_name="+", verbose_name="Behandelnder Arzt")

    # OP-Bericht
    operateur = models.CharField(max_length=200, blank=True)
    assistenz = models.CharField(max_length=200, blank=True)
    anaesthesie = models.CharField("Anästhesie", max_length=200, blank=True)
    op_indikation = models.TextField("Indikation", blank=True)
    op_verlauf = models.TextField("OP-Verlauf", blank=True)
    op_befund = models.TextField("Befund / Ergebnis", blank=True)

    # Entlassungsbrief
    entlass_verlauf = models.TextField("Verlauf", blank=True)
    entlass_befunde = models.TextField("Befunde", blank=True)
    entlass_medikation = models.TextField("Medikation bei Entlassung", blank=True)
    entlass_empfehlung = models.TextField("Empfehlung / Procedere", blank=True)

    # Konsiliarbericht
    konsil_empfaenger = models.CharField("Konsil an", max_length=300, blank=True)
    konsil_fragestellung = models.TextField("Fragestellung", blank=True)
    konsil_befund = models.TextField("Befund", blank=True)
    konsil_beurteilung = models.TextField("Beurteilung / Empfehlung", blank=True)

    bemerkung = models.TextField(blank=True)

    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    geaendert_am = models.DateTimeField(auto_now=True)

    history = HistoricalRecords(excluded_fields=["geaendert_am"])

    # Freitexte, die in der DOCX zur Nachbearbeitung stehen (je Dokumentart)
    FREITEXTE = {
        "op_bericht": ["diagnose", "op_indikation", "op_verlauf", "op_befund"],
        "entlassbrief": ["diagnose", "entlass_verlauf", "entlass_befunde", "entlass_medikation", "entlass_empfehlung"],
        "konsil": ["konsil_fragestellung", "konsil_befund", "konsil_beurteilung"],
    }

    class Meta:
        verbose_name = "Behandlungsfall"
        verbose_name_plural = "Behandlungsfälle"
        ordering = ["-erstellt_am", "-id"]
        indexes = [models.Index(fields=["patient", "status"], name="fall_patient_status")]

    def __str__(self):
        return f"Fall {self.nummer}" + (f" · {self.titel}" if self.titel else "")

    def save(self, *args, **kwargs):
        if not self.nummer:
            jahr = timezone.localdate().year
            self.nummer = f"F-{jahr}-{Zaehler.naechster('fall', jahr):04d}"
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.dokumente.exclude(status=FallDokument.Status.ENTWURF).exists():
            raise PermissionError("Ein Fall mit erzeugten Dokumenten wird nicht gelöscht. Bitte abschließen.")
        return super().delete(*args, **kwargs)

    def clean(self):
        fehler = {}
        if self.aufnahme and self.entlassung and self.entlassung < self.aufnahme:
            fehler["entlassung"] = "Die Entlassung liegt vor der Aufnahme."
        if self.op_datum and self.aufnahme and self.op_datum < self.aufnahme:
            fehler["op_datum"] = "Das OP-Datum liegt vor der Aufnahme."
        if self.op_datum and self.entlassung and self.op_datum > self.entlassung:
            fehler["op_datum"] = "Das OP-Datum liegt nach der Entlassung."
        if fehler:
            raise ValidationError(fehler)

    def pruefe_offen(self):
        self.patient.pruefe_bearbeitbar()
        if self.status != self.Status.OFFEN:
            raise ValidationError({"fehler": "Der Fall ist abgeschlossen."})


# ====================================================================== Dokumente des Falls
class FallDokument(AktenEintrag):
    class Art(models.TextChoices):
        OP_BERICHT = "op_bericht", "OP-Bericht"
        ENTLASSBRIEF = "entlassbrief", "Entlassungsbrief"
        KONSIL = "konsil", "Konsiliarbericht"
        RECHNUNG = "rechnung", "Rechnung"
        STORNO = "storno", "Stornorechnung"
        VORLAGE = "vorlage", "Vorlage"

    class Status(models.TextChoices):
        ENTWURF = "entwurf", "Entwurf"
        ERZEUGT = "erzeugt", "erzeugt"
        FINAL = "final", "unterschrieben / signiert"

    class Weg(models.TextChoices):
        SIGNATUR = "signatur", "elektronisch signiert (fortgeschritten, EPM)"
        SIGNATUR_EXTERN = "signatur_extern", "elektronisch signiert (extern, z. B. qualifiziert)"
        SCAN = "scan", "Papierunterschrift (Scan)"
        FINALISIERT = "finalisiert", "finalisiert ohne Unterschrift"

    # Felder, die sich an einer finalen Rechnung noch genau einmal ändern dürfen (Storno; auch im Trigger)
    STORNO_FELDER = ("storniert_am", "storniert_von", "storno_grund")

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="falldokumente")
    fall = models.ForeignKey(Behandlungsfall, on_delete=models.CASCADE, related_name="dokumente")
    art = models.CharField(max_length=20, choices=Art.choices)
    # Schlüssel der Dokumentvorlage bei Art „vorlage“ (z. B. eigen-rgc-f02); sonst leer (aus Art und Sprache)
    vorlage = models.CharField(max_length=60, blank=True)
    titel = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ENTWURF)
    aus_paket = models.BooleanField(default=False)
    freitext = models.TextField(blank=True, help_text="Zusätzlicher Text des Dokuments (z. B. Hinweis auf der Rechnung)")

    # Rechnung und Storno
    rechnungsnummer = models.CharField(max_length=30, null=True, blank=True, unique=True, editable=False)
    rechnungsdatum = models.DateField(null=True, blank=True)
    zahlungsziel_tage = models.PositiveSmallIntegerField(default=14)
    storno_zu = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="stornorechnung", verbose_name="storniert Rechnung")
    storniert_am = models.DateTimeField(null=True, blank=True)
    storniert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    storno_grund = models.CharField(max_length=300, blank=True)

    # Finalisierung
    unterzeichner = models.ForeignKey(Unterzeichner, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    final_weg = models.CharField(max_length=20, choices=Weg.choices, blank=True)
    final_am = models.DateTimeField(null=True, blank=True)
    final_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                  related_name="+")

    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    geaendert_am = models.DateTimeField(auto_now=True)

    history = HistoricalRecords(excluded_fields=["geaendert_am"])

    class Meta:
        verbose_name = "Dokument eines Falls"
        verbose_name_plural = "Dokumente der Fälle"
        ordering = ["fall", "id"]
        constraints = [
            models.CheckConstraint(name="falldokument_final_vollstaendig",
                                   condition=~models.Q(status="final")
                                   | (models.Q(final_am__isnull=False) & ~models.Q(final_weg=""))),
            models.CheckConstraint(name="falldokument_storno_nur_rechnung",
                                   condition=models.Q(storno_zu__isnull=True) | models.Q(art="storno")),
        ]

    def __str__(self):
        return f"{self.titel} ({self.get_status_display()})"

    @property
    def ist_final(self) -> bool:
        return self.status == self.Status.FINAL

    @property
    def ist_rechnung(self) -> bool:
        return self.art in (self.Art.RECHNUNG, self.Art.STORNO)

    @property
    def sprache(self) -> str:
        return self.fall.sprache

    # ------------------------------------------------------------------ Regeln
    def save(self, *args, **kwargs):
        if self.pk:
            alt = FallDokument.objects.filter(pk=self.pk).values_list("status", "storniert_am").first()
            felder = set(kwargs.get("update_fields") or ())
            storno = (alt and alt[0] == self.Status.FINAL and alt[1] is None and felder
                      and felder <= set(self.STORNO_FELDER) | {"geaendert_am"})
            if alt and alt[0] == self.Status.FINAL and not storno:
                raise PermissionError("Dieses Dokument ist unterschrieben bzw. signiert und damit unveränderlich.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.ENTWURF:
            raise PermissionError("Erzeugte Dokumente bleiben erhalten; nur Entwürfe können entfernt werden.")
        return super().delete(*args, **kwargs)

    def pruefe_aenderbar(self):
        self.patient.pruefe_bearbeitbar()
        if self.ist_final:
            raise ValidationError({"fehler": "Dieses Dokument ist unterschrieben bzw. signiert und damit unveränderlich."
                                             + (" Bitte stornieren und neu erzeugen." if self.ist_rechnung else "")})
        if self.storno_zu_id is None and self.art == self.Art.STORNO:
            raise ValidationError({"fehler": "Stornorechnung ohne Bezug."})

    # ------------------------------------------------------------------ Rechnung
    def summen(self) -> dict:
        """{"netto", "ust", "brutto", "ust_saetze": {Satz: Betrag}} aus den Positionen (Storno: negativ)."""
        netto = Decimal("0")
        ust = {}
        for p in self.positionen.all():
            netto += p.betrag
            if p.ust_satz:
                ust[p.ust_satz] = ust.get(p.ust_satz, Decimal("0")) + p.betrag * p.ust_satz / 100
        ust = {s: runde(b) for s, b in ust.items()}
        summe_ust = sum(ust.values(), Decimal("0"))
        return {"netto": runde(netto), "ust": summe_ust, "brutto": runde(netto + summe_ust), "ust_saetze": ust}

    def letzte_version(self):
        return self.versionen.order_by("-nummer").first()


class Rechnungsposition(models.Model):
    """Leistungsposition einer Rechnung: bis zur Finalisierung änderbar (Menge, Preis, Text, Nachtrag, Entfernen).
    Text und Preis kommen beim Anlegen aus dem Leistungskatalog und lassen sich je Position anpassen."""

    dokument = models.ForeignKey(FallDokument, on_delete=models.CASCADE, related_name="positionen")
    reihenfolge = models.PositiveIntegerField(default=0)
    leistung = models.ForeignKey(Leistung, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    code = models.CharField("Leistungsnummer", max_length=30, blank=True)
    text = models.CharField(max_length=500)
    datum = models.DateField("Leistungsdatum", null=True, blank=True)
    menge = models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("1"))
    einheit = models.CharField(max_length=30, blank=True)
    einzelpreis = models.DecimalField("Einzelpreis (EUR)", max_digits=10, decimal_places=2)
    ust_satz = models.DecimalField("USt. %", max_digits=5, decimal_places=2, default=Decimal("0"))

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Rechnungsposition"
        verbose_name_plural = "Rechnungspositionen"
        ordering = ["dokument", "reihenfolge", "id"]

    def __str__(self):
        return f"{self.code} {self.text}".strip()

    @property
    def betrag(self) -> Decimal:
        return runde((self.menge or 0) * (self.einzelpreis or 0))

    def _pruefe_dokument(self):
        # Zeile sperren: eine gleichzeitige Finalisierung wartet bzw. die Änderung sieht schon „final“
        dok = FallDokument.objects.select_for_update().select_related("patient").get(pk=self.dokument_id)
        if not dok.ist_rechnung:
            raise ValidationError({"dokument": "Positionen gibt es nur an Rechnungen."})
        dok.pruefe_aenderbar()
        if dok.art == FallDokument.Art.STORNO and dok.versionen.exists():
            raise ValidationError({"fehler": "Die Positionen einer Stornorechnung spiegeln die stornierte Rechnung "
                                             "und lassen sich nicht ändern."})

    def save(self, *args, **kwargs):
        self._pruefe_dokument()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._pruefe_dokument()
        return super().delete(*args, **kwargs)

    def clean(self):
        fehler = {}
        if not (self.text or "").strip():
            fehler["text"] = "Bitte einen Text angeben."
        if self.menge is not None and self.menge == 0:
            fehler["menge"] = "Die Menge darf nicht 0 sein."
        if self.ust_satz is not None and not 0 <= self.ust_satz <= 100:
            fehler["ust_satz"] = "Zwischen 0 und 100 %."
        if fehler:
            raise ValidationError(fehler)


class DokumentVersion(models.Model):
    """Eine Erzeugung (oder die finale Fassung) eines Dokuments – unveränderlich, nur anfügen (Trigger).

    Die PDF liegt als Dokument der Akte (bis zur finalen Fassung ausgeblendet), dazu Prüfsumme, Vorlagenversion und
    der Datenstand, aus dem sie entstand. ``daten_hash`` zeigt, ob sich die Falldaten seitdem geändert haben."""

    class Art(models.TextChoices):
        ERZEUGT = "erzeugt", "erzeugt"
        DOCX = "docx", "aus DOCX übernommen"
        SIGNATUR = "signatur", "elektronisch signiert"
        SIGNATUR_EXTERN = "signatur_extern", "extern signiert hochgeladen"
        SCAN = "scan", "Scan der Papierunterschrift"
        FINALISIERT = "finalisiert", "finalisiert"

    dokument = models.ForeignKey(FallDokument, on_delete=models.PROTECT, related_name="versionen")
    nummer = models.PositiveIntegerField()
    art = models.CharField(max_length=20, choices=Art.choices)
    pdf = models.ForeignKey("patienten.Dokument", on_delete=models.PROTECT, related_name="+")
    sha256 = models.CharField(max_length=64)
    docx = models.ForeignKey("patienten.Dokument", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                             verbose_name="übernommene DOCX")
    vorlage = models.CharField(max_length=60, blank=True)
    vorlage_version = models.PositiveIntegerField(null=True, blank=True)
    daten = models.JSONField(default=dict, blank=True)
    daten_hash = models.CharField(max_length=64, blank=True)
    grund = models.CharField(max_length=300, blank=True)
    final = models.BooleanField(default=False)
    erzeugt_am = models.DateTimeField(auto_now_add=True)
    erzeugt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")

    class Meta:
        verbose_name = "Fassung eines Dokuments"
        verbose_name_plural = "Fassungen der Dokumente"
        ordering = ["dokument", "-nummer"]
        constraints = [models.UniqueConstraint(fields=["dokument", "nummer"], name="version_je_dokument")]

    def __str__(self):
        return f"{self.dokument} · Fassung {self.nummer}"
