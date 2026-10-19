import { useEffect, useState } from "react";
import {
  BsArrowRepeat,
  BsCheckCircleFill,
  BsDiagram3,
  BsExclamationOctagonFill,
  BsExclamationTriangleFill,
  BsInfoCircleFill,
  BsPersonCircle,
  BsQuestionCircleFill,
  BsShieldFillX,
  BsWrench,
} from "react-icons/bs";
import { formatDuration } from "../lib/results";
import ResultView from "./ResultView";
import SqlPanel from "./SqlPanel";

function QuestionBubble({ turn }) {
  return (
    <div className="d-flex justify-content-end mb-2">
      <div className="question-bubble">
        <div className="small opacity-75 mb-1">
          <BsPersonCircle className="me-1" aria-hidden="true" />
          {turn.kind === "sql" ? "You ran SQL" : "You asked"}
        </div>
        {turn.kind === "sql" ? <code className="d-block text-reset text-break">{turn.sql}</code> : turn.question}
      </div>
    </div>
  );
}

function Pending({ onCancel, kind }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  const stage = kind === "sql" ? "Checking and running your SQL" : "Writing SQL, checking it and running it";

  return (
    <div className="answer-card card mb-3" role="status" aria-live="polite">
      <div className="card-body d-flex align-items-center gap-3">
        <div className="spinner-border spinner-border-sm text-primary" aria-hidden="true" />
        <span className="me-auto">
          {stage}... <span className="text-body-secondary">{seconds}s</span>
        </span>
        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function Attempts({ attempts }) {
  if (!attempts?.length) return null;
  const stageNames = {
    model_output: "Unreadable model reply",
    validation: "Rejected by the safety check",
    execution: "Database error",
  };
  return (
    <details className="attempts mb-3">
      <summary className="small">
        <BsWrench className="me-1" aria-hidden="true" />
        {attempts.length === 1 ? "1 earlier attempt failed" : `${attempts.length} earlier attempts failed`} and
        was sent back to the model with the error
      </summary>
      <ol className="small mt-2 mb-0">
        {attempts.map((attempt, i) => (
          <li key={i} className="mb-2">
            <strong>{stageNames[attempt.stage] || attempt.stage}:</strong> {attempt.error}
            {attempt.sql && <pre className="attempt-sql mt-1 mb-0">{attempt.sql}</pre>}
          </li>
        ))}
      </ol>
    </details>
  );
}

function Stats({ response }) {
  const { timings, result, model, cached } = response;
  const items = [
    result && ["Rows", result.truncated ? `${result.row_count}+` : result.row_count],
    timings?.generation_ms > 0 && ["AI", formatDuration(timings.generation_ms)],
    ["Database", formatDuration(timings?.execution_ms)],
    ["Total", formatDuration(timings?.total_ms)],
    model && ["Model", model],
  ].filter(Boolean);
  return (
    <ul className="stats list-inline small text-body-secondary mb-0">
      {items.map(([label, value]) => (
        <li key={label} className="list-inline-item me-3">
          {label}: <span className="text-body">{value}</span>
        </li>
      ))}
      {cached && (
        <li className="list-inline-item" title="Same question as before: the earlier SQL was reused and run again">
          <span className="badge text-bg-secondary">reused SQL</span>
        </li>
      )}
    </ul>
  );
}

function Header({ icon, tone, children }) {
  return (
    <div className={`d-flex align-items-center gap-2 fw-semibold mb-2 text-${tone}-emphasis`}>
      {icon}
      <span>{children}</span>
    </div>
  );
}

function Answered({ turn, response, theme, busy, onRunSql, onRefresh }) {
  return (
    <>
      <Header icon={<BsCheckCircleFill aria-hidden="true" />} tone="success">
        {turn.kind === "sql" ? "Query ran" : "Answered"}
        {response.attempts?.length > 0 && <span className="badge text-bg-info ms-2">self-corrected</span>}
      </Header>

      {response.explanation && (
        <p className="mb-2">
          <span className="text-body-secondary">What this query does: </span>
          {response.explanation}
        </p>
      )}
      {response.assumptions?.length > 0 && (
        <div className="assumptions small mb-3">
          <span className="fw-semibold">Assumptions</span>
          <ul className="mb-0">
            {response.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <ResultView result={response.result} theme={theme} busy={busy} onRefresh={onRefresh} />
      <SqlPanel
        key={response.sql}
        sql={response.sql}
        executedSql={response.executed_sql}
        title={turn.kind === "sql" ? "Your SQL" : "Generated SQL"}
        theme={theme}
        busy={busy}
        onRunSql={onRunSql}
      />
      <Attempts attempts={response.attempts} />
      <Stats response={response} />
    </>
  );
}

function Turn({ turn, theme, busy, onAsk, onRetry, onRunSql, onRefresh, onCancel, onOpenSchema, ref }) {
  const response = turn.response;
  let body;

  if (turn.state === "pending") {
    return (
      <div className="turn" ref={ref}>
        <QuestionBubble turn={turn} />
        <Pending onCancel={onCancel} kind={turn.kind} />
      </div>
    );
  }

  if (turn.state === "error") {
    body = (
      <>
        <Header icon={<BsExclamationOctagonFill aria-hidden="true" />} tone="danger">
          Request failed
        </Header>
        <p className="mb-2">{turn.error?.message}</p>
        <button type="button" className="btn btn-sm btn-outline-primary" onClick={onRetry} disabled={busy}>
          <BsArrowRepeat className="me-1" aria-hidden="true" />
          Try again
        </button>
      </>
    );
  } else if (response.status === "answered") {
    body = (
      <Answered
        turn={turn}
        response={response}
        theme={theme}
        busy={busy}
        onRunSql={onRunSql}
        onRefresh={response.sql ? onRefresh : null}
      />
    );
  } else if (response.status === "clarification") {
    body = (
      <>
        <Header icon={<BsQuestionCircleFill aria-hidden="true" />} tone="primary">
          Which do you mean?
        </Header>
        <p className="mb-2">{response.message}</p>
        {response.options?.length > 0 && (
          <div className="d-flex flex-wrap gap-2 mb-2">
            {response.options.map((option) => (
              <button
                key={option}
                type="button"
                className="btn btn-sm btn-outline-primary text-start"
                onClick={() => onAsk(option)}
                disabled={busy}
              >
                {option}
              </button>
            ))}
          </div>
        )}
        <small className="text-body-secondary">Pick one, or answer in your own words below.</small>
      </>
    );
  } else if (response.status === "unsupported") {
    body = (
      <>
        <Header icon={<BsInfoCircleFill aria-hidden="true" />} tone="secondary">
          Can't answer this from the database
        </Header>
        <p className="mb-2">{response.message}</p>
        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onOpenSchema}>
          <BsDiagram3 className="me-1" aria-hidden="true" />
          See what data is available
        </button>
      </>
    );
  } else {
    const blocked = response.status === "rejected";
    body = (
      <>
        <Header
          icon={blocked ? <BsShieldFillX aria-hidden="true" /> : <BsExclamationTriangleFill aria-hidden="true" />}
          tone={blocked ? "warning" : "danger"}
        >
          {blocked ? "Blocked by the safety check, nothing was run" : "The database could not run the query"}
        </Header>
        <p className="mb-3">{response.message}</p>
        {response.sql && (
          <SqlPanel
            key={response.sql}
            sql={response.sql}
            title={blocked ? "Rejected SQL" : "Failed SQL"}
            theme={theme}
            busy={busy}
            onRunSql={onRunSql}
          />
        )}
        <Attempts attempts={response.attempts} />
        {turn.kind === "question" && (
          <button type="button" className="btn btn-sm btn-outline-primary" onClick={onRetry} disabled={busy}>
            <BsArrowRepeat className="me-1" aria-hidden="true" />
            Ask again
          </button>
        )}
      </>
    );
  }

  return (
    <div className="turn" ref={ref}>
      <QuestionBubble turn={turn} />
      <div className="answer-card card mb-4">
        <div className="card-body">{body}</div>
      </div>
    </div>
  );
}

export default Turn;
