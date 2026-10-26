"""Mitgelieferte Vorlagen der Dokumentenautomation (26.10.2026).

- OP-Bericht, Entlassungsbrief, Konsiliarbericht und Rechnung je Sprache (DE/LV/EN) als eigene Schreiben der RGC in der
  Gruppe „fall“ (``eigen-rgc-<art>-<sprache>``). Sie entstehen nur im Behandlungsfall, nicht als Schreiben der Akte.
- Fachspezifische Zusatzbögen zur Aufklärung Operation (Vorlage 07) für Orthopädie/Traumatologie, HNO sowie Adipositas
  und Stoffwechselerkrankungen, zweisprachig DE/LV wie der Grundbogen (``eigen-rgc-z07-…``, Gruppe „formulare“).

Die Datenmigration ``faelle.0002`` legt sie einmal an (Kennung ``mitgeliefert``); danach werden sie unter Vorlagen ›
Dokumentvorlagen wie jede eigene Vorlage gepflegt. Die medizinischen Inhalte der Zusatzbögen sind ein standardisierter
Vorschlag und vor dem Einsatz fachärztlich zu prüfen (wie die lettischen Fassungen von 07/08).
"""

KOPF = {"id": "kopf", "typ": "briefkopf", "bezeichnung": "Briefkopf", "absender": True, "falzmarken": False,
        "briefpapier": "rgc"}
FUSS = {"id": "fuss", "typ": "fusszeile", "bezeichnung": "Fußzeile",
        "text": "{{Absender.Name}} · {{Absender.Straße}} · {{Absender.PLZ_Ort}}\n{{Absender.Telefon}} · "
                "{{Absender.E-Mail}}\n{{Absender.Fußzeile}}", "rechts": "{Seite}/{Seiten}"}

