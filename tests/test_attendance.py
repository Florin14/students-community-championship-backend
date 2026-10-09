"""Attendance permissions, QR validation, concurrency and season statistics.

Exercises the real HTTP routes with stdlib urllib; no extra test dependency.
"""
import asyncio
import base64
import io
import json
import os
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support import call, drop_database, fresh_database, run, test

DB_URL, DB_HANDLE = fresh_database()

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from PIL import Image

from constants import AttendanceStatus, MatchState, PlatformRoles
from extensions.sqlalchemy import SessionLocal, engine
from modules.attendance.models import AttendanceModel, AttendanceStatsParams
from modules.attendance.services import attendance_stats, attendance_summary, confirm_attendance
from modules.audit.models import AuditLogModel
from modules.auth.models import UserModel
from modules.match.models import MatchModel, MatchOperatorModel
from modules.player.models import PlayerModel, PlayerUpdate
from modules.player.routes.update_player import update_player
from modules.player.services import attach_player_stats
from modules.season.models import SeasonModel, SeasonTeamModel
from modules.team.models import TeamModel
from project_helpers.functions import create_access_token
from project_helpers.exceptions import ErrorException
from services.run_api import api

DB = SessionLocal()
ADMIN = UserModel(name="Admin", email="attendance.admin@scc.ro", role=PlatformRoles.ADMIN)
OPERATOR_A = UserModel(name="Operator A", email="attendance.operator.a@scc.ro", role=PlatformRoles.OPERATOR)
OPERATOR = UserModel(name="Operator", email="attendance.operator@scc.ro", role=PlatformRoles.OPERATOR)
for user in (ADMIN, OPERATOR_A, OPERATOR):
    user.password = "password123"
DB.add_all([ADMIN, OPERATOR_A, OPERATOR])
HOME = TeamModel(name="Attendance Home")
AWAY = TeamModel(name="Attendance Away")
OTHER = TeamModel(name="Attendance Other")
SEASON = SeasonModel(name="Attendance 2026", isActive=True)
SEASON2 = SeasonModel(name="Attendance 2027")
DB.add_all([HOME, AWAY, OTHER, SEASON, SEASON2])
DB.flush()
for season in (SEASON, SEASON2):
    for team in (HOME, AWAY, OTHER):
        DB.add(SeasonTeamModel(seasonId=season.id, teamId=team.id))
DB.commit()
AUTH = {user.id: create_access_token(user.get_claims()) for user in (ADMIN, OPERATOR_A, OPERATOR)}

with socket.socket() as free_port:
    free_port.bind(("127.0.0.1", 0))
    PORT = free_port.getsockname()[1]
SERVER = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=PORT, log_level="error"))
THREAD = threading.Thread(target=SERVER.run, daemon=True)
THREAD.start()
for attempt in range(100):
    if SERVER.started:
        break
    time.sleep(0.05)
else:
    raise RuntimeError("The test API did not start")

_sequence = [0]


