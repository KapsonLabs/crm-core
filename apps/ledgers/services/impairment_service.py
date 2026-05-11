from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from django.db import transaction

from apps.ledgers.models import InventoryWriteDown
from apps.ledgers.services.helpers import build_two_line_entry, create_and_post_journal, get_configured_account
from apps.ledgers.services.valuation_service import calculate_nrv, perform_lower_of_cost_or_nrv_test, reverse_inventory_write_down


def calculate_inventory_nrv(*, estimated_selling_price: Decimal, completion_costs: Decimal, selling_costs: Decimal) -> Decimal:
    return calculate_nrv(
        estimated_selling_price=estimated_selling_price,
        completion_costs=completion_costs,
        selling_costs=selling_costs,
    )


def identify_obsolete_inventory(*, aging_days: int, threshold_days: int = 180) -> bool:
    return aging_days >= threshold_days


@transaction.atomic
def create_inventory_provision(
    *,
    inventory_item_id: UUID,
    warehouse_id: UUID,
    carrying_value: Decimal,
    nrv_value: Decimal,
    assessment_date,
    reason: str,
    branch: UUID | None,
    created_by_id: UUID | None,
) -> dict | None:
    write_down = perform_lower_of_cost_or_nrv_test(
        inventory_item_id=inventory_item_id,
        warehouse_id=warehouse_id,
        carrying_value=carrying_value,
        nrv_value=nrv_value,
        assessment_date=assessment_date,
        reason=reason,
        branch=branch,
    )
    if write_down is None:
        return None
    expense_account = get_configured_account("inventory_write_down_expense", branch)
    provision_account = get_configured_account("inventory_provision", branch)
    journal = create_and_post_journal(
        reference=f"NRV-{write_down.id}",
        journal_type="inventory_write_down",
        posting_date=assessment_date,
        description=reason,
        source_module="inventory_impairment",
        source_id=str(write_down.id),
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-write-down:{write_down.id}",
        lines=build_two_line_entry(
            debit_account_id=expense_account.id,
            credit_account_id=provision_account.id,
            amount=write_down.write_down_amount,
            currency="UGX",
            description=reason,
            branch=branch,
            rate_date=assessment_date,
        ),
        transaction_currency_code="UGX",
    )
    return {"write_down": write_down, "journal": journal}


@transaction.atomic
def reverse_inventory_provision(*, write_down_id: UUID, reversal_amount: Decimal, reversal_date, branch: UUID | None, created_by_id: UUID | None):
    write_down = reverse_inventory_write_down(write_down_id=write_down_id, reversal_amount=reversal_amount)
    provision_account = get_configured_account("inventory_provision", branch)
    recovery_income = get_configured_account("inventory_recovery_income", branch)
    journal = create_and_post_journal(
        reference=f"NRV-REV-{write_down_id}",
        journal_type="inventory_write_back",
        posting_date=reversal_date,
        description=f"Inventory write-back {write_down_id}",
        source_module="inventory_impairment",
        source_id=f"{write_down_id}:reversal",
        branch=branch,
        created_by_id=created_by_id,
        idempotency_key=f"inventory-write-back:{write_down_id}",
        lines=build_two_line_entry(
            debit_account_id=provision_account.id,
            credit_account_id=recovery_income.id,
            amount=reversal_amount,
            currency="UGX",
            description=f"Inventory write-back {write_down_id}",
            branch=branch,
            rate_date=reversal_date,
        ),
        transaction_currency_code="UGX",
    )
    return {"write_down": write_down, "journal": journal}
