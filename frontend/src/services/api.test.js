import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, askQuestion, request } from "./api";

function mockFetch(impl) {
  vi.stubGlobal("fetch", vi.fn(impl));
  return globalThis.fetch;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("request", () => {
  it("sends the question and history as JSON", async () => {
    const fetch = mockFetch(async () => new Response(JSON.stringify({ status: "answered" }), { status: 200 }));
    const history = [{ question: "q", sql: "SELECT 1", reply: null }];

    await expect(askQuestion("How many?", history)).resolves.toEqual({ status: "answered" });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toMatch(/\/query$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ question: "How many?", history });
  });

  it("turns the backend's error envelope into an ApiError", async () => {
    mockFetch(async () =>
      new Response(JSON.stringify({ error: { code: "model_unavailable", message: "The AI model is down." } }), {
        status: 502,
      }),
    );
    await expect(request("/query")).rejects.toMatchObject({
      name: "ApiError",
      code: "model_unavailable",
      message: "The AI model is down.",
      status: 502,
    });
  });

  it("handles error responses that are not JSON", async () => {
    mockFetch(async () => new Response("<html>Bad gateway</html>", { status: 502 }));
    await expect(request("/query")).rejects.toMatchObject({ code: "http_error", status: 502 });
  });

  it("reports an unreachable server as a network error", async () => {
    mockFetch(async () => {
      throw new TypeError("Failed to fetch");
    });
    await expect(request("/health")).rejects.toMatchObject({ code: "network" });
  });

  it("reports a cancelled request as cancelled", async () => {
    mockFetch((_, init) => new Promise((_, reject) => {
      init.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    const controller = new AbortController();
    const pending = request("/query", { signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.toBeInstanceOf(ApiError);
    await expect(pending).rejects.toMatchObject({ code: "cancelled" });
  });

  it("gives up after the timeout", async () => {
    vi.useFakeTimers();
    mockFetch((_, init) => new Promise((_, reject) => {
      init.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    const pending = request("/query", { timeoutMs: 1000 });
    const assertion = expect(pending).rejects.toMatchObject({ code: "timeout" });
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
  });
});
