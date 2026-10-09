/**
 * Formatierter Text mit TipTap (ProseMirror). Erlaubt nur, was das Backend beim Speichern stehen lässt
 * (epm/sanitize.py): Absätze, fett, kursiv, unterstrichen, Überschrift, Listen – keine Links, kein Code.
 * Eigene Datei, damit TipTap erst geladen wird, wenn ein Editor erscheint (Editor.tsx).
 */
import { useEffect } from "react";
import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import type { Editor as TiptapEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { rem } from "@/lib/masse";
import { cx } from "./ui/basis";
import type { EditorProps } from "./Editor";

const ERWEITERUNGEN = [
  StarterKit.configure({
    heading: { levels: [3] },
    code: false,
    codeBlock: false,
    link: false,
    strike: false,
    horizontalRule: false,
  }),
];

/** HTML ohne leere Absätze am Ende (ProseMirror hängt nach Listen einen an) */
function html(e: TiptapEditor): string {
  return e.isEmpty ? "" : e.getHTML().replace(/(<p><\/p>)+$/, "");
}

function Werkzeugleiste({ editor }: { editor: TiptapEditor }) {
  const z = useEditorState({
    editor,
    selector: ({ editor: e }: { editor: TiptapEditor }) => ({
      fett: e.isActive("bold"),
      kursiv: e.isActive("italic"),
      unter: e.isActive("underline"),
      ueber: e.isActive("heading", { level: 3 }),
      liste: e.isActive("bulletList"),
      nummern: e.isActive("orderedList"),
    }),
  });
  const knopf = (label: string, text: string, aktiv: boolean, aktion: () => void, klasse?: string) => (
    <button type="button" aria-label={label} aria-pressed={aktiv} title={label}
      className={cx("h-8 min-w-8 px-2 rounded-md border text-sm cursor-pointer", aktiv ? "bg-akzent-weich border-rand text-akzent-text" : "bg-transparent border-transparent hover:bg-fein", klasse)}
      onMouseDown={(e) => e.preventDefault()} onClick={aktion}>
      {text}
    </button>
  );
  return (
    <div role="toolbar" aria-label="Formatierung" className="flex items-center gap-0.5 flex-wrap">
      {knopf("Fett", "B", z.fett, () => editor.chain().focus().toggleBold().run(), "font-bold")}
      {knopf("Kursiv", "I", z.kursiv, () => editor.chain().focus().toggleItalic().run(), "italic font-serif")}
      {knopf("Unterstrichen", "U", z.unter, () => editor.chain().focus().toggleUnderline().run(), "underline")}
      <span className="w-px h-5 bg-rand mx-1.5" aria-hidden="true" />
      {knopf("Überschrift", "Überschrift", z.ueber, () => editor.chain().focus().toggleHeading({ level: 3 }).run())}
      {knopf("Aufzählung", "• Liste", z.liste, () => editor.chain().focus().toggleBulletList().run())}
      {knopf("Nummerierte Liste", "1. Liste", z.nummern, () => editor.chain().focus().toggleOrderedList().run())}
    </div>
  );
}

export default function TiptapFeld({ wert, onAenderung, label, werkzeuge = true, platzhalter, hoehe = 120, autofokus, className, deaktiviert }: EditorProps) {
  const editor = useEditor({
    extensions: ERWEITERUNGEN,
    content: wert,
    editable: !deaktiviert,
    autofocus: autofokus ? "end" : false,
    immediatelyRender: true,
    shouldRerenderOnTransaction: true,
    editorProps: {
      attributes: {
        class: "richtext outline-none",
        role: "textbox",
        "aria-multiline": "true",
        "aria-label": label,
        style: `min-height:${rem(hoehe)}`,
      },
    },
    onUpdate: ({ editor: e }: { editor: TiptapEditor }) => onAenderung(html(e)),
  });

  // Wert von außen (Verwerfen, Neuladen) übernehmen, ohne die eigene Eingabe zu überschreiben
  useEffect(() => {
    if (!editor) return;
    const aktuell = html(editor);
    if (wert !== aktuell) editor.commands.setContent(wert || "", { emitUpdate: false });
  }, [wert, editor]);

  useEffect(() => {
    editor?.setEditable(!deaktiviert);
  }, [deaktiviert, editor]);

  if (!editor) return null;
  return (
    <div className={cx("flex flex-col gap-2", className)}>
      {werkzeuge ? <Werkzeugleiste editor={editor} /> : null}
      <div className="inp h-auto py-2 relative cursor-text" onClick={() => editor.chain().focus().run()}>
        {platzhalter && editor.isEmpty ? (
          <span className="absolute left-3 top-2 gedaempft pointer-events-none" aria-hidden="true">{platzhalter}</span>
        ) : null}
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
