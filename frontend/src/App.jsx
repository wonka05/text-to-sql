import { useState } from "react";

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const askQuestion = async () => {
    if (!question.trim()) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch("http://127.0.0.1:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
        }),
      });

      const data = await res.json();

      if (!res.ok || data.error) {
        throw new Error(data.error || "Something went wrong.");
      }

      setMessages((prev) => [
        ...prev,
        {
          question,
          sql: data.sql,
          explanation: data.explanation,
          data: data.data,
        },
      ]);

      setQuestion("");
    } catch (err) {
      setError(err.message);
    }

    setLoading(false);
  };

  return (
    <div className="container mt-5">
      <div className="card shadow-lg">
        <div className="card-body">

          <h1 className="text-center text-primary">
            🤖 QueryGenie
          </h1>

          <p className="text-center text-muted mb-4">
            Ask questions about your database using natural language
          </p>

          <div
            style={{
              maxHeight: "550px",
              overflowY: "auto",
              marginBottom: "25px",
            }}
          >
            {messages.map((msg, index) => (
              <div key={index} className="mb-5">

                <div className="alert alert-primary">
                  <strong>👤 You</strong>
                  <br />
                  {msg.question}
                </div>

                <div className="card mb-3">
                  <div className="card-header bg-dark text-white">
                    Generated SQL
                  </div>

                  <div className="card-body">
                    <pre>{msg.sql}</pre>
                  </div>
                </div>

                <div className="card mb-3">
                  <div className="card-header bg-info text-white">
                    SQL Explanation
                  </div>

                  <div className="card-body">
                    {msg.explanation}
                  </div>
                </div>

                <div className="card">
                  <div className="card-header bg-success text-white">
                    Query Results
                  </div>

                  <div className="card-body">

                    {msg.data.length > 0 ? (

                      <div className="table-responsive">

                        <table className="table table-striped table-hover table-bordered">

                          <thead className="table-dark">

                            <tr>
                              {Object.keys(msg.data[0]).map((key) => (
                                <th key={key}>{key}</th>
                              ))}
                            </tr>

                          </thead>

                          <tbody>

                            {msg.data.map((row, i) => (
                              <tr key={i}>
                                {Object.values(row).map((value, j) => (
                                  <td key={j}>{String(value)}</td>
                                ))}
                              </tr>
                            ))}

                          </tbody>

                        </table>

                      </div>

                    ) : (

                      <div className="alert alert-warning">
                        No records found.
                      </div>

                    )}

                  </div>
                </div>

              </div>
            ))}

            {loading && (
              <div className="text-center">
                <div className="spinner-border text-primary"></div>
                <p className="mt-3">
                  🤖 QueryGenie is thinking...
                </p>
              </div>
            )}

          </div>

          {error && (
            <div className="alert alert-danger">
              {error}
            </div>
          )}

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

        </div>
      </div>
    </div>
  );
}

export default App;