from pydantic import BaseModel


class Stats(BaseModel):
    sale_total: float = 0
    sale_count: int = 0
