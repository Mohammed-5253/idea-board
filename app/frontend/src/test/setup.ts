/**
 * Vitest global setup: adds DOM matchers like `toBeInTheDocument()` (jest-dom) and
 * cleans the rendered DOM after every test.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  window.__APP_CONFIG__ = { apiBaseUrl: "" };
});
