from typing import List, Optional

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
    isActive: bool = True


class ChangePasswordRequest(BaseSchema):
    currentPassword: str = Field(..., min_length=1)
    newPassword: str = Field(..., min_length=8)


class UserAdd(BaseSchema):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: PlatformRoles = PlatformRoles.OPERATOR


class UserUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=2, max_length=80)
    email: Optional[EmailStr] = None
    role: Optional[PlatformRoles] = None
    isActive: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class UserListParams(BaseSchema):
    role: Optional[PlatformRoles] = None
    isActive: Optional[bool] = None


class UserListResponse(BaseSchema):
    data: List[UserResponse] = []
