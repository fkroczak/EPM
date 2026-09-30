from django.contrib import admin

from patienten.admin import NurLesen

from .models import Infusionsplan, InfusionsplanPosition


class PositionInline(admin.TabularInline):
    model = InfusionsplanPosition
    extra = 0
    can_delete = False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Infusionsplan)
class InfusionsplanAdmin(NurLesen):
    list_display = ["patient", "status", "gueltig_ab", "kcal", "freigegeben_von", "freigegeben_am"]
    list_filter = ["status", "patient__ist_test"]
    inlines = [PositionInline]
