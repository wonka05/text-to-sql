import logging
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import Services
from app.api.query import router as query_router
from app.api.schema import router as schema_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError, RateLimitedError
from app.database.connection import create_query_engine
from app.schemas.query import MAX_HISTORY_TURNS
from app.services.catalog import CatalogProvider, load_catalog
from app.services.executor import QueryExecutor
from app.services.llm import GeminiClient
from app.services.pipeline import QueryPipeline, ReplyCache
from app.services.rate_limit import RateLimiter

logger = logging.getLogger("app")

MAX_BODY_BYTES = 64 * 1024


def build_services(settings: Settings) -> tuple[Services, Callable[[], None]]:
    """Wire up the real database, model and pipeline. Returns a cleanup function."""
    engine = create_query_engine(settings)
    restricted = settings.restricted_column_set
    catalog = CatalogProvider(
        lambda: load_catalog(engine, settings.db_name, restricted),
        ttl_seconds=settings.schema_cache_seconds,
    )
    executor = QueryExecutor(engine, settings.max_result_rows, settings.query_timeout_seconds)
    llm = GeminiClient(
        settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout_seconds
    )
    pipeline = QueryPipeline(
        llm=llm,
        catalog=catalog,
        executor=executor,
        max_rows=settings.max_result_rows,
        restricted_columns=restricted,
        max_repair_attempts=settings.max_repair_attempts,
        max_history_turns=MAX_HISTORY_TURNS,
        cache=ReplyCache(settings.generation_cache_size),
    )
    services = Services(
        pipeline=pipeline,
        catalog=catalog,
        executor=executor,
        rate_limiter=RateLimiter(settings.rate_limit_per_minute),
    )
    return services, engine.dispose


def _error(status_code: int, code: str, message: str, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    """Build the API. Tests pass their own `services` (fake model, test database)."""
    settings = settings or get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cleanup = None
        if services is None:
            app.state.services, cleanup = build_services(settings)
        else:
            app.state.services = services
        yield
        if cleanup:
            cleanup()

    app = FastAPI(title="Querent", version="2.0.0", lifespan=lifespan)

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError):
        headers = None
        if isinstance(exc, RateLimitedError):
            headers = {"Retry-After": str(exc.retry_after)}
        return _error(exc.status_code, exc.code, exc.message, headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = first.get("msg", "Invalid request")
        return _error(422, "invalid_request", f"{field}: {message}" if field else message)

    # Registered before CORS so that it runs inside it: unexpected errors
    # become JSON 500s that still carry CORS headers, instead of an opaque
    # network error in the browser
    @app.middleware("http")
    async def catch_unexpected_errors(request: Request, call_next):
        # The largest valid request (question + history) is ~30 KB. Refuse
        # bigger bodies before they are read into memory.
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > MAX_BODY_BYTES:
            return _error(413, "request_too_large", "The request is too large.")
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Unhandled error on %s %s", request.method, request.url.path)
            return _error(500, "internal_error", "Something went wrong on the server.")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    app.include_router(query_router)
    app.include_router(schema_router)

    @app.get("/")
    def home():
        return {"message": "Welcome to Querent", "docs": "/docs"}

    return app


app = create_app()
