"""MessageFlow API entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.ratelimit import limiter


def create_app() -> FastAPI:
    app = FastAPI(
        title="MessageFlow API",
        description="Bulk messaging campaign management (Phase 1: prepare, don't send).",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    app.state.limiter = limiter

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=429, content={"detail": "Too many requests. Please slow down."})

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "app": settings.APP_NAME}

    app.include_router(api_router, prefix=settings.API_PREFIX)

    return app


app = create_app()
