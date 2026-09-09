from datetime import datetime

from fastapi import status

from constants import MatchState
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.audit.services import record as audit

from .score_service import recalculate_match_score


def _stop_clock(match) -> None:
    """Fold the running segment into the accumulated total."""
    if match.runningSince is not None:
        delta = datetime.utcnow() - match.runningSince
        match.elapsedSeconds = (match.elapsedSeconds or 0) + max(
            0, int(delta.total_seconds())
        )
        match.runningSince = None


def start_match(db, match, user):
    """Kick off. Idempotent, so a double tap on a bad connection is harmless."""
    if match.state == MatchState.LIVE and match.isClockRunning:
        return match

    if match.state == MatchState.FINISHED:
        raise ErrorException(
            Error.INVALID_MATCH_TRANSITION,
            message="The match is already finished; reopen it first",
            status_code=status.HTTP_409_CONFLICT,
        )

    now = datetime.utcnow()
    if match.startedAt is None:
        match.startedAt = now
        match.elapsedSeconds = 0
    match.runningSince = now
    match.state = MatchState.LIVE

    recalculate_match_score(db, match)
    db.flush()

    audit(
        db,
        user=user,
        action="MATCH_STARTED",
        entityType="Match",
        entityId=match.id,
        matchId=match.id,
        summary="Match started",
        details={"startedAt": match.startedAt.isoformat()},
    )
    return match


def pause_match(db, match, user):
    """Half time, or any stoppage that should stop the clock."""
    if match.state != MatchState.LIVE:
        raise ErrorException(
            Error.INVALID_MATCH_TRANSITION,
            message="Only a live match can be paused",
            status_code=status.HTTP_409_CONFLICT,
        )

    _stop_clock(match)
    match.state = MatchState.HALF_TIME
    db.flush()

    audit(
        db,
        user=user,
        action="MATCH_PAUSED",
        entityType="Match",
        entityId=match.id,
        matchId=match.id,
        summary="Match paused at minute %s" % match.currentMinute,
        details={"elapsedSeconds": match.elapsedSeconds},
    )
    return match


def resume_match(db, match, user):
    if match.state != MatchState.HALF_TIME:
        raise ErrorException(
            Error.INVALID_MATCH_TRANSITION,
            message="Only a paused match can be resumed",
            status_code=status.HTTP_409_CONFLICT,
        )

    match.runningSince = datetime.utcnow()
    match.state = MatchState.LIVE
    db.flush()

    audit(
        db,
        user=user,
        action="MATCH_RESUMED",
        entityType="Match",
        entityId=match.id,
        matchId=match.id,
        summary="Match resumed at minute %s" % match.currentMinute,
    )
    return match


def finish_match(db, match, user):
    """Confirm the final result and lock the match.

    After this only a super-admin can reopen it, which is what stops a
    confirmed result from being quietly rewritten (plan, section 6).
    """
    if match.state not in (MatchState.LIVE, MatchState.HALF_TIME):
        raise ErrorException(
            Error.INVALID_MATCH_TRANSITION,
            message="Only a started match can be finished",
            status_code=status.HTTP_409_CONFLICT,
        )

    now = datetime.utcnow()
    _stop_clock(match)
    match.state = MatchState.FINISHED
    match.lockedAt = now
    match.confirmedAt = now
    match.confirmedById = user.id

    recalculate_match_score(db, match)
    db.flush()

    audit(
        db,
        user=user,
        action="MATCH_FINISHED",
        entityType="Match",
        entityId=match.id,
        matchId=match.id,
        summary="Result confirmed: %s-%s" % (match.scoreHome, match.scoreAway),
        details={
            "scoreHome": match.scoreHome,
            "scoreAway": match.scoreAway,
            "elapsedSeconds": match.elapsedSeconds,
        },
    )
    return match


def reopen_match(db, match, user, reason: str):
    """Unlock a confirmed match so it can be corrected.

    The state stays FINISHED: the result is still the published one, it is just
    editable again. A reason is required because this is the one action that
    rewrites a confirmed result.
    """
    if not match.isLocked:
        raise ErrorException(
            Error.INVALID_MATCH_TRANSITION,
            message="The match is not locked",
            status_code=status.HTTP_409_CONFLICT,
        )

    previous = {
        "lockedAt": match.lockedAt.isoformat() if match.lockedAt else None,
        "confirmedById": match.confirmedById,
        "scoreHome": match.scoreHome,
        "scoreAway": match.scoreAway,
    }

    match.lockedAt = None
    match.confirmedAt = None
    match.confirmedById = None
    db.flush()

    audit(
        db,
        user=user,
        action="MATCH_REOPENED",
        entityType="Match",
        entityId=match.id,
        matchId=match.id,
        summary="Match reopened: %s" % reason,
        details={"reason": reason, "previous": previous},
    )
    return match
