from sqlalchemy import event

from modules.season.models import SeasonTeamModel
from modules.standings.models import StandingModel


@event.listens_for(SeasonTeamModel, "after_insert")
def create_standing_row(mapper, connection, target):
    """Every team enrolled in a season starts with a zeroed standings row."""
    standings = StandingModel.__table__
    exists = connection.execute(
        standings.select()
        .where(standings.c.season_id == target.seasonId)
        .where(standings.c.team_id == target.teamId)
        .limit(1)
    ).first()
    if exists is None:
        connection.execute(
            standings.insert().values(
                season_id=target.seasonId,
                team_id=target.teamId,
                played=0,
                wins=0,
                draws=0,
                losses=0,
                goals_for=0,
                goals_against=0,
                points=0,
            )
        )