L = {  # Beschriftungen je Sprache
    "op_bericht": ("OP-Bericht", "Operācijas protokols", "Operation report"),
    "entlassbrief": ("Entlassungsbrief", "Izraksts no slimības vēstures (epikrīze)", "Discharge letter"),
    "konsil": ("Konsiliarbericht", "Konsultācijas atzinums", "Consultation report"),
    "rechnung": ("Rechnung", "Rēķins", "Invoice"),
    "patient": ("Patient/in und Fall", "Pacients un gadījums", "Patient and case"),
    "name": ("Name", "Vārds, uzvārds", "Name"),
    "geburt": ("Geburtsdatum", "Dzimšanas datums", "Date of birth"),
    "pid": ("Patienten-ID", "Pacienta ID", "Patient ID"),
    "fall": ("Fallnummer", "Gadījuma numurs", "Case number"),
    "kostentraeger": ("Kostenträger", "Maksātājs", "Payer"),
    "versicherung": ("Versichertennummer", "Apdrošināšanas numurs", "Insurance number"),
    "aktenzeichen": ("Aktenzeichen", "Lietas numurs", "Reference"),
    "partner": ("Kooperationspartner", "Sadarbības partneris", "Cooperation partner"),
    "aufnahme": ("Aufnahme", "Iestāšanās", "Admission"),
    "entlassung": ("Entlassung", "Izrakstīšana", "Discharge"),
    "zeitraum": ("Behandlungszeitraum", "Ārstēšanas periods", "Treatment period"),
    "op_datum": ("OP-Datum", "Operācijas datums", "Date of surgery"),
    "eingriff": ("Eingriff", "Operācija", "Procedure"),
    "diagnose": ("Diagnose", "Diagnoze", "Diagnosis"),
    "operateur": ("Operateur", "Operētājs", "Surgeon"),
    "assistenz": ("Assistenz", "Asistents", "Assistant"),
    "anaesthesie": ("Anästhesie", "Anestēzija", "Anaesthesia"),
    "indikation": ("Indikation", "Indikācijas", "Indication"),
    "verlauf_op": ("OP-Verlauf", "Operācijas gaita", "Operative procedure"),
    "befund_op": ("Befund und Ergebnis", "Atradne un rezultāts", "Findings and result"),
    "verlauf": ("Verlauf", "Slimības gaita", "Clinical course"),
    "befunde": ("Befunde", "Izmeklējumu rezultāti", "Findings"),
    "medikation": ("Medikation bei Entlassung", "Medikamenti izrakstoties", "Medication on discharge"),
    "empfehlung": ("Empfehlung und weiteres Vorgehen", "Ieteikumi un turpmākā rīcība", "Recommendations and follow-up"),
    "konsil_an": ("Konsil an", "Konsultācija pie", "Consultation requested from"),
    "frage": ("Fragestellung", "Jautājums", "Question"),
    "konsil_befund": ("Befund", "Atradne", "Findings"),
    "beurteilung": ("Beurteilung und Empfehlung", "Slēdziens un ieteikumi", "Assessment and recommendation"),
    "anmerkung": ("Anmerkung", "Piezīmes", "Remarks"),
    "arzt": ("Ärztin / Arzt", "Ārsts", "Physician"),
    "funktion": ("Funktion", "Amats", "Position"),
    "linie": ("Rīga, Datum, Unterschrift", "Rīga, datums, paraksts", "Riga, date, signature"),
    "empfaenger": ("Rechnungsempfänger", "Rēķina saņēmējs", "Bill to"),
    "rechnungsnr": ("Rechnungsnummer", "Rēķina numurs", "Invoice number"),
    "rechnungsdatum": ("Rechnungsdatum", "Rēķina datums", "Invoice date"),
    "leistungen": ("Leistungen", "Pakalpojumi", "Services"),
    "bank": ("Bankverbindung", "Bankas rekvizīti", "Bank details"),
    "zahlung": ("Zahlung", "Apmaksa", "Payment"),
    "einleitung": (
        "Sehr geehrte Kolleginnen und Kollegen,\n\nwir berichten über die Behandlung von {{Patient.Vorname_Name}}, "
        "geb. {{Patient.Geburtsdatum}}, in unserer Klinik im Zeitraum {{Fall.Zeitraum}}.",
        "Godātie kolēģi!\n\nInformējam par pacienta {{Patient.Vorname_Name}}, dzim. {{Patient.Geburtsdatum}}, "
        "ārstēšanu mūsu klīnikā laika posmā {{Fall.Zeitraum}}.",
        "Dear colleagues,\n\nwe report on the treatment of {{Patient.Vorname_Name}}, born {{Patient.Geburtsdatum}}, at "
        "our clinic during {{Fall.Zeitraum}}."),
    "konsil_einleitung": (
        "Sehr geehrte Kollegin, sehr geehrter Kollege,\n\nwir bitten um konsiliarische Mitbeurteilung von "
        "{{Patient.Vorname_Name}}, geb. {{Patient.Geburtsdatum}}.",
        "Godātais kolēģi!\n\nLūdzam konsultēt pacientu {{Patient.Vorname_Name}}, dzim. {{Patient.Geburtsdatum}}.",
        "Dear colleague,\n\nwe kindly ask for your consultation regarding {{Patient.Vorname_Name}}, born "
        "{{Patient.Geburtsdatum}}."),
    "gruss": ("Mit freundlichen kollegialen Grüßen", "Ar cieņu", "Kind regards"),
}
SPRACHEN = ("de", "lv", "en")
NAMEN = {"op_bericht": "OP-Bericht", "entlassbrief": "Entlassungsbrief", "konsil": "Konsiliarbericht",
         "rechnung": "Rechnung"}
SPRACHNAMEN = {"de": "Deutsch", "lv": "Lettisch", "en": "Englisch"}


def _t(schluessel, sprache):
    return L[schluessel][SPRACHEN.index(sprache)]


def _text(kennung, schluessel, feld, s, ueberschrift=True):
    return {"id": kennung, "typ": "text", "bezeichnung": _t(schluessel, s), "text": feld,
            "optionen": {"ueberschrift": ueberschrift, "ausblenden_wenn_leer": True}}


def _patient(s, *weitere):
    felder = [{"label": _t("name", s), "wert": "{{Patient.Name}}"},
              {"label": _t("geburt", s), "wert": "{{Patient.Geburtsdatum}}"},
              {"label": _t("pid", s), "wert": "{{Patient.Nummer}}"},
              {"label": _t("fall", s), "wert": "{{Fall.Nummer}}"}]
    felder += [{"label": _t(k, s), "wert": w} for k, w in weitere]
    return {"id": "patient", "typ": "datenfelder", "bezeichnung": _t("patient", s), "spalten": 2, "felder": felder,
            "optionen": {"ueberschrift": True}}


