"""
Datenschutz in der Akte (DSGVO): Aufbewahrung, Einschränkung der Verarbeitung, Einsicht, Kopie der Akte,
endgültiges Löschen.

Grundlagen (im Einzelnen: docs/DATENSCHUTZ.md):
- Recht auf Löschung und seine Ausnahmen: Art. 17 DSGVO, insbesondere Abs. 3 Buchst. b und e.
- Einschränkung statt Löschung, solange aufbewahrt werden muss: Art. 18 DSGVO, § 35 Abs. 3 BDSG.
- Kopie der Daten: Art. 15 Abs. 3 DSGVO (für Behandelnde zusätzlich § 630g BGB).
- Fristen für Anfragen: Art. 12 Abs. 3 DSGVO.

Dieses Modul enthält die Regeln und die Aktionen an der Akte (``/api/patienten/{id}/…``). Die Listen für
Erklärungen und Anfragen stehen in ``datenschutz_api.py``.
"""
import logging
import shutil
import tempfile
import zipfile
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from accounts.models import Rolle
from accounts.permissions import AkteLoeschenRecht, DatenschutzEntscheidenRecht, recht
from audit.bereinigung import OHNE_GRUND, akte_entfernen as protokoll_entfernen, akte_text
from audit.models import SystemEreignis, protokolliere
from audit.schutz import wartungsmodus
from epm.api_basis import (benutzername, darf_einsicht, patienten_fuer, patienten_mit_eingeschraenkten,
                           pruefe_schreibbereich)
from stammdaten.models import Einstellungen

from .loeschung import trage_ein
from .models import (Akteneinsicht, Bezugsperson, Datenschutzanfrage, Dokument, DokumentVorgang, Erklaerung,
                     Gewichtsmessung, Kontakt, Loeschprotokoll, Patient, PatientArzt, Termin, erklaerungen_stand)

log = logging.getLogger(__name__)
EINSICHT_MINUTEN = 60
KopieRecht = recht("datenschutz_bearbeiten", lesen="datenschutz_bearbeiten")


# ================================================================= Regeln
def loeschbar(patient) -> dict:
    """Darf die Akte endgültig gelöscht werden – und auf welcher Grundlage?

    Nur abgeschlossene Akten. Entweder ist die Aufbewahrungsfrist abgelaufen (``frist``), oder es liegt ein offener
    Antrag auf Löschung vor (``antrag``). Läuft die Frist noch, entscheidet der Mediziner, ob eine
    Aufbewahrungspflicht entgegensteht (Art. 17 Abs. 3 DSGVO); dann wird eingeschränkt statt gelöscht."""
    a = patient.aufbewahrung()
    antrag = patient.datenschutzanfragen.filter(art=Datenschutzanfrage.Art.LOESCHUNG, erledigt_am__isnull=True) \
        .order_by("eingegangen_am", "id").first()
    ergebnis = {"moeglich": False, "rechtsgrund": None, "hinweis": "", "frist_laeuft_bis": None,
                "antrag": antrag.id if antrag else None, "antrag_vom": antrag.eingegangen_am if antrag else None}
    if not patient.ist_abgeschlossen:
        ergebnis["hinweis"] = "Nur abgeschlossene Akten können gelöscht werden. Bitte die Akte zuerst abschließen."
        return ergebnis
    if a["abgelaufen"]:
        return {**ergebnis, "moeglich": True, "rechtsgrund": Loeschprotokoll.Rechtsgrund.FRIST,
                "hinweis": f"Die Aufbewahrungsfrist ist am {a['bis']:%d.%m.%Y} abgelaufen."}
    if antrag is not None:
        return {**ergebnis, "moeglich": True, "rechtsgrund": Loeschprotokoll.Rechtsgrund.ANTRAG,
                "frist_laeuft_bis": a["bis"],
                "hinweis": (f"Antrag auf Löschung vom {antrag.eingegangen_am:%d.%m.%Y}. Die Aufbewahrungsfrist läuft noch "
                            f"bis {a['bis']:%d.%m.%Y}: Löschen nur, wenn keine Aufbewahrungspflicht entgegensteht "
                            f"(Art. 17 Abs. 3 DSGVO) – sonst die Verarbeitung einschränken.")}
    ergebnis["frist_laeuft_bis"] = a["bis"]
    ergebnis["hinweis"] = (f"Die Aufbewahrungsfrist läuft bis {a['bis']:%d.%m.%Y}. Vorher wird nur auf Antrag der "
                           f"betroffenen Person gelöscht (als Datenschutz-Anfrage „Löschung“ erfassen).")
    return ergebnis


def umfang(patient) -> dict:
    """Was mit der Akte gelöscht wird – nur Anzahlen, keine Inhalte (für das Löschprotokoll)."""
    dokumente = list(patient.dokumente.values_list("groesse", flat=True))
    return {
        "kontakte": patient.kontakte.count(), "gewichte": patient.gewichte.count(),
        "termine": patient.termine.count(), "dokumente": len(dokumente), "dateien_bytes": sum(dokumente),
        "infusionsplaene": patient.infusionsplaene.count(), "bezugspersonen": patient.bezugspersonen.count(),
        "aerzte": patient.aerzte.count(), "erklaerungen": patient.erklaerungen.count(),
        "anfragen": patient.datenschutzanfragen.count(),
    }


