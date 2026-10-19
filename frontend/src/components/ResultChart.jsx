import { useState } from "react";
import {
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";
import { formatCell } from "../lib/results";

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, Tooltip);

// One series at a time, in the first categorical slot, stepped per theme.
// Text and grid use neutral ink, never the series color.
const COLORS = {
  light: { series: "#2a78d6", text: "#52514e", grid: "rgba(0, 0, 0, 0.08)", surface: "#ffffff" },
  dark: { series: "#3987e5", text: "#c3c2b7", grid: "rgba(255, 255, 255, 0.10)", surface: "#212529" },
};

function ResultChart({ result, spec, theme }) {
  const [measure, setMeasure] = useState(spec.measureIndexes[0]);
  const colors = COLORS[theme] || COLORS.light;
  const labelColumn = result.columns[spec.labelIndex];
  const measureColumn = result.columns[measure];

  const data = {
    labels: result.rows.map((row) => formatCell(row[spec.labelIndex], labelColumn)),
    datasets: [
      {
        label: measureColumn.name,
        data: result.rows.map((row) => row[measure]),
        backgroundColor: colors.series,
        borderColor: colors.series,
        // Bars: rounded data end, square at the baseline. Lines: 2px with 8px markers
        borderRadius: spec.kind === "bar" ? 4 : 0,
        borderSkipped: "start",
        maxBarThickness: 48,
        borderWidth: spec.kind === "line" ? 2 : 0,
        pointRadius: spec.kind === "line" ? 4 : 0,
        pointHoverRadius: 6,
        pointBackgroundColor: colors.series,
        pointBorderColor: colors.surface,
        pointBorderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context) => `${measureColumn.name}: ${formatCell(context.parsed.y, measureColumn)}`,
        },
      },
    },
    scales: {
      x: { ticks: { color: colors.text, maxRotation: 45, autoSkip: true }, grid: { display: false } },
      y: {
        beginAtZero: spec.kind === "bar",
        ticks: { color: colors.text },
        grid: { color: colors.grid },
        border: { display: false },
      },
    },
  };

  const Chart = spec.kind === "line" ? Line : Bar;
  const describe = `${spec.kind === "line" ? "Line" : "Bar"} chart of ${measureColumn.name} by ${labelColumn.name}`;

  return (
    <figure className="mb-0">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
        <figcaption className="fw-semibold me-auto">
          {measureColumn.name} <span className="text-body-secondary fw-normal">by {labelColumn.name}</span>
        </figcaption>
        {spec.measureIndexes.length > 1 && (
          <label className="d-flex align-items-center gap-2 small">
            Measure
            <select
              className="form-select form-select-sm w-auto"
              value={measure}
              onChange={(e) => setMeasure(Number(e.target.value))}
            >
              {spec.measureIndexes.map((index) => (
                <option key={index} value={index}>
                  {result.columns[index].name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="chart-box" role="img" aria-label={describe}>
        <Chart data={data} options={options} />
      </div>
    </figure>
  );
}

export default ResultChart;
