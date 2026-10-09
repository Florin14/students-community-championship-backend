from sqlalchemy import func

from modules.match.models import MatchModel
from modules.match.services import completed_match_filter


def audience_query(db, season_id=None):
    query = db.query(MatchModel).filter(
        completed_match_filter(), MatchModel.audience.isnot(None),
    )
    if season_id is not None:
        query = query.filter(MatchModel.seasonId == season_id)
    return query


def audience_summary(db, season_id=None):
    total, count, average, maximum = audience_query(db, season_id).with_entities(
        func.sum(MatchModel.audience), func.count(MatchModel.id),
        func.avg(MatchModel.audience), func.max(MatchModel.audience),
    ).one()
    return {
        "totalSpectators": int(total or 0),
        "matchesWithAudience": count,
        "averageSpectators": round(float(average), 2) if average is not None else None,
        "maxSpectators": maximum,
    }
