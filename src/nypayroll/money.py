from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def D(value) -> Decimal:
    """Build a Decimal from str/int/Decimal without float contamination."""
    if isinstance(value, float):
        raise TypeError("floats are not allowed for money; pass str or Decimal")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def cents(value) -> Decimal:
    """Round to whole cents, half-up (the convention payroll agencies use)."""
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)