def request(method, path, data=None, user=OPERATOR_A, token=None):
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    elif user is not None:
        headers["Authorization"] = "Bearer " + AUTH[user.id]
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = Request("http://127.0.0.1:%s%s" % (PORT, path), data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as error:
        return error.code, json.loads(error.read())


def fixture(team=HOME, season=SEASON, photo=True):
    _sequence[0] += 1
    player = PlayerModel(name="Attendance player %s" % _sequence[0], teamId=team.id, avatar=b"cGhvdG8=" if photo else None)
    match = MatchModel(seasonId=season.id, homeTeamId=HOME.id, awayTeamId=AWAY.id, timestamp=datetime(2026, 10, 10, 10))
    DB.add_all([player, match])
    DB.commit()
    return player, match


def qr(player, season=SEASON, regenerate=False):
    status, payload = request("POST", "/players/%s/qr" % player.id, {"seasonId": season.id, "regenerate": regenerate}, user=ADMIN)
    assert status == 200, payload
    return payload["token"]


def confirm(match, token, user=OPERATOR_A):
    return request("POST", "/attendance/matches/%s/confirm" % match.id, {"token": token, "identityConfirmed": True}, user=user)


def expect_error(response, status, code):
    actual_status, payload = response
    assert actual_status == status, payload
    assert payload["code"] == code, payload


@test
def test_operator_permissions_and_login():
    assert {role.value for role in PlatformRoles} == {"OPERATOR", "ADMIN", "SUPER_ADMIN"}
    assert not PlatformRoles.OPERATOR.covers(PlatformRoles.ADMIN)
    assert PlatformRoles.ADMIN.covers(PlatformRoles.OPERATOR)
    status, payload = request("POST", "/auth/login", {"email": OPERATOR_A.email, "password": "password123"}, user=None)
    assert status == 200 and payload["role"] == "OPERATOR"
    player, match = fixture()
    assert request("GET", "/players/%s" % player.id)[0] == 200
    for path, body in (
        ("/players/%s" % player.id, {"name": "Unauthorized"}),
        ("/teams/%s" % HOME.id, {"name": "Unauthorized"}),
        ("/matches/%s" % match.id, {"round": 99}),
        ("/users/%s" % OPERATOR_A.id, {"role": "ADMIN"}),
    ):
        expect_error(request("PUT", path, body), 403, "E0013")
    assert request("POST", "/matches/%s/start" % match.id, {})[0] == 200
    expect_error(request("POST", "/players/%s/qr" % player.id, {"seasonId": SEASON.id}), 403, "E0013")
    expect_error(request("POST", "/players/%s/qr" % player.id, {"seasonId": SEASON.id}, user=OPERATOR), 403, "E0013")


@test
def test_scan_is_private_and_does_not_mark_attendance():
    player, match = fixture()
    token = qr(player)
    path = "/attendance/matches/%s/scan" % match.id
    expect_error(request("POST", path, {"token": token}, user=None), 401, "E0011")
    status, payload = request("POST", path, {"token": token})
    assert status == 200 and payload["player"]["id"] == player.id
    assert payload["player"]["avatar"] and payload["canConfirm"] and not payload["alreadyPresent"]
    assert DB.query(AttendanceModel).filter_by(matchId=match.id).count() == 0
    expect_error(request("GET", "/auth/me", token=token), 401, "E0012")
    expect_error(request("GET", "/stats/attendance", user=None), 401, "E0011")


@test
def test_photo_is_required_and_identity_confirmation_is_explicit():
    player, match = fixture(photo=False)
    expect_error(request("POST", "/players/%s/qr" % player.id, {"seasonId": SEASON.id}, user=ADMIN), 400, "E0063")
    player.avatar = b"cGhvdG8="
    DB.commit()
    token = qr(player)
    expect_error(request("POST", "/attendance/matches/%s/confirm" % match.id, {"token": token, "identityConfirmed": False}), 400, "E0064")
    assert request("POST", "/attendance/matches/%s/confirm" % match.id, {"token": token, "identityConfirmed": "true"})[0] == 422
    assert DB.query(AttendanceModel).filter_by(matchId=match.id).count() == 0


@test
def test_attendance_is_unique_and_has_audited_operator_identity():
    player, match = fixture()
    token = qr(player)
    status, first = confirm(match, token)
    assert status == 200 and not first["alreadyPresent"]
    status, second = confirm(match, token)
    assert status == 200 and second["alreadyPresent"]
    assert second["attendance"]["id"] == first["attendance"]["id"]
    assert first["attendance"]["confirmedById"] == OPERATOR_A.id
    assert DB.query(AttendanceModel).filter_by(matchId=match.id).count() == 1
    assert DB.query(AuditLogModel).filter_by(matchId=match.id, action="ATTENDANCE_CONFIRMED").count() == 1
    status, roster = request("GET", "/attendance/matches/%s" % match.id)
    assert status == 200 and roster["presentCount"] == 1
    assert any(item["player"]["id"] == player.id and item["isPresent"] for item in roster["data"])


@test
def test_forged_login_and_wrong_season_codes_are_rejected():
    player, match = fixture()
    token = qr(player)
    parts = token.split(".")
    parts[1] = ("A" if parts[1][0] != "A" else "B") + parts[1][1:]
    path = "/attendance/matches/%s/scan" % match.id
    expect_error(request("POST", path, {"token": ".".join(parts)}), 400, "E0060")
    expect_error(request("POST", path, {"token": AUTH[OPERATOR_A.id]}), 400, "E0060")
    expect_error(request("POST", path, {"token": qr(player, SEASON2)}), 400, "E0061")
    other, _ = fixture(team=OTHER)
    expect_error(request("POST", path, {"token": qr(other)}), 400, "E0054")


@test
def test_replacement_revocation_and_transfer_invalidate_old_qr():
    player, match = fixture()
    token = qr(player)
    assert qr(player) == token
    new_token = qr(player, regenerate=True)
    expect_error(confirm(match, token), 400, "E0060")
    assert confirm(match, new_token)[0] == 200
    expect_error(request("POST", "/players/%s/qr/revoke" % player.id, {"seasonId": SEASON.id}), 403, "E0013")
    assert request("POST", "/players/%s/qr/revoke" % player.id, {"seasonId": SEASON.id}, user=ADMIN)[0] == 204
    expect_error(confirm(match, new_token), 400, "E0060")
    third = qr(player, regenerate=True)
    checked = DB.query(AttendanceModel).filter_by(matchId=match.id).one()
    assert request("POST", "/attendance/%s/void" % checked.id, {"reason": "Player transferred"}, user=ADMIN)[0] == 200
    call(update_player(data=PlayerUpdate(teamId=AWAY.id), player=player, db=DB))
    expect_error(confirm(match, third), 400, "E0060")


@test
def test_match_and_team_changes_cannot_invalidate_pending_check_ins():
    player, match = fixture()
    assert confirm(match, qr(player))[0] == 200
    expect_error(request("PUT", "/players/%s" % player.id, {"teamId": AWAY.id}, user=ADMIN), 409, "E0032")
    expect_error(request("PUT", "/matches/%s" % match.id, {"homeTeamId": OTHER.id}, user=ADMIN), 409, "E0032")
    DB.refresh(player)
    DB.refresh(match)
    assert player.teamId == HOME.id and match.homeTeamId == HOME.id


@test
def test_check_in_closes_at_first_kickoff_and_existing_retries_are_safe():
    player, match = fixture()
    token = qr(player)
    assert confirm(match, token)[0] == 200
    late, _ = fixture()
    late_token = qr(late)
    match.startedAt = datetime.utcnow()
    match.state = MatchState.LIVE
    DB.commit()
    expect_error(confirm(match, late_token), 409, "E0062")
    assert confirm(match, token)[1]["alreadyPresent"]
    match.state = MatchState.SCHEDULED
    DB.commit()
    expect_error(confirm(match, late_token), 409, "E0062")


@test
def test_only_admins_can_correct_and_corrections_leave_history():
    player, match = fixture()
    token = qr(player)
    _, first = confirm(match, token)
    attendance_id = first["attendance"]["id"]
    path = "/attendance/%s/void" % attendance_id
    expect_error(request("POST", path, {"reason": "Wrong person"}), 403, "E0013")
    expect_error(request("POST", path, {"reason": "   "}, user=ADMIN), 400, "E0031")
    status, payload = request("POST", path, {"reason": "Wrong person"}, user=ADMIN)
    assert status == 200 and payload["status"] == "VOIDED"
    assert DB.query(AuditLogModel).filter_by(matchId=match.id, action="ATTENDANCE_VOIDED").count() == 1
    assert attendance_summary(DB, player_id=player.id)["totalAttendances"] == 0
    assert confirm(match, token)[1]["attendance"]["id"] == attendance_id
    assert DB.query(AuditLogModel).filter_by(matchId=match.id, action="ATTENDANCE_CONFIRMED").count() == 2


@test
def test_season_statistics_and_profiles_exclude_voided_attendance():
    player, match = fixture()
    token = qr(player)
    _, checked = confirm(match, token)
    _, second_match = fixture(season=SEASON2)
    assert confirm(second_match, qr(player, SEASON2))[0] == 200
    assert attendance_summary(DB, SEASON.id, player_id=player.id)["totalAttendances"] == 1
    assert attendance_summary(DB, SEASON2.id, player_id=player.id)["totalAttendances"] == 1
    attach_player_stats(DB, [player], season_id=SEASON.id)
    assert player.attendanceCount == 1
    assert request("POST", "/attendance/%s/void" % checked["attendance"]["id"], {"reason": "Mistaken check-in"}, user=ADMIN)[0] == 200
    attach_player_stats(DB, [player], season_id=SEASON.id)
    assert player.attendanceCount == 0
    stats = attendance_stats(DB, AttendanceStatsParams(seasonId=SEASON.id, playerId=player.id))
    assert stats.totalAttendances == 0 and stats.data[0].presences == 0
    status, payload = request("GET", "/stats/overview?seasonId=%s" % SEASON2.id, user=None)
    assert status == 200 and payload["attendances"] >= 1


@test
def test_player_deletion_keeps_attendance_snapshots_and_statistics():
    player, match = fixture()
    player_id, player_name = player.id, player.name
    assert confirm(match, qr(player))[0] == 200
    DB.delete(player)
    DB.commit()
    DB.expire_all()
    record = DB.query(AttendanceModel).filter_by(matchId=match.id).one()
    assert record.playerId is None and record.playerIdSnapshot == player_id
    assert record.playerNameSnapshot == player_name
    stats = attendance_stats(DB, AttendanceStatsParams(playerId=player_id))
    assert stats.uniquePlayers == 1 and stats.data[0].name == player_name


@test
def test_simultaneous_confirmations_create_one_attendance_on_postgres():
    if engine.dialect.name != "postgresql":
        return
    player, match = fixture()
    token = qr(player)
    player_id, match_id, operator_id = player.id, match.id, OPERATOR_A.id
    DB.commit()

    def worker():
        session = SessionLocal()
        try:
            local_match = session.query(MatchModel).filter_by(id=match_id).one()
            operator = session.query(UserModel).filter_by(id=operator_id).one()
            result, repeated = confirm_attendance(session, local_match, token, operator, True)
            session.commit()
            return result.id, repeated
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert len({result[0] for result in results}) == 1
    assert sorted(result[1] for result in results) == [False, True]
    assert DB.query(AttendanceModel).filter_by(matchId=match_id, playerIdSnapshot=player_id).count() == 1


@test
def test_transfer_and_confirmation_cannot_both_succeed_on_postgres():
    if engine.dialect.name != "postgresql":
        return
    player, match = fixture()
    token = qr(player)
    player_id, match_id, operator_id = player.id, match.id, OPERATOR_A.id
    away_id = AWAY.id
    DB.commit()
    barrier = threading.Barrier(2)

    def worker(transferring):
        session = SessionLocal()
        try:
            local_player = session.query(PlayerModel).filter_by(id=player_id).one()
            local_match = session.query(MatchModel).filter_by(id=match_id).one()
            operator = session.query(UserModel).filter_by(id=operator_id).one()
            barrier.wait(timeout=5)
            if transferring:
                asyncio.run(update_player(data=PlayerUpdate(teamId=away_id), player=local_player, db=session))
            else:
                confirm_attendance(session, local_match, token, operator, True)
                session.commit()
            return "ok"
        except ErrorException as error:
            session.rollback()
            return error.error.code
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(worker, [False, True]))
    assert outcomes.count("ok") == 1, outcomes
    DB.expire_all()
    check_in = DB.query(AttendanceModel).filter_by(matchId=match_id).first()
    if check_in is not None:
        assert DB.query(PlayerModel).filter_by(id=player_id).one().teamId == check_in.teamId


