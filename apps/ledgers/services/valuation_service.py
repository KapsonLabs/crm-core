from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.models import InventoryValuationLayer, InventoryWriteDown
from apps.ledgers.repositories.inventory_repository import InventoryRepository
from apps.ledgers.utils.money import round_currency


def calculate_fifo_value(*, inventory_item_id: UUID, warehouse_id: UUID, quantity: Decimal, branch: UUID | None = None) -> Decimal:
    remaining = quantity
    total = Decimal("0.00")
    for layer in InventoryRepository.valuation_layers(
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        branch=branch,
    ):
        if remaining <= 0:
            break
        consumed = min(remaining, layer.quantity_remaining)
        total += consumed * layer.base_unit_cost
        remaining -= consumed
    return round_currency(total)


def calculate_weighted_average_value(*, inventory_item_id: UUID, warehouse_id: UUID, quantity: Decimal, branch: UUID | None = None) -> Decimal:
    layers = list(
        InventoryRepository.valuation_layers(
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
            branch=branch,
        )
    )
    total_qty = sum((layer.quantity_remaining for layer in layers), Decimal("0.0000"))
    total_value = sum((layer.quantity_remaining * layer.base_unit_cost for layer in layers), Decimal("0.00"))
    if total_qty <= 0:
        return Decimal("0.00")
    return round_currency((total_value / total_qty) * quantity)


def calculate_specific_identification_value(*, valuation_layer_ids: list[UUID]) -> Decimal:
    layers = InventoryValuationLayer.objects.filter(id__in=valuation_layer_ids)
    return round_currency(
        sum((layer.quantity_remaining * layer.base_unit_cost for layer in layers), Decimal("0.00"))
    )


def calculate_nrv(*, estimated_selling_price: Decimal, completion_costs: Decimal, selling_costs: Decimal) -> Decimal:
    return round_currency(estimated_selling_price - completion_costs - selling_costs)


@transaction.atomic
def perform_lower_of_cost_or_nrv_test(
    *,
    inventory_item_id: UUID,
    warehouse_id: UUID,
    carrying_value: Decimal,
    nrv_value: Decimal,
    assessment_date,
    reason: str,
    branch: UUID | None = None,
) -> InventoryWriteDown | None:
    if nrv_value >= carrying_value:
        return None
    return InventoryWriteDown.objects.create(
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        original_value=carrying_value,
        nrv_value=nrv_value,
        write_down_amount=round_currency(carrying_value - nrv_value),
        assessment_date=assessment_date,
        reason=reason,
        branch=branch,
    )


@transaction.atomic
def reverse_inventory_write_down(*, write_down_id: UUID, reversal_amount: Decimal) -> InventoryWriteDown:
    write_down = InventoryWriteDown.objects.get(pk=write_down_id)
    write_down.reversal_amount = round_currency(write_down.reversal_amount + reversal_amount)
    if write_down.reversal_amount >= write_down.write_down_amount:
        write_down.status = "reversed"
    write_down.save(update_fields=["reversal_amount", "status", "updated_at"])
    return write_down
