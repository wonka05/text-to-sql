import { BsChatLeftText, BsPlusLg, BsTrash } from "react-icons/bs";

function ConversationList({ conversations, activeId, busy, onSelect, onNew, onDelete, onClearAll }) {
  return (
    <aside className="card h-100 conversation-list" aria-label="Conversations">
      <div className="card-header d-flex justify-content-between align-items-center">
        <strong>Conversations</strong>
        <button
          type="button"
          className="btn btn-sm btn-primary"
          onClick={onNew}
          disabled={busy}
          title="Start a conversation with no earlier context"
        >
          <BsPlusLg className="me-1" aria-hidden="true" />
          New
        </button>
      </div>

      <ul className="list-group list-group-flush conversation-scroll">
        {conversations.map((conversation) => {
          const active = conversation.id === activeId;
          const questions = conversation.turns.length;
          return (
            <li
              key={conversation.id}
              className={`list-group-item list-group-item-action d-flex align-items-start gap-2 ${active ? "active" : ""}`}
            >
              <button
                type="button"
                className="btn btn-link p-0 text-start text-reset text-decoration-none flex-grow-1 conversation-title"
                onClick={() => onSelect(conversation.id)}
                disabled={busy && !active}
                aria-current={active ? "true" : undefined}
              >
                <BsChatLeftText className="me-2 flex-shrink-0" aria-hidden="true" />
                <span>
                  {conversation.title}
                  <small className={`d-block ${active ? "" : "text-body-secondary"}`}>
                    {questions === 1 ? "1 question" : `${questions} questions`}
                  </small>
                </span>
              </button>
              <button
                type="button"
                className={`btn btn-sm p-1 ${active ? "text-white" : "text-body-secondary"}`}
                onClick={() => onDelete(conversation.id)}
                disabled={busy}
                aria-label={`Delete conversation: ${conversation.title}`}
                title="Delete conversation"
              >
                <BsTrash aria-hidden="true" />
              </button>
            </li>
          );
        })}
      </ul>

      <div className="card-footer">
        <button
          type="button"
          className="btn btn-sm btn-link text-danger p-0"
          onClick={onClearAll}
          disabled={busy}
        >
          Clear all conversations
        </button>
        <small className="d-block text-body-secondary mt-1">Saved in this browser only.</small>
      </div>
    </aside>
  );
}

export default ConversationList;