def eigene_dokumente(ids) -> set[int]:
    """Nummern der Dokumente, die mit diesen Akten enden: die jetzt darin liegen und die, die darin endgültig
    gelöscht wurden. Dokumente, die einer anderen Akte zugeordnet wurden, gehören nicht dazu – sie leben dort weiter."""
    eigene = set(Dokument.objects.filter(patient_id__in=ids).values_list("id", flat=True))
    eigene |= set(DokumentVorgang.objects.filter(von_patient_id__in=ids, art=DokumentVorgang.Art.GELOESCHT)
                  .values_list("dokument_id", flat=True))
    return eigene


def akten_entfernen(ids: list[int]) -> None:
    """Akten mit allen Einträgen und der gesamten Historie aus der Datenbank entfernen.

    Nur im Wartungsmodus aufrufen (die Trigger verhindern sonst jedes Löschen). Gemeinsame Grundlage für das
    endgültige Löschen einer Akte und das Zurücksetzen der Testdaten. Die Dateien entfernt der Aufrufer."""
    from django.apps import apps

    from infusionen.models import Infusionsplan, InfusionsplanPosition

    ids = list(ids)
    eigene = eigene_dokumente(ids)
    plan_ids = set(Infusionsplan.objects.filter(patient_id__in=ids).values_list("id", flat=True))
    plan_ids |= set(Infusionsplan.history.filter(patient_id__in=ids).values_list("id", flat=True))
    # Dokument-Vorgänge: gelöschte Dokumente der Akte entfallen; bei Dokumenten, die zwischen dieser und einer
    # anderen Akte gewechselt haben, bleibt der Vorgang für die andere Akte – ohne Verweis und ohne Freitext
    DokumentVorgang.objects.filter(von_patient_id__in=ids, art=DokumentVorgang.Art.GELOESCHT).delete()
    DokumentVorgang.objects.filter(von_patient_id__in=ids).update(von_patient=None, grund=OHNE_GRUND)
    DokumentVorgang.objects.filter(nach_patient_id__in=ids).update(nach_patient=None, grund=OHNE_GRUND)
    DokumentVorgang.objects.filter(von_patient__isnull=True, nach_patient__isnull=True).delete()
    # Positionen und Pläne zuerst (Vorgänger- und Nachweis-Verweise), dann die Akten mit allem, was daran hängt
    InfusionsplanPosition.objects.filter(plan_id__in=plan_ids).delete()
    Infusionsplan.objects.filter(id__in=plan_ids).update(vorgaenger=None, freigabe_nachweis=None)
    Infusionsplan.objects.filter(id__in=plan_ids).delete()
    Patient.objects.filter(id__in=ids).delete()
    # Historie. Dokumente dieser Akten verlieren ALLE früheren Fassungen – auch die aus der Zeit, in der sie
    # (falsch zugeordnet) in einer anderen Akte lagen; dort bleibt nur der neutrale Vorgang. Dokumente, die
    # inzwischen in einer anderen Akte liegen, behalten ihre früheren Fassungen (sie gehören zu jenem Dokument;
    # die andere Akte zeigt sie als „von einer anderen Akte übernommen“).
    Patient.history.filter(id__in=ids).delete()
    Dokument.history.filter(id__in=eigene).delete()
    frueher = Dokument.history.filter(patient_id__in=ids)
    bleibt = set(Dokument.objects.filter(id__in=frueher.values("id")).values_list("id", flat=True))
    frueher.exclude(id__in=bleibt).delete()
    for modell in (Gewichtsmessung, Kontakt, Termin, Infusionsplan, Bezugsperson, PatientArzt, Erklaerung,
                   Datenschutzanfrage):
        modell.history.filter(patient_id__in=ids).delete()
    InfusionsplanPosition.history.filter(plan_id__in=plan_ids).delete()
    # Historie der Vitamin-Zuordnung (eigene Tabelle von django-simple-history, ohne Fremdschlüssel in der Datenbank)
    apps.get_model("infusionen", "HistoricalInfusionsplan_vitamine").objects.filter(infusionsplan_id__in=plan_ids).delete()


def dateien_entfernen(nummer: int) -> None:
    shutil.rmtree(settings.EPM_DOKUMENTE / str(nummer), ignore_errors=True)


