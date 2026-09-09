from sqlalchemy.orm import Session

from modules.season.models import SeasonTeamModel


def ensure_team_enrolled(db: Session, season_id: int, team_id: int):
    """Enroll a team in a season if it is not already enrolled.

    The standings row is created automatically by the SeasonTeamModel
    after_insert event.
    """
    exists = (
        db.query(SeasonTeamModel)
        .filter(
            SeasonTeamModel.seasonId == season_id,
            SeasonTeamModel.teamId == team_id,
        )
        .first()
    )
    if exists is None:
        db.add(SeasonTeamModel(seasonId=season_id, teamId=team_id))
        db.flush()
