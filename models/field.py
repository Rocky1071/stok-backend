from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from lib.dates import utcnow

FieldType = Literal["text", "number"]


class CustomFieldCreate(BaseModel):
    label: str = Field(min_length=1)
    type: FieldType = "text"


class CustomFieldUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1)
    type: FieldType | None = None


class CustomField(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    key: str
    label: str
    type: str = "text"
    created_at: datetime = Field(default_factory=utcnow)
