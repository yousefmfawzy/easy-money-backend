from decimal import Decimal, ROUND_HALF_UP

MONEY_EXP = Decimal("0.01")
PCT_EXP = Decimal("0.01")

def quantize_money(d: Decimal) -> Decimal:
    return d.quantize(MONEY_EXP, rounding=ROUND_HALF_UP)

def quantize_pct(d: Decimal) -> Decimal:
    return d.quantize(PCT_EXP, rounding=ROUND_HALF_UP)

def pct_change(old: Decimal, new: Decimal) -> Decimal:
    if old == Decimal("0"):
        return Decimal("0.00")
    change = ((new - old) / old) * Decimal("100")
    return quantize_pct(change)

def apply_percentage(current: Decimal, pct: Decimal) -> Decimal:
    new_value = current * (Decimal("1") + (pct / Decimal("100")))
    return quantize_money(new_value)

def trend_for(old: Decimal, new: Decimal) -> str:
    if new > old:
        return "UP"
    elif new < old:
        return "DOWN"
    else:
        return "FLAT"
