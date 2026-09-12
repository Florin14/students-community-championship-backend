"""Default rows the platform needs in place before anyone can use it.

Run by ``services.run_migrations`` immediately after the schema reaches head,
and by the API at startup when it manages its own schema (the local-checkout
mode, ``AUTO_CREATE_TABLES=true``).

Two rules hold for everything in here:

* **Idempotent.** It runs on every deployment, against databases that are
  already populated. A step decides for itself whether there is anything to do.
* **Independent.** One failing step must not stop the others, so each gets its
  own error line and its own rollback. The caller reports whether every step
  succeeded - a default that silently did not happen is the failure mode this
  file exists to avoid.

Adding a default means writing a ``_step(session)`` function and appending it to
``STEPS``.
"""

import logging
import os
from typing import Callable, List, Tuple

from constants import PlatformRoles
from modules.auth.models import UserModel


def _ensure_default_admin(session) -> None:
    """Seed the first super-admin, so a fresh database can be logged into.

    SUPER_ADMIN rather than ADMIN because it is the only role that can reopen a
    confirmed match, and it is the account that creates the operator accounts
    for match day.

    Deliberately keyed on "does any administrator exist", not on the email: once
    a real administrator has been created, changing DEFAULT_ADMIN_EMAIL must not
    inject a second privileged account into a live platform.
    """
    email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@scc.ro")
    password = os.getenv("DEFAULT_ADMIN_PASSWORD")
    name = os.getenv("DEFAULT_ADMIN_NAME", "Administrator")

    has_admin = (
        session.query(UserModel)
        .filter(
            UserModel.role.in_(
                [PlatformRoles.ADMIN, PlatformRoles.SUPER_ADMIN]
            )
        )
        .first()
        is not None
    )
    if has_admin:
        logging.info("An administrator already exists - not seeding one")
        return

    if not password:
        # Not an error: a deployment that creates its administrator by hand
        # leaves the variable empty on purpose.
        logging.warning(
            "No administrator exists and DEFAULT_ADMIN_PASSWORD is not set - "
            "skipping default account creation"
        )
        return

    admin = UserModel(name=name, email=email, role=PlatformRoles.SUPER_ADMIN)
    admin.password = password
    session.add(admin)
    session.flush()
    logging.info("Default super-admin account created: %s", email)


# Ordered: a step may rely on everything above it having run.
STEPS: List[Tuple[str, Callable]] = [
    ("seeding the default administrator", _ensure_default_admin),
]


def populate_defaults(session) -> bool:
    """Apply every default step. Returns True when all of them succeeded.

    Commits per step, so a later failure cannot roll back the defaults that
    already applied cleanly.
    """
    all_ok = True
    for description, step in STEPS:
        try:
            step(session)
            session.commit()
        except Exception as error:  # noqa: BLE001 - reported, never re-raised
            all_ok = False
            session.rollback()
            logging.error("Error %s: %s", description, error, exc_info=True)
    return all_ok
