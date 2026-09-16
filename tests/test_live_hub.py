"""The websocket hub: rooms, snapshots on join, and the only-send-what-changed
rule. No database: the hub is given a scripted fetcher and fake sockets."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import SRC, call, run, test  # noqa: E402

# No database in this module, but importing the fetcher builds the engine.
os.environ.setdefault("DATABASE_URL", "sqlite://")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from modules.live.services.fetcher import MatchNotFound  # noqa: E402
from modules.live.services.hub import (  # noqa: E402
    CLOSE_NOT_FOUND,
    CLOSE_UPSTREAM_DOWN,
    LiveHub,
)
from modules.live.services.socket import origin_allowed  # noqa: E402


class FakeSocket:
    def __init__(self, fail_send=False):
        self.sent = []
        self.closed = None
        self.fail_send = fail_send

    async def send_json(self, message):
        if self.fail_send:
            raise RuntimeError("socket gone")
        self.sent.append(message)

    async def close(self, code=1000, reason=None):
        self.closed = code

    def types(self):
        return [m.get("type") for m in self.sent]


class FakeFetcher:
    """Scripted reads: `feed[seasonId]` and `matches[id]` are what it returns;
    every call is counted so tests can prove nothing was read twice."""

    def __init__(self):
        self.feed = {None: {"data": [], "revision": "empty", "serverTime": "t0"}}
        self.matches = {}
        self.calls = []

    async def live_feed(self, season_id):
        self.calls.append(("live", season_id))
        return dict(self.feed.get(season_id, self.feed[None]))

    async def match(self, match_id):
        self.calls.append(("match", match_id))
        if match_id not in self.matches:
            raise MatchNotFound()
        return dict(self.matches[match_id])


def make_hub():
    fetcher = FakeFetcher()
    fetcher.feed[None] = {"data": [{"id": 1}], "revision": "r1", "serverTime": "t1"}
    fetcher.feed[7] = {"data": [], "revision": "s7", "serverTime": "t1"}
    fetcher.matches[1] = {"id": 1, "scoreHome": 0, "scoreAway": 0, "events": []}
    return LiveHub(fetcher, coalesce_seconds=0), fetcher


@test
def snapshot_on_join():
    """joining the live feed sends one snapshot with the feed's keys"""
    hub, fetcher = make_hub()
    sock = FakeSocket()
    assert call(hub.join_live(sock, None)) is True
    assert sock.types() == ["snapshot"]
    frame = sock.sent[0]
    assert frame["revision"] == "r1" and frame["data"] == [{"id": 1}]
    assert frame["serverTime"] == "t1"
    assert hub.connection_count() == 1


@test
def no_resend_on_same_revision():
    """a refresh with an unchanged revision sends nothing"""
    hub, fetcher = make_hub()
    sock = FakeSocket()
    call(hub.join_live(sock, None))
    call(hub.refresh_live_rooms())
    assert sock.types() == ["snapshot"]


@test
def resend_on_changed_revision():
    """a refresh with a new revision broadcasts to every socket in the room"""
    hub, fetcher = make_hub()
    a, b = FakeSocket(), FakeSocket()
    call(hub.join_live(a, None))
    call(hub.join_live(b, None))
    fetcher.feed[None] = {"data": [{"id": 1, "scoreHome": 1}], "revision": "r2", "serverTime": "t2"}
    call(hub.refresh_live_rooms())
    assert a.types() == ["snapshot", "snapshot"]
    assert b.types() == ["snapshot", "snapshot"]
    assert a.sent[1]["revision"] == "r2"


@test
def season_rooms_are_separate():
    """the seasonId filter gets its own room and its own feed"""
    hub, fetcher = make_hub()
    all_seasons, one_season = FakeSocket(), FakeSocket()
    call(hub.join_live(all_seasons, None))
    call(hub.join_live(one_season, 7))
    assert one_season.sent[0]["revision"] == "s7"
    fetcher.feed[7] = {"data": [{"id": 9}], "revision": "s8", "serverTime": "t2"}
    call(hub.refresh_live_rooms())
    assert one_season.types() == ["snapshot", "snapshot"]
    assert all_seasons.types() == ["snapshot"]


