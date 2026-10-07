"""Passkeys (WebAuthn) als zweiter Faktor (Festlegung 08.10.2026, F130–F132): einrichten, anmelden, bestätigen,
entfernen – mit einem Software-Authenticator, der echte Signaturen erzeugt (P-256, Format „none“)."""
import hashlib
import json
import os
import shutil
import struct
import tempfile
from pathlib import Path

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from django.test import override_settings
from rest_framework.test import APIClient
from webauthn.helpers import bytes_to_base64url

from audit.models import SystemEreignis
from epm.pruefhilfen import KENNWORT, Grundlage, benutzer, client_fuer, mit_zweitem_faktor

from .models import Anmelderegeln, Passkey, Rolle

HERKUNFT = "https://epm.test"


class SoftwareAuthenticator:
    """Verhält sich wie ein Passkey im Browser: erzeugt Schlüssel, signiert Anfragen, zählt hoch."""

    def __init__(self, origin=HERKUNFT, rp_id="epm.test"):
        self.origin = origin
        self.rp_id = rp_id
        self.schluessel = ec.generate_private_key(ec.SECP256R1())
        self.kennung = os.urandom(32)
        self.zaehler = 0

    def _client_data(self, art, challenge):
        return json.dumps({"type": art, "challenge": challenge, "origin": self.origin,
                           "crossOrigin": False}).encode()

    def _rp_hash(self):
        return hashlib.sha256(self.rp_id.encode()).digest()

    def erzeugen(self, optionen):
        zahlen = self.schluessel.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: zahlen.x.to_bytes(32, "big"), -3: zahlen.y.to_bytes(32, "big")})
        auth = (self._rp_hash() + bytes([0x01 | 0x04 | 0x40]) + struct.pack(">I", self.zaehler)
                + b"\0" * 16 + struct.pack(">H", len(self.kennung)) + self.kennung + cose)
        objekt = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth})
        kennung = bytes_to_base64url(self.kennung)
        return {"id": kennung, "rawId": kennung, "type": "public-key", "clientExtensionResults": {},
                "authenticatorAttachment": "platform",
                "response": {"clientDataJSON": bytes_to_base64url(self._client_data("webauthn.create", optionen["challenge"])),
                             "attestationObject": bytes_to_base64url(objekt), "transports": ["internal", "hybrid"]}}

    def signieren(self, optionen, flags=0x01 | 0x04):
        self.zaehler += 1
        auth = self._rp_hash() + bytes([flags]) + struct.pack(">I", self.zaehler)
        client = self._client_data("webauthn.get", optionen["challenge"])
        signatur = self.schluessel.sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        kennung = bytes_to_base64url(self.kennung)
        return {"id": kennung, "rawId": kennung, "type": "public-key", "clientExtensionResults": {},
                "response": {"clientDataJSON": bytes_to_base64url(client),
                             "authenticatorData": bytes_to_base64url(auth),
                             "signature": bytes_to_base64url(signatur), "userHandle": None}}


def anmelden_mit_kennwort(user):
    c = APIClient(HTTP_USER_AGENT="Mozilla/5.0 (iPhone) Safari/18")
    r = c.post("/api/auth/anmelden/", {"benutzername": user.username, "kennwort": KENNWORT}, format="json")
    assert r.status_code == 200, r.content
    return c, r.json()


