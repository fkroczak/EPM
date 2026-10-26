from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Behandlungsfall, FallDokument, Kooperationspartner, Kostentraegertyp, Leistung, Unterzeichner


@admin.register(Behandlungsfall)
class FallAdmin(SimpleHistoryAdmin):
    list_display = ("nummer", "patient", "kostentraegertyp", "status", "erstellt_am")
    list_filter = ("status", "kostentraegertyp")


@admin.register(FallDokument)
class FallDokumentAdmin(SimpleHistoryAdmin):
    list_display = ("titel", "fall", "art", "status", "rechnungsnummer", "final_am")
    list_filter = ("status", "art")


for modell in (Kostentraegertyp, Kooperationspartner, Unterzeichner, Leistung):
    admin.site.register(modell, SimpleHistoryAdmin)
