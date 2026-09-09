from fastapi import Depends, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from modules.user.models import UserAdd, UserModel, UserResponse

from .router import router


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_user(
    data: UserAdd,
    currentUser: UserModel = Depends(JwtRequired(roles=[PlatformRoles.ADMIN])),
    db: Session = Depends(get_db),
):
    """Create an operator, admin or super-admin account.

    Only a super-admin may create another super-admin, so an admin cannot
    escalate their own reach by creating an account above themselves.
    """
    if not currentUser.covers(data.role):
        raise ErrorException(
            Error.FORBIDDEN,
            message="You cannot create an account with a role above your own",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    exists = (
        db.query(UserModel).filter(UserModel.email == data.email).first()
    )
    if exists is not None:
        raise ErrorException(
            Error.CONFLICT,
            message="An account with this email already exists",
            status_code=status.HTTP_409_CONFLICT,
        )

    user = UserModel(name=data.name, email=data.email, role=data.role)
    user.password = data.password
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
