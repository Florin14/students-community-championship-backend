# CLAUDE.md — SCC Backend

FastAPI backend for the students' minifootball championship. Public read
endpoints, role-protected write endpoints, live match scoring built on an
append-only event log.

## Commands

```bash
# From the repo root
python3.9 -m venv --without-pip .venv                     # ensurepip is missing locally
python3.9 -m pip --python .venv/bin/python install -r requirements.txt

cp .env.template .env                     # paste the Neon / Supabase URL into DATABASE_URL

cd src && ../.venv/bin/uvicorn services.run_api:api --reload   # run the API
TEST_DATABASE_URL=postgresql://... .venv/bin/python tests/run_all.py   # run the tests

# Migrations (always from the repo root, never from src/)
.venv/bin/python -m alembic revision --autogenerate -m "what changed"
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic downgrade -1

# Docker: bundled Postgres + the migration job + the API on :8000
docker compose up -d --build
docker compose -f docker-compose.yml up -d   # deployed shape: no bundled DB, no ports
docker compose run --rm migrate              # migrations on their own
```

The stack is split across `docker-compose.yml` (topology), `env.yml`
(configuration), `local_db.yml` + `port_forwards.yml` + `docker-compose.override.yml`
(local only). The override is loaded automatically, so anything deploying must
pass `-f docker-compose.yml` explicitly. New env vars go in `.env.template` and
in `env.yml` in the same change.

**The database is Postgres** (Neon or Supabase in every deployed environment,
the bundled `postgres` container or a Neon branch locally). `DATABASE_URL` is
normalised by `extensions/sqlalchemy/init.py`: `postgres://` / `postgresql://`
become `postgresql+psycopg2://` and managed hosts get `sslmode=require`. The
pool is sized with `DB_POOL_SIZE` / `DB_MAX_OVERFLOW`. SQLite exists only as the
test harness fallback; never write code or migrations that only work there —
every migration must run on Postgres (enum types need `ALTER TYPE` / `DROP TYPE`,
enum columns need an explicit cast in raw SQL). Python 3.9 is the only
interpreter available locally.

## Architecture

```
src/
  constants/           one Enum per file, re-exported from __init__
  extensions/
    sqlalchemy/        engine, SessionLocal, get_db, DBSessionMiddleware, SqlBaseModel
    migrations/        Alembic env + versions/
  project_helpers/
    dependencies/      JwtRequired, GetInstanceFromPath, match access guards
    error/             Error enum: (code, message) pairs
    exceptions/        ErrorException
    functions/         jwt_handler, passwords, process_image
    responses/         exception handlers registered on the app
    schemas/           BaseSchema, PaginationParams
  modules/<feature>/
    models/            SQLAlchemy model + Pydantic schemas
    routes/            ONE FILE PER ROUTE, plus router.py holding the APIRouter
    services/          business logic shared between routes
  services/run_api.py  app entrypoint
```

Modules: `auth`, `user`, `season`, `team`, `player`, `field`, `match`,
`standings`, `stats`, `audit`.

## Conventions

These are load-bearing. Match them exactly when adding code.

- **One route per file.** The file name is the operation (`add_match.py`,
  `void_match_event.py`). Each imports `from .router import router` and is
  re-exported from `routes/__init__.py` with `from .add_match import *`.
- **camelCase attributes, snake_case columns.** Always name the DB column
  explicitly: `seasonId = Column("season_id", ...)`. JSON is camelCase.
- **Python 3.9 syntax only.** Use `Optional[X]` and `List[X]`, never `X | Y`.
- **List endpoints** take `XListParams(PaginationParams)` and return
  `XListResponse` with a `{"data": [...]}` envelope. Detail endpoints return
  `XResponse` directly.
- **Errors** are raised as `ErrorException(Error.NOT_FOUND, message=..., status_code=...)`,
  never as bare `HTTPException`.
- **Auth** is applied per route via
  `dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))]`.
  Read endpoints stay public; every write endpoint declares a role.
- **The session** comes from `db: Session = Depends(get_db)`. Routes call
  `db.flush()` while building, then a single `db.commit()` at the end.
