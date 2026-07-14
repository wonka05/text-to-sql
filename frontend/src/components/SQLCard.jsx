function SQLCard({ sql, explanation }) {
  const copySQL = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      alert("SQL copied successfully!");
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <>
      <div className="card mb-3">
        <div className="card-header bg-dark text-white d-flex justify-content-between align-items-center">
          <span>Generated SQL</span>

          <button
            className="btn btn-outline-light btn-sm"
            onClick={copySQL}
          >
            📋 Copy
          </button>
        </div>

        <div className="card-body">
          <pre>{sql}</pre>
        </div>
      </div>

      <div className="card mb-3">
        <div className="card-header bg-info text-white">
          SQL Explanation
        </div>

        <div className="card-body">
          {explanation}
        </div>
      </div>
    </>
  );
}

export default SQLCard;