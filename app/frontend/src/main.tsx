/**
 * FILE: app/frontend/src/main.tsx
 * WHAT: Browser entry point – mounts the React tree into <div id="root"> (index.html).
 * WHY StrictMode?  In development React intentionally double-invokes effects to surface
 *       side-effect bugs early (e.g. a fetch without cleanup). It has no production cost.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./global.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element in index.html");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
