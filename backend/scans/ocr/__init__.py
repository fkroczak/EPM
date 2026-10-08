"""Texterkennung (OCR) für den Menüpunkt „Scans“ (Festlegung 08.10.2026, F160 ff.).

Alles läuft lokal im Container ``ocr`` – ohne Netz, ohne externe Dienste, ohne Sprachmodell:

- ``laden``       Datei → Seiten als Bild (PDF über pdfium, Fotos mit EXIF-Drehung, TIFF mit mehreren Seiten);
                  PDF-Seiten mit Textebene liefern ihren Text direkt (keine Erkennung nötig).
- ``aufbereitung``Blatt im Foto finden und gerade ziehen, gewellte Seiten glätten (UVDoc), Ausrichtung,
                  Schräglage, Schatten und Rauschen entfernen, auf Lesegröße bringen.
- ``tesseract``   Erkennung 1: Tesseract 5 mit dem genauesten deutschen Modell (tessdata_best).
- ``paddle``      Erkennung 2: PaddleOCR PP-OCRv5 (Erkennung der Zeilen + lateinische Schrift) über onnxruntime.
- ``fusion``      Je Zeile das Ergebnis mit der höheren Sicherheit; Wörter mit Sicherheit und Lage für die Anzeige.
- ``pdf``         Durchsuchbare PDF: Seitenbild mit unsichtbarer Textebene.
- ``auswertung``  Labor-, BIA-Werte, ICD-Codes, Abschnitte, Datum, Patientenvorschlag.

Die Ergebnisse sind Vorschläge: Jeder übernommene Wert wird von einem Menschen bestätigt.
"""
