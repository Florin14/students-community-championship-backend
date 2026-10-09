from datetime import datetime

from fastapi import status
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from constants import AttendanceStatus, MatchState
from modules.attendance.models import (
    AttendanceItem,
    AttendanceModel,
    AttendanceRosterItem,
    AttendanceStatsResponse,
    MatchAttendanceResponse,
    PlayerAttendanceStat,
)
from modules.audit.services import record as audit
from modules.match.models import MatchModel
from modules.player.models import PlayerModel
from modules.player.services import attach_player_stats
from modules.player.services.qr_service import resolve_player_qr
from modules.season.models import SeasonTeamModel
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException


def can_confirm(match):
    return match.state == MatchState.SCHEDULED and match.startedAt is None and not match.isLocked


def _require_open(match):
    if not can_confirm(match):
        raise ErrorException(Error.ATTENDANCE_CLOSED, status_code=status.HTTP_409_CONFLICT)


def find_attendance(db, match_id, player_id):
    return db.query(AttendanceModel).filter(
        AttendanceModel.matchId == match_id,
        AttendanceModel.playerIdSnapshot == player_id,
    ).first()


def confirm_attendance(db, match, token, user, identity_confirmed):
    if identity_confirmed is not True:
        raise ErrorException(Error.IDENTITY_NOT_CONFIRMED)
    # A row lock serializes simultaneous scans and kickoff for this match.
    match = db.query(MatchModel).filter(MatchModel.id == match.id).with_for_update().populate_existing().one()
    player = resolve_player_qr(db, token, match, lock=True)
    attendance = find_attendance(db, match.id, player.id)
    if attendance is not None and attendance.status == AttendanceStatus.PRESENT:
        # Retries after kickoff remain safe; they do not create a new presence.
        return attendance, True
    _require_open(match)
    if attendance is None:
        attendance = AttendanceModel(matchId=match.id, playerIdSnapshot=player.id)
        db.add(attendance)
    attendance.playerId = player.id
    attendance.playerNameSnapshot = player.name
    attendance.teamId = player.teamId
    attendance.teamNameSnapshot = player.teamName
    attendance.shirtNumberSnapshot = player.shirtNumber
    attendance.status = AttendanceStatus.PRESENT
    attendance.confirmedAt = datetime.utcnow()
    attendance.confirmedById = user.id
    attendance.confirmedByNameSnapshot = user.name
    attendance.voidedAt = None
    attendance.voidedById = None
    attendance.voidReason = None
    db.flush()
    audit(db, user, "ATTENDANCE_CONFIRMED", "Attendance", attendance.id, match.id,
          summary="Identity checked and attendance confirmed for %s" % player.name,
          details={"playerId": player.id, "teamId": player.teamId})
    return attendance, False


def void_attendance(db, attendance, user, reason):
    if not reason.strip():
        raise ErrorException(Error.VALIDATION_ERROR, message="A correction reason is required")
    match = db.query(MatchModel).filter(MatchModel.id == attendance.matchId).with_for_update().populate_existing().one()
    attendance = db.query(AttendanceModel).filter(AttendanceModel.id == attendance.id).populate_existing().one()
    if attendance.status == AttendanceStatus.VOIDED:
        return attendance
    _require_open(match)
    attendance.status = AttendanceStatus.VOIDED
    attendance.voidedAt = datetime.utcnow()
    attendance.voidedById = user.id
    attendance.voidReason = reason.strip()
    audit(db, user, "ATTENDANCE_VOIDED", "Attendance", attendance.id, match.id,
          summary="Attendance corrected for %s" % attendance.playerNameSnapshot,
          details={"reason": attendance.voidReason})
    return attendance