@test
def test_disabled_operator_loses_attendance_access():
    OPERATOR_A.isActive = False
    DB.commit()
    expect_error(request("GET", "/stats/attendance"), 403, "E0015")
    OPERATOR_A.isActive = True
    DB.commit()


@test
def test_admin_must_supply_a_valid_player_photo_and_cannot_remove_it():
    image = io.BytesIO()
    Image.new("RGB", (20, 20), color="orange").save(image, format="PNG")
    photo = "data:image/png;base64," + base64.b64encode(image.getvalue()).decode("ascii")
    assert request("POST", "/players/", {"name": "Photo required"}, user=ADMIN)[0] == 422
    for empty in (None, ""):
        expect_error(request("POST", "/players/", {"name": "Photo required", "avatar": empty}, user=ADMIN), 400, "E0063")
    expect_error(request("POST", "/players/", {"name": "Invalid photo", "avatar": "not-an-image"}, user=ADMIN), 400, "E0040")
    status, player = request("POST", "/players/", {"name": "With photo", "avatar": photo}, user=ADMIN)
    assert status == 201 and player["avatar"]
    path = "/players/%s" % player["id"]
    status, updated = request("PUT", path, {"name": "Updated with same photo"}, user=ADMIN)
    assert status == 200 and updated["avatar"] == player["avatar"]
    for empty in (None, ""):
        expect_error(request("PUT", path, {"avatar": empty}, user=ADMIN), 400, "E0063")
    assert request("PUT", path, {"avatar": photo})[0] == 403
    legacy, _ = fixture(photo=False)
    legacy_path = "/players/%s" % legacy.id
    expect_error(request("PUT", legacy_path, {"name": "Missing photo"}, user=ADMIN), 400, "E0063")
    assert request("PUT", legacy_path, {"avatar": photo}, user=ADMIN)[0] == 200