@test
def match_room_sends_match_and_only_changes():
    """a match room sends the match on join and again only when the JSON changed"""
    hub, fetcher = make_hub()
    sock = FakeSocket()
    assert call(hub.join_match(sock, 1)) is True
    assert sock.types() == ["match"] and sock.sent[0]["data"]["id"] == 1
    call(hub.refresh_match(1))
    assert sock.types() == ["match"]
    fetcher.matches[1] = dict(fetcher.matches[1], scoreHome=1)
    call(hub.refresh_match(1))
    assert sock.types() == ["match", "match"]
    assert sock.sent[1]["data"]["scoreHome"] == 1


@test
def unknown_match_gets_error_and_4404():
    """joining a match the API does not know closes with 4404"""
    hub, fetcher = make_hub()
    sock = FakeSocket()
    assert call(hub.join_match(sock, 999)) is False
    assert sock.types() == ["error"]
    assert sock.sent[0]["message"] == "Match not found"
    assert sock.closed == CLOSE_NOT_FOUND
    assert hub.connection_count() == 0


@test
def api_down_on_join_closes_1011():
    """the database being unreachable on join closes the socket so the client polls"""
    hub, fetcher = make_hub()

    async def boom(season_id):
        raise OSError("connection refused")

    fetcher.live_feed = boom
    sock = FakeSocket()
    assert call(hub.join_live(sock, None)) is False
    assert sock.closed == CLOSE_UPSTREAM_DOWN
    assert sock.types() == ["error"]


@test
def notify_coalesces_a_burst_into_one_fetch():
    """ten notices for one match become one live read and one match read"""
    hub, fetcher = make_hub()
    live, watch = FakeSocket(), FakeSocket()
    call(hub.join_live(live, None))
    call(hub.join_match(watch, 1))
    fetcher.calls.clear()
    fetcher.feed[None] = {"data": [{"id": 1, "scoreHome": 1}], "revision": "r2", "serverTime": "t2"}
    fetcher.matches[1] = dict(fetcher.matches[1], scoreHome=1)

    async def burst():
        for _ in range(10):
            hub.notify({"type": "match.updated", "matchId": 1, "reason": "event.added"})
        await hub.flush_now()

    call(burst())
    assert fetcher.calls == [("live", None), ("match", 1)], fetcher.calls
    assert live.types() == ["snapshot", "snapshot"]
    assert watch.types() == ["match", "match"]


@test
def notify_only_refreshes_rooms_that_exist():
    """a message for a match nobody watches fetches nothing for it"""
    hub, fetcher = make_hub()
    live = FakeSocket()
    call(hub.join_live(live, None))
    fetcher.calls.clear()

    async def one():
        hub.notify({"type": "match.updated", "matchId": 42})
        await hub.flush_now()

    call(one())
    assert fetcher.calls == [("live", None)]


@test
def leave_forgets_empty_rooms():
    """the last socket leaving drops the room and its cached revision"""
    hub, fetcher = make_hub()
    sock = FakeSocket()
    call(hub.join_live(sock, None))
    hub.leave(sock)
    assert hub.rooms == {} and hub.connection_count() == 0
    again = FakeSocket()
    call(hub.join_live(again, None))
    assert again.types() == ["snapshot"]


@test
def dead_socket_is_dropped_on_send():
    """a socket whose send fails is removed instead of poisoning the room"""
    hub, fetcher = make_hub()
    good, dead = FakeSocket(), FakeSocket(fail_send=True)
    call(hub.join_live(good, None))
    call(hub.join_live(dead, None))
    assert hub.connection_count() == 1
    fetcher.feed[None] = {"data": [], "revision": "r3", "serverTime": "t3"}
    call(hub.refresh_live_rooms())
    assert good.types() == ["snapshot", "snapshot"]


@test
def match_deleted_while_watching():
    """a match deleted while people watch closes them with 4404"""
    hub, fetcher = make_hub()
    sock = FakeSocket()
    call(hub.join_match(sock, 1))
    del fetcher.matches[1]
    call(hub.refresh_match(1))
    assert sock.closed == CLOSE_NOT_FOUND
    assert ("match", 1) not in hub.rooms


@test
def origin_check_is_exact_and_slash_tolerant():
    """the origin check matches exactly, ignores a trailing slash, allows non-browsers"""
    allowed = ["https://scc.vercel.app"]
    assert origin_allowed("https://scc.vercel.app", allowed)
    assert origin_allowed("https://scc.vercel.app/", allowed)
    assert not origin_allowed("https://evil.example", allowed)
    assert not origin_allowed("http://scc.vercel.app", allowed)
    assert origin_allowed(None, allowed)
    assert origin_allowed("https://anything", ["*"])


if __name__ == "__main__":
    sys.exit(run("Live - the websocket hub"))
