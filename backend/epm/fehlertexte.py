"""Fehlertexte der API an einer Stelle (13.10.2026).

Django REST Framework meldet Eingabefehler sonst in seiner eigenen Übersetzung („Dieses Feld ist zwingend
erforderlich.“, „Gib eine gültige E-Mail Adresse an.“, „Stelle sicher, dass dieses Feld nicht mehr als 100 Zeichen lang
ist.“). Die Oberfläche zeigt diese Texte direkt am Feld – deshalb kurz, freundlich und im Ton der übrigen Meldungen.
``anwenden()`` läuft einmal beim Start (``epm.apps.EpmConfig.ready``); eigene ``error_messages`` einzelner Felder
bleiben unberührt."""
from rest_framework import serializers, validators
from rest_framework.utils import field_mapping

PFLICHT = "Bitte ausfüllen."

TEXTE: dict[type, dict[str, str]] = {
    serializers.Field: {"required": PFLICHT, "null": PFLICHT},
    serializers.CharField: {"invalid": "Bitte einen Text angeben.", "blank": PFLICHT,
                            "max_length": "Höchstens {max_length} Zeichen.", "min_length": "Mindestens {min_length} Zeichen."},
    serializers.EmailField: {"invalid": "Bitte eine gültige E-Mail-Adresse angeben."},
    serializers.IntegerField: {"invalid": "Bitte eine ganze Zahl angeben.", "max_value": "Höchstens {max_value}.",
                               "min_value": "Mindestens {min_value}.", "max_string_length": "Die Zahl ist zu lang."},
    serializers.FloatField: {"invalid": "Bitte eine Zahl angeben.", "max_value": "Höchstens {max_value}.",
                             "min_value": "Mindestens {min_value}.", "max_string_length": "Die Zahl ist zu lang.",
                             "overflow": "Die Zahl ist zu groß."},
    serializers.DecimalField: {"invalid": "Bitte eine Zahl angeben.", "max_value": "Höchstens {max_value}.",
                               "min_value": "Mindestens {min_value}.", "max_string_length": "Die Zahl ist zu lang.",
                               "max_digits": "Höchstens {max_digits} Ziffern.",
                               "max_decimal_places": "Höchstens {max_decimal_places} Nachkommastellen.",
                               "max_whole_digits": "Höchstens {max_whole_digits} Stellen vor dem Komma."},
    serializers.BooleanField: {"invalid": "Bitte ja oder nein angeben."},
    serializers.DateField: {"invalid": "Bitte als TT.MM.JJJJ angeben.", "datetime": "Bitte nur ein Datum angeben, ohne Uhrzeit."},
    serializers.DateTimeField: {"invalid": "Bitte Datum und Uhrzeit angeben.", "date": "Bitte auch die Uhrzeit angeben.",
                                "make_aware": "Diese Uhrzeit gibt es in der Zeitzone „{timezone}“ nicht.",
                                "overflow": "Das Datum liegt außerhalb des möglichen Bereichs."},
    serializers.TimeField: {"invalid": "Bitte als HH:MM angeben."},
    serializers.DurationField: {"invalid": "Bitte eine Dauer angeben, z. B. 1:30:00.", "max_value": "Höchstens {max_value}.",
                                "min_value": "Mindestens {min_value}.",
                                "overflow": "Bitte zwischen {min_days} und {max_days} Tagen."},
    serializers.ChoiceField: {"invalid_choice": "„{input}“ steht nicht zur Auswahl."},
    serializers.MultipleChoiceField: {"invalid_choice": "„{input}“ steht nicht zur Auswahl.",
                                      "not_a_list": "Bitte eine Liste angeben.", "empty": "Bitte mindestens einen Eintrag wählen."},
    serializers.ListField: {"not_a_list": "Bitte eine Liste angeben.", "empty": "Bitte mindestens einen Eintrag angeben.",
                            "min_length": "Mindestens {min_length} Einträge.", "max_length": "Höchstens {max_length} Einträge."},
    serializers.DictField: {"not_a_dict": "Bitte Werte mit Schlüssel angeben.", "empty": "Bitte mindestens einen Eintrag angeben."},
    serializers.JSONField: {"invalid": "Kein gültiges JSON."},
    serializers.FileField: {"required": "Bitte eine Datei wählen.", "invalid": "Das ist keine Datei.",
                            "no_name": "Die Datei hat keinen Namen.", "empty": "Die Datei ist leer.",
                            "max_length": "Der Dateiname darf höchstens {max_length} Zeichen lang sein (er hat {length})."},
    serializers.ImageField: {"invalid_image": "Bitte ein Bild wählen – die Datei ist kein Bild oder beschädigt."},
    serializers.UUIDField: {"invalid": "Keine gültige Kennung."},
    serializers.Serializer: {"invalid": "Ungültige Daten: Es wurde kein Datensatz übermittelt."},
    serializers.ListSerializer: {"not_a_list": "Bitte eine Liste angeben.", "empty": "Bitte mindestens einen Eintrag angeben.",
                                 "min_length": "Mindestens {min_length} Einträge.", "max_length": "Höchstens {max_length} Einträge."},
    serializers.RelatedField: {"required": PFLICHT, "null": PFLICHT},
    serializers.PrimaryKeyRelatedField: {"required": PFLICHT, "does_not_exist": "Eintrag {pk_value} gibt es nicht (mehr).",
                                         "incorrect_type": "Ungültige Auswahl."},
    serializers.SlugRelatedField: {"does_not_exist": "„{value}“ gibt es nicht.", "invalid": "Ungültige Auswahl."},
    serializers.ManyRelatedField: {"not_a_list": "Bitte eine Liste angeben.", "empty": "Bitte mindestens einen Eintrag wählen."},
}

EINDEUTIG = "Gibt es schon – bitte einen anderen Wert wählen."
EINDEUTIG_ZUSAMMEN = "Diese Kombination ({field_names}) gibt es schon."


def _eindeutig_text(model_field):
    """Für ``unique=True`` am Modell: ein Satz statt „Ein(e) Patient mit diesem Nummer existiert bereits.“"""
    return EINDEUTIG


def anwenden():
    for klasse, texte in TEXTE.items():
        klasse.default_error_messages = {**getattr(klasse, "default_error_messages", {}), **texte}
    validators.UniqueValidator.message = EINDEUTIG
    validators.UniqueTogetherValidator.message = EINDEUTIG_ZUSAMMEN
    validators.UniqueTogetherValidator.missing_message = PFLICHT
    field_mapping.get_unique_error_message = _eindeutig_text
