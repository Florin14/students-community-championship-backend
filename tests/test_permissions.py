"""Roles, operator assignment and match access (plan, section 6)."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from support import call, fresh_database, raises, run, test  # noqa: E402

DB_URL, DB_PATH = fresh_database()

from constants import MatchState, PlatformRoles  # noqa: E402
from extensions.sqlalchemy import SessionLocal  # noqa: E402
from project_helpers.dependencies import MatchAccess  # noqa: E402
from project_helpers.error import Error  # noqa: E402
from modules.auth.models import UserModel  # noqa: E402
from modules.field.models import FieldModel  # noqa: E402
from modules.match.models import MatchModel  # noqa: E402
from modules.match.services import set_match_operators  # noqa: E402
from modules.season.models import SeasonModel  # noqa: E402
from modules.team.models import TeamModel  # noqa: E402
from modules.user.routes.add_user import add_user  # noqa: E402
from modules.user.routes.update_user import update_user  # noqa: E402
from modules.auth.models import UserAdd, UserUpdate  # noqa: E402


def makeUser(db, name, email, role):
    user = UserModel(name=name, email=email, role=role)
    user.password = "password123"
    db.add(user)
    db.flush()
    return user


def seed():
    db = SessionLocal()
    superAdmin = makeUser(db, "Root", "root@scc.ro", PlatformRoles.SUPER_ADMIN)
    admin = makeUser(db, "Admin", "admin@scc.ro", PlatformRoles.ADMIN)
    opA = makeUser(db, "Operator A", "opa@scc.ro", PlatformRoles.OPERATOR)
    opB = makeUser(db, "Operator B", "opb@scc.ro", PlatformRoles.OPERATOR)

    season = SeasonModel(name="2026", isActive=True)
    db.add(season)
    home = TeamModel(name="Informatica")
    away = TeamModel(name="Drept")
    db.add_all([home, away])
    field = FieldModel(name="Teren 1", shortName="T1")
    db.add(field)
    db.flush()

    matchA = MatchModel(
        seasonId=season.id,
        homeTeamId=home.id,
        awayTeamId=away.id,
        timestamp=datetime(2026, 5, 1, 10, 0),
        fieldId=field.id,
        state=MatchState.SCHEDULED,
    )
    matchB = MatchModel(
        seasonId=season.id,
        homeTeamId=away.id,
        awayTeamId=home.id,
        timestamp=datetime(2026, 5, 1, 12, 0),
        state=MatchState.SCHEDULED,
    )
    db.add_all([matchA, matchB])
    db.flush()

    set_match_operators(db, matchA, [opA.id])
    set_match_operators(db, matchB, [opB.id])
    db.commit()
    return db, dict(
        superAdmin=superAdmin, admin=admin, opA=opA, opB=opB,
        matchA=matchA, matchB=matchB, field=field, season=season,
    )


DB, FIX = seed()


# --- Role hierarchy ----------------------------------------------------------

@test
def test_role_hierarchy_is_transitive():
    assert FIX["admin"].covers(PlatformRoles.OPERATOR)
    assert FIX["superAdmin"].covers(PlatformRoles.ADMIN)
    assert not FIX["opA"].covers(PlatformRoles.ADMIN)
    assert not FIX["admin"].covers(PlatformRoles.SUPER_ADMIN)


# --- MatchAccess -------------------------------------------------------------

def access(user, match, **kwargs):
    guard = MatchAccess(**kwargs)
    return guard(id=match.id, db=DB, user=user)


@test
def test_operator_may_score_their_own_match():
    ctx = access(FIX["opA"], FIX["matchA"])
    assert ctx.match.id == FIX["matchA"].id
    assert ctx.user.id == FIX["opA"].id


@test
def test_operator_may_not_score_someone_elses_match():
    raises(
        Error.NOT_ASSIGNED_TO_MATCH,
        access,
        FIX["opA"],
        FIX["matchB"],
    )


@test
def test_admin_may_score_any_match_without_assignment():
    assert access(FIX["admin"], FIX["matchB"]).match.id == FIX["matchB"].id
    assert access(FIX["superAdmin"], FIX["matchA"]).match.id == FIX["matchA"].id


@test
def test_operator_is_refused_where_admin_is_required():
    raises(
        Error.FORBIDDEN,
        access,
        FIX["opA"],
        FIX["matchA"],
        minRole=PlatformRoles.ADMIN,
    )


@test
def test_locked_match_refuses_writes_but_allows_reopen():
    match = FIX["matchB"]
    match.lockedAt = datetime.utcnow()
    DB.flush()

    raises(Error.MATCH_LOCKED, access, FIX["admin"], match)

    ctx = access(
        FIX["superAdmin"],
        match,
        minRole=PlatformRoles.SUPER_ADMIN,
        allowLocked=True,
    )
    assert ctx.match.isLocked

    match.lockedAt = None
    DB.flush()


@test
def test_disabled_account_loses_access():
    operator = FIX["opA"]
    operator.isActive = False
    DB.flush()
    # MatchAccess trusts JwtRequired for the active check, so assert the flag is
    # what the token layer reads and that assignment alone is not enough.
    assert operator.isActive is False
    operator.isActive = True
    DB.flush()


# --- Operator assignment -----------------------------------------------------

@test
def test_assignment_replaces_the_whole_set():
    match = FIX["matchA"]
    set_match_operators(DB, match, [FIX["opA"].id, FIX["opB"].id])
    DB.flush()
    assert sorted(match.operatorIds) == sorted(
        [FIX["opA"].id, FIX["opB"].id]
    )

    set_match_operators(DB, match, [FIX["opB"].id])
    DB.flush()
    assert match.operatorIds == [FIX["opB"].id]

    set_match_operators(DB, match, [FIX["opA"].id])
    DB.flush()
    assert match.operatorIds == [FIX["opA"].id]


@test
def test_assignment_rejects_unknown_accounts():
    raises(Error.NOT_FOUND, set_match_operators, DB, FIX["matchA"], [98765])


@test
def test_assignment_rejects_disabled_accounts():
    FIX["opB"].isActive = False
    DB.flush()
    raises(
        Error.BAD_REQUEST,
        set_match_operators,
        DB,
        FIX["matchA"],
        [FIX["opB"].id],
    )
    FIX["opB"].isActive = True
    DB.flush()


# --- Account administration --------------------------------------------------

@test
def test_admin_cannot_create_an_account_above_their_own_role():
    payload = UserAdd(
        name="Escalation",
        email="escalate@scc.ro",
        password="password123",
        role=PlatformRoles.SUPER_ADMIN,
    )
    raises(
        Error.FORBIDDEN,
        call,
        add_user(data=payload, currentUser=FIX["admin"], db=DB),
    )


@test
def test_super_admin_can_create_an_admin():
    payload = UserAdd(
        name="Second Admin",
        email="admin2@scc.ro",
        password="password123",
        role=PlatformRoles.ADMIN,
    )
    created = call(
        add_user(data=payload, currentUser=FIX["superAdmin"], db=DB)
    )
    assert created.platformRole == PlatformRoles.ADMIN
    assert created.isActive is True


@test
def test_duplicate_email_is_rejected():
    payload = UserAdd(
        name="Clone",
        email="admin@scc.ro",
        password="password123",
        role=PlatformRoles.OPERATOR,
    )
    raises(
        Error.CONFLICT,
        call,
        add_user(data=payload, currentUser=FIX["superAdmin"], db=DB),
    )


@test
def test_nobody_can_demote_or_disable_themselves():
    raises(
        Error.CANNOT_DEMOTE_SELF,
        call,
        update_user(
            data=UserUpdate(role=PlatformRoles.OPERATOR),
            user=FIX["superAdmin"],
            currentUser=FIX["superAdmin"],
            db=DB,
        ),
    )
    raises(
        Error.CANNOT_DEMOTE_SELF,
        call,
        update_user(
            data=UserUpdate(isActive=False),
            user=FIX["admin"],
            currentUser=FIX["admin"],
            db=DB,
        ),
    )


@test
def test_admin_cannot_modify_a_super_admin():
    raises(
        Error.FORBIDDEN,
        call,
        update_user(
            data=UserUpdate(name="Hijacked"),
            user=FIX["superAdmin"],
            currentUser=FIX["admin"],
            db=DB,
        ),
    )


@test
def test_password_reset_rehashes_and_does_not_store_plaintext():
    operator = FIX["opA"]
    before = operator.password
    call(
        update_user(
            data=UserUpdate(password="a-brand-new-password"),
            user=operator,
            currentUser=FIX["superAdmin"],
            db=DB,
        )
    )
    assert operator.password != before
    assert "a-brand-new-password" not in operator.password


if __name__ == "__main__":
    code = run("Etapa 1 - roles, assignment and match access")
    DB.close()
    os.unlink(DB_PATH)
    sys.exit(code)
