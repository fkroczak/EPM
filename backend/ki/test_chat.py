"""KI-Chat (12.11.2026): nur eigene Unterhaltungen, Promptvorlagen, Ablauf über den KI-Dienst, Gegenprüfung."""
import os
from pathlib import Path
from unittest import mock

from django.test import override_settings

from audit.models import SystemEreignis
from epm.pruefhilfen import Grundlage, client_fuer
from ki import chat
from ki.modell import Client
from ki.models import KiChat, KiChatNachricht, KiEinstellung, KiPromptvorlage
from ki.testhilfen import KI_TMP, ModellServer

N = KiChatNachricht


@override_settings(EPM_KI=Path(KI_TMP))
class KiChatTest(Grundlage):
    def senden(self, user, text="pat. hat seit 3 tagen fieber 38,5", vorlage=None, chat_id=None):
        c = client_fuer(user)
        if chat_id is None:
            chat_id = c.post("/api/ki/chats/", {}, format="json").json()["id"]
        daten = {"text": text}
        if vorlage is not None:
            daten["vorlage"] = vorlage
        return c.post(f"/api/ki/chats/{chat_id}/nachricht/", daten, format="json")

    def test_mitgelieferte_vorlagen(self):
        namen = list(KiPromptvorlage.objects.values_list("name", flat=True))
        self.assertIn("Medizinisch formulieren", namen)
        r = client_fuer(self.mitarbeiter).get("/api/ki/vorlagen/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.json()), len(namen))

    def test_nur_eigene_chats_auch_nicht_fuer_admin(self):
        r = self.senden(self.mitarbeiter)
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.json()["id"]
        self.assertEqual([m["rolle"] for m in r.json()["nachrichten"]], ["nutzer", "ki"])
        for andere in (self.mediziner, self.admin):
            c = client_fuer(andere)
            self.assertEqual(c.get("/api/ki/chats/").json(), [])
            self.assertEqual(c.get(f"/api/ki/chats/{cid}/").status_code, 404)
            self.assertEqual(c.post(f"/api/ki/chats/{cid}/nachricht/", {"text": "x"}, format="json").status_code, 404)
            self.assertEqual(c.delete(f"/api/ki/chats/{cid}/").status_code, 404)
        self.assertEqual(len(client_fuer(self.mitarbeiter).get("/api/ki/chats/").json()), 1)
        self.assertEqual(client_fuer(self.betrachter).get("/api/ki/chats/").status_code, 403)

    def test_inhalt_nicht_im_audit(self):
        self.senden(self.mitarbeiter, text="Geheimer Befundtext 4711")
        e = SystemEreignis.objects.filter(details__aktion="chat_nachricht").last()
        self.assertIsNotNone(e)
        self.assertNotIn("4711", str(e.details))

    def test_zweite_nachricht_erst_nach_antwort(self):
        cid = self.senden(self.mitarbeiter).json()["id"]
        r = self.senden(self.mitarbeiter, text="noch was", chat_id=cid)
        self.assertEqual(r.status_code, 409)

    def test_vorlage_geht_mit_und_dienst_antwortet(self):
        v = KiPromptvorlage.objects.get(name="Medizinisch formulieren")
        r = self.senden(self.mitarbeiter, vorlage=v.pk)
        n = N.objects.get(chat_id=r.json()["id"], rolle="ki")
        self.assertEqual((n.status, n.vorlage_name), ("wartet", v.name))
        with ModellServer("Seit 3 Tagen Fieber bis 38,5 °C, zuletzt 39,2 °C.") as s:
            holt = chat.holen()
            self.assertEqual(holt.pk, n.pk)
            with mock.patch.object(chat, "ZWISCHENSTAND_S", 0):
                chat.beantworten(holt, Client(s.url))
            gesendet = s.anfragen[0]
        n.refresh_from_db()
        self.assertEqual(n.status, "fertig", n.fehler)
        self.assertTrue(gesendet["stream"])
        self.assertEqual(n.text, "Seit 3 Tagen Fieber bis 38,5 °C, zuletzt 39,2 °C.")
        self.assertIn(chat.RAHMEN[:40], gesendet["messages"][0]["content"])
        self.assertIn(v.anweisung[:40], gesendet["messages"][0]["content"])
        self.assertEqual(gesendet["messages"][1], {"role": "user", "content": "pat. hat seit 3 tagen fieber 38,5"})
        self.assertAlmostEqual(gesendet["temperature"], 0.1)
        # 39,2 steht nirgends in der Eingabe → markiert
        self.assertEqual(n.pruefung["neue_werte"], ["39,2"])
        self.assertFalse(n.pruefung["ok"])
        # danach geht die nächste Nachricht, mit Verlauf
        cid = r.json()["id"]
        self.assertEqual(self.senden(self.mitarbeiter, text="kürzer bitte", chat_id=cid).status_code, 201)
        n2 = chat.holen()
        self.assertEqual([m["role"] for m in chat.verlauf(n2)], ["user", "assistant", "user"])

    def test_modell_nicht_erreichbar_wieder_in_die_queue(self):
        from ki.modell import ModellFehler

        cid = self.senden(self.mitarbeiter).json()["id"]
        with ModellServer(status=500) as s:
            for versuch in range(1, chat.MAX_VERSUCHE + 1):
                n = chat.holen()
                self.assertIsNotNone(n)
                with self.assertRaises(ModellFehler):
                    chat.beantworten(n, Client(s.url))
                n.refresh_from_db()
                self.assertEqual(n.versuche, versuch)
                self.assertEqual(n.status, "wartet" if versuch < chat.MAX_VERSUCHE else "fehler")
        self.assertIsNone(chat.holen())
        self.assertEqual(N.objects.get(chat_id=cid, rolle="ki").status, "fehler")

    def test_zu_lange_wartend(self):
        import datetime as dt

        from django.utils import timezone

        cid = self.senden(self.mitarbeiter).json()["id"]
        N.objects.filter(chat_id=cid).update(erstellt_am=timezone.now() - dt.timedelta(minutes=16))
        self.assertEqual(chat.zu_lange_wartend(), 1)
        n = N.objects.get(chat_id=cid, rolle="ki")
        self.assertEqual(n.status, "fehler")
        self.assertIn("nicht bereit", n.fehler)

    @mock.patch.dict(os.environ, {"KI_HARDWARE_PRUEFEN": "0"})
    def test_dienst_ohne_modell_meldet_fehler(self):
        from ki.management.commands.epm_ki import Dienst

        KiEinstellung.laden()
        KiEinstellung.objects.filter(pk=1).update(max_cpu_prozent=100, min_ram_frei_mb=256, max_last_je_kern=10)
        cid = self.senden(self.mitarbeiter).json()["id"]
        with override_settings(EPM_KI_MODELL_URL=""):
            Dienst(einmal=True).laufen()
        n = N.objects.get(chat_id=cid, rolle="ki")
        self.assertEqual(n.status, "fehler")
        self.assertIn("Kein KI-Modell", n.fehler)

    def test_vorlagen_pflegen(self):
        daten = {"name": "Entlassbrief Abschnitt", "anweisung": "Schreibe …", "temperatur": "0.2"}
        self.assertEqual(client_fuer(self.betrachter).post("/api/ki/vorlagen/", daten, format="json").status_code, 403)
        c = client_fuer(self.admin)
        r = c.post("/api/ki/vorlagen/", daten, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(c.post("/api/ki/vorlagen/", {**daten, "name": "x", "temperatur": "2"},
                                format="json").status_code, 400)
        mit = KiPromptvorlage.objects.filter(mitgeliefert=True).first()
        self.assertEqual(c.delete(f"/api/ki/vorlagen/{mit.pk}/").status_code, 400)
        self.assertEqual(c.patch(f"/api/ki/vorlagen/{mit.pk}/", {"aktiv": False}, format="json").status_code, 200)
        self.assertNotIn(mit.pk, [v["id"] for v in client_fuer(self.mitarbeiter).get("/api/ki/vorlagen/").json()])
        self.assertEqual(c.delete(f"/api/ki/vorlagen/{r.json()['id']}/").status_code, 204)

    def test_alte_chats_werden_geloescht(self):
        import datetime as dt

        from django.utils import timezone

        cid = self.senden(self.mitarbeiter).json()["id"]
        KiChat.objects.filter(pk=cid).update(aktualisiert_am=timezone.now() - dt.timedelta(days=31))
        chat.aufraeumen(dt.timedelta(minutes=5))
        self.assertFalse(KiChat.objects.filter(pk=cid).exists())


class ChatInPauseTest(Grundlage):
    def test_chat_auch_bei_last_pause_nicht_bei_sicherung(self):
        from ki.management.commands.epm_ki import Dienst
        from ki.steuerung import Entscheidung

        d = Dienst(einmal=True)
        d.client, d.modell_bereit = object(), True
        self.assertTrue(d._chat_erlaubt(Entscheidung("pause", 0, True, grund="CPU 92 %", last={"sicherung_laeuft": False})))
        self.assertFalse(d._chat_erlaubt(Entscheidung("pause", 0, True, grund="Sicherung", last={"sicherung_laeuft": True})))
        self.assertFalse(d._chat_erlaubt(Entscheidung("aus", 0, True)))
        d.modell_bereit = False
        self.assertFalse(d._chat_erlaubt(Entscheidung("pause", 0, True, last={})))
        self.assertTrue(d._chat_erlaubt(Entscheidung("tag", 1, True)))

    def test_last_pause_bricht_laufenden_vorgang_nicht_ab(self):
        from types import SimpleNamespace
        from ki.management.commands.epm_ki import Dienst
        from ki.steuerung import Entscheidung

        d, v = Dienst(einmal=True), SimpleNamespace(prioritaet=0)
        d.entscheidung = Entscheidung("pause", 0, True, grund="CPU 74 %", wegen_last=True)
        self.assertIsNone(d._abbrechen(v))
        d.entscheidung = Entscheidung("pause", 0, True, grund="Die Sicherung läuft.")
        self.assertEqual(d._abbrechen(v), "Die Sicherung läuft.")
        d.entscheidung = Entscheidung("aus", 0, True, grund="aus")
        self.assertEqual(d._abbrechen(v), "aus")

    def test_tagsueber_hat_der_chat_vorrang(self):
        from types import SimpleNamespace
        from ki.management.commands.epm_ki import Dienst
        from ki.steuerung import Entscheidung

        d, v = Dienst(), SimpleNamespace(prioritaet=10)  # angefordert
        d.entscheidung = Entscheidung("tag", 1, True)
        self.assertIsNone(d._abbrechen(v))
        d.chat_aktiv = True
        self.assertEqual(d._abbrechen(v), "Chat hat tagsüber Vorrang")
        d.entscheidung = Entscheidung("nacht", 1, False)
        self.assertIsNone(d._abbrechen(v))


@override_settings(EPM_KI=Path(KI_TMP))
class GeradeInArbeitTest(Grundlage):
    def test_dokument_schritt_und_chat_ohne_inhalt(self):
        from django.utils import timezone

        from ki.testhilfen import dokument
        from ki.models import KiVorgang

        d = dokument(self.patient, b"%PDF-1.4 x", name="Labor.pdf", mime="application/pdf")
        v = KiVorgang.objects.create(dokument=d, patient=self.patient, firma_id=d.firma_id, sha256=d.sha256,
                                     status="in_verarbeitung", schritt="Seite 2 von 3: Modell liest", fortschritt=55,
                                     begonnen_am=timezone.now(), ist_test=self.patient.ist_test)
        c = KiChat.objects.create(benutzer=self.mediziner)
        N.objects.create(chat=c, rolle="ki", status="laeuft", text="geheim")
        a = client_fuer(self.mitarbeiter).get("/api/ki/stand/").json()["arbeit"]
        self.assertEqual([x["id"] for x in a["dokumente"]], [v.pk])
        self.assertEqual((a["dokumente"][0]["schritt"], a["dokumente"][0]["fortschritt"]), ("Seite 2 von 3: Modell liest", 55))
        self.assertEqual((a["chats"], a["chat_eigener"]), (1, False))
        self.assertNotIn("geheim", str(a))
        self.assertTrue(client_fuer(self.mediziner).get("/api/ki/stand/").json()["arbeit"]["chat_eigener"])

    def test_protokoll_zeigt_was_bearbeitet_wird(self):
        from ki import pipeline
        from ki.management.commands.epm_ki import Dienst
        from ki.models import KiVorgang
        from ki.steuerung import Entscheidung
        from ki.testhilfen import dokument

        d = dokument(self.patient, b"%PDF-1.4 y", name="Arztbrief Anna Echt.pdf", mime="application/pdf")
        v = KiVorgang.objects.create(dokument=d, patient=self.patient, firma_id=d.firma_id, sha256=d.sha256,
                                     status="in_verarbeitung", ist_test=self.patient.ist_test)

        def verarbeiten(vorgang, rahmen, paddle=None):
            rahmen.schritt("Seite 1 von 1: Texterkennung", 40)
            KiVorgang.objects.filter(pk=vorgang.pk).update(status="zur_pruefung", dokumenttyp="arztbericht")

        dienst = Dienst(einmal=True)
        dienst.entscheidung = Entscheidung("nacht", 1, False)
        with mock.patch.object(pipeline, "verarbeiten", verarbeiten), self.assertLogs("epm.ki", "INFO") as logs:
            dienst._vorgang(v)
        text = "\n".join(logs.output)
        self.assertIn(f"KI-Vorgang Nr. {v.pk} gestartet: Dokument {d.pk}, Akte Nr. {self.patient.nummer}", text)
        self.assertIn("Seite 1 von 1: Texterkennung (40 %)", text)
        self.assertIn("fertig nach", text)
        self.assertIn("Typ arztbericht", text)
        self.assertNotIn("Echt", text)  # keine Namen im Protokoll


def pdf_mit_text(*seiten: str) -> bytes:
    """PDF mit Textebene (ohne Texterkennung lesbar)."""
    import io

    from reportlab.pdfgen import canvas

    puffer = io.BytesIO()
    c = canvas.Canvas(puffer)
    for text in seiten:
        for i, zeile in enumerate(text.splitlines()):
            c.drawString(72, 760 - 16 * i, zeile)
        c.showPage()
    c.save()
    return puffer.getvalue()


@override_settings(EPM_KI=Path(KI_TMP))
class ChatDokumenteTest(Grundlage):
    def neuer_chat(self, user=None):
        return client_fuer(user or self.mitarbeiter).post("/api/ki/chats/", {}, format="json").json()["id"]

    def test_hochladen_ohne_seitengrenze_text_erkannt_datei_geloescht(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from ki.models import KiChatAnhang

        seiten = [f"Laborbefund Seite {i}\nKalium 3,{i} mmol/l am 01.09.2026\nNatrium 138 mmol/l" for i in range(1, 13)]
        cid = self.neuer_chat()
        r = client_fuer(self.mitarbeiter).post(f"/api/ki/chats/{cid}/nachricht/", {
            "text": "Welche Kaliumwerte stehen drin?",
            "dateien": SimpleUploadedFile("labor.pdf", pdf_mit_text(*seiten), content_type="application/pdf")},
            format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["nachrichten"][0]["anhaenge"][0]["name"], "labor.pdf")
        n = chat.holen()
        with ModellServer("Kalium 3,1 bis 3,12 mmol/l.") as s:
            chat.beantworten(n, Client(s.url))
            gesendet = s.anfragen[-1]
        n.refresh_from_db()
        self.assertEqual(n.status, "fertig", n.fehler)
        a = KiChatAnhang.objects.get()
        self.assertEqual((a.status, a.seiten), ("fertig", 12))
        self.assertIsNone(a.datei)  # hochgeladene Datei ist nach der Erkennung weg
        self.assertIn("Kalium\t3,7\tmmol/l", a.text)
        letzte = gesendet["messages"][-1]["content"]
        self.assertIn('<dokument name="labor.pdf">', letzte)
        self.assertIn("[Seite 12]", letzte)
        self.assertIn("Anfrage:\nWelche Kaliumwerte stehen drin?\n\n[Angehängt: labor.pdf]", letzte)
        self.assertEqual(n.pruefung["neue_werte"], [])  # Werte aus dem Dokument gelten als Eingabe
        e = SystemEreignis.objects.filter(details__aktion="chat_nachricht").last()
        self.assertEqual(e.details["dateien"], 1)

    def test_falsches_format(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        cid = self.neuer_chat()
        r = client_fuer(self.mitarbeiter).post(f"/api/ki/chats/{cid}/nachricht/", {
            "dateien": SimpleUploadedFile("notiz.txt", b"nur Text")}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("notiz.txt", str(r.json()))

    def test_aus_der_akte_mit_vorhandenem_text_und_protokoll(self):
        from django.utils import timezone

        from ki.models import KiChatAnhang
        from ki.testhilfen import dokument
        from patienten.models import DokumentText

        dok = dokument(self.patient, b"%PDF-1.4 x", name="a.pdf", mime="application/pdf", titel="Entlassbrief")
        DokumentText.objects.create(dokument=dok, text="Diagnose: Eisenmangel, Ferritin 8 ng/ml",
                                    erkannt_am=timezone.now())
        cid = self.neuer_chat()
        r = client_fuer(self.mitarbeiter).post(f"/api/ki/chats/{cid}/nachricht/",
                                              {"text": "Fasse zusammen", "dokumente": [dok.pk]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        e = SystemEreignis.objects.filter(details__aktion="chat_dokument_aus_akte").last()
        self.assertEqual((e.details["dokument"], e.details["patient_id"]), (dok.pk, self.patient.pk))
        with ModellServer("Eisenmangel, Ferritin 8 ng/ml.") as s:
            chat.beantworten(chat.holen(), Client(s.url))
            letzte = s.anfragen[-1]["messages"][-1]["content"]
        self.assertIn("Ferritin 8 ng/ml", letzte)
        self.assertEqual(KiChatAnhang.objects.get().status, "fertig")
        # wird das Dokument endgültig gelöscht, geht der Auszug mit
        dok.delete()
        self.assertFalse(KiChatAnhang.objects.exists())

    def test_akte_ohne_zugriff_nicht_waehlbar(self):
        from ki.testhilfen import dokument

        dok = dokument(self.patient, b"%PDF-1.4 x", name="a.pdf", mime="application/pdf")
        self.patient.ist_test = False
        cid = self.neuer_chat()
        for wert in (dok.pk + 999, "x"):
            r = client_fuer(self.mitarbeiter).post(f"/api/ki/chats/{cid}/nachricht/",
                                                  {"text": "x", "dokumente": [wert]}, format="json")
            self.assertEqual(r.status_code, 400, r.content)

    def test_lange_unterlagen_teil_fuer_teil(self):
        from ki.models import KiChatAnhang

        cid = self.neuer_chat()
        frage = client_fuer(self.mitarbeiter).post(f"/api/ki/chats/{cid}/nachricht/", {"text": "Kaliumwerte?"},
                                                  format="json")
        self.assertEqual(frage.status_code, 201)
        nutzer = N.objects.get(chat_id=cid, rolle="nutzer")
        text = "\n\n".join(f"[Seite {i}]\nKalium 3,{i % 10} mmol/l " + "Fließtext " * 300 for i in range(1, 41))
        KiChatAnhang.objects.create(nachricht=nutzer, herkunft="upload", name="akte.pdf", status="fertig",
                                    text=text, seiten=40, seiten_fertig=40)
        with ModellServer("- Kalium 3,1 mmol/l (Seite 1)", kontext=8192) as s:
            chat.beantworten(chat.holen(), Client(s.url))
            teile = [a for a in s.anfragen if not a.get("stream")]
            letzte = s.anfragen[-1]
        self.assertGreater(len(teile), 3)
        self.assertIn("Teil 1 von", teile[0]["messages"][1]["content"][0]["text"])
        self.assertTrue(letzte["stream"])
        self.assertIn("Auszüge aus den Unterlagen", letzte["messages"][-1]["content"])
        self.assertLess(len(letzte["messages"][-1]["content"]) // 4, 8192)
        n = N.objects.get(chat_id=cid, rolle="ki")
        self.assertEqual((n.status, n.schritt), ("fertig", ""))
