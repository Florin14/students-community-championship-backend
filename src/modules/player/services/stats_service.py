from typing import Dict, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from constants import CardType
from modules.match.models import CardModel, GoalModel, MatchModel
from modules.match.services import completed_match_filter


def _base_filters(query, season_id: Optional[int]):
    query = query.join(MatchModel).filter(completed_match_filter())
    if season_id:
        query = query.filter(MatchModel.seasonId == season_id)
    return query


def get_player_stats_map(
    db: Session,
    player_ids: Optional[Iterable[int]] = None,
    season_id: Optional[int] = None,
) -> Dict[int, Dict[str, int]]:
    """Return {playerId: {goals, assists, yellowCards, redCards}} computed
    from completed matches (optionally restricted to one season)."""
    ids = set(player_ids) if player_ids is not None else None
    stats: Dict[int, Dict[str, int]] = {}

    def entry(player_id: int) -> Dict[str, int]:
        return stats.setdefault(
            player_id,
            {"goals": 0, "assists": 0, "yellowCards": 0, "redCards": 0},
        )

    goals_query = _base_filters(
        db.query(GoalModel.scorerId, func.count(GoalModel.id)), season_id
    ).filter(GoalModel.scorerId.isnot(None))
    if ids is not None:
        goals_query = goals_query.filter(GoalModel.scorerId.in_(ids))
    for player_id, count in goals_query.group_by(GoalModel.scorerId).all():
        entry(player_id)["goals"] = count

    assists_query = _base_filters(
        db.query(GoalModel.assistPlayerId, func.count(GoalModel.id)), season_id
    ).filter(GoalModel.assistPlayerId.isnot(None))
    if ids is not None:
        assists_query = assists_query.filter(GoalModel.assistPlayerId.in_(ids))
    for player_id, count in assists_query.group_by(
        GoalModel.assistPlayerId
    ).all():
        entry(player_id)["assists"] = count

    cards_query = _base_filters(
        db.query(CardModel.playerId, CardModel.cardType, func.count(CardModel.id)),
        season_id,
    ).filter(CardModel.playerId.isnot(None))
    if ids is not None:
        cards_query = cards_query.filter(CardModel.playerId.in_(ids))
    for player_id, card_type, count in cards_query.group_by(
        CardModel.playerId, CardModel.cardType
    ).all():
        key = "yellowCards" if card_type == CardType.YELLOW else "redCards"
        entry(player_id)[key] = count

    return stats


def attach_player_stats(db: Session, players, season_id: Optional[int] = None):
    """Attach goals/assists/yellowCards/redCards attributes to player instances."""
    if not players:
        return players

    stats = get_player_stats_map(
        db, player_ids=[player.id for player in players], season_id=season_id
    )
    empty = {"goals": 0, "assists": 0, "yellowCards": 0, "redCards": 0}
    for player in players:
        player_stats = stats.get(player.id, empty)
        player.goals = player_stats["goals"]
        player.assists = player_stats["assists"]
        player.yellowCards = player_stats["yellowCards"]
        player.redCards = player_stats["redCards"]

    return players
