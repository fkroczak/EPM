from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class BenutzerAdmin(UserAdmin):
    list_display = ["username", "anzeigename", "kuerzel", "rolle", "ist_test", "is_active", "last_login"]
    list_filter = ["rolle", "is_active", "ist_test"]
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Person", {"fields": ("titel", "first_name", "last_name", "kuerzel", "funktion", "email")}),
        ("Zugang", {"fields": ("rolle", "ist_test", "is_active", "muss_kennwort_aendern", "nur_historisch")}),
        ("Zeiten", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"fields": ("username", "password1", "password2", "rolle", "first_name", "last_name")}),
    )
    readonly_fields = ["last_login", "date_joined"]

    def has_delete_permission(self, request, obj=None):
        return False
