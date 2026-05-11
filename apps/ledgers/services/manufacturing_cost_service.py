from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.models import ManufacturingCostAllocation
from apps.ledgers.services.costing_service import allocate_manufacturing_overheads, calculate_batch_cost
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account


@transaction.atomic
def post_wip_consumption(*, production_order: str, posting_date, raw_material_cost: Decimal, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    wip_account = get_configured_account("manufacturing_wip", branch)
    inventory_account = get_configured_account("inventory_asset", branch)
    return create_and_post_journal(
        reference=f"WIP-CONS-{production_order}",
        journal_type="wip_consumption",
        posting_date=posting_date,
        description=f"WIP consumption {production_order}",
        source_module="inventory_manufacturing",
        source_id=production_order,
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"wip-consumption:{production_order}",
        lines=build_two_line_entry(
            debit_account_id=wip_account.id,
            credit_account_id=inventory_account.id,
            amount=raw_material_cost,
            currency=currency,
            description=f"WIP consumption {production_order}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )


@transaction.atomic
def complete_finished_goods(*, production_order: str, posting_date, total_cost: Decimal, branch: UUID | None, created_by_id: UUID | None, currency: str = "UGX"):
    wip_account = get_configured_account("manufacturing_wip", branch)
    finished_goods_account = get_configured_account("inventory_asset", branch)
    return create_and_post_journal(
        reference=f"FG-COMP-{production_order}",
        journal_type="finished_goods_completion",
        posting_date=posting_date,
        description=f"Finished goods completion {production_order}",
        source_module="inventory_manufacturing",
        source_id=f"{production_order}:complete",
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"finished-goods-complete:{production_order}",
        lines=build_two_line_entry(
            debit_account_id=finished_goods_account.id,
            credit_account_id=wip_account.id,
            amount=total_cost,
            currency=currency,
            description=f"Finished goods completion {production_order}",
            branch=branch,
            rate_date=posting_date,
        ),
        transaction_currency_code=currency,
    )


def calculate_production_variance(*, actual_cost: Decimal, standard_cost: Decimal) -> Decimal:
    return actual_cost - standard_cost


def allocate_factory_overheads(*, production_order: str, direct_cost_base: Decimal, overhead_pool: Decimal, activity_share: Decimal, output_quantity: Decimal, branch: UUID | None = None) -> ManufacturingCostAllocation:
    overhead = allocate_manufacturing_overheads(
        base_amount=direct_cost_base,
        overhead_pool=overhead_pool,
        activity_share=activity_share,
    )
    unit_cost = calculate_batch_cost(
        material_cost=direct_cost_base,
        labor_cost=Decimal("0.00"),
        overhead_cost=overhead,
        batch_quantity=output_quantity,
    )
    total_cost = direct_cost_base + overhead
    return ManufacturingCostAllocation.objects.create(
        production_order=production_order,
        direct_material_cost=direct_cost_base,
        variable_overhead=overhead,
        total_cost=total_cost,
        unit_cost=unit_cost,
        output_quantity=output_quantity,
        branch=branch,
    )
