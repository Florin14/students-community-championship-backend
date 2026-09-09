from enum import Enum


class CardType(str, Enum):
    YELLOW = "YELLOW"
    RED = "RED"

    def __str__(self):
        return self.value
