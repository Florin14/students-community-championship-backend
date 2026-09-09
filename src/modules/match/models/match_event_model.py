from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from constants import MatchEventStatus, MatchEventType
from extensions.sqlalchemy import BigIntPK, SqlBaseModel


class MatchEventModel(SqlBaseModel):
    """One scoring action, exactly as section 5 of the plan describes it.

    The score is never typed in: it is derived from the ACTIVE events of a
    match. A mistake is voided rather than deleted, so the match keeps a
    complete record of what was entered, by whom and when.

    `teamId` is always the team the event counts *for*. For an own goal that is
    the opponent of the player who scored it, which keeps deriving the score a
    plain count grouped by team.
    """

    __tablename__ = "match_events"
    __table_args__ = (
        # The client generates this id before sending, so a retry after a
        # dropped connection lands on the same row instead of a second goal.
        UniqueConstraint(
            "match_id", "client_event_id", name="uq_match_event_client_id"
        ),
    )

    id = Column(BigIntPK, primary_key=True, index=True)
    matchId = Column(
        "match_id",
        BigIntPK,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clientEventId = Column("client_event_id", String(64), nullable=False)

    type = Column(Enum(MatchEventType), nullable=False, index=True)
    status = Column(
        Enum(MatchEventStatus),
        nullable=False,
        default=MatchEventStatus.ACTIVE,
        index=True,
    )

    teamId = Column(
        "team_id", BigIntPK, ForeignKey("teams.id"), nullable=False, index=True
    )
    playerId = Column(
        "player_id",
        BigIntPK,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    playerNameSnapshot = Column("player_name_snapshot", String(80), nullable=True)
    assistPlayerId = Column(
        "assist_player_id",
        BigIntPK,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assistNameSnapshot = Column("assist_name_snapshot", String(80), nullable=True)

    minute = Column(Integer, nullable=True)

    # --- Provenance -----------------------------------------------------------
    # The name snapshots keep the trail readable after an operator account is
    # deleted, which is why the FKs may go null without losing the record.
    createdAt = Column(
        "created_at", DateTime, nullable=False, default=datetime.utcnow
    )
    createdById = Column(
        "created_by_id",
        BigIntPK,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    createdByNameSnapshot = Column(
        "created_by_name_snapshot", String(80), nullable=True
    )

    voidedAt = Column("voided_at", DateTime, nullable=True)
    voidedById = Column(
        "voided_by_id",
        BigIntPK,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    voidedByNameSnapshot = Column(
        "voided_by_name_snapshot", String(80), nullable=True
    )
    voidReason = Column("void_reason", String(200), nullable=True)

    # Set when this event replaces an earlier one, so a correction can be read
    # as a chain instead of an unexplained void followed by a new entry.
    supersedesEventId = Column(
        "supersedes_event_id",
        BigIntPK,
        ForeignKey("match_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    match = relationship("MatchModel", back_populates="events")
    team = relationship("TeamModel", foreign_keys=[teamId])
    player = relationship("PlayerModel", foreign_keys=[playerId])
    assistPlayer = relationship("PlayerModel", foreign_keys=[assistPlayerId])
    createdBy = relationship("UserModel", foreign_keys=[createdById])
    voidedBy = relationship("UserModel", foreign_keys=[voidedById])

    @property
    def isActive(self) -> bool:
        return self.status == MatchEventStatus.ACTIVE

    @property
    def isGoal(self) -> bool:
        return MatchEventType(str(self.type)).isGoal

    @property
    def playerName(self):
        if self.player is not None:
            return self.player.name
        return self.playerNameSnapshot

    @property
    def assistName(self):
        if self.assistPlayer is not None:
            return self.assistPlayer.name
        return self.assistNameSnapshot

    @property
    def createdByName(self):
        if self.createdBy is not None:
            return self.createdBy.name
        return self.createdByNameSnapshot

    @property
    def voidedByName(self):
        if self.voidedBy is not None:
            return self.voidedBy.name
        return self.voidedByNameSnapshot
