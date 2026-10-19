"""Errors that end a request with a non-200 response.

Everything that goes wrong *with a generated query* (rejected by the guard,
failed in the database) is not an exception at the API level: the pipeline
turns it into a normal response with status "rejected" or "failed". The
exceptions here are for problems the user cannot fix by rephrasing: a
dependency is down, the request is malformed, or the client is rate limited.
"""


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ModelUnavailableError(AppError):
    status_code = 502
    code = "model_unavailable"


class ModelOutputError(AppError):
    """The model replied, but not with the JSON we asked for."""

    status_code = 502
    code = "model_output_invalid"


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after
