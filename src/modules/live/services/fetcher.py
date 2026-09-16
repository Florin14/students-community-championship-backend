"""Reads for the hub: the live feed and one match, as JSON.

The hub runs on the event loop and the ORM is synchronous, so each read gets
its own session in a worker thread. The payloads are built by the very same
functions the HTTP routes return, serialised the way FastAPI would serialise
them, so a socket frame and a poll response are interchangeable.
"""
import asyncio
from typing import Any, Dict, Optional

from extensions.sqlalchemy import SessionLocal
from modules.match.models import LiveMatchesResponse, MatchResponse
from modules.match.services import build_live_feed, load_public_match


class MatchNotFound(Exception):
    pass


def _live_feed_sync(seasonId: Optional[int]) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        feed = build_live_feed(session, seasonId)
        return LiveMatchesResponse.model_validate(feed).model_dump(mode="json")
    finally:
        session.close()


def _match_sync(matchId: int) -> Dict[str, Any]:
    session = SessionLocal()
    try:
        match = load_public_match(session, matchId)
        if match is None:
            raise MatchNotFound()
        return MatchResponse.model_validate(match).model_dump(mode="json")
    finally:
        session.close()


class DatabaseFetcher:
    async def live_feed(self, seasonId: Optional[int]) -> Dict[str, Any]:
        return await asyncio.get_event_loop().run_in_executor(
            None, _live_feed_sync, seasonId
        )

    async def match(self, matchId: int) -> Dict[str, Any]:
        return await asyncio.get_event_loop().run_in_executor(
            None, _match_sync, matchId
        )
