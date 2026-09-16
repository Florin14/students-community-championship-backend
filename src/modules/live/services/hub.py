"""Rooms, subscribers and the "only send what changed" rule.

A room is either the live feed for one season filter (`("live", seasonId)`,
where seasonId may be None for "every season") or one match
(`("match", matchId)`). Each room remembers the last thing it sent: the feed's
`revision`, or a fingerprint of the match JSON. A refresh re-reads the data
and broadcasts only when that changed, so a burst of ten notices for the same
goal costs the clients one frame.

The hub lives in the API process and is fed by `extensions.live` - the notice
a match route publishes after its commit lands in `notify()` on the event
loop. That is what makes a single service enough: with one uvicorn worker
every socket and every write share this hub. (Running several workers or
replicas would need a broker between them; that is the day to split the live
service out, not before.)

The hub knows nothing about Starlette: it is given a fetcher with
`live_feed()` / `match()` and sockets with `send_json()` / `close()`, which is
what makes it testable without a network.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set, Tuple

from .fetcher import DatabaseFetcher, MatchNotFound

logger = logging.getLogger(__name__)

RoomKey = Tuple[str, Optional[int]]

CLOSE_NOT_FOUND = 4404
CLOSE_UPSTREAM_DOWN = 1011


class Room:
    def __init__(self, key: RoomKey):
        self.key = key
        self.sockets: Set[Any] = set()
        self.last: Optional[str] = None


def _fingerprint(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class LiveHub:
    def __init__(self, fetcher, coalesce_seconds: float = 0.25):
        self.fetcher = fetcher
        self.coalesce_seconds = coalesce_seconds
        self.rooms: Dict[RoomKey, Room] = {}
        self._refresh_lock = asyncio.Lock()
        # Pending notifications, folded together until the coalesce timer fires.
        self._pending_matches: Set[int] = set()
        self._pending_live = False
        self._flush_task: Optional[asyncio.Task] = None

    # --- membership -----------------------------------------------------------

    def _room(self, key: RoomKey) -> Room:
        room = self.rooms.get(key)
        if room is None:
            room = Room(key)
            self.rooms[key] = room
        return room

    def leave(self, socket) -> None:
        for key in list(self.rooms):
            room = self.rooms[key]
            room.sockets.discard(socket)
            if not room.sockets:
                # Forget the revision too: the next joiner must get a snapshot.
                del self.rooms[key]

    def connection_count(self) -> int:
        return sum(len(room.sockets) for room in self.rooms.values())

    async def join_live(self, socket, season_id: Optional[int]) -> bool:
        """Subscribe to the live feed and send the current snapshot.

        Returns False when the socket was closed instead: the API being down
        is reported by closing with 1011, so the browser falls back to polling
        rather than sitting on an open socket that never says anything.
        """
        key = ("live", season_id)
        try:
            payload = await self.fetcher.live_feed(season_id)
        except Exception as error:  # the database being unreachable
            logger.warning("live feed read failed on join: %s", error)
            await self._close(socket, CLOSE_UPSTREAM_DOWN, "API unavailable")
            return False
        room = self._room(key)
        room.sockets.add(socket)
        room.last = str(payload.get("revision", ""))
        await self._send(room, socket, dict(payload, type="snapshot"))
        return True

    async def join_match(self, socket, match_id: int) -> bool:
        key = ("match", match_id)
        try:
            payload = await self.fetcher.match(match_id)
        except MatchNotFound:
            await self._close(socket, CLOSE_NOT_FOUND, "Match not found")
            return False
        except Exception as error:
            logger.warning("match %s fetch failed on join: %s", match_id, error)
            await self._close(socket, CLOSE_UPSTREAM_DOWN, "API unavailable")
            return False
        room = self._room(key)
        room.sockets.add(socket)
        room.last = _fingerprint(payload)
        await self._send(room, socket, {"type": "match", "data": payload})
        return True

    # --- notifications ---------------------------------------------------------

    def notify(self, message: Dict[str, Any]) -> None:
        """A "match changed" notice arrived. Fold it into the pending set and
        make sure one flush is scheduled; the actual read happens after the
        coalesce window so a burst becomes one refresh.

        Called synchronously from the route that just committed. Without a
        running loop (a script, the tests' sync sections) there is nobody to
        push to, so the notice is dropped on purpose."""
        match_id = message.get("matchId")
        if isinstance(match_id, int):
            self._pending_matches.add(match_id)
        self._pending_live = True
        if self._flush_task is None or self._flush_task.done():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            self._flush_task = loop.create_task(self._flush_later())

    async def _flush_later(self) -> None:
        await asyncio.sleep(self.coalesce_seconds)
        match_ids = set(self._pending_matches)
        refresh_live = self._pending_live
        self._pending_matches.clear()
        self._pending_live = False
        if refresh_live:
            await self.refresh_live_rooms()
        for match_id in match_ids:
            await self.refresh_match(match_id)

    async def flush_now(self) -> None:
        """Test hook: run the pending flush without waiting for the timer."""
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        self.coalesce_seconds, saved = 0, self.coalesce_seconds
        try:
            await self._flush_later()
        finally:
            self.coalesce_seconds = saved

    async def refresh_all(self) -> None:
        """Every room, unconditionally - the safety net a periodic tick uses."""
        await self.refresh_live_rooms()
        for key in list(self.rooms):
            if key[0] == "match" and key[1] is not None:
                await self.refresh_match(key[1])

    async def refresh_live_rooms(self) -> None:
        async with self._refresh_lock:
            for key in list(self.rooms):
                if key[0] != "live":
                    continue
                room = self.rooms.get(key)
                if room is None or not room.sockets:
                    continue
                try:
                    payload = await self.fetcher.live_feed(key[1])
                except Exception as error:
                    logger.warning("live feed refresh failed: %s", error)
                    continue
                revision = str(payload.get("revision", ""))
                if revision == room.last:
                    continue
                room.last = revision
                await self._broadcast(room, dict(payload, type="snapshot"))

    async def refresh_match(self, match_id: int) -> None:
        key = ("match", match_id)
        async with self._refresh_lock:
            room = self.rooms.get(key)
            if room is None or not room.sockets:
                return
            try:
                payload = await self.fetcher.match(match_id)
            except MatchNotFound:
                # Deleted while people were watching: tell them and let go.
                for socket in list(room.sockets):
                    await self._close(socket, CLOSE_NOT_FOUND, "Match not found")
                self.rooms.pop(key, None)
                return
            except Exception as error:
                logger.warning("match %s refresh failed: %s", match_id, error)
                return
            fingerprint = _fingerprint(payload)
            if fingerprint == room.last:
                return
            room.last = fingerprint
            await self._broadcast(room, {"type": "match", "data": payload})

    # --- transport helpers --------------------------------------------------------

    async def _broadcast(self, room: Room, message: Dict[str, Any]) -> None:
        for socket in list(room.sockets):
            await self._send(room, socket, message)

    async def _send(self, room: Room, socket, message: Dict[str, Any]) -> None:
        try:
            await socket.send_json(message)
        except Exception as error:
            # A client that went away between two frames; drop it quietly.
            logger.debug("dropping socket after send failure: %s", error)
            room.sockets.discard(socket)

    async def _close(self, socket, code: int, message: str) -> None:
        try:
            await socket.send_json({"type": "error", "message": message})
        except Exception:
            pass
        try:
            await socket.close(code=code)
        except Exception:
            pass


# The one hub of this process. Registered with the event bus by the app's
# lifespan (services/run_api.py), so route commits reach it.
hub = LiveHub(DatabaseFetcher())
