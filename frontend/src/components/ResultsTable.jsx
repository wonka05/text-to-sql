import Papa from "papaparse";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

import { Bar } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

function ResultsTable({ data }) {
  if (data.length === 0) {
    return (
      <div className="alert alert-warning">
        No records found.
      </div>
    );
  }

  const exportCSV = () => {
    const csv = Papa.unparse(data);

    const blob = new Blob([csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");

    link.href = url;
    link.download = "query_results.csv";

    link.click();

    URL.revokeObjectURL(url);
  };

  // Detect if data has one text column + one numeric column
  const keys = Object.keys(data[0]);

  let chart = null;

  if (keys.length === 2) {
    const firstValue = data[0][keys[0]];
    const secondValue = data[0][keys[1]];

    if (
      typeof firstValue === "string" &&
      typeof secondValue === "number"
    ) {
      chart = (
        <div className="mt-4">
          <Bar
            data={{
              labels: data.map((row) => row[keys[0]]),
              datasets: [
                {
                  label: keys[1],
                  data: data.map((row) => row[keys[1]]),
                },
              ],
            }}
          />
        </div>
      );
    }
  }

  return (
    <div className="card">

      <div className="card-header bg-success text-white d-flex justify-content-between">

        <span>Query Results</span>

        <button
          className="btn btn-light btn-sm"
          onClick={exportCSV}
        >
          📥 Export CSV
        </button>

      </div>

      <div className="card-body">

        <div className="table-responsive">

          <table className="table table-striped table-hover table-bordered">

            <thead className="table-dark">

              <tr>
                {keys.map((key) => (
                  <th key={key}>{key}</th>
                ))}
              </tr>

            </thead>

            <tbody>

              {data.map((row, i) => (
                <tr key={i}>
                  {Object.values(row).map((value, j) => (
                    <td key={j}>{String(value)}</td>
                  ))}
                </tr>
              ))}

            </tbody>

          </table>

        </div>

        {chart}

      </div>

    </div>
  );
}

export default ResultsTable;