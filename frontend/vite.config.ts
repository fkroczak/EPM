import { cpSync, existsSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

/**
 * pdf.js-Zusatzdateien (Decoder für gescannte PDFs als JavaScript, Standardschriften, CMaps, ICC-Profile) nach
 * dist/pdfjs/ kopieren. Sie werden zur Laufzeit von /pdfjs/ geladen – offline, ohne externe Quellen.
 */
function pdfjsDateien() {
  return {
    name: "epm-pdfjs-dateien",
    apply: "build" as const,
    closeBundle() {
      const quelle = fileURLToPath(new URL("./node_modules/pdfjs-dist/", import.meta.url));
      const ziel = fileURLToPath(new URL("./dist/pdfjs/", import.meta.url));
      for (const ordner of ["wasm", "standard_fonts", "cmaps", "iccs"]) {
        if (existsSync(quelle + ordner)) cpSync(quelle + ordner, ziel + ordner, { recursive: true });
      }
    },
  };
}

// Entwicklung: `npm run dev` mit Django auf 127.0.0.1:8000. Im Betrieb liefert Nginx die Dateien aus dist/.
export default defineConfig({
  plugins: [react(), tailwindcss(), pdfjsDateien()],
  // Worker als ES-Modul (pdf.js startet ihn mit type: "module"); Ausgabe als .js, das Nginx korrekt ausliefert
  worker: { format: "es" },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 1500 },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