@test
def test_operators_can_score_any_open_match():
    player, match = fixture()
    path = "/matches/%s" % match.id
    status, mine = request("GET", "/matches/mine")
    assert status == 200 and any(item["id"] == match.id for item in mine["data"])
    assert any(item["id"] == match.id for item in request("GET", "/matches/mine", user=OPERATOR)[1]["data"])
    assert request("POST", path + "/start", {}, user=OPERATOR)[0] == 200
    assert request("POST", path + "/start", {})[0] == 200
    for kind in ("GOAL", "YELLOW_CARD", "RED_CARD"):
        status, event = request("POST", path + "/events", {"type": kind, "teamId": HOME.id, "playerId": player.id, "minute": 3})
        assert status == 201 and event["event"]["createdById"] == OPERATOR_A.id, event
        assert event["scoreHome"] == 1
    assert request("POST", path + "/events/undo", {})[0] == 200
    assert request("POST", path + "/pause", {}, user=OPERATOR)[0] == 200
    assert request("POST", path + "/resume", {})[0] == 200
    assert request("POST", path + "/finish", {})[0] == 200
    assert request("POST", path + "/reopen", {"reason": "Operator cannot reopen"})[0] == 403
    assert request("POST", path + "/reopen", {"reason": "Operator cannot reopen"}, user=OPERATOR)[0] == 403
    assert request("POST", path + "/events", {"type": "GOAL", "teamId": HOME.id})[0] == 409


