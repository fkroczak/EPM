"""Korrespondenz der Akte (Wunsch der Praxis, 14.10.2026): Entwurf → freigegeben → versendet.

Jedes Schreiben an oder über einen Patienten (Arztbrief, Anforderung, Bescheinigung, Erklärung …) liegt in der Akte.
Es entsteht aus einer Dokumentvorlage der Schreiben (feste und eigene, ``vorlagen.schreiben.schreiben_aus_akte``) mit
Betreff, Empfänger und Freitext. Solange es Entwurf ist, lässt es sich ändern und löschen. Mit der Freigabe entsteht
die endgültige PDF aus der aktiven Vorlage und den Daten der Akte zu diesem Zeitpunkt; sie liegt als Dokument der Akte
ab (Prüfsumme und Vorlagenversion am Schreiben, die verwendeten Blöcke als Momentaufnahme). Danach ist das Schreiben
unveränderlich (Modell und Datenbank-Trigger, ``audit.schutz``) – bis auf den einmaligen Vermerk „versendet“ mit Weg
und Datum. Eine Korrektur ist ein neues Schreiben („Als neuen Entwurf kopieren“).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from simple_history.models import HistoricalRecords

from patienten.models import AktenEintrag, Patient

MAX_TEXT = 20000


class Schreiben(AktenEintrag):
    class Status(models.TextChoices):
        ENTWURF = "entwurf", "Entwurf"
        FREIGEGEBEN = "freigegeben", "freigegeben"
        VERSENDET = "versendet", "versendet"

    class Versandweg(models.TextChoices):
        POST = "post", "Post"
        EMAIL = "email", "E-Mail"
        FAX = "fax", "Fax"
        PERSOENLICH = "persoenlich", "persönlich übergeben"
        PORTAL = "portal", "Portal"
        SONSTIGES = "sonstiges", "anderer Weg"

    # Was sich beim Vermerk „versendet“ an einem freigegebenen Schreiben ändern darf (auch im Trigger)
    VERSAND_FELDER = ("status", "versendet_am", "versandweg", "versand_notiz", "versendet_von", "versand_erfasst_am")

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="korrespondenz")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ENTWURF)
    # Schlüssel der Dokumentvorlage (feste Schreiben oder „eigen-…“) und ihr Name beim Anlegen bzw. bei der Freigabe –
    # eigene Schreiben können später umbenannt oder ausgeschaltet werden
    vorlage = models.CharField("Dokumentvorlage", max_length=60)
    vorlage_name = models.CharField("Name der Vorlage", max_length=200, blank=True)
    vorlage_version = models.PositiveIntegerField(null=True, blank=True)
    titel = models.CharField("Betreff", max_length=200)
    empfaenger = models.CharField("Empfänger", max_length=300, blank=True)
    text = models.TextField("Freitext", blank=True)
    termin = models.ForeignKey("patienten.Termin", on_delete=models.RESTRICT, null=True, blank=True, related_name="+")
    # Angaben der Vorlage, z. B. Reisebescheinigung: {"attest": true, "tage": 14}
    optionen = models.JSONField(default=dict, blank=True)
    # Momentaufnahme der Blöcke, aus denen die freigegebene PDF entstand
    bloecke = models.JSONField(default=list, blank=True)
    kopie_von = models.PositiveIntegerField("kopiert aus Schreiben Nr.", null=True, blank=True)

    erstellt_am = models.DateTimeField(auto_now_add=True)
    erstellt_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    geaendert_am = models.DateTimeField(auto_now=True)
    freigegeben_am = models.DateTimeField(null=True, blank=True)
    freigegeben_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                        related_name="+")
    dokument = models.ForeignKey("patienten.Dokument", on_delete=models.PROTECT, null=True, blank=True,
                                 related_name="+", verbose_name="Freigegebene PDF")
    pdf_sha256 = models.CharField(max_length=64, blank=True)

    versendet_am = models.DateField(null=True, blank=True)
    versandweg = models.CharField(max_length=20, choices=Versandweg.choices, blank=True)
    versand_notiz = models.CharField(max_length=300, blank=True)
    versendet_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
                                      related_name="+", verbose_name="Versand vermerkt von")
    versand_erfasst_am = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords(excluded_fields=["geaendert_am"])

    class Meta:
        verbose_name = "Schreiben"
        verbose_name_plural = "Schreiben"
        ordering = ["-erstellt_am", "-id"]
        indexes = [models.Index(fields=["patient", "status"], name="schreiben_patient_status")]

    def __str__(self):
        return f"{self.titel} ({self.get_status_display()})"

    @property
    def ist_entwurf(self) -> bool:
        return self.status == self.Status.ENTWURF

    # ------------------------------------------------------------------ Regeln
    def save(self, *args, **kwargs):
        if self.pk:
            alt = Schreiben.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            felder = set(kwargs.get("update_fields") or ())
            versand = (alt == self.Status.FREIGEGEBEN and self.status == self.Status.VERSENDET
                       and felder and felder <= set(self.VERSAND_FELDER))
            if alt not in (None, self.Status.ENTWURF) and not versand:
                raise PermissionError("Freigegebene Schreiben sind unveränderlich. "
                                      "Bitte als neuen Entwurf kopieren.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != self.Status.ENTWURF:
            raise PermissionError("Nur Entwürfe können gelöscht werden.")
        return super().delete(*args, **kwargs)

    def clean(self):
        fehler = {}
        if not (self.titel or "").strip():
            fehler["titel"] = "Bitte einen Betreff angeben."
        if len(self.text or "") > MAX_TEXT:
            fehler["text"] = f"Höchstens {MAX_TEXT} Zeichen."
        if self.termin_id and self.termin.patient_id != self.patient_id:
            fehler["termin"] = "Der Termin gehört zu einer anderen Akte."
        if fehler:
            raise ValidationError(fehler)

    # ------------------------------------------------------------------ Anzeige
    @property
    def freigabevermerk(self) -> str | None:
        from epm.api_basis import benutzername

        if not self.freigegeben_von_id or not self.freigegeben_am:
            return None
        return (f"Freigegeben von {benutzername(self.freigegeben_von)} "
                f"am {timezone.localtime(self.freigegeben_am):%d.%m.%Y}.")

    @property
    def dateiname(self) -> str:
        from vorlagen.schreiben import dateiname_sicher

        tag = timezone.localtime(self.freigegeben_am).date() if self.freigegeben_am else timezone.localdate()
        return f"{dateiname_sicher(f'{self.titel}-{self.patient.nachname}-{tag:%Y-%m-%d}')}.pdf"

    # ------------------------------------------------------------------ PDF
    def vorlage_angaben(self) -> dict | None:
        """{"termin": bool, …} der Vorlage – None, wenn es sie in der aktiven Firma (nicht mehr) gibt."""
        from vorlagen.schreiben import schreiben_aus_akte

        return schreiben_aus_akte(self.vorlage)

    def kontext(self):
        from vorlagen.felder import Kontext

        return Kontext(patient=self.patient, termin=self.termin, benutzer=self.erstellt_von, schreiben=self)

    def bloecke_fuer(self, vorlage) -> list:
        """Die Blöcke der Vorlage; fehlt dort das Feld ``{{Schreiben.Text}}``, steht der Freitext vor dem Gruß (bzw.
        vor Unterschrift, Fußzeile oder E-Mail-Block, sonst am Ende)."""
        bloecke = [dict(b) for b in vorlage.bloecke]
        if not (self.text or "").strip() or "Schreiben.Text" in str(vorlage.bloecke):
            return bloecke
        block = {"id": "korrespondenz_text", "typ": "text", "bezeichnung": "Text", "text": "{{Schreiben.Text}}",
                 "optionen": {"ausblenden_wenn_leer": True}}
        stelle = next((i for i, b in enumerate(bloecke) if b.get("id") == "gruss"), None)
        if stelle is None:
            stelle = next((i for i, b in enumerate(bloecke) if b.get("typ") in ("unterschrift", "fusszeile", "email")),
                          len(bloecke))
        return [*bloecke[:stelle], block, *bloecke[stelle:]]

    def erzeuge_pdf(self, wasserzeichen=None) -> tuple[bytes, int | None, list]:
        """PDF aus der aktiven Vorlage (in der aktiven Firma) → (PDF, Vorlagenversion, verwendete Blöcke)."""
        from vorlagen.models import Dokumentvorlage
        from vorlagen.pdf import erzeuge_aus_vorlage
        from vorlagen.schreiben import anhaengen, reise_attest

        vorlage = Dokumentvorlage.aktive(self.vorlage)
        bloecke = self.bloecke_fuer(vorlage)
        p = self.patient
        pdf, version = erzeuge_aus_vorlage(self.vorlage, self.kontext(), vorlage=vorlage, bloecke=bloecke,
                                           wasserzeichen=wasserzeichen, titel=f"{self.titel} – {p.nachname}, {p.vorname}")
        o = self.optionen or {}
        if self.vorlage == Dokumentvorlage.Art.REISEBESCHEINIGUNG and o.get("attest", True) is not False:
            pdf = anhaengen(pdf, [reise_attest(self.kontext(), tage=o.get("tage") or None)])
        return pdf, version, bloecke

    def pruefe_vorlage(self):
        angaben = self.vorlage_angaben()
        if angaben is None:
            raise ValidationError({"vorlage": "Diese Vorlage gibt es hier nicht (mehr). Bitte eine andere wählen."})
        if angaben["termin"] and not self.termin_id:
            raise ValidationError({"termin": "Bitte einen Termin wählen."})

    @transaction.atomic
    def freigeben(self, benutzer):
        """Erzeugt die endgültige PDF, legt sie als Dokument der Akte ab und friert das Schreiben ein."""
        from vorlagen.models import art_name
        from vorlagen.pdf import als_dokument, wasserzeichen_fuer

        if not benutzer.hat_recht("schreiben_freigeben"):
            raise PermissionError("Schreiben freigeben darf nur, wer das Recht dazu hat.")
        if self.status != self.Status.ENTWURF:
            raise ValidationError({"fehler": "Nur Entwürfe können freigegeben werden."})
        self.patient.pruefe_bearbeitbar()
        self.full_clean(exclude=["patient", "erstellt_von", "firma", "termin"])
        self.pruefe_vorlage()
        self.status = self.Status.FREIGEGEBEN
        self.freigegeben_am = timezone.now()
        self.freigegeben_von = benutzer
        self.vorlage_name = art_name(self.vorlage)[:200]
        pdf, version, bloecke = self.erzeuge_pdf(wasserzeichen=wasserzeichen_fuer(self.patient))
        heute = timezone.localdate()
        dok = als_dokument(self.patient, pdf, self.titel, "Schreiben", heute, benutzer, self.dateiname)
        self.dokument, self.pdf_sha256, self.vorlage_version, self.bloecke = dok, dok.sha256, version, bloecke
        try:
            super().save()  # letzter Schreibvorgang am Entwurf, danach gesperrt
        except BaseException:
            dok.pfad.unlink(missing_ok=True)
            raise
        return self

    def als_versendet(self, benutzer, am, weg: str, notiz: str = ""):
        fehler = {}
        if self.status == self.Status.ENTWURF:
            raise ValidationError({"fehler": "Bitte das Schreiben zuerst freigeben."})
        if self.status == self.Status.VERSENDET:
            raise ValidationError({"fehler": "Das Schreiben ist bereits als versendet vermerkt."})
        if weg not in self.Versandweg.values:
            fehler["versandweg"] = "Bitte den Weg wählen."
        if am is None:
            fehler["versendet_am"] = "Bitte das Datum angeben."
        elif am > timezone.localdate():
            fehler["versendet_am"] = "Das Datum liegt in der Zukunft."
        elif self.freigegeben_am and am < timezone.localtime(self.freigegeben_am).date():
            fehler["versendet_am"] = "Das Datum liegt vor der Freigabe."
        if len(notiz) > 300:
            fehler["versand_notiz"] = "Höchstens 300 Zeichen."
        if fehler:
            raise ValidationError(fehler)
        self.patient.pruefe_bearbeitbar()
        self.status = self.Status.VERSENDET
        self.versendet_am, self.versandweg, self.versand_notiz = am, weg, notiz
        self.versendet_von, self.versand_erfasst_am = benutzer, timezone.now()
        self.save(update_fields=list(self.VERSAND_FELDER))
        return self

    def kopie(self, benutzer) -> "Schreiben":
        """Neuer Entwurf mit Vorlage, Betreff, Empfänger, Freitext und Angaben dieses Schreibens."""
        neu = Schreiben(patient=self.patient, vorlage=self.vorlage, vorlage_name=self.vorlage_name, titel=self.titel,
                        empfaenger=self.empfaenger, text=self.text, termin=self.termin, optionen=dict(self.optionen or {}),
                        kopie_von=self.pk, erstellt_von=benutzer)
        neu._history_user = benutzer
        neu.save()
        return neu


def verlauf_beschreibung(h) -> str:
    """Kurzbeschreibung einer Fassung für den Verlauf der Akte."""
    teile = [h.titel]
    if h.empfaenger:
        teile.append(f"an {h.empfaenger}")
    if h.vorlage_name:
        teile.append(h.vorlage_name)
    if h.status == Schreiben.Status.VERSENDET and h.versendet_am:
        weg = dict(Schreiben.Versandweg.choices).get(h.versandweg, h.versandweg)
        teile.append(f"versendet am {h.versendet_am:%d.%m.%Y} ({weg})")
    return " · ".join(t for t in teile if t)