def akte_loeschen(patient, benutzer, rechtsgrund: str, grund: str, request=None, nachgezogen: bool = False,
                  eintrag: Loeschprotokoll | None = None) -> Loeschprotokoll:
    """Akte endgültig löschen: Löschprotokoll (ohne Namen), Datenbank, Historie, Audit-Log (Namen entfernt), Dateien.

    Die Löschung kommt außerdem in die Löschliste, damit eine Wiederherstellung aus einer älteren Sicherung die Akte
    nicht zurückbringt. ``eintrag``/``nachgezogen``: beim erneuten Löschen nach einer Wiederherstellung."""
    pid, nummer = patient.id, patient.nummer
    a = patient.aufbewahrung()
    eigene = eigene_dokumente([pid])
    antrag = patient.datenschutzanfragen.filter(art=Datenschutzanfrage.Art.LOESCHUNG, erledigt_am__isnull=True) \
        .order_by("eingegangen_am", "id").first()
    with wartungsmodus():
        zahlen = umfang(patient)
        if antrag is not None:
            zahlen["antrag_eingegangen_am"] = antrag.eingegangen_am.isoformat()
        if eintrag is None:
            eintrag = Loeschprotokoll.objects.create(
                akte_id=pid, nummer=nummer, ist_test=patient.ist_test, angelegt_am=patient.angelegt_am,
                abgeschlossen_am=patient.abgeschlossen_am,
                aufbewahrung_bis=a["bis"], rechtsgrund=rechtsgrund, grund=grund, umfang=zahlen, geloescht_von=benutzer)
        akten_entfernen([pid])
        bereinigt = protokoll_entfernen(pid, nummer, sorted(eigene), namen=(patient.nachname, patient.vorname))
        protokolliere(SystemEreignis.Art.AKTE_GELOESCHT, request, benutzer=benutzer, objekt=f"Akte Nr. {nummer}",
                      akte_id=pid, rechtsgrund=rechtsgrund, grund=grund, umfang=zahlen, protokolleintraege=bereinigt,
                      **({"nachgezogen": True} if nachgezogen else {}))
        if not nachgezogen:
            zeile = _listen_eintrag(eintrag)
            transaction.on_commit(lambda: trage_ein(zeile), robust=True)
        transaction.on_commit(lambda: dateien_entfernen(nummer), robust=True)
    return eintrag


# ================================================================= Kopie der Akte
def _dateiname(text: str) -> str:
    sauber = "".join(c if c.isalnum() or c in "._- " else "_" for c in text).strip(" .")
    return sauber[:120] or "Datei"


def aktenkopie(patient, ziel) -> dict:
    """Schreibt die vollständige Kopie der Akte als ZIP nach ``ziel`` (Datei-Objekt):

    die Akte als PDF (alle Einträge), der Verlauf als PDF (wer wann was geändert hat), alle Dokumente im Original.
    Fehlt eine Datei im Dokumentenverzeichnis, steht das in ``LIESMICH.txt`` (die Kopie bleibt ehrlich)."""
    from vorlagen.listen import aktenkopie_pdf, verlauf_pdf

    from .api import verlauf_eintraege

    fehlend, anzahl = [], 0
    stand = timezone.localdate()
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"Akte-{patient.nummer}.pdf", aktenkopie_pdf(patient))
        z.writestr(f"Verlauf-{patient.nummer}.pdf", verlauf_pdf(patient, verlauf_eintraege(patient, grenze=5000)))
        for d in patient.dokumente.order_by("datum", "id"):
            name = f"Dokumente/{d.id}-{_dateiname(d.originalname or d.titel)}"
            if d.pfad.is_file():
                z.write(d.pfad, name)
                anzahl += 1
            else:
                fehlend.append(f"{d.titel} ({d.originalname})")
        zeilen = [
            f"Kopie der Akte Nr. {patient.nummer} – Stand {stand:%d.%m.%Y}",
            "",
            f"Akte-{patient.nummer}.pdf      alle Angaben und Einträge der Akte",
            f"Verlauf-{patient.nummer}.pdf   wer wann was eingetragen oder geändert hat",
            f"Dokumente/            {anzahl} Dokumente im Original",
        ]
        if fehlend:
            zeilen += ["", "Diese Dokumente sind in der Akte verzeichnet, die Datei fehlt aber:", *[f"- {f}" for f in fehlend]]
        z.writestr("LIESMICH.txt", "\r\n".join(zeilen) + "\r\n")
    return {"dokumente": anzahl, "fehlend": len(fehlend)}


# ================================================================= Daten für den Reiter „Datenschutz“
def einschraenkung_daten(patient):
    if not patient.ist_eingeschraenkt:
        return None
    return {"am": patient.eingeschraenkt_am, "von": benutzername(patient.eingeschraenkt_von),
            "grund": patient.einschraenkung_grund}


def stand_daten(patient) -> dict:
    """Je Art der Erklärung: „nicht_erfasst“, „liegt_vor“ oder „widerrufen“ – nachgehalten wie die Nickelallergie."""
    vorhanden = erklaerungen_stand([patient.id]).get(patient.id, {})
    return {art: vorhanden.get(art, {"status": "nicht_erfasst", "am": None, "id": None}) for art in Erklaerung.Art.values}


def kopien(patient) -> list:
    """Bisher erstellte Kopien der Akte (aus dem Audit-Log)."""
    qs = SystemEreignis.objects.filter(art=SystemEreignis.Art.EXPORT, details__patient_id=patient.id,
                                       details__was="Kopie der Akte").select_related("benutzer")
    return [{"zeitpunkt": e.zeitpunkt, "person": benutzername(e.benutzer) or e.benutzername} for e in qs[:20]]


