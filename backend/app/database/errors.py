"""Helpers for reading MySQL error codes out of SQLAlchemy exceptions."""
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError

# The server is unreachable, refused the login, or dropped the connection
CONNECTION_ERROR_CODES = frozenset({
    1040,  # too many connections
    1045,  # access denied (wrong user or password)
    1049,  # unknown database
    2003,  # can't connect
    2005,  # unknown host
    2006,  # server has gone away
    2013,  # lost connection during query
})

QUERY_TIMEOUT = 3024  # max_execution_time exceeded
PERMISSION_ERROR_CODES = frozenset({1044, 1142, 1143, 1227})
# The query names a table or column that does not exist
UNKNOWN_OBJECT_CODES = frozenset({1054, 1146})


def mysql_error_code(exc: BaseException) -> int | None:
    if isinstance(exc, DBAPIError) and exc.orig is not None and exc.orig.args:
        code = exc.orig.args[0]
        if isinstance(code, int):
            return code
    return None


def mysql_error_message(exc: BaseException) -> str:
    if isinstance(exc, DBAPIError) and exc.orig is not None and len(exc.orig.args) > 1:
        return str(exc.orig.args[1])
    return str(exc)


def describe(exc: BaseException) -> str:
    """One line for the server log: the MySQL code and message, without the SQL."""
    code = mysql_error_code(exc)
    if code is not None:
        return f"MySQL error {code}: {mysql_error_message(exc)}"
    return f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"


def is_connection_error(exc: BaseException) -> bool:
    if isinstance(exc, PoolTimeoutError):
        return True
    code = mysql_error_code(exc)
    if code is not None:
        return code in CONNECTION_ERROR_CODES
    # Errors raised before the server replied (e.g. a closed socket) carry no code
    return isinstance(exc, (OperationalError, InterfaceError))