- **Path lookups** use `Depends(GetInstanceFromPath(MatchModel))` rather than a
  hand-written query plus 404.
- **Schema changes go through Alembic only.** `init_db()` runs `create_all` for
  local convenience; it is disabled in production via `AUTO_CREATE_TABLES=false`.

## Migrations and default data

`src/services/run_migrations.py` is the one place a container moves the schema:
`alembic upgrade head`, then the default rows. It runs as the `migrate` compose
service, which the API waits on with `service_completed_successfully` — so two
replicas can never race the same upgrade, and a failed migration stops the
rollout instead of leaving the API serving against a half-moved schema.

```bash
docker compose run --rm migrate                   # in the stack
cd src && ../.venv/bin/python -m services.run_migrations   # from a checkout
```

It never autogenerates. Revisions are written by hand, reviewed and committed —
a container that invents its own DDL against a live database is a different
product.

**Defaults** live in `src/services/populate_defaults.py`: a `STEPS` list of
`(description, fn)`, applied in order right after the schema reaches head. Add a
default by writing `_step(session)` and appending it. Two rules hold for every
step:

- **Idempotent** — it runs on every deploy, against databases that are already
  populated. The admin step keys on *"does any administrator exist"*, never on
  the email, so changing `DEFAULT_ADMIN_EMAIL` cannot inject a second privileged
  account into a live platform.
- **Independent** — each step gets its own commit and its own error line, so one
  failure does not stop the rest.

Exit codes are the contract: **1** when the migration itself failed (nothing
starts against that database), **0** when the schema is at head — even if a
default did not apply, because a missing default row must not take the platform
down. In that case the last line reads `SOME DEFAULTS DID NOT APPLY`; that line
is the signal, so never make it unconditional.

Which callable runs is `DEFAULTS_POPULATE_FILE` / `DEFAULTS_POPULATE_FUNCTION`
(same env contract as the other platforms), and `SKIP_MIGRATION=true` makes the
job a no-op.

Running from a checkout there is no `migrate` job, so `run_api.py` applies the
same defaults at startup — but only in checkout mode
(`auto_create_tables_enabled()`). In a container the API's startup stays
read-only.

## Roles

| Role | May do |
| --- | --- |
| `OPERATOR` | Score only the matches assigned to them: add and void events, start/pause/finish that match. |
| `ADMIN` | Everything an operator can, plus manage seasons, teams, players, fields, matches and operator accounts. |
| `SUPER_ADMIN` | Everything, plus reopen a confirmed match and correct locked data. |

Role checks are hierarchical: `JwtRequired(roles=[PlatformRoles.ADMIN])` also
admits `SUPER_ADMIN`. Match-scoped access additionally goes through
`MatchAccess` (see `project_helpers/dependencies/match_access.py`), which is what
restricts an operator to their assigned matches.

## The match event log

The heart of the system, and the part most likely to be broken by a careless
change. Rules:

- **Every scoring action is a row in `match_events`** — goal, own goal, yellow
  card, red card. Nothing is ever hard-deleted: a mistake is voided
  (`status = VOIDED`), keeping who voided it and when.
- **The score is derived, never typed.** `matches.score_home` / `score_away` are
  a cache recomputed from active events by `recalculate_match_score()`. Never
  set them directly.
- **Writes are idempotent.** The client sends a `clientEventId` (a UUID it
  generates); replaying it returns the existing event instead of creating a
  second goal. This is what makes retry-on-reconnect safe.
- **Standings and player stats read active events only**, through
  `completed_match_filter()` and `active_event_filter()`.
- **A finished match is locked.** Writes are refused once `lockedAt` is set;
  only `SUPER_ADMIN` can reopen it.

After changing anything in this area, re-run the standings and idempotency
tests — a silent regression here corrupts the whole championship table.

## Testing

`tests/` is a plain-Python harness (no pytest: new dependencies need approval).
Run it with `TEST_DATABASE_URL` pointing at a Postgres server; each module then
creates its own database there, runs the migrations and drops it at the end.
Without the variable it falls back to SQLite, which proves less. Cover at minimum:
recalculation of standings, event idempotency, void semantics, operator
permissions, and match lock/reopen. A feature is not done because the app
starts.
