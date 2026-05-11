from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import F, Sum

from apps.ledgers.models import (
    InventoryLedgerEntry,
    InventoryValuationLayer,
    InventoryWriteDown,
    ManufacturingCostAllocation,
)


class InventoryRepository:
    @staticmethod
    def valuation_layers(*, inventory_item_id: UUID, warehouse_id: UUID, branch: UUID | None = None):
        queryset = InventoryValuationLayer.objects.filter(
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
            quantity_remaining__gt=0,
        ).order_by("acquisition_date", "created_at", "id")
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return queryset

    @staticmethod
    def last_running_quantity(*, inventory_item_id: UUID, warehouse_id: UUID, branch: UUID | None = None) -> Decimal:
        queryset = InventoryLedgerEntry.objects.filter(
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
        ).order_by("-date", "-created_at", "-id")
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        row = queryset.first()
        return row.running_quantity if row else Decimal("0.0000")

    @staticmethod
    def inventory_value(*, inventory_item_id: UUID, warehouse_id: UUID, branch: UUID | None = None) -> Decimal:
        queryset = InventoryValuationLayer.objects.filter(
            inventory_item_id=inventory_item_id,
            warehouse_id=warehouse_id,
        )
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        totals = queryset.aggregate(total=Sum(F("quantity_remaining") * F("base_unit_cost"), default=Decimal("0.00")))
        return totals["total"] or Decimal("0.00")

    @staticmethod
    def active_write_downs(*, inventory_item_id: UUID | None = None, warehouse_id: UUID | None = None, branch: UUID | None = None):
        queryset = InventoryWriteDown.objects.filter(status="active")
        if inventory_item_id is not None:
            queryset = queryset.filter(inventory_item_id=inventory_item_id)
        if warehouse_id is not None:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return queryset.order_by("-assessment_date", "-created_at")

    @staticmethod
    def manufacturing_allocations(*, branch: UUID | None = None):
        queryset = ManufacturingCostAllocation.objects.all().order_by("-created_at")
        if branch is not None:
            queryset = queryset.filter(branch=branch)
        return queryset