# ================================================================= Aktionen an der Akte
class DatenschutzAktionen:
    """Aktionen für ``PatientViewSet``. Vorgänge, die auch bei eingeschränkten Akten möglich sein müssen
    (Einsicht nehmen, Einschränkung aufheben, löschen), holen die Akte über ``_akte`` statt ``get_object``."""

    LOESCHCODE = "epm_akte_loeschcode"
    LOESCH_MINUTEN = 5

    def _akte(self, pk, schreiben=True, loeschen=False):
        """Akte für einen Datenschutz-Vorgang – auch eine eingeschränkte, wenn die Person Einsicht nehmen dürfte."""
        patient = get_object_or_404(patienten_mit_eingeschraenkten(self.request.user), pk=pk)
        if schreiben:
            pruefe_schreibbereich(self.request.user, patient, loeschen=loeschen)
        return patient

    def _verschlossen(self, patient):
        """Antwort für eine eingeschränkte Akte ohne laufende Einsicht: nur Nummer und Zeitpunkt, kein Name."""
        return Response({
            "fehler": "Die Verarbeitung dieser Akte ist eingeschränkt (Art. 18 DSGVO). Sie ist nur mit einer "
                      "begründeten Einsicht lesbar.",
            "eingeschraenkt": True, "id": patient.id, "nummer": patient.nummer,
            "eingeschraenkt_am": patient.eingeschraenkt_am, "darf_einsicht": darf_einsicht(self.request.user, patient),
        }, status=status.HTTP_403_FORBIDDEN)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Http404:
            pk = str(kwargs.get("pk", ""))
            p = patienten_fuer(request.user, eingeschraenkte=True).filter(pk=pk).first() if pk.isdigit() else None
            if p is None or not p.ist_eingeschraenkt:
                raise
            return self._verschlossen(p)

    @action(detail=True, methods=["get"])
    def datenschutz(self, request, pk=None):
        """Stand für den Reiter „Datenschutz“: Aufbewahrung, Einschränkung, Erklärungen, Anfragen, Kopien, Löschen."""
        from vorlagen.models import Dokumentvorlage

        from .datenschutz_api import DatenschutzanfrageSerializer, ErklaerungSerializer

        patient = self._akte(pk, schreiben=False)
        einsicht = Akteneinsicht.objects.filter(patient=patient, benutzer=request.user, bis__gt=timezone.now()) \
            .order_by("-bis").first()
        if patient.ist_eingeschraenkt and einsicht is None:
            return self._verschlossen(patient)  # auch Erklärungen und Anfragen sind Inhalt der Akte
        vorlagen = {}
        for art in Erklaerung.Art.values:
            v = Dokumentvorlage.aktive(art)
            vorlagen[art] = {"version": v.version, "entwurf": v.im_entwurfsmodus}
        kontext = self.get_serializer_context()
        return Response({
            "aufbewahrung": patient.aufbewahrung(),
            "einschraenkung": einschraenkung_daten(patient),
            "einsicht_bis": einsicht.bis if einsicht else None,
            "erklaerungen": ErklaerungSerializer(
                patient.erklaerungen.select_related("dokument", "erfasst_von").order_by("-erteilt_am", "-id"),
                many=True, context=kontext).data,
            "stand": stand_daten(patient),
            "pflicht": Einstellungen.aktuell().pflicht_erklaerungen,
            "vorlagen": vorlagen,
            "anfragen": DatenschutzanfrageSerializer(
                patient.datenschutzanfragen.select_related("patient", "erfasst_von", "erledigt_von"),
                many=True, context=kontext).data,
            "kopien": kopien(patient),
            "loeschen": loeschbar(patient),
        })

    # ------------------------------------------------ Einschränkung der Verarbeitung (Art. 18 DSGVO)
    @action(detail=True, methods=["post"], permission_classes=[DatenschutzEntscheidenRecht])
    def einschraenken(self, request, pk=None):
        """Verarbeitung einschränken: Die Akte bleibt gespeichert, erscheint aber nirgends mehr und ist nur mit
        begründeter Einsicht lesbar. Nur abgeschlossene Akten. ``{"grund": "…"}``"""
        patient = self._akte(pk)
        grund = str(request.data.get("grund", "")).strip()
        if len(grund) < 10:
            return Response({"grund": "Bitte den Grund angeben (mindestens 10 Zeichen)."}, status=status.HTTP_400_BAD_REQUEST)
        einschraenken(patient, request.user, grund, request)
        return Response({"eingeschraenkt": True, "einschraenkung": einschraenkung_daten(patient)})

    @action(detail=True, methods=["post"], url_path="einschraenkung-aufheben", permission_classes=[DatenschutzEntscheidenRecht])
    def einschraenkung_aufheben(self, request, pk=None):
        """Einschränkung aufheben. Vorher ist die betroffene Person zu unterrichten (Art. 18 Abs. 3 DSGVO):
        ``{"grund", "unterrichtet_am"}`` oder – wenn eine Unterrichtung nicht möglich oder nicht nötig ist –
        ``{"grund", "unterrichtung_entfaellt": "Begründung"}``."""
        patient = self._akte(pk)
        if not patient.ist_eingeschraenkt:
            return Response({"fehler": "Die Verarbeitung dieser Akte ist nicht eingeschränkt."}, status=status.HTTP_400_BAD_REQUEST)
        grund = str(request.data.get("grund", "")).strip()
        entfaellt = str(request.data.get("unterrichtung_entfaellt", "")).strip()
        fehler, unterrichtet = {}, None
        if len(grund) < 10:
            fehler["grund"] = "Bitte den Grund angeben (mindestens 10 Zeichen)."
        if request.data.get("unterrichtet_am"):
            try:
                unterrichtet = serializers.DateField().to_internal_value(request.data["unterrichtet_am"])
            except serializers.ValidationError as f:
                fehler["unterrichtet_am"] = f.detail
            else:
                if unterrichtet > timezone.localdate():
                    fehler["unterrichtet_am"] = "Das Datum liegt in der Zukunft."
        elif len(entfaellt) < 10:
            fehler["unterrichtet_am"] = ("Vor dem Aufheben wird die betroffene Person unterrichtet (Art. 18 Abs. 3 DSGVO). "
                                         "Bitte das Datum angeben – oder begründen, warum die Unterrichtung entfällt.")
        if fehler:
            return Response(fehler, status=status.HTTP_400_BAD_REQUEST)
        patient.eingeschraenkt_am = None
        patient.eingeschraenkt_von = None
        patient.einschraenkung_grund = ""
        patient._history_user = request.user
        patient._change_reason = f"Einschränkung aufgehoben: {grund}"[:100]
        patient.save()
        Akteneinsicht.objects.filter(patient=patient, bis__gt=timezone.now()).update(bis=timezone.now())
        protokolliere(SystemEreignis.Art.AKTE_EINSCHRAENKUNG_AUFGEHOBEN, request, objekt=akte_text(patient),
                      patient_id=patient.id, grund=grund,
                      unterrichtet_am=unterrichtet.isoformat() if unterrichtet else None, unterrichtung_entfaellt=entfaellt)
        return Response({"eingeschraenkt": False})

    @action(detail=True, methods=["post"], permission_classes=[DatenschutzEntscheidenRecht])
    def einsicht(self, request, pk=None):
        """Begründete Einsicht in eine eingeschränkte Akte: gilt für diese Person und 60 Minuten, steht mit Grund im
        Audit-Log. ``{"grund": "…"}``"""
        patient = self._akte(pk)
        if not patient.ist_eingeschraenkt:
            return Response({"fehler": "Die Verarbeitung dieser Akte ist nicht eingeschränkt."}, status=status.HTTP_400_BAD_REQUEST)
        grund = str(request.data.get("grund", "")).strip()
        if len(grund) < 10:
            return Response({"grund": "Bitte den Grund der Einsicht angeben (mindestens 10 Zeichen)."},
                            status=status.HTTP_400_BAD_REQUEST)
        bis = timezone.now() + timedelta(minutes=EINSICHT_MINUTEN)
        Akteneinsicht.objects.create(patient=patient, benutzer=request.user, grund=grund, bis=bis)
        protokolliere(SystemEreignis.Art.AKTE_EINSICHT, request, objekt=akte_text(patient), patient_id=patient.id,
                      grund=grund, minuten=EINSICHT_MINUTEN)
        return Response({"bis": bis})

    # ------------------------------------------------ Aufbewahrung im Einzelfall verlängern
    @action(detail=True, methods=["post"], permission_classes=[DatenschutzEntscheidenRecht])
    def aufbewahrung(self, request, pk=None):
        """Aufbewahrung im Einzelfall verlängern (z. B. laufendes Verfahren): ``{"bis": "JJJJ-MM-TT", "grund": "…"}``;
        ``{"bis": null}`` nimmt die Verlängerung zurück. Die reguläre Frist (Abschluss + eingestellte Jahre) bleibt."""
        patient = self._akte(pk)
        grund = str(request.data.get("grund", "")).strip()
        bis = None
        if request.data.get("bis"):
            try:
                bis = serializers.DateField().to_internal_value(request.data["bis"])
            except serializers.ValidationError as f:
                return Response({"bis": f.detail}, status=status.HTTP_400_BAD_REQUEST)
            regulaer = patient.aufbewahrung()["regulaer_bis"]
            if bis <= timezone.localdate():
                return Response({"bis": "Das Datum muss in der Zukunft liegen."}, status=status.HTTP_400_BAD_REQUEST)
            if regulaer and bis <= regulaer:
                return Response({"bis": f"Die reguläre Frist läuft ohnehin bis {regulaer:%d.%m.%Y}."},
                                status=status.HTTP_400_BAD_REQUEST)
            if len(grund) < 10:
                return Response({"grund": "Bitte den Grund angeben (mindestens 10 Zeichen)."}, status=status.HTTP_400_BAD_REQUEST)
        patient.aufbewahrung_bis = bis
        patient.aufbewahrung_grund = grund[:300] if bis else ""
        patient._history_user = request.user
        patient._change_reason = "Aufbewahrung verlängert" if bis else "Verlängerte Aufbewahrung zurückgenommen"
        patient.save()
        protokolliere(SystemEreignis.Art.DATENSCHUTZ, request, objekt=akte_text(patient), patient_id=patient.id,
                      aktion=f"Aufbewahrung verlängert bis {bis:%d.%m.%Y}" if bis else "Verlängerte Aufbewahrung zurückgenommen")
        return Response({"aufbewahrung": patient.aufbewahrung()})

    # ------------------------------------------------ Kopie der Akte (Art. 15 Abs. 3 DSGVO)
    @action(detail=True, methods=["get"], permission_classes=[KopieRecht])
    def kopie(self, request, pk=None):
        """Vollständige Kopie der Akte als ZIP: Akte und Verlauf als PDF, alle Dokumente im Original."""
        patient = self.get_object()
        pruefe_schreibbereich(request.user, patient)  # Admins: Kopien nur von Testpatienten
        datei = tempfile.TemporaryFile()
        inhalt = aktenkopie(patient, datei)
        datei.seek(0)
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=akte_text(patient), was="Kopie der Akte", format="ZIP",
                      patient_id=patient.id, **inhalt)
        antwort = FileResponse(datei, content_type="application/zip")
        antwort["Content-Disposition"] = f'attachment; filename="Aktenkopie-{patient.nummer}-{timezone.localdate():%Y-%m-%d}.zip"'
        antwort["Cache-Control"] = "private, no-store"
        antwort["X-Content-Type-Options"] = "nosniff"
        return antwort

    @action(detail=True, methods=["get"], url_path="erklaerung-pdf")
    def erklaerung_pdf(self, request, pk=None):
        """Datenschutzinformation, Einwilligung oder Schweigepflichtentbindung für diesen Patienten als PDF zum
        Ausdrucken und Unterschreiben (``?art=``), mit der aktiven Dokumentvorlage. Solange die mitgelieferte
        Startvorlage nicht geprüft und veröffentlicht ist, trägt die PDF das Wasserzeichen „ENTWURF“."""
        from vorlagen.api import pdf_antwort
        from vorlagen.felder import Kontext
        from vorlagen.models import Dokumentvorlage
        from vorlagen.pdf import erzeuge_aus_vorlage, wasserzeichen_fuer

        art = request.query_params.get("art")
        if art not in Erklaerung.Art.values:
            return Response({"art": f"Erlaubt: {', '.join(Erklaerung.Art.values)}."}, status=status.HTTP_400_BAD_REQUEST)
        patient = self.get_object()
        vorlage = Dokumentvorlage.aktive(art)
        entwurf = vorlage.im_entwurfsmodus
        name = Erklaerung.Art(art).label
        # Entwurfsmodus manuell aus (U17): ohne Wasserzeichen und ohne den Hinweisblock der Startvorlage („Diese Vorlage
        # ist ein Entwurf …“), der sich an die Bearbeiter richtet und auf dem Blatt des Patienten nichts zu suchen hat
        bloecke = None
        if not entwurf and vorlage.veroeffentlicht_von_id is None:
            bloecke = [b for b in vorlage.bloecke if b.get("id") != "hinweis"]
        pdf, version = erzeuge_aus_vorlage(art, Kontext(patient=patient), vorlage=vorlage, bloecke=bloecke,
                                           wasserzeichen="ENTWURF" if entwurf else wasserzeichen_fuer(patient),
                                           titel=f"{name} – {patient.nachname}, {patient.vorname}")
        protokolliere(SystemEreignis.Art.EXPORT, request, objekt=akte_text(patient), was=name, patient_id=patient.id)
        antwort = pdf_antwort(pdf, f"{_dateiname(name)}-{patient.nummer}.pdf")
        antwort["X-EPM-Vorlage-Version"] = str(version or "")
        antwort["X-EPM-Vorlage-Entwurf"] = "1" if entwurf else "0"
        antwort["Access-Control-Expose-Headers"] = "X-EPM-Vorlage-Version, X-EPM-Vorlage-Entwurf"
        return antwort

    # ------------------------------------------------ Akte endgültig löschen (Art. 17 DSGVO)
    @action(detail=True, methods=["post"], url_path="loeschen-vorbereiten", permission_classes=[AkteLoeschenRecht])
    def loeschen_vorbereiten(self, request, pk=None):
        """Schritt 1: prüfen, ob die Akte gelöscht werden darf, und Bestätigungscode ausgeben (5 Minuten gültig)."""
        import secrets

        patient = self._akte(pk, loeschen=True)
        pruefung = loeschbar(patient)
        if not pruefung["moeglich"]:
            return Response({"fehler": pruefung["hinweis"], "loeschen": pruefung}, status=status.HTTP_409_CONFLICT)
        code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        bis = timezone.now() + timedelta(minutes=self.LOESCH_MINUTEN)
        request.session[self.LOESCHCODE] = {"akte": patient.id, "code": code, "bis": bis.isoformat(), "versuche": 0}
        return Response({"code": code, "gueltig_bis": bis, "loeschen": pruefung, "umfang": umfang(patient)})

    @action(detail=True, methods=["post"], permission_classes=[AkteLoeschenRecht])
    def loeschen(self, request, pk=None):
        """Schritt 2: Akte endgültig löschen (Mediziner und Admin, Recht „Akten endgültig löschen“) – mit Grund, Kennwort, Code aus der Authenticator-App
        und dem abgetippten Bestätigungscode. Danach sind alle Einträge, die Historie und die Dateien weg; es bleiben
        das Löschprotokoll (ohne Namen) und die Einträge im Audit-Log ohne Namen und Inhalte."""
        from datetime import datetime

        from accounts.zweifaktor import OHNE_ZWEITEN_FAKTOR, code_bestaetigt, hat_zweiten_faktor

        patient = self._akte(pk, loeschen=True)
        pruefung = loeschbar(patient)
        if not pruefung["moeglich"]:
            return Response({"fehler": pruefung["hinweis"], "loeschen": pruefung}, status=status.HTTP_409_CONFLICT)
        grund = str(request.data.get("grund", "")).strip()
        if len(grund) < 10:
            return Response({"grund": "Bitte den Grund angeben (mindestens 10 Zeichen)."}, status=status.HTTP_400_BAD_REQUEST)

        def abgelehnt(feld, meldung):
            protokolliere(SystemEreignis.Art.AKTE_LOESCHEN_ABGELEHNT, request, objekt=akte_text(patient),
                          patient_id=patient.id, fehler=meldung)
            return Response({feld: meldung}, status=status.HTTP_400_BAD_REQUEST)

        sitzung = request.session.get(self.LOESCHCODE) or {}
        if sitzung.get("akte") != patient.id or datetime.fromisoformat(sitzung["bis"]) < timezone.now():
            request.session.pop(self.LOESCHCODE, None)
            return abgelehnt("bestaetigung", "Der Bestätigungscode ist abgelaufen. Bitte einen neuen anfordern.")
        eingabe = "".join(ch for ch in str(request.data.get("bestaetigung", "")).upper() if ch.isalnum())
        if eingabe != sitzung["code"]:
            sitzung["versuche"] = sitzung.get("versuche", 0) + 1
            if sitzung["versuche"] >= 3:
                request.session.pop(self.LOESCHCODE, None)
                return abgelehnt("bestaetigung", "Bestätigungscode dreimal falsch. Bitte einen neuen anfordern.")
            request.session[self.LOESCHCODE] = sitzung
            return abgelehnt("bestaetigung", "Der Bestätigungscode stimmt nicht.")
        from accounts.api import bestaetigung_fehlgeschlagen, bestaetigung_gelungen

        if not hat_zweiten_faktor(request.user):
            # Festlegung 03.10.2026: endgültig löschen nur mit eingerichtetem zweitem Faktor
            return abgelehnt("code", OHNE_ZWEITEN_FAKTOR)
        if not request.user.check_password(str(request.data.get("kennwort", ""))):
            antwort = abgelehnt("kennwort", "Kennwort falsch.")
            return bestaetigung_fehlgeschlagen(request, "loeschen_kennwort") or antwort
        if not code_bestaetigt(request.user, request.data.get("code", ""), notfallcodes=False):
            antwort = abgelehnt("code", "Code aus der Authenticator-App falsch oder schon verwendet.")
            return bestaetigung_fehlgeschlagen(request, "loeschen_2fa") or antwort
        bestaetigung_gelungen(request)
        request.session.pop(self.LOESCHCODE, None)
        eintrag = akte_loeschen(patient, request.user, pruefung["rechtsgrund"], grund, request)
        return Response({"geloescht": True, "nummer": eintrag.nummer, "protokoll": eintrag.id})


