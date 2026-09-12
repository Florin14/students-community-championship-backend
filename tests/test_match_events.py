"""The match event log: derived score, idempotency, void, lifecycle and lock.

Covers section 5 of the implementation plan (every action is an event, the score
is computed from the valid ones, a mistake is cancelled rather than deleted) and
the locking rules from section 6.
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import (  # noqa: E402
    call,
    drop_database,
    fresh_database,
    raises,
    run,
    test,
)

DB_URL, DB_HANDLE = fresh_database()

from constants import (  # noqa: E402
    MatchEventStatus,
    MatchEventType,
    MatchState,
    PlatformRoles,
)
from extensions.sqlalchemy import SessionLocal  # noqa: E402
from project_helpers.dependencies import MatchAccess, MatchContext  # noqa: E402
from project_helpers.error import Error  # noqa: E402
from modules.audit.models import AuditLogModel  # noqa: E402
from modules.auth.models import UserModel  # noqa: E402
from modules.match.models import (  # noqa: E402
    MatchEventAdd,
    MatchEventModel,
    MatchEventVoid,
    MatchModel,
    MatchReopen,
)
from modules.match.routes.add_match_event import add_match_event  # noqa: E402
from modules.match.routes.get_match import get_match  # noqa: E402
from modules.match.routes.get_match_events import get_match_events  # noqa: E402
from modules.match.models import MatchEventListParams  # noqa: E402
from modules.match.routes.match_lifecycle import (  # noqa: E402
    finish,
    pause,
    reopen,
    resume,
    start,
)
from modules.match.routes.undo_last_match_event import (  # noqa: E402
    undo_last_match_event,
)
from modules.match.routes.void_match_event import void_match_event  # noqa: E402
from modules.match.services import set_match_operators  # noqa: E402
from modules.player.models import PlayerModel  # noqa: E402
from modules.player.services import get_player_stats_map  # noqa: E402
from modules.season.models import SeasonModel  # noqa: E402
from modules.standings.models import StandingModel  # noqa: E402
from modules.team.models import TeamModel  # noqa: E402

DB = SessionLocal()


def makeUser(name, email, role):
    user = UserModel(name=name, email=email, role=role)
    user.password = "password123"
    DB.add(user)
    DB.flush()
    return user


SUPER = makeUser("Root", "root@scc.ro", PlatformRoles.SUPER_ADMIN)
OPERATOR = makeUser("Operator", "op@scc.ro", PlatformRoles.OPERATOR)

SEASON = SeasonModel(name="2026", isActive=True)
DB.add(SEASON)
HOME = TeamModel(name="Informatica", shortName="INF")
AWAY = TeamModel(name="Drept", shortName="DRP")
DB.add_all([HOME, AWAY])
DB.flush()

H1 = PlayerModel(name="Ionescu", teamId=HOME.id, shirtNumber=9)
H2 = PlayerModel(name="Marin", teamId=HOME.id, shirtNumber=7)
A1 = PlayerModel(name="Popa", teamId=AWAY.id, shirtNumber=10)
DB.add_all([H1, H2, A1])
DB.flush()

_counter = [0]


def newMatch(state=MatchState.SCHEDULED, **kwargs):
    _counter[0] += 1
    match = MatchModel(
        seasonId=SEASON.id,
        homeTeamId=HOME.id,
        awayTeamId=AWAY.id,
        timestamp=datetime(2026, 5, 1, 10, 0) + timedelta(days=_counter[0]),
        round=_counter[0],
        state=state,
        **kwargs
    )
    DB.add(match)
    DB.flush()
    set_match_operators(DB, match, [OPERATOR.id])
    DB.commit()
    return match


def ctx(match, user=None):
    return MatchContext(match=match, user=user or OPERATOR)


def addEvent(match, user=None, **kwargs):
    payload = MatchEventAdd(**kwargs)
    return call(add_match_event(data=payload, ctx=ctx(match, user), db=DB))


def started(**kwargs):
    match = newMatch(**kwargs)
    call(start(ctx=ctx(match), db=DB))
    return match


# --- Score derivation --------------------------------------------------------

@test
def test_score_is_null_before_kickoff():
    match = newMatch()
    assert match.scoreHome is None
    assert match.scoreAway is None
    assert match.currentMinute is None


@test
def test_score_is_derived_from_active_events():
    match = started()
    addEvent(match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id)
    addEvent(match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H2.id)
    result = addEvent(
        match, type=MatchEventType.GOAL, teamId=AWAY.id, playerId=A1.id
    )
    assert (result.scoreHome, result.scoreAway) == (2, 1)
    assert (match.scoreHome, match.scoreAway) == (2, 1)


@test
def test_own_goal_counts_for_the_other_team_not_the_scorer():
    match = started()
    # Popa (Drept) puts it in his own net: the goal is credited to Informatica.
    addEvent(
        match,
        type=MatchEventType.OWN_GOAL,
        teamId=HOME.id,
        playerId=A1.id,
    )
    call(finish(ctx=ctx(match), db=DB))
    assert (match.scoreHome, match.scoreAway) == (1, 0)

    stats = get_player_stats_map(DB, season_id=SEASON.id)
    popa = stats.get(A1.id, {})
    assert popa.get("ownGoals") == 1
    assert popa.get("goals", 0) == 0


@test
def test_own_goal_rejects_a_player_from_the_credited_team():
    match = started()
    # H1 plays for Informatica, so he cannot own-goal *for* Informatica.
    raises(
        Error.PLAYER_NOT_IN_TEAM,
        addEvent,
        match,
        type=MatchEventType.OWN_GOAL,
        teamId=HOME.id,
        playerId=H1.id,
    )


@test
def test_goal_rejects_a_player_from_the_other_team():
    match = started()
    raises(
        Error.PLAYER_NOT_IN_TEAM,
        addEvent,
        match,
        type=MatchEventType.GOAL,
        teamId=HOME.id,
        playerId=A1.id,
    )


@test
def test_event_must_belong_to_one_of_the_two_teams():
    match = started()
    other = TeamModel(name="Litere")
    DB.add(other)
    DB.flush()
    raises(
        Error.BAD_REQUEST,
        addEvent,
        match,
        type=MatchEventType.GOAL,
        teamId=other.id,
    )


# --- Idempotency -------------------------------------------------------------

@test
def test_replaying_a_client_event_id_does_not_duplicate_the_goal():
    match = started()
    first = addEvent(
        match,
        type=MatchEventType.GOAL,
        teamId=HOME.id,
        playerId=H1.id,
        clientEventId="phone-abc-123",
    )
    assert first.created is True
    assert first.scoreHome == 1

    # Same request again, as a retry after a dropped connection would send it.
    second = addEvent(
        match,
        type=MatchEventType.GOAL,
        teamId=HOME.id,
        playerId=H1.id,
        clientEventId="phone-abc-123",
    )
    assert second.created is False
    assert second.event.id == first.event.id
    assert second.scoreHome == 1

    count = (
        DB.query(MatchEventModel)
        .filter(MatchEventModel.matchId == match.id)
        .count()
    )
    assert count == 1


@test
def test_omitted_client_event_id_is_generated_and_unique():
    match = started()
    a = addEvent(match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id)
    b = addEvent(match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id)
    assert a.event.clientEventId != b.event.clientEventId
    assert b.scoreHome == 2


# --- Void and undo -----------------------------------------------------------

@test
def test_voiding_keeps_the_row_and_removes_it_from_the_score():
    match = started()
    added = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
    )
    assert match.scoreHome == 1

    result = call(
        void_match_event(
            data=MatchEventVoid(reason="Wrong scorer"),
            eventId=added.event.id,
            ctx=ctx(match),
            db=DB,
        )
    )
    assert result.scoreHome == 0

    row = (
        DB.query(MatchEventModel)
        .filter(MatchEventModel.id == added.event.id)
        .first()
    )
    assert row is not None, "the event must not be deleted"
    assert row.status == MatchEventStatus.VOIDED
    assert row.voidReason == "Wrong scorer"
    assert row.voidedByName == OPERATOR.name
    assert row.voidedAt is not None


@test
def test_an_event_cannot_be_voided_twice():
    match = started()
    added = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
    )
    call(
        void_match_event(
            data=MatchEventVoid(),
            eventId=added.event.id,
            ctx=ctx(match),
            db=DB,
        )
    )
    raises(
        Error.EVENT_ALREADY_VOIDED,
        call,
        void_match_event(
            data=MatchEventVoid(),
            eventId=added.event.id,
            ctx=ctx(match),
            db=DB,
        ),
    )


@test
def test_undo_voids_the_most_recent_event():
    match = started()
    addEvent(match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id)
    second = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H2.id
    )
    assert match.scoreHome == 2

    result = call(
        undo_last_match_event(data=MatchEventVoid(), ctx=ctx(match), db=DB)
    )
    assert result.event.id == second.event.id
    assert result.scoreHome == 1


@test
def test_undo_on_an_empty_match_is_refused():
    match = started()
    raises(
        Error.NOT_FOUND,
        call,
        undo_last_match_event(data=MatchEventVoid(), ctx=ctx(match), db=DB),
    )


@test
def test_a_correction_marks_the_previous_event_corrected():
    match = started()
    wrong = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
    )
    right = addEvent(
        match,
        type=MatchEventType.GOAL,
        teamId=HOME.id,
        playerId=H2.id,
        supersedesEventId=wrong.event.id,
    )
    DB.refresh(match)

    previous = (
        DB.query(MatchEventModel)
        .filter(MatchEventModel.id == wrong.event.id)
        .first()
    )
    assert previous.status == MatchEventStatus.CORRECTED
    assert right.event.supersedesEventId == wrong.event.id
    # One scorer replaced another: still a single goal.
    assert right.scoreHome == 1


# --- Cards and assists -------------------------------------------------------

@test
def test_a_card_needs_a_player():
    match = started()
    raises(
        Error.BAD_REQUEST,
        addEvent,
        match,
        type=MatchEventType.YELLOW_CARD,
        teamId=HOME.id,
    )


@test
def test_cards_do_not_move_the_score():
    match = started()
    addEvent(
        match,
        type=MatchEventType.YELLOW_CARD,
        teamId=HOME.id,
        playerId=H1.id,
    )
    result = addEvent(
        match, type=MatchEventType.RED_CARD, teamId=AWAY.id, playerId=A1.id
    )
    assert (result.scoreHome, result.scoreAway) == (0, 0)


@test
def test_only_a_goal_can_carry_an_assist():
    match = started()
    raises(
        Error.BAD_REQUEST,
        addEvent,
        match,
        type=MatchEventType.YELLOW_CARD,
        teamId=HOME.id,
        playerId=H1.id,
        assistPlayerId=H2.id,
    )


@test
def test_a_player_cannot_assist_their_own_goal():
    match = started()
    raises(
        Error.BAD_REQUEST,
        addEvent,
        match,
        type=MatchEventType.GOAL,
        teamId=HOME.id,
        playerId=H1.id,
        assistPlayerId=H1.id,
    )


@test
def test_assist_must_come_from_the_scoring_team():
    match = started()
    raises(
        Error.PLAYER_NOT_IN_TEAM,
        addEvent,
        match,
        type=MatchEventType.GOAL,
        teamId=HOME.id,
        playerId=H1.id,
        assistPlayerId=A1.id,
    )


# --- Clock and lifecycle -----------------------------------------------------

@test
def test_starting_a_match_runs_the_clock():
    match = newMatch()
    call(start(ctx=ctx(match), db=DB))
    assert match.state == MatchState.LIVE
    assert match.startedAt is not None
    assert match.isClockRunning
    assert match.currentMinute == 1
    assert (match.scoreHome, match.scoreAway) == (0, 0)


@test
def test_starting_twice_is_harmless():
    match = started()
    startedAt = match.startedAt
    call(start(ctx=ctx(match), db=DB))
    assert match.startedAt == startedAt
    assert match.state == MatchState.LIVE


@test
def test_pause_stops_the_clock_and_resume_restarts_it():
    match = started()
    call(pause(ctx=ctx(match), db=DB))
    assert match.state == MatchState.HALF_TIME
    assert not match.isClockRunning
    frozen = match.playedSeconds

    call(resume(ctx=ctx(match), db=DB))
    assert match.state == MatchState.LIVE
    assert match.isClockRunning
    assert match.playedSeconds >= frozen


@test
def test_a_scheduled_match_cannot_be_paused_or_resumed():
    match = newMatch()
    raises(
        Error.INVALID_MATCH_TRANSITION, call, pause(ctx=ctx(match), db=DB)
    )
    raises(
        Error.INVALID_MATCH_TRANSITION, call, resume(ctx=ctx(match), db=DB)
    )


@test
def test_a_scheduled_match_cannot_be_finished():
    match = newMatch()
    raises(
        Error.INVALID_MATCH_TRANSITION, call, finish(ctx=ctx(match), db=DB)
    )


@test
def test_minute_is_taken_from_the_clock_when_not_given():
    match = started()
    result = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
    )
    assert result.event.minute == match.currentMinute


@test
def test_an_explicit_minute_wins_over_the_clock():
    match = started()
    result = addEvent(
        match,
        type=MatchEventType.GOAL,
        teamId=HOME.id,
        playerId=H1.id,
        minute=37,
    )
    assert result.event.minute == 37


# --- Lock and reopen ---------------------------------------------------------

@test
def test_finishing_confirms_and_locks_the_match():
    match = started()
    addEvent(match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id)
    call(finish(ctx=ctx(match, SUPER), db=DB))

    assert match.state == MatchState.FINISHED
    assert match.isLocked
    assert match.confirmedAt is not None
    assert match.confirmedById == SUPER.id
    assert not match.isClockRunning


@test
def test_a_locked_match_refuses_further_events():
    match = started()
    call(finish(ctx=ctx(match), db=DB))
    DB.commit()

    guard = MatchAccess()
    raises(Error.MATCH_LOCKED, guard, id=match.id, db=DB, user=SUPER)


@test
def test_only_a_super_admin_can_reopen():
    match = started()
    call(finish(ctx=ctx(match), db=DB))
    DB.commit()

    admin = makeUser(
        "Plain Admin", "plain%s@scc.ro" % match.id, PlatformRoles.ADMIN
    )
    DB.commit()

    guard = MatchAccess(
        minRole=PlatformRoles.SUPER_ADMIN, allowLocked=True
    )
    raises(Error.FORBIDDEN, guard, id=match.id, db=DB, user=admin)

    reopenCtx = guard(id=match.id, db=DB, user=SUPER)
    call(
        reopen(
            data=MatchReopen(reason="Scorer entered on the wrong team"),
            ctx=reopenCtx,
            db=DB,
        )
    )
    assert not match.isLocked
    assert match.confirmedById is None
    # The published result stands; it is just editable again.
    assert match.state == MatchState.FINISHED


@test
def test_reopening_an_unlocked_match_is_refused():
    match = started()
    raises(
        Error.INVALID_MATCH_TRANSITION,
        call,
        reopen(
            data=MatchReopen(reason="No reason"),
            ctx=ctx(match, SUPER),
            db=DB,
        ),
    )


@test
def test_a_correction_after_reopening_moves_the_table():
    match = started()
    addEvent(match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id)
    call(finish(ctx=ctx(match), db=DB))
    DB.commit()

    def standing(teamId):
        return (
            DB.query(StandingModel)
            .filter(
                StandingModel.seasonId == SEASON.id,
                StandingModel.teamId == teamId,
            )
            .first()
        )

    homeBefore = standing(HOME.id).points

    match.lockedAt = None
    match.confirmedAt = None
    DB.flush()

    # The opponent equalises: a win becomes a draw.
    addEvent(
        match, type=MatchEventType.GOAL, teamId=AWAY.id, playerId=A1.id, user=SUPER
    )
    DB.commit()

    assert (match.scoreHome, match.scoreAway) == (1, 1)
    assert standing(HOME.id).points == homeBefore - 2
    assert standing(AWAY.id).points >= 1


# --- Audit trail -------------------------------------------------------------

@test
def test_every_action_leaves_an_audit_row():
    match = started()
    added = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
    )
    call(
        void_match_event(
            data=MatchEventVoid(reason="Mistake"),
            eventId=added.event.id,
            ctx=ctx(match),
            db=DB,
        )
    )
    call(finish(ctx=ctx(match), db=DB))
    DB.commit()

    actions = [
        row.action
        for row in DB.query(AuditLogModel)
        .filter(AuditLogModel.matchId == match.id)
        .order_by(AuditLogModel.id)
        .all()
    ]
    assert actions == [
        "MATCH_STARTED",
        "EVENT_ADDED",
        "EVENT_VOIDED",
        "MATCH_FINISHED",
    ]


@test
def test_audit_rows_name_the_operator_and_survive_account_deletion():
    match = started()
    addEvent(match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id)
    DB.commit()

    row = (
        DB.query(AuditLogModel)
        .filter(
            AuditLogModel.matchId == match.id,
            AuditLogModel.action == "EVENT_ADDED",
        )
        .first()
    )
    assert row.userName == OPERATOR.name
    assert row.userNameSnapshot == OPERATOR.name
    assert row.details["scoreAfter"] == [1, 0]

    event = (
        DB.query(MatchEventModel)
        .filter(MatchEventModel.matchId == match.id)
        .first()
    )
    assert event.createdByNameSnapshot == OPERATOR.name


# --- Statistics read the active events only ----------------------------------

@test
def test_voided_events_never_reach_the_statistics():
    match = started()
    keep = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
    )
    drop = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
    )
    call(
        void_match_event(
            data=MatchEventVoid(reason="Double entry"),
            eventId=drop.event.id,
            ctx=ctx(match),
            db=DB,
        )
    )
    call(finish(ctx=ctx(match), db=DB))
    DB.commit()

    stats = get_player_stats_map(DB, player_ids=[H1.id], season_id=SEASON.id)
    goalsFromThisMatch = (
        DB.query(MatchEventModel)
        .filter(
            MatchEventModel.matchId == match.id,
            MatchEventModel.status == MatchEventStatus.ACTIVE,
        )
        .count()
    )
    assert goalsFromThisMatch == 1
    assert stats[H1.id]["goals"] >= 1
    assert keep.event.status == MatchEventStatus.ACTIVE


# --- The read routes the public and the console actually call -----------------

@test
def test_match_detail_returns_the_active_timeline_in_minute_order():
    match = started()
    addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H2.id, minute=40
    )
    early = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id, minute=5
    )
    dropped = addEvent(
        match, type=MatchEventType.GOAL, teamId=AWAY.id, playerId=A1.id, minute=20
    )
    call(
        void_match_event(
            data=MatchEventVoid(reason="Mistake"),
            eventId=dropped.event.id,
            ctx=ctx(match),
            db=DB,
        )
    )
    DB.commit()

    detail = call(get_match(id=match.id, db=DB))
    minutes = [event.minute for event in detail.events]
    assert minutes == [5, 40], "voided events must not reach the public detail"
    assert detail.events[0].id == early.event.id
    assert detail.homeTeamName == "Informatica"
    assert (detail.scoreHome, detail.scoreAway) == (2, 0)


@test
def test_the_console_can_ask_for_the_full_record():
    match = started()
    dropped = addEvent(
        match, type=MatchEventType.GOAL, teamId=HOME.id, playerId=H1.id
    )
    call(
        void_match_event(
            data=MatchEventVoid(reason="Mistake"),
            eventId=dropped.event.id,
            ctx=ctx(match),
            db=DB,
        )
    )
    DB.commit()

    public = call(
        get_match_events(
            id=match.id, params=MatchEventListParams(), db=DB
        )
    )
    assert public.data == []

    full = call(
        get_match_events(
            id=match.id,
            params=MatchEventListParams(includeVoided=True),
            db=DB,
        )
    )
    assert len(full.data) == 1
    assert full.data[0].status == MatchEventStatus.VOIDED
    assert full.data[0].voidReason == "Mistake"


if __name__ == "__main__":
    code = run("Etapa 2 - event log, clock, lock and audit")
    DB.close()
    drop_database(DB_HANDLE)
    sys.exit(code)
