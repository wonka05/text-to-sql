// Decisions about how to present a result set: as a single number, a chart,
// or only a table. Pure functions, so they are unit tested.

const ID_LIKE = /(^id$|_id$)/i;
const TIME_LIKE = /(year|month|date|day|week|quarter|period)/i;
const MAX_CHART_ROWS = 50;

// A single value ("How many customers live in Pune?") reads best as one big number
export function isScalar(result) {
  return result?.columns.length === 1 && result.rows.length === 1;
}

function isNumberColumn(column) {
  return column.type === "number";
}

function isIntegerColumn(result, index) {
  return result.rows.every((row) => Number.isInteger(row[index]));
}

function allUnique(values) {
  return new Set(values.map(String)).size === values.length;
}

// Returns null when a chart would not help, otherwise
// { kind: "bar" | "line", labelIndex, measureIndexes }.
// The UI charts one measure at a time: plotting columns of different scales
// on one axis would mislead.
export function chartSpec(result) {
  if (!result || result.rows.length < 2 || result.rows.length > MAX_CHART_ROWS) return null;
  const { columns } = result;

  let labelIndex = columns.findIndex((c) => ["text", "date", "datetime"].includes(c.type));
  if (labelIndex === -1) {
    // e.g. SELECT YEAR(order_date), COUNT(*): a whole-number first column can label the rest
    const numeric = columns.filter(isNumberColumn).length;
    if (numeric >= 2 && isNumberColumn(columns[0]) && isIntegerColumn(result, 0)) labelIndex = 0;
  }
  if (labelIndex === -1) return null;

  const labels = result.rows.map((row) => row[labelIndex]);
  if (!allUnique(labels)) return null;

  const measureIndexes = columns
    .map((column, index) => ({ column, index }))
    .filter(({ column, index }) => index !== labelIndex && isNumberColumn(column) && !ID_LIKE.test(column.name))
    .map(({ index }) => index);
  if (measureIndexes.length === 0) return null;

  const label = columns[labelIndex];
  const timeLike = ["date", "datetime"].includes(label.type) || TIME_LIKE.test(label.name);
  return { kind: timeLike && result.rows.length >= 3 ? "line" : "bar", labelIndex, measureIndexes };
}

// Ids and years read wrong with thousands separators ("2,025")
function plainNumber(columnName) {
  return ID_LIKE.test(columnName) || TIME_LIKE.test(columnName);
}

export function formatCell(value, column) {
  if (value === null || value === undefined) return "NULL";
  if (typeof value === "number") {
    if (plainNumber(column?.name || "") && Number.isInteger(value)) return String(value);
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

export function formatDuration(ms) {
  if (ms === null || ms === undefined) return "-";
  if (ms < 1) return "<1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}
