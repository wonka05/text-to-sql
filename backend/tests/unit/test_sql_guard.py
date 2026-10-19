import pytest

from app.services.sql_guard import GuardPolicy, QueryRejected, check_query
from tests.conftest import make_catalog


def policy(restricted=frozenset(), max_rows=500):
    catalog = make_catalog(restricted)
    return GuardPolicy(
        database=catalog.database,
        schema=catalog.guard_schema(),
        restricted_columns=restricted,
        max_rows=max_rows,
    )


def rejected(sql, **kwargs) -> QueryRejected:
    with pytest.raises(QueryRejected) as info:
        check_query(sql, policy(**kwargs))
    return info.value


@pytest.mark.parametrize("sql", [
    "SELECT first_name, salary FROM employees",
    # Identifiers and string literals that contain SQL keywords are fine;
    # the old keyword blocklist rejected these
    "SELECT order_id AS created_at FROM orders",
    "SELECT first_name FROM employees WHERE last_name = 'DROP TABLE orders'",
    # Joins, aggregates, grouping, CTEs, unions, subqueries, window functions
    "SELECT d.department_name, AVG(e.salary) AS avg_salary FROM employees e "
    "JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_name "
    "HAVING AVG(e.salary) > 50000 ORDER BY avg_salary DESC",
    "WITH totals AS (SELECT department_id, COUNT(*) AS n FROM employees GROUP BY department_id) "
    "SELECT d.department_name, t.n FROM totals t JOIN departments d ON d.department_id = t.department_id",
    "SELECT first_name FROM employees UNION ALL SELECT department_name FROM departments",
    "SELECT e.first_name FROM employees e WHERE e.salary > "
    "(SELECT AVG(e2.salary) FROM employees e2 WHERE e2.department_id = e.department_id)",
    "SELECT first_name, RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) AS r FROM employees",
    "SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, SUM(total_amount) FROM orders GROUP BY month",
    "SELECT COUNT(*) FROM orders WHERE order_date >= CURDATE() - INTERVAL 30 DAY",
    "SELECT * FROM employees e WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id = e.employee_id)",
    # MySQL column and table names are case-insensitive
    "select First_Name from Employees",
    # The configured database may be named explicitly
    "SELECT first_name FROM shop.employees",
    "SELECT 1 + 1",
    "(SELECT first_name FROM employees)",
])
def test_allows_read_only_queries(sql):
    result = check_query(sql, policy())
    assert result.sql


@pytest.mark.parametrize("sql, reason, repairable", [
    ("DELETE FROM employees", "not_select", False),
    ("UPDATE employees SET salary = 0", "not_select", False),
    ("INSERT INTO orders VALUES (1, '2024-01-01', 5)", "not_select", False),
    ("DROP TABLE employees", "not_select", False),
    ("TRUNCATE TABLE orders", "not_select", False),
    ("CREATE TABLE x (a INT)", "not_select", False),
    ("SHOW TABLES", "not_select", False),
    ("SET @a = 1", "not_select", False),
    ("SELECT 1; DROP TABLE employees", "multiple_statements", True),
    ("SELECT first_name FROM employees; SELECT 2", "multiple_statements", True),
    ("SELECT * INTO @v FROM employees", "forbidden_syntax", True),
    ("SELECT first_name FROM employees FOR UPDATE", "forbidden_syntax", True),
    ("SELECT first_name FROM employees LOCK IN SHARE MODE", "forbidden_syntax", True),
    ("SELECT /*+ MAX_EXECUTION_TIME(100000) */ first_name FROM employees", "forbidden_syntax", True),
    ("SELECT @@datadir", "forbidden_syntax", True),
    ("SELECT @secret", "forbidden_syntax", True),
    ("SELECT first_name FROM employees WHERE employee_id = ?", "forbidden_syntax", True),
    ("SELECT 1 /*!50000 , SLEEP(5) */", "executable_comment", True),
    ("SELECT SLEEP(100)", "forbidden_function", True),
    ("SELECT BENCHMARK(100000000, MD5('a'))", "forbidden_function", True),
    ("SELECT GET_LOCK('x', 10)", "forbidden_function", True),
    ("SELECT LOAD_FILE('/etc/passwd')", "forbidden_function", True),
    ("SELECT USER()", "forbidden_function", True),
    ("SELECT CURRENT_USER()", "forbidden_function", True),
    ("SELECT VERSION()", "forbidden_function", True),
    ("SELECT DATABASE()", "forbidden_function", True),
    ("SELECT * FROM information_schema.tables", "other_schema", True),
    ("SELECT * FROM mysql.user", "other_schema", True),
    ("SELECT * FROM other_db.employees", "other_schema", True),
    ("SELECT * FROM salaries", "unknown_table", True),
    ("SELECT nickname FROM employees", "unknown_column", True),
    ("SELECT e.first_name, d.budget FROM employees e JOIN departments d "
     "ON e.department_id = d.department_id", "unknown_column", True),
    # Ambiguous in MySQL too: both tables have department_id
    ("SELECT department_id FROM employees, departments", "unknown_column", True),
    ("SELECT * FROM JSON_TABLE('[1]', '$[*]' COLUMNS (a INT PATH '$')) AS jt", "table_function", True),
    ("SELECT * FROM employees INTO OUTFILE '/tmp/out.txt'", "parse_error", True),
    ("", "empty", True),
])
def test_rejects(sql, reason, repairable):
    error = rejected(sql)
    assert error.reason == reason
    assert error.repairable is repairable


