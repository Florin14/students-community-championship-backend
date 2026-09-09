from fastapi import Depends, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.dependencies import JwtRequired
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from project_helpers.functions import verify_password
from modules.auth.models import ChangePasswordRequest, UserModel

from .router import router


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    data: ChangePasswordRequest,
    user: UserModel = Depends(JwtRequired()),
    db: Session = Depends(get_db),
):
    if not verify_password(user.password, data.currentPassword):
        raise ErrorException(
            Error.INVALID_CREDENTIALS, status_code=status.HTTP_401_UNAUTHORIZED
        )

    user.password = data.newPassword
    db.commit()
