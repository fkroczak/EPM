"""Korrekturen als Beispiele im Prompt (ki/beispiele.py) und Diktat → gegliederter Bericht (KI-Chat), 14.11.2026."""
from pathlib import Path
from unittest import mock

from django.test import override_settings

from berichte.models import Bericht
from diktate.models import Diktat
from epm.pruefhilfen import Grundlage, client_fuer
from ki import beispiele, chat, eingang, pipeline
from ki.modell import Client
from ki.models import KiChatNachricht, KiEinstellung, KiFeld, KiKorrektur, KiPromptvorlage, KiRohergebnis, KiVorgang
from ki.testhilfen import KI_TMP, Attrappe, ModellServer, dokument, labor_png
from stammdaten.models import Firma


@override_settings(EPM_KI=Path(KI_TMP))
class KorrekturBeispieleTest(Grundlage):
    def setUp(self):
        super().setUp()
        self.a = self.vorgang(labor_png(nachname="Echt", vorname="Anna"))

    def vorgang(self, daten) -> KiVorgang:
        dok = dokument(self.patient, daten)
        eingang.vormerken()
        v = KiVorgang.objects.get(dokument=dok)
        return pipeline.verarbeiten(v, pipeline.Rahmen(client=Attrappe()))

    def korrigieren(self, v: KiVorgang, parameter="Kalium", **neu):
        f = v.felder.get(gruppe="labor", wert__parameter_name=parameter)
        f.korrigiert = {**f.wert, **neu}
        f.save()
        KiKorrektur.objects.create(feld=f, version=1, alt=f.wert, neu=f.korrigiert,
                                   fehlerart=KiKorrektur.Fehlerart.LESEFEHLER, benutzer=self.mitarbeiter)
        return f

    def test_korrektur_geht_als_beispiel_an_das_naechste_dokument(self):
        self.korrigieren(self.a, wert="3.4")
        b_dok = dokument(self.patient, labor_png(nachname="Echt", vorname="Anna") + b"\0")
        eingang.vormerken()
        b = KiVorgang.objects.get(dokument=b_dok)
        modell = Attrappe()
        pipeline.verarbeiten(b, pipeline.Rahmen(client=modell))
        text = next(a["text"] for a in modell.anfragen if a["schema"])
        self.assertIn("Frühere Korrekturen", text)
        self.assertIn("- Laborwert: gelesen „Kalium 3,2 mmol/l“ → richtig „Kalium 3,4 mmol/l“ "
                      "(Zeichen falsch gelesen (OCR))", text)
        roh = KiRohergebnis.objects.get(vorgang=b, art="extraktion")
        self.assertEqual(roh.parameter["korrekturhinweise"], 1)
        # der Vorgang selbst bekommt seine eigenen Korrekturen nicht als Beispiel
        self.assertEqual(beispiele.korrekturhinweise(self.a), ("", 0))

    def test_ausgeschaltet_andere_firma_und_testdaten_nicht(self):
        self.korrigieren(self.a, wert="3.4")
        b = self.vorgang(labor_png(nachname="Echt", vorname="Anna") + b"\0")
        self.assertEqual(beispiele.korrekturhinweise(b)[1], 1)
        KiEinstellung.objects.update(beispiele_max=0)
        self.assertEqual(beispiele.korrekturhinweise(b), ("", 0))
        KiEinstellung.objects.update(beispiele_max=12)
        andere = Firma.objects.exclude(pk=self.a.firma_id).first()
        KiVorgang.objects.filter(pk=b.pk).update(firma=andere)
        b.refresh_from_db()
        self.assertEqual(beispiele.korrekturhinweise(b), ("", 0))
        KiVorgang.objects.filter(pk=b.pk).update(firma=self.a.firma, ist_test=not self.a.ist_test)
        b.refresh_from_db()
        self.assertEqual(beispiele.korrekturhinweise(b), ("", 0))

    def test_gleicher_absender_zuerst_und_nur_lehrreiche_felder(self):
        self.korrigieren(self.a, wert="3.4")
        self.korrigieren(self.a, parameter="Natrium", datum="2026-08-01")  # nur das Datum → kein Beispiel
        patient = self.a.felder.get(schluessel="patient")
        patient.korrigiert = {**patient.wert, "name": "Echt, Anna"}
        patient.save()
        KiKorrektur.objects.create(feld=patient, version=1, alt=patient.wert, neu=patient.korrigiert,
                                   benutzer=self.mitarbeiter)
        b = self.vorgang(labor_png(nachname="Echt", vorname="Anna") + b"\0")
        text, n = beispiele.korrekturhinweise(b, absender="Labor Dr. Beispiel")
        self.assertEqual(n, 1)
        self.assertIn("desselben Absenders", text)
        self.assertNotIn("Echt", text)
        self.assertNotIn("2026", text)
        text, n = beispiele.korrekturhinweise(b, absender="Ganz anderes Labor")
        self.assertEqual(n, 1)
        self.assertNotIn("desselben Absenders", text)

    def test_zeile_je_gruppe(self):
        f = KiFeld(gruppe="meta", schluessel="dokumenttyp", wert={"wert": "verlauf"}, korrigiert={"wert": "labor"})
        self.assertEqual(beispiele.zeile(f), "- Dokumenttyp: gelesen „verlauf“ → richtig „labor“")
        f = KiFeld(gruppe="infusion", schluessel="position", wert={"substanz": "NaCl 0,9%", "menge": "50", "einheit": "ml"},
                   korrigiert={"substanz": "NaCl 0,9%", "menge": "500", "einheit": "ml"})
        self.assertEqual(beispiele.zeile(f), "- Infusion: gelesen „NaCl 0,9% 50 ml“ → richtig „NaCl 0,9% 500 ml“")
        self.assertIsNone(beispiele.zeile(KiFeld(gruppe="text", schluessel="verlauf", wert={"text": "a"},
                                                 korrigiert={"text": "b"})))


