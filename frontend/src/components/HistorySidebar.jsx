import { BsClockHistory, BsTrash } from "react-icons/bs";

function HistorySidebar({
  messages,
  selectedIndex,
  setSelectedIndex,
  clearHistory,
}) {
  return (
    <div className="card shadow-sm h-100">

      <div className="card-header d-flex justify-content-between align-items-center">

        <strong>
          <BsClockHistory className="me-2" />
          History
        </strong>

        <button
          className="btn btn-sm btn-outline-danger"
          onClick={clearHistory}
        >
          <BsTrash />
        </button>

      </div>

      <div
        className="list-group list-group-flush"
        style={{
          maxHeight: "75vh",
          overflowY: "auto",
        }}
      >

        {messages.length === 0 ? (
          <div className="p-3 text-muted">
            No history yet
          </div>
        ) : (
          messages.map((msg, index) => (
            <button
              key={index}
              className={`list-group-item list-group-item-action ${
                selectedIndex === index ? "active" : ""
              }`}
              onClick={() => setSelectedIndex(index)}
            >
              {msg.question}
            </button>
          ))
        )}

      </div>

    </div>
  );
}

export default HistorySidebar;