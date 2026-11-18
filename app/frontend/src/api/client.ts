/**
 * Minimal API client built on the browser's native `fetch` (no HTTP library dependency).
 *
 * WHAT: listIdeas() and createIdea() – the two spec endpoints – getIdea()/editIdea() for
 *       optimistic-concurrency edits (ETag / If-Match), plus a typed ApiError.
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
  return (await requestWithHeaders<T>(path, init)).body;
}

async function requestWithHeaders<T>(
  path: string,
  init?: RequestInit,
): Promise<{ body: T; headers: Headers }> {
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
  return { body: body as T, headers: response.headers };
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

/** An idea plus its ETag (current version), needed to edit it. */
export interface VersionedIdea {
  idea: Idea;
  etag: string;
}

export async function getIdea(id: number): Promise<VersionedIdea> {
  const { body, headers } = await requestWithHeaders<Idea>(`/api/ideas/${id}`);
  return { idea: body, etag: headers.get("ETag") ?? "" };
}

/** PATCH with If-Match: rejects with ApiError status 412 when someone else edited it first. */
export async function editIdea(id: number, content: string, etag: string): Promise<VersionedIdea> {
  const { body, headers } = await requestWithHeaders<Idea>(`/api/ideas/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "If-Match": etag },
    body: JSON.stringify({ content }),
  });
  return { idea: body, etag: headers.get("ETag") ?? "" };
}
