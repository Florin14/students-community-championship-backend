import hashlib
from datetime import datetime
from typing import Optional

from fastapi import Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from constants import MatchEventStatus, MatchState
from extensions.sqlalchemy import get_db
from modules.match.models import (
    LiveMatchesResponse,
    MatchEventModel,
    MatchModel,
)

from .router import router

LIVE_STATES = (MatchState.LIVE, MatchState.HALF_TIME)


def _revision(matches) -> str:
    """Fingerprint what a viewer can see, so an unchanged poll is cheap to ignore.

    Built from state, score and the latest event per match. The running clock is
    excluded on purpose - it changes every minute on its own and the client
    derives the minute locally.
    """
    parts = []
    for match in matches:
        lastEventId = max(
            [event.id for event in match.events] or [0]
        )
        parts.append(
            "%s:%s:%s:%s:%s:%s"
            % (
                match.id,
                match.state,
                match.scoreHome,
                match.scoreAway,
                lastEventId,
                len(match.events),
            )
        )
    if not parts:
        return "empty"
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


@router.get("/live", response_model=LiveMatchesResponse)
async def get_live_matches(
    seasonId: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Every match in progress, with its timeline, in one call.

    This is what the public pages poll. Voided events are excluded, so the
    timeline shows what happened rather than what was mistyped.
    """
    query = (
        db.query(MatchModel)
        .options(
            joinedload(MatchModel.homeTeam),
            joinedload(MatchModel.awayTeam),
            joinedload(MatchModel.season),
            joinedload(MatchModel.field),
            joinedload(MatchModel.events).joinedload(MatchEventModel.player),
            joinedload(MatchModel.events).joinedload(
                MatchEventModel.assistPlayer
            ),
        )
        .filter(MatchModel.state.in_(LIVE_STATES))
    )

    if seasonId:
        query = query.filter(MatchModel.seasonId == seasonId)

    matches = query.order_by(MatchModel.timestamp.asc()).all()

    for match in matches:
        match.events = sorted(
            [
                event
                for event in match.events
                if event.status == MatchEventStatus.ACTIVE
            ],
            key=lambda event: (
                event.minute if event.minute is not None else 0,
                event.id,
            ),
        )

    return LiveMatchesResponse(
        data=matches,
        revision=_revision(matches),
        serverTime=datetime.utcnow(),
    )
