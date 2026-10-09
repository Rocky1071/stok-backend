from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field

Role = Literal["ana_yonetici", "yardimci_yonetici", "uye"]


class UserOut(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    email: str
    name: str = ""
    role: str = "uye"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RegisterInput(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=6)


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class RoleUpdate(BaseModel):
    role: Role
