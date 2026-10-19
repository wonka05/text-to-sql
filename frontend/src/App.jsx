import { useCallback, useEffect, useRef, useState } from "react";
import { toast, ToastContainer } from "react-toastify";
import { BsPlusLg } from "react-icons/bs";

import Navbar from "./layout/Navbar";
import Composer from "./components/Composer";
import ConversationList from "./components/ConversationList";
import SchemaExplorer from "./components/SchemaExplorer";
import Turn from "./components/Turn";
import Welcome from "./components/Welcome";
import { ApiError, askQuestion, getHealth, getSchema, runSql } from "./services/api";
import {
  buildHistory,
  emptyState,
  loadState,
  newConversation,
  newId,
  saveState,
  titleFrom,
} from "./lib/conversations";

function initialTheme() {
  try {
    const saved = localStorage.getItem("theme");
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    // Storage blocked: fall back to the OS preference
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function App() {
  const [store, setStore] = useState(() => loadState());
  const [theme, setTheme] = useState(initialTheme);
  const [health, setHealth] = useState({ state: "checking" });
  const [schemaState, setSchemaState] = useState({ schema: null, error: null, loading: true });
  const [showSchema, setShowSchema] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const controllerRef = useRef(null);
  const composerRef = useRef(null);
  const lastTurnRef = useRef(null);

  const active = store.conversations.find((c) => c.id === store.activeId) || store.conversations[0];

  useEffect(() => {
    saveState(store);
  }, [store]);

  useEffect(() => {
    document.documentElement.dataset.bsTheme = theme;
    try {
      localStorage.setItem("theme", theme);
    } catch {
      // Not saved; the theme still applies for this visit
    }
  }, [theme]);

  const checkHealth = useCallback(async () => {
    try {
      const result = await getHealth();
      setHealth({
        state: result.database.ok ? "ok" : "degraded",
        model: result.model,
        error: result.database.error,
      });
    } catch (err) {
      setHealth({ state: "offline", error: err.message });
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const timer = setInterval(checkHealth, 30_000);
    return () => clearInterval(timer);
  }, [checkHealth]);

  const fetchSchema = useCallback(async () => {
    try {
      const schema = await getSchema();
      setSchemaState({ schema, error: null, loading: false });
    } catch (err) {
      setSchemaState((s) => ({ ...s, error: err.message, loading: false }));
    }
  }, []);

  useEffect(() => {
    fetchSchema();
  }, [fetchSchema]);

  const reloadSchema = () => {
    setSchemaState((s) => ({ ...s, loading: true, error: null }));
    fetchSchema();
  };

  const openSchema = () => {
    if (schemaState.error) reloadSchema();
    setShowSchema(true);
  };

  const turnCount = active.turns.length;
  // Bring the newest question to the top of the view; its answer reads downward
  useEffect(() => {
    lastTurnRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [turnCount, active.id]);

  // --- conversation state helpers -------------------------------------------

  const mapConversation = (id, fn) =>
    setStore((s) => ({ ...s, conversations: s.conversations.map((c) => (c.id === id ? fn(c) : c)) }));

  const updateTurn = (conversationId, turnId, changes) =>
    mapConversation(conversationId, (c) => ({
      ...c,
      turns: c.turns.map((t) =>
        t.id === turnId ? { ...t, ...(typeof changes === "function" ? changes(t) : changes) } : t,
      ),
    }));

  const removeTurn = (conversationId, turnId) =>
    mapConversation(conversationId, (c) => ({ ...c, turns: c.turns.filter((t) => t.id !== turnId) }));

  // --- requests ---------------------------------------------------------------

  // One request at a time; `turns` is the context a question follows on from
  const send = async ({ kind, question = "", sql = null, turns = active.turns }) => {
    if (busy) return;
    const conversationId = active.id;
    const turn = {
      id: newId("t"),
      kind,
      question,
      sql,
      createdAt: new Date().toISOString(),
      state: "pending",
      response: null,
      error: null,
    };
    mapConversation(conversationId, (c) => ({
      ...c,
      title: c.turns.length === 0 ? titleFrom(kind === "sql" ? `SQL: ${sql}` : question) : c.title,
      turns: [...c.turns, turn],
    }));

    const controller = new AbortController();
    controllerRef.current = controller;
    setBusy(true);
    try {
      const response =
        kind === "sql"
          ? await runSql(sql, controller.signal)
          : await askQuestion(question, buildHistory(turns), controller.signal);
      updateTurn(conversationId, turn.id, { state: "done", response });
    } catch (err) {
      if (err instanceof ApiError && err.code === "cancelled") {
        removeTurn(conversationId, turn.id);
        if (kind === "question") setDraft(question);
      } else {
        updateTurn(conversationId, turn.id, {
          state: "error",
          error: { code: err.code || "error", message: err.message },
        });
        if (["network", "database_unavailable"].includes(err.code)) checkHealth();
      }
    } finally {
      controllerRef.current = null;
      setBusy(false);
      composerRef.current?.focus();
    }
  };

  const ask = (question) => {
    setDraft("");
    send({ kind: "question", question });
  };

  const runOwnSql = (sql) => send({ kind: "sql", sql });

  const retry = (turn) => {
    const earlier = active.turns.slice(0, active.turns.findIndex((t) => t.id === turn.id));
    removeTurn(active.id, turn.id);
    if (turn.kind === "sql") send({ kind: "sql", sql: turn.sql, turns: earlier });
    else send({ kind: "question", question: turn.question, turns: earlier });
  };

  // Re-run a turn's SQL for fresh results, without asking the model again
  const refresh = async (turn) => {
    if (busy) return;
    const conversationId = active.id;
    const controller = new AbortController();
    controllerRef.current = controller;
    setBusy(true);
    try {
      const fresh = await runSql(turn.response.sql, controller.signal);
      if (fresh.status !== "answered") {
        toast.error(fresh.message || "The query could not be run again.");
        return;
      }
      updateTurn(conversationId, turn.id, (t) => ({
        response: {
          ...t.response,
          result: fresh.result,
          executed_sql: fresh.executed_sql,
          timings: { ...t.response.timings, execution_ms: fresh.timings.execution_ms },
        },
      }));
      toast.success("Results refreshed");
    } catch (err) {
      if (err.code !== "cancelled") toast.error(err.message);
    } finally {
      controllerRef.current = null;
      setBusy(false);
    }
  };

  const cancel = () => controllerRef.current?.abort();

  // --- conversations ----------------------------------------------------------

  const startConversation = () => {
    if (active.turns.length === 0) {
      composerRef.current?.focus();
      return;
    }
    const conversation = newConversation();
    setStore((s) => ({ conversations: [conversation, ...s.conversations], activeId: conversation.id }));
    setDraft("");
    composerRef.current?.focus();
  };

  const selectConversation = (id) => setStore((s) => ({ ...s, activeId: id }));

  const deleteConversation = (id) => {
    const conversation = store.conversations.find((c) => c.id === id);
    if (conversation?.turns.length && !window.confirm(`Delete "${conversation.title}"?`)) return;
    setStore((s) => {
      const conversations = s.conversations.filter((c) => c.id !== id);
      if (conversations.length === 0) return emptyState();
      const activeId = s.activeId === id ? conversations[0].id : s.activeId;
      return { conversations, activeId };
    });
  };

  const clearAll = () => {
    if (!window.confirm("Delete all conversations saved in this browser?")) return;
    setStore(emptyState());
    toast.success("All conversations deleted");
  };

  const turnProps = (turn) => ({
    turn,
    theme,
    busy,
    onAsk: ask,
    onRetry: () => retry(turn),
    onRunSql: runOwnSql,
    onRefresh: () => refresh(turn),
    onCancel: cancel,
    onOpenSchema: openSchema,
  });

  return (
    <>
      <Navbar
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        health={health}
        onOpenSchema={openSchema}
      />

      <div className="container-fluid app-shell">
        <div className="row g-3 g-lg-4 px-lg-2 pt-3">
          <div className="col-lg-3 d-none d-lg-block">
            <ConversationList
              conversations={store.conversations}
              activeId={active.id}
              busy={busy}
              onSelect={selectConversation}
              onNew={startConversation}
              onDelete={deleteConversation}
              onClearAll={clearAll}
            />
          </div>

          <main className="col-lg-9 d-flex flex-column">
            {/* Small screens: the sidebar is hidden, so offer the same controls here */}
            <div className="d-flex d-lg-none gap-2 mb-3">
              <select
                className="form-select form-select-sm"
                aria-label="Conversation"
                value={active.id}
                onChange={(e) => selectConversation(e.target.value)}
                disabled={busy}
              >
                {store.conversations.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn btn-sm btn-primary text-nowrap"
                onClick={startConversation}
                disabled={busy}
              >
                <BsPlusLg className="me-1" aria-hidden="true" />
                New
              </button>
            </div>

            <div className="thread flex-grow-1">
              {active.turns.length === 0 ? (
                <Welcome schema={schemaState.schema} busy={busy} onAsk={ask} />
              ) : (
                active.turns.map((turn, i) => (
                  <Turn
                    key={turn.id}
                    ref={i === active.turns.length - 1 ? lastTurnRef : undefined}
                    {...turnProps(turn)}
                  />
                ))
              )}
            </div>

            <div className="composer-dock">
              <Composer
                ref={composerRef}
                value={draft}
                onChange={setDraft}
                onSubmit={ask}
                onCancel={cancel}
                busy={busy}
                hasContext={active.turns.some((t) => t.state === "done")}
              />
            </div>
          </main>
        </div>
      </div>

      <SchemaExplorer
        show={showSchema}
        onHide={() => setShowSchema(false)}
        schema={schemaState.schema}
        error={schemaState.error}
        loading={schemaState.loading}
        onReload={reloadSchema}
        onRunSql={(sql) => {
          setShowSchema(false);
          runOwnSql(sql);
        }}
        busy={busy}
      />

      <ToastContainer position="bottom-right" autoClose={2500} theme={theme} />
    </>
  );
}

export default App;
