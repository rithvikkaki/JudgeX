import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // CodeMirror and its language modes are the bulk of the bundle and are
    // only needed on the problem page, so they are split out of the entry
    // chunk. The landing page then loads in a fraction of the payload.
    rollupOptions: {
      output: {
        // Function form: the object form is not accepted by Vite's typings
        // when `output` may also be an array.
        manualChunks(id: string) {
          if (id.includes("codemirror") || id.includes("@lezer")) return "editor";
          if (id.includes("react-router")) return "router";
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
  },
});
