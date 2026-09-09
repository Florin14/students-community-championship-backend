from typing import Iterable, List

from fastapi import status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchOperatorModel


def set_match_operators(
    db: Session, match, userIds: Iterable[int]
) -> List[MatchOperatorModel]:
    """Replace the set of accounts allowed to score this match.

    Any account may be assigned - an admin standing in for a missing operator is
    a normal situation on match day - but the account must exist and be active,
    otherwise the assignment would silently lock the field out of scoring.
    """
    from modules.auth.models import UserModel

    wanted = set(userIds)

    if wanted:
        users = (
            db.query(UserModel).filter(UserModel.id.in_(wanted)).all()
        )
        found = {user.id for user in users}
        missing = wanted - found
        if missing:
            raise ErrorException(
                Error.NOT_FOUND,
                message=f"Accounts not found: {sorted(missing)}",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        inactive = sorted(user.id for user in users if not user.isActive)
        if inactive:
            raise ErrorException(
                Error.BAD_REQUEST,
                message=f"These accounts are disabled: {inactive}",
            )

    existing = {link.userId: link for link in match.matchOperators}

    # Mutate the relationship collection rather than the session directly: the
    # delete-orphan cascade removes dropped rows, and appended rows are visible
    # on `match.operatorIds` straight away instead of after the next expiry.
    for userId, link in list(existing.items()):
        if userId not in wanted:
            match.matchOperators.remove(link)

    for userId in wanted - set(existing.keys()):
        match.matchOperators.append(MatchOperatorModel(userId=userId))

    db.flush()
    return match.matchOperators


def assignable_role(role: PlatformRoles) -> bool:
    """Operators and above can be put on a match; nothing below exists today."""
    return role.covers(PlatformRoles.OPERATOR)
