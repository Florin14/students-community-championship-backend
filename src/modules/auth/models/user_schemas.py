from pydantic import EmailStr, Field

from constants import PlatformRoles
from project_helpers.schemas import BaseSchema


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseSchema):
    id: int
    name: str
    email: EmailStr
    role: PlatformRoles
    accessToken: str


class UserResponse(BaseSchema):
    id: int
    name: str
    email: EmailStr
    role: PlatformRoles


class ChangePasswordRequest(BaseSchema):
    currentPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8)
