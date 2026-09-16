"""What a viewer sees: the live feed and the public view of one match.

Shared by the HTTP routes (`GET /matches/live`, `GET /matches/{id}`) and the
websocket hub, so a frame pushed over the socket is byte-for-byte what a poll
would have returned. Keep it that way: the frontend applies both through the
same reducer.
"""
import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from constants import MatchEventStatus, MatchState
from modules.match.models import (
    LiveMatchesResponse,
    MatchEventModel,
    MatchModel,
)

from .match_loader import load_match_full

LIVE_STATES = (MatchState.LIVE, MatchState.HALF_TIME)


def feed_revision(matches) -> str:
    """Fingerprint what a viewer can see, so an unchanged poll is cheap to ignore.

    Built from state, score and the latest event per match. The running clock is
    excluded on purpose - it changes every second on its own and the client
    ticks it locally from `playedSeconds`.
    """
    parts = []
    for match in matches:
        lastEventId = max([event.id for event in match.events] or [0])
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


def _public_timeline(events):
    """Active events only, in match order: what happened, not what was mistyped."""
    return sorted(
        [event for event in events if event.status == MatchEventStatus.ACTIVE],
        key=lambda event: (event.minute is None, event.minute or 0, event.id),
    )


def build_live_feed(db: Session, seasonId: Optional[int] = None) -> LiveMatchesResponse:
    """Every match in progress, with its timeline, in one call."""
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
        match.events = _public_timeline(match.events)

    return LiveMatchesResponse(
        data=matches,
        revision=feed_revision(matches),
        serverTime=datetime.utcnow(),
    )


def load_public_match(db: Session, matchId: int):
    """One match as the public pages show it, or None. The console reads
    `GET /matches/{id}/events?includeVoided=true` for the full log instead."""
    match = load_match_full(db, matchId)
    if match is None:
        return None
    match.events = _public_timeline(match.events)
    return match
