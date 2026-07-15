import Papa from "papaparse";
import { toast } from "react-toastify";

import {
  BsDownload,
} from "react-icons/bs";

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

    toast.success("CSV exported successfully");
  };

  const keys = Object.keys(data[0]);

  let chart = null;

  if (keys.length === 2) {
    const first = data[0][keys[0]];
    const second = Number(data[0][keys[1]]);

    if (
      typeof first === "string" &&
      !isNaN(second)
    ) {
      chart = (
        <div className="chart-container">

          <Bar
            data={{
              labels: data.map((row) => row[keys[0]]),
              datasets: [
                {
                  label: keys[1],
                  data: data.map((row) =>
                    Number(row[keys[1]])
                  ),
                },
              ],
            }}
          />

        </div>
      );
    }
  }

  return (
    <div className="card shadow-sm">

      <div className="card-header d-flex justify-content-between align-items-center">

        <strong>Query Results</strong>

        <button
          className="btn btn-outline-success btn-sm"
          onClick={exportCSV}
        >
          <BsDownload className="me-1" />
          Export CSV
        </button>

      </div>

      <div className="card-body">

        <div className="table-responsive">

          <table className="table table-hover table-striped table-bordered">

            <thead className="table-dark">

              <tr>

                {keys.map((key) => (

                  <th key={key}>
                    {key}
                  </th>

                ))}

              </tr>

            </thead>

            <tbody>

              {data.map((row, i) => (

                <tr key={i}>

                  {Object.values(row).map((value, j) => (

                    <td key={j}>
                      {String(value)}
                    </td>

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