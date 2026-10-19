import { describe, expect, it } from "vitest";
import {
  buildHistory,
  HISTORY_TURNS,
  LEGACY_KEY,
  loadState,
  MAX_STORED_ROWS,
  saveState,
  STORAGE_KEY,
  titleFrom,
} from "./conversations";

function memoryStorage(initial = {}, { quota = Infinity } = {}) {
  const data = { ...initial };
  return {
    data,
    getItem: (key) => (key in data ? data[key] : null),
    setItem: (key, value) => {
      if (value.length > quota) throw new Error("QuotaExceededError");
      data[key] = value;
    },
    removeItem: (key) => delete data[key],
  };
}

function doneTurn(question, response, kind = "question") {
  return { id: question, kind, question, state: "done", response };
}

describe("loadState", () => {
  it("starts with one empty conversation", () => {
    const state = loadState(memoryStorage());
    expect(state.conversations).toHaveLength(1);
    expect(state.activeId).toBe(state.conversations[0].id);
  });

  it("migrates the first version's flat history", () => {
    const legacy = [
      {
        question: "Average salary by department",
        sql: "SELECT ...",
        explanation: "Averages",
        data: [{ department_name: "Engineering", avg_salary: 120114.29 }],
        executionTime: 812,
        rowsReturned: 1,
        model: "gemini-2.5-flash",
        status: "Success",
        timestamp: "2026-10-01T10:00:00Z",
      },
      { question: "Second", sql: "SELECT 1", data: [] },
    ];
    const state = loadState(memoryStorage({ [LEGACY_KEY]: JSON.stringify(legacy) }));

    expect(state.conversations).toHaveLength(2);
    // Newest first
    expect(state.conversations[1].title).toBe("Average salary by department");
    const response = state.conversations[1].turns[0].response;
    expect(response.status).toBe("answered");
    expect(response.result.columns).toEqual([
      { name: "department_name", type: "text" },
      { name: "avg_salary", type: "number" },
    ]);
    expect(response.result.rows).toEqual([["Engineering", 120114.29]]);
    expect(response.timings.total_ms).toBe(812);
    expect(state.conversations[0].turns[0].response.result.rows).toEqual([]);
  });

  it("drops requests that were still pending when the page closed", () => {
    const saved = {
      activeId: "c1",
      conversations: [{ id: "c1", title: "t", turns: [{ id: "a", state: "done" }, { id: "b", state: "pending" }] }],
    };
    const state = loadState(memoryStorage({ [STORAGE_KEY]: JSON.stringify(saved) }));
    expect(state.conversations[0].turns.map((t) => t.id)).toEqual(["a"]);
  });

  it("survives corrupt storage", () => {
    const state = loadState(memoryStorage({ [STORAGE_KEY]: "{not json" }));
    expect(state.conversations).toHaveLength(1);
  });
});

describe("saveState", () => {
  it("stores at most MAX_STORED_ROWS rows per result and flags it", () => {
    const rows = Array.from({ length: 500 }, (_, i) => [i]);
    const state = {
      activeId: "c1",
      conversations: [{ id: "c1", turns: [doneTurn("q", { status: "answered", result: { columns: [], rows } })] }],
    };
    const storage = memoryStorage();
    saveState(state, storage);

    const saved = JSON.parse(storage.data[STORAGE_KEY]).conversations[0].turns[0].response.result;
    expect(saved.rows).toHaveLength(MAX_STORED_ROWS);
    expect(saved.stored_rows_trimmed).toBe(true);
    // The in-memory state keeps every row
    expect(state.conversations[0].turns[0].response.result.rows).toHaveLength(500);
  });

  it("drops the oldest conversations when the quota is exceeded", () => {
    const big = "x".repeat(400);
    const conversations = ["new", "middle", "old"].map((id) => ({ id, title: big, turns: [] }));
    const storage = memoryStorage({}, { quota: 1000 });
    expect(saveState({ activeId: "new", conversations }, storage)).toBe(true);
    const saved = JSON.parse(storage.data[STORAGE_KEY]).conversations.map((c) => c.id);
    expect(saved).toEqual(["new", "middle"]);
  });

  it("removes the legacy key once the new format is saved", () => {
    const storage = memoryStorage({ [LEGACY_KEY]: "[]" });
    saveState({ activeId: "c", conversations: [{ id: "c", turns: [] }] }, storage);
    expect(storage.data[LEGACY_KEY]).toBeUndefined();
  });
});

describe("buildHistory", () => {
  it("sends SQL for answered turns and the reply for the rest", () => {
    const turns = [
      doneTurn("Employees per department", { status: "answered", sql: "SELECT 1" }),
      doneTurn("Top ones", { status: "clarification", message: "Top by what?" }),
      doneTurn("Weather?", { status: "unsupported", message: "No weather data." }),
    ];
    expect(buildHistory(turns)).toEqual([
      { question: "Employees per department", sql: "SELECT 1", reply: null },
      { question: "Top ones", sql: null, reply: "Top by what?" },
      { question: "Weather?", sql: null, reply: "No weather data." },
    ]);
  });

  it("skips failed and pending turns and keeps only the most recent", () => {
    const turns = [
      ...Array.from({ length: 6 }, (_, i) => doneTurn(`q${i}`, { status: "answered", sql: `SELECT ${i}` })),
      { id: "e", kind: "question", question: "broken", state: "error", error: { message: "x" } },
      { id: "p", kind: "question", question: "waiting", state: "pending" },
    ];
    const history = buildHistory(turns);
    expect(history).toHaveLength(HISTORY_TURNS);
    expect(history.at(-1).question).toBe("q5");
  });

  it("describes SQL the user ran themselves", () => {
    const turn = doneTurn("", { status: "answered", sql: "SELECT 2" }, "sql");
    expect(buildHistory([turn])).toEqual([{ question: "Run my own SQL query", sql: "SELECT 2", reply: null }]);
  });
});

describe("titleFrom", () => {
  it("shortens long questions", () => {
    expect(titleFrom("a ".repeat(50))).toHaveLength(60);
    expect(titleFrom("  How many   orders? ")).toBe("How many orders?");
  });
});
