from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.repositories.inventory_repository import InventoryRepository
from apps.ledgers.services.inventory_posting_service import post_stock_adjustment


def calculate_stock_variance(*, book_quantity: Decimal, physical_quantity: Decimal) -> Decimal:
    return physical_quantity - book_quantity


def reconcile_physical_count(*, inventory_item_id: UUID, warehouse_id: UUID, physical_quantity: Decimal, branch: UUID | None = None) -> dict:
    book_quantity = InventoryRepository.last_running_quantity(
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        branch=branch,
    )
    variance = calculate_stock_variance(book_quantity=book_quantity, physical_quantity=physical_quantity)
    return {"book_quantity": book_quantity, "physical_quantity": physical_quantity, "variance": variance}


@transaction.atomic
def post_inventory_variance(*, variance_id: str, posting_date, inventory_item_id: UUID, warehouse_id: UUID, variance_quantity: Decimal, unit_cost_base: Decimal, branch: UUID | None, created_by_id: UUID | None):
    amount = abs(variance_quantity) * unit_cost_base
    return post_stock_adjustment(
        adjustment_id=variance_id,
        posting_date=posting_date,
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        quantity=abs(variance_quantity),
        amount=amount,
        branch=branch,
        created_by_id=created_by_id,
        increase_stock=variance_quantity > 0,
        currency="UGX",
    )
