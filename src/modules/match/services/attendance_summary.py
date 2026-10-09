from sqlalchemy import func

from constants import AttendanceStatus


def attach_match_attendance(db, matches):
    """Attach public counts in one query, retaining historical player snapshots.

    Player identities and QR credentials are deliberately absent from this
    summary. A repeated check-in cannot add a second row for the same match.
    """
    from modules.attendance.models import AttendanceModel

    by_id = {match.id: match for match in matches}
    for match in matches:
        match.attendanceHome = 0
        match.attendanceAway = 0
        match.attendanceTotal = 0
    if not by_id:
        return matches
    rows = (
        db.query(AttendanceModel.matchId, AttendanceModel.teamId, func.count(AttendanceModel.id))
        .filter(
            AttendanceModel.matchId.in_(by_id),
            AttendanceModel.status == AttendanceStatus.PRESENT,
        )
        .group_by(AttendanceModel.matchId, AttendanceModel.teamId)
        .all()
    )
    for match_id, team_id, count in rows:
        match = by_id[match_id]
        match.attendanceTotal += count
        if team_id == match.homeTeamId:
            match.attendanceHome += count
        elif team_id == match.awayTeamId:
            match.attendanceAway += count
    return matches
