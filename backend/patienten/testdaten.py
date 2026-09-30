"""
Musterdaten: Auswahllisten, Präparate, Testversorger, Testbenutzer und Testpatienten.

Alles ist wiederholbar (legt nur an, was fehlt). Testpatienten tragen ist_test=True und
Nummern ab 9001, zählen in keiner Statistik und sind für den Testbenutzer die einzigen
sichtbaren Akten. Alle Namen sind frei erfunden.
"""
import random
import shutil
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import Rolle, User
from audit.schutz import wartungsmodus
from infusionen.models import Infusionsplan, InfusionsplanPosition
from stammdaten.models import Ansprechpartner, Auswahlwert, Einstellungen, Praeparat, Versorger

from .models import Dokument, Gewichtsmessung, Kontakt, Patient, Termin

TESTBENUTZER = "test"

AUSWAHLWERTE = {
    Auswahlwert.Liste.KATHETER: ["Port", "Hickman", "Broviac", "Groshong", "PICC", "ZVK", "Sonstiger"],
    Auswahlwert.Liste.DOKUMENTTYP: ["Arztbrief", "Laborbefund", "Infusionsplan", "Verordnung", "Rezept",
                                   "Korrespondenz", "Bild/Foto", "Patientendatenblatt", "Sonstiges"],
    Auswahlwert.Liste.KONTAKTART: ["Telefon (Anruf erhalten)", "Telefon (angerufen)", "Persönlich", "E-Mail",
                                  "Brief/Fax", "Versorger", "Sonstiges"],
}

K = Praeparat.Kategorie
PRAEPARATE = [
    (K.BASISLOESUNG, "Sterofundin ISO", ""), (K.BASISLOESUNG, "NaCl", "0,9 %"),
    (K.BASISLOESUNG, "Ringer-Lösung", ""), (K.BASISLOESUNG, "Jonosteril", ""),
    (K.GLUCOSE, "Glucose", "20 %"), (K.GLUCOSE, "Glucose", "40 %"), (K.GLUCOSE, "Glucose", "50 %"),
    (K.GLUCOSE, "Glucose", "70 %"),
    (K.AMINOSAEUREN, "Aminoplasmal", "10 %"), (K.AMINOSAEUREN, "Aminoven", "10 %"),
    (K.LIPIDE, "SMOFlipid", "20 %"), (K.LIPIDE, "Lipofundin MCT", "20 %"), (K.LIPIDE, "Omegaven", "10 %"),
    (K.ALBUMIN, "Albumin", "20 %"),
    (K.ELEKTROLYTE, "Kaliumchlorid", "7,45 %"), (K.ELEKTROLYTE, "Natriumhydrogencarbonat", "8,4 %"),
    (K.ELEKTROLYTE, "Magnesiumsulfat", "10 %"), (K.ELEKTROLYTE, "Calciumgluconat", "10 %"),
    (K.VITAMINE, "Cernevit", ""), (K.VITAMINE, "Vitalipid N Adult", ""), (K.VITAMINE, "Soluvit N", ""),
    (K.SPURENELEMENTE, "Addel N", ""), (K.SPURENELEMENTE, "Tracutil", ""),
    (K.KATHETERSCHUTZ, "Taurolidin-Lock", ""), (K.KATHETERSCHUTZ, "Heparin-Lock", ""),
    (K.MEDIKAMENT, "Pantozol i.v.", "40 mg"), (K.MEDIKAMENT, "Dipeptamin", "20 %"),
]


def stammdaten_anlegen() -> dict:
    neu = {"auswahlwerte": 0, "praeparate": 0}
    for liste, werte in AUSWAHLWERTE.items():
        for i, wert in enumerate(werte):
            _, angelegt = Auswahlwert.objects.get_or_create(liste=liste, wert=wert, defaults={"reihenfolge": (i + 1) * 10})
            neu["auswahlwerte"] += angelegt
    for kategorie, name, konz in PRAEPARATE:
        _, angelegt = Praeparat.objects.get_or_create(
            kategorie=kategorie, name=name, konzentration=konz,
            defaults={"einheit": "mg" if konz.endswith("mg") else "ml"},
        )
        neu["praeparate"] += angelegt
    Einstellungen.aktuell()
    return neu


