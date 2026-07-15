import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Standardizes every error response into one consistent shape, regardless
    of which endpoint or exception type raised it. Client code (or a
    frontend) can rely on `error.message` and `error.status` always existing,
    rather than each endpoint having a slightly different error JSON shape.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "status": exc.status_code,
                "message": exc.detail,
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches anything that isn't an HTTPException — last line of defense
    against leaking raw Python tracebacks to API clients."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "status": 500,
                "message": "An unexpected error occurred. Please try again.",
            }
        },
    )