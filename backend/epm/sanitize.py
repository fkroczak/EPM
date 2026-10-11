"""Bereinigung von Rich-Text (Diagnose, Therapie, Kontakte …) auf erlaubte Tags."""
import nh3

ERLAUBTE_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s", "mark",
    "ul", "ol", "li", "h3", "h4", "blockquote", "hr",
    "table", "thead", "tbody", "tr", "th", "td",
}
ERLAUBTE_ATTRIBUTE = {"td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}}


def bereinige_html(text: str) -> str:
    """Entfernt Skripte, Styles, Links, Bilder und alle unbekannten Tags/Attribute."""
    if not text:
        return ""
    return nh3.clean(
        text,
        tags=ERLAUBTE_TAGS,
        attributes=ERLAUBTE_ATTRIBUTE,
        url_schemes=set(),
        strip_comments=True,
    ).strip()


def pillow_ohne_ghostscript():
    """Pillow öffnet EPS/PostScript über Ghostscript (im Image für OCRmyPDF installiert). EPM braucht solche Dateien
    nie als Bild – abschalten, damit fremdes PostScript den Interpreter nicht erreicht: weder über ein Bild im PDF
    (WeasyPrint < 70 reicht jedes Bild an Pillow weiter, CVE-2026-106443) noch über einen Upload unter „Scans“.
    Sicherheitsprüfung 11.10.2026; läuft einmal beim Start (``VorlagenConfig.ready``)."""
    from PIL import Image

    Image.init()  # alle Formate registrieren, danach wird nichts mehr nachgeladen
    for kennung in ("EPS",):
        Image.OPEN.pop(kennung, None)
        if kennung in Image.ID:
            Image.ID.remove(kennung)
