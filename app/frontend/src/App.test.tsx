/**
 * Component tests for the whole page (Vitest + React Testing Library + jsdom).
 * `fetch` is mocked, so these tests need no backend; the real HTTP contract is covered by
 * backend contract tests and (Phase 4) Playwright end-to-end tests against compose.
 * Testing Library style: query by ROLE/LABEL like a user (and a screen reader) would.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import App from "./App";
import type { Idea } from "./api/types";

const idea = (id: number, content: string): Idea => ({
  id,
  content,
  created_at: "2026-10-28T10:00:00Z",
});

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockFetch(...responses: (Response | Error)[]) {
  const fn = vi.spyOn(globalThis, "fetch");
  for (const r of responses) {
    if (r instanceof Error) fn.mockRejectedValueOnce(r);
    else fn.mockResolvedValueOnce(r);
  }
  return fn;
}

describe("App", () => {
  it("shows a loading state, then the empty state", async () => {
    mockFetch(jsonResponse([]));
    render(<App />);
    expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
    expect(await screen.findByText(/no ideas yet/i)).toBeInTheDocument();
  });

  it("lists ideas newest first as returned by the API", async () => {
    mockFetch(jsonResponse([idea(2, "second"), idea(1, "first")]));
    render(<App />);
    const items = await screen.findAllByRole("listitem");
    expect(items.map((li) => li.querySelector("p")?.textContent)).toEqual(["second", "first"]);
  });

  it("shows an error with a working retry button", async () => {
    mockFetch(new TypeError("Failed to fetch"), jsonResponse([idea(1, "back online")]));
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/cannot reach the server/i);
    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText("back online")).toBeInTheDocument();
  });

  it("submits a trimmed idea, prepends it and clears the form", async () => {
    const fetchMock = mockFetch(
      jsonResponse([idea(1, "old")]),
      jsonResponse(idea(2, "new idea"), 201),
    );
    render(<App />);
    await screen.findByText("old");
    const box = screen.getByLabelText(/your idea/i);
    await userEvent.type(box, "   new idea   ");
    await userEvent.click(screen.getByRole("button", { name: /add idea/i }));

    expect(await screen.findByText("new idea")).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("new idea");
    expect(box).toHaveValue("");
    const [url, init] = fetchMock.mock.calls[1] ?? [];
    expect(url).toBe("/api/ideas");
    expect(init?.method).toBe("POST");
    expect(typeof init?.body).toBe("string");
    expect(JSON.parse(init?.body as string)).toEqual({ content: "new idea" });
  });

  it("disables submit for whitespace-only and over-long content", async () => {
    mockFetch(jsonResponse([]));
    render(<App />);
    await screen.findByText(/no ideas yet/i);
    const button = screen.getByRole("button", { name: /add idea/i });
    const box = screen.getByLabelText(/your idea/i);

    await userEvent.type(box, "    ");
    expect(button).toBeDisabled();

    await userEvent.clear(box);
    await userEvent.click(box);
    await userEvent.paste("a".repeat(501));
    expect(button).toBeDisabled();
    expect(box).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("501/500")).toBeInTheDocument();
  });

  it("shows the backend validation message on 422", async () => {
    mockFetch(
      jsonResponse([]),
      jsonResponse(
        {
          error: {
            code: "validation_error",
            message: "Request validation failed.",
            details: [{ field: "content", message: "String should have at most 500 characters" }],
          },
        },
        422,
      ),
    );
    render(<App />);
    await screen.findByText(/no ideas yet/i);
    await userEvent.type(screen.getByLabelText(/your idea/i), "valid locally");
    await userEvent.click(screen.getByRole("button", { name: /add idea/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/at most 500 characters/i);
  });

  it("renders HTML in ideas as plain text (XSS-safe)", async () => {
    mockFetch(jsonResponse([idea(1, "<img src=x onerror=alert(1)>")]));
    render(<App />);
    expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });

  it("uses the runtime-configured API base URL", async () => {
    window.__APP_CONFIG__ = { apiBaseUrl: "https://api.example.test/" };
    const fetchMock = mockFetch(jsonResponse([]));
    render(<App />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(fetchMock.mock.calls[0]?.[0]).toBe("https://api.example.test/api/ideas");
  });
});