@override_settings(EPM_PASSKEY_ORIGINS=[HERKUNFT], EPM_PASSKEY_RP_ID="")
class Passkeys(Grundlage):
    def einrichten(self, client, geraet=None, name="iPhone"):
        geraet = geraet or SoftwareAuthenticator()
        r = client.post("/api/auth/passkey/optionen/", {"zweck": "registrieren"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        optionen = r.json()
        self.assertEqual(optionen["rp"]["id"], "epm.test")
        self.assertEqual(optionen["authenticatorSelection"]["userVerification"], "required")
        r = client.post("/api/auth/passkey/registrieren/", {"antwort": geraet.erzeugen(optionen), "name": name},
                        format="json")
        self.assertEqual(r.status_code, 200, r.content)
        return geraet, r.json()

    def test_einrichten_in_mein_konto_und_anmelden(self):
        """F130/F131: Passkey unter Mein Konto einrichten (erster zweiter Faktor → Notfall-Codes), danach meldet sich
        die Person mit Kennwort und Passkey an; der Code der App wird nicht gebraucht."""
        user = benutzer("pk_mitarbeiter", Rolle.MITARBEITER)
        c, status = anmelden_mit_kennwort(user)
        self.assertEqual(status["schritt"], "fertig")           # zweiter Faktor freiwillig
        self.assertTrue(status["passkey"]["verfuegbar"])
        geraet, antwort = self.einrichten(c)
        self.assertEqual(len(antwort["notfallcodes"]), 10)
        self.assertEqual(antwort["passkey_neu"]["name"], "iPhone")
        self.assertTrue(antwort["benutzer"]["passkey"])
        self.assertFalse(antwort["benutzer"]["authenticator"])
        self.assertTrue(antwort["benutzer"]["zweiter_faktor"])
        self.assertEqual(c.get("/api/auth/sicherheit/").json()["passkeys"][0]["name"], "iPhone")
        self.assertTrue(SystemEreignis.objects.filter(art=SystemEreignis.Art.ZWEITER_FAKTOR_EINGERICHTET,
                                                      benutzer=user, details__passkey="iPhone").exists())

        # neue Anmeldung: nach dem Kennwort fehlt der zweite Faktor, angeboten wird der Passkey
        c2, status = anmelden_mit_kennwort(user)
        self.assertEqual(status["schritt"], "2fa")
        self.assertEqual(status["faktoren"], {"authenticator": False, "passkey": True})
        self.assertEqual(c2.get("/api/patienten/").status_code, 403)  # vorher kein Zugriff
        optionen = c2.post("/api/auth/passkey/optionen/", {"zweck": "anmelden"}, format="json").json()
        self.assertEqual([x["id"] for x in optionen["allowCredentials"]], [bytes_to_base64url(geraet.kennung)])
        r = c2.post("/api/auth/passkey/", {"antwort": geraet.signieren(optionen)}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["schritt"], "fertig")
        self.assertEqual(c2.get("/api/patienten/").status_code, 200)
        p = Passkey.objects.get(user=user)
        self.assertEqual(p.sign_count, 1)
        self.assertIsNotNone(p.zuletzt_am)
        self.assertTrue(SystemEreignis.objects.filter(art=SystemEreignis.Art.ANMELDUNG, benutzer=user,
                                                      details__schritt="passkey").exists())

    def test_erste_anmeldung_mit_pflicht_passkey_statt_app(self):
        """Ist der zweite Faktor Pflicht, kann ihn die Person bei der ersten Anmeldung auch als Passkey einrichten."""
        Anmelderegeln.objects.update_or_create(pk=1, defaults={"zweiter_faktor": Anmelderegeln.ZweiterFaktor.ALLE})
        user = benutzer("pk_pflicht", Rolle.MEDIZINER)
        c, status = anmelden_mit_kennwort(user)
        self.assertEqual(status["schritt"], "2fa_einrichten")
        _, antwort = self.einrichten(c, name="Windows Hello")
        self.assertEqual(antwort["schritt"], "fertig")
        self.assertEqual(len(antwort["notfallcodes"]), 10)
        self.assertEqual(c.get("/api/patienten/").status_code, 200)

    def test_antwort_gilt_nur_einmal_und_nur_fuer_diese_herkunft(self):
        user = benutzer("pk_wiederholung", Rolle.MITARBEITER)
        c, _ = anmelden_mit_kennwort(user)
        geraet, _ = self.einrichten(c)
        c2, _ = anmelden_mit_kennwort(user)
        # andere Seite (Phishing): Herkunft passt nicht → abgelehnt, zählt als Fehlversuch
        optionen = c2.post("/api/auth/passkey/optionen/", {"zweck": "anmelden"}, format="json").json()
        fremd = SoftwareAuthenticator(origin="https://epm-anmeldung.example")
        fremd.schluessel, fremd.kennung = geraet.schluessel, geraet.kennung
        r = c2.post("/api/auth/passkey/", {"antwort": fremd.signieren(optionen)}, format="json")
        self.assertEqual(r.status_code, 401, r.content)
        # Antwort auf eine andere Aufgabe des Servers → abgelehnt
        optionen = c2.post("/api/auth/passkey/optionen/", {"zweck": "anmelden"}, format="json").json()
        r = c2.post("/api/auth/passkey/", {"antwort": geraet.signieren({**optionen, "challenge": "ZmFsc2No"})},
                    format="json")
        self.assertEqual(r.status_code, 401, r.content)
        user.refresh_from_db()
        self.assertEqual(user.fehlversuche, 2)
        # gültige Antwort: angemeldet; dieselbe Antwort ein zweites Mal findet keine offene Aufgabe mehr
        optionen = c2.post("/api/auth/passkey/optionen/", {"zweck": "anmelden"}, format="json").json()
        antwort = geraet.signieren(optionen)
        self.assertEqual(c2.post("/api/auth/passkey/", {"antwort": antwort}, format="json").status_code, 200)
        self.assertEqual(c2.post("/api/auth/passkey/", {"antwort": antwort}, format="json").status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.fehlversuche, 0)

    def test_ohne_bestaetigung_durch_den_nutzer_abgelehnt(self):
        """User Verification ist Pflicht (Fingerabdruck, Gesicht oder PIN) – nur „anwesend“ reicht nicht."""
        user = benutzer("pk_ohne_uv", Rolle.MITARBEITER)
        c, _ = anmelden_mit_kennwort(user)
        geraet, _ = self.einrichten(c)
        c2, _ = anmelden_mit_kennwort(user)
        optionen = c2.post("/api/auth/passkey/optionen/", {"zweck": "anmelden"}, format="json").json()
        r = c2.post("/api/auth/passkey/", {"antwort": geraet.signieren(optionen, flags=0x01)}, format="json")
        self.assertEqual(r.status_code, 401, r.content)

    def test_fremder_passkey_passt_nicht(self):
        a = benutzer("pk_a", Rolle.MITARBEITER)
        b = benutzer("pk_b", Rolle.MITARBEITER)
        ca, _ = anmelden_mit_kennwort(a)
        geraet_a, _ = self.einrichten(ca)
        cb, _ = anmelden_mit_kennwort(b)
        self.einrichten(cb)
        cb2, _ = anmelden_mit_kennwort(b)
        optionen = cb2.post("/api/auth/passkey/optionen/", {"zweck": "anmelden"}, format="json").json()
        r = cb2.post("/api/auth/passkey/", {"antwort": geraet_a.signieren(optionen)}, format="json")
        self.assertEqual(r.status_code, 401, r.content)

    def test_ueber_ip_adresse_nicht_verfuegbar(self):
        user = benutzer("pk_ip", Rolle.MITARBEITER)
        c, _ = anmelden_mit_kennwort(user)
        with override_settings(EPM_PASSKEY_ORIGINS=["https://192.168.1.154"]):
            status = c.get("/api/auth/status/").json()
            self.assertFalse(status["passkey"]["verfuegbar"])
            self.assertIn("IP-Adresse", status["passkey"]["grund"])
            r = c.post("/api/auth/passkey/optionen/", {"zweck": "registrieren"}, format="json")
            self.assertEqual(r.status_code, 400)
            self.assertIn("IP-Adresse", r.json()["fehler"])

    def test_bestaetigung_mit_passkey_statt_code(self):
        """F132: Bestätigungen (hier: zweiten Faktor ausschalten) mit Kennwort und Passkey statt Code; eine Antwort für
        „anmelden“ zählt dabei nicht."""
        user = benutzer("pk_bestaetigen", Rolle.MITARBEITER)
        c, _ = anmelden_mit_kennwort(user)
        geraet, _ = self.einrichten(c)
        optionen = c.post("/api/auth/passkey/optionen/", {"zweck": "bestaetigen"}, format="json").json()
        # falsches Kennwort: der Passkey wird gar nicht erst geprüft, dieselbe Antwort gilt danach noch
        antwort = geraet.signieren(optionen)
        r = c.post("/api/auth/2fa/ausschalten/", {"kennwort": "falsch", "passkey": antwort}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("kennwort", r.json())
        r = c.post("/api/auth/2fa/ausschalten/", {"kennwort": KENNWORT, "passkey": {**antwort, "id": "AAAA"}},
                   format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "Der Passkey konnte nicht bestätigt werden. Bitte erneut versuchen.")
        optionen = c.post("/api/auth/passkey/optionen/", {"zweck": "bestaetigen"}, format="json").json()
        r = c.post("/api/auth/2fa/ausschalten/", {"kennwort": KENNWORT, "passkey": geraet.signieren(optionen)},
                   format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["zweiter_faktor"])
        self.assertFalse(Passkey.objects.filter(user=user).exists())

    def test_passkey_entfernen_und_umbenennen(self):
        user = benutzer("pk_entfernen", Rolle.MITARBEITER)
        codes = mit_zweitem_faktor(user)
        c = client_fuer(user)
        geraet, antwort = self.einrichten(c, name="Laptop")
        self.assertNotIn("notfallcodes", antwort)   # Notfall-Codes gab es schon (Authenticator)
        pk = antwort["passkey_neu"]["id"]
        self.assertEqual(c.patch(f"/api/auth/passkeys/{pk}/", {"name": "Büro-PC"}, format="json").json()["name"],
                         "Büro-PC")
        self.assertEqual(client_fuer(benutzer("pk_fremd", Rolle.MITARBEITER))
                         .patch(f"/api/auth/passkeys/{pk}/", {"name": "x"}, format="json").status_code, 404)
        r = c.post(f"/api/auth/passkeys/{pk}/entfernen/", {"kennwort": KENNWORT, "code": codes[0]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["authenticator"])
        self.assertFalse(r.json()["passkey"])
        self.assertEqual(c.get("/api/auth/passkeys/").json(), [])

    def test_letzter_faktor_bei_pflicht_bleibt(self):
        Anmelderegeln.objects.update_or_create(pk=1, defaults={"zweiter_faktor": Anmelderegeln.ZweiterFaktor.ALLE})
        user = benutzer("pk_letzter", Rolle.MITARBEITER)
        c, _ = anmelden_mit_kennwort(user)
        geraet, antwort = self.einrichten(c)
        optionen = c.post("/api/auth/passkey/optionen/", {"zweck": "bestaetigen"}, format="json").json()
        r = c.post(f"/api/auth/passkeys/{antwort['passkey_neu']['id']}/entfernen/",
                   {"kennwort": KENNWORT, "passkey": geraet.signieren(optionen)}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Passkey.objects.filter(user=user).exists())

    def test_admin_setzt_zweiten_faktor_zurueck(self):
        user = benutzer("pk_verloren", Rolle.MITARBEITER)
        c, _ = anmelden_mit_kennwort(user)
        self.einrichten(c)
        admin = client_fuer(self.admin)
        self.assertEqual(admin.post(f"/api/benutzer/{user.id}/2fa-zuruecksetzen/").status_code, 200)
        self.assertFalse(Passkey.objects.filter(user=user).exists())


@override_settings(EPM_PASSKEY_ORIGINS=[HERKUNFT], EPM_PASSKEY_RP_ID="")
class PasskeyBeiSystemauftraegen(Grundlage):
    """F132: auch Updates/Neustart (Administration › System) lassen sich mit Passkey bestätigen."""

    def setUp(self):
        self.ordner = Path(tempfile.mkdtemp(prefix="epm-system-"))
        (self.ordner / "auftraege").mkdir()
        (self.ordner / "status" / "auftraege").mkdir(parents=True)
        self.einstellung = override_settings(EPM_SYSTEM=self.ordner)
        self.einstellung.enable()

    def tearDown(self):
        self.einstellung.disable()
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_neustart_mit_passkey(self):
        from system.models import Systemauftrag

        c, _ = anmelden_mit_kennwort(self.admin)
        geraet = SoftwareAuthenticator()
        optionen = c.post("/api/auth/passkey/optionen/", {"zweck": "registrieren"}, format="json").json()
        self.assertEqual(c.post("/api/auth/passkey/registrieren/", {"antwort": geraet.erzeugen(optionen)},
                                format="json").status_code, 200)
        optionen = c.post("/api/auth/passkey/optionen/", {"zweck": "bestaetigen"}, format="json").json()
        r = c.post("/api/system/auftraege/", {"aktion": "epm_neustart", "minuten": 0, "kennwort": KENNWORT,
                                              "passkey": geraet.signieren(optionen)}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(Systemauftrag.objects.filter(aktion="epm_neustart").exists())
        # dieselbe Antwort ein zweites Mal: abgelehnt
        r = c.post("/api/system/auftraege/", {"aktion": "epm_neustart", "minuten": 0, "kennwort": KENNWORT,
                                              "passkey": geraet.signieren(optionen)}, format="json")
        self.assertEqual(r.status_code, 400, r.content)