@test
def test_audience_permissions_validation_history_and_public_display():
    _, match = fixture()
    path = "/matches/%s/audience" % match.id
    assert request("PUT", path, {"audience": 10}, user=None)[0] == 401
    assert request("PUT", path, {"audience": None}, user=OPERATOR)[0] == 200
    for data in ({}, {"audience": -1}, {"audience": 1.5}, {"audience": True}, {"audience": "10"}, {"audience": 2147483648}):
        assert request("PUT", path, data)[0] == 422, data
    assert request("PUT", path, {"audience": 125})[1]["audience"] == 125
    assert request("GET", "/matches/%s" % match.id, user=None)[1]["audience"] == 125
    assert request("PUT", path, {"audience": 125})[0] == 200
    assert DB.query(AuditLogModel).filter_by(matchId=match.id, action="MATCH_AUDIENCE_UPDATED").count() == 1
    entry = DB.query(AuditLogModel).filter_by(matchId=match.id, action="MATCH_AUDIENCE_UPDATED").one()
    assert entry.userId == OPERATOR_A.id and entry.details == {"previous": None, "audience": 125}
    assert request("PUT", path, {"audience": 0})[1]["audience"] == 0
    assert request("PUT", path, {"audience": None})[1]["audience"] is None
    DB.add(MatchOperatorModel(matchId=match.id, userId=OPERATOR.id))
    DB.commit()
    assert request("PUT", path, {"audience": 7}, user=OPERATOR)[0] == 200
    match.lockedAt = datetime.utcnow()
    DB.commit()
    assert request("PUT", path, {"audience": 9})[0] == 409
    assert request("PUT", path, {"audience": 9}, user=ADMIN)[0] == 409
    DB.refresh(match)
    assert match.audience == 7


