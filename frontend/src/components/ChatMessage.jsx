function ChatMessage({ question }) {
  return (
    <div className="alert alert-primary">
      <strong>👤 You</strong>
      <br />
      {question}
    </div>
  );
}

export default ChatMessage;