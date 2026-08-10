from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from blackbox_api.api.routes_analytics import router as analytics_router
from blackbox_api.api.routes_health import router as health_router
from blackbox_api.api.routes_incidents import router as incidents_router
from blackbox_api.config import get_settings
from blackbox_api.logging import configure_logging, log
from blackbox_api.storage.db import init_db

logger = logging.getLogger("blackbox.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    init_db()
    log(logger, logging.INFO, "database initialized")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="BlackBox API",
        description="Flight recorder and incident reconstruction for "
        "autonomous robots.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(incidents_router)
    app.include_router(analytics_router)
    return app


app = create_app()
