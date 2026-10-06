from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import BiaMessung, Laborbefund, Laborwert


class LaborwertInline(admin.TabularInline):
    model = Laborwert
    extra = 0


@admin.register(Laborbefund)
class LaborbefundAdmin(SimpleHistoryAdmin):
    list_display = ("patient", "abgenommen_am", "labor", "anzahl_werte")
    list_filter = ("abgenommen_am",)
    search_fields = ("patient__nachname", "patient__vorname", "labor")
    inlines = [LaborwertInline]


@admin.register(BiaMessung)
class BiaMessungAdmin(SimpleHistoryAdmin):
    list_display = ("patient", "gemessen_am", "gewicht_kg", "bcm_kg", "fettmasse_kg", "bmi")
    list_filter = ("gemessen_am",)
    search_fields = ("patient__nachname", "patient__vorname")
