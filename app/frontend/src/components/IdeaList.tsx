/**
 * IdeaList – renders ideas newest-first (the order the backend returns).
 *
 * SECURITY NOTE: idea text is rendered as a React text node, which ESCAPES HTML. A stored
 *   "<script>…" idea is displayed literally, never executed (XSS protection). Never use
 *   dangerouslySetInnerHTML for user content.
 * `key={idea.id}` – stable keys let React update the list efficiently when we prepend.
 */
import styles from "../App.module.css";
import type { Idea } from "../api/types";

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

export function IdeaList({ ideas }: { ideas: Idea[] }) {
  return (
    <ul className={styles.list}>
      {ideas.map((idea) => (
        <li key={idea.id} className={styles.item}>
          <p className={styles.content}>{idea.content}</p>
          <time dateTime={idea.created_at} className={styles.muted}>
            {dateFormatter.format(new Date(idea.created_at))}
          </time>
        </li>
      ))}
    </ul>
  );
}
