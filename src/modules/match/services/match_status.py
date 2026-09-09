from sqlalchemy import and_

from constants import MatchState
from modules.match.models import MatchModel


def completed_match_filter():
    """SQL expression selecting matches that count towards standings/stats."""
    return and_(
        MatchModel.state == MatchState.FINISHED,
        MatchModel.scoreHome.isnot(None),
        MatchModel.scoreAway.isnot(None),
    )


def match_is_completed(match: MatchModel) -> bool:
    return (
        match.state == MatchState.FINISHED
        and match.scoreHome is not None
        and match.scoreAway is not None
    )
