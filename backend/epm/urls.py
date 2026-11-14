from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts import api as konto
from audit.api import SystemEreignisViewSet, TestdatenViewSet
from system import api as system
from altimport import api as altimport
from system import sicherung_api as backup
from system import verwaltung_api as verwaltung
from infusionen.api import InfusionsplanViewSet
from vorlagen import api as vorlagen
from patienten.api import (
    BezugspersonViewSet, DiagnoseViewSet, TherapieschrittViewSet, DokumentViewSet, GewichtViewSet, KalenderViewSet, KontaktViewSet,
    MedikamentViewSet, PatientArztViewSet, PatientViewSet, StartseiteViewSet, TerminViewSet,
)
from hilfe import api as hilfe
from patienten import meine_akten
from patienten.datenschutz_api import DatenschutzanfrageViewSet, DatenschutzViewSet, ErklaerungViewSet
from stammdaten.api import (
    AnsprechpartnerViewSet, ArztViewSet, AuswahlwertViewSet, BriefkopfView, DiagnosevorlageViewSet, EinstellungenView,
    LaborparameterViewSet, LogoView, PraeparatViewSet, VersorgerViewSet,
)
from befunde.api import BiaMessungViewSet, LaborbefundViewSet
from berichte.api import BerichtViewSet
from diktate.api import DiktatViewSet
from korrespondenz.api import SchreibenViewSet
from faelle import api as faelle
from scans.api import ScanViewSet
from ki import api as ki

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
router.register("diagnosen", DiagnoseViewSet, basename="diagnose")
router.register("medikamente", MedikamentViewSet, basename="medikament")
router.register("therapieschritte", TherapieschrittViewSet, basename="therapieschritt")
router.register("laborbefunde", LaborbefundViewSet, basename="laborbefund")
router.register("bia-messungen", BiaMessungViewSet, basename="biamessung")
router.register("berichte", BerichtViewSet, basename="bericht")
router.register("diktate", DiktatViewSet, basename="diktat")
router.register("korrespondenz", SchreibenViewSet, basename="korrespondenz")
# Dokumentenautomation der RGC (26.10.2026): Fälle, Dokumente mit Fassungen, Rechnung, Leistungskatalog
router.register("faelle", faelle.FallViewSet, basename="fall")
router.register("falldokumente", faelle.FallDokumentViewSet, basename="falldokument")
router.register("rechnungspositionen", faelle.PositionViewSet, basename="rechnungsposition")
router.register("leistungen", faelle.LeistungViewSet, basename="leistung")
router.register("kostentraegertypen", faelle.KostentraegertypViewSet, basename="kostentraegertyp")
router.register("kooperationspartner", faelle.KooperationspartnerViewSet, basename="kooperationspartner")
router.register("unterzeichner", faelle.UnterzeichnerViewSet, basename="unterzeichner")
router.register("erklaerungen", ErklaerungViewSet, basename="erklaerung")
router.register("datenschutzanfragen", DatenschutzanfrageViewSet, basename="datenschutzanfrage")
router.register("datenschutz", DatenschutzViewSet, basename="datenschutz")
router.register("infusionsplaene", InfusionsplanViewSet, basename="infusionsplan")
router.register("versorger", VersorgerViewSet, basename="versorger")
router.register("ansprechpartner", AnsprechpartnerViewSet, basename="ansprechpartner")
router.register("aerzte", ArztViewSet, basename="arzt")
router.register("praeparate", PraeparatViewSet, basename="praeparat")
router.register("laborparameter", LaborparameterViewSet, basename="laborparameter")
router.register("diagnoseliste", DiagnosevorlageViewSet, basename="diagnosevorlage")
router.register("auswahlwerte", AuswahlwertViewSet, basename="auswahlwert")
router.register("benutzer", konto.BenutzerViewSet, basename="benutzer")
router.register("protokoll", SystemEreignisViewSet, basename="protokoll")
router.register("testdaten", TestdatenViewSet, basename="testdaten")
router.register("sitzungen", konto.SitzungenViewSet, basename="sitzung")
router.register("scans", ScanViewSet, basename="scan")
# KI (Experimentell, 14.10.2026)
router.register("ki/vorgaenge", ki.KiVorgangViewSet, basename="ki-vorgang")
router.register("ki/hinweise", ki.KiHinweisViewSet, basename="ki-hinweis")
router.register("ki/berichte", ki.KiBerichtViewSet, basename="ki-bericht")
router.register("ki/modelle", ki.ModelleViewSet, basename="ki-modell")
router.register("ki/vorlagen", ki.KiPromptvorlageViewSet, basename="ki-vorlage")
router.register("ki/chats", ki.KiChatViewSet, basename="ki-chat")
# Akte auf einen Blick, Nachtaufgaben (14.11.2026)
router.register("ki/zusammenfassungen", ki.KiZusammenfassungViewSet, basename="ki-zusammenfassung")
router.register("ki/aufgaben", ki.KiAufgabeViewSet, basename="ki-aufgabe")

