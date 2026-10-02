from django.contrib import admin

from .models import SystemEreignis


@admin.register(SystemEreignis)
class SystemEreignisAdmin(admin.ModelAdmin):
    list_display = ["zeitpunkt", "art", "benutzername", "objekt", "ip"]
    list_filter = ["art"]
    search_fields = ["benutzername", "objekt"]

    def get_queryset(self, request):
        # Einträge zu Akten mit eingeschränkter Verarbeitung (Art. 18 DSGVO) erscheinen hier nicht – das Audit-Log in
        # EPM zeigt sie Personen ohne Einsichtsrecht ohne Namen (audit/api.py).
        from patienten.models import Patient

        from .bereinigung import akte_bedingung

        qs = super().get_queryset(request)
        for pid, nummer in Patient.objects.filter(eingeschraenkt_am__isnull=False).values_list("id", "nummer"):
            qs = qs.exclude(id__in=SystemEreignis.objects.filter(akte_bedingung(pid, nummer)).values("id"))
        return qs

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
