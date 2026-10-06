from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Bericht


@admin.register(Bericht)
class BerichtAdmin(SimpleHistoryAdmin):
    list_display = ("titel", "patient", "datum", "status", "freigegeben_am")
    list_filter = ("status", "datum")
    search_fields = ("titel", "patient__nachname", "patient__vorname")
