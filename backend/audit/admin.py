from django.contrib import admin

from .models import SystemEreignis


@admin.register(SystemEreignis)
class SystemEreignisAdmin(admin.ModelAdmin):
    list_display = ["zeitpunkt", "art", "benutzername", "objekt", "ip"]
    list_filter = ["art"]
    search_fields = ["benutzername", "objekt"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
