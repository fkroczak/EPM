"""Erzeugen, Neu-Erzeugen und Finalisieren der Dokumente eines Falls (Anforderung 26.10.2026, Punkt 2).

- ``erzeugen``: PDF aus der aktiven Vorlage und dem aktuellen Stand des Falls (bzw. der Rechnungspositionen); jede
  Erzeugung ist eine neue Fassung, die vorherige bleibt erhalten. Erlaubt, solange das Dokument nicht final ist.
- ``finalisieren``: elektronische Signatur (fortgeschritten, mit dem Zertifikat der unterschriftsberechtigten Person),
  hochgeladene extern signierte PDF (z. B. qualifiziert), Scan der Papierunterschrift oder ausdrückliche
  Finalisierung – danach ist die Fassung unveränderlich.
- ``stornieren``: finale Rechnung → Stornorechnung (negative Positionen) und auf Wunsch eine neue Rechnung als Entwurf.
- ``docx_export``/``docx_import``: Freitexte zur Nachbearbeitung in Word und zurück in eine neue PDF.
"""
import hashlib
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Behandlungsfall, DokumentVersion, FallDokument, Rechnungsposition, Zaehler

MAX_UPLOAD = 25 * 1024 * 1024
SCAN_MIME = {"application/pdf", "image/jpeg", "image/png"}


# ====================================================================== Vorlage und Daten
def vorlage_fuer(dok: FallDokument) -> str:
    from .startvorlagen import schluessel

    if dok.art == FallDokument.Art.VORLAGE:
        return dok.vorlage
    art = FallDokument.Art.RECHNUNG if dok.art == FallDokument.Art.STORNO else dok.art
    return schluessel(art, dok.fall.sprache)


class _Schreiben:
    """Was die eigenen Schreiben als „Schreiben (Korrespondenz)“ kennen: Betreff, Empfänger, Freitext."""

    def __init__(self, dok):
        self.titel = dok.titel
        self.empfaenger = ""
        self.text = dok.freitext
        self.freigabevermerk = None


def kontext(dok: FallDokument, benutzer=None):
    from vorlagen.felder import Kontext

    return Kontext(patient=dok.patient, benutzer=benutzer or dok.erstellt_von, schreiben=_Schreiben(dok),
                   fall=dok.fall, falldokument=dok)


