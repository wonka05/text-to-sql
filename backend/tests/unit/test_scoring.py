from evals.scoring import results_match


def match(gold_cols, gold, pred, ordered=False):
    return results_match(gold_cols, gold, pred, order_matters=ordered)[0]


def test_identical_results_match():
    assert match(["name", "n"], [["a", 1], ["b", 2]], [["a", 1], ["b", 2]])


def test_row_order_is_ignored_unless_it_matters():
    gold, pred = [["a"], ["b"]], [["b"], ["a"]]
    assert match(["name"], gold, pred)
    assert not match(["name"], gold, pred, ordered=True)


def test_extra_and_reordered_columns_are_fine():
    assert match(["name", "total"], [["Ann", 10.0]], [[7, 10.004, "Ann"]])


def test_concatenated_names_match_separate_columns():
    gold = [["Ishwar", "Yadav"]]
    assert match(["first_name", "last_name"], gold, [["Ishwar Yadav", 177000]])


def test_year_number_matches_year_text():
    assert match(["y", "n"], [[2025, 3]], [["2025", 3]])


def test_wrong_row_count_fails():
    ok, detail = results_match(["name"], [["a"], ["b"]], [["a"]])
    assert not ok and "expected 2 rows" in detail


def test_wrong_values_fail():
    assert not match(["n"], [[23]], [[24]])
    assert not match(["city"], [["Pune"]], [["Mumbai"]])


def test_values_must_line_up_in_the_same_rows():
    # Each column alone matches, but the pairs are swapped
    gold = [["Engineering", 35], ["Sales", 13]]
    pred = [["Engineering", 13], ["Sales", 35]]
    assert not match(["dept", "n"], gold, pred)


def test_missing_gold_column_fails():
    ok, detail = results_match(["name", "salary"], [["Ann", 50000]], [["Ann"]])
    assert not ok and "salary" in detail


def test_empty_results_match():
    assert match(["name"], [], [])


def test_rounding_tolerance():
    assert match(["avg"], [[120114.29]], [[120114.2857]])
    assert not match(["avg"], [[120114.29]], [[120114.35]])
