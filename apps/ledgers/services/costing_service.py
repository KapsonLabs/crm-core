from __future__ import annotations

from decimal import Decimal

from apps.ledgers.utils.money import round_currency


def calculate_fifo_cost(*, quantity_to_issue: Decimal, cost_layers: list[dict]) -> Decimal:
    remaining = quantity_to_issue
    total_cost = Decimal("0.00")
    for layer in cost_layers:
        if remaining <= 0:
            break
        consumed = min(remaining, Decimal(str(layer["quantity_remaining"])))
        total_cost += consumed * Decimal(str(layer["base_unit_cost"]))
        remaining -= consumed
    return round_currency(total_cost)


def calculate_weighted_average_cost(*, total_cost: Decimal, total_units: Decimal) -> Decimal:
    if total_units <= 0:
        return Decimal("0.00")
    return round_currency(total_cost / total_units)


def calculate_standard_cost(*, standard_material: Decimal, standard_labor: Decimal, standard_overhead: Decimal) -> Decimal:
    return round_currency(standard_material + standard_labor + standard_overhead)


def allocate_manufacturing_overheads(*, base_amount: Decimal, overhead_pool: Decimal, activity_share: Decimal) -> Decimal:
    """Allocate a share of the overhead pool to this production run.

    activity_share is the fraction (0.0–1.0) of the total activity base consumed
    by this production order.  base_amount is retained as a guard against calling
    with no activity, not as a divisor.
    """
    if base_amount <= 0 or activity_share <= 0:
        return Decimal("0.00")
    return round_currency(overhead_pool * activity_share)


def calculate_batch_cost(*, material_cost: Decimal, labor_cost: Decimal, overhead_cost: Decimal, batch_quantity: Decimal) -> Decimal:
    if batch_quantity <= 0:
        return Decimal("0.00")
    return round_currency((material_cost + labor_cost + overhead_cost) / batch_quantity)
