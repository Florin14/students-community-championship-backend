from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import GetInstanceFromPath, JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.user.models import UserModel, UserResponse, UserUpdate

from .router import router


@router.put("/{id}", response_model=UserResponse)
async def update_user(
    data: UserUpdate,
    user: UserModel = Depends(GetInstanceFromPath(UserModel)),
    currentUser: UserModel = Depends(JwtRequired(roles=[PlatformRoles.ADMIN])),
    db: Session = Depends(get_db),
):
    """Rename an account, change its role, reset its password or disable it."""
    isSelf = user.id == currentUser.id

    if isSelf and (data.role is not None or data.isActive is False):
        raise ErrorException(
            Error.CANNOT_DEMOTE_SELF, status_code=status.HTTP_403_FORBIDDEN
        )

    if not currentUser.covers(user.platformRole) and not isSelf:
        raise ErrorException(
            Error.FORBIDDEN,
            message="You cannot modify an account with a role above your own",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if data.role is not None and not currentUser.covers(data.role):
        raise ErrorException(
            Error.FORBIDDEN,
            message="You cannot grant a role above your own",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if data.email is not None and data.email != user.email:
        taken = (
            db.query(UserModel)
            .filter(UserModel.email == data.email, UserModel.id != user.id)
            .first()
        )
        if taken is not None:
            raise ErrorException(
                Error.CONFLICT,
                message="An account with this email already exists",
                status_code=status.HTTP_409_CONFLICT,
            )

    user.update(data, exclude={"password"})
    if data.password:
        user.password = data.password

    db.commit()
    db.refresh(user)
    return user
