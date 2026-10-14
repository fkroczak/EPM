/**
 * Text mit Angaben aus der Akte als Chips (E-Mail-Vorlagen, 14.10.2026): Schreiben wie in Word, die Platzhalter
 * {{Patient.Briefanrede}} erscheinen als lesbarer Chip „Briefanrede“ und lassen sich wie ein Zeichen löschen oder
 * verschieben. Gespeichert wird weiter reiner Text mit {{…}} und Zeilenumbrüchen – die E-Mail geht als reiner Text.
 * Eigene Datei, damit TipTap erst geladen wird, wenn das Fenster aufgeht (wie EditorTiptap.tsx).
 */
import { useEffect, useRef } from "react";
import { EditorContent, Extension, Node, mergeAttributes, useEditor } from "@tiptap/react";
import type { Editor as TiptapEditor, JSONContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { cx } from "./ui/basis";

export type Beschriftung = { text: string; titel: string; unbekannt: boolean };
export type AngabenZiel = { einfuegen: (name: string) => void };
export type TextMitAngabenProps = {
  wert: string;
  onWert: (wert: string) => void;
  label: string;
  beschrifte: (name: string) => Beschriftung;
  einzeilig?: boolean;
  minHoehe?: number;
  autofokus?: boolean;
  /** meldet das Feld als Ziel für „Angabe einfügen“, sobald es den Fokus hat */
  onFokus?: (ziel: AngabenZiel) => void;
  className?: string;
};

const PLATZHALTER = /\{\{\s*([^{}]+?)\s*\}\}/g;

function zeileZuInhalt(zeile: string): JSONContent[] | undefined {
  const teile: JSONContent[] = [];
  let pos = 0;
  for (const m of zeile.matchAll(PLATZHALTER)) {
    if ((m.index ?? 0) > pos) teile.push({ type: "text", text: zeile.slice(pos, m.index) });
    teile.push({ type: "angabe", attrs: { name: m[1] } });
    pos = (m.index ?? 0) + m[0].length;
  }
  if (pos < zeile.length) teile.push({ type: "text", text: zeile.slice(pos) });
  return teile.length ? teile : undefined;
}

/** Text → Dokument: jede Zeile ein Absatz, Platzhalter als Chip */
export function zuDokument(text: string, einzeilig = false): JSONContent {
  const zeilen = einzeilig ? [text.replace(/\n/g, " ")] : text.split("\n");
  return { type: "doc", content: zeilen.map((z) => ({ type: "paragraph", content: zeileZuInhalt(z) })) };
}

/** Dokument → Text: Absätze mit Zeilenumbruch, Chips als {{Name}} */
export function zuText(editor: TiptapEditor): string {
  const zeilen: string[] = [];
  editor.state.doc.forEach((absatz) => {
    let s = "";
    absatz.forEach((n) => {
      if (n.type.name === "angabe") s += `{{${n.attrs.name}}}`;
      else if (n.isText) s += n.text ?? "";
    });
    zeilen.push(s);
  });
  return zeilen.join("\n");
}

function angabeKnoten(beschrifte: { current: (name: string) => Beschriftung }) {
  return Node.create({
    name: "angabe",
    group: "inline",
    inline: true,
    atom: true,
    selectable: true,
    addAttributes() {
      return { name: { default: "" } };
    },
    parseHTML() {
      return [{ tag: "span[data-angabe]", getAttrs: (el) => ({ name: (el as HTMLElement).getAttribute("data-angabe") }) }];
    },
    renderHTML({ node, HTMLAttributes }) {
      const b = beschrifte.current(node.attrs.name);
      return ["span", mergeAttributes(HTMLAttributes, {
        "data-angabe": node.attrs.name, title: b.titel, contenteditable: "false",
        class: b.unbekannt ? "feldchip feldchip-unbekannt" : "feldchip",
      }), b.text];
    },
    renderText({ node }) {
      return `{{${node.attrs.name}}}`;
    },
  });
}

/** einzeilig (Betreff): Enter beendet nicht den Absatz */
const OhneUmbruch = Extension.create({
  name: "ohneUmbruch",
  addKeyboardShortcuts() {
    return { Enter: () => true, "Shift-Enter": () => true };
  },
});

export default function TextMitAngaben({ wert, onWert, label, beschrifte, einzeilig, minHoehe = 0, autofokus, onFokus, className }: TextMitAngabenProps) {
  const beschriftung = useRef(beschrifte);
  beschriftung.current = beschrifte;
  const zuletzt = useRef(wert);
  const melden = useRef(onWert);
  melden.current = onWert;
  const editor = useEditor({
    immediatelyRender: true,
    extensions: [
      StarterKit.configure({
        bold: false, italic: false, underline: false, strike: false, code: false, codeBlock: false, heading: false,
        blockquote: false, bulletList: false, orderedList: false, listItem: false, listKeymap: false,
        horizontalRule: false, link: false, hardBreak: false,
      }),
      angabeKnoten(beschriftung),
      ...(einzeilig ? [OhneUmbruch] : []),
    ],
    content: zuDokument(wert, einzeilig),
    autofocus: autofokus ? "end" : false,
    editorProps: {
      attributes: {
        role: "textbox", "aria-label": label, "aria-multiline": einzeilig ? "false" : "true",
        class: cx("outline-none whitespace-pre-wrap [&_p]:m-0 [&_p]:min-h-[1.5em]", einzeilig ? "leading-normal" : "leading-relaxed"),
      },
    },
    onUpdate: ({ editor: e }) => {
      const text = zuText(e);
      // von Hand getippte oder eingefügte {{…}} werden zum Chip
      let roh = false;
      e.state.doc.descendants((n) => { if (n.isText && /\{\{[^{}]+\}\}/.test(n.text ?? "")) roh = true; });
      if (roh) {
        e.commands.setContent(zuDokument(text, einzeilig), { emitUpdate: false });
        e.commands.focus("end");
      }
      zuletzt.current = text;
      melden.current(text);
    },
  });
  // von außen geändert (z. B. Startvorlage geladen): Inhalt übernehmen
  useEffect(() => {
    if (wert !== zuletzt.current) {
      zuletzt.current = wert;
      editor.commands.setContent(zuDokument(wert, einzeilig), { emitUpdate: false });
    }
  }, [wert, editor, einzeilig]);
  const ziel = useRef<AngabenZiel>({ einfuegen: () => undefined });
  ziel.current.einfuegen = (name: string) => { editor.chain().focus().insertContent({ type: "angabe", attrs: { name } }).insertContent(" ").run(); };
  useEffect(() => {
    if (autofokus) onFokus?.(ziel.current);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className={cx("cursor-text", className)} style={{ minHeight: minHoehe }} onFocus={() => onFokus?.(ziel.current)}
      onClick={() => { if (!editor.isFocused) editor.commands.focus("end"); }}>
      <EditorContent editor={editor} />
    </div>
  );
}
