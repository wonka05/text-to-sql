import { toast } from "react-toastify";

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

import {
  BsCodeSlash,
  BsClipboard,
  BsInfoCircle,
} from "react-icons/bs";

function SQLCard({ sql, explanation }) {
  const copySQL = async () => {
    await navigator.clipboard.writeText(sql);
    toast.success("SQL copied successfully");
  };

  return (
    <>
      <div className="card shadow-sm mb-4">

        <div className="card-header d-flex justify-content-between align-items-center">

          <div className="d-flex align-items-center">

            <BsCodeSlash className="me-2 text-primary" />

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
            padding: "20px",
            borderRadius: 0,
            fontSize: "15px",
          }}
        >
          {sql}
        </SyntaxHighlighter>

      </div>

      <div className="card shadow-sm mb-4">

        <div className="card-header">

          <BsInfoCircle className="me-2 text-primary" />

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