def _unterschrift(s):
    return {"id": "unterschrift", "typ": "unterschrift", "bezeichnung": "Unterschrift", "linie": _t("linie", s),
            "felder": [{"label": _t("arzt", s), "wert": "{{Dokument.Unterzeichner}}"},
                       {"label": _t("funktion", s), "wert": "{{Dokument.Unterzeichner_Funktion}}"}],
            "optionen": {"nicht_teilen": True}}


def _titel(art, s):
    return {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": _t(art, s), "zusatz": "{{Fall.Nummer}}"}


def op_bericht(s):
    return [
        KOPF, _titel("op_bericht", s),
        _patient(s, ("op_datum", "{{Fall.OP_Datum}}"), ("eingriff", "{{Fall.Eingriff}}"),
                 ("operateur", "{{Fall.Operateur}}"), ("assistenz", "{{Fall.Assistenz}}"),
                 ("anaesthesie", "{{Fall.Anästhesie}}"), ("aufnahme", "{{Fall.Aufnahme}}")),
        _text("diagnose", "diagnose", "{{Fall.Diagnose}}", s),
        _text("indikation", "indikation", "{{Fall.OP_Indikation}}", s),
        _text("verlauf", "verlauf_op", "{{Fall.OP_Verlauf}}", s),
        _text("befund", "befund_op", "{{Fall.OP_Befund}}", s),
        _text("anmerkung", "anmerkung", "{{Dokument.Freitext}}", s),
        _unterschrift(s), FUSS,
    ]


def entlassbrief(s):
    return [
        KOPF,
        {"id": "empfaenger", "typ": "zweispaltig", "bezeichnung": "Empfänger und Datum",
         "links": "{{Patient.Hausarzt}}", "rechts": "Rīga, {{Heute}}"},
        _titel("entlassbrief", s),
        _patient(s, ("zeitraum", "{{Fall.Zeitraum}}"), ("eingriff", "{{Fall.Eingriff}}"),
                 ("op_datum", "{{Fall.OP_Datum}}"), ("kostentraeger", "{{Fall.Kostenträger}}")),
        {"id": "einleitung", "typ": "text", "bezeichnung": "Einleitung", "text": _t("einleitung", s)},
        _text("diagnose", "diagnose", "{{Fall.Diagnose}}", s),
        _text("verlauf", "verlauf", "{{Fall.Verlauf}}", s),
        _text("befunde", "befunde", "{{Fall.Befunde}}", s),
        _text("medikation", "medikation", "{{Fall.Entlassmedikation}}", s),
        _text("empfehlung", "empfehlung", "{{Fall.Empfehlung}}", s),
        _text("anmerkung", "anmerkung", "{{Dokument.Freitext}}", s),
        {"id": "gruss", "typ": "text", "bezeichnung": "Gruß", "text": _t("gruss", s),
         "optionen": {"nicht_teilen": True}},
        _unterschrift(s), FUSS,
    ]


def konsil(s):
    return [
        KOPF,
        {"id": "empfaenger", "typ": "zweispaltig", "bezeichnung": "Empfänger und Datum",
         "links": "{{Fall.Konsil_an}}", "rechts": "Rīga, {{Heute}}"},
        _titel("konsil", s),
        _patient(s, ("eingriff", "{{Fall.Eingriff}}"), ("op_datum", "{{Fall.OP_Datum}}")),
        {"id": "einleitung", "typ": "text", "bezeichnung": "Einleitung", "text": _t("konsil_einleitung", s)},
        _text("diagnose", "diagnose", "{{Fall.Diagnose}}", s),
        _text("frage", "frage", "{{Fall.Konsil_Fragestellung}}", s),
        _text("befund", "konsil_befund", "{{Fall.Konsil_Befund}}", s),
        _text("beurteilung", "beurteilung", "{{Fall.Konsil_Beurteilung}}", s),
        _text("anmerkung", "anmerkung", "{{Dokument.Freitext}}", s),
        {"id": "gruss", "typ": "text", "bezeichnung": "Gruß", "text": _t("gruss", s),
         "optionen": {"nicht_teilen": True}},
        _unterschrift(s), FUSS,
    ]


def rechnung(s):
    return [
        KOPF,
        {"id": "empfaenger", "typ": "zweispaltig", "bezeichnung": _t("empfaenger", s),
         "links": "{{Fall.Rechnungsempfänger}}", "rechts": "Rīga, {{Rechnung.Datum}}"},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": "{{Rechnung.Titel}} {{Rechnung.Nummer}}",
         "zusatz": "{{Rechnung.Bezug}}"},
        _patient(s, ("rechnungsdatum", "{{Rechnung.Datum}}"), ("zeitraum", "{{Fall.Zeitraum}}"),
                 ("eingriff", "{{Fall.Eingriff}}"), ("kostentraeger", "{{Fall.Kostenträger}}"),
                 ("versicherung", "{{Fall.Versichertennummer}}"), ("aktenzeichen", "{{Fall.Aktenzeichen}}"),
                 ("partner", "{{Fall.Kooperationspartner}}")),
        {"id": "positionen", "typ": "tabelle", "bezeichnung": _t("leistungen", s), "quelle": "rechnung",
         "optionen": {"ueberschrift": True}},
        {"id": "zahlung", "typ": "text", "bezeichnung": _t("zahlung", s),
         "text": "{{Rechnung.USt_Hinweis}}\n{{Rechnung.Zahlungsziel}}", "optionen": {"ausblenden_wenn_leer": True}},
        _text("anmerkung", "anmerkung", "{{Dokument.Freitext}}", s, ueberschrift=False),
        _text("bank", "bank", "{{Absender.Bankverbindung}}", s),
        _unterschrift(s), FUSS,
    ]


