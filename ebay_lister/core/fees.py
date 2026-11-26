"""Profit calculation for the Items Database."""


def calc_profit(sold_price, fees, cost):
    """Profit = sold price - fees - your cost (missing fees/cost count as 0). None if there's no sold price."""
    if sold_price is None:
        return None
    return round(sold_price - (fees or 0) - (cost or 0), 2)
