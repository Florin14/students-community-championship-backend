#!/bin/sh
# Container entrypoint.
#
#   serve      run the API (default)
#   migrate    apply migrations and exit - used as a one-shot job
#   <other>    executed verbatim, so `docker run ... sh` still works
#
# Migrations are applied by the `serve` path only when RUN_MIGRATIONS=true.
# Leave it false wherever more than one replica starts at once and run the
# `migrate` job first instead, so two containers cannot race the same upgrade.
set -eu

DEV_JWT_SECRET="dev-only-not-a-secret"

# Migrations AND the default rows, in that order - see
# src/services/run_migrations.py. Never `alembic upgrade head` directly: the
# defaults have to follow the schema move, and skipping them leaves a fresh
# deployment with no account to log in with.
run_migrations() {
    echo "[entrypoint] applying migrations and defaults"
    cd /app/src
    python -m services.run_migrations
}

# The compose default for JWT_SECRET_KEY is a visible placeholder. Serving with
# it outside a local stack would mean anyone who has read the repo can mint an
# admin token, and that is the kind of thing nobody notices until it is used -
# so refuse to start instead of logging a warning nobody reads.
check_jwt_secret() {
    env_name="${APP_ENV:-${ENV:-local}}"
    if [ "$env_name" != "local" ] && [ "${JWT_SECRET_KEY:-}" = "$DEV_JWT_SECRET" ]; then
        echo "[entrypoint] refusing to start: JWT_SECRET_KEY still holds the" >&2
        echo "             development placeholder while APP_ENV=$env_name." >&2
        echo "             Set a real secret for this environment." >&2
        exit 1
    fi
}

case "${1:-serve}" in
    migrate)
        run_migrations
        echo "[entrypoint] migrations applied"
        ;;
    serve)
        check_jwt_secret
        if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
            run_migrations
        fi
        cd /app/src
        echo "[entrypoint] starting API ${APP_VERSION:-dev} on port ${PORT:-8000}"
        # --reload is a local-development switch (docker-compose.override.yml
        # sets it alongside the bind mount). It must stay off in deployed
        # environments: the reloader's parent process keeps PID 1 alive even
        # when the worker dies, so `restart: always` would never fire.
        if [ "${RELOAD:-false}" = "true" ]; then
            set -- --reload --reload-dir /app/src
        else
            set --
        fi
        exec uvicorn services.run_api:api \
            --host 0.0.0.0 \
            --port "${PORT:-8000}" \
            --proxy-headers \
            --forwarded-allow-ips '*' \
            "$@"
        ;;
    *)
        exec "$@"
        ;;
esac
