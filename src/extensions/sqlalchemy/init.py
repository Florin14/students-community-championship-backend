import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import configure_mappers, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

from .base_model import BaseModel

load_dotenv(".env", override=False)

local_env_path = Path(".env.local")
if local_env_path.exists():
    load_dotenv(local_env_path, override=True)


def build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url

    host = os.getenv("POSTGRESQL_HOST")
    database = os.getenv("POSTGRESQL_DATABASE")
    username = os.getenv("POSTGRESQL_USERNAME")
    password = os.getenv("POSTGRESQL_PASSWORD")
    port = os.getenv("POSTGRESQL_PORT", "5432")

    if host and database and username:
        return f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"

    raise RuntimeError(
        "DATABASE_URL or POSTGRESQL_* env vars are required. "
        "Copy .env.example to .env and fill in the connection details."
    )


DATABASE_URL = build_database_url()

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db(request: Request):
    return request.state.db


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        db = SessionLocal()
        request.state.db = db
        try:
            response = await call_next(request)
        except OperationalError:
            logging.warning("DB connection lost, retrying with a fresh session")
            db.close()
            engine.dispose()
            db = SessionLocal()
            request.state.db = db
            response = await call_next(request)
        finally:
            db.close()
        return response


def init_db():
    configure_mappers()
    BaseModel.metadata.create_all(bind=engine)
