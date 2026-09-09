from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from constants import MatchEventStatus, MatchEventType, MatchState
from modules.match.models import MatchEventModel

GOAL_TYPES = (MatchEventType.GOAL, MatchEventType.OWN_GOAL)

# States in which a score exists at all. Before kickoff the score stays null so
# the public pages show a fixture, not a 0-0 result.
SCORED_STATES = (MatchState.LIVE, MatchState.HALF_TIME, MatchState.FINISHED)


def active_event_filter():
    """SQL expression selecting the events that count."""
    return MatchEventModel.status == MatchEventStatus.ACTIVE


def goals_by_team(db: Session, matchId: int) -> Dict[int, int]:
    rows = (
        db.query(MatchEventModel.teamId, func.count(MatchEventModel.id))
        .filter(
            MatchEventModel.matchId == matchId,
            MatchEventModel.type.in_(GOAL_TYPES),
            active_event_filter(),
        )
        .group_by(MatchEventModel.teamId)
        .all()
    )
    return {teamId: count for teamId, count in rows}


def recalculate_match_score(db: Session, match) -> None:
    """Derive the match score from its active events.

    The only writer of `scoreHome` / `scoreAway`. Nothing else may set them:
    a typed-in score is what makes a score and its statistics diverge, which
    section 12 of the plan lists as a launch blocker.
    """
    if match.startedAt is None and match.state != MatchState.FINISHED:
        match.scoreHome = None
        match.scoreAway = None
        return

    counts = goals_by_team(db, match.id)
    match.scoreHome = counts.get(match.homeTeamId, 0)
    match.scoreAway = counts.get(match.awayTeamId, 0)
