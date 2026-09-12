import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Same anchoring as extensions.sqlalchemy.init: the app is started from src/,
# the env files live at the repo root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(_PROJECT_ROOT / ".env", override=False)
if (_PROJECT_ROOT / ".env.local").exists():
    load_dotenv(_PROJECT_ROOT / ".env.local", override=True)

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from extensions.sqlalchemy import (
    DBSessionMiddleware,
    SessionLocal,
    auto_create_tables_enabled,
    init_db,
)
from project_helpers.exceptions import ErrorException
from project_helpers.functions import get_build_info, version_string
from project_helpers.responses import (
    error_exception_handler,
    http_exception_handler,
    sqlalchemy_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from modules import (
    auditRouter,
    authRouter,
    fieldRouter,
    matchRouter,
    playerRouter,
    seasonRouter,
    standingsRouter,
    statsRouter,
    teamRouter,
    userRouter,
)
from services.populate_defaults import populate_defaults


def _populate_defaults_for_checkout():
    """Apply the default rows when this process also owns the schema.

    In a container the `migrate` job (services.run_migrations) has already run
    them before this API was allowed to start, and startup stays read-only -
    which is what keeps two replicas from racing the same insert. Running from a
    checkout there is no such job, so do it here.
    """
    if not auto_create_tables_enabled():
        return

    session = SessionLocal()
    try:
        if populate_defaults(session) is False:
            logging.error("Some defaults did not apply - see the errors above")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    # First line in the logs says exactly which build is serving, which is what
    # makes a deployment marker useful when something goes wrong at 3pm.
    logging.info(
        "Starting SCC API %s (%s)",
        version_string(),
        os.getenv("APP_ENV", "local"),
    )
    init_db()
    _populate_defaults_for_checkout()
    yield


api = FastAPI(
    title="Students Community Championship API",
    version=str(get_build_info()["version"]),
    lifespan=lifespan,
    exception_handlers={
        ErrorException: error_exception_handler,
        HTTPException: http_exception_handler,
        RequestValidationError: validation_exception_handler,
        SQLAlchemyError: sqlalchemy_exception_handler,
        Exception: unhandled_exception_handler,
    },
)


def parse_allowed_origins():
    raw = os.getenv("ALLOWED_ORIGINS", "*")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


api.add_middleware(DBSessionMiddleware)
api.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.get("/health")
def health():
    """Liveness probe. Deliberately does not touch the database: a slow query
    must not make the orchestrator restart a healthy container."""
    return {"status": "ok"}


@api.get("/version")
def version():
    """What is actually running here. Used by deploy scripts and smoke tests."""
    return get_build_info()


for router in (
    authRouter,
    userRouter,
    seasonRouter,
    teamRouter,
    playerRouter,
    fieldRouter,
    matchRouter,
    standingsRouter,
    statsRouter,
    auditRouter,
):
    api.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.run_api:api",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
