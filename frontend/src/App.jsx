import { useState, useEffect } from "react";
import { ToastContainer, toast } from "react-toastify";

import Navbar from "./layout/Navbar";
import Header from "./layout/Header";

import HistorySidebar from "./components/HistorySidebar";
import ChatMessage from "./components/ChatMessage";
import SQLCard from "./components/SQLCard";
import ExecutionStats from "./components/ExecutionStats";
import ResultsTable from "./components/ResultsTable";
import LoadingSpinner from "./components/LoadingSpinner";
import InputBar from "./components/InputBar";

import { askQuery } from "./services/api";

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [loading, setLoading] = useState(false);

  // Load history on startup
  useEffect(() => {
    const savedHistory = localStorage.getItem("querygenie-history");

    if (savedHistory) {
      const parsed = JSON.parse(savedHistory);

      setMessages(parsed);

      if (parsed.length > 0) {
        setSelectedIndex(parsed.length - 1);
      }
    }
  }, []);

  // Save history whenever messages change
  useEffect(() => {
    localStorage.setItem(
      "querygenie-history",
      JSON.stringify(messages)
    );
  }, [messages]);

  const clearHistory = () => {
    setMessages([]);
    setSelectedIndex(null);

    localStorage.removeItem("querygenie-history");

    toast.success("History cleared");
  };

  const askQuestion = async () => {
    if (!question.trim()) return;

    setLoading(true);

    try {
      const data = await askQuery(question);

      const newMessage = {
        question,
        sql: data.sql,
        explanation: data.explanation,
        data: data.data,
        executionTime: data.execution_time,
        rowsReturned: data.rows_returned,
        model: data.model,
        status: data.status,
      };

      setMessages((prev) => {
        const updated = [...prev, newMessage];

        setSelectedIndex(updated.length - 1);

        return updated;
      });

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

      <div className="container-fluid app-bg">
        <div className="container py-4">

          <Header />

          <div className="row g-4">

            {/* History Sidebar */}

            <div className="col-lg-3">

              <HistorySidebar
                messages={messages}
                selectedIndex={selectedIndex}
                setSelectedIndex={setSelectedIndex}
                clearHistory={clearHistory}
              />

            </div>

            {/* Main Content */}

            <div className="col-lg-9">

              <div className="card border-0 shadow-sm main-card">

                <div className="card-body">

                  {/* Welcome Screen */}

                  {messages.length === 0 && (

                    <div className="welcome text-center py-5">

                      <h3>Welcome to QueryGenie</h3>

                      <p className="text-muted mb-4">
                        Ask questions about your database using natural language.
                      </p>

                      <div className="d-grid gap-2 col-md-8 mx-auto">

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

                  {/* Loading */}

                  {loading && <LoadingSpinner />}

                  {/* Selected Conversation */}

                  {!loading &&
                    selectedIndex !== null &&
                    messages[selectedIndex] && (

                      <>

                        <ChatMessage
                          question={messages[selectedIndex].question}
                        />

                        <SQLCard
                          sql={messages[selectedIndex].sql}
                          explanation={
                            messages[selectedIndex].explanation
                          }
                        />

                        <ExecutionStats
                          model={messages[selectedIndex].model}
                          executionTime={
                            messages[selectedIndex].executionTime
                          }
                          rowsReturned={
                            messages[selectedIndex].rowsReturned
                          }
                          status={messages[selectedIndex].status}
                        />

                        <ResultsTable
                          data={messages[selectedIndex].data}
                        />

                      </>

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

        </div>

      </div>

      <ToastContainer
        position="top-right"
        autoClose={2500}
        newestOnTop
        closeOnClick
        pauseOnHover
        theme="light"
      />

    </>
  );
}

export default App;