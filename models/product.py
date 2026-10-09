from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from lib.dates import utcnow

# "adet" = pieces (whole numbers), "kg" = weight in kilograms (gram precision).
Unit = Literal["adet", "kg"]


class ProductCreate(BaseModel):
    name: str = Field(min_length=1)
    brand: str = ""
    model: str = ""
    lot_number: str = ""
    unit: Unit = "adet"
    purchase_price: float = Field(default=0, ge=0)  # kg products: price per kilogram
    sale_price: float = Field(default=0, ge=0)
    quantity: float = Field(default=0, ge=0)
    min_stock: float = Field(default=5, ge=0)
    image: str | None = None
    images: list[str] = Field(default_factory=list)
    notes: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)


class ProductUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    lot_number: str | None = None
    unit: Unit | None = None
    purchase_price: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    quantity: float | None = Field(default=None, ge=0)
    min_stock: float | None = Field(default=None, ge=0)
    image: str | None = None
    images: list[str] | None = None
    notes: str | None = None
    attributes: dict[str, str] | None = None


class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    brand: str = ""
    model: str = ""
    lot_number: str = ""
    unit: str = "adet"
    purchase_price: float = 0
    sale_price: float = 0
    quantity: float = 0
    min_stock: float = 5
    image: str | None = None
    images: list[str] = Field(default_factory=list)
    notes: str = ""
    attributes: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
