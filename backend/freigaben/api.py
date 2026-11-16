"""API des Menüs „Freigaben“ (16.11.2026) – alle Endpunkte unter ``/api/freigaben/``.

    GET  freigaben/                         offene Vorschläge (Datenpflege), Plan-Entwürfe, KI-Prüfungen, laufende Freigaben
         ?patient=ID                        nur eine Akte
    GET  freigaben/zaehler/                 {offen} für die Zahl im Menü
    POST freigaben/suchen/                  Datenpflege-Vorschläge erstellen ({"patient": ID} oder alle Akten)
    POST freigaben/datenpflege/ID/freigeben/  {"schritte": [...]} → Freigabe (wird nach 60 s umgesetzt)
    POST freigaben/datenpflege/ID/verwerfen/
    POST freigaben/datenpflege/sammel/      alle eindeutigen (ohne offene Frage) gemeinsam freigeben → {gruppe, anzahl,
                                            uebersprungen}; ``{"ids": [...]}`` schränkt ein
    POST freigaben/aerzte/ID/freigeben/     doppelte Ärzte zusammenführen {"ziel": ID, "werte": {...}}
    POST freigaben/aerzte/ID/verwerfen/     „keine Dublette“ (wird nicht wieder vorgeschlagen)
    POST freigaben/plaene/ID/freigeben/     Infusionsplan-Entwurf freigeben (nach 60 s)
    POST freigaben/gruppe/UUID/zuruecknehmen/  Sammelfreigabe zurücknehmen
    POST freigaben/ID/zuruecknehmen/        innerhalb der 60 s
    POST freigaben/ID/umsetzen/             fällige Freigaben jetzt umsetzen (die Seite ruft das nach dem Countdown)

Jeder Aufruf setzt zuerst fällige Freigaben um. Sichtbar ist nur, was zum Bereich der Person gehört (``patienten_fuer``).
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import Angemeldet
from audit.models import SystemEreignis, protokolliere
from epm.api_basis import benutzername, patienten_fuer

from django.db.models import Q

from . import aerzte, datenpflege, dienst, lernen
from .models import RUECKGAENGIG_S, Arztdublette, Datenpflegevorschlag, Freigabe

D = Datenpflegevorschlag.Status


def darf_freigaben(user) -> bool:
    return any(user.hat_recht(r) for r in ("datenpflege_freigeben", "plaene_freigeben", "ki_ansehen"))


def _fehler(e) -> Response:
    if isinstance(e, PermissionError):
        return Response({"fehler": str(e)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(e, ValidationError):
        daten = e.message_dict if hasattr(e, "message_dict") else {"fehler": " ".join(e.messages)}
        return Response({k: " ".join(v) if isinstance(v, list) else v for k, v in daten.items()},
                        status=status.HTTP_400_BAD_REQUEST)
    return Response({"fehler": str(e)}, status=status.HTTP_400_BAD_REQUEST)


def _patient(p) -> dict:
    return {"id": p.id, "nummer": p.nummer, "name": f"{p.nachname}, {p.vorname}", "geburtsdatum": p.geburtsdatum,
            "geschlecht": p.geschlecht}


def _bestand(p) -> dict:
    """Was die Akte heute schon hat – für die Ansicht „vorher → nachher“."""
    return {
        "felder": {f: datenpflege._feldwert(p, f) for f in datenpflege.FELDER},
        "bezugspersonen": [{"id": b.id, "name": b.name, "beziehung": b.beziehung.wert if b.beziehung_id else "",
                            "telefon": b.telefon, "mobil": b.mobil}
                           for b in p.bezugspersonen.filter(aktiv=True).select_related("beziehung")],
        "aerzte": [{"id": z.id, "rolle": z.rolle, "rolle_name": z.get_rolle_display(), "name": z.arzt.name,
                    "ort": z.arzt.ort, "telefon": z.arzt.telefon}
                   for z in p.aerzte.filter(aktiv=True).select_related("arzt")],
        "hinweise": [{"titel": h["titel"], "inhalt": h["inhalt"]} for h in datenpflege.hinweise(p.bemerkung)]
        + ([{"titel": "Bemerkung aus dem Altsystem", "inhalt": datenpflege._text(datenpflege.hinweis_rest(p.bemerkung))}]
           if datenpflege.hinweis_rest(p.bemerkung) else []),
        "abgeschlossen": p.ist_abgeschlossen,
    }


def _vorschlag(v: Datenpflegevorschlag) -> dict:
    return {"id": v.id, "art": "datenpflege", "patient": _patient(v.patient), "erstellt_am": v.erstellt_am,
            "verfahren": v.verfahren, "status": v.status, "schritte": datenpflege.darstellung(v),
            "bestand": _bestand(v.patient), "eindeutig": datenpflege.eindeutig(v)}


def _freigabe(f: Freigabe) -> dict:
    rest = (f.umsetzen_ab - timezone.now()).total_seconds()
    titel = f.get_art_display()
    wer = f" · {f.patient.nachname}, {f.patient.vorname}" if f.patient_id else ""
    return {"id": f.id, "art": f.art, "objekt_id": f.objekt_id, "status": f.status, "status_name": f.get_status_display(),
            "titel": f"{titel}{wer}", "patient_id": f.patient_id, "gruppe": f.gruppe,
            "freigegeben_am": f.freigegeben_am, "umsetzen_ab": f.umsetzen_ab,
            "sekunden": max(0, round(rest)) if f.status == Freigabe.Status.WARTET else 0,
            "fehler": f.fehler, "von": benutzername(f.freigegeben_von)}


def _plan(plan) -> dict:
    v = plan.vergleich()
    return {"id": plan.id, "art": "infusionsplan", "patient": _patient(plan.patient), "gueltig_ab": plan.gueltig_ab,
            "erstellt_am": plan.erstellt_am,
            "erstellt_von": benutzername(plan.erstellt_von) if plan.erstellt_von_id else None,
            "vorgaenger": v["vorgaenger"], "anzahl_geaendert": v["anzahl_geaendert"],
            "zeilen": [z for z in v["zeilen"] if z["geaendert"] or v["vorgaenger"] is None and z["jetzt"]]}


class _Basis(APIView):
    permission_classes = [Angemeldet]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not darf_freigaben(request.user):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Für Freigaben fehlt das Recht.")
        dienst.faellige_umsetzen()

    def akten(self):
        return patienten_fuer(self.request.user)


FILTER = {
    "alle": lambda v: True,
    "eindeutig": lambda v: datenpflege.eindeutig(v),
    "fragen": lambda v: not datenpflege.eindeutig(v),
    "inaktiv": lambda v: any(s["art"] == "abschluss" for s in v.schritte),
}


class FreigabenView(_Basis):
    def get(self, request):
        user, akten = request.user, self.akten()
        pid = request.query_params.get("patient", "")
        if pid.isdigit():
            akten = akten.filter(pk=int(pid))
        filter_ = request.query_params.get("filter", "alle")
        filter_ = filter_ if filter_ in FILTER else "alle"
        wartend = set(Freigabe.objects.filter(status=Freigabe.Status.WARTET).values_list("art", "objekt_id"))
        daten = {"rueckgaengig_s": RUECKGAENGIG_S, "datenpflege": [], "plaene": [], "aerzte": [], "ki_zur_pruefung": 0,
                 "filter": filter_, "zahlen": {},
                 "darf": {"datenpflege": user.hat_recht("datenpflege_freigeben"),
                          "sammel": user.hat_recht("sammelfreigabe") and user.hat_recht("datenpflege_freigeben"),
                          "abschliessen": user.hat_recht("akten_abschliessen"),
                          "plaene": user.darf_plaene_freigeben, "ki": user.hat_recht("ki_ansehen"),
                          "aerzte_anlegen": user.hat_recht("versorger_pflegen")}}
        if daten["darf"]["datenpflege"]:
            alle = [v for v in Datenpflegevorschlag.objects.filter(status=D.OFFEN, patient__in=akten)
                    .select_related("patient").order_by("patient__nachname", "patient__vorname", "id")[:500]
                    if ("datenpflege", v.id) not in wartend]
            daten["zahlen"] = {k: sum(1 for v in alle if f(v)) for k, f in FILTER.items()}
            gewaehlt = [v for v in alle if FILTER[filter_](v)]
            daten["datenpflege_gesamt"] = len(gewaehlt)
            daten["datenpflege"] = [_vorschlag(v) for v in gewaehlt[:25]]
            daten["lernstand"] = lernen.stand()
            if user.hat_recht("versorger_pflegen") and not pid.isdigit():
                daten["aerzte"] = [aerzte.darstellung(d) for d in Arztdublette.objects.filter(status="offen")[:25]
                                   if ("aerzte", d.id) not in wartend]
        if daten["darf"]["plaene"]:
            from infusionen.models import Infusionsplan

            qs = (Infusionsplan.objects.filter(status=Infusionsplan.Status.ENTWURF, patient__in=akten)
                  .select_related("patient", "erstellt_von").order_by("erstellt_am"))
            daten["plaene"] = [_plan(p) for p in qs[:25] if ("infusionsplan", p.id) not in wartend]
        if daten["darf"]["ki"]:
            from ki.api import vorgaenge_fuer
            from ki.models import KiVorgang

            daten["ki_zur_pruefung"] = vorgaenge_fuer(user).filter(patient__in=akten,
                                                                  status__in=KiVorgang.PRUEFBAR).count()
        # eigene Freigaben der letzten 10 Minuten: Countdown, Ergebnis, Fehler
        seit = timezone.now() - timezone.timedelta(minutes=10)
        daten["laufend"] = [_freigabe(f) for f in Freigabe.objects.filter(freigegeben_von=user, freigegeben_am__gte=seit)
                            .select_related("patient", "freigegeben_von").order_by("-freigegeben_am")[:200]]
        return Response(daten)


class ZaehlerView(_Basis):
    def get(self, request):
        user, akten = request.user, self.akten()
        n = 0
        if user.hat_recht("datenpflege_freigeben"):
            n += Datenpflegevorschlag.objects.filter(status=D.OFFEN, patient__in=akten).count()
            if user.hat_recht("versorger_pflegen"):
                n += Arztdublette.objects.filter(status="offen").count()
        if user.darf_plaene_freigeben:
            from infusionen.models import Infusionsplan

            n += Infusionsplan.objects.filter(status=Infusionsplan.Status.ENTWURF, patient__in=akten).count()
        return Response({"offen": n})


class SuchenView(_Basis):
    def post(self, request):
        if not request.user.hat_recht("datenpflege_freigeben"):
            return _fehler(PermissionError("Dafür fehlt das Recht „Freigaben: Datenpflege aus dem Altbestand "
                                           "freigeben“."))
        akten = self.akten()
        pid = str(request.data.get("patient") or "")
        if pid:
            akten = self.akten().filter(pk=int(pid)) if pid.isdigit() else self.akten().none()
            if not akten.exists():
                # fremde oder unbekannte Akte: nichts verraten, nichts protokollieren (Firmentrennung)
                return Response({"fehler": "Akte nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
        n = datenpflege.alle_erstellen(akten)
        dubletten = aerzte.suchen() if request.user.hat_recht("versorger_pflegen") else 0
        protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt="Datenpflege", aktion="vorschlaege_erstellt",
                      anzahl=n, dubletten=dubletten, patient_id=int(pid) if pid.isdigit() else None)
        return Response({"neu": n, "dubletten": dubletten})


class DatenpflegeView(_Basis):
    def post(self, request, pk: int, aktion: str):
        v = (Datenpflegevorschlag.objects.filter(pk=pk, patient__in=self.akten()).select_related("patient").first())
        if v is None:
            return Response({"fehler": "Vorschlag nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
        try:
            if aktion == "freigeben":
                f = dienst.freigeben_datenpflege(v, request.data.get("schritte"), request.user,
                                                 firma=getattr(request.user, "firma", None))
                return Response(_freigabe(f), status=status.HTTP_201_CREATED)
            if aktion == "verwerfen":
                dienst._recht(request.user, "datenpflege_freigeben")
                if v.status != D.OFFEN:
                    raise ValidationError({"fehler": "Dieser Vorschlag ist nicht mehr offen."})
                v.status, v.erledigt_am, v.erledigt_von = D.VERWORFEN, timezone.now(), request.user
                v.save(update_fields=["status", "erledigt_am", "erledigt_von"])
                protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt=f"Datenpflege {v.pk}",
                              aktion="datenpflege_verworfen", patient_id=v.patient_id)
                return Response({"status": v.status})
        except (ValidationError, PermissionError) as e:
            return _fehler(e)
        return Response(status=status.HTTP_404_NOT_FOUND)


class SammelView(_Basis):
    def post(self, request):
        qs = Datenpflegevorschlag.objects.filter(status=D.OFFEN, patient__in=self.akten()).select_related("patient")
        ids = request.data.get("ids")
        if isinstance(ids, list):
            qs = qs.filter(pk__in=[i for i in ids if isinstance(i, int)])
        wartend = set(Freigabe.objects.filter(status=Freigabe.Status.WARTET, art=Freigabe.Art.DATENPFLEGE)
                      .values_list("objekt_id", flat=True))
        vorschlaege = [v for v in qs.order_by("patient__nachname", "id")[:200] if v.id not in wartend]
        try:
            gruppe, freigaben, uebersprungen = dienst.sammel_freigeben(vorschlaege, request.user,
                                                                       firma=getattr(request.user, "firma", None))
        except PermissionError as e:
            return _fehler(e)
        protokolliere(SystemEreignis.Art.STAMMDATEN, request, objekt="Datenpflege (Sammelfreigabe)",
                      aktion="sammelfreigabe", anzahl=len(freigaben), uebersprungen=len(uebersprungen))
        return Response({"gruppe": gruppe, "anzahl": len(freigaben),
                         "uebersprungen": [u for u in uebersprungen if u["grund"] != "hat eine offene Frage"],
                         "mit_frage": sum(1 for u in uebersprungen if u["grund"] == "hat eine offene Frage")},
                        status=status.HTTP_201_CREATED)


class AerzteView(_Basis):
    def post(self, request, pk: int, aktion: str):
        d = Arztdublette.objects.filter(pk=pk).first()
        if d is None:
            return Response({"fehler": "Vorschlag nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
        try:
            if aktion == "freigeben":
                f = dienst.freigeben_aerzte(d, request.data, request.user)
                return Response(_freigabe(f), status=status.HTTP_201_CREATED)
            if aktion == "verwerfen":
                dienst._recht(request.user, "versorger_pflegen")
                if d.status != Arztdublette.Status.OFFEN:
                    raise ValidationError({"fehler": "Dieser Vorschlag ist nicht mehr offen."})
                d.status, d.erledigt_am, d.erledigt_von = Arztdublette.Status.VERWORFEN, timezone.now(), request.user
                d.save(update_fields=["status", "erledigt_am", "erledigt_von"])
                return Response({"status": d.status})
        except (ValidationError, PermissionError) as e:
            return _fehler(e)
        return Response(status=status.HTTP_404_NOT_FOUND)


class PlanFreigebenView(_Basis):
    def post(self, request, pk: int):
        from infusionen.models import Infusionsplan

        plan = Infusionsplan.objects.filter(pk=pk, patient__in=self.akten()).select_related("patient").first()
        if plan is None:
            return Response({"fehler": "Plan nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
        try:
            f = dienst.freigeben_plan(plan, request.user, firma=getattr(request.user, "firma", None))
        except (ValidationError, PermissionError) as e:
            return _fehler(e)
        return Response(_freigabe(f), status=status.HTTP_201_CREATED)


class GruppeView(_Basis):
    def post(self, request, gruppe: str):
        try:
            n = dienst.gruppe_zuruecknehmen(gruppe, request.user)
        except (ValidationError, PermissionError) as e:
            return _fehler(e)
        return Response({"zurueckgenommen": n})


class FreigabeView(_Basis):
    def post(self, request, pk: int, aktion: str):
        f = (Freigabe.objects.filter(pk=pk).filter(Q(patient__in=self.akten()) | Q(patient__isnull=True))
             .select_related("patient").first())
        if f is None:
            return Response({"fehler": "Freigabe nicht gefunden."}, status=status.HTTP_404_NOT_FOUND)
        try:
            if aktion == "zuruecknehmen":
                f = dienst.zuruecknehmen(f, request.user)
            elif aktion != "umsetzen":
                return Response(status=status.HTTP_404_NOT_FOUND)
        except (ValidationError, PermissionError) as e:
            return _fehler(e)
        f.refresh_from_db()
        return Response(_freigabe(f))