auth = [
    path("status/", konto.StatusView.as_view()),
    path("anmelden/", konto.AnmeldenView.as_view()),
    path("2fa/", konto.ZweiterFaktorView.as_view()),
    path("kennwort/", konto.KennwortView.as_view()),
    path("2fa/einrichten/", konto.ZweiterFaktorEinrichtenView.as_view()),
    path("2fa/bestaetigen/", konto.ZweiterFaktorBestaetigenView.as_view()),
    path("2fa/ausschalten/", konto.ZweiterFaktorAusschaltenView.as_view()),
    path("abmelden/", konto.AbmeldenView.as_view()),
    path("ich/", konto.IchView.as_view()),
    path("firma/", konto.FirmaView.as_view()),
    path("notfallcodes/", konto.NotfallcodesView.as_view()),
    path("sicherheit/", konto.SicherheitView.as_view()),
    # Passkeys (Festlegung 08.10.2026)
    path("passkey/optionen/", konto.PasskeyOptionenView.as_view()),
    path("passkey/", konto.PasskeyAnmeldenView.as_view()),
    path("passkey/registrieren/", konto.PasskeyRegistrierenView.as_view()),
    path("passkeys/", konto.PasskeysView.as_view()),
    path("passkeys/<int:pk>/", konto.PasskeyView.as_view()),
    path("passkeys/<int:pk>/entfernen/", konto.PasskeyEntfernenView.as_view()),
]

