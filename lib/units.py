"""Units: "adet" (pieces) and "kg" (weight).

Stock for a kg product is stored as a float in KILOGRAMS, rounded to 3 decimals (= gram
precision), so "10 kg 500 g" is 10.5 and the value reads naturally in MySQL and Excel.
Piece products are whole numbers. QTY_PRECISION keeps float drift out of the database.
"""

ADET = "adet"
KG = "kg"
UNITS = (ADET, KG)
UNIT_LABELS = {ADET: "Adet", KG: "Kilogram"}


def normalize_qty(quantity: float, unit: str) -> float:
    """Round to the unit's precision: whole pieces, or gram-precision kilograms."""
    if unit == KG:
        return round(float(quantity), 3)
    return float(int(round(float(quantity))))


def format_qty(quantity: float, unit: str) -> str:
    """Human string: 9.5 kg -> '9 kg 500 g'; 24 adet -> '24 adet'."""
    if unit == KG:
        total_grams = int(round(float(quantity) * 1000))
        sign = "-" if total_grams < 0 else ""
        total_grams = abs(total_grams)
        kilos, grams = divmod(total_grams, 1000)
        if kilos and grams:
            return f"{sign}{kilos} kg {grams} g"
        if kilos:
            return f"{sign}{kilos} kg"
        return f"{sign}{grams} g"
    return f"{int(round(float(quantity)))} adet"
