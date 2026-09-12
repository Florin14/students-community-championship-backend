import os
from functools import lru_cache
from typing import Dict, Optional

"""Build identity of the running image.

The values are baked in at build time (see the Dockerfile's ARG/ENV pair) and
default to "dev" when the app runs straight from a checkout. Everything that
reports a version - the /version endpoint, log lines, deployment markers - reads
it from here, so there is one answer to "what is actually deployed".
"""

UNKNOWN = "dev"


@lru_cache(maxsize=1)
def get_build_info() -> Dict[str, Optional[str]]:
    return {
        "name": "students-community-championship-backend",
        "version": os.getenv("APP_VERSION", UNKNOWN),
        "gitSha": os.getenv("GIT_SHA", UNKNOWN),
        "buildDate": os.getenv("BUILD_DATE") or None,
        "environment": os.getenv("APP_ENV", "local"),
    }


def version_string() -> str:
    """`0.2.0+ab12cd3` - what to put in a log line or a deployment marker."""
    info = get_build_info()
    if info["gitSha"] and info["gitSha"] != UNKNOWN:
        return "%s+%s" % (info["version"], info["gitSha"][:7])
    return str(info["version"])
