"""Decide whether a predicted result set answers the question like the gold one.

Comparing SQL text is useless (many queries are equivalent), so results are
compared instead, with some tolerance for presentation choices that do not
change the answer:

- Extra columns in the prediction are fine (e.g. it also returned an id).
- Column names and order don't matter; each gold column just has to appear.
- Numbers match within 0.01 (rounding differences).
- Text matches case-insensitively, and a gold value may be part of a
  predicted one, so first_name + last_name match CONCAT(first_name, ' ', last_name).
- Row order only matters when the item says so ("cheapest to most expensive").

The row count must match exactly: returning 6 rows for "top 5" is wrong.
"""
import itertools
from collections import Counter
from decimal import Decimal

MAX_MAPPINGS = 256


def normalize(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, Decimal)):
        return round(float(value), 2)
    return str(value).strip().lower()


def cell_match(gold, pred) -> bool:
    if gold is None or pred is None:
        return gold is None and pred is None
    if isinstance(gold, float) and isinstance(pred, float):
        return abs(gold - pred) <= max(0.01, abs(gold) * 1e-9)
    if isinstance(gold, str) and isinstance(pred, str):
        return gold == pred or (len(gold) >= 2 and gold in pred)
    # A year from YEAR() vs '2025' from DATE_FORMAT
    number, text = (gold, pred) if isinstance(gold, float) else (pred, gold)
    if isinstance(number, float) and number.is_integer():
        return str(int(number)) == text
    return False


def _pair_all(golds, preds, match) -> bool:
    """Greedily pair every gold item with a distinct matching predicted item."""
    used = [False] * len(preds)
    for gold in golds:
        for i, pred in enumerate(preds):
            if not used[i] and match(gold, pred):
                used[i] = True
                break
        else:
            return False
    return True


def _column_compatible(gold_values, pred_values) -> bool:
    if Counter(gold_values) == Counter(pred_values):
        return True
    return _pair_all(gold_values, pred_values, cell_match)


def results_match(
    gold_columns: list[str],
    gold_rows: list[list],
    pred_rows: list[list],
    order_matters: bool = False,
) -> tuple[bool, str]:
    if len(gold_rows) != len(pred_rows):
        return False, f"expected {len(gold_rows)} rows, got {len(pred_rows)}"
    if not gold_rows:
        return True, "both empty"

    gold = [[normalize(v) for v in row] for row in gold_rows]
    pred = [[normalize(v) for v in row] for row in pred_rows]
    pred_width = len(pred[0])

    candidates = []
    for j, name in enumerate(gold_columns):
        gold_values = [row[j] for row in gold]
        matches = [
            k for k in range(pred_width)
            if _column_compatible(gold_values, [row[k] for row in pred])
        ]
        if not matches:
            return False, f"no predicted column matches gold column '{name}'"
        candidates.append(matches)

    for mapping in itertools.islice(itertools.product(*candidates), MAX_MAPPINGS):
        def row_match(gold_row, pred_row, mapping=mapping):
            return all(cell_match(gold_row[j], pred_row[k]) for j, k in enumerate(mapping))

        if order_matters:
            if all(row_match(g, p) for g, p in zip(gold, pred, strict=True)):
                return True, "match (ordered)"
        elif _pair_all(gold, pred, row_match):
            return True, "match"
    return False, "values or row order differ" if order_matters else "values differ"
