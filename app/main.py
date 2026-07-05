from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.metrics import router as metrics_router
from app.api.projects import router as projects_router
from app.api.queues import router as queues_router
from app.api.workers import router as workers_router
from app.config import settings
from app.core.errors import AppError, app_error_handler, unhandled_error_handler
from app.core.logging import correlation_id_middleware, setup_logging

setup_logging(settings.log_level)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Distributed Job Scheduler",
        description="A production-inspired platform for reliable background job execution.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.environment == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(correlation_id_middleware)

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(projects_router)
    app.include_router(queues_router)
    app.include_router(jobs_router)
    app.include_router(metrics_router)
    app.include_router(workers_router)

    return app


app = create_app()
