from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from lib.dates import utcnow

MovementType = Literal["giris", "satis", "kullanim", "transfer"]

# Stock direction per movement type: giriş raises stock, sales/usage lower it,
# transfer only documents a relocation (total unchanged).
STOCK_DELTA = {"giris": 1, "satis": -1, "kullanim": -1, "transfer": 0}


class MovementCreate(BaseModel):
    product_id: str
    type: MovementType
    quantity: float = Field(gt=0)  # pieces, or kilograms for a kg product
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")  # YYYY-MM-DD
    destination: str = ""
    note: str = ""
    unit_price: float | None = Field(default=None, ge=0)


class Movement(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    product_id: str
    product_name: str
    type: str
    quantity: float
    unit: str = "adet"  # snapshot of the product's unit at entry time
    date: str
    destination: str = ""
    note: str = ""
    unit_price: float | None = None
    created_by: str = ""
    created_at: datetime = Field(default_factory=utcnow)
