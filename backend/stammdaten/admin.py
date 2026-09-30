from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Ansprechpartner, Auswahlwert, Einstellungen, Praeparat, Versorger


class OhneLoeschen(SimpleHistoryAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


class AnsprechpartnerInline(admin.TabularInline):
    model = Ansprechpartner
    extra = 0
    can_delete = False


@admin.register(Versorger)
class VersorgerAdmin(OhneLoeschen):
    list_display = ["name", "ort", "telefon", "aktiv"]
    list_filter = ["aktiv"]
    search_fields = ["name", "ort"]
    inlines = [AnsprechpartnerInline]


@admin.register(Auswahlwert)
class AuswahlwertAdmin(OhneLoeschen):
    list_display = ["liste", "wert", "reihenfolge", "aktiv"]
    list_filter = ["liste", "aktiv"]
    list_editable = ["reihenfolge", "aktiv"]


@admin.register(Praeparat)
class PraeparatAdmin(OhneLoeschen):
    list_display = ["name", "konzentration", "kategorie", "einheit", "aktiv"]
    list_filter = ["kategorie", "aktiv"]
    search_fields = ["name"]


@admin.register(Einstellungen)
class EinstellungenAdmin(OhneLoeschen):
    def has_add_permission(self, request):
        return not Einstellungen.objects.exists()