ERZEUGER = {"op_bericht": op_bericht, "entlassbrief": entlassbrief, "konsil": konsil, "rechnung": rechnung}
BESCHREIBUNG = {
    "op_bericht": "OP-Bericht aus den Angaben des Behandlungsfalls",
    "entlassbrief": "Entlassungsbrief an Hausarzt bzw. weiterbehandelnde Ärzte aus dem Behandlungsfall",
    "konsil": "Konsiliarbericht bzw. Konsilanforderung aus dem Behandlungsfall",
    "rechnung": "Rechnung bzw. Stornorechnung mit den Leistungspositionen des Falls",
}


def schluessel(art: str, sprache: str) -> str:
    return f"eigen-rgc-{art}-{sprache}"


def fall_vorlagen() -> list[dict]:
    """[{schluessel, name, beschreibung, gruppe, mitgeliefert, bloecke}] der Fall-Dokumente je Sprache."""
    return [{"schluessel": schluessel(art, s), "name": f"{NAMEN[art]} ({SPRACHNAMEN[s]})",
             "beschreibung": BESCHREIBUNG[art], "gruppe": "fall", "mitgeliefert": f"rgc-fall-{art}-{s}",
             "bloecke": erzeuger(s)}
            for art, erzeuger in ERZEUGER.items() for s in SPRACHEN]