@pytest.mark.parametrize("sql", [
    "SELECT SlEeP(1)",
    "SELECT `sleep`(1)",
    "SELECT sleep (1)",
    "SELECT shop.sleep(1)",
    "SELECT mysql.sleep(1)",
    "SELECT first_name FROM employees WHERE 1 = 1 AND SLEEP(1)",
    "SELECT first_name FROM employees ORDER BY SLEEP(1)",
    "SELECT (SELECT SLEEP(1))",
    "SELECT CONVERT(LOAD_FILE('x') USING utf8)",
])
def test_forbidden_functions_cannot_be_disguised(sql):
    assert rejected(sql).reason == "forbidden_function"


def test_unknown_table_message_lists_real_tables():
    assert "departments, employees, orders" in rejected("SELECT * FROM staff").message


def test_cte_names_are_not_mistaken_for_unknown_tables():
    check_query("WITH staff AS (SELECT first_name FROM employees) SELECT * FROM staff", policy())


def test_cte_cannot_hide_a_system_table():
    error = rejected("WITH t AS (SELECT * FROM mysql.user) SELECT * FROM t")
    assert error.reason == "other_schema"


class TestRestrictedColumns:
    restricted = frozenset({("employees", "email")})

    @pytest.mark.parametrize("sql", [
        "SELECT email FROM employees",
        "SELECT e.EMAIL FROM employees e",
        "SELECT * FROM employees",
        "SELECT e.* FROM employees e",
        "SELECT x.m FROM (SELECT email AS m FROM employees) x",
        "WITH c AS (SELECT email FROM employees) SELECT * FROM c",
        "SELECT first_name FROM employees WHERE email LIKE '%@example.com'",
        "SELECT COUNT(DISTINCT email) FROM employees",
    ])
    def test_rejected_however_referenced(self, sql):
        assert rejected(sql, restricted=self.restricted).reason == "restricted_column"

    def test_other_columns_of_the_table_are_fine(self):
        check_query("SELECT first_name, salary FROM employees", policy(self.restricted))


class TestRowCap:
    def test_adds_limit_with_one_extra_row(self):
        assert check_query("SELECT first_name FROM employees", policy()).sql.endswith("LIMIT 501")

    def test_keeps_a_smaller_limit(self):
        result = check_query("SELECT first_name FROM employees ORDER BY salary DESC LIMIT 5", policy())
        assert result.sql.endswith("LIMIT 5")
        assert not result.limit_applied

    def test_lowers_a_larger_limit_and_keeps_offset(self):
        result = check_query("SELECT first_name FROM employees LIMIT 10, 100000", policy())
        assert "LIMIT 501 OFFSET 10" in " ".join(result.sql.split())
        assert result.limit_applied

    def test_caps_the_whole_union(self):
        sql = "SELECT first_name FROM employees UNION SELECT department_name FROM departments"
        executed = " ".join(check_query(sql, policy(max_rows=50)).sql.split())
        assert executed.endswith("UNION SELECT department_name FROM departments LIMIT 51")


class TestExecutedSql:
    def test_comments_are_removed(self):
        result = check_query("SELECT first_name /* note */ FROM employees -- trailing", policy())
        assert "note" not in result.sql and "trailing" not in result.sql

    def test_trailing_semicolon_is_accepted(self):
        assert check_query("SELECT first_name FROM employees;", policy()).sql.startswith("SELECT")

    def test_reports_tables_used(self):
        sql = ("SELECT e.first_name, d.department_name FROM employees e "
               "JOIN departments d ON e.department_id = d.department_id")
        assert check_query(sql, policy()).tables == ("departments", "employees")
