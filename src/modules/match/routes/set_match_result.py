from fastapi import Depends, status
from sqlalchemy.orm import Session, joinedload

from constants import MatchState, PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import (
    CardModel,
    GoalModel,
    MatchModel,
    MatchResponse,
    MatchResultSet,
)
from modules.player.models import PlayerModel
from modules.standings.services import recalculate_match_standings

from .router import router


@router.put(
    "/{id}/result",
    response_model=MatchResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def set_match_result(
    data: MatchResultSet,
    match: MatchModel = Depends(GetInstanceFromPath(MatchModel)),
    db: Session = Depends(get_db),
):
    """Set the final score and replace the match's goals and cards in one call."""
    match_team_ids = {match.homeTeamId, match.awayTeamId}

    for entry in list(data.goals) + list(data.cards):
        if entry.teamId not in match_team_ids:
            raise ErrorException(
                Error.BAD_REQUEST,
                message="Goal/card team must be one of the match teams",
            )

    player_ids = set()
    for goal in data.goals:
        if goal.scorerId is not None:
            player_ids.add(goal.scorerId)
        if goal.assistPlayerId is not None:
            player_ids.add(goal.assistPlayerId)
    for card in data.cards:
        player_ids.add(card.playerId)

    players = {}
    if player_ids:
        rows = (
            db.query(PlayerModel)
            .filter(PlayerModel.id.in_(player_ids))
            .all()
        )
        players = {player.id: player for player in rows}
        missing = player_ids - set(players.keys())
        if missing:
            raise ErrorException(
                Error.NOT_FOUND,
                message=f"Players not found: {sorted(missing)}",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    db.query(GoalModel).filter(GoalModel.matchId == match.id).delete()
    db.query(CardModel).filter(CardModel.matchId == match.id).delete()

    for goal in data.goals:
        scorer = players.get(goal.scorerId) if goal.scorerId else None
        assist = (
            players.get(goal.assistPlayerId) if goal.assistPlayerId else None
        )
        db.add(
            GoalModel(
                matchId=match.id,
                teamId=goal.teamId,
                scorerId=goal.scorerId,
                scorerNameSnapshot=scorer.name if scorer else None,
                assistPlayerId=goal.assistPlayerId,
                assistNameSnapshot=assist.name if assist else None,
                minute=goal.minute,
            )
        )

    for card in data.cards:
        player = players.get(card.playerId)
        db.add(
            CardModel(
                matchId=match.id,
                teamId=card.teamId,
                playerId=card.playerId,
                playerNameSnapshot=player.name if player else None,
                cardType=card.cardType,
                minute=card.minute,
            )
        )

    match.scoreHome = data.scoreHome
    match.scoreAway = data.scoreAway
    match.state = MatchState.FINISHED
    db.flush()

    recalculate_match_standings(db, match)
    db.commit()

    match = (
        db.query(MatchModel)
        .options(
            joinedload(MatchModel.homeTeam),
            joinedload(MatchModel.awayTeam),
            joinedload(MatchModel.season),
            joinedload(MatchModel.goals).joinedload(GoalModel.scorer),
            joinedload(MatchModel.goals).joinedload(GoalModel.assistPlayer),
            joinedload(MatchModel.cards).joinedload(CardModel.player),
        )
        .filter(MatchModel.id == match.id)
        .first()
    )
    return match
