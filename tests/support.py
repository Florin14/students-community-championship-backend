"""Minimal test harness: no pytest, no httpx, no new dependencies.

Each test is a function registered with @test; `run(module)` executes them and
prints a pass/fail line per case. Routes are async, so `call()` drives them
through asyncio and passes the session and user explicitly instead of going
through FastAPI's dependency injection.
"""
import asyncio
import os
import subprocess
import sys
import tempfile
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
    """Create an empty database at head and return its URL.

    Migrations are run rather than metadata.create_all, so the tests exercise
    the same schema a deployment gets.
    """
    handle, path = tempfile.mkstemp(suffix=".db", prefix="scc-test-")
    os.close(handle)
    os.unlink(path)
    url = "sqlite:///%s" % path

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
    return url, path


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
