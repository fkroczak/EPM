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
