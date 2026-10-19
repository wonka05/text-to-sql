import { describe, expect, it } from "vitest";
import { chartSpec, formatCell, formatDuration, isScalar } from "./results";

const col = (name, type) => ({ name, type });

describe("chartSpec", () => {
  it("charts a label column against a measure", () => {
    const result = {
      columns: [col("department_name", "text"), col("avg_salary", "number")],
      rows: [["Engineering", 120114.29], ["Sales", 69961.54]],
    };
    expect(chartSpec(result)).toEqual({ kind: "bar", labelIndex: 0, measureIndexes: [1] });
  });

  it("uses a line for time-like labels", () => {
    const result = {
      columns: [col("month", "text"), col("revenue", "number")],
      rows: [["2025-01", 1], ["2025-02", 2], ["2025-03", 3]],
    };
    expect(chartSpec(result).kind).toBe("line");
  });

  it("lets a whole-number first column label the rest (YEAR(...), COUNT(*))", () => {
    const result = {
      columns: [col("YEAR(order_date)", "number"), col("COUNT(*)", "number")],
      rows: [[2024, 105], [2025, 177], [2026, 275]],
    };
    expect(chartSpec(result)).toEqual({ kind: "line", labelIndex: 0, measureIndexes: [1] });
  });

  it("never charts id columns as measures", () => {
    const result = {
      columns: [col("customer_name", "text"), col("customer_id", "number"), col("total", "number")],
      rows: [["Ann", 1, 10], ["Bob", 2, 20]],
    };
    expect(chartSpec(result).measureIndexes).toEqual([2]);
  });

  it.each([
    ["a single row", { columns: [col("a", "text"), col("n", "number")], rows: [["x", 1]] }],
    ["no numbers", { columns: [col("a", "text"), col("b", "text")], rows: [["x", "y"], ["z", "w"]] }],
    ["repeated labels", { columns: [col("a", "text"), col("n", "number")], rows: [["x", 1], ["x", 2]] }],
    ["too many rows", { columns: [col("a", "text"), col("n", "number")], rows: Array.from({ length: 51 }, (_, i) => [`r${i}`, i]) }],
  ])("returns null for %s", (_, result) => {
    expect(chartSpec(result)).toBeNull();
  });
});

describe("isScalar", () => {
  it("is true for one column and one row", () => {
    expect(isScalar({ columns: [col("n", "number")], rows: [[23]] })).toBe(true);
    expect(isScalar({ columns: [col("n", "number")], rows: [[1], [2]] })).toBe(false);
  });
});

describe("formatCell", () => {
  it("formats numbers, but not ids and years", () => {
    expect(formatCell(1234567.891, col("total", "number"))).toBe((1234567.89).toLocaleString());
    expect(formatCell(2025, col("year", "number"))).toBe("2025");
    expect(formatCell(1042, col("order_id", "number"))).toBe("1042");
  });

  it("shows NULL for missing values", () => {
    expect(formatCell(null, col("a", "text"))).toBe("NULL");
  });
});

describe("formatDuration", () => {
  it("picks a readable unit", () => {
    expect(formatDuration(0.4)).toBe("<1 ms");
    expect(formatDuration(812.3)).toBe("812 ms");
    expect(formatDuration(2345)).toBe("2.3 s");
  });
});
