"""Bring the database to head, then populate the default rows.

This is the one place migrations are applied in a container. It runs as its own
step - the ``migrate`` service in docker-compose.yml, which the API waits on
with ``service_completed_successfully`` - so that two API replicas can never
race the same upgrade, and a failed migration stops the rollout instead of
leaving a container serving against a half-moved schema.

    python -m services.run_migrations      # from src/, or via the entrypoint

Deliberately NOT autogenerating revisions at start-up. Revisions are written by
hand, reviewed and committed (see CLAUDE.md); a container that invents its own
DDL against a production database is a different product.

Environment
-----------
SKIP_MIGRATION              true -> do nothing and exit 0. For a service that
                            shares a database it does not own.
DEFAULTS_POPULATE_FILE      module holding the defaults callable.
DEFAULTS_POPULATE_FUNCTION  its name. Same contract as the other platforms;
                            only the default module path is SCC's own layout.

Exit codes
----------
0   schema at head (whether or not the defaults all applied)
1   the migration itself failed - nothing should start against this database
"""

import importlib
import logging
import os
import sys
from pathlib import Path

# The app is normally started from src/ while alembic.ini lives at the repo
# root, and Alembic resolves `script_location` and `prepend_sys_path` against
# the WORKING DIRECTORY, not against the ini file. Anchoring on this file and
# chdir-ing means the script behaves the same from a checkout and from /app.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

DEFAULT_POPULATE_MODULE = "services.populate_defaults"
DEFAULT_POPULATE_FUNCTION = "populate_defaults"


def _load_populate_defaults():
    """Resolve the defaults callable, or None when there is nothing to run.

    Every failure here is a warning rather than an exception: defaults are not
    allowed to take a deployment down. The cause is always logged - a silent
    skip is how a broken import goes unnoticed for weeks.
    """
    module_name = os.getenv("DEFAULTS_POPULATE_FILE", DEFAULT_POPULATE_MODULE)
    function_name = os.getenv(
        "DEFAULTS_POPULATE_FUNCTION", DEFAULT_POPULATE_FUNCTION
    )
    try:
        module = importlib.import_module(module_name)
    except Exception as error:  # noqa: BLE001 - broad on purpose, see docstring
        logging.warning(
            "Could not import %s (%r) - skipping default population",
            module_name,
            error,
            exc_info=True,
        )
        return None

    populate = getattr(module, function_name, None)
    if not callable(populate):
        logging.warning(
            "%s has no callable %s - skipping default population",
            module_name,
            function_name,
        )
        return None

    logging.info("Defaults will be populated by %s.%s", module_name, function_name)
    return populate


def upgrade_to_head() -> None:
    # The URL is not read from the ini file: migrations/env.py builds it from
    # the environment, the same way the app does.
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    logging.info("Applying migrations: alembic upgrade head")
    command.upgrade(config, "head")


def _configure_logging() -> None:
    """(Re)apply our log level.

    Has to be callable twice: Alembic's env.py runs `fileConfig(alembic.ini)`,
    and alembic.ini sets the root logger to WARN - so everything this script
    logs at INFO after the upgrade would otherwise disappear, including the line
    saying which module populated the defaults.
    """
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter("%(levelname)-5.5s [migrations] %(message)s")
    logging.basicConfig(level=level)
    root = logging.getLogger()
    root.setLevel(level)
    # basicConfig only formats on its first call, and fileConfig replaced the
    # handlers in between - so set the format on whatever is attached now.
    for handler in root.handlers:
        handler.setFormatter(formatter)


def main() -> int:
    _configure_logging()

    if os.getenv("SKIP_MIGRATION", "false").lower() == "true":
        logging.warning("SKIP_MIGRATION is set - leaving the database alone")
        return 0

    try:
        upgrade_to_head()
    except Exception as error:  # noqa: BLE001 - the one fatal case
        logging.error("Migration failed: %s", error, exc_info=True)
        return 1
    finally:
        # Alembic reconfigured logging from alembic.ini on its way through.
        _configure_logging()
    logging.info("Schema is at head")

    populate = _load_populate_defaults()
    if populate is None:
        print("Schema at head. No defaults to populate.", flush=True)
        return 0

    # Imported only now: it pulls in the models, and it must never be the
    # reason a migration fails to start.
    from extensions.sqlalchemy import SessionLocal

    session = SessionLocal()
    try:
        # Only an explicit False counts as a failure: a defaults module written
        # to the other platforms' contract reports through exceptions and
        # returns nothing, and must not be read as "everything failed".
        defaults_ok = populate(session) is not False
    except Exception as error:  # noqa: BLE001
        defaults_ok = False
        session.rollback()
        logging.error("Populating defaults failed: %s", error, exc_info=True)
    finally:
        session.close()

    # The exit code stays 0: a missing default row must not stop the platform
    # from starting. This line is the signal - say plainly which one it is,
    # because an unconditional success message is how a skipped backfill hides.
    if defaults_ok:
        print("Schema at head. Defaults populated.", flush=True)
    else:
        print(
            "Schema at head. SOME DEFAULTS DID NOT APPLY - see the errors above.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
