from enum import Enum


class MatchEventStatus(str, Enum):
    """An event is never deleted, only moved out of the active set.

    Plan, section 5: "Daca apare o greseala, evenimentul este anulat, nu sters
    definitiv." Only ACTIVE events count towards the score and statistics.
    """

    ACTIVE = "ACTIVE"
    CORRECTED = "CORRECTED"
    VOIDED = "VOIDED"

    def __str__(self):
        return self.value
