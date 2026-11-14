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
  build: {
    outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        // Bibliotheken (React, Router, Abfragen, Base UI) als eigene Datei (Performance-Prüfung 14.11.2026): Sie ändert
        // sich nur mit einem Bibliotheks-Update. Nach einem EPM-Update lädt der Browser dann nur den geänderten
        // eigenen Code neu (rund 70 KB statt 230 KB komprimiert), den Rest hat er noch im Zwischenspeicher.
        manualChunks(id) {
          if (/node_modules\/(react|react-dom|scheduler|react-router|@tanstack|@base-ui|@floating-ui|use-sync-external-store)\//.test(id)) {
            return "bibliotheken";
          }
        },
      },
    },
  },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