def testbenutzer_anlegen():
    """Legt den Testbenutzer an (Rolle Mediziner). Gibt das Einmal-Kennwort zurück, falls neu."""
    user, angelegt = User.objects.get_or_create(
        username=TESTBENUTZER,
        defaults={"first_name": "Tessa", "last_name": "Test", "titel": "", "kuerzel": "TT",
                  "funktion": "Testzugang für Schulung und Prüfung nach Updates",
                  "rolle": Rolle.MEDIZINER, "ist_test": True},
    )
    if not angelegt:
        return user, None
    kennwort = user.neues_einmal_kennwort()
    user.save()
    return user, kennwort


def _testversorger():
    v1, _ = Versorger.objects.get_or_create(
        name="Testversorger Nord (fiktiv)",
        defaults={"strasse": "Musterweg 1", "plz": "48143", "ort": "Münster", "telefon": "0251 000000"},
    )
    v2, _ = Versorger.objects.get_or_create(
        name="Testversorger Süd (fiktiv)",
        defaults={"strasse": "Beispielstraße 5", "plz": "44135", "ort": "Dortmund", "telefon": "0231 000000"},
    )
    a = {}
    for v, name in [(v1, "Frau Beispiel"), (v1, "Herr Muster"), (v2, "Frau Probe")]:
        a[name], _ = Ansprechpartner.objects.get_or_create(versorger=v, name=name, defaults={"telefon": "0000 0000"})
    return v1, v2, a


TESTPATIENTEN = [
    # nachname, vorname, geburtsdatum, geschlecht, groesse, versorger-idx, ansprechpartner, katheter, nickel, profil
    ("Musterfrau", "Erika", date(1961, 3, 14), "w", Decimal("166"), 0, "Frau Beispiel", "Port", "nein", "stabil"),
    ("Mustermann", "Max", date(1954, 11, 2), "m", Decimal("181"), 0, "Herr Muster", "Hickman", "unbekannt", "abnahme"),
    ("Beispiel", "Paula", date(1988, 7, 21), "w", Decimal("159"), 1, "Frau Probe", "Broviac", "ja", "zunahme"),
    ("Probe", "Jonas", date(1975, 1, 30), "m", Decimal("176"), 1, "Frau Probe", "PICC", "unbekannt", "stabil"),
    ("Test", "Hanna", date(1949, 9, 9), "w", Decimal("162"), 0, "Frau Beispiel", "Port", "nein", "neu"),
    ("Demo", "Karl", date(1958, 5, 17), "m", Decimal("172"), 1, "Frau Probe", "Port", "nein", "abgeschlossen"),
]

DIAGNOSEN = [
    "<p><strong>Kurzdarmsyndrom</strong> nach ausgedehnter Dünndarmresektion (Testdaten).</p>"
    "<p>Restdünndarmlänge ca. 80 cm, Colon in Kontinuität.</p>",
    "<p>Chronisches Darmversagen bei Morbus Crohn (Testdaten).</p><ul><li>Z. n. mehreren Resektionen</li></ul>",
    "<p>Mangelernährung bei Motilitätsstörung (Testdaten).</p>",
]


def _nutzer(user, obj):
    obj._history_user = user  # Bearbeiter in der Historie
    return obj


def _gewichte(patient, user, profil, heute, rnd):
    start = {"stabil": 64.0, "abnahme": 78.0, "zunahme": 48.0, "neu": 58.0, "abgeschlossen": 70.0}[profil]
    monate = 2 if profil == "neu" else 36
    for m in range(monate, -1, -1):
        tag = heute - timedelta(days=30 * m + rnd.randint(0, 9))
        if profil == "abnahme":
            kg = start - (36 - m) * 0.1 - (6.0 if m <= 2 else 0) - (2.0 if m == 0 else 0)
        elif profil == "zunahme":
            kg = start + (36 - m) * 0.25
        else:
            kg = start + rnd.uniform(-1.2, 1.2)
        _nutzer(user, Gewichtsmessung(
            patient=patient, gewicht_kg=Decimal(str(round(kg, 1))), gemessen_am=tag, erfasst_von=user,
            quelle=rnd.choice([Gewichtsmessung.Quelle.TELEFONISCH, Gewichtsmessung.Quelle.VERSORGER,
                               Gewichtsmessung.Quelle.AMBULANZ]),
        )).save()