@test
def test_audience_can_be_set_when_scheduling_and_cleared_without_changing_score():
    status, match = request("POST", "/matches/", {
        "seasonId": SEASON.id, "homeTeamId": HOME.id, "awayTeamId": AWAY.id,
        "timestamp": "2026-10-12T10:00:00", "audience": 42,
    }, user=ADMIN)
    assert status == 201 and match["audience"] == 42
    path = "/matches/%s" % match["id"]
    assert request("PUT", path, {"round": 2}, user=ADMIN)[1]["audience"] == 42
    assert request("PUT", path, {"audience": None}, user=ADMIN)[1]["audience"] is None
    assert request("PUT", path, {"audience": -5}, user=ADMIN)[0] == 422
    try:
        with DB.begin_nested():
            DB.execute(text("UPDATE matches SET audience = -1 WHERE id = :id"), {"id": match["id"]})
    except IntegrityError:
        pass
    else:
        raise AssertionError("The database must reject negative spectator counts")
    DB.rollback()
    assert request("POST", path + "/start", {})[0] == 200
    previous = request("GET", "/matches/live", user=None)[1]["revision"]
    assert request("PUT", path + "/audience", {"audience": 100})[0] == 200
    assert request("GET", "/matches/live", user=None)[1]["revision"] != previous
    current = request("GET", path, user=None)[1]
    assert current["scoreHome"] == 0 and current["scoreAway"] == 0


@test
def test_public_match_counts_are_per_match_and_team_without_private_records():
    player, match = fixture()
    away, _ = fixture(team=AWAY)
    second, second_match = fixture()
    token = qr(player)
    checked = confirm(match, token)[1]["attendance"]
    assert confirm(match, token)[1]["alreadyPresent"]
    assert confirm(match, qr(away))[0] == 200
    assert confirm(second_match, token)[0] == 200
    payload = request("GET", "/matches/%s" % match.id, user=None)[1]
    assert (payload["attendanceHome"], payload["attendanceAway"], payload["attendanceTotal"]) == (1, 1, 2)
    assert "records" not in payload and "token" not in payload
    listed = request("GET", "/matches/?seasonId=%s" % SEASON.id, user=None)[1]["data"]
    assert next(item for item in listed if item["id"] == second_match.id)["attendanceTotal"] == 1
    assert request("POST", "/attendance/%s/void" % checked["id"], {"reason": "Wrong identity"}, user=ADMIN)[0] == 200
    payload = request("GET", "/matches/%s" % match.id, user=None)[1]
    assert (payload["attendanceHome"], payload["attendanceAway"], payload["attendanceTotal"]) == (0, 1, 1)
    assert request("GET", "/matches/%s" % second_match.id, user=None)[1]["attendanceTotal"] == 1
    DB.delete(away)
    DB.commit()
    assert request("GET", "/matches/%s" % match.id, user=None)[1]["attendanceAway"] == 1
    assert request("POST", "/matches/%s/start" % match.id, {}, user=OPERATOR)[0] == 200
    live = request("GET", "/matches/live", user=None)[1]["data"]
    assert next(item for item in live if item["id"] == match.id)["attendanceTotal"] == 1


