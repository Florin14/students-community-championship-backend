from datetime import datetime
from typing import List, Optional

from pydantic import Field, StrictBool

from constants import AttendanceStatus
from modules.player.models import PlayerResponse
from project_helpers.schemas import BaseSchema, PaginationParams


class AttendanceScan(BaseSchema):
    token: str = Field(..., min_length=20, max_length=2048)


class AttendanceConfirm(AttendanceScan):
    identityConfirmed: StrictBool


class AttendanceVoid(BaseSchema):
    reason: str = Field(..., min_length=3, max_length=200)


class AttendanceItem(BaseSchema):
    id: int
    matchId: int
    playerId: Optional[int] = None
    playerIdSnapshot: int
    playerNameSnapshot: str
    teamId: int
    teamNameSnapshot: str
    shirtNumberSnapshot: Optional[int] = None
    status: AttendanceStatus
    confirmedAt: datetime
    confirmedById: Optional[int] = None
    confirmedByNameSnapshot: str
    voidedAt: Optional[datetime] = None
    voidReason: Optional[str] = None


class AttendanceScanResponse(BaseSchema):
    matchId: int
    player: PlayerResponse
    alreadyPresent: bool
    canConfirm: bool
    attendance: Optional[AttendanceItem] = None


class AttendanceConfirmResponse(BaseSchema):
    attendance: AttendanceItem
    alreadyPresent: bool


class AttendanceRosterItem(BaseSchema):
    player: PlayerResponse
    attendance: Optional[AttendanceItem] = None
    isPresent: bool = False


class MatchAttendanceResponse(BaseSchema):
    matchId: int
    canConfirm: bool
    presentCount: int
    totalPlayers: int
    data: List[AttendanceRosterItem] = Field(default_factory=list)
    records: List[AttendanceItem] = Field(default_factory=list)


class AttendanceStatsParams(PaginationParams):
    seasonId: Optional[int] = Field(None, gt=0)
    teamId: Optional[int] = Field(None, gt=0)
    playerId: Optional[int] = Field(None, gt=0)


class PlayerAttendanceStat(BaseSchema):
    playerId: int
    name: str
    teamId: Optional[int] = None
    teamName: Optional[str] = None
    presences: int
    lastPresentAt: Optional[datetime] = None


class AttendanceStatsResponse(BaseSchema):
    totalAttendances: int
    uniquePlayers: int
    matchesWithAttendance: int
    data: List[PlayerAttendanceStat] = Field(default_factory=list)
