/**
 * FILE: app/frontend/vite.config.ts
 * WHAT: Build tool configuration (Vite) + unit test configuration (Vitest).
 * WHY:  Vite serves the app in development with instant hot reload and builds a static,
 *       minified bundle (dist/) for production. Vitest reuses this exact config, so tests
 *       transform code the same way the app build does.
 *
 * DEV PROXY: in development the browser talks to Vite (localhost:5173). Requests to /api
 *       are proxied to the backend (localhost:8000 by default). This mirrors production,
 *       where Envoy Gateway routes /api to the backend on the SAME origin – so the app
 *       never needs CORS and never hard-codes a backend URL (D-03, ADR-011).
 *       IF your backend runs elsewhere THEN set VITE_DEV_API_TARGET=http://host:port.
 *       BUT note: this variable only affects the DEV SERVER, never the built bundle.
 * LEARN: docs/learning/11-frontend-react-vite-typescript.md §3, §5
 */
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  // loadEnv reads VITE_DEV_* from .env files AND the shell environment. Using it (instead
  // of `process.env`) avoids needing Node type definitions (@types/node is not approved).
  const env = loadEnv(mode, ".", "VITE_DEV_");
  const apiTarget = env.VITE_DEV_API_TARGET ?? "http://localhost:8000";
  // Vite's dev server rejects unknown Host headers (DNS-rebinding protection) with 403.
  // In docker-compose the E2E browser reaches it as "frontend:8080", so the dev override
  // sets VITE_DEV_ALLOWED_HOSTS=frontend. DEV SERVER ONLY – the production nginx image
  // is unaffected. SECURITY NOTE: never set this to `true` (allows any host).
  const allowedHosts = (env.VITE_DEV_ALLOWED_HOSTS ?? "")
    .split(",")
    .map((h) => h.trim())
    .filter(Boolean);

  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true, // fail loudly instead of silently picking another port
      allowedHosts,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true, // debuggable production bundle; maps are served only if deployed
    },
    test: {
      environment: "jsdom", // simulated browser DOM (approved, Phase 3)
      globals: true, // describe/it/expect without imports, like Jest
      setupFiles: ["./src/test/setup.ts"],
      css: { modules: { classNameStrategy: "non-scoped" } }, // readable class names in tests
      restoreMocks: true, // every test starts with fresh fetch mocks
    },
  };
});
