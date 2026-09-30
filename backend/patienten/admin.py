"""Patientendaten im Django-Admin nur lesen (Bearbeitung über die Anwendung)."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Dokument, Gewichtsmessung, Kontakt, Patient, Termin


class NurLesen(SimpleHistoryAdmin):
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
