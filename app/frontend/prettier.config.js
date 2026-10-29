/**
 * Prettier formatting rules (JS config so it can carry comments, ADR-003).
 * Kept close to defaults on purpose: less to argue about in reviews.
 */
/** @type {import("prettier").Config} */
export default {
  printWidth: 100,
  trailingComma: "all",
};
