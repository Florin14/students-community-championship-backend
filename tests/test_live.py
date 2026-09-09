"""The live feed the public pages poll (plan section 4, launch condition 2)."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import call, fresh_database, run, test  # noqa: E402

DB_URL, DB_PATH = fresh_database()

from constants import MatchEventType, MatchState, PlatformRoles  # noqa: E402
from extensions.sqlalchemy import SessionLocal  # noqa: E402
from project_helpers.dependencies import MatchContext  # noqa: E402
from modules.auth.models import UserModel  # noqa: E402
from modules.match.models import (  # noqa: E402
    MatchEventAdd,
    MatchEventVoid,
    MatchModel,
)
from modules.match.routes.add_match_event import add_match_event  # noqa: E402
from modules.match.routes.get_live_matches import get_live_matches  # noqa: E402
from modules.match.routes.match_lifecycle import finish, pause, start  # noqa: E402
from modules.match.routes.void_match_event import void_match_event  # noqa: E402
from modules.player.models import PlayerModel  # noqa: E402
from modules.season.models import SeasonModel  # noqa: E402
from modules.team.models import TeamModel  # noqa: E402

DB = SessionLocal()

ADMIN = UserModel(name="Root", email="root@scc.ro", role=PlatformRoles.SUPER_ADMIN)
ADMIN.password = "password123"
DB.add(ADMIN)

SEASON = SeasonModel(name="2026", isActive=True)
DB.add(SEASON)
HOME = TeamModel(name="Informatica")
AWAY = TeamModel(name="Drept")
DB.add_all([HOME, AWAY])
DB.flush()
H1 = PlayerModel(name="Ionescu", teamId=HOME.id)
DB.add(H1)
DB.flush()

_n = [0]


def newMatch():
    _n[0] += 1
    match = MatchModel(
        seasonId=SEASON.id,
        homeTeamId=HOME.id,
        awayTeamId=AWAY.id,
        timestamp=datetime(2026, 5, 1, 10, 0) + timedelta(days=_n[0]),
        round=_n[0],
    )
    DB.add(match)
    DB.commit()
    return match


def ctx(match):
    return MatchContext(match=match, user=ADMIN)


def live(seasonId=None):
    return call(get_live_matches(seasonId=seasonId, db=DB))


def goal(match):
    return call(
        add_match_event(
            data=MatchEventAdd(
                type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
            ),
            ctx=ctx(match),
            db=DB,
        )
    )


@test
def test_a_scheduled_match_is_not_live():
    newMatch()
    assert live().data == []


@test
def test_a_started_match_appears_in_the_feed():
    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    DB.commit()

    payload = live()
    ids = [item.id for item in payload.data]
    assert match.id in ids
    item = [i for i in payload.data if i.id == match.id][0]
    assert item.state == MatchState.LIVE
    assert item.homeTeamName == "Informatica"
    assert item.isClockRunning is True


@test
def test_a_paused_match_stays_in_the_feed():
    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    call(pause(ctx=ctx(match), db=DB))
    DB.commit()

    item = [i for i in live().data if i.id == match.id]
    assert len(item) == 1
    assert item[0].state == MatchState.HALF_TIME
    assert item[0].isClockRunning is False


@test
def test_a_finished_match_leaves_the_feed():
    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    call(finish(ctx=ctx(match), db=DB))
    DB.commit()

    assert match.id not in [i.id for i in live().data]


@test
def test_the_timeline_travels_with_the_match():
    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    goal(match)
    DB.commit()

    item = [i for i in live().data if i.id == match.id][0]
    assert len(item.events) == 1
    assert item.events[0].playerName == "Ionescu"
    assert (item.scoreHome, item.scoreAway) == (1, 0)


@test
def test_voided_events_are_absent_from_the_public_timeline():
    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    added = goal(match)
    call(
        void_match_event(
            data=MatchEventVoid(reason="Mistake"),
            eventId=added.event.id,
            ctx=ctx(match),
            db=DB,
        )
    )
    DB.commit()

    item = [i for i in live().data if i.id == match.id][0]
    assert item.events == []
    assert item.scoreHome == 0


@test
def test_revision_is_stable_while_nothing_changes():
    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    goal(match)
    DB.commit()

    first = live().revision
    second = live().revision
    assert first == second
    assert first != "empty"


@test
def test_revision_changes_on_a_goal_and_on_a_void():
    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    DB.commit()
    before = live().revision

    added = goal(match)
    DB.commit()
    afterGoal = live().revision
    assert afterGoal != before

    call(
        void_match_event(
            data=MatchEventVoid(),
            eventId=added.event.id,
            ctx=ctx(match),
            db=DB,
        )
    )
    DB.commit()
    afterVoid = live().revision
    assert afterVoid != afterGoal


@test
def test_the_season_filter_narrows_the_feed():
    other = SeasonModel(name="2027")
    DB.add(other)
    DB.flush()

    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    DB.commit()

    assert live(seasonId=SEASON.id).data != []
    assert live(seasonId=other.id).data == []


@test
def test_an_empty_feed_reports_a_stable_revision():
    for match in DB.query(MatchModel).all():
        match.state = MatchState.SCHEDULED
    DB.commit()

    payload = live()
    assert payload.data == []
    assert payload.revision == "empty"
    assert payload.serverTime is not None


if __name__ == "__main__":
    code = run("Etapa 3 - the live feed")
    DB.close()
    os.unlink(DB_PATH)
    sys.exit(code)
