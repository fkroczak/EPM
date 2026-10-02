from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts import api as konto
from audit.api import SystemEreignisViewSet, TestdatenViewSet
from system import api as system
from system import sicherung_api as backup
from infusionen.api import InfusionsplanViewSet
from vorlagen import api as vorlagen
from patienten.api import (
    BezugspersonViewSet, DokumentViewSet, GewichtViewSet, KalenderViewSet, KontaktViewSet, PatientArztViewSet,
    PatientViewSet, StartseiteViewSet, TerminViewSet,
)
from patienten.datenschutz_api import DatenschutzanfrageViewSet, DatenschutzViewSet, ErklaerungViewSet
from stammdaten.api import (
    AnsprechpartnerViewSet, ArztViewSet, AuswahlwertViewSet, BriefkopfView, EinstellungenView, LogoView, PraeparatViewSet,
    VersorgerViewSet,
)

router = DefaultRouter()
router.register("startseite", StartseiteViewSet, basename="startseite")
router.register("patienten", PatientViewSet, basename="patient")
router.register("gewichte", GewichtViewSet, basename="gewicht")
router.register("kontakte", KontaktViewSet, basename="kontakt")
router.register("termine", TerminViewSet, basename="termin")
router.register("kalender", KalenderViewSet, basename="kalender")
router.register("dokumente", DokumentViewSet, basename="dokument")
router.register("bezugspersonen", BezugspersonViewSet, basename="bezugsperson")
router.register("patient-aerzte", PatientArztViewSet, basename="patientarzt")
router.register("erklaerungen", ErklaerungViewSet, basename="erklaerung")
router.register("datenschutzanfragen", DatenschutzanfrageViewSet, basename="datenschutzanfrage")
router.register("datenschutz", DatenschutzViewSet, basename="datenschutz")
router.register("infusionsplaene", InfusionsplanViewSet, basename="infusionsplan")
router.register("versorger", VersorgerViewSet, basename="versorger")
router.register("ansprechpartner", AnsprechpartnerViewSet, basename="ansprechpartner")
router.register("aerzte", ArztViewSet, basename="arzt")
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
    path("api/vorlagen/", vorlagen.VorlagenView.as_view()),
    path("api/vorlagen/<str:art>/", vorlagen.VorlageView.as_view()),
    path("api/vorlagen/<str:art>/entwurf/", vorlagen.EntwurfView.as_view()),
    path("api/vorlagen/<str:art>/veroeffentlichen/", vorlagen.VeroeffentlichenView.as_view()),
    path("api/vorlagen/<str:art>/versionen/<int:version>/", vorlagen.VersionView.as_view()),
    path("api/vorlagen/<str:art>/startvorlage/", vorlagen.StartvorlageView.as_view()),
    path("api/vorlagen/<str:art>/vorschau/", vorlagen.VorschauView.as_view()),
    # Administration › System (nur Admin)
    path("api/system/uebersicht/", system.UebersichtView.as_view()),
    path("api/system/verlauf/", system.VerlaufView.as_view()),
    path("api/system/auftraege/", system.AuftraegeView.as_view()),
    path("api/system/auftraege/<uuid:kennung>/abbrechen/", system.AuftragAbbrechenView.as_view()),
    path("api/system/epm/", system.EpmAufgabeView.as_view()),
    path("api/system/hinweis/", system.HinweisView.as_view()),
    path("api/system/sitzungen/<int:pk>/", system.SitzungBeendenView.as_view()),
    # Administration › Backup (Recht „Sicherungen verwalten“)
    path("api/backup/", backup.UebersichtView.as_view()),
    path("api/backup/jetzt/", backup.JetztView.as_view()),
    path("api/backup/passwort/", backup.PasswortView.as_view()),
    path("api/backup/passwort/pruefen/", backup.PasswortPruefenView.as_view()),
    path("api/backup/passwortblatt/", backup.PasswortblattView.as_view()),
    path("api/backup/ziel/", backup.ZielView.as_view()),
    path("api/backup/ziel/entfernen/", backup.ZielEntfernenView.as_view()),
    path("api/backup/ziel/testen/", backup.ZielTestenView.as_view()),
    path("api/backup/uebertragen/", backup.UebertragenView.as_view()),
    path("api/backup/auftraege/<uuid:kennung>/abbrechen/", backup.AuftragAbbrechenView.as_view()),
    path("api/backup/<str:stempel>/wiederherstellen/", backup.WiederherstellenView.as_view()),
    path("api/", include(router.urls)),
]

if settings.EPM_DJANGO_ADMIN:
    from django.contrib import admin
    from django_otp.admin import OTPAdminSite

    admin.site.__class__ = OTPAdminSite  # Django-Admin nur mit Authenticator-Code
    admin.site.site_header = "EPM Verwaltung"
    admin.site.site_title = "EPM"
    urlpatterns.append(path("verwaltung/", admin.site.urls))
