// Talks to the FastAPI backend. Every failure becomes an ApiError with a
// `code`, so the UI can tell "you cancelled" from "the server is down".

const BASE_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

// The backend may call the model twice (one repair) before answering
const QUERY_TIMEOUT_MS = 120_000;

export class ApiError extends Error {
  constructor(message, code, status = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export async function request(path, { method = "GET", body, signal, timeoutMs = 15_000 } = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onCallerAbort = () => controller.abort();
  signal?.addEventListener("abort", onCallerAbort);

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch {
    if (signal?.aborted) throw new ApiError("Cancelled.", "cancelled");
    if (timedOut) throw new ApiError("The server took too long to answer. Try again.", "timeout");
    throw new ApiError(
      "Can't reach the Querent API. Check that the backend is running.",
      "network",
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onCallerAbort);
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON body (e.g. a proxy error page); handled below
  }

  if (!response.ok) {
    throw new ApiError(
      data?.error?.message || `The server returned an error (HTTP ${response.status}).`,
      data?.error?.code || "http_error",
      response.status,
    );
  }
  if (data === null) {
    throw new ApiError("The server sent a response the app could not read.", "bad_response");
  }
  return data;
}

export function askQuestion(question, history, signal) {
  return request("/query", {
    method: "POST",
    body: { question, history },
    signal,
    timeoutMs: QUERY_TIMEOUT_MS,
  });
}

export function runSql(sql, signal) {
  return request("/sql", { method: "POST", body: { sql }, signal, timeoutMs: 60_000 });
}

export function getSchema() {
  return request("/schema");
}

export function getHealth() {
  return request("/health", { timeoutMs: 8_000 });
}
