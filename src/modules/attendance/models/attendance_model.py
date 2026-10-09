from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint

from constants import AttendanceStatus
from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class AttendanceModel(SqlBaseModel):
    __tablename__ = "match_attendances"
    __table_args__ = (
        UniqueConstraint("match_id", "player_id_snapshot", name="uq_match_attendance_player"),
    )

    id = Column(BigIntPK, primary_key=True, index=True)
    matchId = Column("match_id", BigIntPK, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    playerId = Column("player_id", BigIntPK, ForeignKey("players.id", ondelete="SET NULL"), nullable=True, index=True)
    playerIdSnapshot = Column("player_id_snapshot", BigIntPK, nullable=False)
    playerNameSnapshot = Column("player_name_snapshot", String(80), nullable=False)
    teamId = Column("team_id", BigIntPK, ForeignKey("teams.id"), nullable=False, index=True)
    teamNameSnapshot = Column("team_name_snapshot", String(80), nullable=False)
    shirtNumberSnapshot = Column("shirt_number_snapshot", Integer, nullable=True)
    status = Column(Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.PRESENT, index=True)
    confirmedAt = Column("confirmed_at", DateTime, nullable=False, default=datetime.utcnow)
    confirmedById = Column("confirmed_by_id", BigIntPK, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmedByNameSnapshot = Column("confirmed_by_name_snapshot", String(80), nullable=False)
    voidedAt = Column("voided_at", DateTime, nullable=True)
    voidedById = Column("voided_by_id", BigIntPK, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voidReason = Column("void_reason", String(200), nullable=True)
