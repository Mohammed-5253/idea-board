/**
 * IdeaForm – textarea + submit button.
 *
 * VALIDATION: mirrors the backend rules (trim, 1..500 chars) for instant feedback, BUT the
 *   backend remains the authority: its 422 message is shown if anything slips through
 *   (never trust the client – anyone can call the API with curl).
 * ACCESSIBILITY: label bound to the textarea, live character counter, errors announced via
 *   role="alert", the button is disabled while submitting (prevents double POSTs).
 */
import { type FormEvent, useId, useState } from "react";

import styles from "../App.module.css";
import { createIdea } from "../api/client";
import { CONTENT_MAX_LENGTH, type Idea } from "../api/types";

interface IdeaFormProps {
  onCreated: (idea: Idea) => void;
}

export function IdeaForm({ onCreated }: IdeaFormProps) {
  const inputId = useId();
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = content.trim();
  const tooLong = trimmed.length > CONTENT_MAX_LENGTH;
  const canSubmit = trimmed.length > 0 && !tooLong && !submitting;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const idea = await createIdea({ content: trimmed });
      onCreated(idea);
      setContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your idea.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={(e) => void handleSubmit(e)} noValidate>
      <label htmlFor={inputId}>Your idea</label>
      <textarea
        id={inputId}
        name="content"
        rows={3}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="My new idea"
        aria-invalid={tooLong}
        aria-describedby={`${inputId}-count`}
      />
      <div className={styles.formFooter}>
        <span id={`${inputId}-count`} className={tooLong ? styles.errorText : styles.muted}>
          {trimmed.length}/{CONTENT_MAX_LENGTH}
        </span>
        <button type="submit" disabled={!canSubmit}>
          {submitting ? "Saving…" : "Add idea"}
        </button>
      </div>
      {error && (
        <p role="alert" className={styles.errorText}>
          {error}
        </p>
      )}
    </form>
  );
}
