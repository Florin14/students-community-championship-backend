"""Minimal test harness: no pytest, no httpx, no new dependencies.

Each test is a function registered with @test; `run(module)` executes them and
prints a pass/fail line per case. Routes are async, so `call()` drives them
through asyncio and passes the session and user explicitly instead of going
through FastAPI's dependency injection.

Databases: point TEST_DATABASE_URL at a Postgres server (any database on it,
e.g. `postgresql://postgres@127.0.0.1:5432/postgres`) and every module gets its
own freshly created database there, dropped again when the module ends. That is
the mode that proves anything, since the platform runs on Postgres. Without it
the harness falls back to a throwaway SQLite file and says so.
"""
import asyncio
import os
import subprocess
import sys
import tempfile
import time
import traceback

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO_ROOT, "src")

_TESTS = []


def test(fn):
    _TESTS.append(fn)
    return fn


def call(coroutine):
    """Run an async route handler to completion."""
    return asyncio.get_event_loop().run_until_complete(coroutine)


def fresh_database():
    """Create an empty database at head and return `(url, handle)`.

    Migrations are run rather than metadata.create_all, so the tests exercise
    the same schema a deployment gets. Pass the handle to `drop_database` when
    the module is done.
    """
    server_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if server_url:
        url, handle = _fresh_postgres_database(server_url)
        print("database: postgres (%s)" % handle)
    else:
        url, handle = _fresh_sqlite_database()
        print("database: sqlite fallback - set TEST_DATABASE_URL for Postgres")

    env = dict(os.environ)
    env["DATABASE_URL"] = url
    env["AUTO_CREATE_TABLES"] = "false"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "alembic upgrade failed:\n%s" % result.stdout.decode("utf-8")
        )

    os.environ["DATABASE_URL"] = url
    os.environ["AUTO_CREATE_TABLES"] = "false"
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    return url, handle


def _fresh_sqlite_database():
    handle, path = tempfile.mkstemp(suffix=".db", prefix="scc-test-")
    os.close(handle)
    os.unlink(path)
    return "sqlite:///%s" % path, path


def _postgres_admin_connection(server_url):
    """A psycopg2 connection to the server's maintenance database."""
    import psycopg2
    from sqlalchemy.engine import make_url

    parsed = make_url(_as_sqlalchemy_url(server_url))
    connection = psycopg2.connect(
        host=parsed.host,
        port=parsed.port or 5432,
        user=parsed.username,
        password=parsed.password,
        dbname=parsed.database or "postgres",
        **{k: v for k, v in parsed.query.items() if k == "sslmode"}
    )
    connection.autocommit = True
    return connection, parsed


def _as_sqlalchemy_url(url):
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def _fresh_postgres_database(server_url):
    name = "scc_test_%d_%d" % (os.getpid(), int(time.time()))
    connection, parsed = _postgres_admin_connection(server_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute('CREATE DATABASE "%s"' % name)
    finally:
        connection.close()
    url = parsed.set(database=name).render_as_string(hide_password=False)
    return url, name


def drop_database(handle):
    """Remove the database `fresh_database` created. Safe to call once."""
    server_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not server_url:
        if os.path.exists(handle):
            os.unlink(handle)
        return

    # Our own engine still holds pooled connections to the database.
    from extensions.sqlalchemy import engine

    engine.dispose()
    connection, _ = _postgres_admin_connection(server_url)
    try:
        with connection.cursor() as cursor:
            cursor.execute('DROP DATABASE IF EXISTS "%s" WITH (FORCE)' % handle)
    finally:
        connection.close()


def raises(errorEnum, fn, *args, **kwargs):
    """Assert the call fails with a specific Error code, and return the error."""
    from project_helpers.exceptions import ErrorException

    try:
        fn(*args, **kwargs)
    except ErrorException as exc:
        actual = exc.error if hasattr(exc, "error") else None
        code = getattr(actual, "code", None)
        if code != errorEnum.code:
            raise AssertionError(
                "expected %s (%s), got %s (%s)"
                % (errorEnum.name, errorEnum.code, getattr(actual, "name", "?"), code)
            )
        return exc
    raise AssertionError("expected %s, but the call succeeded" % errorEnum.name)


def run(label):
    print("\n%s" % label)
    print("-" * len(label))
    failures = []
    for fn in _TESTS:
        name = fn.__name__.replace("test_", "").replace("_", " ")
        try:
            fn()
        except Exception:
            failures.append((name, traceback.format_exc()))
            print("  FAIL  %s" % name)
        else:
            print("  ok    %s" % name)

    print("")
    if failures:
        for name, tb in failures:
            print("=" * 70)
            print("FAILED: %s" % name)
            print(tb)
        print("%d of %d failed" % (len(failures), len(_TESTS)))
        return 1
    print("all %d passed" % len(_TESTS))
    return 0
