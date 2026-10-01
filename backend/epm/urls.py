from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts import api as konto
from audit.api import SystemEreignisViewSet, TestdatenViewSet
from infusionen.api import InfusionsplanViewSet
from patienten.api import (
    DokumentViewSet, GewichtViewSet, KontaktViewSet, PatientViewSet, StartseiteViewSet, TerminViewSet,
)
from stammdaten.api import (
    AnsprechpartnerViewSet, AuswahlwertViewSet, BriefkopfView, EinstellungenView, LogoView, PraeparatViewSet,
    VersorgerViewSet,
)

router = DefaultRouter()
router.register("startseite", StartseiteViewSet, basename="startseite")
router.register("patienten", PatientViewSet, basename="patient")
router.register("gewichte", GewichtViewSet, basename="gewicht")
router.register("kontakte", KontaktViewSet, basename="kontakt")
router.register("termine", TerminViewSet, basename="termin")
router.register("dokumente", DokumentViewSet, basename="dokument")
router.register("infusionsplaene", InfusionsplanViewSet, basename="infusionsplan")
router.register("versorger", VersorgerViewSet, basename="versorger")
router.register("ansprechpartner", AnsprechpartnerViewSet, basename="ansprechpartner")
router.register("praeparate", PraeparatViewSet, basename="praeparat")
router.register("auswahlwerte", AuswahlwertViewSet, basename="auswahlwert")
router.register("benutzer", konto.BenutzerViewSet, basename="benutzer")
router.register("protokoll", SystemEreignisViewSet, basename="protokoll")
router.register("testdaten", TestdatenViewSet, basename="testdaten")
router.register("sitzungen", konto.SitzungenViewSet, basename="sitzung")

auth = [
    path("status/", konto.StatusView.as_view()),
    path("anmelden/", konto.AnmeldenView.as_view()),
    path("2fa/", konto.ZweiterFaktorView.as_view()),
    path("kennwort/", konto.KennwortView.as_view()),
    path("2fa/einrichten/", konto.ZweiterFaktorEinrichtenView.as_view()),
    path("2fa/bestaetigen/", konto.ZweiterFaktorBestaetigenView.as_view()),
    path("abmelden/", konto.AbmeldenView.as_view()),
    path("ich/", konto.IchView.as_view()),
    path("notfallcodes/", konto.NotfallcodesView.as_view()),
    path("sicherheit/", konto.SicherheitView.as_view()),
]

urlpatterns = [
    path("api/auth/", include(auth)),
    path("api/einstellungen/", EinstellungenView.as_view()),
    path("api/rechte/", konto.RechteView.as_view()),
    path("api/briefkopf/", BriefkopfView.as_view()),
    path("api/briefkopf/logo/", LogoView.as_view()),
    path("api/", include(router.urls)),
]

if settings.EPM_DJANGO_ADMIN:
    from django.contrib import admin
    from django_otp.admin import OTPAdminSite

    admin.site.__class__ = OTPAdminSite  # Django-Admin nur mit Authenticator-Code
    admin.site.site_header = "EPM Verwaltung"
    admin.site.site_title = "EPM"
    urlpatterns.append(path("verwaltung/", admin.site.urls))
