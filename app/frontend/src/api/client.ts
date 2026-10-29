/**
 * Minimal API client built on the browser's native `fetch` (no HTTP library dependency).
 *
 * WHAT: listIdeas() and createIdea() – the two spec endpoints – plus a typed ApiError.
 * WHY fetch?  It's built into every browser and into Node 24 (tests); adding axios would be
 *       an unapproved dependency for two calls.
 * TIMEOUTS: every request is aborted after 10 s (AbortController). IF the backend hangs
 *       THEN the UI shows an error instead of spinning forever.
 * ERRORS: non-2xx responses are parsed into the backend's {error:{...}} shape when possible,
 *       so the UI can show the server's validation message (e.g. "too long").
 * LEARN: docs/learning/11-frontend-react-vite-typescript.md §3, §6
 */
import { apiBaseUrl } from "../config";
import type { ApiErrorBody, Idea, NewIdea } from "./types";

const REQUEST_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof (value as ApiErrorBody).error?.message === "string"
  );
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      headers: { Accept: "application/json", ...init?.headers },
      signal: controller.signal,
    });
  } catch {
    // Network failure, DNS, CORS, or our timeout → one friendly error type.
    // (The raw cause is visible in the browser devtools Network tab.)
    throw new ApiError(0, "network_error", "Cannot reach the server. Please try again.");
  } finally {
    clearTimeout(timer);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    if (isApiErrorBody(body)) {
      const detail = body.error.details[0]?.message;
      throw new ApiError(response.status, body.error.code, detail ?? body.error.message);
    }
    throw new ApiError(response.status, "http_error", `Request failed (${response.status}).`);
  }
  return body as T;
}

export function listIdeas(): Promise<Idea[]> {
  return request<Idea[]>("/api/ideas");
}

export function createIdea(idea: NewIdea): Promise<Idea> {
  return request<Idea>("/api/ideas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(idea),
  });
}
