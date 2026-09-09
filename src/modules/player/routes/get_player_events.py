from fastapi import Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from constants import MatchEventType
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath
from modules.match.models import MatchEventModel, MatchModel
from modules.match.services import active_event_filter
from modules.player.models import (
    PlayerEventItem,
    PlayerEventsResponse,
    PlayerModel,
)

from .router import router

# How an event reads on a player's own timeline. A card keeps its colour; a goal
# the player conceded into their own net is named as such rather than counted as
# a goal.
_LABELS = {
    MatchEventType.GOAL: "GOAL",
    MatchEventType.OWN_GOAL: "OWN_GOAL",
    MatchEventType.YELLOW_CARD: "YELLOW",
    MatchEventType.RED_CARD: "RED",
}


def _item(match: MatchModel, eventType: str, minute):
    return PlayerEventItem(
        matchId=match.id,
        timestamp=match.timestamp,
        homeTeamName=match.homeTeamName,
        awayTeamName=match.awayTeamName,
        scoreHome=match.scoreHome,
        scoreAway=match.scoreAway,
        type=eventType,
        minute=minute,
    )


@router.get("/{id}/events", response_model=PlayerEventsResponse)
async def get_player_events(
    player: PlayerModel = Depends(GetInstanceFromPath(PlayerModel)),
    db: Session = Depends(get_db),
):
    """Chronological list of the player's goals, assists and cards.

    Reads the active event log, so an event that was voided during the match
    never shows up on a profile.
    """
    events = (
        db.query(MatchEventModel)
        .options(
            joinedload(MatchEventModel.match).joinedload(MatchModel.homeTeam),
            joinedload(MatchEventModel.match).joinedload(MatchModel.awayTeam),
        )
        .filter(
            or_(
                MatchEventModel.playerId == player.id,
                MatchEventModel.assistPlayerId == player.id,
            ),
            active_event_filter(),
        )
        .all()
    )

    items = []
    for event in events:
        eventType = MatchEventType(str(event.type))
        if event.playerId == player.id:
            items.append(_item(event.match, _LABELS[eventType], event.minute))
        if (
            event.assistPlayerId == player.id
            and eventType == MatchEventType.GOAL
        ):
            items.append(_item(event.match, "ASSIST", event.minute))

    items.sort(
        key=lambda e: (e.timestamp, e.minute if e.minute is not None else -1),
        reverse=True,
    )

    return PlayerEventsResponse(data=items)
