from typing import Optional

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from modules.match.models import LiveMatchesResponse
from modules.match.services import build_live_feed

from .router import router


@router.get("/live", response_model=LiveMatchesResponse)
async def get_live_matches(
    seasonId: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Every match in progress, with its timeline, in one call.

    This is what the public pages poll when the websocket is not available,
    and exactly what the websocket pushes - see services/live_feed.py.
    """
    return build_live_feed(db, seasonId)
