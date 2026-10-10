"""
Notfallplan (F188): der Wiederaufbau-Plan als Markdown (``notfallplan.md``, gleichlautend in ``docs/NOTFALLPLAN.md``),
als HTML für die Oberfläche (Administration › System › Notfall, Hilfe) und als PDF für das Notfallpaket.

Bewusst ohne Markdown-Bibliothek: nur der kleine Teil, den der Plan benutzt (Überschriften, Absätze, Listen auch
eingerückt, Aufgaben-Kästchen, Codeblöcke, Tabellen, Trennlinien, **fett**, *kursiv*, `Code`). Alles wird
HTML-escaped – der Plan enthält keine Daten aus der Datenbank.
"""
import html
import re
from pathlib import Path

QUELLE = Path(__file__).with_name("notfallplan.md")


def markdown() -> str:
    return QUELLE.read_text(encoding="utf-8")


def _inline(text: str) -> str:
    teile = re.split(r"(`[^`]+`)", text)
    aus = []
    for t in teile:
        if t.startswith("`") and t.endswith("`") and len(t) > 1:
            aus.append(f"<code>{html.escape(t[1:-1])}</code>")
            continue
        t = html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
        aus.append(t)
    return "".join(aus)


def zu_html(text: str | None = None) -> str:
    """Markdown des Plans → HTML-Fragment (ohne <html>)."""
    zeilen = (text if text is not None else markdown()).splitlines()
    aus: list[str] = []
    absatz: list[str] = []
    listen: list[tuple[int, str]] = []        # (Einrückung, "ul"|"ol")
    i = 0

    def absatz_schliessen():
        if absatz:
            aus.append(f"<p>{_inline(' '.join(absatz))}</p>")
            absatz.clear()

    def listen_schliessen(bis=-1):
        while listen and listen[-1][0] > bis:
            aus.append(f"</li></{listen.pop()[1]}>")

    while i < len(zeilen):
        z = zeilen[i]
        if z.startswith("```"):
            absatz_schliessen()
            code = []
            i += 1
            while i < len(zeilen) and not zeilen[i].startswith("```"):
                code.append(zeilen[i])
                i += 1
            aus.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
            i += 1
            continue
        if not z.strip():
            absatz_schliessen()
            i += 1
            continue
        m = re.match(r"^(#{1,3}) (.+)$", z)
        if m:
            absatz_schliessen()
            listen_schliessen()
            n = len(m.group(1))
            aus.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            i += 1
            continue
        if re.match(r"^-{3,}$", z.strip()):
            absatz_schliessen()
            listen_schliessen()
            aus.append("<hr>")
            i += 1
            continue
        if z.startswith("|"):
            absatz_schliessen()
            listen_schliessen()
            reihen = []
            while i < len(zeilen) and zeilen[i].startswith("|"):
                reihen.append([c.strip() for c in zeilen[i].strip().strip("|").split("|")])
                i += 1
            kopf, rest = reihen[0], [r for r in reihen[1:] if not all(re.match(r"^:?-+:?$", c) for c in r)]
            aus.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in kopf) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rest)
                       + "</tbody></table>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.) (.+)$", z)
        if m:
            absatz_schliessen()
            tiefe, art = len(m.group(1)), "ol" if m.group(2)[0].isdigit() else "ul"
            inhalt = m.group(3)
            kaestchen = re.match(r"^\[( |x)\] (.+)$", inhalt)
            if kaestchen:
                inhalt = ("☑ " if kaestchen.group(1) == "x" else "☐ ") + kaestchen.group(2)
            if listen and listen[-1][0] == tiefe:
                aus.append("</li>")
            elif not listen or listen[-1][0] < tiefe:
                aus.append(f"<{art}>")
                listen.append((tiefe, art))
            else:
                listen_schliessen(tiefe)
                if listen and listen[-1][0] == tiefe:
                    aus.append("</li>")
                else:
                    aus.append(f"<{art}>")
                    listen.append((tiefe, art))
            # Fortsetzungszeilen (eingerückt, kein neuer Punkt) gehören zum Punkt
            text = [inhalt]
            while i + 1 < len(zeilen) and zeilen[i + 1].startswith(" ") and zeilen[i + 1].strip() \
                    and not re.match(r"^\s*([-*]|\d+\.) ", zeilen[i + 1]) and not zeilen[i + 1].strip().startswith("```"):
                i += 1
                text.append(zeilen[i].strip())
            aus.append(f"<li>{_inline(' '.join(text))}")
            i += 1
            continue
        if listen and z.startswith(" "):
            # eingerückter Codeblock o. Ä. innerhalb einer Liste: als Absatz anhängen
            aus.append(f" {_inline(z.strip())}")
            i += 1
            continue
        listen_schliessen()
        absatz.append(z.strip())
        i += 1
    absatz_schliessen()
    listen_schliessen()
    return "\n".join(aus)


CSS_ZUSATZ = """
h1 { font-size: 15pt; margin: 0 0 6pt; } h2 { font-size: 12pt; margin: 14pt 0 4pt; page-break-after: avoid; }
h3 { font-size: 10.5pt; margin: 10pt 0 3pt; } p, li { margin: 3pt 0; }
pre { background: #f2f3f5; padding: 5pt 7pt; border-radius: 3pt; white-space: pre-wrap; font-size: 8.5pt;
      page-break-inside: avoid; } code { font-family: "IBM Plex Mono", "DejaVu Sans Mono", monospace; font-size: 8.5pt; }
table { border-collapse: collapse; width: 100%; font-size: 8.5pt; } th, td { border: 0.5pt solid #aab; padding: 3pt 4pt;
      text-align: left; vertical-align: top; } hr { border: 0; border-top: 0.5pt solid #aab; margin: 10pt 0; }
"""


def zu_pdf() -> bytes:
    """Der Plan als PDF (WeasyPrint, Schrift aus dem Image; keine externen Ressourcen)."""
    from vorlagen.pdf import html_zu_pdf, seite

    dokument = seite("EPM – Notfallplan", f"<style>{CSS_ZUSATZ}</style>{zu_html()}",
                     fusszeile="EPM – Notfallplan · im Notfallpaket als NOTFALLPLAN.md und NOTFALLPLAN.pdf")
    return html_zu_pdf(dokument)