def _kontakte(patient, user, heute, rnd, art):
    texte = [
        "<p>Patientin/Patient telefonisch erreicht, Befinden stabil. Infusion läuft ohne Probleme.</p>",
        "<p>Versorger meldet Lieferung für nächste Woche bestätigt.</p>",
        "<p>Rückfrage zur Laufzeit der Infusion, <strong>Laufzeit auf 12 h</strong> belassen.</p>",
        "<p>Gewicht telefonisch durchgegeben, Rückruf in 4 Wochen vereinbart.</p>",
    ]
    kontakte = []
    for i in range(rnd.randint(3, 6)):
        zeit = timezone.make_aware(datetime.combine(heute - timedelta(days=20 * i + rnd.randint(0, 5)),
                                                    time(9 + rnd.randint(0, 7), rnd.choice([0, 15, 30, 45]))))
        k = _nutzer(user, Kontakt(patient=patient, zeitpunkt=zeit, art=art, text=rnd.choice(texte), erfasst_von=user))
        k.save()
        kontakte.append(k)
    return kontakte


def _plan(patient, user, p, gueltig_ab, glucose, aa, lipide, freigeben=True):
    plan = Infusionsplan.neuer_entwurf(patient, user)
    plan.gueltig_ab = gueltig_ab
    plan.basis_praeparat = p("basisloesung", "Sterofundin ISO")
    plan.basis_ml = 1000
    plan.glucose_praeparat, plan.glucose_g = p("glucose", "Glucose", "50 %"), Decimal(glucose)
    plan.aminosaeuren_praeparat, plan.aminosaeuren_g = p("aminosaeuren", "Aminoplasmal"), Decimal(aa)
    plan.lipide_praeparat, plan.lipide_g = p("lipide", "SMOFlipid"), Decimal(lipide)
    plan.laufzeit_h = Decimal("12")
    plan.tage_pro_woche = 7
    plan.katheterschutz = p("katheterschutz", "Taurolidin-Lock")
    plan.pantozol_stufe, plan.pantozol_tage = 1, 5
    plan.bemerkung = "<p>Testplan – keine echte Verordnung.</p>"
    _nutzer(user, plan).save()
    if not plan.positionen.exists():
        for i, (kat, name) in enumerate([("vitamine", "Cernevit"), ("spurenelemente", "Addel N"),
                                         ("elektrolyte", "Kaliumchlorid")]):
            _nutzer(user, InfusionsplanPosition(plan=plan, praeparat=p(kat, name), menge=Decimal("10" if i < 2 else "20"),
                                                einheit="ml", haeufigkeit="täglich", reihenfolge=i)).save()
    if freigeben:
        plan.freigeben(user)
    return plan


@transaction.atomic
def testpatienten_anlegen() -> int:
    if Patient.objects.filter(ist_test=True).exists():
        return 0
    rnd = random.Random(20260930)  # immer dieselben Daten
    heute = timezone.localdate()
    user, _ = testbenutzer_anlegen()
    v1, v2, ansprech = _testversorger()
    katheter = {a.wert: a for a in Auswahlwert.objects.filter(liste=Auswahlwert.Liste.KATHETER)}
    art = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.KONTAKTART).first()
    doktyp = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.DOKUMENTTYP, wert="Arztbrief").first()

    def p(kat, name, konz=None):
        qs = Praeparat.objects.filter(kategorie=kat, name=name)
        if konz is not None:
            qs = qs.filter(konzentration=konz)
        return qs.first()

    for i, (nach, vor, geb, geschl, groesse, vi, ap, kath, nickel, profil) in enumerate(TESTPATIENTEN):
        pat = _nutzer(user, Patient(
            nachname=nach, vorname=vor, geburtsdatum=geb, geschlecht=geschl, groesse_cm=groesse,
            versorger=(v1, v2)[vi], ansprechpartner=ansprech[ap], katheter=katheter.get(kath), nickelallergie=nickel,
            strasse=f"Teststraße {i + 1}", plz="48341", ort="Altenberge", telefon="0000 000000",
            diagnose=DIAGNOSEN[i % len(DIAGNOSEN)],
            therapie=f"<p><strong>Aktuell:</strong> parenterale Ernährung 7×/Woche über {kath}.</p>"
                     f"<p><strong>Verlauf:</strong></p><ul><li>{(heute - timedelta(days=700)):%d.%m.%Y} Beginn HPE</li>"
                     f"<li>{(heute - timedelta(days=200)):%d.%m.%Y} Umstellung Lipide</li></ul>",
            empfehlung="<p>Gewichtskontrolle alle 4 Wochen (Testdaten).</p>",
            ist_test=True, angelegt_von=user,
        ))
        pat.save()
        _gewichte(pat, user, profil, heute, rnd)
        kontakte = _kontakte(pat, user, heute, rnd, art)

        if profil != "neu":
            _plan(pat, user, p, heute - timedelta(days=500), 150, 60, 30)
            if i != 3:  # Patient 4 behält den alten Plan → Hinweis „älter als 12 Monate“
                _plan(pat, user, p, heute - timedelta(days=90 + 40 * i), 175, 70, 40)
        if profil == "stabil" and i == 0:
            _plan(pat, user, p, heute, 200, 70, 40, freigeben=False)  # offener Entwurf

        # Termine: überfällig, heute, nächste Woche, später
        faellig = [heute - timedelta(days=3), heute, heute + timedelta(days=5), heute + timedelta(days=40)]
        arten = [Termin.Art.RUECKRUF, Termin.Art.WIEDERVORLAGE, Termin.Art.PRAXISTERMIN, Termin.Art.WIEDERVORLAGE]
        _nutzer(user, Termin(
            patient=pat, art=arten[i % 4], faellig_am=faellig[i % 4],
            uhrzeit=time(10, 30) if arten[i % 4] == Termin.Art.PRAXISTERMIN else None,
            bei="Praxis Dr. Holtmeier" if arten[i % 4] == Termin.Art.PRAXISTERMIN else "",
            titel={Termin.Art.RUECKRUF: "Rückruf wegen Gewicht", Termin.Art.WIEDERVORLAGE: "Plan prüfen",
                   Termin.Art.PRAXISTERMIN: "Kontrolltermin"}[arten[i % 4]],
            kontakt=kontakte[0], angelegt_von=user,
        )).save()

        if i == 0:
            _beispieldokument(pat, user, doktyp)

        if profil == "abgeschlossen":
            pat.abgeschlossen_am = heute - timedelta(days=30)
            pat.abschluss_anlass = Patient.Abschlussanlass.THERAPIE_BEENDET
            pat.abschluss_notiz = "Darmfunktion ausreichend, HPE beendet (Testdaten)."
            _nutzer(user, pat).save()
    return len(TESTPATIENTEN)


