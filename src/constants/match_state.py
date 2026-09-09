from enum import Enum


class MatchState(str, Enum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    HALF_TIME = "HALF_TIME"
    FINISHED = "FINISHED"
    POSTPONED = "POSTPONED"

    def __str__(self):
        return self.value
