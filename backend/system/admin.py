from django.contrib import admin

from .models import Systemauftrag, Systemhinweis


@admin.register(Systemauftrag)
class SystemauftragAdmin(admin.ModelAdmin):
    list_display = ["angefordert_am", "ziel", "aktion", "status", "angefordert_von", "ergebnis"]
    list_filter = ["ziel", "status", "aktion"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Systemhinweis)
class SystemhinweisAdmin(admin.ModelAdmin):
    list_display = ["angelegt_am", "art", "text", "gueltig_bis", "beendet_am"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