def einschraenken(patient, benutzer, grund: str, request=None):
    """Verarbeitung einer abgeschlossenen Akte einschränken (auch als Ergebnis einer Datenschutz-Anfrage)."""
    from django.core.exceptions import ValidationError

    if not patient.ist_abgeschlossen:
        raise ValidationError({"fehler": "Nur abgeschlossene Akten können eingeschränkt werden – in einer laufenden "
                                         "Betreuung wird die Akte gebraucht. Bitte die Akte zuerst abschließen."})
    if patient.ist_eingeschraenkt:
        raise ValidationError({"fehler": "Die Verarbeitung dieser Akte ist bereits eingeschränkt."})
    patient.eingeschraenkt_am = timezone.now()
    patient.eingeschraenkt_von = benutzer
    patient.einschraenkung_grund = grund[:300]
    patient._history_user = benutzer
    patient._change_reason = "Verarbeitung eingeschränkt"
    patient.save()
    protokolliere(SystemEreignis.Art.AKTE_EINGESCHRAENKT, request, benutzer=benutzer, objekt=akte_text(patient),
                  patient_id=patient.id, grund=grund)



# ================================================================= Löschungen und Sicherungen
# Eine Sicherung enthält auch Akten, die nach ihr gelöscht wurden. Wird sie wiederhergestellt, müssen diese
# Löschungen erneut vollzogen werden. Dafür steht jede gelöschte Akte – wie jedes endgültig gelöschte Dokument –
# in der Löschliste (``patienten/loeschung.py``: eigener Ordner, übersteht eine Wiederherstellung; ohne Namen).
# ``epm_loeschungen_nachholen`` läuft bei jedem Start des Backends und ruft ``akten_nachholen`` auf.
def _listen_eintrag(x: Loeschprotokoll) -> dict:
    return {
        "akte": x.akte_id, "nummer": x.nummer, "ist_test": x.ist_test, "angelegt_am": x.angelegt_am.isoformat(),
        "abgeschlossen_am": x.abgeschlossen_am.isoformat() if x.abgeschlossen_am else None,
        "aufbewahrung_bis": x.aufbewahrung_bis.isoformat() if x.aufbewahrung_bis else None,
        "rechtsgrund": x.rechtsgrund, "grund": x.grund, "umfang": x.umfang,
        "geloescht_am": x.geloescht_am.isoformat(), "person": x.geloescht_von_id,
    }


