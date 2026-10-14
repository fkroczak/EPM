from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Schreiben


@admin.register(Schreiben)
class SchreibenAdmin(SimpleHistoryAdmin):
    list_display = ("titel", "patient", "vorlage_name", "status", "erstellt_am", "freigegeben_am", "versendet_am")
    list_filter = ("status", "versandweg")
    search_fields = ("titel", "empfaenger", "patient__nachname", "patient__vorname")
