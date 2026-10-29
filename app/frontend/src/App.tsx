/**
 * FILE: app/frontend/src/App.tsx
 * WHAT: The whole page: a form to submit ideas + the list of ideas.
 * SPEC: "A React application that displays a list of ideas and has a form to submit new ones."
 *
 * STATE MACHINE for the list (capability requirement: loading, error, empty states):
 *   loading → (success) ready [empty | non-empty]
 *          → (failure) error  → "Retry" → loading
 * After a successful POST we PREPEND the returned idea locally (newest first, matching the
 * backend order) instead of refetching – instant feedback, one request fewer.
 * IF two tabs add ideas concurrently THEN each tab shows its own additions until refresh
 * (acceptable for a basic app; a production app might poll or use server-sent events).
 * LEARN: docs/learning/11-frontend-react-vite-typescript.md §3 (hooks, effects)
 */
import { useEffect, useState } from "react";

import styles from "./App.module.css";
import { listIdeas } from "./api/client";
import type { Idea } from "./api/types";
import { IdeaForm } from "./components/IdeaForm";
import { IdeaList } from "./components/IdeaList";

type ListState =
  { status: "loading" } | { status: "error"; message: string } | { status: "ready"; ideas: Idea[] };

export default function App() {
  // Initial state is "loading", so the first render already shows the loading message.
  const [state, setState] = useState<ListState>({ status: "loading" });
  // Bumping this key re-runs the effect below (used by the Retry button).
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    // Canonical React data-fetching pattern: the effect SUBSCRIBES to a promise and only
    // calls setState inside its callbacks (never synchronously in the effect body, which
    // would trigger an extra cascading render – lint rule `react-hooks/set-state-in-effect`).
    // The `cancelled` flag: IF the component unmounts (or StrictMode re-runs the effect)
    // before the request finishes THEN the stale response is ignored.
    let cancelled = false;
    listIdeas().then(
      (ideas) => {
        if (!cancelled) setState({ status: "ready", ideas });
      },
      (err: unknown) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof Error ? err.message : "Unknown error",
          });
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  // Retry is an EVENT HANDLER (not an effect), so setting state synchronously is fine here.
  const retry = () => {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  };

  const handleCreated = (idea: Idea) => {
    setState((prev) =>
      prev.status === "ready" ? { status: "ready", ideas: [idea, ...prev.ideas] } : prev,
    );
  };

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <h1>Idea Board</h1>
        <p className={styles.subtitle}>Share an idea. See everyone&apos;s ideas.</p>
      </header>

      <IdeaForm onCreated={handleCreated} />

      <section aria-labelledby="ideas-heading" className={styles.listSection}>
        <h2 id="ideas-heading">Ideas</h2>
        {state.status === "loading" && (
          <p role="status" className={styles.muted}>
            Loading ideas…
          </p>
        )}
        {state.status === "error" && (
          <div role="alert" className={styles.error}>
            <p>Could not load ideas: {state.message}</p>
            <button type="button" onClick={retry}>
              Retry
            </button>
          </div>
        )}
        {state.status === "ready" &&
          (state.ideas.length === 0 ? (
            <p className={styles.muted}>No ideas yet – be the first!</p>
          ) : (
            <IdeaList ideas={state.ideas} />
          ))}
      </section>
    </main>
  );
}
