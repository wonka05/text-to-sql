import { useState } from "react";
import { ToastContainer, toast } from "react-toastify";

import Navbar from "./layout/Navbar";
import Header from "./layout/Header";

import ChatMessage from "./components/ChatMessage";
import SQLCard from "./components/SQLCard";
import ExecutionStats from "./components/ExecutionStats";
import ResultsTable from "./components/ResultsTable";
import LoadingSpinner from "./components/LoadingSpinner";
import InputBar from "./components/InputBar";

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const askQuestion = async () => {
    if (!question.trim()) return;

    setLoading(true);

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
        throw new Error(data.error || "Something went wrong");
      }

      setMessages((prev) => [
        ...prev,
        {
          question,
          sql: data.sql,
          explanation: data.explanation,
          data: data.data,
          executionTime: data.execution_time,
          rowsReturned: data.rows_returned,
          model: data.model,
          status: data.status,
        },
      ]);

      setQuestion("");

      toast.success("Query executed successfully");
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />

      <div
        className="container-fluid app-bg"
      >
        <div className="container py-4">

          <Header />

          <div className="card border-0 shadow-sm main-card">

            <div className="card-body">

              <div className="chat-window">

                {messages.length === 0 && (
                  <div className="welcome">

                    <h3>Welcome to QueryGenie</h3>

                    <p>
                      Ask questions about your database using natural language.
                    </p>

                    <div className="d-grid gap-2 col-md-6 mx-auto">

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
                          setQuestion(
                            "Average salary by department"
                          )
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

                    <ExecutionStats
                      model={msg.model}
                      executionTime={msg.executionTime}
                      rowsReturned={msg.rowsReturned}
                      status={msg.status}
                    />

                    <ResultsTable
                      data={msg.data}
                    />

                  </div>

                ))}

                {loading && <LoadingSpinner />}

              </div>

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

      <ToastContainer
        position="top-right"
        autoClose={2500}
        theme="light"
      />

    </>
  );
}

export default App;