def _wert(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


def datenstand(dok: FallDokument) -> dict:
    """Alles, woraus die PDF entsteht (ohne Vorlage): Fall, Patient, Dokument, Positionen. Grundlage für
    „veraltet“ und für die Nachvollziehbarkeit jeder Fassung."""
    fall, p = dok.fall, dok.patient
    felder = {f.attname: _wert(getattr(fall, f.attname)) for f in Behandlungsfall._meta.concrete_fields
              if f.attname not in ("geaendert_am", "erstellt_am", "erstellt_von_id", "firma_id", "status")}
    daten = {
        "fall": felder,
        "patient": {"name": f"{p.nachname}, {p.vorname}", "geburtsdatum": _wert(p.geburtsdatum),
                    "anschrift": [p.strasse, p.plz, p.ort], "versichertennummer": p.versichertennummer},
        "dokument": {"titel": dok.titel, "freitext": dok.freitext, "vorlage": vorlage_fuer(dok),
                     "unterzeichner_id": dok.unterzeichner_id, "rechnungsdatum": _wert(dok.rechnungsdatum),
                     "zahlungsziel_tage": dok.zahlungsziel_tage},
    }
    if dok.ist_rechnung:
        daten["positionen"] = [{"id": x.pk, "code": x.code, "text": x.text, "datum": _wert(x.datum),
                                "menge": str(x.menge), "einheit": x.einheit, "einzelpreis": str(x.einzelpreis),
                                "ust_satz": str(x.ust_satz)} for x in dok.positionen.all()]
        daten["summen"] = {k: str(v) for k, v in dok.summen().items() if k != "ust_saetze"}
    return daten


def daten_hash(daten: dict) -> str:
    return hashlib.sha256(json.dumps(daten, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def ist_veraltet(dok: FallDokument) -> bool:
    """Wurden Falldaten oder Positionen nach der letzten Erzeugung geändert? (nicht bei finalen Dokumenten)"""
    if dok.ist_final:
        return False
    letzte = dok.letzte_version()
    return letzte is None or letzte.daten_hash != daten_hash(datenstand(dok))


def pruefe_vorlage(dok: FallDokument) -> str:
    from vorlagen.models import EigenesSchreiben

    schluessel = vorlage_fuer(dok)
    if not EigenesSchreiben.objects.filter(schluessel=schluessel, aktiv=True).exists():
        raise ValidationError({"fehler": "Die Vorlage zu diesem Dokument gibt es nicht (mehr) oder sie ist "
                                         "ausgeschaltet (Vorlagen › Dokumentvorlagen)."})
    return schluessel


def pdf_bauen(dok: FallDokument, benutzer=None, wasserzeichen=None) -> tuple[bytes, int | None, str]:
    """PDF im Namen der Regeneration Clinic (Briefkopf, Bankverbindung, Vorlagen der RGC) – auch wenn gerade in der
    anderen Firma gearbeitet wird."""
    from epm.firma import setze_aktive_firma, zuruecksetzen
    from stammdaten.models import Firma
    from vorlagen.pdf import erzeuge_aus_vorlage

    schluessel = pruefe_vorlage(dok)
    p = dok.patient
    token = setze_aktive_firma(Firma.objects.filter(kuerzel=Firma.RG).first() or dok.fall.firma)
    try:
        pdf, version = erzeuge_aus_vorlage(schluessel, kontext(dok, benutzer), wasserzeichen=wasserzeichen,
                                           titel=f"{dok.titel} – {p.nachname}, {p.vorname}")
    finally:
        zuruecksetzen(token)
    return pdf, version, schluessel


def vorschau(dok: FallDokument, benutzer) -> bytes:
    """PDF mit dem aktuellen Stand, ohne Fassung (Wasserzeichen VORSCHAU)."""
    pdf, _, _ = pdf_bauen(dok, benutzer, wasserzeichen="VORSCHAU")
    return pdf


# ====================================================================== Fassungen
def _dateiname(dok, nummer, endung="pdf") -> str:
    from vorlagen.schreiben import dateiname_sicher

    teile = [dok.titel, dok.rechnungsnummer or "", dok.patient.nachname, f"Fassung-{nummer}"]
    return f"{dateiname_sicher('-'.join(t for t in teile if t))}.{endung}"


def _ablegen(dok, daten: bytes, mime: str, dateiname: str, benutzer, sichtbar=False, titel=None):
    """Datei als Dokument der Akte (Herkunft „Von EPM erzeugt“); nicht finale Fassungen ausgeblendet."""
    from django.core.files.base import ContentFile

    from patienten.api import speichere_datei
    from patienten.models import Dokument
    from stammdaten.models import Auswahlwert

    meta = speichere_datei(dok.patient, ContentFile(daten, name=dateiname), mime)
    typ_wert = "Rechnung" if dok.ist_rechnung else "Bericht"
    typ = Auswahlwert.objects.filter(liste=Auswahlwert.Liste.DOKUMENTTYP, wert=typ_wert).first()
    d = Dokument(patient=dok.patient, typ=typ, titel=(titel or dok.titel)[:200], datum=timezone.localdate(),
                 hochgeladen_von=benutzer, datum_quelle=Dokument.DatumQuelle.EINGABE, ausgeblendet=not sichtbar,
                 notiz=f"Fall {dok.fall.nummer} · {dok.titel}"[:500], **meta)
    d.herkunft = Dokument.Herkunft.SYSTEM
    d._history_user = benutzer
    d.save()
    return d


def _neue_version(dok, benutzer, art, pdf_dok, daten, schluessel="", vorlage_version=None, grund="", docx=None,
                  final=False) -> DokumentVersion:
    nummer = (dok.versionen.order_by("-nummer").values_list("nummer", flat=True).first() or 0) + 1
    return DokumentVersion.objects.create(
        dokument=dok, nummer=nummer, art=art, pdf=pdf_dok, sha256=pdf_dok.sha256, docx=docx, vorlage=schluessel,
        vorlage_version=vorlage_version, daten=daten, daten_hash=daten_hash(daten), grund=grund[:300], final=final,
        erzeugt_von=benutzer)


def _sperren(dok) -> FallDokument:
    return FallDokument.objects.select_for_update().select_related("fall", "patient").get(pk=dok.pk)


@transaction.atomic
def erzeugen(dok: FallDokument, benutzer, grund: str = "", art=DokumentVersion.Art.ERZEUGT, docx=None) -> DokumentVersion:
    """Neue Fassung aus dem aktuellen Stand. Rechnungen bekommen bei der ersten Erzeugung ihre Nummer."""
    from vorlagen.pdf import wasserzeichen_fuer

    dok = _sperren(dok)
    dok.pruefe_aenderbar()
    dok.fall.pruefe_offen()
    if dok.ist_rechnung:
        if not dok.positionen.exists():
            raise ValidationError({"fehler": "Die Rechnung hat noch keine Leistungspositionen."})
        if not dok.rechnungsdatum:
            dok.rechnungsdatum = timezone.localdate()
        if not dok.rechnungsnummer:
            jahr = dok.rechnungsdatum.year
            dok.rechnungsnummer = f"RGC-{jahr}-{Zaehler.naechster('rechnung', jahr):04d}"
    daten = datenstand(dok)
    pdf, version, schluessel = pdf_bauen(dok, benutzer, wasserzeichen=wasserzeichen_fuer(dok.patient))
    nummer = (dok.versionen.order_by("-nummer").values_list("nummer", flat=True).first() or 0) + 1
    pdf_dok = _ablegen(dok, pdf, "application/pdf", _dateiname(dok, nummer), benutzer,
                       titel=f"{dok.titel} {dok.rechnungsnummer or ''} – Fassung {nummer}".replace("  ", " "))
    try:
        v = _neue_version(dok, benutzer, art, pdf_dok, daten, schluessel, version, grund, docx=docx)
        dok.status = FallDokument.Status.ERZEUGT
        dok._history_user = benutzer
        dok.save()
    except BaseException:
        pdf_dok.pfad.unlink(missing_ok=True)
        raise
    return v


# ====================================================================== Finalisieren
def _pdf_pruefen(daten: bytes):
    if not daten.startswith(b"%PDF"):
        raise ValidationError({"datei": "Bitte eine PDF-Datei hochladen."})


def signiere(pdf: bytes, unterzeichner, kennwort: str, grund: str) -> bytes:
    """Fortgeschrittene elektronische Signatur (PAdES) mit dem PKCS#12-Zertifikat der Person."""
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers

    if not unterzeichner.zertifikat:
        raise ValidationError({"fehler": f"Für {unterzeichner.name} ist kein Zertifikat hinterlegt."})
    if unterzeichner.zertifikat_bis and unterzeichner.zertifikat_bis < timezone.now():
        raise ValidationError({"fehler": "Das Zertifikat ist abgelaufen."})
    try:
        signer = signers.SimpleSigner.load_pkcs12_data(bytes(unterzeichner.zertifikat), other_certs=[],
                                                       passphrase=(kennwort or "").encode() or None)
    except Exception:
        signer = None
    if signer is None:
        raise ValidationError({"kennwort": "Das Kennwort des Zertifikats stimmt nicht."})
    meta = signers.PdfSignatureMetadata(field_name="EPM-Signatur", reason=grund[:200], location="Rīga",
                                        name=unterzeichner.name, md_algorithm="sha256",
                                        subfilter=fields.SigSeedSubFilter.PADES)
    ausgabe = signers.sign_pdf(IncrementalPdfFileWriter(io.BytesIO(pdf), strict=False), meta, signer=signer)
    return ausgabe.getvalue()


def pruefe_signatur(pdf: bytes) -> dict:
    """Extern signierte PDF: mindestens eine Signatur, unversehrt und über das ganze Dokument. → Angaben zur Signatur."""
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    try:
        reader = PdfFileReader(io.BytesIO(pdf), strict=False)
        signaturen = reader.embedded_signatures
    except Exception:
        raise ValidationError({"datei": "Die PDF lässt sich nicht lesen."})
    if not signaturen:
        raise ValidationError({"datei": "Die PDF enthält keine elektronische Signatur."})
    letzte = signaturen[-1]
    try:
        status = validate_pdf_signature(letzte)
    except Exception:
        raise ValidationError({"datei": "Die Signatur lässt sich nicht prüfen."})
    if not status.intact:
        raise ValidationError({"datei": "Die Signatur ist beschädigt oder das Dokument wurde danach verändert."})
    zert = status.signing_cert
    return {"anzahl": len(signaturen), "unterzeichner": zert.subject.human_friendly if zert else "",
            "abdeckung": str(status.coverage.name) if status.coverage else "", "vertrauenswuerdig": bool(status.trusted)}


@transaction.atomic
def finalisieren(dok: FallDokument, benutzer, weg: str, unterzeichner=None, datei=None, kennwort: str = "",
                 notiz: str = "") -> DokumentVersion:
    W = FallDokument.Weg
    if not benutzer.hat_recht("dokumente_finalisieren"):
        raise PermissionError("Finalisieren und signieren darf nur, wer das Recht dazu hat.")
    dok = _sperren(dok)
    dok.pruefe_aenderbar()
    if weg not in W.values:
        raise ValidationError({"weg": "Bitte den Weg wählen."})
    letzte = dok.letzte_version()
    if letzte is None:
        raise ValidationError({"fehler": "Bitte zuerst die PDF erzeugen."})
    veraltet = ist_veraltet(dok)
    if veraltet and weg in (W.SIGNATUR, W.FINALISIERT):
        raise ValidationError({"fehler": "Die Falldaten wurden nach der letzten Erzeugung geändert. Bitte zuerst die "
                                         "PDF neu erzeugen."})
    if unterzeichner is not None and not unterzeichner.aktiv:
        raise ValidationError({"unterzeichner": "Diese Person ist nicht (mehr) unterschriftsberechtigt."})
    if weg in (W.SIGNATUR, W.SCAN) and unterzeichner is None:
        raise ValidationError({"unterzeichner": "Bitte die unterschriftsberechtigte Person wählen."})
    grund = notiz.strip()[:300]
    daten = {**letzte.daten, "grundlage_fassung": letzte.nummer, "veraltet_bei_finalisierung": veraltet}
    sichtbar_titel = f"{dok.titel} {dok.rechnungsnummer or ''}".replace("  ", " ").strip()

    if weg == W.SIGNATUR:
        if unterzeichner.benutzer_id != benutzer.pk:
            raise PermissionError("Signieren darf nur die Person selbst (mit ihrem Benutzerkonto).")
        if dok.unterzeichner_id != unterzeichner.pk:
            # Name der Person steht auf der PDF → mit ihr neu erzeugen, dann signieren
            dok.unterzeichner = unterzeichner
            daten = {**datenstand(dok), "grundlage_fassung": letzte.nummer, "veraltet_bei_finalisierung": False}
            pdf, _, _ = pdf_bauen(dok, benutzer)
        else:
            pdf = letzte.pdf.pfad.read_bytes()
            if hashlib.sha256(pdf).hexdigest() != letzte.sha256:
                raise ValidationError({"fehler": "Die Prüfsumme der letzten Fassung stimmt nicht. Bitte neu erzeugen."})
        signiert = signiere(pdf, unterzeichner, kennwort, grund or f"{dok.titel} {dok.rechnungsnummer or ''}".strip())
        pdf_dok = _ablegen(dok, signiert, "application/pdf", _dateiname(dok, "signiert"), benutzer, sichtbar=True,
                           titel=f"{sichtbar_titel} (signiert)")
        art = DokumentVersion.Art.SIGNATUR
    elif weg in (W.SIGNATUR_EXTERN, W.SCAN):
        if datei is None:
            raise ValidationError({"datei": "Bitte die Datei hochladen."})
        if datei.size > MAX_UPLOAD:
            raise ValidationError({"datei": "Die Datei ist größer als 25 MB."})
        inhalt = datei.read()
        if weg == W.SIGNATUR_EXTERN:
            _pdf_pruefen(inhalt)
            daten["signatur"] = pruefe_signatur(inhalt)
            mime, art, endung, zusatz = "application/pdf", DokumentVersion.Art.SIGNATUR_EXTERN, "pdf", "signiert"
        else:
            mime = _scan_mime(inhalt)
            endung = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}[mime]
            art, zusatz = DokumentVersion.Art.SCAN, "unterschrieben"
        pdf_dok = _ablegen(dok, inhalt, mime, _dateiname(dok, zusatz, endung), benutzer, sichtbar=True,
                           titel=f"{sichtbar_titel} ({zusatz})")
    else:  # ausdrücklich finalisiert: die letzte erzeugte Fassung gilt
        pdf_dok = letzte.pdf
        pdf_dok.ausgeblendet = False
        pdf_dok._history_user = benutzer
        pdf_dok.save(update_fields=["ausgeblendet"])
        art = DokumentVersion.Art.FINALISIERT

    v = _neue_version(dok, benutzer, art, pdf_dok, daten, letzte.vorlage, letzte.vorlage_version, grund, final=True)
    dok.status = FallDokument.Status.FINAL
    dok.final_weg, dok.final_am, dok.final_von = weg, timezone.now(), benutzer
    if unterzeichner is not None:
        dok.unterzeichner = unterzeichner
    dok._history_user = benutzer
    dok.save()
    return v


def _scan_mime(inhalt: bytes) -> str:
    if inhalt.startswith(b"%PDF"):
        return "application/pdf"
    if inhalt.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if inhalt.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    raise ValidationError({"datei": "Bitte eine PDF, JPEG- oder PNG-Datei hochladen."})


# ====================================================================== Storno
@transaction.atomic
def stornieren(dok: FallDokument, benutzer, grund: str, neue_rechnung: bool = True) -> tuple:
    """Finale Rechnung stornieren: Stornorechnung mit negativen Positionen (sofort erzeugt) und – auf Wunsch – eine
    neue Rechnung als Entwurf mit denselben Positionen zur Korrektur. → (Storno, neue Rechnung oder None)."""
    if not benutzer.hat_recht("dokumente_finalisieren"):
        raise PermissionError("Stornieren darf nur, wer das Recht „Dokumente finalisieren“ hat.")
    dok = _sperren(dok)
    grund = (grund or "").strip()
    if dok.art != FallDokument.Art.RECHNUNG:
        raise ValidationError({"fehler": "Nur Rechnungen werden storniert."})
    if not dok.ist_final:
        raise ValidationError({"fehler": "Eine noch nicht finale Rechnung wird einfach geändert und neu erzeugt."})
    if dok.storniert_am:
        raise ValidationError({"fehler": "Diese Rechnung ist bereits storniert."})
    if not grund:
        raise ValidationError({"storno_grund": "Bitte den Grund angeben."})
    if len(grund) > 300:
        raise ValidationError({"storno_grund": "Höchstens 300 Zeichen."})
    dok.fall.pruefe_offen()
    positionen = list(dok.positionen.all())
    storno = FallDokument(patient=dok.patient, fall=dok.fall, art=FallDokument.Art.STORNO, storno_zu=dok,
                          titel=f"Stornorechnung zu {dok.rechnungsnummer}"[:200], freitext=grund,
                          unterzeichner=dok.unterzeichner, erstellt_von=benutzer)
    storno._history_user = benutzer
    storno.save()
    for p in positionen:
        _kopie(p, storno, -p.menge)
    dok.storniert_am, dok.storniert_von, dok.storno_grund = timezone.now(), benutzer, grund
    dok._history_user = benutzer
    dok.save(update_fields=list(FallDokument.STORNO_FELDER) + ["geaendert_am"])
    erzeugen(storno, benutzer, grund=f"Storno: {grund}")
    neu = None
    if neue_rechnung:
        neu = FallDokument(patient=dok.patient, fall=dok.fall, art=FallDokument.Art.RECHNUNG, titel="Rechnung",
                           freitext=dok.freitext, zahlungsziel_tage=dok.zahlungsziel_tage, erstellt_von=benutzer)
        neu._history_user = benutzer
        neu.save()
        for p in positionen:
            _kopie(p, neu, p.menge)
    return storno, neu


def _kopie(p: Rechnungsposition, ziel, menge):
    k = Rechnungsposition(dokument=ziel, reihenfolge=p.reihenfolge, leistung=p.leistung, code=p.code, text=p.text,
                          datum=p.datum, menge=menge, einheit=p.einheit, einzelpreis=p.einzelpreis, ust_satz=p.ust_satz)
    k.save()
    return k


# ====================================================================== DOCX zur Nachbearbeitung
KENNUNG = re.compile(r"\[\[([a-z_]+(?::\d+)?)\]\]")


def docx_felder(dok: FallDokument) -> list[tuple[str, str, str]]:
    """[(Kennung, Bezeichnung, Text)] der Freitexte des Dokuments."""
    fall = dok.fall
    felder = [(f, str(Behandlungsfall._meta.get_field(f).verbose_name), getattr(fall, f) or "")
              for f in Behandlungsfall.FREITEXTE.get(dok.art, [])]
    if dok.ist_rechnung:
        felder += [(f"position:{p.pk}", f"Position {i}" + (f" ({p.code})" if p.code else ""), p.text)
                   for i, p in enumerate(dok.positionen.all(), 1)]
    felder.append(("freitext", "Zusätzlicher Text des Dokuments", dok.freitext or ""))
    return felder


def docx_export(dok: FallDokument) -> bytes:
    from docx import Document
    from docx.shared import Pt

    d = Document()
    d.add_heading(f"{dok.titel} – {dok.patient.nachname}, {dok.patient.vorname}", level=1)
    d.add_paragraph(f"Fall {dok.fall.nummer} · Dokument {dok.pk} · Stand {timezone.localtime():%d.%m.%Y %H:%M}")
    hinweis = d.add_paragraph("Bitte nur die Texte in der rechten Spalte ändern. Die Kennungen in [[…]] links nicht "
                              "verändern. Danach die Datei in EPM unter „DOCX übernehmen“ hochladen – EPM übernimmt die "
                              "Texte in den Fall und erzeugt eine neue PDF.")
    hinweis.runs[0].italic = True
    tabelle = d.add_table(rows=0, cols=2)
    tabelle.style = "Table Grid"
    for kennung, name, text in docx_felder(dok):
        zeile = tabelle.add_row().cells
        zeile[0].text = f"{name}\n[[{kennung}]]"
        for lauf in zeile[0].paragraphs[-1].runs:
            lauf.font.size = Pt(7)
        absaetze = (text or "").split("\n")
        zeile[1].text = absaetze[0]
        for a in absaetze[1:]:
            zeile[1].add_paragraph(a)
    puffer = io.BytesIO()
    d.core_properties.title = dok.titel
    d.core_properties.identifier = f"epm-falldokument-{dok.pk}"
    d.save(puffer)
    return puffer.getvalue()


def docx_lesen(dok: FallDokument, inhalt: bytes) -> dict[str, str]:
    from docx import Document

    try:
        d = Document(io.BytesIO(inhalt))
    except Exception:
        raise ValidationError({"datei": "Bitte die aus EPM heruntergeladene DOCX-Datei hochladen."})
    if d.core_properties.identifier != f"epm-falldokument-{dok.pk}":
        raise ValidationError({"datei": "Diese DOCX gehört zu einem anderen Dokument."})
    erlaubt = {k for k, _, _ in docx_felder(dok)}
    werte = {}
    for tabelle in d.tables:
        for zeile in tabelle.rows:
            if len(zeile.cells) < 2:
                continue
            m = KENNUNG.search(zeile.cells[0].text)
            if m and m.group(1) in erlaubt:
                werte[m.group(1)] = "\n".join(p.text for p in zeile.cells[1].paragraphs).strip()
    if not werte:
        raise ValidationError({"datei": "In der DOCX stehen keine Texte dieses Dokuments."})
    return werte


@transaction.atomic
def docx_import(dok: FallDokument, datei, benutzer) -> tuple[list[str], DokumentVersion]:
    """Übernimmt geänderte Freitexte aus der DOCX in Fall, Dokument und Positionen und erzeugt eine neue Fassung.
    Die hochgeladene DOCX liegt (ausgeblendet) in der Akte und hängt an der Fassung."""
    dok = _sperren(dok)
    dok.pruefe_aenderbar()
    dok.fall.pruefe_offen()
    if datei.size > MAX_UPLOAD:
        raise ValidationError({"datei": "Die Datei ist größer als 25 MB."})
    inhalt = datei.read()
    werte = docx_lesen(dok, inhalt)
    fall = Behandlungsfall.objects.select_for_update().get(pk=dok.fall_id)
    geaendert, fall_geaendert, dok_geaendert = [], [], False
    for kennung, text in werte.items():
        if kennung.startswith("position:"):
            p = dok.positionen.filter(pk=int(kennung.split(":")[1])).first()
            if p is not None and text and p.text != text[:500]:
                p.text = text[:500]
                p._history_user = benutzer
                p.save()
                geaendert.append(kennung)
        elif kennung == "freitext":
            if dok.freitext != text:
                dok.freitext = text
                dok_geaendert = True
                geaendert.append(kennung)
        elif getattr(fall, kennung) != text:
            setattr(fall, kennung, text)
            fall_geaendert.append(kennung)
            geaendert.append(kennung)
    if not geaendert:
        raise ValidationError({"datei": "Die DOCX enthält keine Änderungen."})
    if fall_geaendert:
        fall._history_user = benutzer
        fall.save()
    if dok_geaendert:
        dok._history_user = benutzer
        dok.save()
    docx_dok = _ablegen(dok, inhalt,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        _dateiname(dok, "bearbeitet", "docx"), benutzer, titel=f"{dok.titel} (DOCX bearbeitet)")
    dok.refresh_from_db()
    v = erzeugen(dok, benutzer, grund="Freitexte aus DOCX übernommen: " + ", ".join(geaendert),
                 art=DokumentVersion.Art.DOCX, docx=docx_dok)
    return geaendert, v
