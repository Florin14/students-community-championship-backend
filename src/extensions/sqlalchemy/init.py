import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import configure_mappers, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

from .base_model import BaseModel

# The API is normally started from src/, while the env files live at the repo
# root, so anchor the lookup to this file instead of the working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Precedence, highest first: the real environment, then .env.local, then .env.
# Neither file may override a variable that is already exported - that is how a
# test run or a one-off `DATABASE_URL=... python ...` ends up writing into the
# development database instead of the one it was pointed at.
local_env_path = PROJECT_ROOT / ".env.local"
if local_env_path.exists():
    load_dotenv(local_env_path, override=False)
load_dotenv(PROJECT_ROOT / ".env", override=False)

# Hosts that only accept TLS. A connection string copied from the Neon or
# Supabase console usually carries `sslmode=require` already; this is for the
# one that was trimmed by hand.
MANAGED_POSTGRES_SUFFIXES = (".neon.tech", ".supabase.co", ".supabase.com")


def normalize_database_url(url: str) -> str:
    """Turn any Postgres connection string into the one SQLAlchemy accepts.

    The consoles hand out `postgres://` (rejected outright by SQLAlchemy 2) and
    `postgresql://` (accepted, but leaves the driver choice implicit). Both
    become `postgresql+psycopg2://`, and a managed host gets `sslmode=require`
    when no sslmode was given. Anything that is not Postgres is returned as is.
    """
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg2://" + url[len(prefix):]
            break
    if not url.startswith("postgresql"):
        return url

    parsed = make_url(url)
    host = (parsed.host or "").lower()
    if host.endswith(MANAGED_POSTGRES_SUFFIXES) and "sslmode" not in parsed.query:
        parsed = parsed.update_query_dict({"sslmode": "require"})
    return parsed.render_as_string(hide_password=False)


def build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return normalize_database_url(database_url)

    host = os.getenv("POSTGRESQL_HOST")
    database = os.getenv("POSTGRESQL_DATABASE")
    username = os.getenv("POSTGRESQL_USERNAME")
    password = os.getenv("POSTGRESQL_PASSWORD")
    port = os.getenv("POSTGRESQL_PORT", "5432")

    if host and database and username:
        return normalize_database_url(
            f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
        )

    raise RuntimeError(
        "DATABASE_URL or POSTGRESQL_* env vars are required. "
        "Copy .env.template to .env and paste the Neon / Supabase connection "
        "string into DATABASE_URL."
    )


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    return int(value) if value else default


DATABASE_URL = build_database_url()

connect_args = {}
engine_options = {}
if DATABASE_URL.startswith("sqlite"):
    # Only the test harness fallback ever lands here (tests/support.py).
    connect_args["check_same_thread"] = False
else:
    # Managed Postgres counts connections, not requests: Neon caps them per
    # compute size and Supabase per plan, and every API replica holds its own
    # pool. Keep the pool small by default and size it per environment.
    engine_options["pool_size"] = _int_env("DB_POOL_SIZE", 5)
    engine_options["max_overflow"] = _int_env("DB_MAX_OVERFLOW", 5)
    engine_options["pool_timeout"] = _int_env("DB_POOL_TIMEOUT", 30)
    # Fail fast on an unreachable host instead of hanging the request.
    connect_args["connect_timeout"] = _int_env("DB_CONNECT_TIMEOUT", 10)

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    # Neon suspends an idle compute and Supabase's pooler drops idle
    # connections: ping before use and never keep a connection past 5 minutes.
    pool_pre_ping=True,
    pool_recycle=300,
    **engine_options,
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


def auto_create_tables_enabled() -> bool:
    """True when this process owns its own schema, i.e. it runs from a checkout.

    Every container sets it to false: there the schema is moved by the `migrate`
    job before the API starts. Read through this helper rather than the variable
    so the API's startup and its table creation can never disagree about which
    mode they are in.
    """
    return os.getenv("AUTO_CREATE_TABLES", "true").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def init_db():
    """Prepare the mappers and, for local development only, create the tables.

    Schema changes go through Alembic. `AUTO_CREATE_TABLES` exists so a local
    checkout does not need a migration run; set it to false in every deployed
    environment so the schema is only ever moved by `alembic upgrade`.
    """
    configure_mappers()

    if auto_create_tables_enabled():
        BaseModel.metadata.create_all(bind=engine)
    else:
        logging.info("AUTO_CREATE_TABLES is off - schema is managed by Alembic")
