import { BsSendFill } from "react-icons/bs";

function InputBar({
  question,
  setQuestion,
  askQuestion,
  loading,
}) {
  return (
    <div className="input-group mt-4">

      <input
        className="form-control"
        placeholder="Ask a question about your database..."
        value={question}
        onChange={(e) =>
          setQuestion(e.target.value)
        }
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            askQuestion();
          }
        }}
      />

      <button
        className="btn btn-primary px-4"
        onClick={askQuestion}
        disabled={loading}
      >
        <BsSendFill />
      </button>

    </div>
  );
}

export default InputBar;