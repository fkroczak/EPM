"""Patientendaten im Django-Admin nur lesen (Bearbeitung über die Anwendung)."""
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from simple_history.admin import SimpleHistoryAdmin

from .models import Bezugsperson, Dokument, Gewichtsmessung, Kontakt, Patient, PatientArzt, Termin


class NurLesen(SimpleHistoryAdmin):
    #: Weg vom Modell zur Akte ("" = die Akte selbst)
    akte = "patient__"

    def get_queryset(self, request):
        # Akten mit eingeschränkter Verarbeitung (Art. 18 DSGVO) erscheinen hier nicht, auch nicht mit ihren
        # Einträgen: Einsicht gibt es nur in EPM, mit Grund und Eintrag im Audit-Log.
        return super().get_queryset(request).filter(**{f"{self.akte}eingeschraenkt_am__isnull": True})

    def has_view_permission(self, request, obj=None):
        # gilt auch für die Historien-Ansicht, die ein Objekt notfalls aus der Historie holt
        try:
            akte = obj if isinstance(obj, Patient) else getattr(obj, "patient", None)
        except ObjectDoesNotExist:
            akte = None
        if akte is not None and akte.eingeschraenkt_am:
            return False
        return super().has_view_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class GewichtInline(admin.TabularInline):
    model = Gewichtsmessung
    fields = ["gemessen_am", "gewicht_kg", "quelle", "erfasst_von"]
    extra = 0
    can_delete = False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Patient)
class PatientAdmin(NurLesen):
    akte = ""
    list_display = ["nummer", "nachname", "vorname", "geburtsdatum", "versorger", "abgeschlossen_am", "ist_test"]
    list_filter = ["ist_test", "versorger", ("abgeschlossen_am", admin.EmptyFieldListFilter)]
    search_fields = ["nachname", "vorname"]
    inlines = [GewichtInline]


@admin.register(Kontakt)
class KontaktAdmin(NurLesen):
    list_display = ["patient", "zeitpunkt", "art", "erfasst_von", "storniert_am"]
    list_filter = ["patient__ist_test"]


@admin.register(Termin)
class TerminAdmin(NurLesen):
    list_display = ["patient", "art", "faellig_am", "titel", "erledigt_am"]
    list_filter = ["art", "patient__ist_test"]


@admin.register(Dokument)
class DokumentAdmin(NurLesen):
    list_display = ["patient", "titel", "typ", "datum", "groesse"]


@admin.register(Gewichtsmessung)
class GewichtAdmin(NurLesen):
    list_display = ["patient", "gemessen_am", "gewicht_kg", "quelle"]


@admin.register(Bezugsperson)
class BezugspersonAdmin(NurLesen):
    list_display = ["patient", "beziehung", "name", "telefon", "auskunft_erlaubt", "aktiv"]
    list_filter = ["aktiv", "auskunft_erlaubt", "patient__ist_test"]


@admin.register(PatientArzt)
class PatientArztAdmin(NurLesen):
    list_display = ["patient", "rolle", "arzt", "aktiv"]
    list_filter = ["rolle", "aktiv", "patient__ist_test"]
