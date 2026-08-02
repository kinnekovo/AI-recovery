from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.users.model import UserRole
from app.modules.users.schema import UserRead


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.patient


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenUser(BaseModel):
    id: UUID
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: TokenUser


class RegisterResponse(BaseModel):
    user: UserRead