# ====================================================================== Zusatzbögen zu Vorlage 07
def _zusatz(kennung, titel_de, titel_lv, eingriffe, risiken, nachher, fragen):
    bloecke = [
        {**KOPF, "absender": False},
        {"id": "titel", "typ": "titel", "bezeichnung": "Titel", "text": f"Zusatzbogen {titel_de} / Papildlapa: {titel_lv}",
         "zusatz": "Ergänzung zur Aufklärung Operation (Vorlage 07) · Papildinājums operācijas informētajai piekrišanai (veidlapa 07)"},
        {"id": "stand", "typ": "text", "bezeichnung": "Stand der Vorlage",
         "text": f"Zusatzbogen {kennung} zu Vorlage 07 · Version 1 · Stand 10/2026 · standardisierter Vorschlag, vor dem "
                 "Einsatz fachärztlich zu prüfen",
         "optionen": {"schrift": "klein"}},
        {"id": "patient", "typ": "datenfelder", "bezeichnung": "Patient/in · Pacients", "spalten": 2,
         "optionen": {"ueberschrift": True}, "felder": [
             {"label": "Name · Vārds, uzvārds", "wert": "{{Patient.Name}}"},
             {"label": "Geburtsdatum · Dzimšanas datums", "wert": "{{Patient.Geburtsdatum}}"},
             {"label": "Patienten-ID · Pacienta ID", "wert": "{{Patient.Nummer}}"},
             {"label": "Fall · Gadījums", "wert": "{{Fall.Nummer}}"},
             {"label": "Geplanter Eingriff · Plānotā operācija", "wert": "{{Fall.Eingriff}}"},
             {"label": "OP-Datum · Operācijas datums", "wert": "{{Fall.OP_Datum}}"}]},
        {"id": "eingriffe", "typ": "text", "bezeichnung": "Geplanter Eingriff (ankreuzen) · Plānotā operācija (atzīmēt)",
         "text": "\n".join(f"☐ {de} · {lv}" for de, lv in eingriffe) + "\n☐ Anderer Eingriff · Cita operācija: "
                 "______________________________", "optionen": {"ueberschrift": True}},
        {"id": "risiken", "typ": "text", "bezeichnung": "Eingriffsspezifische Risiken · Operācijai specifiskie riski",
         "text": "Zusätzlich zu den allgemeinen Risiken des Grundbogens (Vorlage 07) wurde ich insbesondere über "
                 "folgende Risiken aufgeklärt · Papildus vispārējiem riskiem (veidlapa 07) esmu informēts(-a) īpaši "
                 "par šādiem riskiem:\n" + "\n".join(f"• {de} · {lv}" for de, lv in risiken),
         "optionen": {"ueberschrift": True}},
        {"id": "nachher", "typ": "text", "bezeichnung": "Nach dem Eingriff · Pēc operācijas",
         "text": "\n".join(f"• {de} · {lv}" for de, lv in nachher), "optionen": {"ueberschrift": True}},
        {"id": "fragen", "typ": "text", "bezeichnung": "Ergänzende Fragen · Papildu jautājumi",
         "text": "\n".join(f"{de} · {lv}   ☐ ja / jā   ☐ nein / nē" for de, lv in fragen),
         "optionen": {"ueberschrift": True}},
        {"id": "anmerkungen", "typ": "text", "bezeichnung": "Besprochene Besonderheiten · Pārrunātās īpatnības",
         "text": "______________________________________________________________________\n"
                 "______________________________________________________________________",
         "optionen": {"ueberschrift": True}},
        {"id": "erklaerung", "typ": "text", "bezeichnung": "Erklärung · Apliecinājums",
         "text": "Ich bin zusätzlich zum Grundbogen (Vorlage 07) in einem Gespräch über den geplanten Eingriff, seine "
                 "spezifischen Risiken, mögliche Alternativen und das Verhalten danach aufgeklärt worden. Meine Fragen "
                 "wurden verständlich beantwortet. Ich willige in den Eingriff ein.\n\n"
                 "Papildus pamatveidlapai (veidlapa 07) sarunā esmu informēts(-a) par plānoto operāciju, tās "
                 "specifiskajiem riskiem, iespējamām alternatīvām un rīcību pēc tās. Uz maniem jautājumiem ir sniegtas "
                 "saprotamas atbildes. Es piekrītu operācijai.",
         "optionen": {"ueberschrift": True, "nicht_teilen": True}},
        {"id": "u_patient", "typ": "unterschrift", "bezeichnung": "Unterschrift Patient/in",
         "linie": "Rīga, Datum, Unterschrift Patient/in · datums, pacienta paraksts", "optionen": {"nicht_teilen": True}},
        {"id": "u_arzt", "typ": "unterschrift", "bezeichnung": "Unterschrift Ärztin/Arzt",
         "linie": "Unterschrift aufklärende Ärztin/aufklärender Arzt · informējošā ārsta paraksts",
         "felder": [{"label": "Ärztin/Arzt · Ārsts", "wert": "{{Dokument.Unterzeichner}}"}],
         "optionen": {"nicht_teilen": True, "neben_vorherigem": "haelfte"}},
        FUSS,
    ]
    return bloecke


