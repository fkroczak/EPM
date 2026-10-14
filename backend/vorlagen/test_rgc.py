"""Mitgelieferte Vorlagen der Regeneration Clinic (13.10.2026): angelegt, gültig, nur in der Firma RGC sichtbar."""
from datetime import date

from accounts.models import Mitgliedschaft, Rolle
from epm.firma import setze_aktive_firma, zuruecksetzen
from epm.pruefhilfen import Grundlage, client_fuer, echte_anmeldung, mit_zweitem_faktor
from patienten.models import Patient, PatientFirma
from stammdaten.models import Firma

from .bloecke import pruefe_bloecke
from .felder import Kontext
from .models import Dokumentvorlage, EigenesSchreiben
from .pdf import bloecke_html, erzeuge_aus_vorlage
from .rgc import vorlagen
from .tests import kompakt, pdf_text


class RgcVorlagenTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.rg = Firma.objects.get(kuerzel="rg")
        Mitgliedschaft.objects.create(benutzer=cls.admin, firma=cls.rg, rolle=Rolle.ADMIN)

    def test_alle_vorlagen_angelegt_und_gueltig(self):
        quellen = vorlagen()
        self.assertEqual(len(quellen), 35)
        rgc = EigenesSchreiben.objects.filter(firma=self.rg)
        self.assertEqual(rgc.count(), 35)
        # 14 Anforderungen der RGC und 9 Bögen der Laborprofile Malabsorption (Übersicht, MAL-01 bis MAL-06)
        self.assertEqual(rgc.filter(gruppe="anforderungen").count(), 23)
        self.assertEqual(sorted(rgc.filter(schluessel__startswith="eigen-rgc-mal").values_list("schluessel", flat=True)),
                         ["eigen-rgc-mal00", "eigen-rgc-mal01", "eigen-rgc-mal02a", "eigen-rgc-mal02b",
                          "eigen-rgc-mal02c", "eigen-rgc-mal03", "eigen-rgc-mal04", "eigen-rgc-mal05", "eigen-rgc-mal06"])
        # Formulare 01–12 (Patientenerklärungen, Schweigepflicht, Aufklärungen, ÖGK, Anlage K, Anwaltsvollmacht)
        self.assertEqual(sorted(rgc.filter(gruppe="formulare").values_list("schluessel", flat=True)),
                         [f"eigen-rgc-f{n:02d}" for n in range(1, 13)])
        for e in rgc:
            v = Dokumentvorlage.objects.get(art=e.schluessel, status="aktiv")
            self.assertEqual(pruefe_bloecke(e.schluessel, v.bloecke), [], e.name)

    def test_nur_in_der_firma_rgc(self):
        c = echte_anmeldung(self.admin, mit_zweitem_faktor(self.admin, 1)[0])
        namen = {v["name"] for v in c.get("/api/vorlagen/").json()}
        self.assertNotIn("Laboranforderung Basislabor", namen)  # in der DSKM nicht zu sehen
        self.assertNotIn("Laboranforderung Basislabor", {v["name"] for v in client_fuer(self.admin).get("/api/vorlagen/").json()})
        self.assertEqual(c.get("/api/vorlagen/eigen-rgc-a01/").status_code, 404)
        self.assertEqual(c.post("/api/auth/firma/", {"firma": "rg"}, format="json").status_code, 200)
        liste = {v["name"]: v for v in c.get("/api/vorlagen/").json()}
        self.assertEqual(liste["Laboranforderung Basislabor"]["gruppe"], "anforderungen")
        self.assertEqual(liste["Aufklärung Operation (DE/LV)"]["gruppe"], "formulare")
        schreiben = {s["name"]: s for s in c.get("/api/schreiben/").json()}
        self.assertEqual(schreiben["MRT-Anforderung"]["gruppe_name"],
                         "Anforderungen: Labor, Bildgebung, Funktionsdiagnostik")
        # neu angelegte eigene Vorlagen gehören der aktiven Firma
        r = c.post("/api/vorlagen/", {"name": "Laborbrief RGC"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(EigenesSchreiben.objects.get(name="Laborbrief RGC").firma, self.rg)

    def test_pdf_mit_patientendaten(self):
        token = setze_aktive_firma(self.rg)
        try:
            p = Patient.objects.create(nachname="Bērziņa", vorname="Ilze", geschlecht="w", nummer=4711,
                                       geburtsdatum=date(1970, 5, 3))
            PatientFirma.objects.filter(patient=p).update(firma=self.rg)
            pdf, version = erzeuge_aus_vorlage("eigen-rgc-a01", Kontext(patient=p), titel="Basislabor")
            text = kompakt(pdf_text(pdf))
            self.assertEqual(version, 1)
            for erwartet in ("Bērziņa, Ilze", "4711", "Basislabor", "Retikulozyten", "Regeneration Clinic SIA"):
                self.assertIn(kompakt(erwartet), text)
            pdf, _ = erzeuge_aus_vorlage("eigen-rgc-f07", Kontext(patient=p), titel="Aufklärung")
            self.assertIn(kompakt("16. Einwilligungserklärung · Piekrišanas apliecinājums"), kompakt(pdf_text(pdf)))
            for art, erwartet in (("eigen-rgc-f01", "Bērziņa, Ilze"), ("eigen-rgc-f11", "Anlage K"),
                                  ("eigen-rgc-f12", "Vollmacht")):
                pdf, _ = erzeuge_aus_vorlage(art, Kontext(patient=p), titel=art)
                self.assertIn(kompakt(erwartet), kompakt(pdf_text(pdf)), art)
        finally:
            zuruecksetzen(token)

    def test_laborprofile_malabsorption(self):
        """Laborprofile Malabsorption (14.10.2026): jeder Parameter des Dokuments steht mit Material auf dem Bogen."""
        import json

        from .rgc import ORDNER

        daten = json.loads((ORDNER.parent / "laborprofile-malabsorption.json").read_text(encoding="utf-8"))
        self.assertEqual([p["id"] for p in daten["profile"]],
                         ["MAL-01", "MAL-02A", "MAL-02B", "MAL-02C", "MAL-03A", "MAL-03B", "MAL-03C", "MAL-03D",
                          "MAL-04", "MAL-05", "MAL-06"])
        self.assertEqual(len(daten["parameter"]), 71)
        self.assertEqual([r["id"] for r in daten["regeln"]], [f"R{n}" for n in range(1, 12)])
        boegen = {v["quelle"]: json.dumps(v["bloecke"], ensure_ascii=False) for v in vorlagen()
                  if v["quelle"].startswith("RC_Labor_MAL-")}
        for p in daten["parameter"]:
            if p["nr"] in ("5.1", "6.6"):  # dynamisch bzw. Pflichthinweis, kein eigener Eintrag
                continue
            bogen = boegen["RC_Labor_MAL-03" if p["profil"].startswith("MAL-03") else f"RC_Labor_{p['profil']}"]
            self.assertIn(f" {p['nr']} ", bogen, p["nr"])
            if p["material"] not in ("berechnet", "–", "Funktionsdiagnostik", "nuklearmedizinisch (extern)",
                                     "gemäß ESPEN-HPN"):  # ohne Röhrchen: eigene Überschrift statt Material
                self.assertIn(p["material"], bogen, p["nr"])
        # Pflichtparameter angekreuzt, optionale und Reflexe zum Ankreuzen; Reflex aus anderem Profil mit Röhrchen
        mal01 = boegen["RC_Labor_MAL-01"]
        for erwartet in ("☒ 1.32 Zink", "☐ 1.05 Präalbumin", "☐ 1.26 Löslicher Transferrinrezeptor",
                         "☐ 2A.4 Parathormon, intakt", "Röhrchen / Material: Serum (Spurenelement-Röhrchen)",
                         "Röhrchen / Material: EDTA-Plasma, gekühlt", "Patient unter glutenhaltiger Kost?"):
            self.assertIn(erwartet, mal01)
        # MAL-04 = Pflichtparameter von MAL-01, MAL-02A und MAL-02B
        for nr in ("1.01", "2A.4", "2B.7"):
            self.assertIn(f" {nr} ", boegen["RC_Labor_MAL-04"])
        token = setze_aktive_firma(self.rg)
        try:
            p = Patient.objects.create(nachname="Kalniņa", vorname="Anna", geschlecht="w", nummer=815,
                                       geburtsdatum=date(1981, 2, 1))
            PatientFirma.objects.filter(patient=p).update(firma=self.rg)
            for art, erwartet in (("eigen-rgc-mal01", ["Kalniņa, Anna", "MAL-01 · Basisprofil",
                                                       "Citratplasma", "1.20 INR (Quick)", "Regeneration Clinic SIA",
                                                       # Briefpapier der Klinik: Kopfband, Fußband, Kontakt
                                                       "Jana Asara iela 3", "Registration No.: 40203593175",
                                                       "Health Institution Code: 001000289", "Prof. Dr. Markus Masin"]),
                                  ("eigen-rgc-mal06", ["Thiaminsubstitution", "NaF-Plasma"]),
                                  ("eigen-rgc-mal00", ["Profilübersicht", "R11"])):
                pdf, _ = erzeuge_aus_vorlage(art, Kontext(patient=p), titel=art)
                text = kompakt(pdf_text(pdf))
                for e in erwartet:
                    self.assertIn(kompakt(e), text, art)
        finally:
            zuruecksetzen(token)

    def test_briefpapier(self):
        """Briefpapier 1:1 (14.10.2026): Bänder auf jeder Seite, Angaben der ersten Seite nur mit Absender."""
        p = Patient(nachname="A", vorname="B")
        kopf = {"id": "k", "typ": "briefkopf", "briefpapier": "rgc", "absender": True}
        text = {"id": "t", "typ": "text", "text": "Zeile\n" * 400}
        self.assertEqual(pruefe_bloecke("eigen-x", [kopf, text]), [])
        self.assertTrue(pruefe_bloecke("eigen-x", [{**kopf, "briefpapier": "xyz"}, text]))
        inhalt = bloecke_html("eigen-x", [kopf, text], Kontext(patient=p, heute=date(2026, 10, 14)))[0]
        self.assertIn('class="briefpapier"', inhalt)
        self.assertIn("Riga, 14.10.2026", inhalt)
        self.assertNotIn("Prof. Dr. Markus Masin",
                         bloecke_html("eigen-x", [{**kopf, "absender": False}, text], Kontext(patient=p))[0])
        from .pdf import html_zu_pdf, seite

        seiten = pdf_text(html_zu_pdf(seite("x", inhalt))).split("\f")
        seiten = [s for s in seiten if s.strip()]
        self.assertGreater(len(seiten), 1)
        for s in seiten:  # Kopf- und Fußband auf jeder Seite
            self.assertIn("info@regeneration-clinic.eu", s)
            self.assertIn(kompakt("Registration No.: 40203593175"), kompakt(s))

    def test_text_in_spalten(self):
        p = Patient(nachname="A", vorname="B")
        b = [{"id": "t", "typ": "text", "text": "☐ a\n☐ b\n☐ c", "optionen": {"spalten": 3}}]
        self.assertEqual(pruefe_bloecke("eigen-x", b), [])
        self.assertIn("sp-3", bloecke_html("eigen-x", b, Kontext(patient=p))[0])
        b[0]["optionen"]["spalten"] = 4
        self.assertTrue(pruefe_bloecke("eigen-x", b))


class MigrationMitSchutzTest(Grundlage):
    """Rückfall 2.0.26 → 2.0.24 (14.10.2026): Datenmigrationen an freigegebenen Fassungen laufen auf dem Server bei
    eingeschaltetem Schutz-Trigger (frische Test-Datenbanken haben ihn beim ersten migrate noch nicht)."""

    def test_0012_bei_eingeschaltetem_trigger(self):
        from importlib import import_module

        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        from audit.schutz import installiere_trigger

        installiere_trigger()
        migration = import_module("vorlagen.migrations.0012_rgc_laborprofile_briefpapier")
        # Modelle im Stand der Migration (ohne die Sperre in Dokumentvorlage.save), wie beim echten migrate
        apps = MigrationExecutor(connection).loader.project_state([("vorlagen", "0011_rgc_laborprofile")]).apps
        with connection.schema_editor(atomic=True) as editor:
            migration.umstellen(apps, editor)
        v = Dokumentvorlage.objects.get(art="eigen-rgc-mal01", status="aktiv")
        self.assertTrue(any(b.get("briefpapier") == "rgc" for b in v.bloecke))
