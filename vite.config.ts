import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/map/",
  build: {
    outDir: "src/web/static/map",
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: {
        map: path.resolve(__dirname, "src/map-entry.tsx"),
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:5050",
        changeOrigin: true,
      },
    },
  },
});
