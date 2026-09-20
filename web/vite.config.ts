import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Built straight into the Python package, which serves it as static files.
  build: { outDir: "../src/physiosync/web", emptyOutDir: true },
  server: {
    proxy: {
      "/api": backend,
      "/ws": { target: backend, ws: true },
    },
  },
});