ORTHOPAEDIE = _zusatz(
    "Orthopädie/Traumatologie", "Orthopädie / Traumatologie", "Ortopēdija / traumatoloģija",
    eingriffe=[("Gelenkersatz (Endoprothese) Hüfte / Knie / Schulter", "Locītavas endoprotezēšana – gūža / celis / plecs"),
               ("Arthroskopie (Gelenkspiegelung)", "Artroskopija"),
               ("Osteosynthese (Platte, Nagel, Schrauben) nach Fraktur", "Osteosintēze (plate, intramedulārā nagla, "
                "skrūves) pēc lūzuma"),
               ("Eingriff an Bändern, Sehnen oder Meniskus", "Saišu, cīpslu vai meniska operācija"),
               ("Eingriff an der Wirbelsäule", "Mugurkaula operācija"),
               ("Metallentfernung", "Metāla konstrukcijas izņemšana")],
    risiken=[("Thrombose und Lungenembolie; Thromboseprophylaxe erforderlich",
              "Tromboze un plaušu artērijas embolija; nepieciešama trombozes profilakse"),
             ("Infektion des Gelenks, Knochens oder Implantats, ggf. mit Folgeoperation oder Implantatwechsel",
              "Locītavas, kaula vai implanta infekcija, iespējama atkārtota operācija vai implanta nomaiņa"),
             ("Verletzung von Nerven und Gefäßen mit Gefühlsstörung, Lähmung oder Blutung",
              "Nervu un asinsvadu bojājums ar jušanas traucējumiem, parēzi vai asiņošanu"),
             ("Lockerung, Bruch oder Verschleiß des Implantats; Luxation (Ausrenkung) einer Prothese",
              "Implanta izkustēšanās, lūzums vai nolietojums; endoprotēzes izmežģījums"),
             ("Bewegungseinschränkung, Gelenksteife, Beinlängendifferenz, Fehlstellung",
              "Kustību ierobežojums, locītavas stīvums, kāju garuma atšķirība, nepareizs stāvoklis"),
             ("Verzögerte oder ausbleibende Knochenheilung (Pseudarthrose)",
              "Aizkavēta vai neiestājusies kaula saaugšana (pseidoartroze)"),
             ("Komplexes regionales Schmerzsyndrom (CRPS), anhaltende Schmerzen",
              "Komplekss reģionāls sāpju sindroms (CRPS), ilgstošas sāpes")],
    nachher=[("Teilbelastung bzw. Entlastung wie ärztlich angeordnet, Gehstützen",
              "Daļēja slodze vai atslogošana pēc ārsta norādījuma, kruķi"),
             ("Thromboseprophylaxe für die verordnete Dauer", "Trombozes profilakse noteikto laiku"),
             ("Physiotherapie und Kontrolluntersuchungen (Röntgen) nach Plan",
              "Fizioterapija un kontroles izmeklējumi (rentgens) pēc plāna"),
             ("Bei Fieber, Rötung, Schwellung oder Wundsekretion sofort melden",
              "Drudža, apsārtuma, tūskas vai brūces izdalījumu gadījumā nekavējoties ziņot")],
    fragen=[("Frühere Thrombose oder Lungenembolie?", "Iepriekš bijusi tromboze vai plaušu embolija?"),
            ("Bekannte Metallallergie (z. B. Nickel, Kobalt, Chrom)?", "Zināma alerģija pret metāliem (niķelis, kobalts, hroms)?"),
            ("Frühere Operationen oder Implantate an der betroffenen Stelle?",
             "Iepriekšējas operācijas vai implanti attiecīgajā vietā?"),
            ("Einnahme von Blutverdünnern oder Kortison?", "Lietojat asins šķidrinātājus vai kortikosteroīdus?")])

