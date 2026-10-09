from typing import Dict, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from constants import MatchEventType
from modules.match.models import MatchEventModel, MatchModel
from modules.match.services import active_event_filter, completed_match_filter

EMPTY = {
    "goals": 0,
    "ownGoals": 0,
    "assists": 0,
    "yellowCards": 0,
    "redCards": 0,
}

# Which stat each event type feeds. An own goal is deliberately kept out of
# `goals`: it counts on the scoreboard for the other team, never in the
# scorer's tally.
_STAT_BY_TYPE = {
    MatchEventType.GOAL: "goals",
    MatchEventType.OWN_GOAL: "ownGoals",
    MatchEventType.YELLOW_CARD: "yellowCards",
    MatchEventType.RED_CARD: "redCards",
}


def _completed_events(query, seasonId: Optional[int]):
    """Restrict to active events of matches that count."""
    query = query.join(
        MatchModel, MatchEventModel.matchId == MatchModel.id
    ).filter(completed_match_filter(), active_event_filter())
    if seasonId:
        query = query.filter(MatchModel.seasonId == seasonId)
    return query


def get_player_stats_map(
    db: Session,
    player_ids: Optional[Iterable[int]] = None,
    season_id: Optional[int] = None,
) -> Dict[int, Dict[str, int]]:
    """Return {playerId: {goals, ownGoals, assists, yellowCards, redCards}}
    computed from the active events of completed matches.
    """
    ids = set(player_ids) if player_ids is not None else None
    stats: Dict[int, Dict[str, int]] = {}

    def entry(playerId: int) -> Dict[str, int]:
        return stats.setdefault(playerId, dict(EMPTY))

    # Goals, own goals and cards all hang off the event's player.
    byType = _completed_events(
        db.query(
            MatchEventModel.playerId,
            MatchEventModel.type,
            func.count(MatchEventModel.id),
        ),
        season_id,
    ).filter(MatchEventModel.playerId.isnot(None))
    if ids is not None:
        byType = byType.filter(MatchEventModel.playerId.in_(ids))

    for playerId, eventType, count in byType.group_by(
        MatchEventModel.playerId, MatchEventModel.type
    ).all():
        key = _STAT_BY_TYPE.get(MatchEventType(str(eventType)))
        if key is not None:
            entry(playerId)[key] = count

    # Assists hang off a second column on the same rows.
    assists = _completed_events(
        db.query(
            MatchEventModel.assistPlayerId, func.count(MatchEventModel.id)
        ),
        season_id,
    ).filter(
        MatchEventModel.assistPlayerId.isnot(None),
        MatchEventModel.type == MatchEventType.GOAL,
    )
    if ids is not None:
        assists = assists.filter(MatchEventModel.assistPlayerId.in_(ids))

    for playerId, count in assists.group_by(
        MatchEventModel.assistPlayerId
    ).all():
        entry(playerId)["assists"] = count

    return stats


def attach_player_stats(db: Session, players, season_id: Optional[int] = None):
    """Attach the per-season stat counters onto player instances."""
    if not players:
        return players

    stats = get_player_stats_map(
        db, player_ids=[player.id for player in players], season_id=season_id
    )
    from constants import AttendanceStatus
    from modules.attendance.models import AttendanceModel

    attendance_query = db.query(
        AttendanceModel.playerIdSnapshot, func.count(AttendanceModel.id)
    ).join(MatchModel, MatchModel.id == AttendanceModel.matchId).filter(
        AttendanceModel.status == AttendanceStatus.PRESENT,
        AttendanceModel.playerIdSnapshot.in_([player.id for player in players]),
    )
    if season_id is not None:
        attendance_query = attendance_query.filter(MatchModel.seasonId == season_id)
    attendance_counts = dict(attendance_query.group_by(AttendanceModel.playerIdSnapshot).all())
    for player in players:
        player.attendanceCount = attendance_counts.get(player.id, 0)
        playerStats = stats.get(player.id, EMPTY)
        player.goals = playerStats["goals"]
        player.ownGoals = playerStats["ownGoals"]
        player.assists = playerStats["assists"]
        player.yellowCards = playerStats["yellowCards"]
        player.redCards = playerStats["redCards"]

    return players
