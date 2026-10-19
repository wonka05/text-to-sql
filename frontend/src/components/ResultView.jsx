import { lazy, Suspense, useState } from "react";
import Papa from "papaparse";
import { toast } from "react-toastify";
import { BsArrowClockwise, BsBarChart, BsDownload, BsTable } from "react-icons/bs";
import { chartSpec, formatCell, isScalar } from "../lib/results";
import ResultTable from "./ResultTable";

// Chart.js is loaded only when someone opens a chart
const ResultChart = lazy(() => import("./ResultChart"));

function exportCsv(result, filename) {
  const csv = Papa.unparse({ fields: result.columns.map((c) => c.name), data: result.rows });
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  toast.success("CSV downloaded");
}

function ResultView({ result, theme, busy, onRefresh }) {
  const spec = chartSpec(result);
  const [view, setView] = useState("table");
  const { rows, columns } = result;

  const refresh = onRefresh && (
    <button
      type="button"
      className="btn btn-sm btn-outline-secondary"
      onClick={onRefresh}
      disabled={busy}
      title="Run the same SQL again for fresh results (no AI call)"
    >
      <BsArrowClockwise className="me-1" aria-hidden="true" />
      Refresh
    </button>
  );

  if (rows.length === 0) {
    return (
      <div className="alert alert-secondary d-flex justify-content-between align-items-center gap-2 mb-3">
        <span>
          <strong>No rows.</strong> The query ran successfully and nothing in the database matched it.
        </span>
        {refresh}
      </div>
    );
  }

  if (isScalar(result)) {
    return (
      <div className="card stat-tile mb-3">
        <div className="card-body d-flex justify-content-between align-items-end gap-3">
          <div>
            <div className="text-body-secondary small">{columns[0].name}</div>
            <div className="stat-value">{formatCell(rows[0][0], columns[0])}</div>
          </div>
          {refresh}
        </div>
      </div>
    );
  }

  const shownView = spec ? view : "table";

  return (
    <section className="card mb-3" aria-label="Query results">
      <div className="card-header d-flex flex-wrap gap-2 justify-content-between align-items-center">
        <div className="d-flex align-items-center gap-2">
          <strong>Results</strong>
          <span className="text-body-secondary small">
            {result.truncated ? `first ${rows.length} rows` : `${rows.length} ${rows.length === 1 ? "row" : "rows"}`}
          </span>
        </div>
        <div className="d-flex flex-wrap gap-2">
          {spec && (
            <div className="btn-group btn-group-sm" role="group" aria-label="Result view">
              <button
                type="button"
                className={`btn ${shownView === "table" ? "btn-secondary" : "btn-outline-secondary"}`}
                onClick={() => setView("table")}
                aria-pressed={shownView === "table"}
              >
                <BsTable className="me-1" aria-hidden="true" />
                Table
              </button>
              <button
                type="button"
                className={`btn ${shownView === "chart" ? "btn-secondary" : "btn-outline-secondary"}`}
                onClick={() => setView("chart")}
                aria-pressed={shownView === "chart"}
              >
                <BsBarChart className="me-1" aria-hidden="true" />
                Chart
              </button>
            </div>
          )}
          {refresh}
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={() => exportCsv(result, "querent-results.csv")}
          >
            <BsDownload className="me-1" aria-hidden="true" />
            CSV
          </button>
        </div>
      </div>

      {result.truncated && (
        <div className="alert alert-warning rounded-0 border-0 border-bottom mb-0 small">
          The query matched more than {result.row_limit} rows, so only the first {result.row_limit} are
          shown. Add a filter or ask for a summary (e.g. counts per group) to see everything.
        </div>
      )}
      {result.stored_rows_trimmed && (
        <div className="alert alert-info rounded-0 border-0 border-bottom mb-0 small">
          Only the first {rows.length} rows were saved in this browser. Use Refresh to load all of them.
        </div>
      )}

      {shownView === "chart" ? (
        <div className="card-body">
          <Suspense fallback={<p className="text-body-secondary mb-0">Loading chart...</p>}>
            <ResultChart result={result} spec={spec} theme={theme} />
          </Suspense>
        </div>
      ) : (
        <ResultTable result={result} />
      )}
    </section>
  );
}

export default ResultView;
