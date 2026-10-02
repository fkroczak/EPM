"""Stammdaten: Präparate mit Nutzung, Versorger/Ansprechpartner, Einstellungen (echte Datenbank)."""
from django.utils import timezone

from epm.pruefhilfen import Grundlage, client_fuer
from infusionen.models import Infusionsplan
from patienten.models import Patient

from .models import Ansprechpartner, Auswahlwert, Einstellungen, Praeparat, Versorger


class Praeparate(Grundlage):
    def test_in_plaenen(self):
        glamin = Praeparat.objects.get(name="Glamin")
        soluvit = Praeparat.objects.get(name="Soluvit N")
        plan = Infusionsplan.neuer_entwurf(self.patient, self.mediziner)
        plan.aminosaeuren_praeparat, plan.aminosaeuren_g = glamin, 70
        plan.save()
        plan.vitamine.set([soluvit])
        plan.freigeben(self.mediziner)
        Infusionsplan.neuer_entwurf(self.patient, self.mediziner)  # übernimmt Glamin und Soluvit N

        c = client_fuer(self.betrachter)  # lesen dürfen alle
        werte = {p["name"]: p["in_plaenen"] for p in c.get("/api/praeparate/").json()}
        self.assertEqual(werte["Glamin"], 2)
        self.assertEqual(werte["Soluvit N"], 2)
        self.assertEqual(werte["Clinoleic"], 0)
        einzeln = c.get(f"/api/praeparate/{glamin.id}/").json()
        self.assertEqual(einzeln["in_plaenen"], 2)

    def test_vorlagen_pflegen_mit_recht_kein_loeschen(self):
        neu = {"kategorie": "lipide", "name": "Omegaven", "konzentration": "10 %", "einheit": "ml", "reihenfolge": 5}
        self.assertEqual(client_fuer(self.betrachter).post("/api/praeparate/", neu, format="json").status_code, 403)
        # Vorlagen pflegen auch Mitarbeiter (Festlegung 01.10.2026)
        r = client_fuer(self.mitarbeiter).post("/api/praeparate/", {**neu, "konzentration": "15 %"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        r = client_fuer(self.mediziner).post("/api/praeparate/", {**neu, "konzentration": "20 %"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)  # Mediziner wie Admin (Festlegung 01.10.2026)
        a = client_fuer(self.admin)
        r = a.post("/api/praeparate/", neu, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(a.delete(f"/api/praeparate/{r.json()['id']}/").status_code, 405)
        r = a.patch(f"/api/praeparate/{r.json()['id']}/", {"aktiv": False}, format="json")
        self.assertFalse(r.json()["aktiv"])
        aktive = [p["anzeige"] for p in a.get("/api/praeparate/?kategorie=lipide&aktiv=true").json()]
        self.assertNotIn("Omegaven 10 %", aktive)
        self.assertIn("Omegaven 20 %", aktive)

    def test_auswahllisten_wie_im_entwurf(self):
        orte = list(Auswahlwert.objects.filter(liste="terminort").values_list("wert", flat=True))
        self.assertEqual(orte, ["Praxis Dr. Holtmeier"])
        katheter = list(Auswahlwert.objects.filter(liste="katheter").order_by("reihenfolge")
                        .values_list("wert", flat=True))
        self.assertEqual(katheter, ["Port", "Hickman", "Broviac", "PICC", "Port 1-Kammer", "Port 2-Kammer"])


class VersorgerUndAnsprechpartner(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.v = Versorger.objects.create(name="Homecare Nord")
        cls.ap1 = Ansprechpartner.objects.create(versorger=cls.v, name="Frau Alt", zustaendigkeit="Münsterland")
        cls.ap2 = Ansprechpartner.objects.create(versorger=cls.v, name="Herr Neu")
        cls.fremd = Ansprechpartner.objects.create(versorger=Versorger.objects.create(name="Andere GmbH"), name="X")
        cls.p1 = Patient.objects.create(nachname="Eins", vorname="E", geburtsdatum="1970-01-01",
                                        versorger=cls.v, ansprechpartner=cls.ap1)
        cls.p2 = Patient.objects.create(nachname="Zwei", vorname="Z", geburtsdatum="1971-01-01",
                                        versorger=cls.v, ansprechpartner=cls.ap1,
                                        abgeschlossen_am=timezone.localdate(), abschluss_anlass="verstorben")

    def test_rechte(self):
        neu = {"name": "Versorger aus Neuer Patient"}
        self.assertEqual(client_fuer(self.betrachter).post("/api/versorger/", neu, format="json").status_code, 403)
        self.assertEqual(client_fuer(self.mitarbeiter).post("/api/versorger/", neu, format="json").status_code, 201)
        ap = {"versorger": self.v.id, "name": "Frau Drei", "zustaendigkeit": "Ruhrgebiet"}
        self.assertEqual(client_fuer(self.mediziner).post("/api/ansprechpartner/", ap, format="json").status_code, 201)
        self.assertEqual(client_fuer(self.admin).delete(f"/api/versorger/{self.v.id}/").status_code, 405)

    def test_patienten_und_neu_zuordnen(self):
        c = client_fuer(self.mitarbeiter)
        daten = c.get(f"/api/ansprechpartner/{self.ap1.id}/").json()
        self.assertEqual((daten["patienten_anzahl"], daten["zustaendigkeit"]), (1, "Münsterland"))
        self.assertEqual([p["id"] for p in c.get(f"/api/ansprechpartner/{self.ap1.id}/patienten/").json()],
                         [self.p1.id])
        url = f"/api/ansprechpartner/{self.ap1.id}/neu-zuordnen/"
        for ziel in (self.fremd.id, self.ap1.id, 99999, None):
            with self.subTest(ziel=ziel):
                self.assertEqual(c.post(url, {"ziel": ziel}, format="json").status_code, 400)
        r = c.post(url, {"ziel": self.ap2.id}, format="json")
        self.assertEqual(r.json(), {"neu_zugeordnet": 1})
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.ansprechpartner, self.ap2)
        self.assertEqual(self.p2.ansprechpartner, self.ap1)  # abgeschlossene Akte bleibt unverändert
        v = c.get(f"/api/patienten/{self.p1.id}/verlauf/?bereich=stammdaten").json()
        self.assertEqual(v[0]["person"], self.mitarbeiter.anzeigename)
        self.assertIn("ansprechpartner", [a["feld"] for a in v[0]["aenderungen"]])


class EinstellungenPruefen(Grundlage):
    def test_grenzen_und_rechte(self):
        a = client_fuer(self.admin)
        self.assertEqual(client_fuer(self.mediziner).get("/api/einstellungen/").status_code, 200)
        self.assertEqual(client_fuer(self.betrachter).patch("/api/einstellungen/", {"kcal_max_tag": 3000},
                                                            format="json").status_code, 403)
        # Vorlagen pflegen auch Mitarbeiter (Festlegung 01.10.2026)
        self.assertEqual(client_fuer(self.mitarbeiter).patch("/api/einstellungen/", {"kcal_max_tag": 4900},
                                                             format="json").status_code, 200)
        self.assertEqual(client_fuer(self.mediziner).patch("/api/einstellungen/", {"kcal_max_tag": 4800},
                                                           format="json").status_code, 200)
        r = a.patch("/api/einstellungen/", {"glucose_min_g": 1200}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("glucose_min_g", r.json())
        r = a.patch("/api/einstellungen/", {"natrium_min_mmol": 10, "natrium_max_mmol": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        r = a.patch("/api/einstellungen/", {"kontakt_ueberfaellig_monate": 8, "kalium_max_mmol": 250}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        e = Einstellungen.aktuell()
        self.assertEqual((e.kontakt_ueberfaellig_monate, e.kalium_max_mmol), (8, 250))
        eintrag = a.get("/api/protokoll/?gruppe=vorlage").json()["results"][0]
        self.assertEqual(eintrag["gruppe_name"], "Vorlage")
        self.assertIn("„Kontakt überfällig“ von 6 auf 8 Monate geändert", eintrag["beschreibung"])
        self.assertIn("„Kalium maximal“ von 300 auf 250 mmol geändert", eintrag["beschreibung"])


def png_kopf(breite, hoehe):
    """Kopf einer PNG-Datei (für die Prüfung reichen Signatur und IHDR)."""
    return (b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + breite.to_bytes(4, "big")
            + hoehe.to_bytes(4, "big") + b"\x08\x06\x00\x00\x00" + b"\x00" * 64)


class BriefkopfUndLogo(Grundlage):
    def test_briefkopf_lesen_und_aendern(self):
        r = client_fuer(self.betrachter).get("/api/briefkopf/").json()
        self.assertEqual(r["aktiv"], "stiftung")
        self.assertEqual(r["absender"]["stiftung"]["strasse"], "Waltrup 16")
        self.assertEqual(r["absender"]["gug"]["name"], "")
        self.assertFalse(r["logo"]["vorhanden"])
        aenderung = {"aktiv": "gug", "absender": {"stiftung": {"telefon": "0251 98 11 401"},
                                                  "gug": {"name": "DSKM gUG", "ort": "Altenberge"}}}
        self.assertEqual(client_fuer(self.betrachter).patch("/api/briefkopf/", aenderung, format="json").status_code,
                         403)
        r = client_fuer(self.mediziner).patch("/api/briefkopf/", aenderung, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["aktiv"], r.json()["absender"]["gug"]["name"]), ("gug", "DSKM gUG"))
        texte = [e["beschreibung"] for e in client_fuer(self.admin).get("/api/protokoll/?gruppe=vorlage").json()["results"]]
        self.assertIn("Briefkopf (stiftung): „Telefon“ von 0251 98 11 400 auf 0251 98 11 401 geändert", texte)
        for falsch in ({"aktiv": "firma"}, {"absender": {"firma": {"name": "x"}}},
                       {"absender": {"stiftung": {"plz": "1" * 20}}}):
            with self.subTest(falsch=falsch):
                self.assertEqual(client_fuer(self.admin).patch("/api/briefkopf/", falsch, format="json").status_code,
                                 400)

    def test_logo(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from rest_framework.test import APIClient

        anonym = APIClient()
        self.assertEqual(anonym.get("/api/briefkopf/logo/").status_code, 404)
        a = client_fuer(self.admin)

        def hochladen(name, inhalt, client=a):
            return client.post("/api/briefkopf/logo/", {"datei": SimpleUploadedFile(name, inhalt)}, format="multipart")

        faelle = [
            ("schmal.png", png_kopf(500, 120), "600 px"),
            ("hoch.png", png_kopf(800, 900), "Querformat"),
            ("text.png", b"kein Bild", "PNG und SVG"),
            ("skript.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "Skripten"),
            ("ereignis.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="x()"></svg>', "Ereignis"),
            ("extern.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://x.example/a.png"/></svg>',
             "externen"),
        ]
        for name, inhalt, meldung in faelle:
            with self.subTest(name=name):
                r = hochladen(name, inhalt)
                self.assertEqual(r.status_code, 400, r.content)
                self.assertIn(meldung, r.json()["datei"])
        self.assertEqual(hochladen("logo.png", png_kopf(800, 280), client_fuer(self.betrachter)).status_code, 403)
        r = hochladen("logo.png", png_kopf(800, 280))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["logo"]["breite"], r.json()["logo"]["mime"]), (800, "image/png"))
        d = anonym.get("/api/briefkopf/logo/")
        self.assertEqual(d.status_code, 200)
        self.assertEqual(d["Content-Type"], "image/png")
        self.assertIn("default-src 'none'", d["Content-Security-Policy"])
        self.assertEqual(b"".join(d.streaming_content)[:8], b"\x89PNG\r\n\x1a\n")
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 100"><rect width="300" height="100"/></svg>'
        self.assertEqual(hochladen("logo.svg", svg).json()["logo"]["mime"], "image/svg+xml")
        self.assertEqual(anonym.get("/api/briefkopf/logo/")["Content-Type"], "image/svg+xml")


class Reihenfolge(Grundlage):
    def test_praeparate_und_auswahlwerte_sortieren(self):
        m = client_fuer(self.mediziner)
        ids = [p["id"] for p in m.get("/api/praeparate/?kategorie=aminosaeuren").json()]
        neu = list(reversed(ids))
        self.assertEqual(client_fuer(self.betrachter).post("/api/praeparate/reihenfolge/", {"ids": neu},
                                                           format="json").status_code, 403)
        r = m.post("/api/praeparate/reihenfolge/", {"ids": neu}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([p["id"] for p in m.get("/api/praeparate/?kategorie=aminosaeuren").json()], neu)
        gemischt = [ids[0], Praeparat.objects.get(name="Clinoleic").id]
        self.assertEqual(m.post("/api/praeparate/reihenfolge/", {"ids": gemischt}, format="json").status_code, 400)
        self.assertEqual(m.post("/api/praeparate/reihenfolge/", {"ids": "1,2"}, format="json").status_code, 400)
        orte = [a["id"] for a in m.get("/api/auswahlwerte/?liste=katheter").json()]
        r = m.post("/api/auswahlwerte/reihenfolge/", {"ids": orte[::-1]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual([a["id"] for a in m.get("/api/auswahlwerte/?liste=katheter").json()], orte[::-1])

    def test_seitengroesse(self):
        for i in range(3):
            Patient.objects.create(nachname=f"Seite{i}", vorname="S", geburtsdatum="1970-01-01")
        r = client_fuer(self.betrachter).get("/api/patienten/?seitengroesse=2").json()
        self.assertEqual(len(r["results"]), 2)
        self.assertIn("seitengroesse=2", r["next"])
