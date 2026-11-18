/**
 * IdeaEditor – "Edit" button + inline editor for one idea (optimistic concurrency).
 *
 * Edit loads the idea with its ETag (GET /api/ideas/{id}); Save sends PATCH with If-Match.
 * IF someone else saved in between (412) THEN we keep the editor open, say so, and load the
 * current content + ETag again, so the next Save is based on what is really stored.
 */
import { useState } from "react";

import styles from "../App.module.css";
import { ApiError, editIdea, getIdea } from "../api/client";
import type { Idea } from "../api/types";
import { CONTENT_MAX_LENGTH } from "../api/types";

export const CONFLICT_MESSAGE = "This idea was changed by someone else.";

type EditorState =
  | { status: "closed" }
  | { status: "open"; draft: string; etag: string; message?: string | undefined; busy?: boolean };

export function IdeaEditor({ id, onEdited }: { id: number; onEdited: (idea: Idea) => void }) {
  const [state, setState] = useState<EditorState>({ status: "closed" });
  const [error, setError] = useState<string | null>(null);

  const open = async (message?: string) => {
    try {
      const { idea, etag } = await getIdea(id);
      setState({ status: "open", draft: idea.content, etag, message });
      setError(null);
      if (message) onEdited(idea); // the list shows what is really stored now
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  if (state.status === "closed") {
    return (
      <>
        <button type="button" onClick={() => void open()}>
          Edit
        </button>
        {error && (
          <p role="alert" className={styles.errorText}>
            {error}
          </p>
        )}
      </>
    );
  }

  const trimmed = state.draft.trim();
  const save = async () => {
    setState({ ...state, busy: true });
    try {
      const { idea } = await editIdea(id, trimmed, state.etag);
      onEdited(idea);
      setState({ status: "closed" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 412) {
        await open(CONFLICT_MESSAGE);
      } else {
        setState({
          ...state,
          busy: false,
          message: err instanceof Error ? err.message : "Unknown error",
        });
      }
    }
  };

  return (
    <div className={styles.form}>
      <label>
        Edit idea
        <textarea
          value={state.draft}
          maxLength={CONTENT_MAX_LENGTH}
          onChange={(e) => setState({ ...state, draft: e.target.value })}
        />
      </label>
      {state.message && (
        <p role="alert" className={styles.errorText}>
          {state.message}
        </p>
      )}
      <button
        type="button"
        disabled={state.busy || trimmed.length === 0}
        onClick={() => void save()}
      >
        Save
      </button>
    </div>
  );
}
