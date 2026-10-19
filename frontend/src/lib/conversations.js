// Conversations are kept in the browser (localStorage), not on the server.
// The keys keep the app's old name (QueryGenie) so saved conversations survive the rename.
//
// Shape:
//   { conversations: [{ id, title, createdAt, turns: [turn] }], activeId }
//   turn = { id, kind: "question" | "sql", question, sql, createdAt,
//            state: "pending" | "done" | "error", response, error }
// `response` is the API's QueryResponse exactly as received (snake_case), so
// a change in the UI never needs to translate stored data.

export const STORAGE_KEY = "querygenie-conversations";
// The first version of the app stored a flat list of answered questions here
export const LEGACY_KEY = "querygenie-history";

export const HISTORY_TURNS = 4;
const MAX_CONVERSATIONS = 30;
// Results are capped at 500 rows by the server; keep fewer to stay well
// under the browser's ~5 MB localStorage quota
export const MAX_STORED_ROWS = 100;

export function newId(prefix) {
  return `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

export function newConversation() {
  return { id: newId("c"), title: "New conversation", createdAt: new Date().toISOString(), turns: [] };
}

export function titleFrom(text) {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > 60 ? `${clean.slice(0, 57)}...` : clean || "New conversation";
}

export function emptyState() {
  const conversation = newConversation();
  return { conversations: [conversation], activeId: conversation.id };
}

// Converts one v1 message ({question, sql, explanation, data: [{col: value}],
// executionTime, rowsReturned, model, status, timestamp}) into a conversation.
export function migrateLegacyMessage(message) {
  const data = Array.isArray(message.data) ? message.data : [];
  const columns = data.length ? Object.keys(data[0]) : [];
  const createdAt = message.timestamp || new Date().toISOString();
  return {
    id: newId("c"),
    title: titleFrom(message.question || "Imported question"),
    createdAt,
    turns: [
      {
        id: newId("t"),
        kind: "question",
        question: message.question || "",
        createdAt,
        state: "done",
        response: {
          status: "answered",
          question: message.question || "",
          explanation: message.explanation || "",
          assumptions: [],
          options: [],
          sql: message.sql || null,
          executed_sql: null,
          result: {
            columns: columns.map((name) => ({ name, type: inferType(data.map((row) => row[name])) })),
            rows: data.map((row) => columns.map((name) => row[name])),
            row_count: data.length,
            truncated: false,
            row_limit: null,
          },
          attempts: [],
          model: message.model || null,
          cached: false,
          timings: { generation_ms: 0, execution_ms: 0, total_ms: message.executionTime || 0 },
        },
      },
    ],
  };
}

function inferType(values) {
  const present = values.filter((v) => v !== null && v !== undefined);
  if (present.length && present.every((v) => typeof v === "number")) return "number";
  return "text";
}

function isValidState(state) {
  return (
    state &&
    Array.isArray(state.conversations) &&
    state.conversations.every((c) => c && typeof c.id === "string" && Array.isArray(c.turns))
  );
}

export function loadState(storage = window.localStorage) {
  try {
    const saved = JSON.parse(storage.getItem(STORAGE_KEY));
    if (isValidState(saved)) {
      // A request that was in flight when the page closed will never finish
      const conversations = saved.conversations.map((c) => ({
        ...c,
        turns: c.turns.filter((t) => t.state !== "pending"),
      }));
      if (conversations.length === 0) return emptyState();
      const activeId = conversations.some((c) => c.id === saved.activeId)
        ? saved.activeId
        : conversations[0].id;
      return { conversations, activeId };
    }

    const legacy = JSON.parse(storage.getItem(LEGACY_KEY));
    if (Array.isArray(legacy) && legacy.length) {
      const conversations = legacy.map(migrateLegacyMessage).reverse();
      return { conversations, activeId: conversations[0].id };
    }
  } catch {
    // Corrupt or unreadable storage: start fresh rather than crash
  }
  return emptyState();
}

export function trimForStorage(state) {
  const conversations = state.conversations.slice(0, MAX_CONVERSATIONS).map((c) => ({
    ...c,
    turns: c.turns
      .filter((t) => t.state !== "pending")
      .map((t) => {
        const result = t.response?.result;
        if (!result || result.rows.length <= MAX_STORED_ROWS) return t;
        return {
          ...t,
          response: {
            ...t.response,
            result: { ...result, rows: result.rows.slice(0, MAX_STORED_ROWS), stored_rows_trimmed: true },
          },
        };
      }),
  }));
  return { ...state, conversations };
}

export function saveState(state, storage = window.localStorage) {
  let trimmed = trimForStorage(state);
  // If the quota is still exceeded, drop the oldest conversations until it fits
  while (trimmed.conversations.length > 0) {
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
      storage.removeItem(LEGACY_KEY);
      return true;
    } catch {
      trimmed = { ...trimmed, conversations: trimmed.conversations.slice(0, -1) };
    }
  }
  return false;
}

// What the server needs to understand a follow-up: the last few finished
// turns, as {question, sql, reply}. Failed and cancelled turns are left out.
export function buildHistory(turns) {
  return turns
    .filter((t) => t.state === "done" && t.response)
    .slice(-HISTORY_TURNS)
    .map((t) => {
      const r = t.response;
      const ranQuery = r.status === "answered" && r.sql;
      return {
        question: t.kind === "sql" ? "Run my own SQL query" : t.question,
        sql: ranQuery ? r.sql : null,
        reply: ranQuery ? null : r.message || null,
      };
    });
}
