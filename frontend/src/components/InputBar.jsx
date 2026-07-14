function InputBar({
  question,
  setQuestion,
  askQuestion,
  loading,
}) {
  return (
    <div className="input-group">

      <input
        className="form-control"
        placeholder="Ask anything..."
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            askQuestion();
          }
        }}
      />

      <button
        className="btn btn-primary"
        onClick={askQuestion}
        disabled={loading}
      >
        {loading ? "Thinking..." : "Send"}
      </button>

    </div>
  );
}

export default InputBar;