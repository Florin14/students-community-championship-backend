from sqlalchemy.orm import Session, joinedload

from modules.match.models import (
    MatchEventModel,
    MatchModel,
    MatchOperatorModel,
)
from .attendance_summary import attach_match_attendance


def load_match_full(db: Session, matchId: int):
    """Re-read a match with every relationship the response schema exposes.

    Used after a write so the response carries team names, logos, the field,
    the assigned operators and the goal/card details without lazy loads firing
    once the request's session is closed.
    """
    match = (
        db.query(MatchModel)
        .options(
            joinedload(MatchModel.homeTeam),
            joinedload(MatchModel.awayTeam),
            joinedload(MatchModel.season),
            joinedload(MatchModel.field),
            joinedload(MatchModel.confirmedBy),
            joinedload(MatchModel.matchOperators).joinedload(
                MatchOperatorModel.user
            ),
            joinedload(MatchModel.events).joinedload(MatchEventModel.player),
            joinedload(MatchModel.events).joinedload(
                MatchEventModel.assistPlayer
            ),
            joinedload(MatchModel.events).joinedload(
                MatchEventModel.createdBy
            ),
        )
        .filter(MatchModel.id == matchId)
        .first()
    )
    if match is not None:
        attach_match_attendance(db, [match])
    return match