HNO = _zusatz(
    "HNO", "HNO (Hals, Nase, Ohren)", "LOR (ausis, kakls, deguns)",
    eingriffe=[("Tonsillektomie / Tonsillotomie (Mandeln)", "Tonsilektomija / tonsilotomija (mandeles)"),
               ("Septumplastik / Nasenmuschelverkleinerung", "Deguna starpsienas plastika / deguna gliemežnīcu samazināšana"),
               ("Nasennebenhöhlenoperation (FESS)", "Deguna blakusdobumu operācija (FESS)"),
               ("Paukendrainage / Mittelohr- oder Trommelfelloperation", "Bungplēvītes drenāža / vidusauss vai bungplēvītes operācija"),
               ("Eingriff an Kehlkopf oder Stimmlippen (Mikrolaryngoskopie)", "Balsenes vai balss saišu operācija (mikrolaringoskopija)"),
               ("Eingriff an Speicheldrüse oder Hals", "Siekalu dziedzera vai kakla operācija")],
    risiken=[("Nachblutung, bei Mandeloperationen auch noch bis etwa 3 Wochen danach – ggf. Notfalloperation",
              "Pēcoperācijas asiņošana, pēc mandeļu operācijas līdz apmēram 3 nedēļām – iespējama neatliekama operācija"),
             ("Schluckbeschwerden, Schmerzen, Geschmacksstörung", "Rīšanas traucējumi, sāpes, garšas traucējumi"),
             ("Verletzung von Zähnen, Lippen oder Zunge durch Instrumente", "Zobu, lūpu vai mēles bojājums ar instrumentiem"),
             ("Riechstörung, Verwachsungen, Nasenbluten, Perforation der Nasenscheidewand",
              "Ožas traucējumi, saaugumi, deguna asiņošana, starpsienas perforācija"),
             ("Selten: Verletzung von Augenhöhle, Schädelbasis mit Nervenwasserfluss, Sehstörung",
              "Reti: acs dobuma, galvaskausa pamatnes bojājums ar likvora tecēšanu, redzes traucējumi"),
             ("Hörminderung, Ohrgeräusche, Schwindel; selten Gesichtsnervenlähmung",
              "Dzirdes pasliktināšanās, troksnis ausīs, reibonis; reti sejas nerva parēze"),
             ("Heiserkeit oder Stimmveränderung", "Aizsmakums vai balss izmaiņas")],
    nachher=[("Bei jeder Blutung aus Mund oder Nase sofort ärztliche Hilfe (Notruf 113 bzw. 112)",
              "Jebkuras asiņošanas no mutes vai deguna gadījumā nekavējoties meklēt palīdzību (113 vai 112)"),
             ("Kein Schnäuzen, keine schwere körperliche Anstrengung, keine Sauna für die angeordnete Zeit",
              "Nešņaukt degunu, izvairīties no smagas fiziskas slodzes un pirts noteikto laiku"),
             ("Weiche, kühle Kost; keine scharfen oder sauren Speisen", "Mīksts, vēss ēdiens; bez asiem un skābiem ēdieniem"),
             ("Flugreisen nur nach ärztlicher Freigabe", "Lidojumi tikai pēc ārsta atļaujas")],
    fragen=[("Neigung zu Blutungen oder blauen Flecken (auch in der Familie)?",
             "Nosliece uz asiņošanu vai zilumiem (arī ģimenē)?"),
            ("Einnahme von Blutverdünnern, ASS oder Schmerzmitteln?", "Lietojat asins šķidrinātājus, aspirīnu vai pretsāpju līdzekļus?"),
            ("Lockere Zähne, Zahnersatz oder Kronen?", "Kustīgi zobi, protēzes vai kroņi?"),
            ("Schnarchen oder Atemaussetzer im Schlaf?", "Krākšana vai elpošanas pauzes miegā?")])

ADIPOSITAS = _zusatz(
    "Adipositas/Stoffwechsel", "Adipositas und Stoffwechselerkrankungen", "Aptaukošanās un vielmaiņas slimības",
    eingriffe=[("Schlauchmagen (Sleeve-Gastrektomie)", "Kuņģa piedurknes rezekcija (sleeve)"),
               ("Roux-en-Y-Magenbypass", "Roux-en-Y kuņģa šuntēšana"),
               ("Omega-Loop- / Mini-Bypass", "Omega cilpas / mini šuntēšana"),
               ("Revisions- oder Umwandlungsoperation", "Revīzijas vai konversijas operācija"),
               ("Magenballon (endoskopisch)", "Kuņģa balons (endoskopiski)")],
    risiken=[("Undichtigkeit der Klammernaht oder Verbindung (Leckage) mit Bauchfellentzündung, ggf. Folgeoperation",
              "Skavu šuves vai savienojuma nehermētiskums (noplūde) ar peritonītu, iespējama atkārtota operācija"),
             ("Blutung, Thrombose und Lungenembolie (erhöhtes Risiko bei Adipositas)",
              "Asiņošana, tromboze un plaušu embolija (paaugstināts risks aptaukošanās gadījumā)"),
             ("Engstelle (Stenose), Geschwür an der Verbindung, Sodbrennen (Reflux)",
              "Sašaurinājums (stenoze), čūla savienojuma vietā, grēmas (reflukss)"),
             ("Dumping-Syndrom, Unterzuckerung nach dem Essen", "Dempinga sindroms, hipoglikēmija pēc ēšanas"),
             ("Mangel an Vitaminen, Eisen, Eiweiß und Spurenelementen – lebenslange Ergänzung und Kontrollen nötig",
              "Vitamīnu, dzelzs, olbaltumvielu un mikroelementu deficīts – nepieciešama mūža papildināšana un kontrole"),
             ("Innere Hernie, Darmverschluss, Gallensteine", "Iekšējā trūce, zarnu nosprostojums, žultsakmeņi"),
             ("Unzureichende Gewichtsabnahme oder erneute Gewichtszunahme; psychische Belastung",
              "Nepietiekams svara zudums vai atkārtota svara pieaugšana; psihiska slodze")],
    nachher=[("Kostaufbau in Stufen (flüssig, püriert, weich, fest) nach Ernährungsplan",
              "Pakāpeniska diēta (šķidra, biezeņa, mīksta, cieta) pēc uztura plāna"),
             ("Lebenslang Vitamine und Mineralstoffe nach Verordnung, Laborkontrollen nach Plan",
              "Visu mūžu vitamīni un minerālvielas pēc norādījuma, laboratoriskā kontrole pēc plāna"),
             ("Keine Schwangerschaft in den ersten 12–18 Monaten; sichere Verhütung",
              "Izvairīties no grūtniecības pirmos 12–18 mēnešus; droša kontracepcija"),
             ("Medikamente (z. B. Diabetes, Blutdruck) nach ärztlicher Anpassung",
              "Medikamentu (piem., diabēta, asinsspiediena) devas pēc ārsta korekcijas"),
             ("Bei Bauchschmerzen, Fieber, Herzrasen oder Erbrechen sofort melden",
              "Sāpju vēderā, drudža, sirdsklauvju vai vemšanas gadījumā nekavējoties ziņot")],
    fragen=[("Diabetes mellitus, Schlafapnoe oder Bluthochdruck bekannt?",
             "Zināms cukura diabēts, miega apnoja vai paaugstināts asinsspiediens?"),
            ("Frühere Bauchoperationen?", "Iepriekšējas vēdera operācijas?"),
            ("Rauchen? (Rauchstopp mindestens 4 Wochen vor dem Eingriff empfohlen)",
             "Smēķēšana? (ieteicams atmest vismaz 4 nedēļas pirms operācijas)"),
            ("Ernährungs- und psychologische Vorbereitung abgeschlossen?",
             "Uztura un psiholoģiskā sagatavošana pabeigta?")])

