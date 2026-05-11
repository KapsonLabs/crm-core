from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import DecimalField, ExpressionWrapper, F, Sum

from apps.ledgers.constants import DEFAULT_CURRENCY
from apps.ledgers.models import (
    InventoryLedgerEntry,
    InventoryValuationLayer,
    InventoryWriteDown,
    LandedCostAllocation,
    ManufacturingCostAllocation,
)


def generate_inventory_valuation_report(*, as_of_date: date, branch: UUID | None = None) -> dict:
    qs = InventoryLedgerEntry.objects.filter(date__lte=as_of_date)
    if branch is not None:
        qs = qs.filter(branch=branch)
    rows = list(
        qs.values("inventory_item_id", "warehouse_id").annotate(
            quantity=ExpressionWrapper(
                Sum("quantity_in", default=Decimal("0.0000")) - Sum("quantity_out", default=Decimal("0.0000")),
                output_field=DecimalField(max_digits=18, decimal_places=4),
            ),
            inventory_value_base=Sum("inventory_value_base", default=Decimal("0.00")),
        )
    )
    return {"as_of_date": as_of_date, "report_currency": DEFAULT_CURRENCY, "rows": rows}


def generate_fifo_layer_report(*, branch: UUID | None = None) -> list[InventoryValuationLayer]:
    qs = InventoryValuationLayer.objects.filter(costing_method="fifo").order_by("inventory_item_id", "warehouse_id", "acquisition_date")
    if branch is not None:
        qs = qs.filter(branch=branch)
    return list(qs)


def generate_weighted_average_cost_report(*, branch: UUID | None = None) -> list[dict]:
    qs = InventoryValuationLayer.objects.all()
    if branch is not None:
        qs = qs.filter(branch=branch)
    return list(
        qs.values("inventory_item_id", "warehouse_id").annotate(
            quantity=Sum("quantity_remaining", default=Decimal("0.0000")),
            value_base=Sum(
                ExpressionWrapper(F("quantity_remaining") * F("base_unit_cost"), output_field=DecimalField(max_digits=18, decimal_places=2)),
                default=Decimal("0.00"),
            ),
        )
    )


def generate_inventory_aging_report(*, branch: UUID | None = None) -> list[InventoryValuationLayer]:
    qs = InventoryValuationLayer.objects.all().order_by("acquisition_date")
    if branch is not None:
        qs = qs.filter(branch=branch)
    return list(qs)


def generate_nrv_exposure_report(*, branch: UUID | None = None) -> list[InventoryWriteDown]:
    qs = InventoryWriteDown.objects.all().order_by("-assessment_date")
    if branch is not None:
        qs = qs.filter(branch=branch)
    return list(qs)


def generate_inventory_write_down_report(*, branch: UUID | None = None) -> list[InventoryWriteDown]:
    return generate_nrv_exposure_report(branch=branch)


def generate_manufacturing_variance_report(*, branch: UUID | None = None) -> list[ManufacturingCostAllocation]:
    qs = ManufacturingCostAllocation.objects.all().order_by("-created_at")
    if branch is not None:
        qs = qs.filter(branch=branch)
    return list(qs)


def generate_stock_movement_ledger(*, inventory_item_id: UUID, warehouse_id: UUID, branch: UUID | None = None) -> list[InventoryLedgerEntry]:
    qs = InventoryLedgerEntry.objects.filter(inventory_item_id=inventory_item_id, warehouse_id=warehouse_id).order_by("date", "created_at")
    if branch is not None:
        qs = qs.filter(branch=branch)
    return list(qs)


def generate_landed_cost_allocation_report(*, branch: UUID | None = None) -> list[LandedCostAllocation]:
    qs = LandedCostAllocation.objects.all().order_by("-allocated_at")
    if branch is not None:
        qs = qs.filter(branch=branch)
    return list(qs)


def generate_inventory_turnover_report(*, branch: UUID | None = None) -> dict:
    valuation = generate_inventory_valuation_report(as_of_date=date.today(), branch=branch)
    total_value = sum((row["inventory_value_base"] for row in valuation["rows"]), Decimal("0.00"))
    return {"report_currency": DEFAULT_CURRENCY, "inventory_value_base": total_value}


def generate_slow_moving_inventory_report(*, branch: UUID | None = None) -> list[InventoryValuationLayer]:
    return generate_inventory_aging_report(branch=branch)


def generate_warehouse_valuation_report(*, as_of_date: date, branch: UUID | None = None) -> list[dict]:
    return generate_inventory_valuation_report(as_of_date=as_of_date, branch=branch)["rows"]


def generate_inventory_reconciliation_report(*, branch: UUID | None = None) -> dict:
    return {"report_currency": DEFAULT_CURRENCY, "write_downs": generate_inventory_write_down_report(branch=branch)}


def generate_grni_report(*, branch: UUID | None = None) -> list[dict]:
    from apps.ledgers.models import InventoryAccrual

    qs = InventoryAccrual.objects.filter(status="active").order_by("-accrual_date")
    if branch is not None:
        qs = qs.filter(branch=branch)
    return list(qs.values())


def generate_inventory_forecasting_support_report(*, branch: UUID | None = None) -> dict:
    return {"valuation": generate_inventory_turnover_report(branch=branch), "aging": generate_inventory_aging_report(branch=branch)}
