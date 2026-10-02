"""Übernahme der Altdaten (F65): Dump des Altsystems lesen, Zuordnungen pflegen, Probelauf, Import, Zurücknehmen.

Aufbau:
- ``dump``       MySQL-Dump lesen (reines Python, ohne Django)
- ``werte``      einzelne Werte lesen und bereinigen (Text, Zahl, Datum, HTML)
- ``felder``     Katalog: welche Angaben das Werkzeug aus welcher Tabelle erwartet
- ``umsetzung``  aus Tabellen + Zuordnungen + Bestand die neuen Datensätze, offenen Punkte und das Protokoll bilden
- ``dienst``     Datenbank und Dateien: schreiben, zurücknehmen, abschließen (Django)
- ``api``        Administration › Import
"""
