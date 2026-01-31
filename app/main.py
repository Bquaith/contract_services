from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.errors import error_payload, register_exception_handlers
from app.api.metrics import record_http_request
from app.api.routers import contracts_router, publish_router, system_router, validation_router
from app.config import get_settings
from app.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def api_key_guard(request: Request, call_next):  # type: ignore[no-redef]
        if request.method != "GET":
            provided = request.headers.get("X-API-Key")
            if provided != settings.api_key:
                response = JSONResponse(
                    status_code=401,
                    content=error_payload(
                        code="unauthorized",
                        message="Invalid or missing X-API-Key",
                        details={"header": "X-API-Key"},
                    ),
                )
                record_http_request(request.method, request.url.path, response.status_code)
                return response

        response = await call_next(request)
        record_http_request(request.method, request.url.path, response.status_code)
        return response

    app.include_router(system_router)
    app.include_router(validation_router)
    app.include_router(contracts_router)
    app.include_router(publish_router)

    return app


app = create_app()
