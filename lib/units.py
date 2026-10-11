"""Units: "adet" (pieces), "kg" (weight), "litre" (volume), and "metre" (length).

Stock for kg/litre/metre products is stored as a float with 3 decimals precision (= gram/ml/mm precision).
Piece products are whole numbers.
"""

ADET = "adet"
KG = "kg"
LITRE = "litre"
METRE = "metre"

UNITS = (ADET, KG, LITRE, METRE)
UNIT_LABELS = {
    ADET: "Adet",
    KG: "Kilogram",
    LITRE: "Litre",
    METRE: "Metre"
}


def normalize_qty(quantity: float, unit: str) -> float:
    """Round to the unit's precision: whole pieces, or 3-decimal float for kg/litre/metre."""
    if unit in (KG, LITRE, METRE):
        return round(float(quantity), 3)
    return float(int(round(float(quantity))))


def format_qty(quantity: float, unit: str) -> str:
    """Human string formatting:
    9.5 kg -> '9 kg 500 g'
    1.5 litre -> '1 L 500 ml'
    2.5 metre -> '2 m 50 cm'
    24 adet -> '24 adet'
    """
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

    if unit == LITRE:
        total_ml = int(round(float(quantity) * 1000))
        sign = "-" if total_ml < 0 else ""
        total_ml = abs(total_ml)
        litres, ml = divmod(total_ml, 1000)
        if litres and ml:
            return f"{sign}{litres} L {ml} ml"
        if litres:
            return f"{sign}{litres} L"
        return f"{sign}{ml} ml"

    if unit == METRE:
        total_cm = int(round(float(quantity) * 100))
        sign = "-" if total_cm < 0 else ""
        total_cm = abs(total_cm)
        metres, cm = divmod(total_cm, 100)
        if metres and cm:
            return f"{sign}{metres} m {cm} cm"
        if metres:
            return f"{sign}{metres} m"
        return f"{sign}{cm} cm"

    return f"{int(round(float(quantity)))} adet"
