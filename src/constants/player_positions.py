from enum import Enum


class PlayerPositions(str, Enum):
    GOALKEEPER = "GOALKEEPER"
    DEFENDER = "DEFENDER"
    MIDFIELDER = "MIDFIELDER"
    FORWARD = "FORWARD"

    def __str__(self):
        return self.value
