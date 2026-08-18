import { defineConfig, configDefaults } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // Overridable so the Playwright E2E suite can point the dev server
        // at its own isolated backend instance instead of the real one.
        target: process.env.E2E_BACKEND_URL ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    // e2e/ holds Playwright specs, run separately via `npm run test:e2e` -
    // vitest's default glob would otherwise also pick them up.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
