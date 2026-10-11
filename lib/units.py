"""Units: "adet" (pieces), "kg" (weight), "lt" (volume) and "m" (length).

Stock is stored as a float in the BASE unit of each type:
  - kg: kilograms, rounded to 3 decimals (= gram precision), "10 kg 500 g" is 10.5
  - lt: litres, rounded to 3 decimals (= mL precision), "2 L 250 mL" is 2.25
  - m:  metres, rounded to 2 decimals (= cm precision), "1 m 50 cm" is 1.5
Piece products are whole numbers. Rounding keeps float drift out of the database.
"""

ADET = "adet"
KG = "kg"
LT = "lt"
M = "m"
UNITS = (ADET, KG, LT, M)
UNIT_LABELS = {ADET: "Adet", KG: "Kilogram", LT: "Litre", M: "Metre"}

# Fractional units: unit -> (decimals, small units per 1 base unit, big label, small label)
_SPLIT = {
    KG: (3, 1000, "kg", "g"),
    LT: (3, 1000, "L", "mL"),
    M: (2, 100, "m", "cm"),
}


def normalize_qty(quantity: float, unit: str) -> float:
    """Round to the unit's precision: whole pieces, or the fractional unit's decimals."""
    if unit in _SPLIT:
        decimals = _SPLIT[unit][0]
        return round(float(quantity), decimals)
    return float(int(round(float(quantity))))


def format_qty(quantity: float, unit: str) -> str:
    """Human string: 9.5 kg -> '9 kg 500 g'; 1.25 m -> '1 m 25 cm'; 24 adet -> '24 adet'."""
    if unit in _SPLIT:
        _, factor, big, small = _SPLIT[unit]
        total = int(round(float(quantity) * factor))
        sign = "-" if total < 0 else ""
        total = abs(total)
        whole, part = divmod(total, factor)
        if whole and part:
            return f"{sign}{whole} {big} {part} {small}"
        if whole:
            return f"{sign}{whole} {big}"
        return f"{sign}{part} {small}"
    return f"{int(round(float(quantity)))} adet"
