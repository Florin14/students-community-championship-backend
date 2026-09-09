from typing import List, Optional

import jwt as pyjwt
from fastapi import Depends, Request, status
from sqlalchemy.orm import Session

from constants import PlatformRoles
from extensions.sqlalchemy import get_db
from project_helpers.error import Error
from project_helpers.exceptions import ErrorException
from project_helpers.functions import decode_access_token


class JwtRequired:
    """Dependency that validates the Bearer token and loads the current user.

    Usage:
        dependencies=[Depends(JwtRequired())]
        dependencies=[Depends(JwtRequired(roles=[PlatformRoles.ADMIN]))]
    """

    def __init__(self, roles: Optional[List[PlatformRoles]] = None):
        self.roles = [str(role) for role in roles] if roles else None

    def __call__(self, request: Request, db: Session = Depends(get_db)):
        from modules.auth.models import UserModel

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise ErrorException(
                Error.TOKEN_NOT_FOUND, status_code=status.HTTP_401_UNAUTHORIZED
            )

        token = auth_header[len("Bearer "):].strip()
        try:
            claims = decode_access_token(token)
        except pyjwt.PyJWTError:
            raise ErrorException(
                Error.INVALID_TOKEN, status_code=status.HTTP_401_UNAUTHORIZED
            )

        user_id = claims.get("userId")
        if user_id is None:
            raise ErrorException(
                Error.INVALID_TOKEN, status_code=status.HTTP_401_UNAUTHORIZED
            )

        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if user is None:
            raise ErrorException(
                Error.USER_NOT_FOUND, status_code=status.HTTP_401_UNAUTHORIZED
            )

        if self.roles and str(user.role) not in self.roles:
            raise ErrorException(
                Error.FORBIDDEN, status_code=status.HTTP_403_FORBIDDEN
            )

        request.state.user = user
        return user