ZUSATZBOEGEN = {
    "orthopaedie": ("eigen-rgc-z07-ortho", "Zusatzbogen 07 – Orthopädie / Traumatologie (DE/LV)", ORTHOPAEDIE),
    "hno": ("eigen-rgc-z07-hno", "Zusatzbogen 07 – HNO (DE/LV)", HNO),
    "adipositas": ("eigen-rgc-z07-adipositas", "Zusatzbogen 07 – Adipositas und Stoffwechselerkrankungen (DE/LV)",
                   ADIPOSITAS),
}


def zusatz_vorlagen() -> list[dict]:
    return [{"schluessel": k, "name": name, "gruppe": "formulare", "mitgeliefert": f"rgc-z07-{fach}",
             "beschreibung": "Eingriffsspezifische Ergänzung zur Aufklärung Operation (Vorlage 07), zweisprachig",
             "bloecke": bloecke}
            for fach, (k, name, bloecke) in ZUSATZBOEGEN.items()]


def anlegen(apps, schema_editor=None):
    """Datenmigration: Fall-Dokumente und Zusatzbögen als eigene Schreiben der RGC (nur Fehlendes)."""
    from django.utils import timezone

    Firma = apps.get_model("stammdaten", "Firma")
    EigenesSchreiben = apps.get_model("vorlagen", "EigenesSchreiben")
    Dokumentvorlage = apps.get_model("vorlagen", "Dokumentvorlage")
    firma = Firma.objects.filter(kuerzel="rg").first()
    if firma is None:
        return
    jetzt = timezone.now()
    for v in fall_vorlagen() + zusatz_vorlagen():
        if EigenesSchreiben.objects.filter(mitgeliefert=v["mitgeliefert"]).exists() or \
                EigenesSchreiben.objects.filter(schluessel=v["schluessel"]).exists():
            continue
        name = v["name"]
        if EigenesSchreiben.objects.filter(name__iexact=name).exists():
            name = f"{name} (RGC)"[:100]
        e = EigenesSchreiben.objects.create(schluessel=v["schluessel"], name=name, beschreibung=v["beschreibung"],
                                            mit_termin=False, aktiv=True, firma=firma, gruppe=v["gruppe"],
                                            mitgeliefert=v["mitgeliefert"])
        Dokumentvorlage.objects.create(art=e.schluessel, version=1, status="aktiv", bloecke=v["bloecke"],
                                       notiz="Mitgeliefert mit der Dokumentenautomation (26.10.2026)",
                                       veroeffentlicht_am=jetzt)
