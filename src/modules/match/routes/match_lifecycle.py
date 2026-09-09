"""Start, pause, resume, finish and reopen a match.

Grouped in one file because they are one state machine: splitting five
three-line handlers across five files would hide that they belong together.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import MatchAccess, MatchContext
from modules.match.models import MatchReopen, MatchResponse
from modules.match.services import (
    finish_match,
    load_match_full,
    pause_match,
    reopen_match,
    resume_match,
    start_match,
)
from modules.standings.services import recalculate_match_standings

from .router import router


@router.post("/{id}/start", response_model=MatchResponse)
async def start(
    ctx: MatchContext = Depends(MatchAccess()),
    db: Session = Depends(get_db),
):
    """Kick off. Starts the clock the console reads the minute from."""
    start_match(db, ctx.match, ctx.user)
    db.commit()
    return load_match_full(db, ctx.match.id)


@router.post("/{id}/pause", response_model=MatchResponse)
async def pause(
    ctx: MatchContext = Depends(MatchAccess()),
    db: Session = Depends(get_db),
):
    """Half time, or any stoppage that should stop the clock."""
    pause_match(db, ctx.match, ctx.user)
    db.commit()
    return load_match_full(db, ctx.match.id)


@router.post("/{id}/resume", response_model=MatchResponse)
async def resume(
    ctx: MatchContext = Depends(MatchAccess()),
    db: Session = Depends(get_db),
):
    resume_match(db, ctx.match, ctx.user)
    db.commit()
    return load_match_full(db, ctx.match.id)


@router.post("/{id}/finish", response_model=MatchResponse)
async def finish(
    ctx: MatchContext = Depends(MatchAccess()),
    db: Session = Depends(get_db),
):
    """Confirm the final result and lock the match.

    From here the result counts towards the table, and only a super-admin can
    reopen it for correction.
    """
    finish_match(db, ctx.match, ctx.user)
    recalculate_match_standings(db, ctx.match)
    db.commit()
    return load_match_full(db, ctx.match.id)


@router.post("/{id}/reopen", response_model=MatchResponse)
async def reopen(
    data: MatchReopen,
    ctx: MatchContext = Depends(
        MatchAccess(minRole=PlatformRoles.SUPER_ADMIN, allowLocked=True)
    ),
    db: Session = Depends(get_db),
):
    """Unlock a confirmed match so it can be corrected.

    Super-admin only, and a reason is required: this is the one action that
    rewrites a result the public has already seen.
    """
    reopen_match(db, ctx.match, ctx.user, reason=data.reason)
    recalculate_match_standings(db, ctx.match)
    db.commit()
    return load_match_full(db, ctx.match.id)
