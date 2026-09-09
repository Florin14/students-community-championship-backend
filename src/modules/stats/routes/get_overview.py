from typing import Optional

from fastapi import Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from constants import CardType, MatchState
from extensions.sqlalchemy import get_db
from modules.match.models import CardModel, MatchModel
from modules.match.services import completed_match_filter
from modules.season.models import SeasonTeamModel
from modules.player.models import PlayerModel
from modules.stats.models import OverviewResponse
from modules.team.models import TeamModel

from .helpers import build_top_players
from .router import router


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    seasonId: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    if seasonId:
        teams = (
            db.query(func.count(SeasonTeamModel.id))
            .filter(SeasonTeamModel.seasonId == seasonId)
            .scalar()
        )
    else:
        teams = db.query(func.count(TeamModel.id)).scalar()

    players = db.query(func.count(PlayerModel.id)).scalar()

    completed_query = db.query(MatchModel).filter(completed_match_filter())
    upcoming_query = db.query(MatchModel).filter(
        MatchModel.state == MatchState.SCHEDULED
    )
    if seasonId:
        completed_query = completed_query.filter(
            MatchModel.seasonId == seasonId
        )
        upcoming_query = upcoming_query.filter(MatchModel.seasonId == seasonId)

    matches_played = completed_query.count()
    matches_upcoming = upcoming_query.count()

    goals_query = db.query(
        func.sum(MatchModel.scoreHome + MatchModel.scoreAway)
    ).filter(completed_match_filter())
    if seasonId:
        goals_query = goals_query.filter(MatchModel.seasonId == seasonId)
    goals = int(goals_query.scalar() or 0)

    cards_query = (
        db.query(CardModel.cardType, func.count(CardModel.id))
        .join(MatchModel)
        .filter(completed_match_filter())
    )
    if seasonId:
        cards_query = cards_query.filter(MatchModel.seasonId == seasonId)
    cards = dict(cards_query.group_by(CardModel.cardType).all())

    top_scorers = build_top_players(
        db,
        seasonId,
        sort_key=lambda s: (s["goals"], s["assists"]),
        limit=1,
        keep=lambda s: s["goals"] > 0,
    )
    top_scorer = top_scorers[0] if top_scorers else None

    return OverviewResponse(
        teams=teams or 0,
        players=players or 0,
        matchesPlayed=matches_played,
        matchesUpcoming=matches_upcoming,
        goals=goals,
        avgGoalsPerMatch=(
            round(goals / matches_played, 2) if matches_played else 0.0
        ),
        yellowCards=cards.get(CardType.YELLOW, 0),
        redCards=cards.get(CardType.RED, 0),
        topScorerName=top_scorer.name if top_scorer else None,
        topScorerTeamName=top_scorer.teamName if top_scorer else None,
        topScorerGoals=top_scorer.goals if top_scorer else 0,
    )