@test
def test_audience_statistics_filter_completed_matches_and_preserve_unknown_vs_zero():
    season = SeasonModel(name="Audience statistics isolated")
    empty = SeasonModel(name="Audience statistics empty")
    DB.add_all([season, empty])
    DB.flush()
    matches = []
    for index, (audience, state, scores) in enumerate((
        (200, MatchState.FINISHED, (1, 0)),
        (0, MatchState.FINISHED, (0, 0)),
        (100, MatchState.FINISHED, (2, 1)),
        (None, MatchState.FINISHED, (0, 0)),
        (9000, MatchState.SCHEDULED, (None, None)),
        (8000, MatchState.LIVE, (1, 0)),
        (7000, MatchState.FINISHED, (None, None)),
    )):
        match = MatchModel(seasonId=season.id, homeTeamId=HOME.id, awayTeamId=AWAY.id,
            timestamp=datetime(2026, 10, 15, 10, index), audience=audience,
            state=state, scoreHome=scores[0], scoreAway=scores[1])
        DB.add(match)
        matches.append(match)
    DB.commit()
    path = "/stats/audience?seasonId=%s" % season.id
    status, stats = request("GET", path, user=None)
    assert status == 200 and stats["totalSpectators"] == 300
    assert stats["matchesWithAudience"] == 3 and stats["averageSpectators"] == 100
    assert stats["maxSpectators"] == 200
    assert [item["audience"] for item in stats["data"]] == [200, 100, 0]
    assert stats["data"][0]["matchId"] == matches[0].id
    paged = request("GET", path + "&skip=1&limit=1", user=None)[1]
    assert paged["totalSpectators"] == 300 and len(paged["data"]) == 1
    assert paged["data"][0]["audience"] == 100
    overview = request("GET", "/stats/overview?seasonId=%s" % season.id, user=None)[1]
    assert (overview["audienceTotal"], overview["audienceMatches"], overview["audienceAverage"], overview["audienceMax"]) == (300, 3, 100, 200)
    no_data = request("GET", "/stats/audience?seasonId=%s" % empty.id, user=None)[1]
    assert no_data["totalSpectators"] == 0 and no_data["matchesWithAudience"] == 0
    assert no_data["averageSpectators"] is None and no_data["maxSpectators"] is None and no_data["data"] == []
    matches[0].audience = None
    matches[2].audience = None
    DB.commit()
    only_zero = request("GET", path, user=None)[1]
    assert only_zero["averageSpectators"] == 0 and only_zero["maxSpectators"] == 0
    assert only_zero["matchesWithAudience"] == 1
    assert request("GET", "/stats/audience?seasonId=0", user=None)[0] == 422


@test
def test_audience_migration_preserves_existing_players_and_matches():
    player, match = fixture()
    player_id, match_id = player.id, match.id
    DB.commit()
    config = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
    command.downgrade(config, "c31a94e0d672")
    assert DB.execute(text("SELECT avatar FROM players WHERE id = :id"), {"id": player_id}).scalar()
    assert DB.execute(text("SELECT id FROM matches WHERE id = :id"), {"id": match_id}).scalar() == match_id
    DB.commit()
    command.upgrade(config, "head")
    DB.expire_all()
    assert DB.query(MatchModel).filter_by(id=match_id).one().audience is None
    assert DB.query(PlayerModel).filter_by(id=player_id).one().avatar
    DB.commit()


@test
def test_retired_role_is_rejected_on_account_creation_updates_and_filters():
    data = {"name": "Legacy role", "email": "legacy.role@scc.ro", "password": "password123", "role": "VOLUNTEER"}
    assert request("POST", "/users/", data, user=ADMIN)[0] == 422
    assert request("PUT", "/users/%s" % OPERATOR_A.id, {"role": "VOLUNTEER"}, user=ADMIN)[0] == 422
    assert request("GET", "/users/?role=VOLUNTEER", user=ADMIN)[0] == 422


