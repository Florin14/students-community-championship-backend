from fastapi import Depends

from project_helpers.dependencies import JwtRequired
from modules.auth.models import UserModel, UserResponse

from .router import router


@router.get("/me", response_model=UserResponse)
async def get_me(user: UserModel = Depends(JwtRequired())):
    return user
