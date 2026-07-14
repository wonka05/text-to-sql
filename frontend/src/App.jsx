import { useState } from "react";

import Navbar from "./layout/Navbar";
import Header from "./layout/Header";

import ChatMessage from "./components/ChatMessage";
import SQLCard from "./components/SQLCard";
import ResultsTable from "./components/ResultsTable";
import LoadingSpinner from "./components/LoadingSpinner";
import InputBar from "./components/InputBar";

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
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />

      <div
        className="container-fluid"
        style={{
          background: "#F8FAFC",
          minHeight: "100vh",
        }}
      >
        <div className="container py-4">

          <Header />

          <div className="card shadow-sm border-0">

            <div className="card-body">

              <div
                style={{
                  maxHeight: "550px",
                  overflowY: "auto",
                  marginBottom: "25px",
                }}
              >
                {messages.length === 0 && (
                  <div className="text-center text-muted py-5">
                    <h5>Start by asking a question</h5>

                    <p className="mt-3">
                      Example:
                    </p>

                    <div className="d-flex flex-column gap-2">

                      <button
                        className="btn btn-outline-primary"
                        onClick={() =>
                          setQuestion("Highest paid employee")
                        }
                      >
                        Highest paid employee
                      </button>

                      <button
                        className="btn btn-outline-primary"
                        onClick={() =>
                          setQuestion("Average salary by department")
                        }
                      >
                        Average salary by department
                      </button>

                      <button
                        className="btn btn-outline-primary"
                        onClick={() =>
                          setQuestion("Products with low stock")
                        }
                      >
                        Products with low stock
                      </button>

                    </div>
                  </div>
                )}

                {messages.map((msg, index) => (
                  <div key={index} className="mb-5">

                    <ChatMessage
                      question={msg.question}
                    />

                    <SQLCard
                      sql={msg.sql}
                      explanation={msg.explanation}
                    />

                    <ResultsTable
                      data={msg.data}
                    />

                  </div>
                ))}

                {loading && <LoadingSpinner />}

              </div>

              {error && (
                <div className="alert alert-danger">
                  {error}
                </div>
              )}

              <InputBar
                question={question}
                setQuestion={setQuestion}
                askQuestion={askQuestion}
                loading={loading}
              />

            </div>

          </div>

        </div>

      </div>

    </>
  );
}

export default App;