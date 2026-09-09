import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv(".env", override=False)
if os.path.exists(".env.local"):
    load_dotenv(".env.local", override=True)

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
    matchRouter,
    playerRouter,
    seasonRouter,
    standingsRouter,
    statsRouter,
    teamRouter,
)
from modules.auth.models import UserModel


def _ensure_default_admin():
    email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@scc.ro")
    password = os.getenv("DEFAULT_ADMIN_PASSWORD")
    name = os.getenv("DEFAULT_ADMIN_NAME", "Administrator")

    db = SessionLocal()
    try:
        has_admin = (
            db.query(UserModel)
            .filter(UserModel.role == PlatformRoles.ADMIN)
            .first()
            is not None
        )
        if not has_admin:
            if not password:
                logging.warning(
                    "No admin exists and DEFAULT_ADMIN_PASSWORD is not set - "
                    "skipping default admin creation"
                )
                return
            admin = UserModel(name=name, email=email, role=PlatformRoles.ADMIN)
            admin.password = password
            db.add(admin)
            db.commit()
            logging.info("Default admin user created: %s", email)
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
    seasonRouter,
    teamRouter,
    playerRouter,
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