def _beispieldokument(patient, user, typ):
    import hashlib

    from .models import dokument_pfad

    inhalt = (
        "Beispiel-Arztbrief (TESTDATEN)\n\nDieser Brief ist frei erfunden und dient nur zum Testen "
        "von Upload, Anzeige und Download im EPM.\n"
    ).encode("utf-8")
    relativ = dokument_pfad(patient, "Beispiel-Arztbrief.txt")
    ziel = settings.EPM_DOKUMENTE / relativ
    ziel.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    ziel.write_bytes(inhalt)
    _nutzer(user, Dokument(
        patient=patient, typ=typ, titel="Beispiel-Arztbrief", datum=timezone.localdate() - timedelta(days=14),
        datei=relativ, originalname="Beispiel-Arztbrief.txt", mime="text/plain; charset=utf-8",
        groesse=len(inhalt), sha256=hashlib.sha256(inhalt).hexdigest(), hochgeladen_von=user,
    )).save()


def testdaten_zuruecksetzen() -> dict:
    """Löscht alle Testpatienten samt Historie und Dateien und legt die Musterdaten neu an."""
    with wartungsmodus():
        testpatienten = list(Patient.objects.filter(ist_test=True).values_list("id", "nummer"))
        ids = [i for i, _ in testpatienten]
        plan_ids = list(Infusionsplan.objects.filter(patient_id__in=ids).values_list("id", flat=True))
        # Positionen und Pläne zuerst (Vorgänger-Verweise), dann die Akten
        InfusionsplanPosition.objects.filter(plan_id__in=plan_ids).delete()
        Infusionsplan.objects.filter(id__in=plan_ids).update(vorgaenger=None)
        Infusionsplan.objects.filter(id__in=plan_ids).delete()
        Patient.objects.filter(id__in=ids).delete()
        # Historie der Testakten entfernen
        Patient.history.filter(id__in=ids).delete()
        for modell in (Gewichtsmessung, Kontakt, Termin, Dokument, Infusionsplan):
            modell.history.filter(patient_id__in=ids).delete()
        InfusionsplanPosition.history.filter(plan_id__in=plan_ids).delete()
    for _, nummer in testpatienten:
        shutil.rmtree(settings.EPM_DOKUMENTE / str(nummer), ignore_errors=True)
    angelegt = testpatienten_anlegen()
    return {"geloescht": len(ids), "angelegt": angelegt}
