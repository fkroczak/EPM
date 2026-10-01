import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

// Entwicklung: `npm run dev` mit Django auf 127.0.0.1:8000. Im Betrieb liefert Nginx die Dateien aus dist/.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 1500 },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
