"""Dokumentenautomation der RGC (Anforderungsspezifikation 26.10.2026).

Abnahmekriterium: Nach Erzeugung einer PDF (insbesondere Rechnung) kann der Inhalt noch geändert und die PDF neu
erzeugt werden. Erst nach Unterschrift/Signatur ist die Fassung unveränderlich. Alle Versionen sind nachvollziehbar.
"""
import datetime
import hashlib
import io
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import override_settings

from accounts.models import Rolle
from audit.models import SystemEreignis
from audit.schutz import wartungsmodus
from epm.pruefhilfen import Grundlage, benutzer, client_fuer
from patienten.datenschutz import akten_entfernen
from patienten.models import Dokument, Patient
from vorlagen.bloecke import pruefe_bloecke
from vorlagen.models import Dokumentvorlage, EigenesSchreiben
from vorlagen.tests import kompakt, pdf_text

from . import erzeugung
from .models import (Behandlungsfall, DokumentVersion, FallDokument, Kooperationspartner, Kostentraegertyp, Leistung,
                     Rechnungsposition, Unterzeichner)


def p12(name="Prof. Dr. Markus Masin", kennwort="geheim") -> bytes:
    """Selbst ausgestelltes Zertifikat mit Schlüssel als PKCS#12 (wie es die Person hinterlegt)."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    schluessel = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subjekt = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name),
                         x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Regeneration Clinic SIA")])
    jetzt = datetime.datetime.now(datetime.timezone.utc)
    zert = (x509.CertificateBuilder().subject_name(subjekt).issuer_name(subjekt).public_key(schluessel.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(jetzt - datetime.timedelta(days=1))
            .not_valid_after(jetzt + datetime.timedelta(days=365))
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(schluessel, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(b"epm", schluessel, zert, None,
                                                 serialization.BestAvailableEncryption(kennwort.encode()))


# eigener Ordner: jede Fassung ist eine Datei – im gemeinsamen Testordner kämen sonst andere Tests durcheinander
# (z. B. „Dokumente prüfen“, das nur die ersten 100 Dateien ohne Eintrag nennt)
@override_settings(EPM_DOKUMENTE=Path(tempfile.mkdtemp(prefix="epm-test-faelle-")))
class FallTest(Grundlage):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.gkv = Kostentraegertyp.objects.get(kuerzel="de-gkv")
        cls.op = Leistung.objects.create(code="OP-101", bezeichnung="Knie-TEP rechts", bezeichnung_en="Total knee "
                                         "replacement, right", bezeichnung_lv="Ceļa endoprotezēšana, labā",
                                         gruppe="Operation", einheit="Eingriff", preis=Decimal("8900.00"))
        cls.zimmer = Leistung.objects.create(code="UNT-1", bezeichnung="Unterbringung Einzelzimmer", einheit="Tag",
                                             preis=Decimal("250.00"))
        cls.masin = Unterzeichner.objects.get(name="Prof. Dr. Markus Masin")

    # ---------------------------------------------------------------- Hilfen
    def fall(self, client=None, erwartet=201, **extra):
        c = client or client_fuer(self.mitarbeiter)
        daten = {"patient": self.patient.id, "kostentraegertyp": self.gkv.id, "titel": "Knie-TEP rechts",
                 "eingriff": "Knie-TEP rechts", "aufnahme": "2026-10-01", "entlassung": "2026-10-08",
                 "op_datum": "2026-10-02", "diagnose": "Gonarthrose rechts (M17.1)", "kostentraeger": "AOK Bayern",
                 "op_verlauf": "Komplikationsloser Verlauf, Blutsperre 70 Minuten.", **extra}
        r = c.post("/api/faelle/", daten, format="json")
        self.assertEqual(r.status_code, erwartet, r.content)
        return r.json()

    def dokument(self, fall, art):
        return FallDokument.objects.get(fall_id=fall["id"], art=art, storniert_am__isnull=True)

    def position(self, dok, leistung=None, client=None, erwartet=201, **extra):
        c = client or client_fuer(self.mitarbeiter)
        daten = {"dokument": dok.pk, **({"leistung": leistung.pk} if leistung else {}), **extra}
        r = c.post("/api/rechnungspositionen/", daten, format="json")
        self.assertEqual(r.status_code, erwartet, r.content)
        return r.json()

    def erzeugen(self, dok, client=None, erwartet=201):
        r = (client or client_fuer(self.mitarbeiter)).post(f"/api/falldokumente/{dok.pk}/erzeugen/", {}, format="json")
        self.assertEqual(r.status_code, erwartet, r.content)
        return r.json()

    def finalisieren(self, dok, client=None, erwartet=200, **daten):
        r = (client or client_fuer(self.mediziner)).post(f"/api/falldokumente/{dok.pk}/finalisieren/",
                                                         {"weg": "finalisiert", **daten})
        self.assertEqual(r.status_code, erwartet, r.content)
        return r.json()

    def pdf(self, dok, fassung=None, client=None):
        url = f"/api/falldokumente/{dok.pk}/pdf/" + (f"?fassung={fassung}" if fassung else "")
        r = (client or client_fuer(self.mitarbeiter)).get(url)
        self.assertEqual(r.status_code, 200, r.content)
        return b"".join(r.streaming_content) if r.streaming else r.content

    # ---------------------------------------------------------------- Stammdaten und Vorlagen
    def test_mitgelieferte_stammdaten_und_vorlagen(self):
        self.assertEqual(Kostentraegertyp.objects.count(), 8)
        self.assertTrue(Kostentraegertyp.objects.filter(kuerzel="international").exists())
        self.assertEqual(sorted(Kooperationspartner.objects.values_list("name", flat=True)),
                         ["AIWA", "ARS", "Eibach", "WC4"])
        self.assertEqual(sorted(Unterzeichner.objects.values_list("name", flat=True)),
                         ["Dr. Markus Gottwald", "Prof. Dr. Markus Masin"])
        fall_vorlagen = EigenesSchreiben.objects.filter(gruppe="fall")
        self.assertEqual(fall_vorlagen.count(), 12)  # 4 Dokumente × DE/LV/EN
        zusatz = EigenesSchreiben.objects.filter(schluessel__startswith="eigen-rgc-z07-")
        self.assertEqual(zusatz.count(), 3)
        for e in [*fall_vorlagen, *zusatz]:
            self.assertEqual(e.firma.kuerzel, "rg")
            v = Dokumentvorlage.objects.get(art=e.schluessel, status="aktiv")
            self.assertEqual(pruefe_bloecke(e.schluessel, v.bloecke), [], e.name)
        for typ in Kostentraegertyp.objects.all():
            self.assertEqual(typ.clean(), None)
        # Fall-Vorlagen nicht als Schreiben der Akte wählbar
        namen = [s["art"] for s in client_fuer(self.mitarbeiter).get("/api/schreiben/").json()]
        self.assertNotIn("eigen-rgc-rechnung-de", namen)

    def test_paket_unbekanntes_dokument(self):
        r = client_fuer(self.mitarbeiter).patch(f"/api/kostentraegertypen/{self.gkv.pk}/",
                                                {"paket": ["rechnung", "gibt-es-nicht", "rechnung"]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(len(r.json()["paket"]), 2)
        konten = client_fuer(self.mitarbeiter).get("/api/unterzeichner/konten/").json()
        self.assertIn(self.mediziner.pk, [k["id"] for k in konten])
        self.assertEqual(client_fuer(self.betrachter).get("/api/unterzeichner/konten/").status_code, 403)
        self.assertEqual(client_fuer(self.betrachter).patch(f"/api/kostentraegertypen/{self.gkv.pk}/",
                                                            {"name": "X"}, format="json").status_code, 403)

    # ---------------------------------------------------------------- Fall und Paket
    def test_fall_mit_paket_je_kostentraegertyp(self):
        f = self.fall(fachbereich="orthopaedie")
        self.assertRegex(f["nummer"], r"^F-\d{4}-0001$")
        arten = sorted(FallDokument.objects.filter(fall_id=f["id"]).values_list("art", "vorlage"))
        self.assertEqual(arten, sorted([
            ("vorlage", "eigen-rgc-f02"), ("vorlage", "eigen-rgc-f11"), ("vorlage", "eigen-rgc-f06"),
            ("vorlage", "eigen-rgc-f07"), ("vorlage", "eigen-rgc-z07-ortho"), ("vorlage", "eigen-rgc-f08"),
            ("op_bericht", ""), ("entlassbrief", ""), ("rechnung", "")]))
        self.assertEqual(f["versichertennummer"], self.patient.versichertennummer)
        # Paket erneut: nichts doppelt
        r = client_fuer(self.mitarbeiter).post(f"/api/faelle/{f['id']}/paket/")
        self.assertEqual(r.json()["neu"], 0)
        # Konsil von Hand dazu
        r = client_fuer(self.mitarbeiter).post("/api/falldokumente/", {"fall": f["id"], "art": "konsil"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["titel"], "Konsiliarbericht")
        self.assertEqual(client_fuer(self.betrachter).post("/api/faelle/", {"patient": self.patient.id,
                                                                            "kostentraegertyp": self.gkv.id},
                                                           format="json").status_code, 403)
        self.assertIn("entlassung", self.fall(entlassung="2026-09-01", erwartet=400))

    def test_op_bericht_aus_falldaten_und_formular_mit_falldaten(self):
        f = self.fall()
        op = self.dokument(f, "op_bericht")
        d = self.erzeugen(op)
        self.assertEqual((d["status"], d["versionen_anzahl"]), ("erzeugt", 1))
        text = kompakt(pdf_text(self.pdf(op)))
        self.assertIn("OP-Bericht", text)
        self.assertIn("KomplikationsloserVerlauf", text)
        self.assertIn(kompakt(f["nummer"]), text)
        # Formular der RGC (Revision 3) mit Datenfeldern des Falls
        anlage = FallDokument.objects.get(fall_id=f["id"], vorlage="eigen-rgc-f02")
        self.erzeugen(anlage)
        self.assertIn("Echt", pdf_text(self.pdf(anlage)))

    # ---------------------------------------------------------------- Rechnung: änderbar bis final
    def test_rechnung_aenderbar_bis_finalisierung(self):
        f = self.fall()
        r = self.dokument(f, "rechnung")
        self.assertIn("fehler", self.erzeugen(r, erwartet=400))  # ohne Positionen
        p1 = self.position(r, self.op)
        self.assertEqual((p1["text"], Decimal(str(p1["einzelpreis"])), p1["code"]),
                         ("Knie-TEP rechts", Decimal("8900"), "OP-101"))
        self.position(r, self.zimmer, menge="7")
        d = self.erzeugen(r)
        nummer = d["rechnungsnummer"]
        self.assertRegex(nummer, r"^RGC-\d{4}-0001$")
        self.assertEqual(d["summe"], "10650.00")
        self.assertFalse(d["veraltet"])
        erste = self.pdf(r)
        self.assertIn("10.650,00", pdf_text(erste))
        # nach der PDF: Preis korrigieren, Nachtrag, Position entfernen
        c = client_fuer(self.mitarbeiter)
        self.assertEqual(c.patch(f"/api/rechnungspositionen/{p1['id']}/", {"einzelpreis": "9100.00",
                                                                          "text": "Knie-TEP rechts, zementiert"},
                                 format="json").status_code, 200)
        nachtrag = self.position(r, text="Physiotherapie", einzelpreis="80.00", menge="3")
        self.assertEqual(c.delete(f"/api/rechnungspositionen/{nachtrag['id']}/").status_code, 204)
        self.assertTrue(c.get(f"/api/falldokumente/{r.pk}/").json()["veraltet"])
        d = self.erzeugen(r)
        self.assertEqual((d["rechnungsnummer"], d["versionen_anzahl"], d["summe"]), (nummer, 2, "10850.00"))
        self.assertIn("zementiert", pdf_text(self.pdf(r)))
        # die erste Fassung bleibt unverändert abrufbar, beide stehen im Verlauf
        self.assertEqual(self.pdf(r, fassung=1), erste)
        versionen = c.get(f"/api/falldokumente/{r.pk}/versionen/").json()
        self.assertEqual([v["nummer"] for v in versionen], [2, 1])
        self.assertEqual(versionen[1]["sha256"], hashlib.sha256(erste).hexdigest())
        self.assertNotEqual(versionen[0]["sha256"], versionen[1]["sha256"])
        self.assertTrue(Dokument.objects.filter(pk=versionen[1]["pdf"], ausgeblendet=True).exists())
        self.assertEqual(SystemEreignis.objects.filter(art="fall", details__aktion="PDF erzeugt").count(), 2)
        # Mitarbeiter darf nicht finalisieren; Mediziner schon
        self.finalisieren(r, client=client_fuer(self.mitarbeiter), erwartet=403)
        d = self.finalisieren(r, unterzeichner=self.masin.pk)
        self.assertEqual((d["status"], d["final_weg"], d["unterzeichner_name"]),
                         ("final", "finalisiert", "Prof. Dr. Markus Masin"))
        final = DokumentVersion.objects.get(dokument=r, final=True)
        self.assertFalse(final.pdf.ausgeblendet)  # finale Fassung in den Dokumenten der Akte
        # danach unveränderlich: API, Modell und Datenbank
        self.assertIn(c.patch(f"/api/rechnungspositionen/{p1['id']}/", {"menge": "2"}, format="json").status_code,
                      (400, 403))
        self.position(r, self.zimmer, erwartet=400)
        self.assertEqual(c.patch(f"/api/falldokumente/{r.pk}/", {"freitext": "x"}, format="json").status_code, 400)
        self.erzeugen(r, erwartet=400)
        self.finalisieren(r, erwartet=400)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Rechnungsposition.objects.filter(dokument=r).update(menge=5)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FallDokument.objects.filter(pk=r.pk).update(freitext="manipuliert")
        with self.assertRaises(DatabaseError), transaction.atomic():
            DokumentVersion.objects.filter(dokument=r).update(grund="x")
        with self.assertRaises(DatabaseError), transaction.atomic():
            DokumentVersion.objects.filter(dokument=r).delete()

    def test_finalisieren_nur_aktuelle_fassung(self):
        f = self.fall()
        op = self.dokument(f, "op_bericht")
        self.finalisieren(op, erwartet=400)  # noch keine PDF
        self.erzeugen(op)
        r = client_fuer(self.mitarbeiter).patch(f"/api/faelle/{f['id']}/", {"op_befund": "Gute Stellung"},
                                                format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn("neu erzeugen", str(self.finalisieren(op, erwartet=400)["fehler"]))
        # nur Angaben, die die Vorlage verwendet: der OP-Befund macht die Rechnung nicht veraltet
        r = self.dokument(f, "rechnung")
        self.position(r, self.op)
        self.erzeugen(r)
        c = client_fuer(self.mitarbeiter)
        c.patch(f"/api/faelle/{f['id']}/", {"op_befund": "Gute Stellung, Drainage entfernt"}, format="json")
        self.assertFalse(c.get(f"/api/falldokumente/{r.pk}/").json()["veraltet"])
        self.assertTrue(c.get(f"/api/falldokumente/{op.pk}/").json()["veraltet"])
        c.patch(f"/api/faelle/{f['id']}/", {"kostentraeger": "TK"}, format="json")
        self.assertTrue(c.get(f"/api/falldokumente/{r.pk}/").json()["veraltet"])

    def test_storno_und_neue_rechnung(self):
        f = self.fall()
        r = self.dokument(f, "rechnung")
        self.position(r, self.op)
        self.erzeugen(r)
        c = client_fuer(self.mediziner)
        self.assertIn("fehler", c.post(f"/api/falldokumente/{r.pk}/stornieren/", {"grund": "x"}).json())  # nicht final
        self.finalisieren(r)
        self.assertIn("storno_grund", c.post(f"/api/falldokumente/{r.pk}/stornieren/", {"grund": ""}).json())
        antwort = c.post(f"/api/falldokumente/{r.pk}/stornieren/", {"grund": "Falscher Kostenträger"})
        self.assertEqual(antwort.status_code, 200, antwort.content)
        d = antwort.json()
        self.assertIsNotNone(d["rechnung"]["storniert_am"])
        storno, neu = FallDokument.objects.get(pk=d["storno"]["id"]), FallDokument.objects.get(pk=d["neu"]["id"])
        self.assertEqual((storno.status, storno.storno_zu_id, storno.summen()["brutto"]),
                         ("erzeugt", r.pk, Decimal("-8900.00")))
        self.assertNotEqual(storno.rechnungsnummer, r.rechnungsnummer)
        r.refresh_from_db()
        text = pdf_text(self.pdf(storno))
        self.assertIn("Stornorechnung", text)
        self.assertIn(r.rechnungsnummer, text)
        self.assertEqual((neu.status, neu.positionen.count(), neu.rechnungsnummer), ("entwurf", 1, None))
        self.assertEqual(c.post(f"/api/falldokumente/{r.pk}/stornieren/", {"grund": "nochmal"}).status_code, 400)
        # Paket legt die stornierte Rechnung nicht erneut an (es gibt schon die neue)
        self.assertEqual(client_fuer(self.mitarbeiter).post(f"/api/faelle/{f['id']}/paket/").json()["neu"], 0)
        # Stornorechnung lässt sich finalisieren; negative Mengen auf normalen Rechnungen nicht
        self.finalisieren(storno)
        self.position(neu, self.op, menge="-1", erwartet=400)

    def test_sprachen(self):
        f = self.fall(sprache="en")
        r = self.dokument(f, "rechnung")
        self.position(r, self.op)
        self.erzeugen(r)
        text = pdf_text(self.pdf(r))
        self.assertIn("Invoice", text)
        self.assertIn("Totalknee", kompakt(text))
        self.assertIn("8,900.00", text)
        # Formulare der RGC bleiben deutsch: Anlage K mit Kostenträger, Kostenvoranschlag und Summe aus der Rechnung
        anlage = FallDokument.objects.get(fall_id=f["id"], vorlage="eigen-rgc-f11")
        self.erzeugen(anlage)
        text = kompakt(pdf_text(self.pdf(anlage)))
        for erwartet in ("AOKBayern", f"{f['nummer']}vom", "EUR8.900,00", "Echt,Anna,geb."):
            self.assertIn(erwartet, text)
        f2 = self.fall(sprache="lv")
        op = self.dokument(f2, "op_bericht")
        self.erzeugen(op)
        self.assertIn("Operācijas", pdf_text(self.pdf(op)))

    # ---------------------------------------------------------------- Signatur und Scan
    def test_elektronische_signatur(self):
        self.masin.benutzer = self.mediziner
        self.masin.save()
        c = client_fuer(self.mediziner)
        datei = SimpleUploadedFile("masin.p12", p12(), content_type="application/x-pkcs12")
        r = c.post(f"/api/unterzeichner/{self.masin.pk}/zertifikat/", {"datei": datei, "kennwort": "falsch"})
        self.assertEqual(r.status_code, 400)
        datei = SimpleUploadedFile("masin.p12", p12(), content_type="application/x-pkcs12")
        r = c.post(f"/api/unterzeichner/{self.masin.pk}/zertifikat/", {"datei": datei, "kennwort": "geheim"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["hat_zertifikat"])
        self.assertIn("Masin", r.json()["zertifikat_info"])
        # fremdes Zertifikat hochladen darf ein Mitarbeiter mit „Vorlagen pflegen“ – signieren nur die Person selbst
        f = self.fall()
        op = self.dokument(f, "op_bericht")
        self.erzeugen(op)
        andere = benutzer("medizin2", Rolle.MEDIZINER)
        self.finalisieren(op, client=client_fuer(andere), erwartet=403, weg="signatur", unterzeichner=self.masin.pk,
                          kennwort="geheim")
        self.finalisieren(op, erwartet=400, weg="signatur", unterzeichner=self.masin.pk, kennwort="falsch")
        d = self.finalisieren(op, weg="signatur", unterzeichner=self.masin.pk, kennwort="geheim")
        self.assertEqual((d["status"], d["final_weg"]), ("final", "signatur"))
        signiert = self.pdf(op)
        info = erzeugung.pruefe_signatur(signiert)
        self.assertIn("Masin", info["unterzeichner"])
        self.assertIn("Prof.Dr.MarkusMasin", kompakt(pdf_text(signiert)))  # mit Namen neu erzeugt
        # extern signierte PDF zu einem anderen Dokument hochladen
        eb = self.dokument(f, "entlassbrief")
        self.erzeugen(eb)
        ohne = SimpleUploadedFile("x.pdf", self.pdf(eb), content_type="application/pdf")
        self.assertIn("datei", self.finalisieren(eb, erwartet=400, weg="signatur_extern", datei=ohne))
        # signierte PDF eines anderen Dokuments: abgelehnt
        fremd = SimpleUploadedFile("x.pdf", signiert, content_type="application/pdf")
        self.assertIn("keiner Fassung", str(self.finalisieren(eb, erwartet=400, weg="signatur_extern", datei=fremd)))
        # extern signiert (hier mit demselben Zertifikat): die heruntergeladene Fassung, Signatur angehängt
        self.masin.refresh_from_db()
        extern = erzeugung.signiere(self.pdf(eb), self.masin, "geheim", "extern")
        d = self.finalisieren(eb, weg="signatur_extern", datei=SimpleUploadedFile("x.pdf", extern))
        self.assertEqual(d["final_weg"], "signatur_extern")
        v = DokumentVersion.objects.get(dokument=eb, final=True)
        self.assertEqual((v.daten["signatur"]["anzahl"], v.daten["signiert_fassung"]), (1, 1))

    def test_scan_der_papierunterschrift(self):
        f = self.fall()
        dok = FallDokument.objects.get(fall_id=f["id"], vorlage="eigen-rgc-f06")
        self.erzeugen(dok)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        self.assertIn("unterzeichner", self.finalisieren(dok, erwartet=400, weg="scan",
                                                         datei=SimpleUploadedFile("s.png", png)))
        self.assertIn("datei", self.finalisieren(dok, erwartet=400, weg="scan", unterzeichner=self.masin.pk,
                                                 datei=SimpleUploadedFile("s.txt", b"hallo")))
        d = self.finalisieren(dok, weg="scan", unterzeichner=self.masin.pk, datei=SimpleUploadedFile("s.png", png),
                              notiz="Original im Ordner")
        self.assertEqual((d["status"], d["final_weg"]), ("final", "scan"))
        v = DokumentVersion.objects.get(dokument=dok, final=True)
        self.assertEqual((v.pdf.mime, v.grund, v.daten["grundlage_fassung"]), ("image/png", "Original im Ordner", 1))
        r = client_fuer(self.mitarbeiter).get(f"/api/falldokumente/{dok.pk}/pdf/")
        self.assertEqual(r["Content-Type"], "image/png")

    # ---------------------------------------------------------------- DOCX
    def test_docx_nachbearbeitung(self):
        from docx import Document

        f = self.fall()
        eb = self.dokument(f, "entlassbrief")
        self.erzeugen(eb)
        c = client_fuer(self.mitarbeiter)
        r = c.get(f"/api/falldokumente/{eb.pk}/docx/")
        self.assertEqual(r.status_code, 200)
        d = Document(io.BytesIO(r.content))
        for zeile in d.tables[0].rows:
            if "[[entlass_empfehlung]]" in zeile.cells[0].text:
                zeile.cells[1].text = "Vollbelastung nach 6 Wochen.\nKontrolle in der Sprechstunde."
        puffer = io.BytesIO()
        d.save(puffer)
        r = c.post(f"/api/falldokumente/{eb.pk}/docx/",
                   {"datei": SimpleUploadedFile("eb.docx", puffer.getvalue())})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["versionen_anzahl"], 2)
        fall = Behandlungsfall.objects.get(pk=f["id"])
        self.assertEqual(fall.entlass_empfehlung, "Vollbelastung nach 6 Wochen.\nKontrolle in der Sprechstunde.")
        v = eb.letzte_version()
        self.assertEqual(v.art, "docx")
        self.assertIsNotNone(v.docx)
        self.assertIn("Vollbelastungnach6Wochen", kompakt(pdf_text(self.pdf(eb))))
        # unverändert erneut hochladen: keine Änderung; fremde DOCX abgelehnt
        r = c.post(f"/api/falldokumente/{eb.pk}/docx/", {"datei": SimpleUploadedFile("eb.docx", puffer.getvalue())})
        self.assertEqual(r.status_code, 400)
        op = self.dokument(f, "op_bericht")
        r = c.post(f"/api/falldokumente/{op.pk}/docx/", {"datei": SimpleUploadedFile("eb.docx", puffer.getvalue())})
        self.assertIn("anderen Dokument", str(r.json()))

    # ---------------------------------------------------------------- Leistungskatalog
    def test_leistungskatalog_csv(self):
        csv = ("code;bezeichnung;bezeichnung_en;gruppe;einheit;preis;ust_satz\n"
               "OP-101;Knie-TEP rechts;Total knee replacement;Operation;Eingriff;9.200,00;0\n"
               "ANA-1;Allgemeinanästhesie;General anaesthesia;Anästhesie;Stunde;450.00;0\n").encode()
        c = client_fuer(self.mitarbeiter)
        r = c.post("/api/leistungen/import/", {"datei": SimpleUploadedFile("k.csv", csv)})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json(), {"neu": 1, "geaendert": 1})
        self.assertEqual(Leistung.objects.get(code="OP-101").preis, Decimal("9200.00"))
        kaputt = b"code;bezeichnung;preis\nX-1;Test;abc\n"
        self.assertEqual(c.post("/api/leistungen/import/", {"datei": SimpleUploadedFile("k.csv", kaputt)}).status_code,
                         400)
        self.assertFalse(Leistung.objects.filter(code="X-1").exists())
        self.assertEqual(client_fuer(self.betrachter).post("/api/leistungen/", {"code": "Y", "bezeichnung": "Y",
                                                                               "preis": "1"}).status_code, 403)

    # ---------------------------------------------------------------- Datenschutz
    def test_akte_endgueltig_entfernen_mit_faellen(self):
        anderer = Patient.objects.create(nachname="Fall", vorname="Fritz", geburtsdatum="1970-01-01")
        f = self.fall(patient=anderer.id)
        r = self.dokument(f, "rechnung")
        self.position(r, self.op)
        self.erzeugen(r)
        self.finalisieren(r)
        with wartungsmodus():
            akten_entfernen([anderer.id])
        self.assertFalse(Behandlungsfall.objects.filter(patient_id=anderer.id).exists())
        self.assertFalse(DokumentVersion.objects.exists())
        self.assertFalse(FallDokument.history.filter(patient_id=anderer.id).exists())
