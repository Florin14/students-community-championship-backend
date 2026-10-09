"""University metadata round trips, partial updates and migration compatibility."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import call, drop_database, fresh_database, run, test

DB_URL, DB_HANDLE = fresh_database()

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import inspect, text

from extensions.sqlalchemy import SessionLocal, engine
from modules.team.models import TeamAdd, TeamListParams, TeamModel, TeamResponse, TeamUpdate
from modules.team.routes.add_team import add_team
from modules.team.routes.get_all_teams import get_teams
from modules.team.routes.update_team import update_team

DB = SessionLocal()


@test
def test_university_and_faculty_are_saved_and_returned_separately():
    team = call(add_team(TeamAdd(
        name="Metadata round trip", university="Universitatea din București",
        faculty="Facultatea de Matematică",
    ), db=DB))
    DB.expire_all()
    saved = TeamResponse.model_validate(DB.get(TeamModel, team.id))
    assert saved.university == "Universitatea din București"
    assert saved.faculty == "Facultatea de Matematică"


@test
def test_partial_updates_preserve_university_and_explicit_null_clears_it():
    team = call(add_team(TeamAdd(name="Partial update", university="Original", faculty="Faculty"), db=DB))
    call(update_team(TeamUpdate(shortName="PART"), team=team, db=DB))
    assert team.university == "Original"
    call(update_team(TeamUpdate(university="Updated"), team=team, db=DB))
    assert team.university == "Updated" and team.faculty == "Faculty"
    call(update_team(TeamUpdate(university=None), team=team, db=DB))
    assert team.university is None and team.faculty == "Faculty"


@test
def test_existing_payloads_do_not_require_a_university():
    team = call(add_team(TeamAdd(name="Legacy payload", faculty="Legacy faculty"), db=DB))
    assert TeamResponse.model_validate(team).university is None


@test
def test_team_search_includes_university_and_faculty():
    call(add_team(TeamAdd(name="Searchable", university="Distinct university", faculty="Distinct faculty"), db=DB))
    for term in ("searchable", "distinct university", "distinct faculty"):
        found = call(get_teams(params=TeamListParams(search=term), db=DB)).data
        assert [team.name for team in found] == ["Searchable"]
    assert call(get_teams(params=TeamListParams(search="missing university"), db=DB)).data == []


@test
def test_university_length_is_validated_before_writing():
    for schema, data in ((TeamAdd, {"name": "Length", "university": "X" * 161}),
                         (TeamUpdate, {"university": "X" * 161})):
        try:
            schema(**data)
        except ValidationError:
            pass
        else:
            raise AssertionError("University longer than 160 characters was accepted")


@test
def test_migration_preserves_existing_teams_and_restores_nullable_column():
    DB.close()
    config = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
    command.downgrade(config, "e94b3128f560")
    assert "university" not in {column["name"] for column in inspect(engine).get_columns("teams")}
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO teams (name, faculty) VALUES ('Before university migration', 'Preserved faculty')"))
    command.upgrade(config, "head")
    with SessionLocal() as session:
        legacy = session.query(TeamModel).filter_by(name="Before university migration").one()
        assert legacy.university is None and legacy.faculty == "Preserved faculty"


if __name__ == "__main__":
    try:
        code = run("Team university metadata")
    finally:
        DB.close()
        drop_database(DB_HANDLE)
    sys.exit(code)
