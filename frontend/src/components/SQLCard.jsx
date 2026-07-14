import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

import {
  BsCodeSlash,
  BsClipboard,
  BsCheckCircle
} from "react-icons/bs";

function SQLCard({ sql, explanation }) {
  const copySQL = async () => {
    await navigator.clipboard.writeText(sql);
  };

  return (
    <>
      <div className="card shadow-sm border-0 mb-4">

        <div className="card-header bg-white d-flex justify-content-between align-items-center">

          <div className="d-flex align-items-center">

            <BsCodeSlash
              className="me-2"
              color="#2563EB"
            />

            <strong>Generated SQL</strong>

          </div>

          <button
            className="btn btn-outline-primary btn-sm"
            onClick={copySQL}
          >
            <BsClipboard className="me-1" />
            Copy SQL
          </button>

        </div>

        <SyntaxHighlighter
          language="sql"
          style={oneLight}
          customStyle={{
            margin: 0,
            borderRadius: 0,
            fontSize: "15px",
            padding: "20px",
          }}
        >
          {sql}
        </SyntaxHighlighter>

      </div>

      <div className="card shadow-sm border-0">

        <div className="card-header bg-white">

          <BsCheckCircle
            className="me-2"
            color="#2563EB"
          />

          <strong>SQL Explanation</strong>

        </div>

        <div className="card-body">

          {explanation}

        </div>

      </div>
    </>
  );
}

export default SQLCard;