def lies_akten() -> list[dict]:
    """Gelöschte Akten aus der Löschliste (Zeilen mit ``akte``; die Zeilen der Dokumente bleiben unberührt)."""
    import json

    from .loeschung import loeschliste

    pfad = loeschliste()
    if not pfad.exists():
        return []
    eintraege = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(zeile)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("akte") and e.get("nummer") and e.get("angelegt_am") and e.get("geloescht_am"):
            eintraege.append(e)
    return eintraege


def akten_nachholen() -> dict:
    """Gelöschte Akten nach einer Wiederherstellung erneut löschen; Löschliste und Löschprotokoll abgleichen.

    Eine Akte wird nur gelöscht, wenn interne Kennung, Patientennummer und Anlagezeitpunkt übereinstimmen
    (Testakten nie: ihre Nummern werden beim Zurücksetzen neu vergeben). Ohne Befund passiert nichts."""
    from datetime import date, datetime

    from accounts.models import User

    ergebnis = {"akten": 0, "protokoll_ergaenzt": 0, "akten_liste_ergaenzt": 0, "ordner_entfernt": 0, "akten_fehler": 0}

    def schluessel(akte, nummer, geloescht_am):
        return int(akte), int(nummer), geloescht_am

    aus_liste = {}
    for e in lies_akten():
        try:
            aus_liste.setdefault(schluessel(e["akte"], e["nummer"], datetime.fromisoformat(e["geloescht_am"])), e)
        except (TypeError, ValueError):
            continue
    aus_db = {schluessel(x.akte_id, x.nummer, x.geloescht_am): x for x in Loeschprotokoll.objects.all()}
    for k, x in aus_db.items():
        if k not in aus_liste:
            eintrag = _listen_eintrag(x)
            trage_ein(eintrag)
            aus_liste[k] = eintrag
            ergebnis["akten_liste_ergaenzt"] += 1
    for k, e in aus_liste.items():
        # jede Zeile für sich: eine unlesbare oder widersprüchliche Zeile hält die übrigen nicht auf
        getan = []
        try:
            with transaction.atomic():
                angelegt_am = datetime.fromisoformat(e["angelegt_am"])
                eintrag = aus_db.get(k)
                if eintrag is None:
                    eintrag = Loeschprotokoll.objects.create(
                        akte_id=k[0], nummer=k[1], ist_test=bool(e.get("ist_test")), angelegt_am=angelegt_am,
                        abgeschlossen_am=date.fromisoformat(e["abgeschlossen_am"]) if e.get("abgeschlossen_am") else None,
                        aufbewahrung_bis=date.fromisoformat(e["aufbewahrung_bis"]) if e.get("aufbewahrung_bis") else None,
                        rechtsgrund=e.get("rechtsgrund") or Loeschprotokoll.Rechtsgrund.FRIST, grund=e.get("grund") or "",
                        umfang=e.get("umfang") or {}, geloescht_am=k[2],
                        geloescht_von=User.objects.filter(id=e.get("person")).first() if e.get("person") else None)
                    getan.append("protokoll_ergaenzt")
                # Testakten nie: ihre Nummern werden beim Zurücksetzen neu vergeben
                patient = None if e.get("ist_test") else Patient.objects.filter(id=k[0], nummer=k[1], ist_test=False).first()
                if patient is not None and patient.angelegt_am == angelegt_am:
                    akte_loeschen(patient, None, eintrag.rechtsgrund, eintrag.grund, nachgezogen=True, eintrag=eintrag)
                    getan.append("akten")
                elif not e.get("ist_test") and patient is None and not Patient.objects.filter(nummer=k[1]).exists():
                    # Die Akte ist weg, ihr Dokumentenordner aber noch da (das Löschen der Dateien war fehlgeschlagen
                    # oder eine Wiederherstellung hat nur die Dateien zurückgebracht): Nummern echter Akten werden
                    # nicht neu vergeben, der Ordner gehört also zur gelöschten Akte.
                    ordner = settings.EPM_DOKUMENTE / str(k[1])
                    if ordner.is_dir():
                        dateien_entfernen(k[1])
                        if not ordner.exists():
                            getan.append("ordner_entfernt")
        except Exception:  # noqa: BLE001 – der Start des Backends darf daran nicht scheitern
            log.exception("Löschung der Akte Nr. %s konnte nicht nachgeholt werden", k[1])
            ergebnis["akten_fehler"] += 1
        else:
            for was in getan:
                ergebnis[was] += 1
    return ergebnis
