from fastapi import Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from constants import CardType
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath
from modules.match.models import CardModel, GoalModel, MatchModel
from modules.player.models import (
    PlayerEventItem,
    PlayerEventsResponse,
    PlayerModel,
)

from .router import router


def _event_from_match(match: MatchModel, event_type: str, minute):
    return PlayerEventItem(
        matchId=match.id,
        timestamp=match.timestamp,
        homeTeamName=match.homeTeamName,
        awayTeamName=match.awayTeamName,
        scoreHome=match.scoreHome,
        scoreAway=match.scoreAway,
        type=event_type,
        minute=minute,
    )


@router.get("/{id}/events", response_model=PlayerEventsResponse)
async def get_player_events(
    player: PlayerModel = Depends(GetInstanceFromPath(PlayerModel)),
    db: Session = Depends(get_db),
):
    """Chronological list of the player's goals, assists and cards."""
    events = []

    goals = (
        db.query(GoalModel)
        .options(joinedload(GoalModel.match).joinedload(MatchModel.homeTeam))
        .options(joinedload(GoalModel.match).joinedload(MatchModel.awayTeam))
        .filter(
            or_(
                GoalModel.scorerId == player.id,
                GoalModel.assistPlayerId == player.id,
            )
        )
        .all()
    )
    for goal in goals:
        if goal.scorerId == player.id:
            events.append(_event_from_match(goal.match, "GOAL", goal.minute))
        if goal.assistPlayerId == player.id:
            events.append(_event_from_match(goal.match, "ASSIST", goal.minute))

    cards = (
        db.query(CardModel)
        .options(joinedload(CardModel.match).joinedload(MatchModel.homeTeam))
        .options(joinedload(CardModel.match).joinedload(MatchModel.awayTeam))
        .filter(CardModel.playerId == player.id)
        .all()
    )
    for card in cards:
        event_type = "YELLOW" if card.cardType == CardType.YELLOW else "RED"
        events.append(_event_from_match(card.match, event_type, card.minute))

    events.sort(
        key=lambda e: (e.timestamp, e.minute if e.minute is not None else -1),
        reverse=True,
    )

    return PlayerEventsResponse(data=events)
