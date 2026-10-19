import { BsSendFill, BsStopFill } from "react-icons/bs";

// Same limit as the backend (app/schemas/query.py)
const MAX_QUESTION_CHARS = 500;

function Composer({ value, onChange, onSubmit, onCancel, busy, hasContext, ref }) {
  const tooLong = value.length > MAX_QUESTION_CHARS;
  const canSend = !busy && value.trim() && !tooLong;

  const submit = (e) => {
    e.preventDefault();
    if (canSend) onSubmit(value.trim());
  };

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="question" className="visually-hidden">
        Ask a question about the database
      </label>
      <div className="input-group">
        <textarea
          id="question"
          ref={ref}
          className={`form-control ${tooLong ? "is-invalid" : ""}`}
          rows={Math.min(4, Math.max(1, value.split("\n").length))}
          placeholder={hasContext ? "Ask a follow-up, e.g. \"only for 2025\"..." : "Ask a question about your data..."}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) submit(e);
          }}
          aria-describedby="composer-help"
        />
        {busy ? (
          <button type="button" className="btn btn-outline-secondary px-3" onClick={onCancel} aria-label="Cancel request">
            <BsStopFill aria-hidden="true" />
          </button>
        ) : (
          <button type="submit" className="btn btn-primary px-3" disabled={!canSend} aria-label="Send question">
            <BsSendFill aria-hidden="true" />
          </button>
        )}
      </div>
      <div id="composer-help" className="d-flex justify-content-between small text-body-secondary mt-1">
        <span>
          {hasContext
            ? "Follow-ups use this conversation's earlier questions. Start a new conversation for a new topic."
            : "Enter to send, Shift+Enter for a new line."}
        </span>
        {value.length > MAX_QUESTION_CHARS * 0.8 && (
          <span className={tooLong ? "text-danger" : undefined}>
            {value.length}/{MAX_QUESTION_CHARS}
          </span>
        )}
      </div>
    </form>
  );
}

export default Composer;
