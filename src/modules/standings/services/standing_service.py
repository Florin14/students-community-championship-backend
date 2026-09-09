from typing import Dict, Iterable, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from modules.match.models import MatchModel
from modules.match.services import completed_match_filter, match_is_completed
from modules.standings.models import StandingModel


def ensure_standing_row(db: Session, season_id: int, team_id: int) -> StandingModel:
    standing = (
        db.query(StandingModel)
        .filter(
            StandingModel.seasonId == season_id,
            StandingModel.teamId == team_id,
        )
        .first()
    )
    if standing is None:
        standing = StandingModel(
            seasonId=season_id,
            teamId=team_id,
            played=0,
            wins=0,
            draws=0,
            losses=0,
            goalsFor=0,
            goalsAgainst=0,
            points=0,
        )
        db.add(standing)
        db.flush()
    return standing


def _recalculate_team_standing(db: Session, season_id: int, team_id: int):
    standing = ensure_standing_row(db, season_id, team_id)

    matches = (
        db.query(MatchModel)
        .filter(
            MatchModel.seasonId == season_id,
            or_(
                MatchModel.homeTeamId == team_id,
                MatchModel.awayTeamId == team_id,
            ),
            completed_match_filter(),
        )
        .all()
    )

    wins = draws = losses = goals_for = goals_against = 0
    for match in matches:
        is_home = match.homeTeamId == team_id
        scored = match.scoreHome if is_home else match.scoreAway
        conceded = match.scoreAway if is_home else match.scoreHome
        goals_for += scored
        goals_against += conceded
        if scored > conceded:
            wins += 1
        elif scored == conceded:
            draws += 1
        else:
            losses += 1

    standing.played = len(matches)
    standing.wins = wins
    standing.draws = draws
    standing.losses = losses
    standing.goalsFor = goals_for
    standing.goalsAgainst = goals_against
    standing.points = wins * 3 + draws


def recalculate_standings_for_teams(
    db: Session, season_id: int, team_ids: Iterable[int]
):
    for team_id in set(team_ids):
        _recalculate_team_standing(db, season_id, team_id)


def recalculate_match_standings(db: Session, match: MatchModel):
    recalculate_standings_for_teams(
        db, match.seasonId, [match.homeTeamId, match.awayTeamId]
    )


def build_form_map(db: Session, season_id: int, last: int = 5) -> Dict[int, str]:
    """Return {teamId: 'WDLWW'} built from the season's completed matches,
    most recent first."""
    matches: List[MatchModel] = (
        db.query(MatchModel)
        .filter(MatchModel.seasonId == season_id, completed_match_filter())
        .order_by(MatchModel.timestamp.desc(), MatchModel.id.desc())
        .all()
    )

    form: Dict[int, List[str]] = {}
    for match in matches:
        if not match_is_completed(match):
            continue
        for team_id, scored, conceded in (
            (match.homeTeamId, match.scoreHome, match.scoreAway),
            (match.awayTeamId, match.scoreAway, match.scoreHome),
        ):
            letters = form.setdefault(team_id, [])
            if len(letters) >= last:
                continue
            if scored > conceded:
                letters.append("W")
            elif scored == conceded:
                letters.append("D")
            else:
                letters.append("L")

    return {team_id: "".join(letters) for team_id, letters in form.items()}