def match_attendance(db, match):
    players = db.query(PlayerModel).options(joinedload(PlayerModel.team)).filter(
        PlayerModel.teamId.in_([match.homeTeamId, match.awayTeamId])
    ).order_by(PlayerModel.teamId, PlayerModel.name).all()
    attach_player_stats(db, players, season_id=match.seasonId)
    records = db.query(AttendanceModel).filter(AttendanceModel.matchId == match.id).order_by(AttendanceModel.confirmedAt).all()
    by_player = {record.playerIdSnapshot: record for record in records}
    return MatchAttendanceResponse(
        matchId=match.id,
        canConfirm=can_confirm(match),
        presentCount=sum(record.status == AttendanceStatus.PRESENT for record in records),
        totalPlayers=len(players),
        data=[AttendanceRosterItem(player=player, attendance=by_player.get(player.id),
              isPresent=bool(by_player.get(player.id) and by_player[player.id].status == AttendanceStatus.PRESENT)) for player in players],
        records=[AttendanceItem.model_validate(record) for record in records],
    )


def attendance_query(db, season_id=None, team_id=None, player_id=None):
    query = db.query(AttendanceModel).join(MatchModel, MatchModel.id == AttendanceModel.matchId).filter(AttendanceModel.status == AttendanceStatus.PRESENT)
    if season_id is not None:
        query = query.filter(MatchModel.seasonId == season_id)
    if team_id is not None:
        query = query.filter(AttendanceModel.teamId == team_id)
    if player_id is not None:
        query = query.filter(AttendanceModel.playerIdSnapshot == player_id)
    return query


def attendance_summary(db, season_id=None, team_id=None, player_id=None):
    query = attendance_query(db, season_id, team_id, player_id)
    total, players, matches = query.with_entities(
        func.count(AttendanceModel.id),
        func.count(func.distinct(AttendanceModel.playerIdSnapshot)),
        func.count(func.distinct(AttendanceModel.matchId)),
    ).one()
    return {"totalAttendances": total, "uniquePlayers": players, "matchesWithAttendance": matches}


def attendance_stats(db, params):
    # Counts describe confirmed arrivals, independently of playing minutes.
    summary = attendance_summary(db, params.seasonId, params.teamId, params.playerId)
    rows = attendance_query(db, params.seasonId, params.teamId, params.playerId).with_entities(
        AttendanceModel.playerIdSnapshot,
        func.count(AttendanceModel.id),
        func.max(AttendanceModel.confirmedAt),
    ).group_by(AttendanceModel.playerIdSnapshot).all()
    counts = {player_id: (count, last) for player_id, count, last in rows}
    players = db.query(PlayerModel).options(joinedload(PlayerModel.team))
    if params.seasonId is not None:
        players = players.filter(PlayerModel.teamId.in_(db.query(SeasonTeamModel.teamId).filter(SeasonTeamModel.seasonId == params.seasonId)))
    if params.teamId is not None:
        players = players.filter(PlayerModel.teamId == params.teamId)
    if params.playerId is not None:
        players = players.filter(PlayerModel.id == params.playerId)
    items = {player.id: PlayerAttendanceStat(playerId=player.id, name=player.name, teamId=player.teamId, teamName=player.teamName, presences=counts.get(player.id, (0, None))[0], lastPresentAt=counts.get(player.id, (0, None))[1]) for player in players.all()}
    # Preserve the historical identity/team for removed or transferred players.
    for player_id, (count, last) in counts.items():
        if player_id not in items:
            snapshot = attendance_query(db, params.seasonId, params.teamId, player_id).order_by(AttendanceModel.confirmedAt.desc()).first()
            items[player_id] = PlayerAttendanceStat(playerId=player_id, name=snapshot.playerNameSnapshot, teamId=snapshot.teamId, teamName=snapshot.teamNameSnapshot, presences=count, lastPresentAt=last)
    ranked = sorted(items.values(), key=lambda item: (-item.presences, item.name.casefold(), item.playerId))
    end = params.skip + params.limit if params.limit is not None else None
    return AttendanceStatsResponse(**summary, data=ranked[params.skip:end])
