from fastapi import FastAPI, Request

from app.api.errors import register_exception_handlers
from app.api.metrics import record_http_request
from app.api.routers import (
    contracts_router,
    introspection_router,
    publish_router,
    system_router,
    validation_router,
)
from app.auth import build_swagger_init_oauth, configure_swagger_oidc
from app.config import get_settings
from app.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    configure_swagger_oidc(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_init_oauth=build_swagger_init_oauth(settings) if settings.auth_enabled else None,
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):  # type: ignore[no-redef]
        response = await call_next(request)
        record_http_request(request.method, request.url.path, response.status_code)
        return response

    app.include_router(system_router)
    app.include_router(validation_router)
    app.include_router(introspection_router)
    app.include_router(contracts_router)
    app.include_router(publish_router)

    return app


app = create_app()
