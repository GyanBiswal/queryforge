from fastapi import FastAPI
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import init_db
from app.api import documents

configure_logging()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Enterprise Knowledge Assistant — RAG platform for internal document Q&A",
        version="0.1.0",
    )

    init_db()

    @app.get("/health", tags=["system"])
    def health_check() -> dict:
        return {"status": "ok", "app": settings.app_name, "environment": settings.environment}

    app.include_router(documents.router)

    return app


app = create_app()