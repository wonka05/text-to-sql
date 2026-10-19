import { useState } from "react";
import { toast } from "react-toastify";
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import sqlLanguage from "react-syntax-highlighter/dist/esm/languages/prism/sql";
import oneDark from "react-syntax-highlighter/dist/esm/styles/prism/one-dark";
import oneLight from "react-syntax-highlighter/dist/esm/styles/prism/one-light";
import { BsClipboard, BsPencilSquare, BsPlayFill } from "react-icons/bs";

// Registering only SQL keeps the highlighter out of the bundle's way
SyntaxHighlighter.registerLanguage("sql", sqlLanguage);

function SqlPanel({ sql, executedSql, title = "Generated SQL", theme, busy, onRunSql }) {
  const [showExecuted, setShowExecuted] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(sql || "");
  const differs = executedSql && executedSql !== sql;
  const shown = showExecuted && differs ? executedSql : sql;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shown);
      toast.success("SQL copied");
    } catch {
      toast.error("Could not copy. Select the SQL and copy it manually.");
    }
  };

  const run = () => {
    if (!draft.trim()) return;
    setEditing(false);
    onRunSql(draft.trim());
  };

  return (
    <section className="card sql-panel mb-3" aria-label={title}>
      <div className="card-header d-flex flex-wrap gap-2 justify-content-between align-items-center">
        {differs ? (
          <div className="btn-group btn-group-sm" role="group" aria-label="Which SQL to show">
            <button
              type="button"
              className={`btn ${showExecuted ? "btn-outline-secondary" : "btn-secondary"}`}
              onClick={() => setShowExecuted(false)}
              aria-pressed={!showExecuted}
            >
              {title}
            </button>
            <button
              type="button"
              className={`btn ${showExecuted ? "btn-secondary" : "btn-outline-secondary"}`}
              onClick={() => setShowExecuted(true)}
              aria-pressed={showExecuted}
              title="The checked SQL the database actually ran, with the server's row limit"
            >
              Executed SQL
            </button>
          </div>
        ) : (
          <strong>{title}</strong>
        )}

        <div className="d-flex gap-2">
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={copy}>
            <BsClipboard className="me-1" aria-hidden="true" />
            Copy
          </button>
          {onRunSql && !editing && (
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              onClick={() => {
                setDraft(sql || "");
                setEditing(true);
              }}
              disabled={busy}
              title="Edit the SQL and run it yourself (checked by the same safety rules)"
            >
              <BsPencilSquare className="me-1" aria-hidden="true" />
              Edit
            </button>
          )}
        </div>
      </div>

      {editing ? (
        <div className="card-body">
          <label htmlFor="sql-editor" className="form-label small text-body-secondary">
            Edit the query. It runs through the same read-only checks as generated SQL.
          </label>
          <textarea
            id="sql-editor"
            className="form-control font-monospace sql-editor"
            rows={Math.min(12, Math.max(4, draft.split("\n").length + 1))}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run();
            }}
            spellCheck={false}
          />
          <div className="d-flex gap-2 mt-2">
            <button type="button" className="btn btn-sm btn-primary" onClick={run} disabled={busy || !draft.trim()}>
              <BsPlayFill className="me-1" aria-hidden="true" />
              Run (Ctrl+Enter)
            </button>
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <SyntaxHighlighter
          language="sql"
          style={theme === "dark" ? oneDark : oneLight}
          customStyle={{ margin: 0, padding: "1rem", borderRadius: 0, fontSize: "0.875rem" }}
          codeTagProps={{ style: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" } }}
        >
          {shown || ""}
        </SyntaxHighlighter>
      )}
    </section>
  );
}

export default SqlPanel;
