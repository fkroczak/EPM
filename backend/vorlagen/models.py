"""Dokumentvorlagen (Entwurf 18 · Dokumentvorlagen): Infusionsplan, Patientendatenblatt und die Erklärungen zum
Datenschutz (Datenschutzinformation, Einwilligung, Schweigepflichtentbindung) aus Blöcken.

Je Art gibt es höchstens einen Entwurf und genau eine aktive Version. Veröffentlichen macht aus dem Entwurf die
nächste Version; die bisherige wird „abgelöst“ und bleibt erhalten. Veröffentlichte Versionen sind unveränderlich
(Modell), damit jede gespeicherte PDF auf ihre Vorlagenversion zurückgeführt werden kann.

Vorlagen je Firma (Festlegung „Gemischt“, 11.10.2026): Ohne ``firma`` ist eine Vorlage gemeinsam. Eine Firma kann je
Art eine eigene Vorlage anlegen (Kopie der gemeinsamen); dann gelten Entwurf, Fassungen und Veröffentlichen für
ihre Vorlage, und ``aktive()`` liefert in dieser Firma ihre aktive Fassung, sonst die gemeinsame. Die Word-Vorlagen der
Regeneration Clinic sind eigene Schreiben der Firma RGC (``vorlagen.rgc``).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from simple_history.models import HistoricalRecords


class Dokumentvorlage(models.Model):
    class Art(models.TextChoices):
        INFUSIONSPLAN = "infusionsplan", "Infusionsplan"
        PATIENTENDATENBLATT = "patientendatenblatt", "Patientendatenblatt"
        # Wünsche aus der Praxis vom 06.10.2026: Berichte aus der Akte (F115) und das Sprechstundenblatt (F116)
        BERICHT = "bericht", "Bericht"
        SPRECHSTUNDE = "sprechstunde", "Unterlagen für die Sprechstunde"
        # Medikamentenplan der Akte (Wunsch 11.10.2026)
        MEDIKATIONSPLAN = "medikationsplan", "Medikationsplan"
        # Schreiben mit E-Mail-Text (Vorlagen von Alice Hessel, 09.10.2026): aus der Akte (F172) bzw. aus dem
        # Kalender für alle Termine eines Zeitraums (F173)
        PATIENTENAUFNAHME = "patientenaufnahme", "Patientenaufnahme (benötigte Unterlagen)"
        TERMINBESTAETIGUNG = "terminbestaetigung", "Terminbestätigung Sprechstunde"
        REISEBESCHEINIGUNG = "reisebescheinigung", "Reisebescheinigung"
        PATIENTENANKUENDIGUNG = "patientenankuendigung", "Patientenankündigung Sprechstunde"
        # Datenschutz (Festlegung 02.10.2026): zum Ausdrucken und Unterschreiben je Patient. Die mitgelieferten
        # Startvorlagen sind Entwürfe mit Lücken in [eckigen Klammern]; bis die Stiftung sie geprüft und
        # veröffentlicht hat, tragen die PDFs das Wasserzeichen „ENTWURF“.
        DATENSCHUTZINFORMATION = "datenschutzinformation", "Datenschutzinformation"
        EINWILLIGUNG = "einwilligung", "Einwilligung in die Datenverarbeitung"
        SCHWEIGEPFLICHTENTBINDUNG = "schweigepflichtentbindung", "Schweigepflichtentbindung"
        # zwei Firmen (11.10.2026): Voraussetzung, um eine Akte der DSKM und der Regeneration Clinic zuzuordnen
        FIRMEN = "firmen", "Einwilligung Austausch zwischen DSKM und Regeneration Clinic"

    class Ausrichtung(models.TextChoices):
        HOCH = "hoch", "Hochformat"
        QUER = "quer", "Querformat"

    class Status(models.TextChoices):
        ENTWURF = "entwurf", "Entwurf"
        AKTIV = "aktiv", "aktiv"
        ABGELOEST = "abgeloest", "abgelöst"

    # feste Arten (``Art``) oder eigene Schreiben „eigen-…“ (F176, ``EigenesSchreiben``) – daher ohne choices
    art = models.CharField(max_length=30)
    # leer = gemeinsame Vorlage; gesetzt = eigene Vorlage dieser Firma (11.10.2026)
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="dokumentvorlagen")
    version = models.PositiveIntegerField(null=True, blank=True, help_text="leer beim Entwurf")
    # Seitenformat der PDF (Medikationsplan im Querformat, 13.10.2026)
    ausrichtung = models.CharField(max_length=4, choices=Ausrichtung.choices, default=Ausrichtung.HOCH)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ENTWURF)
    bloecke = models.JSONField(default=list)
    notiz = models.CharField(max_length=200, blank=True, help_text="z. B. „Startvorlage nach Entwurf“")
    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")
    geaendert_am = models.DateTimeField(auto_now=True)
    geaendert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+")
    veroeffentlicht_am = models.DateTimeField(null=True, blank=True)
    veroeffentlicht_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True,
                                            blank=True, related_name="+")

    history = HistoricalRecords(excluded_fields=["geaendert_am"])

    class Meta:
        verbose_name = "Dokumentvorlage"
        verbose_name_plural = "Dokumentvorlagen"
        ordering = ["art", "-version"]
        constraints = [
            # je Art und Firma (gemeinsam = NULL, zählt hier wie ein Wert) ein Entwurf, eine aktive, eindeutige Versionen
            models.UniqueConstraint(fields=["art", "firma"], condition=models.Q(status="entwurf"),
                                    nulls_distinct=False, name="ein_entwurf_je_art"),
            models.UniqueConstraint(fields=["art", "firma"], condition=models.Q(status="aktiv"),
                                    nulls_distinct=False, name="eine_aktive_je_art"),
            models.UniqueConstraint(fields=["art", "firma", "version"], nulls_distinct=False,
                                    name="version_je_art_eindeutig"),
            models.CheckConstraint(name="version_nur_veroeffentlicht",
                                   condition=models.Q(status="entwurf", version__isnull=True)
                                   | (~models.Q(status="entwurf") & models.Q(version__isnull=False))),
        ]

    def __str__(self):
        firma = f" ({self.firma.kurzname})" if self.firma_id else ""
        return f"{self.get_art_display()}{firma} {'Entwurf' if self.version is None else f'v{self.version}'}"

    def get_art_display(self) -> str:
        return art_name(self.art)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.pk and not (update_fields and set(update_fields) <= {"status"}):
            alt = Dokumentvorlage.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if alt != self.Status.ENTWURF:
                raise PermissionError("Veröffentlichte Vorlagen sind unveränderlich. Bitte einen neuen Entwurf anlegen.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.ENTWURF:
            raise PermissionError("Veröffentlichte Vorlagen werden nicht gelöscht.")
        return super().delete(*args, **kwargs)

    def clean(self):
        from .bloecke import pruefe_bloecke

        fehler = pruefe_bloecke(self.art, self.bloecke)
        if fehler:
            raise ValidationError({"bloecke": fehler})

    # --- Abläufe ---
    @classmethod
    def aktive(cls, art: str, firma=None) -> "Dokumentvorlage":
        """Die aktive Version für die Firma (ohne Angabe: die aktive Firma der Anfrage): ihre eigene, sonst die
        gemeinsame. Gibt es noch keine, wird die Startvorlage nach dem Entwurf als v1 angelegt – bei Vorlagen, die
        fest zu einer Firma gehören (``NUR_FIRMA``), als Vorlage dieser Firma."""
        firma = firma_der_art(art, firma)
        if firma is not None:
            v = cls.objects.filter(art=art, firma=firma, status=cls.Status.AKTIV).first()
            if v is not None:
                return v
        return cls._aktive_oder_start(art, firma if art in NUR_FIRMA else None)

    @classmethod
    def gemeinsame(cls, art: str) -> "Dokumentvorlage":
        """Die gemeinsame aktive Version (unabhängig von der Firma)."""
        return cls._aktive_oder_start(art, None)

    @classmethod
    def _aktive_oder_start(cls, art: str, ziel) -> "Dokumentvorlage":
        v = cls.objects.filter(art=art, firma=ziel, status=cls.Status.AKTIV).first()
        if v is None:
            from .bloecke import STARTAUSRICHTUNG, STARTVORLAGEN

            with transaction.atomic():
                v = cls.objects.select_for_update().filter(art=art, firma=ziel, status=cls.Status.AKTIV).first()
                if v is None:
                    v = cls.objects.create(art=art, firma=ziel, version=1, status=cls.Status.AKTIV,
                                           bloecke=STARTVORLAGEN[art], notiz="Startvorlage nach Entwurf",
                                           ausrichtung=STARTAUSRICHTUNG.get(art, cls.Ausrichtung.HOCH),
                                           veroeffentlicht_am=timezone.now())
        return v

    @classmethod
    def zustaendig(cls, art: str, firma=None):
        """Welche Vorlage gilt beim Bearbeiten in der Firma: ihre eigene (→ die Firma), sonst die gemeinsame
        (→ ``None``). Vorlagen, die fest zu einer Firma gehören, immer diese Firma."""
        firma = firma_der_art(art, firma)
        if firma is None:
            return None
        if art in NUR_FIRMA or cls.objects.filter(art=art, firma=firma, status=cls.Status.AKTIV).exists():
            return firma
        return None

    @classmethod
    def eigene_anlegen(cls, art: str, firma, benutzer) -> "Dokumentvorlage":
        """Eigene Vorlage der Firma als Kopie der gemeinsamen aktiven Fassung – sofort in Gebrauch. Hat die Firma
        schon einmal eine eigene gehabt (abgelöst), zählt die Fassung weiter."""
        if art in NUR_FIRMA:
            raise ValidationError("Diese Vorlage gehört fest zur Firma.")
        with transaction.atomic():
            eigene = cls.objects.filter(art=art, firma=firma, status=cls.Status.AKTIV).first()
            if eigene is not None:
                return eigene
            quelle = cls.gemeinsame(art)
            hoechste = cls.objects.filter(art=art, firma=firma).aggregate(m=models.Max("version"))["m"] or 0
            # Wasserzeichen „ENTWURF“ bleibt, solange die Kopie eine ungeprüfte Startvorlage ist (veroeffentlicht_von)
            return cls.objects.create(art=art, firma=firma, version=hoechste + 1, status=cls.Status.AKTIV,
                                      bloecke=quelle.bloecke, ausrichtung=quelle.ausrichtung, erstellt_von=benutzer,
                                      notiz=f"Kopie der gemeinsamen Vorlage, Fassung {quelle.version}",
                                      veroeffentlicht_am=timezone.now(), veroeffentlicht_von=quelle.veroeffentlicht_von)

    @classmethod
    def eigene_entfernen(cls, art: str, firma) -> int:
        """Eigene Vorlage der Firma ablegen (aktive Fassung abgelöst, Entwurf verworfen) – es gilt wieder die
        gemeinsame. Die Fassungen bleiben erhalten. → Zahl der abgelösten Fassungen."""
        if art in NUR_FIRMA:
            raise ValidationError("Diese Vorlage gehört fest zur Firma.")
        with transaction.atomic():
            for entwurf in cls.objects.filter(art=art, firma=firma, status=cls.Status.ENTWURF):
                entwurf.delete()
            abgeloest = 0
            for v in cls.objects.select_for_update().filter(art=art, firma=firma, status=cls.Status.AKTIV):
                v.status = cls.Status.ABGELOEST
                v.save(update_fields=["status"])
                abgeloest += 1
            return abgeloest

    # Vordrucke zum Datenschutz: mitgelieferte Startvorlagen sind ungeprüfte Entwürfe (U17)
    VORDRUCKE = ("datenschutzinformation", "einwilligung", "schweigepflichtentbindung", "firmen")

    @property
    def entwurfsmodus_schluessel(self) -> str:
        """Eintrag in ``Einstellungen.vordrucke_ohne_entwurf``: die Art, bei einer eigenen Vorlage „art@firma“."""
        return f"{self.art}@{self.firma.kuerzel}" if self.firma_id else self.art

    @property
    def im_entwurfsmodus(self) -> bool:
        """Trägt die PDF das Wasserzeichen „ENTWURF“? Bei den Vordrucken, solange die mitgelieferte Startvorlage aktiv
        ist (nie von einem Menschen veröffentlicht) – außer jemand hat den Entwurfsmodus für diese Art ausgeschaltet."""
        from stammdaten.models import Einstellungen

        if self.art not in self.VORDRUCKE or self.veroeffentlicht_von_id is not None:
            return False
        return self.entwurfsmodus_schluessel not in (Einstellungen.aktuell().vordrucke_ohne_entwurf or [])

    @classmethod
    def entwurf_von(cls, art: str, firma=None):
        """Der Entwurf der Vorlage, die in der Firma gilt (``zustaendig``)."""
        return cls.objects.filter(art=art, firma=cls.zustaendig(art, firma), status=cls.Status.ENTWURF).first()

    @transaction.atomic
    def veroeffentlichen(self, benutzer) -> "Dokumentvorlage":
        if self.status != self.Status.ENTWURF:
            raise ValidationError("Nur ein Entwurf kann veröffentlicht werden.")
        self.full_clean()
        alt = Dokumentvorlage.objects.select_for_update().filter(art=self.art, firma=self.firma,
                                                                 status=self.Status.AKTIV).first()
        hoechste = Dokumentvorlage.objects.filter(art=self.art, firma=self.firma) \
            .aggregate(m=models.Max("version"))["m"] or 0
        if alt:
            alt.status = self.Status.ABGELOEST
            alt.save(update_fields=["status"])
        self.status = self.Status.AKTIV
        self.version = hoechste + 1
        self.veroeffentlicht_am = timezone.now()
        self.veroeffentlicht_von = benutzer
        super().save()  # letzter Schreibvorgang, danach unveränderlich
        return self


# Arten, die fest zu einer Firma gehören (Art → Kürzel). Derzeit keine: die Vorlagen der Regeneration Clinic sind eigene
# Schreiben der Firma RGC (``EigenesSchreiben.firma``, ``vorlagen.rgc``).
NUR_FIRMA: dict[str, str] = {}


def firma_der_art(art: str, firma=None):
    """Firma, deren Vorlage gilt: bei fest zugeordneten Arten diese, sonst die übergebene bzw. aktive Firma."""
    from epm.firma import aktive_firma

    if art in NUR_FIRMA:
        from stammdaten.models import Firma

        return Firma.objects.get(kuerzel=NUR_FIRMA[art])
    return firma or aktive_firma()


def art_sichtbar(art: str, firma=None) -> bool:
    """Erscheint die Art in der Firma (ohne aktive Firma: überall)? Die RGC-Vorlagen nur in der RGC."""
    from epm.firma import aktive_firma

    firma = firma or aktive_firma()
    return art not in NUR_FIRMA or firma is None or firma.kuerzel == NUR_FIRMA[art]


def vordruck_schluessel_gueltig(schluessel) -> bool:
    """Eintrag in ``Einstellungen.vordrucke_ohne_entwurf``: Art eines Vordrucks, bei einer eigenen Vorlage „art@firma“."""
    if not isinstance(schluessel, str):
        return False
    art, _, firma = schluessel.partition("@")
    return art in Dokumentvorlage.VORDRUCKE and (not firma or firma.isalnum())


def art_name(art: str) -> str:
    """Anzeigename einer Vorlagenart, auch eines eigenen Schreibens (F176)."""
    if art in Dokumentvorlage.Art.values:
        return Dokumentvorlage.Art(art).label
    e = EigenesSchreiben.objects.filter(schluessel=art).only("name").first()
    return e.name if e else art


def gibt_es_art(art) -> bool:
    return isinstance(art, str) and (art in Dokumentvorlage.Art.values
                                     or EigenesSchreiben.sichtbare().filter(schluessel=art).exists())


class EigenesSchreiben(models.Model):
    """Unter Vorlagen › Dokumentvorlagen selbst angelegtes Schreiben (F176), z. B. „Rezeptanforderung“. Der Aufbau
    liegt wie bei den festen Arten in ``Dokumentvorlage`` (Art = ``schluessel``); hier stehen Name, Beschreibung und ob
    beim Erzeugen ein Termin gewählt wird. Nie gelöscht, nur deaktiviert (dann nicht mehr in der Akte wählbar)."""

    schluessel = models.CharField(max_length=30, unique=True, editable=False)
    name = models.CharField(max_length=100, unique=True)
    beschreibung = models.CharField(max_length=300, blank=True)
    mit_termin = models.BooleanField("Termin wählen", default=False)
    aktiv = models.BooleanField(default=True)
    # Vorlagen einer Firma (RGC-Vorlagen, 13.10.2026): nur in dieser Firma sichtbar; leer = in allen Firmen
    firma = models.ForeignKey("stammdaten.Firma", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="eigene_schreiben")
    # Gruppe in der Übersicht und in der Akte (``portal.GRUPPEN``), z. B. „anforderungen“ für Labor und Bildgebung
    gruppe = models.CharField(max_length=20, default="eigen")
    # mitgelieferte Vorlagen (z. B. „rgc-labor-01“): Kennung der Quelle, damit sie nur einmal angelegt werden
    mitgeliefert = models.CharField(max_length=40, unique=True, null=True, blank=True, editable=False)
    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                     related_name="+")

    history = HistoricalRecords()

    @classmethod
    def sichtbare(cls, firma=None):
        """Eigene Schreiben der aktiven Firma und die ohne Firma. Ohne aktive Firma (Befehle, Hintergrund) gilt wie bei
        den Akten die Hauptfirma (DSKM)."""
        from epm.firma import HAUPTFIRMA, aktive_firma

        firma = firma or aktive_firma()
        eigene = models.Q(firma=firma) if firma is not None else models.Q(firma__kuerzel=HAUPTFIRMA)
        return cls.objects.filter(eigene | models.Q(firma__isnull=True))

    class Meta:
        verbose_name = "Eigenes Schreiben"
        verbose_name_plural = "Eigene Schreiben"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        raise PermissionError("Eigene Schreiben werden nicht gelöscht, nur deaktiviert.")

    def save(self, *args, **kwargs):
        if not self.schluessel:
            import secrets

            from .felder import EIGEN_PRAEFIX

            self.schluessel = f"{EIGEN_PRAEFIX}{secrets.token_hex(5)}"
        super().save(*args, **kwargs)


class Anlage(models.Model):
    """PDF zum Anhängen an die E-Mails der Schreiben (F174), z. B. der Leitfaden Zottentraining oder die
    Handlungsempfehlung zu Locklösungen. Gepflegt unter Vorlagen › Anlagen; nie gelöscht, nur deaktiviert.

    Die mitgelieferten Anlagen (``MITGELIEFERT``, Dateien in ``statisch/anlagen``) werden beim ersten Aufruf der
    Liste einmal angelegt und danach wie hochgeladene behandelt."""

    name = models.CharField(max_length=150)
    beschreibung = models.CharField(max_length=300, blank=True)
    datei = models.CharField(max_length=255, unique=True, editable=False, help_text="Pfad unter EPM_DOKUMENTE")
    dateiname = models.CharField(max_length=150, editable=False)
    sha256 = models.CharField(max_length=64, editable=False)
    groesse = models.PositiveIntegerField(editable=False)
    mitgeliefert = models.CharField(max_length=40, unique=True, null=True, blank=True, editable=False)
    aktiv = models.BooleanField(default=True)
    reihenfolge = models.PositiveSmallIntegerField(default=100)
    hochgeladen_am = models.DateTimeField(auto_now_add=True)
    hochgeladen_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="+")

    history = HistoricalRecords()

    MITGELIEFERT = [
        ("zottentraining", "Leitfaden Kurzdarmsyndrom und Zottentraining", "Zottentraining.pdf",
         "Leitfaden für Patientinnen und Patienten nach Prof. Dr. Markus Masin"),
        ("lockloesungen", "Handlungsempfehlung Aspiration NutriLock/TauroLock", "Handlungsempfehlung-Lockloesungen.pdf",
         "Aspiration von NutriLock- und TauroLock-Locklösungen"),
        ("blutuntersuchung", "Blutuntersuchung – Schreiben an Hausärzte", "Blutuntersuchung-2026.pdf",
         "Bitte um wohnortnahe Blutabnahme mit Übersicht der Laborparameter"),
    ]

    class Meta:
        verbose_name = "Anlage"
        verbose_name_plural = "Anlagen"
        ordering = ["reihenfolge", "name"]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        raise PermissionError("Anlagen werden nicht gelöscht, nur deaktiviert.")

    @property
    def pfad(self):
        return settings.EPM_DOKUMENTE / self.datei

    @classmethod
    def mitgelieferte_anlegen(cls):
        from pathlib import Path

        from .pdf import sha256

        ordner = Path(__file__).resolve().parent / "statisch" / "anlagen"
        vorhanden = set(cls.objects.exclude(mitgeliefert=None).values_list("mitgeliefert", flat=True))
        for i, (schluessel, name, dateiname, beschreibung) in enumerate(cls.MITGELIEFERT):
            quelle = ordner / dateiname
            if schluessel in vorhanden or not quelle.is_file():
                continue
            daten = quelle.read_bytes()
            ziel = f"anlagen/{schluessel}-{sha256(daten)[:12]}.pdf"
            (settings.EPM_DOKUMENTE / "anlagen").mkdir(parents=True, exist_ok=True)
            (settings.EPM_DOKUMENTE / ziel).write_bytes(daten)
            cls.objects.get_or_create(mitgeliefert=schluessel, defaults=dict(
                name=name, beschreibung=beschreibung, datei=ziel, dateiname=dateiname, sha256=sha256(daten),
                groesse=len(daten), reihenfolge=10 * (i + 1)))
