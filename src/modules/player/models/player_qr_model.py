from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint

from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class PlayerQrModel(SqlBaseModel):
    """One revocable credential per player and season, bound to their team."""

    __tablename__ = "player_qr_credentials"
    __table_args__ = (UniqueConstraint("player_id", "season_id", name="uq_player_qr_season"),)

    id = Column(BigIntPK, primary_key=True, index=True)
    playerId = Column("player_id", BigIntPK, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    seasonId = Column("season_id", BigIntPK, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    teamId = Column("team_id", BigIntPK, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(32), nullable=False)
    issuedAt = Column("issued_at", DateTime, nullable=False, default=datetime.utcnow)
    revokedAt = Column("revoked_at", DateTime, nullable=True)
