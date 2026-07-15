import { BsPersonCircle } from "react-icons/bs";

function ChatMessage({ question }) {
  return (
    <div className="card shadow-sm mb-4">

      <div className="card-body">

        <div className="d-flex align-items-center mb-2">

          <BsPersonCircle
            className="text-primary me-2"
            size={24}
          />

          <strong>Your Question</strong>

        </div>

        <div
          style={{
            fontSize: "16px",
            color: "#374151",
          }}
        >
          {question}
        </div>

      </div>

    </div>
  );
}

export default ChatMessage;