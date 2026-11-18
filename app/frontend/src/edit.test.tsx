/**
 * Edit UI tests. fetch is mocked by method + URL (call order does not
 * matter); queries go by role/text only.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import App from "./App";

const idea = (id: number, content: string) => ({
  id,
  content,
  created_at: "2026-10-28T10:00:00Z",
});

function json(body: unknown, status = 200, etag?: string): Response {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (etag) headers.ETag = etag;
  return new Response(JSON.stringify(body), { status, headers });
}

function errorBody(status: number, code: string): Response {
  return json({ error: { code, message: code, details: [] } }, status);
}

type Handler = (init: RequestInit | undefined) => Response;
type Call = { method: string; url: string; headers: Headers; body: unknown };

function routeFetch(routes: Record<string, Handler | Handler[]>) {
  const calls: Call[] = [];
  const spy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const method = (init?.method ?? "GET").toUpperCase();
    const headers = new Headers(init?.headers);
    calls.push({
      method,
      url,
      headers,
      body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
    });
    const route = routes[`${method} ${url}`];
    const handler = Array.isArray(route) ? route.shift() : route;
    if (!handler) throw new Error(`unexpected ${method} ${url}`);
    return handler(init);
  });
  return { spy, calls };
}

async function itemFor(text: string): Promise<HTMLElement> {
  const p = await screen.findByText(text);
  const li = p.closest("li");
  if (!li) throw new Error(`no list item for ${text}`);
  return li;
}

describe("edit idea ", () => {
  it("loads the idea with its ETag, PATCHes with If-Match and shows the result", async () => {
    const { calls } = routeFetch({
      "GET /api/ideas": () => json([idea(7, "seven"), idea(3, "three")]),
      "GET /api/ideas/7": () => json(idea(7, "seven server"), 200, '"4"'),
      "PATCH /api/ideas/7": () => json(idea(7, "seven edited"), 200, '"5"'),
    });
    render(<App />);
    const seven = await itemFor("seven");
    await userEvent.click(within(seven).getByRole("button", { name: "Edit" }));
    const box = await within(seven).findByRole("textbox");
    await waitFor(() => expect(box).toHaveValue("seven server"));
    await userEvent.clear(box);
    await userEvent.type(box, "seven edited");
    await userEvent.click(within(seven).getByRole("button", { name: "Save" }));

    await waitFor(() => expect(within(seven).queryByRole("textbox")).not.toBeInTheDocument());
    expect(seven).toHaveTextContent("seven edited");
    const patch = calls.filter((c) => c.method === "PATCH");
    expect(patch).toHaveLength(1);
    expect(patch[0]?.headers.get("If-Match")).toBe('"4"');
    expect(patch[0]?.body).toEqual({ content: "seven edited" });
    // No reload of the list; the other idea is untouched.
    expect(calls.filter((c) => c.method === "GET" && c.url === "/api/ideas")).toHaveLength(1);
    expect(await itemFor("three")).toBeInTheDocument();
  });

  it("on 412 keeps the editor open, warns, reloads and can save again", async () => {
    const { calls } = routeFetch({
      "GET /api/ideas": () => json([idea(9, "nine")]),
      "GET /api/ideas/9": [
        () => json(idea(9, "nine"), 200, '"1"'),
        () => json(idea(9, "nine by someone else"), 200, '"2"'),
      ],
      "PATCH /api/ideas/9": [
        () => errorBody(412, "precondition_failed"),
        () => json(idea(9, "mine after all"), 200, '"3"'),
      ],
    });
    render(<App />);
    const nine = await itemFor("nine");
    await userEvent.click(within(nine).getByRole("button", { name: "Edit" }));
    const box = await within(nine).findByRole("textbox");
    await waitFor(() => expect(box).toHaveValue("nine"));
    await userEvent.clear(box);
    await userEvent.type(box, "mine");
    await userEvent.click(within(nine).getByRole("button", { name: "Save" }));

    expect(await screen.findByText("This idea was changed by someone else.")).toBeInTheDocument();
    const reopened = within(nine).getByRole("textbox");
    await waitFor(() => expect(reopened).toHaveValue("nine by someone else"));

    await userEvent.clear(reopened);
    await userEvent.type(reopened, "mine after all");
    await userEvent.click(within(nine).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(within(nine).queryByRole("textbox")).not.toBeInTheDocument());
    expect(nine).toHaveTextContent("mine after all");
    const ifMatch = calls.filter((c) => c.method === "PATCH").map((c) => c.headers.get("If-Match"));
    expect(ifMatch).toEqual(['"1"', '"2"']);
  });

  it("can edit an idea that was just added through the form", async () => {
    const { calls } = routeFetch({
      "GET /api/ideas": () => json([]),
      "POST /api/ideas": () => json(idea(11, "fresh"), 201, '"1"'),
      "GET /api/ideas/11": () => json(idea(11, "fresh"), 200, '"1"'),
      "PATCH /api/ideas/11": () => json(idea(11, "fresher"), 200, '"2"'),
    });
    render(<App />);
    await screen.findByText(/No ideas yet/);
    const form = screen.getAllByRole("textbox")[0]!;
    await userEvent.type(form, "fresh");
    await userEvent.click(screen.getByRole("button", { name: /submit|add|share|post/i }));
    const fresh = await itemFor("fresh");
    await userEvent.click(within(fresh).getByRole("button", { name: "Edit" }));
    const box = await within(fresh).findByRole("textbox");
    await waitFor(() => expect(box).toHaveValue("fresh"));
    await userEvent.clear(box);
    await userEvent.type(box, "fresher");
    await userEvent.click(within(fresh).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(fresh).toHaveTextContent("fresher"));
    expect(calls.find((c) => c.method === "PATCH")?.headers.get("If-Match")).toBe('"1"');
  });
});
