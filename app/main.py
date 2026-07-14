from fastapi import FastAPI
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.database import init_db
from app.api import documents
from app.api import documents, query
from app.api import documents, query, conversations
import os

configure_logging()
print("SERVER CWD:", os.getcwd())
print("SERVER DB ABS PATH:", os.path.abspath("queryforge.db"))

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
    app.include_router(query.router)
    app.include_router(conversations.router)

    return app


app = create_app()