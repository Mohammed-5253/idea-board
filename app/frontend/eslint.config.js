/**
 * FILE: app/frontend/eslint.config.js  (ESLint "flat config")
 * WHAT: Lint rules: ESLint recommended + typescript-eslint (type-aware) + React Hooks rules.
 * WHY:  The React Hooks rules catch the most common React bugs (missing effect deps,
 *       conditional hooks). Type-aware rules catch unhandled promises (floating promises).
 * Formatting is Prettier's job; ESLint does not fight it (no stylistic rules here).
 */
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "node_modules", "public/config.js"] },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  reactHooks.configs.flat.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: ["eslint.config.js", "prettier.config.js"],
    extends: [tseslint.configs.disableTypeChecked],
    languageOptions: { globals: { ...globals.node } },
  },
);
