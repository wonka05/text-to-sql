import { formatCell } from "../lib/results";

function ResultTable({ result }) {
  const { columns, rows } = result;
  return (
    <div className="table-responsive result-table">
      <table className="table table-sm table-striped table-hover align-middle mb-0">
        <thead>
          <tr>
            {columns.map((column, i) => (
              <th key={i} scope="col" className={column.type === "number" ? "text-end" : undefined}>
                {column.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((value, c) => (
                <td
                  key={c}
                  className={[
                    columns[c]?.type === "number" ? "text-end font-monospace" : "",
                    value === null ? "text-body-secondary fst-italic" : "",
                  ].join(" ")}
                >
                  {formatCell(value, columns[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default ResultTable;
