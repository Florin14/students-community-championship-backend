import uuid
from datetime import datetime
from typing import Optional, Tuple

from fastapi import status
from sqlalchemy.orm import Session

from constants import MatchEventStatus, MatchEventType
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.audit.services import record as audit
from modules.match.models import MatchEventModel

from .score_service import recalculate_match_score


def _load_player(db: Session, playerId: int):
    from modules.player.models import PlayerModel

    player = (
        db.query(PlayerModel).filter(PlayerModel.id == playerId).first()
    )
    if player is None:
        raise ErrorException(
            Error.NOT_FOUND,
            message="Player %s not found" % playerId,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return player


def _expected_team_for_player(match, eventType: MatchEventType, teamId: int):
    """Which squad the player must belong to for this event to make sense.

    A goal is credited to the team the scorer plays for; an own goal is credited
    to the opponent, so the player belongs to the *other* team. Getting this
    backwards is how an own goal ends up in the wrong striker's tally.
    """
    if eventType == MatchEventType.OWN_GOAL:
        return (
            match.awayTeamId if teamId == match.homeTeamId else match.homeTeamId
        )
    return teamId


def add_match_event(
    db: Session, match, user, data
) -> Tuple[MatchEventModel, bool]:
    """Record one event. Returns (event, created).

    `created` is False when the client's event id has been seen before: the
    stored event is returned unchanged, which is what makes retrying a request
    over a bad connection safe.
    """
    clientEventId = (data.clientEventId or "").strip() or str(uuid.uuid4())

    existing = (
        db.query(MatchEventModel)
        .filter(
            MatchEventModel.matchId == match.id,
            MatchEventModel.clientEventId == clientEventId,
        )
        .first()
    )
    if existing is not None:
        return existing, False

    eventType = MatchEventType(str(data.type))

    if data.teamId not in (match.homeTeamId, match.awayTeamId):
        raise ErrorException(
            Error.BAD_REQUEST,
            message="The event must be credited to one of the two teams",
        )

    player = None
    if eventType.isCard and data.playerId is None:
        raise ErrorException(
            Error.BAD_REQUEST, message="A card needs the player who received it"
        )

    if data.playerId is not None:
        player = _load_player(db, data.playerId)
        expectedTeamId = _expected_team_for_player(
            match, eventType, data.teamId
        )
        if player.teamId != expectedTeamId:
            raise ErrorException(
                Error.PLAYER_NOT_IN_TEAM,
                message=(
                    "%s does not play for the team this %s belongs to"
                    % (player.name, str(eventType).lower().replace("_", " "))
                ),
            )

    assistPlayer = None
    if data.assistPlayerId is not None:
        if eventType != MatchEventType.GOAL:
            raise ErrorException(
                Error.BAD_REQUEST,
                message="Only a goal can carry an assist",
            )
        if data.assistPlayerId == data.playerId:
            raise ErrorException(
                Error.BAD_REQUEST,
                message="A player cannot assist their own goal",
            )
        assistPlayer = _load_player(db, data.assistPlayerId)
        if assistPlayer.teamId != data.teamId:
            raise ErrorException(
                Error.PLAYER_NOT_IN_TEAM,
                message="%s does not play for the scoring team"
                % assistPlayer.name,
            )

    superseded = None
    if data.supersedesEventId is not None:
        superseded = (
            db.query(MatchEventModel)
            .filter(
                MatchEventModel.id == data.supersedesEventId,
                MatchEventModel.matchId == match.id,
            )
            .first()
        )
        if superseded is None:
            raise ErrorException(
                Error.NOT_FOUND,
                message="The event being corrected was not found on this match",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    minute = data.minute if data.minute is not None else match.currentMinute

    event = MatchEventModel(
        matchId=match.id,
        clientEventId=clientEventId,
        type=eventType,
        status=MatchEventStatus.ACTIVE,
        teamId=data.teamId,
        playerId=data.playerId,
        playerNameSnapshot=player.name if player else None,
        assistPlayerId=data.assistPlayerId,
        assistNameSnapshot=assistPlayer.name if assistPlayer else None,
        minute=minute,
        createdById=user.id,
        createdByNameSnapshot=user.name,
        supersedesEventId=superseded.id if superseded else None,
    )
    db.add(event)
    db.flush()

    if superseded is not None and superseded.status == MatchEventStatus.ACTIVE:
        superseded.status = MatchEventStatus.CORRECTED
        superseded.voidedAt = datetime.utcnow()
        superseded.voidedById = user.id
        superseded.voidedByNameSnapshot = user.name
        superseded.voidReason = "Corrected by event %s" % event.id
        db.flush()

    recalculate_match_score(db, match)

    audit(
        db,
        user=user,
        action="EVENT_ADDED",
        entityType="MatchEvent",
        entityId=event.id,
        matchId=match.id,
        summary="%s at minute %s" % (str(eventType), minute),
        details={
            "type": str(eventType),
            "teamId": data.teamId,
            "playerId": data.playerId,
            "playerName": event.playerNameSnapshot,
            "assistPlayerId": data.assistPlayerId,
            "minute": minute,
            "clientEventId": clientEventId,
            "supersedesEventId": event.supersedesEventId,
            "scoreAfter": [match.scoreHome, match.scoreAway],
        },
    )

    return event, True


def void_match_event(
    db: Session, match, event: MatchEventModel, user, reason: Optional[str] = None
) -> MatchEventModel:
    """Take an event out of the active set without deleting it."""
    if event.matchId != match.id:
        raise ErrorException(
            Error.NOT_FOUND,
            message="That event does not belong to this match",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if event.status != MatchEventStatus.ACTIVE:
        raise ErrorException(
            Error.EVENT_ALREADY_VOIDED, status_code=status.HTTP_409_CONFLICT
        )

    event.status = MatchEventStatus.VOIDED
    event.voidedAt = datetime.utcnow()
    event.voidedById = user.id
    event.voidedByNameSnapshot = user.name
    event.voidReason = reason
    db.flush()

    recalculate_match_score(db, match)

    audit(
        db,
        user=user,
        action="EVENT_VOIDED",
        entityType="MatchEvent",
        entityId=event.id,
        matchId=match.id,
        summary="Voided %s at minute %s" % (str(event.type), event.minute),
        details={
            "type": str(event.type),
            "teamId": event.teamId,
            "playerName": event.playerNameSnapshot,
            "minute": event.minute,
            "reason": reason,
            "scoreAfter": [match.scoreHome, match.scoreAway],
        },
    )

    return event


def last_active_event(db: Session, matchId: int) -> Optional[MatchEventModel]:
    """The most recently entered active event - what 'undo' acts on."""
    return (
        db.query(MatchEventModel)
        .filter(
            MatchEventModel.matchId == matchId,
            MatchEventModel.status == MatchEventStatus.ACTIVE,
        )
        .order_by(MatchEventModel.createdAt.desc(), MatchEventModel.id.desc())
        .first()
    )
