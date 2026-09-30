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
