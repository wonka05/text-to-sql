from dataclasses import dataclass

from fastapi import Request

from app.core.errors import RateLimitedError
from app.services.catalog import CatalogProvider
from app.services.executor import QueryExecutor
from app.services.pipeline import QueryPipeline
from app.services.rate_limit import RateLimiter


@dataclass
class Services:
    """Everything the routes need, built once at startup (see app.main)."""

    pipeline: QueryPipeline
    catalog: CatalogProvider
    executor: QueryExecutor
    rate_limiter: RateLimiter


def get_services(request: Request) -> Services:
    return request.app.state.services


def enforce_rate_limit(request: Request) -> None:
    services: Services = request.app.state.services
    # Behind a proxy, run uvicorn with --proxy-headers so this is the real client
    client = request.client.host if request.client else "unknown"
    retry_after = services.rate_limiter.check(client)
    if retry_after is not None:
        raise RateLimitedError(
            f"Too many requests. Try again in {retry_after} seconds.",
            retry_after=retry_after,
        )
