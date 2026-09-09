from enum import Enum


class MatchEventType(str, Enum):
    """Every scoring action recorded during a match (plan, section 5)."""

    GOAL = "GOAL"
    OWN_GOAL = "OWN_GOAL"
    YELLOW_CARD = "YELLOW_CARD"
    RED_CARD = "RED_CARD"

    def __str__(self):
        return self.value

    @property
    def isGoal(self) -> bool:
        return self in (MatchEventType.GOAL, MatchEventType.OWN_GOAL)

    @property
    def isCard(self) -> bool:
        return self in (
            MatchEventType.YELLOW_CARD,
            MatchEventType.RED_CARD,
        )
