# CLAUDE.md — SCC Backend

FastAPI backend for the students' minifootball championship. Public read
endpoints, role-protected write endpoints, live match scoring built on an
append-only event log.

## Commands

```bash
# From the repo root
python3.9 -m venv --without-pip .venv                     # ensurepip is missing locally
python3.9 -m pip --python .venv/bin/python install -r requirements.txt

cp .env.example .env                                       # then fill DATABASE_URL

cd src && ../.venv/bin/uvicorn services.run_api:api --reload   # run the API
cd src && ../.venv/bin/python -m pytest ../tests -q             # run the tests

# Migrations (always from the repo root, never from src/)
.venv/bin/alembic revision --autogenerate -m "what changed"
.venv/bin/alembic upgrade head
.venv/bin/alembic downgrade -1
```

Local dev without Postgres: `DATABASE_URL=sqlite:///./scc.db`. Python 3.9 is the
only interpreter available locally.

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

`tests/` uses pytest with a SQLite database per test module. Cover at minimum:
recalculation of standings, event idempotency, void semantics, operator
permissions, and match lock/reopen. A feature is not done because the app
starts.
