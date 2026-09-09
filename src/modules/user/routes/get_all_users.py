from fastapi import Depends
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from modules.user.models import UserListParams, UserListResponse, UserModel

from .router import router


@router.get(
    "/",
    response_model=UserListResponse,
    dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))],
)
async def get_all_users(
    params: UserListParams = Depends(),
    db: Session = Depends(get_db),
):
    """List the platform accounts: operators, admins and super-admins."""
    query = db.query(UserModel)

    if params.role is not None:
        query = query.filter(UserModel.role == params.role)
    if params.isActive is not None:
        query = query.filter(UserModel.isActive == params.isActive)

    users = query.order_by(UserModel.name).all()
    return UserListResponse(data=users)
