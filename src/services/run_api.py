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

from extensions.sqlalchemy import DBSessionMiddleware, SessionLocal, init_db
from project_helpers.exceptions import ErrorException
from project_helpers.responses import (
    error_exception_handler,
    http_exception_handler,
    sqlalchemy_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from constants import PlatformRoles
from modules import (
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
from modules.auth.models import UserModel


def _ensure_default_admin():
    """Seed the first super-admin so a fresh database is usable.

    The first account is a SUPER_ADMIN because it is the only role that can
    reopen a confirmed match, and it is the account that creates the operator
    accounts for match day.
    """
    email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@scc.ro")
    password = os.getenv("DEFAULT_ADMIN_PASSWORD")
    name = os.getenv("DEFAULT_ADMIN_NAME", "Administrator")

    db = SessionLocal()
    try:
        has_admin = (
            db.query(UserModel)
            .filter(
                UserModel.role.in_(
                    [PlatformRoles.ADMIN, PlatformRoles.SUPER_ADMIN]
                )
            )
            .first()
            is not None
        )
        if not has_admin:
            if not password:
                logging.warning(
                    "No administrator exists and DEFAULT_ADMIN_PASSWORD is not "
                    "set - skipping default account creation"
                )
                return
            admin = UserModel(
                name=name, email=email, role=PlatformRoles.SUPER_ADMIN
            )
            admin.password = password
            db.add(admin)
            db.commit()
            logging.info("Default super-admin account created: %s", email)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO)
    init_db()
    _ensure_default_admin()
    yield


api = FastAPI(
    title="Students Community Championship API",
    version="0.1.0",
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
    return {"status": "ok"}


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