urlpatterns = [
    path("api/auth/", include(auth)),
    path("api/einstellungen/", EinstellungenView.as_view()),
    path("api/rechte/", konto.RechteView.as_view()),
    path("api/briefkopf/", BriefkopfView.as_view()),
    path("api/briefkopf/logo/", LogoView.as_view()),
    path("api/anlagen/", vorlagen.AnlagenView.as_view()),
    path("api/anlagen/<int:pk>/", vorlagen.AnlageView.as_view()),
    path("api/anlagen/<int:pk>/datei/", vorlagen.AnlageDateiView.as_view()),
    path("api/vorlagen/", vorlagen.VorlagenView.as_view()),
    path("api/vorlagen/<str:art>/", vorlagen.VorlageView.as_view()),
    path("api/vorlagen/<str:art>/entwurf/", vorlagen.EntwurfView.as_view()),
    path("api/vorlagen/<str:art>/veroeffentlichen/", vorlagen.VeroeffentlichenView.as_view()),
    path("api/vorlagen/<str:art>/eigen/", vorlagen.EigenesSchreibenView.as_view()),
    path("api/schreiben/", vorlagen.SchreibenListeView.as_view()),
    path("api/vorlagen/<str:art>/entwurfsmodus/", vorlagen.EntwurfsmodusView.as_view()),
    path("api/vorlagen/<str:art>/versionen/<int:version>/", vorlagen.VersionView.as_view()),
    path("api/vorlagen/<str:art>/startvorlage/", vorlagen.StartvorlageView.as_view()),
    path("api/vorlagen/<str:art>/versionen/<int:version>/wiederherstellen/", vorlagen.WiederherstellenView.as_view()),
    path("api/vorlagen/<str:art>/duplizieren/", vorlagen.DuplizierenView.as_view()),
    path("api/vorlagen/<str:art>/firma/", vorlagen.FirmaVorlageView.as_view()),
    path("api/vorlagen/<str:art>/vorschau/", vorlagen.VorschauView.as_view()),
    # Administration › System (nur Admin)
    path("api/system/uebersicht/", system.UebersichtView.as_view()),
    path("api/system/verlauf/", system.VerlaufView.as_view()),
    path("api/system/auftraege/", system.AuftraegeView.as_view()),
    path("api/system/auftraege/<uuid:kennung>/abbrechen/", system.AuftragAbbrechenView.as_view()),
    path("api/system/epm/", system.EpmAufgabeView.as_view()),
    path("api/system/hinweis/", system.HinweisView.as_view()),
    path("api/system/einstellungen/", system.EinstellungenView.as_view()),
    path("api/system/leeren/vorbereiten/", system.LeerenVorbereitenView.as_view()),
    path("api/system/leeren/", system.LeerenView.as_view()),
    path("api/system/sitzungen/<int:pk>/", system.SitzungBeendenView.as_view()),
    # Wartung ohne SSH (F179)
    path("api/system/dienste/neustart/", verwaltung.DienstNeustartView.as_view()),
    path("api/system/versionen/zurueck/", verwaltung.ZurueckView.as_view()),
    path("api/system/pakete/erstellen/", verwaltung.PaketErstellenView.as_view()),
    path("api/system/pakete/schluessel/<str:was>/", verwaltung.PaketSchluesselView.as_view()),
    path("api/system/pakete/<str:datei>/", verwaltung.PaketDateiView.as_view()),
    path("api/system/hochladen/", verwaltung.HochladenView.as_view()),
    path("api/system/hochladen/<str:kennung>/", verwaltung.HochladenTeilView.as_view()),
    path("api/system/hochladen/<str:kennung>/einspielen/", verwaltung.EinspielenView.as_view()),
    path("api/system/zertifikat/erneuern/", verwaltung.ZertifikatErneuernView.as_view()),
    path("api/system/zertifikat/importieren/", verwaltung.ZertifikatImportierenView.as_view()),
    path("api/system/technik/", verwaltung.TechnikView.as_view()),
    path("api/system/protokolle/", verwaltung.ProtokolleView.as_view()),
    path("api/system/protokolle/<uuid:kennung>/", verwaltung.ProtokollView.as_view()),
    path("api/system/journal/aufraeumen/", verwaltung.JournalView.as_view()),
    path("api/system/images/loeschen/", verwaltung.ImagesLoeschenView.as_view()),
    path("api/system/uhr/", verwaltung.UhrView.as_view()),
    path("api/system/notfall/", verwaltung.NotfallView.as_view()),
    path("api/system/notfall/<str:datei>/", verwaltung.NotfallDateiView.as_view()),
    path("api/system/notfallplan/", verwaltung.NotfallplanView.as_view()),
    # Zugang: SSH auf Zeit, erlaubte Netze, Fail2ban (11.10.2026)
    path("api/system/zugang/ssh/oeffnen/", verwaltung.SshOeffnenView.as_view()),
    path("api/system/zugang/ssh/schliessen/", verwaltung.SshSchliessenView.as_view()),
    path("api/system/zugang/netze/", verwaltung.NetzHinzufuegenView.as_view()),
    path("api/system/zugang/netze/entfernen/", verwaltung.NetzEntfernenView.as_view()),
    path("api/system/zugang/filter/", verwaltung.HttpsFilterView.as_view()),
    path("api/system/zugang/entsperren/", verwaltung.EntsperrenView.as_view()),
    # Selbstheilung (13.10.2026)
    path("api/system/heilung/bestaetigen/", verwaltung.HeilungBestaetigenView.as_view()),
    path("api/system/heilung/schalten/", verwaltung.HeilungSchaltenView.as_view()),
    # Administration › Import: Übernahme der Altdaten (nur Admin)
    path("api/altimport/", altimport.StandView.as_view()),
    path("api/altimport/dump/", altimport.DumpView.as_view()),
    path("api/altimport/zuordnung/", altimport.ZuordnungView.as_view()),
    path("api/altimport/probelauf/", altimport.ProbelaufView.as_view()),
    path("api/altimport/import/", altimport.ImportView.as_view()),
    path("api/altimport/dokumente/", altimport.DokumenteView.as_view()),
    path("api/altimport/zuruecknehmen/", altimport.ZuruecknehmenView.as_view()),
    path("api/altimport/abschliessen/", altimport.AbschliessenView.as_view()),
    path("api/altimport/laeufe/<int:pk>/", altimport.LaufView.as_view()),
    path("api/altimport/laeufe/<int:pk>/text/", altimport.LaufView.as_view(), {"text": True}),
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
    path("api/backup/aufbewahrung/", backup.AufbewahrungView.as_view()),
    path("api/backup/loeschen/", backup.LoeschenView.as_view()),
    path("api/backup/zeitplan/", backup.ZeitplanView.as_view()),
    path("api/backup/hochladen/", backup.HochladenView.as_view()),
    path("api/backup/hochladen/<str:kennung>/", backup.HochladenTeilView.as_view()),
    path("api/backup/hochladen/<str:kennung>/einlesen/", backup.EinlesenView.as_view()),
    path("api/backup/<str:stempel>/wiederherstellen/", backup.WiederherstellenView.as_view()),
    path("api/backup/<str:stempel>/bereitstellen/", backup.BereitstellenView.as_view()),
    path("api/backup/<str:stempel>/datei/", backup.DateiView.as_view()),
    # KI (Experimentell): Stand, Einstellungen, Qualität, Evaluation
    path("api/ki/stand/", ki.StandView.as_view()),
    path("api/ki/einstellungen/", ki.EinstellungenView.as_view()),
    path("api/ki/rechtsgrundlage/", ki.RechtsgrundlageView.as_view()),
    path("api/ki/qualitaet/", ki.QualitaetView.as_view()),
    path("api/ki/evaluation/", ki.EvaluationView.as_view()),
    # KI-Einrichtung aus der Oberfläche (15.10.2026): Aufträge an den Systemagenten, Modell-Paket hochladen
    path("api/ki/einrichtung/", ki.EinrichtungView.as_view()),
    path("api/ki/hochladen/", ki.KiHochladenView.as_view()),
    path("api/ki/hochladen/<str:kennung>/", ki.KiHochladenTeilView.as_view()),
    path("api/ki/hochladen/<str:kennung>/einspielen/", ki.KiEinspielenView.as_view()),
    path("api/ki/benchmarks/", ki.BenchmarkView.as_view()),
    path("api/meine-akten/", meine_akten.MeineAktenView.as_view()),
    path("api/meine-akten/merken/", meine_akten.MerkenView.as_view()),
    path("api/meine-akten/merken/<int:patient>/", meine_akten.MerkenView.as_view()),
    path("api/meine-akten/geoeffnet/", meine_akten.GeoeffnetView.as_view()),
    path("api/hilfe/", hilfe.HilfeView.as_view()),
    path("api/hilfe/<slug:abschnitt>/ergaenzung/", hilfe.ErgaenzungView.as_view()),
    path("api/hilfe/<slug:abschnitt>/ergaenzung/versionen/", hilfe.VersionenView.as_view()),
    path("api/", include(router.urls)),
]

# Django-Admin: erreichbar nur, solange der Schalter an ist (epm.technik.TechnikMiddleware)
from django.contrib import admin  # noqa: E402
from django_otp.admin import OTPAdminSite  # noqa: E402

admin.site.__class__ = OTPAdminSite  # Django-Admin nur mit Authenticator-Code
from accounts.verwaltung import VerwaltungAnmeldung  # noqa: E402

admin.site.login_form = VerwaltungAnmeldung  # Fehlversuche zählen, auch beim Code
admin.site.site_header = "EPM Verwaltung"
admin.site.site_title = "EPM"
urlpatterns.append(path("verwaltung/", admin.site.urls))
