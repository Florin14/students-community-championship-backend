"""Calendar persistence, inclusive phases, validation and migration compatibility."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import call, drop_database, fresh_database, run, test

DB_URL, DB_HANDLE = fresh_database()

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, text
from extensions.sqlalchemy import SessionLocal, engine
from constants import MatchState
from modules.match.models import MatchModel, MatchResponse
from modules.match.routes.get_live_matches import _revision
from modules.season.models import SeasonAdd, SeasonModel, SeasonResponse, SeasonUpdate
from modules.season.routes.add_season import add_season
from modules.season.routes.update_season import update_season
from modules.team.models import TeamModel

DB = SessionLocal()
HOME = TeamModel(name="Calendar Home")
AWAY = TeamModel(name="Calendar Away")
DB.add_all([HOME, AWAY])
DB.commit()


def period(start, end, label, phase="LEAGUE", round=None, isBreak=False):
    return dict(startDate=start, endDate=end, label=label, phase=phase, round=round, isBreak=isBreak)


CALENDAR = [
    period("2026-11-30", "2026-12-01", "FREE WEEK", isBreak=True),
    period("2026-12-07", "2026-12-08", "Stage 6", round=6),
    period("2027-01-11", "2027-01-12", "Stage 8", round=8),
    period("2027-04-26", "2027-04-27", "SEMI-FINALS – 2ND LEG", phase="SEMIFINALS"),
    period("2027-05-15", "2027-05-15", "FINAL", phase="FINAL"),
]


@test
def test_calendar_round_trip_sorts_dates_and_keeps_names():
    season = call(add_season(SeasonAdd(name="Calendar sorted", calendar=list(reversed(CALENDAR))), db=DB))
    DB.expire_all()
    response = SeasonResponse.model_validate(DB.get(SeasonModel, season.id))
    assert [item.model_dump(mode="json") for item in response.calendar] == CALENDAR


@test
def test_updates_preserve_omitted_calendar_and_allow_explicit_clear():
    season = call(add_season(SeasonAdd(name="Calendar updates", calendar=CALENDAR), db=DB))
    call(update_season(SeasonUpdate(description="Updated"), season=season, db=DB))
    assert season.calendar == CALENDAR
    call(update_season(SeasonUpdate(calendar=[]), season=season, db=DB))
    assert season.calendar == []


@test
def test_invalid_ranges_overlaps_and_break_rounds_are_rejected():
    invalid = [
        [period("2026-12-08", "2026-12-07", "Reversed")],
        [period("2026-12-07", "2026-12-08", "First"), period("2026-12-08", "2026-12-09", "Overlapping")],
        [period("2026-12-07", "2026-12-08", "Break", round=1, isBreak=True)],
        [period("2026-12-07", "2026-12-08", "   ")],
        [period("2026-12-07", "2026-12-08", "Wrong phase", phase="UNKNOWN")],
        [period("2026-12-07", "2026-12-08", "Boolean round", round=True)],
        [period("2026-12-07", "2026-12-08", "Fractional round", round=1.5)],
    ]
    for calendar in invalid:
        for schema, values in ((SeasonAdd, dict(name="Invalid", calendar=calendar)), (SeasonUpdate, dict(calendar=calendar))):
            try:
                schema(**values)
            except ValidationError:
                pass
            else:
                raise AssertionError("Invalid calendar accepted: %s" % calendar)


@test
def test_calendar_label_uses_inclusive_dates_for_unnumbered_phases_only():
    season = call(add_season(SeasonAdd(name="Phase dates", calendar=CALENDAR), db=DB))
    for timestamp, expected in (
        (datetime(2027, 4, 26, 0, 0), "SEMI-FINALS – 2ND LEG"),
        (datetime(2027, 4, 27, 23, 59), "SEMI-FINALS – 2ND LEG"),
        (datetime(2027, 4, 28, 0, 0), None),
        (datetime(2026, 11, 30, 12, 0), None),
        (datetime(2026, 12, 7, 12, 0), None),
        (datetime(2027, 5, 15, 23, 59), "FINAL"),
    ):
        match = MatchModel(season=season, homeTeamId=HOME.id, awayTeamId=AWAY.id, timestamp=timestamp)
        DB.add(match)
        DB.commit()
        assert MatchResponse.model_validate(match).calendarLabel == expected


@test
def test_calendar_updates_do_not_rewrite_existing_results_or_rounds():
    season = call(add_season(SeasonAdd(name="Keep results", calendar=CALENDAR), db=DB))
    match = MatchModel(season=season, homeTeamId=HOME.id, awayTeamId=AWAY.id,
                       timestamp=datetime(2027, 5, 15, 12, 0), round=8,
                       scoreHome=2, scoreAway=1, state=MatchState.FINISHED)
    DB.add(match)
    DB.commit()
    renamed = [dict(item, label="Updated final") if item["phase"] == "FINAL" else item for item in CALENDAR]
    call(update_season(SeasonUpdate(calendar=renamed), season=season, db=DB))
    DB.refresh(match)
    assert (match.round, match.scoreHome, match.scoreAway, match.state) == (8, 2, 1, MatchState.FINISHED)
    assert match.calendarLabel == "Updated final"


@test
def test_calendar_labels_change_the_live_revision():
    season = call(add_season(SeasonAdd(name="Live phase", calendar=CALENDAR), db=DB))
    match = MatchModel(season=season, homeTeamId=HOME.id, awayTeamId=AWAY.id,
                       timestamp=datetime(2027, 5, 15, 12, 0), state=MatchState.LIVE)
    DB.add(match)
    DB.commit()
    match.attendanceHome = match.attendanceAway = 0
    before = _revision([match])
    call(update_season(SeasonUpdate(calendar=[]), season=season, db=DB))
    assert _revision([match]) != before


@test
def test_calendar_limits_and_legacy_seasons():
    legacy = call(add_season(SeasonAdd(name="Legacy calendar payload"), db=DB))
    assert SeasonResponse.model_validate(legacy).calendar == []
    for values in (dict(calendar=None), dict(calendar=[period("2026-12-07", "2026-12-08", "x" * 161)])):
        try:
            SeasonUpdate(**values)
        except ValidationError:
            pass
        else:
            raise AssertionError("Invalid calendar limit was accepted")


@test
def test_migration_preserves_existing_seasons_and_matches():
    DB.close()
    config = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
    command.downgrade(config, "f52c18a794bd")
    assert "calendar" not in {column["name"] for column in inspect(engine).get_columns("seasons")}
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO seasons (name, is_active) VALUES ('Before calendar migration', false)"))
    command.upgrade(config, "head")
    with SessionLocal() as session:
        old = session.query(SeasonModel).filter_by(name="Before calendar migration").one()
        assert old.calendar == []
        assert session.query(MatchModel).count() > 0


if __name__ == "__main__":
    try:
        code = run("Season competition calendar")
    finally:
        DB.close()
        drop_database(DB_HANDLE)
    sys.exit(code)