@override_settings(EPM_KI=Path(KI_TMP))
class DiktatGliedernTest(Grundlage):
    def diktat(self, **extra) -> Diktat:
        b = Bericht.objects.create(patient=self.patient, titel="Arztbrief", erstellt_von=self.mediziner)
        daten = {"patient": self.patient, "bericht": b, "status": Diktat.Status.FERTIG, "erstellt_von": self.mediziner,
                 "text": "<p>Diagnose Kurzdarmsyndrom.</p><p>Kalium 3,2 &amp; Natrium 138<br>Termin am 1.12.2026</p>"}
        return Diktat.objects.create(**{**daten, **extra})

    def test_diktat_wird_zum_chat_und_entwurf_mit_gegenpruefung(self):
        d = self.diktat()
        r = client_fuer(self.mediziner).post("/api/ki/chats/diktat/", {"diktat": d.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        frage, antwort = r.json()["nachrichten"]
        self.assertEqual(frage["text"], "Berichtsart: Arztbrief\n\nAbschrift des Diktats:\nDiagnose Kurzdarmsyndrom."
                                        "\n\nKalium 3,2 & Natrium 138\nTermin am 1.12.2026")
        self.assertEqual((antwort["status"], antwort["vorlage_name"]), ("wartet", chat.DIKTAT_VORLAGE))
        n = KiChatNachricht.objects.get(pk=antwort["id"])
        self.assertEqual(n.anweisung, KiPromptvorlage.objects.get(name=chat.DIKTAT_VORLAGE).anweisung)
        self.assertEqual(n.anweisung, chat.DIKTAT_ANWEISUNG)
        with ModellServer("## Diagnosen\n- Kurzdarmsyndrom\n\n## Befund\nKalium 3,4, Natrium 138.") as s:
            with mock.patch.object(chat, "ZWISCHENSTAND_S", 0):
                chat.beantworten(chat.holen(), Client(s.url))
        n.refresh_from_db()
        self.assertEqual(n.status, "fertig", n.fehler)
        self.assertEqual(n.pruefung["neue_werte"], ["3,4"])
        self.assertEqual(n.pruefung["fehlende_werte"], ["1.12.2026", "3,2"])
        # nur die eigene Unterhaltung
        self.assertEqual(client_fuer(self.admin).get(f"/api/ki/chats/{r.json()['id']}/").status_code, 404)

    def test_ohne_vorlage_gilt_der_eingebaute_text(self):
        KiPromptvorlage.objects.filter(name=chat.DIKTAT_VORLAGE).update(aktiv=False)
        r = client_fuer(self.mediziner).post("/api/ki/chats/diktat/", {"diktat": self.diktat().pk}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(KiChatNachricht.objects.get(pk=r.json()["nachrichten"][1]["id"]).anweisung,
                         chat.DIKTAT_ANWEISUNG)

    def test_nicht_abgeschrieben_unbekannt_und_ohne_recht(self):
        c = client_fuer(self.mediziner)
        r = c.post("/api/ki/chats/diktat/", {"diktat": self.diktat(status=Diktat.Status.WARTET, text="").pk},
                   format="json")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(c.post("/api/ki/chats/diktat/", {"diktat": 999999}, format="json").status_code, 404)
        r = client_fuer(self.betrachter).post("/api/ki/chats/diktat/", {"diktat": self.diktat().pk}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    def test_html_zu_text(self):
        self.assertEqual(chat.html_zu_text("<h3>Befund</h3><p>a<br/>b</p><ul><li>x</li></ul>"), "Befund\n\na\nb\n\nx")
