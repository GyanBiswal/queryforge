from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.core.errors import http_exception_handler, unhandled_exception_handler
from app.db.database import init_db
from app.api import documents, query, conversations, admin
from slowapi.middleware import SlowAPIMiddleware

from app.core.seed import seed_demo_document
from app.db.database import SessionLocal

configure_logging()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Enterprise Knowledge Assistant — RAG platform for internal document Q&A",
        version="0.1.0",
    )

    app.state.limiter = limiter
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    init_db()

    db = SessionLocal()
    try:
        seed_demo_document(db)
    finally:
        db.close()

    @app.get("/health", tags=["system"])
    def health_check() -> dict:
        return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

    app.include_router(documents.router)
    app.include_router(query.router)
    app.include_router(conversations.router)
    app.include_router(admin.router)

    return app


app = create_app()