from fastapi import Depends, status
from sqlalchemy.orm import Session

from extensions.sqlalchemy import get_db
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from project_helpers.functions import create_access_token, verify_password
from modules.auth.models import LoginRequest, LoginResponse, UserModel

from .router import router


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserModel).filter(UserModel.email == data.email).first()

    if user is None or not verify_password(user.password, data.password):
        raise ErrorException(
            Error.INVALID_CREDENTIALS, status_code=status.HTTP_401_UNAUTHORIZED
        )

    access_token = create_access_token(user.get_claims())

    return LoginResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        accessToken=access_token,
    )
