from fastapi import Depends, Path, status
from sqlalchemy.orm import Session, joinedload

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException

from .jwt_required import JwtRequired

# One shared instance so FastAPI caches the token check per request: several
# MatchAccess dependencies on the same route resolve the user only once.
_authenticate = JwtRequired()


class MatchContext:
    """A match together with the authenticated user allowed to write to it."""

    def __init__(self, match, user):
        self.match = match
        self.user = user

    @property
    def isSuperAdmin(self) -> bool:
        return self.user.covers(PlatformRoles.SUPER_ADMIN)


class MatchAccess:
    """Load the match from `{id}` and check the caller may write to it.

    Two rules, both from section 6 of the implementation plan:

    - An operator may only touch a match they are assigned to; admins and
      super-admins may touch any match.
    - A confirmed match is locked, and writes are refused until a super-admin
      reopens it. Reopening is the only call that passes `allowLocked=True`.

    Yields a `MatchContext` rather than the match alone, so a route gets both
    the match and the user from one dependency without resolving the JWT twice.

    Usage:
        ctx: MatchContext = Depends(MatchAccess())
        ctx: MatchContext = Depends(MatchAccess(minRole=PlatformRoles.ADMIN))
        ctx: MatchContext = Depends(
            MatchAccess(minRole=PlatformRoles.SUPER_ADMIN, allowLocked=True)
        )
    """

    def __init__(
        self,
        minRole: PlatformRoles = PlatformRoles.OPERATOR,
        allowLocked: bool = False,
    ):
        self.minRole = minRole
        self.allowLocked = allowLocked

    def __call__(
        self,
        id: int = Path(...),
        db: Session = Depends(get_db),
        user=Depends(_authenticate),
    ) -> MatchContext:
        from modules.match.models import MatchModel

        if not user.covers(self.minRole):
            raise ErrorException(
                Error.FORBIDDEN, status_code=status.HTTP_403_FORBIDDEN
            )

        match = (
            db.query(MatchModel)
            .options(joinedload(MatchModel.matchOperators))
            .filter(MatchModel.id == id)
            .first()
        )
        if match is None:
            raise ErrorException(
                Error.NOT_FOUND,
                message="Match not found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

        isOperatorOnly = not user.covers(PlatformRoles.ADMIN)
        if isOperatorOnly and user.id not in match.operatorIds:
            raise ErrorException(
                Error.NOT_ASSIGNED_TO_MATCH,
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if match.isLocked and not self.allowLocked:
            raise ErrorException(
                Error.MATCH_LOCKED, status_code=status.HTTP_409_CONFLICT
            )

        return MatchContext(match=match, user=user)
