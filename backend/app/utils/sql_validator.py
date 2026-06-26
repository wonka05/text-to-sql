FORBIDDEN = [
    "DELETE",
    "DROP",
    "UPDATE",
    "INSERT",
    "ALTER",
    "TRUNCATE",
    "CREATE"
]


def validate_sql(sql: str):
    sql_upper = sql.upper()

    if not sql_upper.strip().startswith("SELECT"):
        return False

    for keyword in FORBIDDEN:
        if keyword in sql_upper:
            return False

    return True