@test
def test_operator_merge_preserves_accounts_attendance_audit_and_existing_tokens():
    player, match = fixture()
    token = qr(player)
    attendance = confirm(match, token)[1]["attendance"]
    assert request("PUT", "/matches/%s/audience" % match.id, {"audience": 15})[0] == 200
    disabled = UserModel(name="Disabled staff", email="disabled.merge@scc.ro", role=PlatformRoles.OPERATOR, isActive=False)
    disabled.password = "password123"
    DB.add(disabled)
    DB.add(MatchOperatorModel(matchId=match.id, userId=OPERATOR_A.id))
    DB.commit()
    operator_id, disabled_id = OPERATOR_A.id, disabled.id
    legacy_token = create_access_token({"userId": operator_id, "role": "VOLUNTEER", "userName": OPERATOR_A.name})
    snapshot = DB.execute(text("SELECT id, name, email, password, is_active FROM users ORDER BY id")).all()
    DB.commit()
    config = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
    command.downgrade(config, "b72e640a1c98")
    DB.execute(text("UPDATE users SET role = 'VOLUNTEER' WHERE id IN (:active, :disabled)"), {"active": operator_id, "disabled": disabled_id})
    DB.commit()
    command.upgrade(config, "head")
    DB.expire_all()
    assert DB.execute(text("SELECT id, name, email, password, is_active FROM users ORDER BY id")).all() == snapshot
    assert DB.query(UserModel).filter_by(id=operator_id).one().platformRole == PlatformRoles.OPERATOR
    assert DB.query(UserModel).filter_by(id=disabled_id).one().isActive is False
    saved_attendance = DB.query(AttendanceModel).filter_by(id=attendance["id"]).one()
    assert saved_attendance.confirmedById == operator_id and saved_attendance.status == AttendanceStatus.PRESENT
    audit = DB.query(AuditLogModel).filter_by(matchId=match.id, action="MATCH_AUDIENCE_UPDATED").one()
    assert audit.userId == operator_id
    assert DB.query(MatchOperatorModel).filter_by(matchId=match.id, userId=operator_id).one()
    assert DB.execute(text("SELECT COUNT(*) FROM users WHERE role::text = 'VOLUNTEER'" if engine.dialect.name == "postgresql" else "SELECT COUNT(*) FROM users WHERE role = 'VOLUNTEER'")).scalar() == 0
    if engine.dialect.name == "postgresql":
        assert DB.execute(text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_type.oid = enumtypid WHERE typname = 'platformroles' ORDER BY enumsortorder")).scalars().all() == ["OPERATOR", "ADMIN", "SUPER_ADMIN"]
    DB.commit()
    assert request("GET", "/auth/me", token=legacy_token)[1]["role"] == "OPERATOR"
    assert request("GET", "/attendance/matches/%s" % match.id, token=legacy_token)[0] == 200
    assert request("PUT", "/matches/%s/audience" % match.id, {"audience": 16}, token=legacy_token)[0] == 200
    assert request("PUT", "/teams/%s" % HOME.id, {"name": "Forbidden"}, token=legacy_token)[0] == 403
    assert request("POST", "/auth/login", {"email": OPERATOR_A.email, "password": "password123"}, user=None)[1]["role"] == "OPERATOR"
    disabled_token = create_access_token({"userId": disabled_id, "role": "VOLUNTEER", "userName": "Disabled staff"})
    assert request("GET", "/auth/me", token=disabled_token)[0] == 403


@test
def test_historical_attendance_rollback_disables_legacy_staff():
    DB.commit()
    config = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
    operator_id = OPERATOR_A.id
    DB.commit()
    command.downgrade(config, "b72e640a1c98")
    DB.execute(text("UPDATE users SET role = 'VOLUNTEER' WHERE id = :id"), {"id": operator_id})
    DB.commit()
    command.downgrade(config, "a2be5663eafa")
    DB.expire_all()
    assert DB.query(UserModel).filter_by(id=OPERATOR_A.id).one().isActive is False
    DB.commit()
    command.upgrade(config, "head")
    assert DB.execute(text("SELECT COUNT(*) FROM match_attendances")).scalar() == 0
    DB.commit()


if __name__ == "__main__":
    try:
        code = run("Operator attendance and QR verification")
    finally:
        SERVER.should_exit = True
        THREAD.join(timeout=5)
        DB.close()
        drop_database(DB_HANDLE)
    sys.exit(code)
