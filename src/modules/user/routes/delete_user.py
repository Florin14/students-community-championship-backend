from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.match.models import MatchOperatorModel
from modules.user.models import UserModel

from .router import router


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user: UserModel = Depends(GetInstanceFromPath(UserModel)),
    currentUser: UserModel = Depends(JwtRequired(roles=[PlatformRoles.ADMIN])),
    db: Session = Depends(get_db),
):
    """Delete an account.

    Events the operator recorded keep their authorship through a name snapshot,
    so the audit trail survives the account being removed.
    """
    if user.id == currentUser.id:
        raise ErrorException(
            Error.CANNOT_DEMOTE_SELF,
            message="You cannot delete your own account",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if not currentUser.covers(user.platformRole):
        raise ErrorException(
            Error.FORBIDDEN,
            message="You cannot delete an account with a role above your own",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    lastAdmin = (
        user.covers(PlatformRoles.ADMIN)
        and db.query(UserModel)
        .filter(
            UserModel.role.in_(
                [PlatformRoles.ADMIN, PlatformRoles.SUPER_ADMIN]
            ),
            UserModel.id != user.id,
            UserModel.isActive.is_(True),
        )
        .first()
        is None
    )
    if lastAdmin:
        raise ErrorException(
            Error.BAD_REQUEST,
            message="This is the last active administrator account",
        )

    db.query(MatchOperatorModel).filter(
        MatchOperatorModel.userId == user.id
    ).delete()
    db.delete(user)
    db.commit()
    return None
