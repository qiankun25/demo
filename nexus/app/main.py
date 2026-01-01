from app.core.paths import ensure_contracts_on_path

ensure_contracts_on_path()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.lifecycle import create_start_app_handler, create_stop_app_handler  # noqa: E402
from app.api.routes import router as api_router  # noqa: E402
from app.infrastructure.metrics import metrics_router  # noqa: E402

def get_application() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="Nexus Orchestration Service",
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Lifecycle
    app.add_event_handler("startup", create_start_app_handler(app))
    app.add_event_handler("shutdown", create_stop_app_handler(app))
    
    # Routes
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(metrics_router)
    
    return app

app = get_application()
