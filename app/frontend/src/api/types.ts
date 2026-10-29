/**
 * API contract types – mirror the backend's Pydantic models (app/backend/.../schemas.py).
 *
 * SPEC: GET /api/ideas returns a JSON array of ideas; each idea has the table's columns
 *       (id, content, created_at). POST accepts {"content": "..."}.
 * NOTE: `created_at` is an ISO 8601 STRING on the wire (JSON has no date type); we format
 *       it for display but keep the raw string in state (no silent timezone conversion bugs).
 */
export interface Idea {
  id: number;
  content: string;
  created_at: string;
}

export interface NewIdea {
  content: string;
}

/** The backend's single error shape (see backend api/errors.py). */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: { field: string; message: string }[];
  };
}

/** Must match the backend limit (CONTENT_MAX_LENGTH = 500). */
export const CONTENT_MAX_LENGTH = 500;
